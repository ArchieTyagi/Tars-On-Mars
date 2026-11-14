"""Typical weather at Jezero by season and hour, from Perseverance's MEDA weather station.

Built by pipeline/weather_build.py from NASA PDS MEDA files (air and ground
temperature from CAL_TIRS, wind speed from DER_WS), sampling one sol in every 15
across the mission. These are typical conditions, not a forecast.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "assets" / "meda_hourly.json"  # small, kept in git so the server works anywhere
SEASONS = [(0, "northern spring (Ls 0-90)"), (90, "northern summer (Ls 90-180)"),
           (180, "northern autumn (Ls 180-270)"), (270, "northern winter (Ls 270-360)")]


def season_of(ls):
    return int(ls % 360 // 90)


def load():
    return json.loads(FILE.read_text()) if FILE.exists() else None


def along(ls, ltst_h):
    """Typical air temp, ground temp (deg C) and wind (m/s) for each time in ltst_h."""
    w = load()
    if w is None:
        return None
    s = w["seasons"][str(season_of(ls))]
    hrs = np.asarray(ltst_h) % 24
    out = {}
    for var in ("air", "ground", "wind"):
        mean = np.array([np.nan if v is None else v for v in s[var]["mean"]], float)
        ok = np.isfinite(mean)
        if ok.sum() < 2:
            out[var] = [None] * len(hrs)
            continue
        h = np.arange(24) + 0.5  # bin centers
        hh, mm = np.concatenate([h[ok] - 24, h[ok], h[ok] + 24]), np.tile(mean[ok], 3)  # wrap midnight
        out[var] = [round(float(x), 1) for x in np.interp(hrs, hh, mm)]
    return out


def _sky(ls):
    from pipeline.dust import sky
    return sky(ls)


def summary(ls, ltst_h):
    a = along(ls, ltst_h)
    if a is None:
        return None
    w = load()
    s = season_of(ls)
    air = [x for x in a["air"] if x is not None]
    gnd = [x for x in a["ground"] if x is not None]
    wind = [x for x in a["wind"] if x is not None]
    return {
        "season": SEASONS[s][1],
        "air_c_min": min(air) if air else None, "air_c_max": max(air) if air else None,
        "ground_c_min": min(gnd) if gnd else None, "ground_c_max": max(gnd) if gnd else None,
        "wind_ms_max": max(wind) if wind else None,
        "per_point": a,
        "sky": _sky(ls),
        "source": w["source"],
        "note": "typical conditions from Perseverance's MEDA station for this season and hour, not a forecast",
        "wind_note": (None if wind else
                      "no wind data for this season: MEDA's wind sensors were damaged by wind-blown sand after "
                      "sol 313 and processed wind is only published for earlier sols"),
    }
