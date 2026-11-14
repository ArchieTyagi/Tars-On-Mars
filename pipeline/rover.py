"""Where Perseverance really drove, cut to our map. The rover drove it safely, so this is
ground truth we can show on the map and check our zones against.

Source: NASA/JPL-Caltech, Mars 2020 mission rover location data (M20_traverse.json, M20_waypoints.json).
Run: python -m pipeline.rover   (needs the two files in data/rover/, writes assets/rover_track.json)
"""
import json
import math

import numpy as np

from pipeline.loader import ROOT

FILE = ROOT / "assets" / "rover_track.json"
SOURCE = ("NASA/JPL-Caltech, Mars 2020 mission rover location data "
          "(M20_traverse.json and M20_waypoints.json, the files behind NASA's 'Where is Perseverance' map)")


def clip(points, inside):
    """Keep the runs of points that are inside. A line that leaves and comes back becomes two runs.
    Runs of a single point are dropped (one point is not a line)."""
    runs, cur = [], []
    for p in points:
        if inside(p):
            cur.append(p)
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def _inside(site):
    R, C = site.zone.shape

    def f(p):
        r, c = site.lonlat_to_cell(p[0], p[1])
        return 0 <= r < R and 0 <= c < C
    return f


def build(name="jezero"):
    from planner.route import Site
    site = Site(name)
    inside = _inside(site)
    src = ROOT / "data" / "rover"
    segments = []
    for f in json.load(open(src / "M20_traverse.json"))["features"]:
        pts = [[round(x, 7), round(y, 7)] for x, y, *_ in f["geometry"]["coordinates"]]
        for run in clip(pts, inside):
            segments.append({"sol": int(f["properties"]["sol"]), "points": run})
    way = [f["properties"] for f in json.load(open(src / "M20_waypoints.json"))["features"]]
    stops = [{"lonlat": [round(p["lon"], 7), round(p["lat"], 7)], "sol": int(p["sol"]),
              "tilt_deg": round(float(p["tilt"]), 3), "drive_total_km": round(float(p["dist_total_m"]) / 1000, 3)}
             for p in way if p.get("tilt") is not None and p["dist_m"] > 0 and inside((p["lon"], p["lat"]))]
    first = way[0]
    out = {"source": SOURCE, "site": name,
           "landing": {"lonlat": [round(first["lon"], 7), round(first["lat"], 7)],
                       "name": "Octavia E. Butler Landing",
                       "note": "where the rover sat from landing (sol 0) until its first drive"},
           "segments": segments, "stops": stops}
    FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(segments)} drives, {sum(len(s['points']) for s in segments)} points, {len(stops)} stops, "
          f"{FILE.stat().st_size // 1024} KB")
    return FILE


def load(name="jezero"):
    if not FILE.exists():
        return None
    t = json.loads(FILE.read_text())
    return t if t.get("site") == name else None


def _meters(a, b, radius):
    (l1, p1), (l2, p2) = [(math.radians(x), math.radians(y)) for x, y in (a, b)]
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(min(1.0, h)))


def squares(site, track):
    """Every grid square the track touches, exactly: for each piece of the line we find where it
    crosses a grid line, and take the square between each pair of crossings. No sampling, so a
    square the line only clips at a corner still counts."""
    R, C = site.zone.shape
    out = set()
    for seg in track["segments"]:
        p = np.array(seg["points"])
        x, y = site._to_xy.transform(p[:, 0], p[:, 1])
        col, row = (np.asarray(x) - site.x0) / site.a, (np.asarray(y) - site.y0) / site.e  # in cell units
        for c0, r0, c1, r1 in zip(col[:-1], row[:-1], col[1:], row[1:]):
            ts = [0.0, 1.0]
            for a, b in ((c0, c1), (r0, r1)):
                lo, hi = sorted((a, b))
                if hi > lo:
                    ts += [(g - a) / (b - a) for g in range(math.floor(lo) + 1, math.ceil(hi))]
            ts = np.unique(ts)
            mid = (ts[:-1] + ts[1:]) / 2 if len(ts) > 1 else np.array([0.0])
            rr = np.floor(r0 + mid * (r1 - r0)).astype(int)
            cc = np.floor(c0 + mid * (c1 - c0)).astype(int)
            out.update((int(a), int(b)) for a, b in zip(rr, cc) if 0 <= a < R and 0 <= b < C)
    return out


def summary(site, track):
    """Length of the track on the map, and what our map says about the ground the rover drove on:
    every grid square the track touches counted once, as GO / CAUTION / NO-GO."""
    km = sum(_meters(a, b, site.radius) for seg in track["segments"]
             for a, b in zip(seg["points"], seg["points"][1:])) / 1000
    cells = np.array(sorted(squares(site, track)))
    z = site.zone[cells[:, 0], cells[:, 1]]
    sols = [s["sol"] for s in track["segments"]]
    return {"km_on_map": round(km, 2), "sols": [min(sols), max(sols)],
            "our_map_on_the_track": {"squares": int(len(z)), "go": float((z == 0).mean()),
                                     "caution": float((z == 1).mean()), "nogo": float((z == 2).mean())}}


if __name__ == "__main__":
    build()
