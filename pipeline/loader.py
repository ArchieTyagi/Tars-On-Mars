"""Cut a square piece of the USGS height map and save it as data/jezero/dtm.tif.

Reads in row chunks so a slow connection can resume where it stopped.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds

ROOT = Path(__file__).resolve().parents[1]


def load_config(name="jezero"):
    return json.loads((ROOT / "config" / f"{name}.json").read_text())


def crop_bounds(cfg):
    r = cfg["radius_m"]
    cx = round(r * math.radians(cfg["center_lon"]))
    cy = round(r * math.radians(cfg["center_lat"]))
    h = cfg["half_size_m"]
    return cx - h, cy - h, cx + h, cy + h


def from_local(cfg, name):
    """Site whose height map is already on disk (e.g. the LOLA Moon maps). Optional crop."""
    out_dir = ROOT / "data" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = [("dtm_path", "dtm.tif")]
    if cfg.get("slope_err_path"):
        pairs.append(("slope_err_path", "slope_err.tif"))
    for key, out_name in pairs:
        with rasterio.open(ROOT / cfg[key]) as src:
            if cfg.get("half_size_m"):
                cx, cy = cfg["center_xy"]
                h = cfg["half_size_m"]
                win = from_bounds(cx - h, cy - h, cx + h, cy + h, src.transform).round_offsets().round_lengths()
            else:
                win = Window(0, 0, src.width, src.height)
            a = src.read(1, window=win).astype("float32")
            if src.nodata is not None and not np.isnan(src.nodata):
                a[a == src.nodata] = np.nan
            with rasterio.open(out_dir / out_name, "w", driver="GTiff", height=a.shape[0], width=a.shape[1], count=1,
                               dtype="float32", crs=src.crs, transform=src.window_transform(win),
                               nodata=np.nan, tiled=True, compress="deflate") as dst:
                dst.write(a, 1)
        print("saved", out_dir / out_name, a.shape)
    return out_dir / "dtm.tif"


def fetch(name="jezero"):
    cfg = load_config(name)
    if cfg.get("dtm_path"):
        return from_local(cfg, name)
    out_dir = ROOT / "data" / name
    parts = out_dir / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    left, bottom, right, top = crop_bounds(cfg)

    with rasterio.open("/vsicurl/" + cfg["dtm_url"]) as src:
        win = from_bounds(left, bottom, right, top, src.transform).round_offsets().round_lengths()
        nodata = src.nodata
        transform = src.window_transform(win)
        crs = src.crs
        step = cfg["chunk_rows"]
        n_chunks = math.ceil(win.height / step)
        for i in range(n_chunks):
            f = parts / f"rows_{i:03d}.npy"
            if f.exists():
                continue
            h = min(step, win.height - i * step)
            w = Window(win.col_off, win.row_off + i * step, win.width, h)
            np.save(f, src.read(1, window=w))
            print(f"chunk {i + 1}/{n_chunks} saved", flush=True)

    done = sorted(parts.glob("rows_*.npy"))
    if len(done) < n_chunks:
        print(f"{len(done)}/{n_chunks} chunks so far, run again to continue")
        return None

    dem = np.concatenate([np.load(f) for f in done]).astype("float32")
    if nodata is not None:
        dem[dem == nodata] = np.nan
    out = out_dir / "dtm.tif"
    with rasterio.open(out, "w", driver="GTiff", height=dem.shape[0], width=dem.shape[1],
                       count=1, dtype="float32", crs=crs, transform=transform,
                       nodata=np.nan, tiled=True, compress="deflate") as dst:
        dst.write(dem, 1)
    print("saved", out, dem.shape, "gaps:", f"{np.isnan(dem).mean():.2%}")
    return out


if __name__ == "__main__":
    fetch(sys.argv[1] if len(sys.argv) > 1 else "jezero")
