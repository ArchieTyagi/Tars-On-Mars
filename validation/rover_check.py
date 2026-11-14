"""Check our map against where Perseverance actually drove.

1. Every point of the rover's drive inside our map: did we call it GO / CAUTION / NO-GO?
   (the rover drove there safely, so NO-GO there = a false alarm)
2. At each rover stop: our slope vs the tilt the rover measured itself.
Writes docs/rover_check.png and docs/rover_check.json.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LightSource, ListedColormap

from pipeline.layers import slope_deg
from planner.route import Site

ROOT = Path(__file__).resolve().parents[1]
ROVER = ROOT / "data" / "rover"


def drive_points(site, step_m=2.0):
    """Rover drive lines, filled in every ~2 m, keeping only points on our map."""
    pts, sols = [], []
    for f in json.load(open(ROVER / "M20_traverse.json"))["features"]:
        c = np.array(f["geometry"]["coordinates"])[:, :2]
        for a, b in zip(c[:-1], c[1:]):
            n = max(2, int(np.hypot(*(b - a)) / 0.00034 * 20 / step_m))  # ~20 m per 0.00034 deg
            for t in np.linspace(0, 1, n, endpoint=False):
                pts.append(a + t * (b - a)); sols.append(f["properties"]["sol"])
    pts = np.array(pts)
    cells = np.array([site.lonlat_to_cell(*p) for p in pts])
    inside = (cells[:, 0] >= 0) & (cells[:, 0] < site.zone.shape[0]) & (cells[:, 1] >= 0) & (cells[:, 1] < site.zone.shape[1])
    cells = cells[inside]
    _, keep = np.unique(cells, axis=0, return_index=True)  # each 4 m square once
    return cells[np.sort(keep)], np.array(sols)[inside][np.sort(keep)]


def main():
    site = Site()
    cells, sols = drive_points(site)
    out = {"rover_squares_on_map": int(len(cells)), "sols": [int(sols.min()), int(sols.max())]}
    for lim in (20, 15):
        site.set_limit(lim)
        z = site.zone[cells[:, 0], cells[:, 1]]
        out[f"limit_{lim}"] = {"go": float((z == 0).mean()), "caution": float((z == 1).mean()),
                               "nogo_false_alarm": float((z == 2).mean())}
    site.set_limit(None)
    zone_on_drive = site.zone[cells[:, 0], cells[:, 1]]

    # slope vs rover tilt at stops
    with rasterio.open(ROOT / "data" / "jezero" / "dtm.tif") as src:
        dem, tr = src.read(1), src.transform
    s1 = slope_deg(dem, 1.0)
    rows = []
    for f in json.load(open(ROVER / "M20_waypoints.json"))["features"]:
        p = f["properties"]
        if p.get("tilt") is None or p["dist_m"] <= 0:
            continue
        r, c = site.lonlat_to_cell(p["lon"], p["lat"])
        if not (0 <= r < site.zone.shape[0] and 0 <= c < site.zone.shape[1]):
            continue
        x, y = site.radius * np.radians(p["lon"]), site.radius * np.radians(p["lat"])
        rr, cc = int((y - tr.f) // tr.e), int((x - tr.c) // tr.a)
        win = s1[max(rr - 1, 0): rr + 2, max(cc - 1, 0): cc + 2]  # ~3 m, about the rover's size
        rows.append((p["tilt"], float(np.nanmean(win)), float(site.slope[r, c])))
    t = np.array(rows)
    out["rover_stops_on_map"] = int(len(t))
    out["tilt_vs_slope"] = {
        "rover_tilt_median": float(np.median(t[:, 0])), "rover_tilt_max": float(t[:, 0].max()),
        "our_1m_slope_median": float(np.median(t[:, 1])),
        "our_planning_slope_median": float(np.median(t[:, 2])),
        "corr_1m": float(np.corrcoef(t[:, 0], t[:, 1])[0, 1]),
        "mean_abs_err_1m_deg": float(np.mean(np.abs(t[:, 1] - t[:, 0]))),
        "planning_slope_ge_rover_tilt": float((t[:, 2] >= t[:, 0]).mean()),
    }
    (ROOT / "docs" / "rover_check.json").write_text(json.dumps(out, indent=1))

    fig, ax = plt.subplots(1, 2, figsize=(15, 7), gridspec_kw={"width_ratios": [1.15, 1]})
    shade = LightSource(315, 45).hillshade(np.nan_to_num(site.height), dx=4, dy=4, vert_exag=2)
    ax[0].imshow(shade, cmap="gray")
    zz = np.ma.masked_where(site.zone == 0, site.zone)
    ax[0].imshow(zz, cmap=ListedColormap(["#f5a623", "#d0021b"]), alpha=0.45, vmin=1, vmax=2)
    col = np.array(["#00e5ff", "#f5a623", "#ff00ff"])[zone_on_drive]
    ax[0].scatter(cells[:, 1], cells[:, 0], s=3, c=col)
    l20 = out["limit_20"]
    ax[0].set_title(f"Perseverance's real drive (sols {out['sols'][0]}-{out['sols'][1]}) on our map\n"
                    f"{l20['go']:.1%} GO, {l20['caution']:.1%} CAUTION, {l20['nogo_false_alarm']:.1%} NO-GO (false alarm)")
    ax[0].axis("off")
    ts = out["tilt_vs_slope"]
    ax[1].scatter(t[:, 0], t[:, 1], s=14, label="our 1 m slope (3 m around the stop)")
    ax[1].scatter(t[:, 0], t[:, 2], s=14, marker="x", label="our planning slope (worst in 4 m)")
    m = max(t.max(), 5) + 1
    ax[1].plot([0, m], [0, m], "k--", lw=1, label="perfect match")
    ax[1].set_xlabel("tilt the rover measured itself (deg)"); ax[1].set_ylabel("slope from our map (deg)")
    ax[1].set_title(f"{len(t)} rover stops | 1 m slope off by {ts['mean_abs_err_1m_deg']:.1f} deg on average\n"
                    f"planning slope >= real tilt at {ts['planning_slope_ge_rover_tilt']:.0%} of stops (errs on the safe side)")
    ax[1].legend(); ax[1].set_xlim(0, m); ax[1].set_ylim(0, m); ax[1].set_aspect("equal")
    fig.savefig(ROOT / "docs" / "rover_check.png", dpi=100, bbox_inches="tight")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
