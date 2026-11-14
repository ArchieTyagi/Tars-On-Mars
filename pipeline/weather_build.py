"""Turn MEDA samples (sol, hour, variable, value in K or m/s) into data/weather/meda_hourly.json.

Input: data/weather/meda_samples.json = {"rows": [[sol, hour, var, value], ...]}
Season per sol comes from pipeline.mars_time (the file's own Ls column is not usable:
it reads -0.85 deg at sol 120, when the real season was about 62 deg).
"""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from pipeline.mars_time import ls_from_m20_sol
from pipeline.weather import season_of

ROOT = Path(__file__).resolve().parents[1]


def build():
    raw = json.loads((ROOT / "data" / "weather" / "meda_samples.json").read_text())
    bins = defaultdict(list)
    sols = set()
    for sol, hour, var, val in raw["rows"]:
        if var in ("air", "ground"):
            val = val - 273.15  # K -> deg C
        bins[(season_of(ls_from_m20_sol(sol, hour)), var, int(hour) % 24)].append(val)
        sols.add(sol)
    out = {"source": "NASA PDS, Mars 2020 MEDA (Rodriguez-Manfredi et al.), CAL_TIRS air/ground temperature "
                      "and DER_WS wind speed; one sol in every 15, %d sols" % len(sols),
           "units": {"air": "deg C", "ground": "deg C", "wind": "m/s"},
           "seasons": {}}
    for s in range(4):
        out["seasons"][str(s)] = {}
        for var in ("air", "ground", "wind"):
            stats = {"mean": [], "p10": [], "p90": [], "n": []}
            for h in range(24):
                v = np.array(bins.get((s, var, h), []))
                if len(v) >= 20:
                    stats["mean"].append(round(float(v.mean()), 1))
                    stats["p10"].append(round(float(np.percentile(v, 10)), 1))
                    stats["p90"].append(round(float(np.percentile(v, 90)), 1))
                else:
                    stats["mean"].append(None); stats["p10"].append(None); stats["p90"].append(None)
                stats["n"].append(int(len(v)))
            out["seasons"][str(s)][var] = stats
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "meda_hourly.json").write_text(json.dumps(out))
    return out


if __name__ == "__main__":
    o = build()
    for s in range(4):
        a = o["seasons"][str(s)]["air"]["mean"]
        print(s, "air by hour:", a)
