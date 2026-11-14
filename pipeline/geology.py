"""Ground type for every grid cell, from the USGS geologic map of Jezero (SIM 3464).

Each map unit gets a ground type (sand / regolith / bedrock) from rules.json,
and each ground type has its own slope limit. Writes data/<name>/ground.npz.
"""
import json
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio import features

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geology"
GDB = GEO / "sim3464_JezeroNili_FINAL" / "Geodatabase" / "Nili.gdb"
GROUND = ["default", "bedrock", "regolith", "sand"]  # index = code in the grid


def unpack():
    if not GDB.exists():
        with zipfile.ZipFile(GEO / "sim3464_database.zip") as z:
            for n in z.namelist():
                if "/Geodatabase/" in n and not n.startswith("__MACOSX"):
                    z.extract(n, GEO)


def build(name="jezero"):
    unpack()
    rules = json.loads((ROOT / "config" / "rules.json").read_text())
    k = rules["grid_m"]
    mapping = rules["geology_to_ground"]
    with rasterio.open(ROOT / "data" / name / "dtm.tif") as src:
        crs = src.crs
        tr = src.transform * src.transform.scale(k, k)
        shape = (src.height // k, src.width // k)

    units = gpd.read_file(GDB, layer="GeoUnits_v1").to_crs(crs)
    names = sorted(units["name"].unique())
    code = {n: i + 1 for i, n in enumerate(names)}
    unit_grid = features.rasterize(
        ((g, code[n]) for g, n in zip(units.geometry, units["name"])),
        out_shape=shape, transform=tr, fill=0, dtype="uint16")

    ground = np.zeros(shape, "uint8")
    for n, c in code.items():
        g = mapping.get(n, mapping["_default"])
        ground[unit_grid == c] = GROUND.index(g)

    out = ROOT / "data" / name / "ground.npz"
    np.savez_compressed(out, ground=ground, units=unit_grid, unit_names=np.array(["(none)"] + names))
    for i, g in enumerate(GROUND):
        print(f"{g:9s} {np.mean(ground == i):6.1%}")
    return out


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "jezero")
