"""Helicopter scouting: check the least certain parts of a route before anyone walks it.

1. score every point on the route by how unsure the map is there
2. pick the worst stretches as scout targets
3. plan helicopter hops from base, each hop no longer than the flight range
4. after the flight, mark what was seen (safe / blocked) and re-plan

Precedent: NASA's Ingenuity helicopter scouted ahead of Perseverance at Jezero;
its longest single flight was about 700 m.
"""
import math

import numpy as np

from pipeline.costmap import CAUTION, NOGO

BOUNDARY_M = 40       # 1:75,000 geologic map borders can be tens of meters off
ROUGH_STEP_M = 0.5    # height jump inside a 4 m square beyond what the slope explains
EDGE_DEG = 2.0        # slope within this of its limit could flip either way


def uncertainty(site, cells, light=None):
    """Score 0..n for each route point, plus the reasons."""
    p = np.array(cells)
    r, c = p[:, 0], p[:, 1]
    reasons = [[] for _ in range(len(p))]
    score = np.zeros(len(p))

    # slope right at the edge of its limit
    edge = np.abs(site.limit[r, c] - site.slope[r, c]) <= EDGE_DEG
    # rough: height jump inside the square that slope alone does not explain
    explained = site.dx * math.sqrt(2) * np.tan(np.radians(np.nan_to_num(site.slope[r, c])))
    rough = (site.rough[r, c] - explained) > ROUGH_STEP_M
    # near a ground-type border
    near_border = np.zeros(len(p), bool)
    if site.ground is not None:
        k = int(round(BOUNDARY_M / min(site.dx, site.dy)))
        g = site.ground
        for i, (rr, cc) in enumerate(p):
            win = g[max(rr - k, 0): rr + k + 1, max(cc - k, 0): cc + k + 1]
            near_border[i] = (win != g[rr, cc]).any()
    # near a hazard that is in shadow when you get there
    hidden = np.zeros(len(p), bool)
    for w in (light or {}).get("hidden_hazards", []):
        hidden[w["from"]: w["to"] + 1] = True

    for mask, why, weight in ((edge, "slope at the edge of its limit", 1.0),
                              (rough, "rough ground, possible boulders or a step", 1.0),
                              (near_border, "near a ground-type border (map may be off here)", 0.5),
                              (hidden, "hazard nearby in shadow", 1.5)):
        score[mask] += weight
        for i in np.nonzero(mask)[0]:
            reasons[i].append(why)
    return score, reasons


def pick_targets(site, path_lonlat, cells, score, reasons, elapsed_h, max_targets=6, spacing_m=150):
    """Highest-scoring stretches, at least `spacing_m` apart along the route."""
    p = np.array(cells)
    d = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(p[:, 0]) * site.dy, np.diff(p[:, 1]) * site.dx))])
    order = np.argsort(-score, kind="stable")
    chosen = []
    for i in order:
        if score[i] <= 0 or len(chosen) >= max_targets:
            break
        if all(abs(d[i] - d[j]) >= spacing_m for j in chosen):
            chosen.append(int(i))
    chosen.sort(key=lambda i: d[i])
    return [{"index": i, "lonlat": list(path_lonlat[i]), "score": float(score[i]),
             "reasons": sorted(set(reasons[i])), "km_along": round(d[i] / 1000, 2),
             "elapsed_h": round(float(elapsed_h[i]), 2)} for i in chosen]


def flight_plan(site, base_lonlat, targets, range_m=700.0):
    """Hops base -> target 1 -> target 2 ... -> base, splitting any hop longer than the range."""
    def xy(ll):
        r, c = site.lonlat_to_cell(*ll)
        return np.array([c * site.dx, r * site.dy])

    stops = [list(base_lonlat)] + [t["lonlat"] for t in targets] + [list(base_lonlat)]
    hops, total = [], 0.0
    for a, b in zip(stops, stops[1:]):
        dist = float(np.hypot(*(xy(b) - xy(a))))
        n = max(1, math.ceil(dist / range_m))
        for k in range(n):
            hops.append({"from": a if k == 0 else "relay", "to": b if k == n - 1 else "relay",
                         "m": round(dist / n)})
        total += dist
    return {"flights": len(hops), "total_km": round(total / 1000, 2), "range_m": range_m, "hops": hops}


def apply_observations(site, observations):
    """What the helicopter saw overrides the map: 'blocked' -> NO-GO, 'safe' -> CAUTION at worst
    (still never GO on a slope over its limit). Returns a new Site; the original is untouched."""
    import copy
    s = copy.copy(site)
    s.zone = site.zone.copy()
    for o in observations:
        r, c = s.lonlat_to_cell(*o["lonlat"])
        k = max(1, int(round(o.get("radius_m", 20) / min(s.dx, s.dy))))
        rr, cc = np.ogrid[-k: k + 1, -k: k + 1]
        disk = (rr ** 2 + cc ** 2) <= k * k
        r0, c0 = max(r - k, 0), max(c - k, 0)
        win = s.zone[r0: r + k + 1, c0: c + k + 1]
        m = disk[(r0 - (r - k)):(r0 - (r - k)) + win.shape[0], (c0 - (c - k)):(c0 - (c - k)) + win.shape[1]]
        if o["finding"] == "blocked":
            win[m] = NOGO
        elif o["finding"] == "safe":
            over = s.slope[r0: r + k + 1, c0: c + k + 1] >= s.limit[r0: r + k + 1, c0: c + k + 1]
            win[m & ~over & (win == NOGO)] = CAUTION
    from pipeline.costmap import walk_cost
    s.cost = walk_cost(s.slope, s.zone, s.rules)
    return s
