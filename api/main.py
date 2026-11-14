"""Web API the frontend calls. Run: uvicorn api.main:app --reload"""
import io
from functools import lru_cache
from typing import List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from matplotlib.colors import LightSource
from PIL import Image
from pydantic import BaseModel, Field

from planner.route import Site

app = FastAPI(title="TARS on Mars")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


SITES = ["jezero", "moon"]


@lru_cache(maxsize=16)
def site(limit: Optional[float] = None, name: str = "jezero") -> Site:
    if name not in SITES:
        raise HTTPException(404, f"unknown site {name}, try one of {SITES}")
    s = Site(name)
    s.set_limit(limit)
    return s


def site_cfg(name):
    import json
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parents[1] / "config" / f"{name}.json").read_text())


def bounds(s: Site):
    """For Mars (lon/lat grid) these are the true edges. For polar maps the edges
    are curved in lon/lat, so this is the box around the four corners."""
    R, C = s.zone.shape
    corners = [s.cell_to_lonlat(r, c) for r, c in ((-0.5, -0.5), (-0.5, C - 0.5), (R - 0.5, -0.5), (R - 0.5, C - 0.5))]
    lons, lats = [p[0] for p in corners], [p[1] for p in corners]
    return {"west": min(lons), "south": min(lats), "east": max(lons), "north": max(lats),
            "corners": corners}


def png(rgba: np.ndarray) -> Response:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG", optimize=True)
    return Response(buf.getvalue(), media_type="image/png",
                    headers={"Cache-Control": "public, max-age=3600"})


# what the scout helicopter reported (kept in memory while the server runs)
OBSERVATIONS: dict = {n: [] for n in SITES}


class ObservationIn(BaseModel):
    site: str = "jezero"
    lonlat: List[float] = Field(..., min_length=2, max_length=2)
    finding: str = Field(..., pattern="^(safe|blocked)$")
    radius_m: float = Field(20, gt=0, le=200)


class PlanIn(BaseModel):
    site: str = "jezero"
    base: List[float] = Field(..., min_length=2, max_length=2, description="[lon, lat]")
    stops: List[List[float]] = Field(..., min_length=1, max_length=6)
    slope_limit: Optional[float] = Field(None, ge=5, le=35)
    # mission settings, chosen by the user (defaults come from config/rules.json)
    o2_hours: Optional[float] = Field(None, gt=0, le=24, description="suit oxygen supply, hours")
    o2_reserve: Optional[float] = Field(None, ge=0, lt=1, description="share kept untouched, 0.25 = 25%")
    walk_speed_kmh: Optional[float] = Field(None, gt=0, le=10)
    # radio line-of-sight: antenna heights above ground
    base_antenna_m: Optional[float] = Field(None, ge=0, le=100)
    suit_antenna_m: Optional[float] = Field(None, ge=0, le=10)
    # sun check (optional): season and the Mars local time you set off
    ls: Optional[float] = Field(None, ge=0, lt=360, description="season, Ls degrees (0 = northern spring)")
    start_ltst_h: Optional[float] = Field(None, ge=0, lt=24, description="Mars local solar time at start, hours")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/sites")
def sites():
    return [{"id": n, "name": site_cfg(n)["name"], "body": site_cfg(n).get("body", "mars")} for n in SITES]


@app.get("/api/site")
def site_info(site_id: str = Query("jezero", alias="site")):
    s = site(None, site_id)
    cfg = site_cfg(site_id)
    b = bounds(s)
    r0, c0 = (np.array(s.zone.shape) // 2)
    go = np.argwhere(s.zone == 0)
    mid = go[np.argmin(np.hypot(go[:, 0] - r0, go[:, 1] - c0))]
    return {"id": site_id, "name": cfg["name"], "body": s.body, "bounds": b,
            "center": list(s.cell_to_lonlat(r0, c0)),
            "grid_m": round(s.dy, 2), "shape": list(s.zone.shape), "rules": s.rules,
            "default_base": cfg.get("default_base") or list(s.cell_to_lonlat(*mid)),
            "has_ground_types": s.ground is not None and bool(s.ground.any()),
            "has_slope_error": s.slope_err is not None,
            "sun_check": s.body == "mars",
            "source": cfg.get("source")}


@app.post("/api/plan")
def plan(req: PlanIn):
    s = site(round(req.slope_limit, 1) if req.slope_limit else None, req.site)
    obs = OBSERVATIONS.get(req.site, [])
    if obs:
        from planner.scout import apply_observations
        s = apply_observations(s, obs)
    s = s.with_settings(
        o2_hours=req.o2_hours, o2_reserve=req.o2_reserve, walk_speed_kmh=req.walk_speed_kmh,
        base_antenna_m=req.base_antenna_m, suit_antenna_m=req.suit_antenna_m)
    try:
        r = s.plan(tuple(req.base), [tuple(p) for p in req.stops], ls_deg=req.ls, start_ltst_h=req.start_ltst_h)
    except ValueError as e:
        raise HTTPException(422, str(e))
    r["path"] = [[round(lon, 6), round(lat, 6)] for lon, lat in r["path"]]
    r["observations"] = obs
    r["site"] = req.site
    if r["light"] is None and req.ls is not None and s.body != "mars":
        r["light_note"] = "sun and shadow check is only built for Mars so far"
    return r


@app.post("/api/observe")
def observe(o: ObservationIn):
    """Helicopter report: this spot is safe / blocked. The next plan uses it."""
    site(None, o.site)  # 404 if unknown
    d = o.model_dump()
    OBSERVATIONS[o.site].append({k: v for k, v in d.items() if k != "site"})
    return {"observations": OBSERVATIONS[o.site]}


@app.delete("/api/observe")
def clear_observations(site_id: str = Query("jezero", alias="site")):
    OBSERVATIONS.get(site_id, []).clear()
    return {"observations": []}


@app.get("/api/point")
def point(lon: float, lat: float, site_id: str = Query("jezero", alias="site")):
    """What's under one spot: height, slope, zone. For the map's hover readout."""
    s = site(None, site_id)
    r, c = s.lonlat_to_cell(lon, lat)
    if not (0 <= r < s.zone.shape[0] and 0 <= c < s.zone.shape[1]):
        return {"inside": False}
    names = ["GO", "CAUTION", "NO-GO"]
    h = float(s.height[r, c])
    sl = float(s.slope[r, c])
    err = None if s.slope_err is None or np.isnan(s.slope_err[r, c]) else round(float(s.slope_err[r, c]), 1)
    return {"inside": True, "height_m": None if np.isnan(h) else round(h, 1),
            "slope_deg": None if np.isnan(sl) else round(sl, 1), "slope_err_deg": err,
            "zone": names[int(s.zone[r, c])]}


@app.get("/api/layers/radio.png")
def radio_layer(lon: float, lat: float, base_antenna_m: float = 3.0, suit_antenna_m: float = 2.0,
                site_id: str = Query("jezero", alias="site")):
    """Where a suit can talk to base directly. Darkened = no line of sight."""
    from planner.radio import viewshed
    s = site(None, site_id)
    cell = s.lonlat_to_cell(lon, lat)
    if not (0 <= cell[0] < s.zone.shape[0] and 0 <= cell[1] < s.zone.shape[1]):
        raise HTTPException(422, "base is outside the map")
    v = viewshed(s, cell, base_antenna_m, suit_antenna_m, step=4)
    rgba = np.zeros(v.shape + (4,), "uint8")
    rgba[~v] = (40, 0, 60, 150)  # purple tint = no radio
    return png(rgba)


@app.get("/api/sun")
def sun(ls: float, ltst_h: float, site_id: str = Query("jezero", alias="site")):
    """Sun height and direction over the site at a given season and Mars local time."""
    from pipeline.sun import sun_position
    if site(None, site_id).body != "mars":
        raise HTTPException(422, "the sun model is only built for Mars so far")
    b = bounds(site(None, site_id))
    el, az = sun_position((b["south"] + b["north"]) / 2, ls, ltst_h)
    return {"elevation_deg": round(el, 2), "azimuth_deg": round(az, 2), "up": el > 0}


@app.get("/api/terrain")
def terrain(step: int = 4, site_id: str = Query("jezero", alias="site")):
    """Height grid for the 3D view, every `step` cells (4 = 16 m spacing on Jezero).
    Raw little-endian float32, row by row from the top of the map. Size + spacing in the headers."""
    s = site(None, site_id)
    step = max(1, min(step, 16))
    h = s.height[::step, ::step].astype("<f4")
    h = np.where(np.isnan(h), float(np.nanmin(h)), h)
    return Response(h.tobytes(), media_type="application/octet-stream", headers={
        "X-Rows": str(h.shape[0]), "X-Cols": str(h.shape[1]),
        "X-Dx-M": f"{s.dx * step:.4f}", "X-Dy-M": f"{s.dy * step:.4f}",
        "Access-Control-Expose-Headers": "X-Rows, X-Cols, X-Dx-M, X-Dy-M"})


@app.get("/api/layers/zones.png")
def zones(slope_limit: Optional[float] = None, site_id: str = Query("jezero", alias="site")):
    z = site(slope_limit, site_id).zone
    rgba = np.zeros(z.shape + (4,), "uint8")
    rgba[z == 1] = (245, 166, 35, 150)  # caution
    rgba[z == 2] = (208, 2, 27, 170)    # no-go
    return png(rgba)


@app.get("/api/layers/hillshade.png")
def hillshade(site_id: str = Query("jezero", alias="site")):
    s = site(None, site_id)
    h = LightSource(315, 45).hillshade(np.nan_to_num(s.height, nan=float(np.nanmean(s.height))),
                                       dx=s.dx, dy=s.dy, vert_exag=2)
    g = (h * 255).astype("uint8")
    return png(np.dstack([g, g, g, np.full_like(g, 255)]))


@app.get("/api/layers/safe_range.png")
def safe_range(lon: float, lat: float, site_id: str = Query("jezero", alias="site")):
    s = site(None, site_id)
    ok = s.safe_range((lon, lat))
    rgba = np.zeros(ok.shape + (4,), "uint8")
    rgba[~ok] = (0, 0, 0, 140)  # darken what you can't reach and come back from
    return png(rgba)
