"""Dominant minerals at Jezero from the CRISM mineral map of Parente et al. (2021),
Zenodo 10.5281/zenodo.5575824, CC BY 4.0. 36 m pixels.

Each mineral has a bright color (high confidence) and a dull color (medium confidence),
from the authors' readme. Black = not identified. Pure white is not in their key, so we
treat it as no data. The authors note names are the closest match to known minerals and
need further analysis to confirm, so we always show that caveat.
"""
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "minerals" / "jezeroFinal.tif"

# name, high-confidence RGB, medium-confidence RGB (authors' readme, "Key for Mineral Detections")
KEY = [
    ("Olivine", (255, 0, 0), (153, 0, 0)),
    ("Mg-carbonate", (0, 255, 0), (0, 153, 0)),
    ("Fe/Mg-smectite (clay)", (0, 255, 255), (0, 153, 153)),
    ("Olivine + smectite", (255, 128, 114), (153, 77, 68)),
    ("Olivine/smectite + 2.2 um feature", (128, 128, 0), (77, 77, 0)),
    ("Carbonate + 2.2 um feature", (255, 215, 0), (153, 129, 0)),
    ("High-calcium pyroxene", (255, 128, 0), (153, 77, 0)),
    ("Low-calcium pyroxene", (218, 165, 32), (130, 99, 19)),
    ("Kaolinite (clay)", (139, 69, 19), (83, 41, 11)),
    ("Mg-smectite 2 (clay)", (0, 0, 255), (0, 0, 153)),
]
CAVEAT = ("Mineral names are the closest match to known minerals (Parente et al. 2021); "
          "exact identification needs further analysis. 36 m pixels.")
NODATA, UNIDENTIFIED = 0, 255  # codes in our grid; minerals are 1..10, +100 = medium confidence


def classify_rgb(rgb, tol=9):
    """(3, H, W) uint8 -> code grid. 1..10 high confidence, 101..110 medium, 255 unidentified, 0 no data.
    Each pixel takes the nearest key color if it is within `tol` (the image was smoothed when it was
    resized, so edge pixels are a few shades off). The two closest key colors differ by 19 in one
    channel, so with tol 9 no pixel can be within reach of two colors. Blends further off stay no data."""
    px = rgb.reshape(3, -1).T.astype(int)
    cols = [((0, 0, 0), UNIDENTIFIED)]
    for i, (_, hi, med) in enumerate(KEY, start=1):
        cols += [(hi, i), (med, 100 + i)]
    ref = np.array([c for c, _ in cols])
    codes = np.array([v for _, v in cols], np.uint8)
    dist = np.abs(px[:, None, :] - ref[None, :, :]).max(axis=2)  # biggest channel difference
    best = dist.argmin(axis=1)
    out = np.where(dist[np.arange(len(px)), best] <= tol, codes[best], 0).astype(np.uint8)
    return out.reshape(rgb.shape[1:])  # white and anything else stays 0 = no data


def name_of(code):
    if code == NODATA:
        return None, None
    if code == UNIDENTIFIED:
        return "not identified", None
    i = code % 100
    return KEY[i - 1][0], ("high" if code < 100 else "medium")


def build(name="jezero"):
    with rasterio.open(SRC) as src:
        code = classify_rgb(src.read())
        src_tr, src_crs = src.transform, src.crs
    d = np.load(ROOT / "data" / name / "layers.npz")
    a, b, x0, dd, e, y0 = d["transform"]
    shape = d["zone"].shape
    out = np.zeros(shape, np.uint8)
    reproject(code, out, src_transform=src_tr, src_crs=src_crs,
              dst_transform=rasterio.Affine(a, b, x0, dd, e, y0), dst_crs=str(d["crs"]),
              resampling=Resampling.nearest, src_nodata=None, dst_nodata=None)
    np.savez_compressed(ROOT / "data" / name / "minerals.npz", code=out)
    vals, counts = np.unique(out, return_counts=True)
    for v, c in sorted(zip(vals, counts), key=lambda x: -x[1]):
        n, conf = name_of(int(v))
        print(f"{c / out.size:6.1%}  {n or 'no data'}{' (' + conf + ')' if conf else ''}")
    return out


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "jezero")
