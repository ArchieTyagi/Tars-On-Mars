"""Safest walking route: base -> stops (best order) -> base."""
import itertools
import math
from pathlib import Path

import numpy as np
from skimage.graph import MCP_Geometric

from pipeline.costmap import CAUTION, NOGO, classify, load_rules, walk_cost

ROOT = Path(__file__).resolve().parents[1]


class Site:
    def __init__(self, name="jezero", rules=None):
        d = np.load(ROOT / "data" / name / "layers.npz")
        self.slope, self.rough, self.height = d["slope"], d["rough"], d["height"]
        self.a, self.b, self.x0, self.d, self.e, self.y0 = d["transform"]
        self.rules = rules or load_rules()
        self.radius = 3396190.0
        self.set_limit(None)

    def set_limit(self, limit_deg):
        """What-if: force one slope limit everywhere (the slider). None = rules file."""
        self.zone, _ = classify(self.slope, self.rules, limit_override=limit_deg)
        self.cost = walk_cost(self.slope, self.zone, self.rules)

    # map position <-> grid cell
    def lonlat_to_cell(self, lon, lat):
        x, y = self.radius * math.radians(lon), self.radius * math.radians(lat)
        return int((y - self.y0) // self.e), int((x - self.x0) // self.a)

    def cell_to_lonlat(self, r, c):
        x = self.x0 + (c + 0.5) * self.a
        y = self.y0 + (r + 0.5) * self.e
        return math.degrees(x / self.radius), math.degrees(y / self.radius)

    def _check(self, cell, label):
        r, c = cell
        if not (0 <= r < self.zone.shape[0] and 0 <= c < self.zone.shape[1]):
            raise ValueError(f"{label} is outside the map")
        if self.zone[r, c] == NOGO:
            raise ValueError(f"{label} is on NO-GO ground ({self.slope[r, c]:.0f} deg)")

    def leg_stats(self, path):
        p = np.array(path)
        step = np.hypot(*np.diff(p, axis=0).T) * self.a
        s = self.slope[p[:, 0], p[:, 1]]
        mid = (s[1:] + s[:-1]) / 2
        speed = self.rules["walk_speed_kmh"] * 1000
        hours = float(np.sum(step / speed * (1 + self.rules["slope_slowdown_per_deg"] * mid)))
        z = self.zone[p[:, 0], p[:, 1]]
        return float(step.sum()), hours, float(s.max()), int((z == CAUTION).sum())

    def plan(self, base, stops):
        """base, stops = (lon, lat). Returns the best loop and its numbers."""
        pts = [self.lonlat_to_cell(*base)] + [self.lonlat_to_cell(*s) for s in stops]
        for i, p in enumerate(pts):
            self._check(p, "base" if i == 0 else f"stop {i}")

        costs = np.where(self.cost < 0, np.inf, self.cost)
        mcps, table = [], np.full((len(pts), len(pts)), np.inf)
        for i, p in enumerate(pts):
            m = MCP_Geometric(costs, fully_connected=True)
            cum, _ = m.find_costs([p])
            mcps.append(m)
            for j, q in enumerate(pts):
                table[i, j] = cum[q]
        if not np.isfinite(table).all():
            bad = [i for i in range(1, len(pts)) if not np.isfinite(table[0, i])]
            raise ValueError(f"no safe way to stop(s) {bad}")

        best = min(itertools.permutations(range(1, len(pts))),
                   key=lambda o: sum(table[a, b] for a, b in zip((0,) + o, o + (0,))))
        order = (0,) + best + (0,)

        legs, full = [], []
        for a, b in zip(order, order[1:]):
            path = mcps[a].traceback(pts[b])
            dist, hrs, smax, caut = self.leg_stats(path)
            legs.append({"from": a, "to": b, "km": round(dist / 1000, 2), "hours": round(hrs, 2),
                         "max_slope": round(smax, 1), "caution_cells": caut})
            full += path if not full else path[1:]

        hours = sum(l["hours"] for l in legs)
        usable = self.rules["o2_hours"] * (1 - self.rules["o2_reserve"])
        return {
            "order": list(best),
            "km": round(sum(l["km"] for l in legs), 2),
            "hours": round(hours, 2),
            "max_slope": max(l["max_slope"] for l in legs),
            "o2_ok": hours <= usable,
            "o2_margin_h": round(usable - hours, 2),
            "legs": legs,
            "path": [self.cell_to_lonlat(r, c) for r, c in full],
        }
