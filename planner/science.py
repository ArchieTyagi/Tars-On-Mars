"""Science stops worth walking to: patches of an identified mineral that you can reach and
get back from on your oxygen.

Minerals come from the CRISM map (Parente et al. 2021, 36 m pixels). We only suggest
high-confidence patches at least two mineral-map pixels big, and we name the spot on the
patch that is cheapest to walk to. Minerals that form in water come first: they are why
Jezero was chosen as a landing site.
"""
import numpy as np
from scipy import ndimage

from pipeline.costmap import NOGO
from pipeline.minerals import KEY

# code -> (order, why it is worth a stop). Water-made minerals first.
WHY = {
    2: (0, "carbonate: forms in water and is good at preserving traces of past life"),
    6: (1, "carbonate with an extra 2.2 micron signal: water-made, with hydrated silica or aluminium clay mixed in"),
    3: (2, "clay (smectite): forms when water alters rock, and clays hold on to organic matter"),
    9: (3, "clay (kaolinite): forms where a lot of water flowed through the rock"),
    10: (4, "clay (smectite): forms when water alters rock, and clays hold on to organic matter"),
    4: (5, "olivine partly turned to clay: volcanic rock caught while water was changing it"),
    5: (6, "olivine or clay with an extra 2.2 micron signal: a sign of hydrated silica or aluminium clay"),
    1: (7, "olivine: a volcanic mineral that water breaks down fast, so it shows how dry this rock stayed"),
    7: (8, "pyroxene (high calcium): a volcanic mineral that tells what kind of lava made this rock"),
    8: (9, "pyroxene (low calcium): a volcanic mineral that tells what kind of lava made this rock"),
}
CRISM_PIXEL_M = 36.0


def suggest(site, base, n=5, min_sep_m=250.0, min_patch_m2=2 * CRISM_PIXEL_M ** 2):
    """Up to n stops, each: lonlat, mineral, confidence, why, round_trip_h (walking there and back
    the way the planner would route it), patch_m2. One of each kind of mineral first, then the nearest rest.
    Every stop fits the oxygen budget on its own (walk there, work at the stop, walk back)."""
    if getattr(site, "minerals", None) is None:
        return []
    b = site.lonlat_to_cell(*base)
    site._check(b, "base")
    costs = np.where(site.cost < 0, np.inf, site.cost)
    mcp = site._mcp(costs)
    cum, _ = mcp.find_costs([b])
    usable = site.rules["o2_hours"] * (1 - site.rules["o2_reserve"])
    stop_h = float(site.rules.get("stop_minutes", 0)) / 60.0
    cell_m2 = site.dx * site.dy
    walkable = (site.zone != NOGO) & np.isfinite(cum)

    patches = []  # (order, cost to walk there, code, cell, area)
    for code, (order, _) in WHY.items():
        labels, k = ndimage.label(site.minerals == code)
        if k == 0:
            continue
        idx = np.arange(1, k + 1)
        area = ndimage.sum_labels(np.ones(labels.shape), labels, idx) * cell_m2
        big = idx[area >= min_patch_m2]
        if len(big) == 0:
            continue
        masked = np.where(walkable & np.isin(labels, big), cum, np.inf)
        best = ndimage.minimum_position(masked, labels, big)
        for lab, cell in zip(big, best):
            if np.isfinite(masked[cell]):
                patches.append((order, float(cum[cell]), code, tuple(int(v) for v in cell), float(area[lab - 1])))

    chosen = []

    def far_enough(cell):
        return all(np.hypot((cell[0] - c[0]) * site.dy, (cell[1] - c[1]) * site.dx) >= min_sep_m for c in chosen_cells)

    def try_add(p):
        order, _, code, cell, area = p
        if cell == b or not far_enough(cell):
            return False
        _, hrs, _, _ = site.leg_stats(mcp.traceback(cell))
        if 2 * hrs + stop_h > usable:
            return False
        chosen_cells.append(cell)
        chosen.append({"lonlat": list(site.cell_to_lonlat(*cell)), "mineral": KEY[code - 1][0], "confidence": "high",
                       "why": WHY[code][1], "round_trip_h": round(2 * hrs, 2), "patch_m2": round(area)})
        return True

    chosen_cells = []
    by_kind = sorted(patches)  # water minerals first, nearest patch of each kind first
    seen = set()
    for p in by_kind:           # pass 1: one of each kind
        if len(chosen) >= n:
            break
        if p[2] not in seen and try_add(p):
            seen.add(p[2])
    used = set(chosen_cells)
    for p in sorted(patches, key=lambda p: p[1]):   # pass 2: fill up with the nearest that are left
        if len(chosen) >= n:
            break
        if p[3] not in used:
            try_add(p)
    return chosen
