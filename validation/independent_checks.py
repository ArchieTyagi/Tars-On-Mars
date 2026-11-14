"""Check our numbers against things we did not compute ourselves.

1. Moon slope vs the slope map NASA's LOLA team publishes for the same site.
2. Route costs and stop order vs a second shortest-path solver (scipy Dijkstra on every cell).
3. Route length vs great-circle distance on the Mars sphere.
4. Photo vs height map: does the photo sit where the height map says the hills are?
5. Height at the landing site vs the rover's own position file.
Writes docs/independent_checks.json.

Run: python -m validation.independent_checks
"""
import itertools
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

from pipeline.layers import slope_deg
from planner.route import Site

ROOT = Path(__file__).resolve().parents[1]


def moon_slope_vs_lola():
    with rasterio.open(ROOT / "data/moon/Site01_final_adj_5mpp_surf.tif") as d:
        z = d.read(1).astype("float64")
    with rasterio.open(ROOT / "data/moon/Site01_final_adj_5mpp_slp.tif") as d:
        ref = d.read(1).astype("float64")
    ours = slope_deg(z, 5.0).astype("float64")
    m = np.isfinite(ours) & np.isfinite(ref)
    diff = np.abs(ours[m] - ref[m])
    return {"cells": int(m.sum()), "median_abs_diff_deg": float(np.median(diff)),
            "p95_abs_diff_deg": float(np.percentile(diff, 95)),
            "agree_on_over_20_deg": float(np.mean((ours[m] >= 20) == (ref[m] >= 20)))}


def second_solver(s, base, stops):
    H, W = s.zone.shape
    cost = np.where(s.cost < 0, np.inf, s.cost).astype("float64")
    idx = np.arange(H * W).reshape(H, W)
    rows, cols, vals = [], [], []
    for dr, dc in [(0, 1), (1, 0), (1, 1), (1, -1)]:
        a = idx[0:H - dr, max(0, -dc):W - max(0, dc)].ravel()
        b = idx[dr:H, max(0, dc):W - max(0, -dc)].ravel()
        w = math.hypot(dr * s.dy, dc * s.dx) * (cost.flat[a] + cost.flat[b]) / 2
        ok = np.isfinite(w)
        rows += [a[ok], b[ok]]; cols += [b[ok], a[ok]]; vals += [w[ok], w[ok]]
    g = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(H * W, H * W)).tocsr()
    pts = [s.lonlat_to_cell(*base)] + [s.lonlat_to_cell(*p) for p in stops]
    d = dijkstra(g, indices=[idx[p] for p in pts])
    table = np.array([[d[i, idx[q]] for q in pts] for i in range(len(pts))])
    ours = np.zeros_like(table)
    for i, p in enumerate(pts):
        cum, _ = s._mcp(cost).find_costs([p])
        ours[i] = [cum[q] for q in pts]
    best = min(itertools.permutations(range(1, len(pts))),
               key=lambda o: sum(table[a, b] for a, b in zip((0,) + o, o + (0,))))
    plan = s.plan(base, stops)
    R = s.radius

    def gc(a, b):
        (l1, p1), (l2, p2) = [(math.radians(u), math.radians(v)) for u, v in (a, b)]
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h))
    km = sum(gc(a, b) for a, b in zip(plan["path"], plan["path"][1:])) / 1000
    return {"cells": int(H * W), "max_relative_cost_diff": float(np.max(np.abs(ours - table) / np.maximum(table, 1e-9))),
            "stop_order_second_solver": list(best), "stop_order_planner": plan["order"],
            "km_planner": plan["km"], "km_great_circle": round(km, 3)}


def landing_height(s):
    from pipeline import rover
    t = rover.load()
    r, c = s.lonlat_to_cell(*t["landing"]["lonlat"])
    way = json.load(open(ROOT / "data/rover/M20_waypoints.json"))["features"][0]["properties"]
    return {"our_height_m": round(float(s.height[r, c]), 2), "rover_file_elev_geoid_m": way["elev_geoid"]}


def main():
    from pipeline import photo
    s = Site("jezero")
    out = {"moon_slope_vs_lola": moon_slope_vs_lola(),
           "second_solver": second_solver(s, (77.4508, 18.4447), [(77.46, 18.47), (77.43, 18.455), (77.445, 18.43)]),
           "photo_vs_height_map": photo.registration_check("jezero"),
           "landing_height": landing_height(s)}
    out["photo_vs_height_map"] = {k: (float(v) if not isinstance(v, int) else v) for k, v in out["photo_vs_height_map"].items()}
    (ROOT / "docs" / "independent_checks.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
