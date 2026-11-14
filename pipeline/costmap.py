"""Build the planning grid: slope, roughness, GO/CAUTION/NO-GO, and walking cost."""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

import math

from pipeline.layers import block_max, ground_scale_x, roughness, slope_deg

ROOT = Path(__file__).resolve().parents[1]
GO, CAUTION, NOGO = 0, 1, 2


def load_rules():
    return json.loads((ROOT / "config" / "rules.json").read_text())


GROUND = ["default", "bedrock", "regolith", "sand"]  # same order as pipeline/geology.py


def classify(slope, rules, ground=None, limit_override=None):
    """GO / CAUTION / NO-GO for every cell.
    ground = optional grid of ground-type codes (index into GROUND).
    limit_override = the what-if slider: one limit everywhere, ground types ignored."""
    lim = np.full(slope.shape, float(limit_override or rules["slope_limit_deg"]["default"]), "float32")
    if ground is not None and limit_override is None:
        for i, name in enumerate(GROUND):
            lim[ground == i] = rules["slope_limit_deg"].get(name, rules["slope_limit_deg"]["default"])
    zone = np.full(slope.shape, GO, "uint8")
    zone[slope >= lim * rules["caution_from"]] = CAUTION
    zone[(slope >= lim) | np.isnan(slope)] = NOGO
    return zone, lim


def walk_cost(slope, zone, rules):
    """Cost per cell. 1 = flat easy ground. NO-GO = -1 (route can't enter)."""
    s = np.nan_to_num(slope, nan=90.0)
    cost = 1.0 + rules["slope_slowdown_per_deg"] * s
    cost[zone == CAUTION] *= rules["caution_cost"]
    cost[zone == NOGO] = -1
    return cost.astype("float32")


def site_config(name):
    return json.loads((ROOT / "config" / f"{name}.json").read_text())


def build(name="jezero"):
    rules = load_rules()
    cfg = site_config(name)
    k = cfg.get("grid_m", rules["grid_m"])
    with rasterio.open(ROOT / "data" / name / "dtm.tif") as src:
        dem = src.read(1)
        cell = src.res[0]
        crs = src.crs
        step = max(1, int(round(k / cell)))
        transform = src.transform * src.transform.scale(step, step)
        mid_y = src.transform.f + src.transform.e * dem.shape[0] / 2
    radius = float(cfg.get("radius_m", 3396190.0))
    if "+proj=eqc" in crs.to_proj4():
        # equirectangular grid: only true to size at the equator
        kx = ground_scale_x(math.degrees(mid_y / radius))
    else:
        kx = 1.0  # polar stereographic near the pole: true to size within 0.01%
    slope = block_max(slope_deg(dem, cell, cell * kx), step)
    rough = roughness(dem, step)
    height = dem[: slope.shape[0] * step, : slope.shape[1] * step].reshape(
        slope.shape[0], step, slope.shape[1], step).mean(axis=(1, 3)).astype("float32")
    gfile = ROOT / "data" / name / "ground.npz"
    ground = np.load(gfile)["ground"][: slope.shape[0], : slope.shape[1]] if gfile.exists() else None
    if ground is None:
        print("no ground-type map for this site, default slope limit everywhere")
    zone, _ = classify(slope, rules, ground)
    efile = ROOT / "data" / name / "slope_err.tif"
    slope_err = None
    if efile.exists():
        with rasterio.open(efile) as src:
            slope_err = block_max(src.read(1).astype("float32"), step)[: slope.shape[0], : slope.shape[1]]
    out = ROOT / "data" / name / "layers.npz"
    np.savez_compressed(out, slope=slope, rough=rough, height=height, zone=zone, kx=kx,
                        ground=ground if ground is not None else np.zeros_like(zone),
                        slope_err=slope_err if slope_err is not None else np.full(slope.shape, np.nan, "float32"),
                        radius=radius, body=cfg.get("body", "mars"),
                        transform=np.array(transform)[:6], crs=str(crs))
    print(f"{name}: cell {k} m, east-west scale {kx:.4f}")
    print(f"grid {zone.shape} at {k} m | GO {np.mean(zone==GO):.1%}  CAUTION {np.mean(zone==CAUTION):.1%}  NO-GO {np.mean(zone==NOGO):.1%}")
    print(f"slope p50 {np.nanpercentile(slope,50):.1f}  p95 {np.nanpercentile(slope,95):.1f}  max {np.nanmax(slope):.1f} deg | height {np.nanmin(height):.0f}..{np.nanmax(height):.0f} m")
    return out


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "jezero")
