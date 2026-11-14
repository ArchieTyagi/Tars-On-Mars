"""The real photo of the ground: USGS HiRISE orthomosaic of Jezero (25 cm per pixel),
cut to the same box as our height map and shrunk to 1 m by averaging.

Source: Fergason et al. 2020, Mars 2020 Terrain Relative Navigation HiRISE Orthorectified
Image Mosaic, USGS, doi:10.5066/P9QJDP48 (CC0). Same product family as our height map,
so the two are already lined up; registration_check() proves it.

Run: python -m pipeline.photo        (resumable: run again if the connection drops)
"""
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

from pipeline.loader import ROOT, crop_bounds, load_config

SOURCE = ("USGS Astrogeology, Mars 2020 Terrain Relative Navigation HiRISE Orthorectified Image Mosaic "
          "(Fergason et al. 2020), doi:10.5066/P9QJDP48, CC0. Image data: NASA/JPL/University of Arizona")
OUT_M = 1.0       # stored pixel size, meters
CHUNK_ROWS = 400  # source rows per download piece


def block_mean(a, k):
    """Shrink by k, averaging each k x k block. 0 = no data: left out of the average,
    and a block with no data at all stays 0."""
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k).astype("float64")
    n = (b > 0).sum(axis=(1, 3))
    mean = b.sum(axis=(1, 3)) / np.maximum(n, 1)
    return np.where(n > 0, np.clip(np.rint(mean), 1, 255), 0).astype("uint8")


def window_for(cfg, transform):
    """Pixel window of the mosaic that covers exactly the height map's ground box."""
    return from_bounds(*crop_bounds(cfg), transform).round_offsets().round_lengths()


def fetch(name="jezero", only=None):
    """Download the box in pieces (each saved, so it can resume) and build data/<name>/photo.npz.
    only = (i, n): this run only does pieces where piece_number % n == i, so several runs can share the work."""
    cfg = load_config(name)
    if not cfg.get("photo_url"):
        print("no photo_url in config for", name)
        return None
    out_dir = ROOT / "data" / name
    parts = out_dir / "photo_parts"
    parts.mkdir(parents=True, exist_ok=True)
    with rasterio.open("/vsicurl/" + cfg["photo_url"]) as src:
        win = window_for(cfg, src.transform)
        k = int(round(OUT_M / src.res[0]))
        n_chunks = -(-win.height // CHUNK_ROWS)
        for i in range(n_chunks):
            f = parts / f"rows_{i:03d}.npy"
            if f.exists() or (only and i % only[1] != only[0]):
                continue
            h = min(CHUNK_ROWS, win.height - i * CHUNK_ROWS)
            a = src.read(1, window=Window(win.col_off, win.row_off + i * CHUNK_ROWS, win.width, h))
            tmp = parts / f"tmp_{i:03d}_{only[0] if only else 0}.npy"
            np.save(tmp, block_mean(a, k))
            tmp.rename(f)
            print(f"piece {i + 1}/{n_chunks} saved", flush=True)
    done = sorted(parts.glob("rows_*.npy"))
    if len(done) < n_chunks:
        print(f"{len(done)}/{n_chunks} pieces so far, run again to continue")
        return None
    gray = np.concatenate([np.load(f) for f in done])
    out = out_dir / "photo.npz"
    np.savez_compressed(out, gray=gray, m_per_px=OUT_M)
    print("saved", out, gray.shape, f"no data: {(gray == 0).mean():.2%}")
    return out


def load(name="jezero"):
    f = ROOT / "data" / name / "photo.npz"
    return np.load(f)["gray"] if f.exists() else None


def registration_check(name="jezero", max_shift=4):
    """Does the photo sit exactly on the height map? Slopes facing the sun are bright in the
    photo, so we shade the height map from every sun direction, keep the direction that fits the
    photo best, then slide the photo around by a few cells. The best fit must be at zero shift."""
    from matplotlib.colors import LightSource

    from planner.route import Site
    s = Site(name)
    full = load(name)
    p = block_mean(full, full.shape[0] // s.zone.shape[0]).astype("float64")  # photo on the planner's grid
    h = np.nan_to_num(s.height, nan=float(np.nanmean(s.height)))
    ok = np.isfinite(s.height) & (p > 0)

    def norm(a):  # keep only local detail, so big bright/dark regions do not decide the answer
        from scipy.ndimage import uniform_filter
        return a - uniform_filter(a, 25)

    pn = norm(p)
    m = max_shift

    def match(shade, dr, dc):
        a = shade[m:-m, m:-m]
        b = pn[m + dr: pn.shape[0] - m + dr, m + dc: pn.shape[1] - m + dc]
        w = ok[m:-m, m:-m]
        return float(np.corrcoef(a[w], b[w])[0, 1])

    best_az, best0 = None, -2.0
    for az in range(0, 360, 15):
        sh = norm(LightSource(az, 45).hillshade(h, dx=s.dx, dy=s.dy))
        v = match(sh, 0, 0)
        if v > best0:
            best_az, best0 = az, v
    sh = norm(LightSource(best_az, 45).hillshade(h, dx=s.dx, dy=s.dy))
    grid = {(dr, dc): match(sh, dr, dc) for dr in range(-m, m + 1) for dc in range(-m, m + 1)}
    (dr, dc), v = max(grid.items(), key=lambda kv: kv[1])
    return {"sun_from_deg": best_az, "shift_rows": dr, "shift_cols": dc, "match": round(v, 3),
            "match_at_zero": round(grid[(0, 0)], 3), "cell_m": round(s.dy, 2)}


if __name__ == "__main__":
    only = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else None
    fetch(sys.argv[1] if len(sys.argv) > 1 else "jezero", only)
