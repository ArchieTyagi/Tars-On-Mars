"""Wider pictures around the planning box, so the map can show where on Mars the box sits.

Three levels for Jezero (listed under "context" in config/jezero.json), from far to near:
  planet   the whole of Mars, Viking colour mosaic shrunk to about 10 km per pixel
  region   about 237 km around Jezero, the same mosaic at its full 232 m per pixel
  mosaic   the 21 km HiRISE photo mosaic our box is cut from, shrunk to 16 m per pixel

The planner does NOT use any of them. Outside the planning box no checked height map is loaded,
so the web app shows these pictures darkened and marked as not mapped for walking.

All sources are in the same map projection as our site (equirectangular on the Mars sphere), so a
picture's corner positions in map meters are simply read from its source file.

The source files have no small preview inside them and are far too big to download whole
(the HiRISE mosaic is 7 GB). They are stored row by row, so this reads only the rows it needs:
a few rows out of every block, averaged. That is plenty for a picture at these scales.

Run: python -m pipeline.context jezero planet      (resumable: run again if the connection drops)
     python -m pipeline.context jezero region
     python -m pipeline.context jezero mosaic
"""
import json
import sys

import numpy as np
import rasterio
from PIL import Image
from rasterio.windows import Window

from pipeline.loader import ROOT, crop_bounds, load_config
from pipeline.photo import SOURCE as PHOTO_SOURCE

CHUNK = 50  # picture rows per download piece (a level can set its own "chunk" in the config)
NOTE = "Real ground, but no checked height map is loaded for it, so no walk can be planned there."


def sample_rows(n_src_rows, k, per_block):
    """Which source rows to read: `per_block` rows spread evenly inside each block of k rows.
    Rows at the bottom that do not fill a whole block are left out."""
    offs = [int((j + 0.5) * k / per_block) for j in range(per_block)]
    return [[b * k + o for o in offs] for b in range(n_src_rows // k)]


def shrink(rows, k):
    """rows: the source rows of ONE picture row, shape (n, width). Returns that picture row:
    the mean of each k columns over all the rows. 0 = no data: left out of the mean, and a block
    with no data at all stays 0."""
    w = (rows.shape[1] // k) * k
    b = rows[:, :w].reshape(rows.shape[0], w // k, k).astype("float64")
    n = (b > 0).sum(axis=(0, 2))
    mean = b.sum(axis=(0, 2)) / np.maximum(n, 1)
    return np.where(n > 0, np.clip(np.rint(mean), 1, 255), 0).astype("uint8")


def window(src_width, src_height, src_left, src_top, res, center_xy=None, half_size_m=None):
    """Which part of the source to use, as (col_off, row_off, width, height) in source pixels.
    No half size = the whole source. Otherwise a square around the center, cut where the source ends."""
    if half_size_m is None:
        return 0, 0, src_width, src_height
    cx, cy = center_xy
    c0 = max(0, int(round((cx - half_size_m - src_left) / res)))
    c1 = min(src_width, int(round((cx + half_size_m - src_left) / res)))
    r0 = max(0, int(round((src_top - (cy + half_size_m)) / res)))
    r1 = min(src_height, int(round((src_top - (cy - half_size_m)) / res)))
    return c0, r0, c1 - c0, r1 - r0


def extent(left, top, res, width, height, k):
    """Ground box and size of a picture made from `width` x `height` source pixels starting at
    (left, top): whole blocks of k source pixels from the top-left corner."""
    cols, rows = width // k, height // k
    m = k * res
    return {"left": left, "top": top, "right": left + cols * m, "bottom": top - rows * m,
            "cols": cols, "rows": rows, "m_per_px": m}


def levels(cfg):
    """The context levels of a site, far to near, with the source address and credit filled in."""
    out = []
    for lv in cfg.get("context", []):
        lv = dict(lv)
        lv["url"] = lv.get("url") or cfg.get(lv.get("url_key", ""))
        lv["source"] = lv.get("source") or (PHOTO_SOURCE if lv.get("source_key") == "photo" else None)
        if lv["url"]:
            out.append(lv)
    return out


def _files(name, level_id):
    stem = ROOT / "assets" / f"context_{name}_{level_id}"
    return stem.with_suffix(".jpg"), stem.with_suffix(".json")


def fetch(name="jezero", level_id="mosaic", only=None):
    """Download one level in pieces (each saved, so it can resume), then build its files in assets/.
    only = (i, n): this run only does pieces where piece_number % n == i, so several runs can share the work."""
    cfg = load_config(name)
    lv = next((x for x in levels(cfg) if x["id"] == level_id), None)
    if lv is None:
        print(f"no context level '{level_id}' in the config for {name}")
        return None
    k, per = int(lv["k"]), int(lv.get("rows_per_block", 1))
    parts = ROOT / "data" / name / "context_parts" / level_id
    parts.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = crop_bounds(cfg)
    with rasterio.open("/vsicurl/" + lv["url"]) as src:
        c0, r0, w, h = window(src.width, src.height, src.bounds.left, src.bounds.top, src.res[0],
                              ((x0 + x1) / 2, (y0 + y1) / 2), lv.get("half_size_m"))
        e = extent(src.bounds.left + c0 * src.res[0], src.bounds.top - r0 * src.res[0], src.res[0], w, h, k)
        plan = sample_rows(h, k, per)
        chunk = int(lv.get("chunk", CHUNK))
        n_chunks = -(-len(plan) // chunk)
        for i in range(n_chunks):
            f = parts / f"rows_{i:03d}.npy"
            if f.exists() or (only and i % only[1] != only[0]):
                continue
            out = [[shrink(np.stack([src.read(b, window=Window(c0, r0 + r, w, 1))[0] for r in group]), k)
                    for b in range(1, src.count + 1)] for group in plan[i * chunk:(i + 1) * chunk]]
            tmp = parts / f"tmp_{i:03d}_{only[0] if only else 0}.npy"
            np.save(tmp, np.moveaxis(np.array(out, "uint8"), 1, 2))  # (rows, cols, bands)
            tmp.rename(f)
            print(f"{level_id}: piece {i + 1}/{n_chunks} saved", flush=True)
    done = sorted(parts.glob("rows_*.npy"))
    if len(done) < n_chunks:
        print(f"{level_id}: {len(done)}/{n_chunks} pieces so far, run again to continue")
        return None
    return build(name, lv, np.concatenate([np.load(f) for f in done]), e)


def build(name, lv, pixels, e):
    """Write assets/context_<site>_<level>.jpg and the small .json that says which ground it covers."""
    if pixels.ndim == 2:
        pixels = pixels[:, :, None]
    assert pixels.shape[:2] == (e["rows"], e["cols"]), (pixels.shape, e)
    jpg, meta_file = _files(name, lv["id"])
    img = Image.fromarray(pixels[:, :, 0], "L") if pixels.shape[2] == 1 else Image.fromarray(pixels[:, :, :3], "RGB")
    img.save(jpg, "JPEG", quality=85, optimize=True)
    per, k = int(lv.get("rows_per_block", 1)), int(lv["k"])
    meta = {"id": lv["id"], "name": lv["name"], "about": lv["about"], "source": lv["source"],
            "extent_xy": {x: e[x] for x in ("left", "top", "right", "bottom")},
            "cols": e["cols"], "rows": e["rows"], "m_per_px": e["m_per_px"],
            "made_from": ("the source at its full sharpness" if k == 1 else
                          f"{per} of every {k} source rows, averaged over blocks of {k} pixels")}
    meta_file.write_text(json.dumps(meta, indent=1) + "\n")
    print("saved", jpg, pixels.shape, f"no data: {(pixels == 0).all(axis=2).mean():.2%}")
    return jpg


def info(name="jezero"):
    """The context pictures that exist for a site, far to near. Empty when it has none."""
    out = []
    for lv in levels(load_config(name)):
        jpg, meta_file = _files(name, lv["id"])
        if jpg.exists() and meta_file.exists():
            out.append(json.loads(meta_file.read_text()))
    return out


def jpg_bytes(name, level_id):
    return _files(name, level_id)[0].read_bytes()


if __name__ == "__main__":
    site_name = sys.argv[1] if len(sys.argv) > 1 else "jezero"
    level = sys.argv[2] if len(sys.argv) > 2 else "mosaic"
    fetch(site_name, level, (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else None)
