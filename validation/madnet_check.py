"""Is the AI-made 50 cm height map (MADNet) safe to plan with?

Compares its slopes against the measured USGS HiRISE 1 m map over the same
2 x 2 km box at the landing site. Writes docs/madnet_vs_usgs.png and .json.
"""
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import ListedColormap
from rasterio.windows import from_bounds

from pipeline.layers import ground_scale_x, slope_deg

ROOT = Path(__file__).resolve().parents[1]
R = 3396190.0
LON, LAT, HALF = 77.4298, 18.4663, 1000  # USGS landing-site center


def read_box(path, bounds):
    with rasterio.open(path) as src:
        win = from_bounds(*bounds, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win).astype("float32")
        if src.nodata is not None and not np.isnan(src.nodata):
            a[a == src.nodata] = np.nan
        a[a < -1e30] = np.nan
        return a, src.window_transform(win), src.res[0]


def main(madnet_path):
    cx, cy = round(R * math.radians(LON)), round(R * math.radians(LAT))
    b = (cx - HALF, cy - HALF, cx + HALF, cy + HALF)
    u, tu, ru = read_box(ROOT / "data" / "jezero" / "dtm.tif", b)
    m, tm, rm = read_box(madnet_path, b)
    assert (tu.c, tu.f) == (tm.c, tm.f), "grids not aligned"
    k = int(round(ru / rm))
    m = m[: u.shape[0] * k, : u.shape[1] * k].reshape(u.shape[0], k, u.shape[1], k).mean(axis=(1, 3))

    kx = ground_scale_x(LAT)
    su, sm = slope_deg(u, ru, ru * kx), slope_deg(m, ru, ru * kx)
    ok = ~(np.isnan(su) | np.isnan(sm))
    d = (m - u)[ok]
    out = {
        "box": "2 x 2 km at the Perseverance landing site, compared on a 1 m grid",
        "gaps_usgs": float(np.isnan(u).mean()), "gaps_madnet": float(np.isnan(m).mean()),
        "height_diff_mean_m": float(d.mean()), "height_diff_std_m": float(d.std()),
        "height_diff_p95_abs_m": float(np.percentile(np.abs(d), 95)),
        "slope_corr": float(np.corrcoef(su[ok], sm[ok])[0, 1]),
        "slope_diff_std_deg": float((sm - su)[ok].std()),
        "slope_diff_p95_abs_deg": float(np.percentile(np.abs(sm - su)[ok], 95)),
        "p99_slope_usgs": float(np.percentile(su[ok], 99)), "p99_slope_madnet": float(np.percentile(sm[ok], 99)),
    }
    for lim in (10, 15, 20):
        bu, bm = su[ok] >= lim, sm[ok] >= lim
        out[f"at_{lim}deg"] = {
            "blocked_usgs": float(bu.mean()), "blocked_madnet": float(bm.mean()),
            "flips": float((bu != bm).mean()),
            "madnet_says_safe_but_usgs_blocked": float((bu & ~bm).mean()),
            "share_of_usgs_blocked_missed": float((bu & ~bm).sum() / max(bu.sum(), 1)),
        }
    (ROOT / "docs" / "madnet_vs_usgs.json").write_text(json.dumps(out, indent=1))

    a20 = out["at_20deg"]
    miss = (su >= 20) & (sm < 20)
    extra = (su < 20) & (sm >= 20)
    fig, ax = plt.subplots(1, 3, figsize=(15, 5.4))
    for i, (s, t) in enumerate([(su, "USGS measured slope (1 m)"), (sm, "MADNet AI slope (resampled to 1 m)")]):
        im = ax[i].imshow(s, cmap="magma", vmin=0, vmax=35)
        ax[i].set_title(t)
    fig.colorbar(im, ax=ax[:2], fraction=0.025, label="slope (deg)")
    diff = np.zeros(su.shape, "uint8"); diff[extra] = 1; diff[miss] = 2
    ax[2].imshow(diff, cmap=ListedColormap(["#eeeeee", "#f5a623", "#d0021b"]), vmin=0, vmax=2, interpolation="nearest")
    ax[2].set_title(f"At 20 deg: red = AI says safe, USGS says too steep\norange = AI says too steep, USGS says fine | "
                    f"AI misses {a20['share_of_usgs_blocked_missed']:.0%} of the steep spots")
    for x in ax: x.axis("off")
    fig.suptitle(f"Slope agreement r = {out['slope_corr']:.2f} | height error p95 = {out['height_diff_p95_abs_m']:.2f} m "
                 f"| verdict: USGS for safety, AI map for visuals only", fontsize=12)
    fig.savefig(ROOT / "docs" / "madnet_vs_usgs.png", dpi=100, bbox_inches="tight")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "mnt/Downloads/JEZ_MADNet_DTM_50cm_v8.tif"))
