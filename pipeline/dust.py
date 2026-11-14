"""How hazy the sky is over Jezero through the Mars year.

Optical depth (tau) = how much the air dims the sun. 0 = perfectly clear. With the sun straight
overhead, exp(-tau) of its direct light reaches the ground (tau 1 -> 37%); the rest is scattered
into sky glow. It counts everything in the air column: dust plus thin water-ice cloud.

Data: optical depth measured by Perseverance's Mastcam-Z camera from images of the Sun,
Mark Lemmon, "The Perseverance Rover's Mastcam-Z Visible Aerosol Optical Depth Record",
Mendeley Data, v2 (2026), doi:10.17632/gktjp9jptb.2, CC BY 4.0. The author marks the table
PRELIMINARY. We use the green channel (544 nm, close to what the eye sees).

Run: python -m pipeline.dust   (needs data/dust/m20-ztau-merged-1717.txt, writes assets/dust_tau.json)
"""
import json
import math

import numpy as np

from pipeline.loader import ROOT

RAW = ROOT / "data" / "dust" / "m20-ztau-merged-1717.txt"
FILE = ROOT / "assets" / "dust_tau.json"
SOURCE = ("Mark Lemmon, The Perseverance Rover's Mastcam-Z Visible Aerosol Optical Depth Record, "
          "Mendeley Data v2 (2026), doi:10.17632/gktjp9jptb.2, CC BY 4.0")
STATUS = "PRELIMINARY (so marked by the author of the data)"
MEANING = ("Optical depth: how much the air dims the sun. It counts dust and thin ice cloud together. "
           "0.3-0.5 is a normal clear day on Mars, above 1 is a dusty sky.")
BIN_DEG = 30


def parse(text):
    """-> [(sol, Ls, optical depth at 544 nm)], skipping readings marked invalid (-1)."""
    rows, cols = [], None
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if cols is None:
            if "tau-G" in parts and "L_s" in parts:
                cols = (parts.index("Sol"), parts.index("L_s"), parts.index("tau-G"))
            continue
        if len(parts) <= max(cols):
            continue
        try:
            sol, ls, tau = int(parts[cols[0]]), float(parts[cols[1]]), float(parts[cols[2]])
        except ValueError:
            continue
        if tau > 0 and 0 <= ls <= 360:
            rows.append((sol, ls, tau))
    return rows


def bin_index(ls):
    return int((ls % 360) // BIN_DEG)


def bins(rows):
    """Twelve 30-degree slices of the Mars year, each with the typical, low, high and highest optical depth."""
    out = []
    for i in range(360 // BIN_DEG):
        v = np.array([t for _, ls, t in rows if bin_index(ls) == i])
        sols = {s for s, ls, _ in rows if bin_index(ls) == i}
        r = lambda x: None if len(v) == 0 else round(float(x), 3)
        out.append({"ls_from": i * BIN_DEG, "ls_to": (i + 1) * BIN_DEG, "n": int(len(v)), "sols": len(sols),
                    "median": r(np.median(v)) if len(v) else None,
                    "p10": r(np.percentile(v, 10)) if len(v) else None,
                    "p90": r(np.percentile(v, 90)) if len(v) else None,
                    "max": r(v.max()) if len(v) else None})
    return out


def direct_sun_share(tau, sun_elevation_deg):
    """Share of the sun's direct beam that reaches the ground (Beer-Lambert law, flat-layer air).
    Good above ~15 degrees of sun; lower than that the real air path is a bit shorter than this assumes."""
    if sun_elevation_deg <= 0:
        return 0.0
    return math.exp(-tau / math.sin(math.radians(sun_elevation_deg)))


def build():
    rows = parse(RAW.read_text())
    out = {"source": SOURCE, "status": STATUS, "meaning": MEANING, "channel_nm": 544,
           "measurements": len(rows), "sols": [min(r[0] for r in rows), max(r[0] for r in rows)],
           "bins": bins(rows)}
    FILE.write_text(json.dumps(out, indent=1))
    print(f"{len(rows)} valid readings, sols {out['sols']}")
    for b in out["bins"]:
        print(f"  Ls {b['ls_from']:3d}-{b['ls_to']:3d}: typical {b['median']}  ({b['p10']} to {b['p90']}), highest {b['max']}, n={b['n']}")
    return FILE


def load():
    return json.loads(FILE.read_text()) if FILE.exists() else None


def sky(ls):
    """The sky for one season, in the words the planner hands to the astronaut."""
    t = load()
    if t is None:
        return None
    b = t["bins"][bin_index(ls)]
    if b["median"] is None:
        return None
    return {"optical_depth_typical": b["median"], "optical_depth_low": b["p10"], "optical_depth_high": b["p90"],
            "optical_depth_highest_seen": b["max"],
            "direct_sun_share_overhead": round(math.exp(-b["median"]), 2),
            "ls_range": [b["ls_from"], b["ls_to"]], "measurements": b["n"],
            "meaning": t["meaning"], "status": t["status"], "source": t["source"],
            "note": "typical for this part of the Mars year, not a forecast: a dust storm can push it far above typical"}


if __name__ == "__main__":
    build()
