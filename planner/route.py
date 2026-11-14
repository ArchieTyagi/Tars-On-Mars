"""Safest walking route: base -> stops (best order) -> base."""
import copy
import itertools
import math
from pathlib import Path

import numpy as np
from skimage.graph import MCP_Geometric

from pipeline.costmap import CAUTION, NOGO, classify, load_rules, walk_cost
from pipeline.sun import MARS_HOUR_IN_EARTH_HOURS, dark_at, sun_positions

ROOT = Path(__file__).resolve().parents[1]


class Site:
    def __init__(self, name="jezero", rules=None):
        d = np.load(ROOT / "data" / name / "layers.npz")
        self.slope, self.rough, self.height = d["slope"], d["rough"], d["height"]
        self.name = name
        self.a, self.b, self.x0, self.d, self.e, self.y0 = d["transform"]
        self.radius = float(d["radius"]) if "radius" in d else 3396190.0
        self.body = str(d["body"]) if "body" in d else "mars"
        self.crs = str(d["crs"])
        se = d["slope_err"] if "slope_err" in d else None
        self.slope_err = se if se is not None and np.isfinite(se).any() else None
        self.set_projection(self.crs, self.radius)
        mf = ROOT / "data" / name / "minerals.npz"
        self.minerals = np.load(mf)["code"] if mf.exists() else None
        kx = float(d["kx"]) if "kx" in d else 1.0
        self.ground = d["ground"] if "ground" in d else None
        self.dx, self.dy = self.a * kx, abs(self.e)  # real ground size of a cell, meters
        self.rules = rules or load_rules()
        self.set_limit(None)

    def set_projection(self, crs, radius):
        """Map coordinates <-> lon/lat for this body (works for any projection pyproj knows)."""
        from pyproj import Transformer
        self.crs, self.radius = crs, radius
        geo = f"+proj=longlat +R={radius} +no_defs"
        self._to_xy = Transformer.from_crs(geo, crs, always_xy=True)
        self._to_ll = Transformer.from_crs(crs, geo, always_xy=True)

    def set_limit(self, limit_deg):
        """What-if: force one slope limit everywhere (the slider). None = rules file."""
        self.zone, self.limit = classify(self.slope, self.rules, self.ground, limit_override=limit_deg)
        self.cost = walk_cost(self.slope, self.zone, self.rules)

    # map position <-> grid cell
    def lonlat_to_cell(self, lon, lat):
        x, y = self._to_xy.transform(lon, lat)
        return int((y - self.y0) // self.e), int((x - self.x0) // self.a)

    def cell_to_lonlat(self, r, c):
        x = self.x0 + (c + 0.5) * self.a
        y = self.y0 + (r + 0.5) * self.e
        lon, lat = self._to_ll.transform(x, y)
        return float(lon), float(lat)

    def _check(self, cell, label):
        r, c = cell
        the = label[0].upper() + label[1:] if label[-1].isdigit() else f"The {label}"
        if not (0 <= r < self.zone.shape[0] and 0 <= c < self.zone.shape[1]):
            raise ValueError(f"{the} is outside the map data.")
        if self.zone[r, c] == NOGO:
            raise ValueError(f"{the} is on NO-GO ground ({self.slope[r, c]:.0f} deg slope). Pick a spot nearby.")

    def time_cost(self):
        """Hours per meter walked on each cell, inf on NO-GO."""
        speed = self.rules["walk_speed_kmh"] * 1000
        t = 1.0 / speed * (1 + self.rules["slope_slowdown_per_deg"] * np.nan_to_num(self.slope, nan=90.0))
        return np.where(self.zone == NOGO, np.inf, t)

    def _mcp(self, costs):
        return MCP_Geometric(costs, fully_connected=True, sampling=(self.dy, self.dx))

    def _steps_m(self, p):
        d = np.diff(p, axis=0)
        return np.hypot(d[:, 0] * self.dy, d[:, 1] * self.dx)

    def home_field(self, base):
        """Hours to walk straight back to base from every cell (safest way, inf = can't)."""
        m = self._mcp(self.time_cost())
        hours, _ = m.find_costs([self.lonlat_to_cell(*base)])
        return hours

    def safe_range(self, base):
        """Cells you can walk to AND get back from on usable oxygen."""
        usable = self.rules["o2_hours"] * (1 - self.rules["o2_reserve"])
        return self.home_field(base) * 2 + float(self.rules.get("stop_minutes", 0)) / 60.0 <= usable

    def leg_stats(self, path):
        p = np.array(path)
        step = self._steps_m(p)
        s = self.slope[p[:, 0], p[:, 1]]
        mid = (s[1:] + s[:-1]) / 2
        speed = self.rules["walk_speed_kmh"] * 1000
        hours = float(np.sum(step / speed * (1 + self.rules["slope_slowdown_per_deg"] * mid)))
        z = self.zone[p[:, 0], p[:, 1]]
        return float(step.sum()), hours, float(s.max()), int((z == CAUTION).sum())

    def with_settings(self, **settings):
        """Same map, different mission settings (oxygen, reserve, speed). Nothing is copied but the rules."""
        s = copy.copy(self)
        s.rules = {**self.rules, **{k: v for k, v in settings.items() if v is not None}}
        return s

    def light_check(self, cells, elapsed_h, ls_deg, start_ltst_h, near_m=12):
        """Sun along the walk. The sun moves while you walk, so each point uses the sun
        at the moment you reach it. Flags stretches that pass close to NO-GO ground
        that is dark right then: you may not see the drop until you're at it."""
        p = np.array(cells)
        lat = float(np.mean([self.cell_to_lonlat(*p[0])[1], self.cell_to_lonlat(*p[-1])[1]]))
        ltst = start_ltst_h + np.asarray(elapsed_h) / MARS_HOUR_IN_EARTH_HOURS
        el, az = sun_positions(lat, ls_deg, ltst)
        dark_here = dark_at(self.height, self.dx, self.dy, p[:, 0], p[:, 1], el, az)

        # NO-GO cells near each route point, and whether any of them are dark at that moment
        rad = int(round(near_m / min(self.dx, self.dy)))
        nogo = self.zone == NOGO
        hidden = np.zeros(len(p), bool)
        for i, (r, c) in enumerate(p):
            win = nogo[max(r - rad, 0): r + rad + 1, max(c - rad, 0): c + rad + 1]
            if not win.any():
                continue
            rr, cc = np.nonzero(win)
            rr, cc = rr + max(r - rad, 0), cc + max(c - rad, 0)
            n = len(rr)
            hidden[i] = dark_at(self.height, self.dx, self.dy, rr, cc,
                                np.full(n, el[i]), np.full(n, az[i])).any()

        # merge into stretches
        warnings = []
        i = 0
        while i < len(p):
            if hidden[i]:
                j = i
                while j + 1 < len(p) and hidden[j + 1]:
                    j += 1
                warnings.append({"from": i, "to": j, "lonlat": self.cell_to_lonlat(*p[i]),
                                 "elapsed_h": round(float(elapsed_h[i]), 2),
                                 "sun_el": round(float(el[i]), 1),
                                 "note": "NO-GO ground within 12 m is in shadow here, the drop may be hard to see"})
                i = j + 1
            else:
                i += 1
        return {
            "ls": ls_deg, "start_ltst_h": start_ltst_h,
            "end_ltst_h": round(float(ltst[-1] % 24), 2),
            "sun_el_start": round(float(el[0]), 1), "sun_el_end": round(float(el[-1]), 1),
            "low_sun": bool((el < 15).any()),
            "starts_in_dark": bool(el[0] <= 0),
            "sunset_before_home": bool(el[0] > 0 and (el <= 0).any()),
            "ends_in_dark": bool(el[-1] <= 0),
            "dark": [bool(x) for x in dark_here],
            "hidden_hazards": warnings,
        }

    def plan(self, base, stops, ls_deg=None, start_ltst_h=None):
        """base, stops = (lon, lat). Returns the best loop and its numbers.
        Give ls_deg (season) + start_ltst_h (Mars local time you set off) for the sun check."""
        pts = [self.lonlat_to_cell(*base)] + [self.lonlat_to_cell(*s) for s in stops]
        for i, p in enumerate(pts):
            self._check(p, "base" if i == 0 else f"stop {i}")

        costs = np.where(self.cost < 0, np.inf, self.cost)
        mcps, table = [], np.full((len(pts), len(pts)), np.inf)
        for i, p in enumerate(pts):
            m = self._mcp(costs)
            cum, _ = m.find_costs([p])
            mcps.append(m)
            for j, q in enumerate(pts):
                table[i, j] = cum[q]
        if not np.isfinite(table).all():
            bad = [i for i in range(1, len(pts)) if not np.isfinite(table[0, i])]
            names = ", ".join(f"stop {i}" for i in bad)
            raise ValueError(f"There's no safe way to reach {names} from base with these slope limits. "
                             "Move it, or try a higher slope limit to see what blocks it.")

        best = min(itertools.permutations(range(1, len(pts))),
                   key=lambda o: sum(table[a, b] for a, b in zip((0,) + o, o + (0,))))
        order = (0,) + best + (0,)

        legs, full, arrive = [], [], []
        for a, b in zip(order, order[1:]):
            path = mcps[a].traceback(pts[b])
            dist, hrs, smax, caut = self.leg_stats(path)
            legs.append({"from": a, "to": b, "km": round(dist / 1000, 2), "hours": round(hrs, 2),
                         "max_slope": round(smax, 1), "caution_cells": caut})
            full += path if not full else path[1:]
            arrive.append(len(full) - 1)  # index where this leg ends (a stop, or base at the very end)

        walk_hours = sum(l["hours"] for l in legs)
        stop_h = float(self.rules.get("stop_minutes", 0)) / 60.0
        n_stops = len(pts) - 1
        hours = walk_hours + n_stops * stop_h  # whole outing: walking + time spent working at each stop
        usable = self.rules["o2_hours"] * (1 - self.rules["o2_reserve"])
        home = self.home_field(base)
        p = np.array(full)
        step = self._steps_m(p)
        s = self.slope[p[:, 0], p[:, 1]]
        dt = step / (self.rules["walk_speed_kmh"] * 1000) * (1 + self.rules["slope_slowdown_per_deg"] * (s[1:] + s[:-1]) / 2)
        elapsed = np.concatenate([[0.0], np.cumsum(dt)])
        for i in arrive[:-1]:          # time at each stop is spent before walking on
            elapsed[i + 1:] += stop_h
        back = home[p[:, 0], p[:, 1]]
        margin = usable - elapsed - back
        ponr = None
        bad = np.where(margin < 0)[0]
        if len(bad):
            i = int(bad[0])
            ponr = {"index": i, "lonlat": self.cell_to_lonlat(*full[i]),
                    "elapsed_h": round(float(elapsed[i]), 2),
                    "note": "turn back before this point or you can't reach base on usable oxygen"}
        light = (self.light_check(full, elapsed, ls_deg, start_ltst_h)
                 if ls_deg is not None and start_ltst_h is not None and self.body == "mars" else None)
        from planner.scout import flight_plan, pick_targets, uncertainty
        path_ll = [self.cell_to_lonlat(r, c) for r, c in full]
        score, why = uncertainty(self, full, light)
        targets = pick_targets(self, path_ll, full, score, why, elapsed)
        scout = {"targets": targets, "uncertain_share": round(float((score > 0).mean()), 3),
                 **flight_plan(self, base, targets, self.rules.get("scout_range_m", 700.0))}
        weather = None
        if self.body == "mars" and ls_deg is not None and start_ltst_h is not None:
            from pipeline.mars_time import MARS_HOUR_IN_EARTH_HOURS as _mh
            from pipeline.weather import summary
            weather = summary(ls_deg, start_ltst_h + np.asarray(elapsed) / _mh)
        from planner.radio import route_contact
        radio = route_contact(self, pts[0], full, elapsed,
                              float(self.rules.get("base_antenna_m", 3.0)), float(self.rules.get("suit_antenna_m", 2.0)))
        stop_minerals = None
        if getattr(self, "minerals", None) is not None:
            from pipeline.minerals import name_of
            stop_minerals = []
            for i, p in enumerate(pts[1:], start=1):
                n, conf = name_of(int(self.minerals[p]))
                stop_minerals.append({"stop": i, "mineral": n, "confidence": conf})
        return {
            "order": list(best),
            "km": round(sum(l["km"] for l in legs), 2),
            "hours": round(hours, 2),
            "walk_hours": round(walk_hours, 2),
            "stop_hours": round(n_stops * stop_h, 2),
            "stop_arrivals": [{"stop": int(order[k + 1]), "index": int(i), "arrive_h": round(float(elapsed[i]), 2),
                               "leave_h": round(float(elapsed[i]) + stop_h, 2)} for k, i in enumerate(arrive[:-1])],
            "max_slope": max(l["max_slope"] for l in legs),
            "o2_ok": hours <= usable,
            "o2_margin_h": round(usable - hours, 2),
            "settings": {k: self.rules.get(k, 0) for k in ("o2_hours", "o2_reserve", "walk_speed_kmh", "stop_minutes")},
            "usable_o2_h": round(usable, 2),
            "point_of_no_return": ponr,
            "margin_h": [round(float(x), 2) for x in margin],
            # per point along the path, for the walk-through HUD
            "elapsed_h": [round(float(x), 3) for x in elapsed],
            "home_h": [round(float(x), 3) if np.isfinite(x) else None for x in back],
            "slope_deg": [round(float(x), 1) if np.isfinite(x) else None for x in s],
            "light": light,
            "scout": scout,
            "radio": radio,
            "weather": weather,
            "stop_minerals": stop_minerals,
            "legs": legs,
            "path": path_ll,
            "path_xy": [[round(self.x0 + (c + 0.5) * self.a, 1), round(self.y0 + (r + 0.5) * self.e, 1)] for r, c in full],
        }
