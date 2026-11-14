"""Radio line-of-sight between the suit and base.

Direct radio needs a clear straight line. For each point we check the terrain
between it and base, including the curve of Mars (radius 3390 km: over 5 km the
ground in the middle bulges up ~0.9 m, which matters with antennas this short).
No relays, no bouncing off terrain: this is the simple, conservative case.
"""
import numpy as np

MARS_RADIUS_M = 3389500.0


def line_clear(height, dx, dy, a, bs, h_a, h_b, samples=256, radius_m=MARS_RADIUS_M):
    """a = (row, col) of base, bs = array of (row, col) targets.
    h_a / h_b = antenna height above ground at base / at each target.
    Returns True where the straight line between antennas clears the terrain."""
    h = np.nan_to_num(height, nan=float(np.nanmin(height)))
    bs = np.atleast_2d(bs)
    r0, c0 = a
    t = np.linspace(0, 1, samples)[None, :]                       # (1, S)
    rr = r0 + (bs[:, :1] - r0) * t                                # (N, S)
    cc = c0 + (bs[:, 1:2] - c0) * t
    ground = h[np.rint(rr).astype(int), np.rint(cc).astype(int)]
    za = h[r0, c0] + h_a
    zb = h[bs[:, 0], bs[:, 1]] + h_b
    dist = np.hypot((bs[:, 0] - r0) * dy, (bs[:, 1] - c0) * dx)[:, None]
    line = za + (zb[:, None] - za) * t
    bulge = t * (1 - t) * dist ** 2 / (2 * radius_m)        # ground rises toward the middle
    inner = (t > 0) & (t < 1)
    blocked = ((ground + bulge) > line) & inner
    return ~blocked.any(axis=1)


def route_contact(site, base_cell, cells, elapsed_h, base_ant_m, suit_ant_m):
    p = np.array(cells)
    ok = np.zeros(len(p), bool)
    for s in range(0, len(p), 2000):  # chunks keep memory small
        ok[s:s + 2000] = line_clear(site.height, site.dx, site.dy, base_cell, p[s:s + 2000], base_ant_m, suit_ant_m,
                                    radius_m=getattr(site, "radius", MARS_RADIUS_M))
    gaps, i = [], 0
    while i < len(p):
        if not ok[i]:
            j = i
            while j + 1 < len(p) and not ok[j + 1]:
                j += 1
            gaps.append({"from": i, "to": j, "lonlat": site.cell_to_lonlat(*p[i]),
                         "elapsed_h": round(float(elapsed_h[i]), 2),
                         "duration_h": round(float(elapsed_h[j] - elapsed_h[i]), 2)})
            i = j + 1
        else:
            i += 1
    return {"base_antenna_m": base_ant_m, "suit_antenna_m": suit_ant_m,
            "in_contact": [bool(x) for x in ok], "share_in_contact": round(float(ok.mean()), 3),
            "blackouts": gaps, "longest_blackout_h": max([g["duration_h"] for g in gaps], default=0.0)}


def viewshed(site, base_cell, base_ant_m, suit_ant_m, step=4):
    """Where base can hear a suit, on a coarser grid (every `step` cells)."""
    rows, cols = np.mgrid[0:site.height.shape[0]:step, 0:site.height.shape[1]:step]
    pts = np.stack([rows.ravel(), cols.ravel()], axis=1)
    out = np.zeros(len(pts), bool)
    for s in range(0, len(pts), 4000):
        out[s:s + 4000] = line_clear(site.height, site.dx, site.dy, base_cell, pts[s:s + 4000], base_ant_m, suit_ant_m,
                                    radius_m=getattr(site, "radius", MARS_RADIUS_M))
    return out.reshape(rows.shape)
