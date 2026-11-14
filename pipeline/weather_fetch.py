"""Sample Perseverance MEDA weather data from NASA PDS without downloading whole files.

For each sampled sol it reads ~40 small byte ranges spread across the day's
CAL_TIRS file (air + ground temperature) and ~30 across DER_WS (wind), keeps only
readings whose quality flags are good, and writes data/weather/meda_samples.json.
Then run: python -m pipeline.weather_build

Quality flags used (1 = good, empty = not applicable), per the CAL_TIRS labels:
  air:    SUN_OUTSIDE_TIRS_FOV. With the sun in view, 15:00-16:00 readings come out
          ~30 C too warm (median -3.7 C vs -32 C, sampled sols). RSM_HEAD is 0 on every
          air reading and shows no such effect, so it is not used.
  ground: WHEEL_OUTSIDE_TIRS_DOWNWARD_LOOKING_FOV, ROVER_LOW_TILT,
          TIRS_GROUND_FOOTPRINT_NOT_IN_SHADOW (the label ties these to the downward channels)
"""
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDS = "https://atmos.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/"


def get(url, rng=None):
    req = urllib.request.Request(url, headers={"Range": f"bytes={rng[0]}-{rng[1]}"} if rng else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace"), r.headers.get("Content-Range")


def links(url):
    return re.findall(r'href="([^"?/][^"]*)"', get(url)[0])


def size(url):
    _, cr = get(url, (0, 0))
    return int(cr.split("/")[1]) if cr else 0


def slices(url, k, length=1600):
    n = size(url)
    out = []
    for i in range(k):
        s = int(i * (n - length) / max(k - 1, 1))
        out += get(url, (s, s + length))[0].split("\n")[1:-1]
    return out


def hour_of(ltst):
    m = re.search(r" (\d\d):(\d\d)", ltst)
    return int(m.group(1)) + int(m.group(2)) / 60 if m else None


def sample_sol(sol, groups):
    g = next(x for x in groups if int(x[4:8]) <= sol <= int(x[9:13]))
    sd = f"sol_{sol:04d}/"
    rows = []
    cal = links(PDS + "data_calibrated_env/" + g + sd)
    tirs = next((f for f in cal if "CAL_TIRS" in f and f.endswith(".CSV")), None)
    if tirs:
        url = PDS + "data_calibrated_env/" + g + sd + tirs
        head = get(url, (0, 1500))[0].split("\n")[0].strip().split(",")
        ix = {n: head.index(n) if n in head else -1 for n in head + ["X"]}
        good = lambda c, n: ix.get(n, -1) < 0 or c[ix[n]] in ("", "1")
        for line in slices(url, 40):
            c = line.split(",")
            h = hour_of(c[2]) if len(c) > 2 else None
            if h is None or len(c) < len(head):
                continue
            air, gnd = float(c[ix["AIR_TEMP"]] or 0), float(c[ix["GROUND_TEMP"]] or 0)
            if 100 < air < 350 and good(c, "SUN_OUTSIDE_TIRS_FOV"):
                rows.append([sol, round(h, 2), "air", air])
            if 100 < gnd < 350 and all(good(c, n) for n in ("WHEEL_OUTSIDE_TIRS_DOWNWARD_LOOKING_FOV",
                                                             "ROVER_LOW_TILT", "TIRS_GROUND_FOOTPRINT_NOT_IN_SHADOW")):
                rows.append([sol, round(h, 2), "ground", gnd])
    der = links(PDS + "data_derived_env/" + g + sd)
    ws = next((f for f in der if "DER_WS" in f and f.endswith(".CSV")), None)
    if ws:
        for line in slices(PDS + "data_derived_env/" + g + sd + ws, 30):
            c = line.split(",")
            if len(c) > 3 and c[3] not in ("", None):
                h, v = hour_of(c[2]), float(c[3])
                if h is not None and 0 <= v < 60:
                    rows.append([sol, round(h, 2), "wind", v])
    return rows


def main(step=15, first=15, last=1845):
    groups = [x for x in links(PDS + "data_calibrated_env/") if x.startswith("sol_") and x.endswith("/")]
    sols = list(range(first, last + 1, step))
    rows = []
    with ThreadPoolExecutor(6) as ex:
        for r in ex.map(lambda s: _safe(s, groups), sols):
            rows += r
    out = ROOT / "data" / "weather" / "meda_samples.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"rows": rows}))
    print("saved", out, len(rows), "readings")


def _safe(sol, groups):
    try:
        return sample_sol(sol, groups)
    except Exception as e:  # a few sols have no TIRS file
        print("skip sol", sol, e)
        return []


if __name__ == "__main__":
    main()
