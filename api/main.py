"""Web API the frontend calls. Run: uvicorn api.main:app --reload"""
import io
from functools import lru_cache
from typing import List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from matplotlib.colors import LightSource
from PIL import Image
from pydantic import BaseModel, Field

from planner.route import Site

app = FastAPI(title="TARS on Mars")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@lru_cache(maxsize=8)
def site(limit: Optional[float] = None) -> Site:
    s = Site()
    s.set_limit(limit)
    return s


def bounds(s: Site):
    w, n = s.cell_to_lonlat(-0.5, -0.5)
    e, so = s.cell_to_lonlat(s.zone.shape[0] - 0.5, s.zone.shape[1] - 0.5)
    return {"west": w, "south": so, "east": e, "north": n}


def png(rgba: np.ndarray) -> Response:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG", optimize=True)
    return Response(buf.getvalue(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


class PlanIn(BaseModel):
    base: List[float] = Field(..., min_length=2, max_length=2, description="[lon, lat]")
    stops: List[List[float]] = Field(..., min_length=1, max_length=6)
    slope_limit: Optional[float] = Field(None, ge=5, le=35)
    # mission settings, chosen by the user (defaults come from config/rules.json)
    o2_hours: Optional[float] = Field(None, gt=0, le=24, description="suit oxygen supply, hours")
    o2_reserve: Optional[float] = Field(None, ge=0, lt=1, description="share kept untouched, 0.25 = 25%")
    walk_speed_kmh: Optional[float] = Field(None, gt=0, le=10)
    # sun check (optional): season and the Mars local time you set off
    ls: Optional[float] = Field(None, ge=0, lt=360, description="season, Ls degrees (0 = northern spring)")
    start_ltst_h: Optional[float] = Field(None, ge=0, lt=24, description="Mars local solar time at start, hours")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/site")
def site_info():
    s = site()
    b = bounds(s)
    return {"name": "Jezero Crater", "body": "mars", "bounds": b,
            "center": [(b["west"] + b["east"]) / 2, (b["south"] + b["north"]) / 2],
            "grid_m": s.rules["grid_m"], "shape": list(s.zone.shape), "rules": s.rules,
            "default_base": [77.4508, 18.4447]}


@app.post("/api/plan")
def plan(req: PlanIn):
    s = site(round(req.slope_limit, 1) if req.slope_limit else None).with_settings(
        o2_hours=req.o2_hours, o2_reserve=req.o2_reserve, walk_speed_kmh=req.walk_speed_kmh)
    try:
        r = s.plan(tuple(req.base), [tuple(p) for p in req.stops], ls_deg=req.ls, start_ltst_h=req.start_ltst_h)
    except ValueError as e:
        raise HTTPException(422, str(e))
    r["path"] = [[round(lon, 6), round(lat, 6)] for lon, lat in r["path"]]
    return r


@app.get("/api/point")
def point(lon: float, lat: float):
    """What's under one spot: height, slope, zone. For the map's hover readout."""
    s = site()
    r, c = s.lonlat_to_cell(lon, lat)
    if not (0 <= r < s.zone.shape[0] and 0 <= c < s.zone.shape[1]):
        return {"inside": False}
    names = ["GO", "CAUTION", "NO-GO"]
    h = float(s.height[r, c])
    sl = float(s.slope[r, c])
    return {"inside": True, "height_m": None if np.isnan(h) else round(h, 1),
            "slope_deg": None if np.isnan(sl) else round(sl, 1), "zone": names[int(s.zone[r, c])]}


@app.get("/api/sun")
def sun(ls: float, ltst_h: float):
    """Sun height and direction over the site at a given season and Mars local time."""
    from pipeline.sun import sun_position
    b = bounds(site())
    el, az = sun_position((b["south"] + b["north"]) / 2, ls, ltst_h)
    return {"elevation_deg": round(el, 2), "azimuth_deg": round(az, 2), "up": el > 0}


@app.get("/api/terrain")
def terrain(step: int = 4):
    """Height grid for the 3D view, every `step` cells (4 = 16 m spacing).
    Raw little-endian float32, row by row from north to south. Size + spacing in the headers."""
    s = site()
    step = max(1, min(step, 16))
    h = s.height[::step, ::step].astype("<f4")
    h = np.where(np.isnan(h), float(np.nanmin(h)), h)
    return Response(h.tobytes(), media_type="application/octet-stream", headers={
        "X-Rows": str(h.shape[0]), "X-Cols": str(h.shape[1]),
        "X-Dx-M": f"{s.dx * step:.4f}", "X-Dy-M": f"{s.dy * step:.4f}",
        "Access-Control-Expose-Headers": "X-Rows, X-Cols, X-Dx-M, X-Dy-M"})


@app.get("/api/layers/zones.png")
def zones(slope_limit: Optional[float] = None):
    z = site(slope_limit).zone
    rgba = np.zeros(z.shape + (4,), "uint8")
    rgba[z == 1] = (245, 166, 35, 150)  # caution
    rgba[z == 2] = (208, 2, 27, 170)    # no-go
    return png(rgba)


@app.get("/api/layers/hillshade.png")
def hillshade():
    s = site()
    h = LightSource(315, 45).hillshade(np.nan_to_num(s.height, nan=float(np.nanmean(s.height))),
                                       dx=4, dy=4, vert_exag=2)
    g = (h * 255).astype("uint8")
    return png(np.dstack([g, g, g, np.full_like(g, 255)]))


@app.get("/api/layers/safe_range.png")
def safe_range(lon: float, lat: float):
    s = site()
    ok = s.safe_range((lon, lat))
    rgba = np.zeros(ok.shape + (4,), "uint8")
    rgba[~ok] = (0, 0, 0, 140)  # darken what you can't reach and come back from
    return png(rgba)
