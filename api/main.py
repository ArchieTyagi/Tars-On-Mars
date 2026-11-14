"""Web API the frontend calls. Run: uvicorn api.main:app --reload"""
import io
from functools import lru_cache
import math
from typing import Annotated, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from matplotlib.colors import LightSource
from PIL import Image
from pydantic import BaseModel, Field

from planner.route import Site

app = FastAPI(title="TARS on Mars")

from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

FIELD_NAMES = {"base": "base", "stops": "stops", "slope_limit": "slope limit", "o2_hours": "oxygen supply",
               "o2_reserve": "oxygen reserve", "walk_speed_kmh": "walking speed", "ls": "season (Ls)",
               "start_ltst_h": "start time", "base_antenna_m": "base antenna height",
               "suit_antenna_m": "suit antenna height", "stop_minutes": "time at each stop", "lonlat": "position", "finding": "finding",
               "radius_m": "radius", "lon": "longitude", "lat": "latitude", "observations": "helicopter reports",
               "sol": "sol", "ltst_h": "local time", "step": "step", "x": "x", "y": "y"}


@app.exception_handler(RequestValidationError)
async def readable_errors(request, exc):
    msgs = []
    for e in exc.errors():
        loc = [str(x) for x in e.get("loc", []) if x not in ("body", "query")]
        field = FIELD_NAMES.get(loc[0], loc[0]) if loc else "request body"
        t, ctx = e.get("type", ""), e.get("ctx", {}) or {}
        if t == "finite_number":
            msg = f"The {field} must be a real number (not NaN or infinity)."
        elif t == "json_invalid":
            msg = "The request body is not valid JSON."
        elif t in ("too_short", "too_long") and loc and loc[0] in ("base", "stops", "lonlat") and (loc[0] != "stops" or len(loc) > 1):
            msg = f"Each point in {field} needs exactly 2 numbers: [longitude, latitude]."
        elif t == "too_long":
            msg = f"Too many {field}: at most {ctx.get('max_length')}."
        elif t == "too_short":
            msg = f"Add at least {ctx.get('min_length')} {field[:-1] if field.endswith('s') else field}."
        elif t == "greater_than":
            msg = f"The {field} must be more than {ctx.get('gt')}."
        elif t == "greater_than_equal":
            msg = f"The {field} must be at least {ctx.get('ge')}."
        elif t == "less_than":
            msg = f"The {field} must be below {ctx.get('lt')}."
        elif t == "less_than_equal":
            msg = f"The {field} must be at most {ctx.get('le')}."
        elif not loc and t.endswith("_type"):
            msg = "The request body must be a JSON object."
        elif t.endswith("parsing") or t.endswith("_type"):
            msg = f"The {field} must be a number."
        elif t == "missing":
            msg = f"The {field} is missing."
        else:
            msg = f"Check the {field}: {e.get('msg')}."
        msgs.append(msg)
    return JSONResponse(status_code=422, content={"detail": " ".join(dict.fromkeys(msgs))})
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


SITES = ["jezero", "moon"]


@lru_cache(maxsize=len(SITES))
def base_site(name: str) -> Site:
    return Site(name)


@lru_cache(maxsize=8)
def _limited(limit: float, name: str) -> Site:
    import copy
    s = copy.copy(base_site(name))  # shares the big arrays, only zones/cost/limit are new
    s.set_limit(limit)
    return s


def site(limit: Optional[float] = None, name: str = "jezero") -> Site:
    if name not in SITES:
        raise HTTPException(404, f"Unknown site '{name}'. Try one of: {', '.join(SITES)}.")
    return base_site(name) if limit is None else _limited(round(float(limit), 1), name)


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


def png_bytes(rgba: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG", optimize=True)
    return buf.getvalue()


def png(data) -> Response:
    if isinstance(data, np.ndarray):
        data = png_bytes(data)
    return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


Num = Annotated[float, Field(allow_inf_nan=False)]
Point = Annotated[List[Num], Field(min_length=2, max_length=2)]


def num_q(default=..., **kw):
    """Query number that refuses NaN / infinity."""
    return Query(default, allow_inf_nan=False, **kw)


def _the(label: str) -> str:
    """'base' -> 'The base', 'stop 2' -> 'Stop 2'."""
    return label[0].upper() + label[1:] if label[-1].isdigit() else f"The {label}"


def cell_of(s: Site, lon: float, lat: float, label: str):
    """Grid cell for a lon/lat, or a clear 422 if it is not a real spot on this map."""
    if not (math.isfinite(lon) and math.isfinite(lat) and -360 <= lon <= 360 and -90 <= lat <= 90):
        raise HTTPException(422, f"{_the(label)} is not a real position (longitude -360..360, latitude -90..90).")
    try:
        r, c = s.lonlat_to_cell(lon, lat)
    except (ValueError, OverflowError):
        raise HTTPException(422, f"{_the(label)} is outside the map data.")
    if not (0 <= r < s.zone.shape[0] and 0 <= c < s.zone.shape[1]):
        raise HTTPException(422, f"{_the(label)} is outside the map data.")
    return r, c


class ObservationIn(BaseModel):
    """What the scout helicopter saw at one spot. Sent along with each plan, so every
    user only changes their own plan (the server keeps no shared state)."""
    lonlat: Point
    finding: str = Field(..., pattern="^(safe|blocked)$")
    radius_m: Num = Field(20, gt=0, le=200)


class PlanIn(BaseModel):
    site: str = "jezero"
    base: Point = Field(..., description="[lon, lat]")
    stops: List[Point] = Field(..., min_length=1, max_length=6)
    observations: List[ObservationIn] = Field([], max_length=50)
    slope_limit: Optional[Num] = Field(None, ge=5, le=35)
    # mission settings, chosen by the user (defaults come from config/rules.json)
    o2_hours: Optional[Num] = Field(None, gt=0, le=24, description="suit oxygen supply, hours")
    o2_reserve: Optional[Num] = Field(None, ge=0, lt=1, description="share kept untouched, 0.25 = 25%")
    walk_speed_kmh: Optional[Num] = Field(None, gt=0, le=10)
    stop_minutes: Optional[Num] = Field(None, ge=0, le=480, description="time spent working at each stop")
    # radio line-of-sight: antenna heights above ground
    base_antenna_m: Optional[Num] = Field(None, ge=0, le=100)
    suit_antenna_m: Optional[Num] = Field(None, ge=0, le=10)
    # sun check (optional): season and the Mars local time you set off
    ls: Optional[Num] = Field(None, ge=0, lt=360, description="season, Ls degrees (0 = northern spring)")
    start_ltst_h: Optional[Num] = Field(None, ge=0, lt=24, description="Mars local solar time at start, hours")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/convert")
def convert(site_id: str = Query("jezero", alias="site"), lon: Optional[float] = num_q(None),
            lat: Optional[float] = num_q(None), x: Optional[float] = num_q(None), y: Optional[float] = num_q(None)):
    """lon/lat <-> map meters for a site. Needed to draw polar maps (the Moon) on a flat screen."""
    s = site(None, site_id)
    if lon is not None and lat is not None:
        if not (-360 <= lon <= 360 and -90 <= lat <= 90):
            raise HTTPException(422, "Longitude must be -360..360 and latitude -90..90.")
        xx, yy = s._to_xy.transform(lon, lat)
        return {"x": xx, "y": yy}
    if x is not None and y is not None:
        lo, la = s._to_ll.transform(x, y)
        if not (math.isfinite(lo) and math.isfinite(la)):
            raise HTTPException(422, "Those map meters are not a real position on this body.")
        return {"lon": lo, "lat": la}
    raise HTTPException(422, "Give lon and lat, or x and y.")


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
            "has_minerals": getattr(s, "minerals", None) is not None,
            "sun_check": s.body == "mars",
            "crs": s.crs,
            "extent_xy": {"left": s.x0, "top": s.y0, "right": s.x0 + s.a * s.zone.shape[1],
                          "bottom": s.y0 + s.e * s.zone.shape[0]},
            "source": cfg.get("source")}


@app.post("/api/plan")
def plan(req: PlanIn):
    if (req.ls is None) != (req.start_ltst_h is None):
        raise HTTPException(422, "For the sun check give both the season (Ls) and the start time, or neither.")
    s = site(req.slope_limit, req.site)
    cell_of(s, *req.base, "base")
    for i, st in enumerate(req.stops, 1):
        cell_of(s, *st, f"stop {i}")
    for i, o in enumerate(req.observations, 1):
        cell_of(s, *o.lonlat, f"helicopter report {i}")
    obs = [o.model_dump() for o in req.observations]
    if obs:
        from planner.scout import apply_observations
        s = apply_observations(s, obs)
    s = s.with_settings(
        o2_hours=req.o2_hours, o2_reserve=req.o2_reserve, walk_speed_kmh=req.walk_speed_kmh, stop_minutes=req.stop_minutes,
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


@app.get("/api/point")
def point(lon: float = num_q(), lat: float = num_q(), site_id: str = Query("jezero", alias="site")):
    """What's under one spot: height, slope, zone. For the map's hover readout."""
    s = site(None, site_id)
    try:
        r, c = cell_of(s, lon, lat, "point")
    except HTTPException:
        return {"inside": False}
    names = ["GO", "CAUTION", "NO-GO"]
    h = float(s.height[r, c])
    sl = float(s.slope[r, c])
    err = None if s.slope_err is None or np.isnan(s.slope_err[r, c]) else round(float(s.slope_err[r, c]), 1)
    mineral = conf = None
    if getattr(s, "minerals", None) is not None:
        from pipeline.minerals import name_of
        mineral, conf = name_of(int(s.minerals[r, c]))
    return {"inside": True, "height_m": None if np.isnan(h) else round(h, 1),
            "slope_deg": None if np.isnan(sl) else round(sl, 1), "slope_err_deg": err,
            "mineral": mineral, "mineral_confidence": conf,
            "zone": names[int(s.zone[r, c])]}


@app.get("/api/layers/radio.png")
def radio_layer(lon: float = num_q(), lat: float = num_q(), base_antenna_m: float = num_q(3.0, ge=0, le=100),
                suit_antenna_m: float = num_q(2.0, ge=0, le=10),
                site_id: str = Query("jezero", alias="site")):
    """Where a suit can talk to base directly. Darkened = no line of sight."""
    from planner.radio import viewshed
    s = site(None, site_id)
    cell = cell_of(s, lon, lat, "base")
    v = viewshed(s, cell, base_antenna_m, suit_antenna_m, step=4)
    rgba = np.zeros(v.shape + (4,), "uint8")
    rgba[~v] = (40, 0, 60, 150)  # purple tint = no radio
    return png(rgba)


@app.get("/api/sun")
def sun(ls: float = num_q(ge=0, lt=360), ltst_h: float = num_q(ge=0, lt=24), site_id: str = Query("jezero", alias="site")):
    """Sun height and direction over the site at a given season and Mars local time."""
    from pipeline.sun import sun_position
    if site(None, site_id).body != "mars":
        raise HTTPException(422, "the sun model is only built for Mars so far")
    b = bounds(site(None, site_id))
    el, az = sun_position((b["south"] + b["north"]) / 2, ls, ltst_h)
    return {"elevation_deg": round(el, 2), "azimuth_deg": round(az, 2), "up": el > 0}


@app.get("/api/weather")
def weather(ls: float = num_q(ge=0, lt=360)):
    """Typical Jezero weather by hour for a season, from Perseverance's MEDA station."""
    from pipeline.weather import SEASONS, load, season_of
    w = load()
    if w is None:
        raise HTTPException(503, "Weather table not built yet (python -m pipeline.weather_build).")
    k = season_of(ls)
    return {"season": SEASONS[k][1], "units": w["units"], "source": w["source"],
            "hours": list(range(24)), **w["seasons"][str(k)],
            "note": "typical conditions, not a forecast; hours are Mars local solar time",
            "wind_note": (None if any(v is not None for v in w["seasons"][str(k)]["wind"]["mean"]) else
                          "no wind data for this season: MEDA's wind sensors were damaged by wind-blown sand "
                          "after sol 313 and processed wind is only published for earlier sols")}


@app.get("/api/sol_to_ls")
def sol_to_ls(sol: float = num_q(ge=0, le=100000)):
    """Season (Ls) for a Perseverance mission sol, Allison & McEwen 2000."""
    from pipeline.mars_time import ls_from_m20_sol, utc_from_m20_sol
    return {"sol": sol, "ls": round(ls_from_m20_sol(sol), 2), "utc": utc_from_m20_sol(sol).isoformat()}


@app.get("/api/terrain")
def terrain(step: int = Query(4, ge=1, le=16), site_id: str = Query("jezero", alias="site")):
    """Height grid for the 3D view, every `step` cells (4 = 16 m spacing on Jezero).
    Raw little-endian float32, row by row from the top of the map. Size + spacing in the headers."""
    s = site(None, site_id)
    h = s.height[::step, ::step].astype("<f4")
    h = np.where(np.isnan(h), float(np.nanmin(h)), h)
    return Response(h.tobytes(), media_type="application/octet-stream", headers={
        "X-Rows": str(h.shape[0]), "X-Cols": str(h.shape[1]),
        "X-Dx-M": f"{s.dx * step:.4f}", "X-Dy-M": f"{s.dy * step:.4f}",
        "Access-Control-Expose-Headers": "X-Rows, X-Cols, X-Dx-M, X-Dy-M"})


@app.get("/api/layers/zones.png")
def zones(slope_limit: Optional[float] = num_q(None, ge=5, le=35), site_id: str = Query("jezero", alias="site")):
    site(None, site_id)  # 404 if unknown
    return png(_zones_png(None if slope_limit is None else round(float(slope_limit), 1), site_id))


@lru_cache(maxsize=16)
def _zones_png(limit, name) -> bytes:
    z = site(limit, name).zone
    rgba = np.zeros(z.shape + (4,), "uint8")
    rgba[z == 1] = (245, 166, 35, 150)  # caution
    rgba[z == 2] = (208, 2, 27, 170)    # no-go
    return png_bytes(rgba)


@app.get("/api/minerals")
def minerals_legend():
    """Legend for the mineral layer, with the authors' own caveat."""
    from pipeline.minerals import CAVEAT, KEY
    return {"classes": [{"code": i, "name": n, "rgb_high": list(hi), "rgb_medium": list(med)}
                        for i, (n, hi, med) in enumerate(KEY, start=1)],
            "caveat": CAVEAT,
            "source": "Parente, Saranathan, Itoh, Tarnas, Seelos, Mustard (2021), Zenodo 10.5281/zenodo.5575824, CC BY 4.0"}


@app.get("/api/layers/minerals.png")
def minerals_layer(site_id: str = Query("jezero", alias="site")):
    if getattr(site(None, site_id), "minerals", None) is None:
        raise HTTPException(404, "No mineral map for this site.")
    return png(_minerals_png(site_id))


@lru_cache(maxsize=len(SITES))
def _minerals_png(name) -> bytes:
    s = site(None, name)
    from pipeline.minerals import KEY
    m = s.minerals
    rgba = np.zeros(m.shape + (4,), "uint8")
    for i, (_, hi, med) in enumerate(KEY, start=1):
        rgba[m == i] = (*hi, 200)
        rgba[m == 100 + i] = (*med, 150)
    return png_bytes(rgba)


@app.get("/api/layers/hillshade.png")
def hillshade(site_id: str = Query("jezero", alias="site")):
    site(None, site_id)  # 404 if unknown
    return png(_hillshade_png(site_id))


@lru_cache(maxsize=len(SITES))
def _hillshade_png(name) -> bytes:
    s = site(None, name)
    h = LightSource(315, 45).hillshade(np.nan_to_num(s.height, nan=float(np.nanmean(s.height))),
                                       dx=s.dx, dy=s.dy, vert_exag=2)
    g = (h * 255).astype("uint8")
    return png_bytes(np.dstack([g, g, g, np.full_like(g, 255)]))


@app.get("/api/layers/safe_range.png")
def safe_range(lon: float = num_q(), lat: float = num_q(), site_id: str = Query("jezero", alias="site"),
               slope_limit: Optional[float] = num_q(None, ge=5, le=35), o2_hours: Optional[float] = num_q(None, gt=0, le=24),
               o2_reserve: Optional[float] = num_q(None, ge=0, lt=1), walk_speed_kmh: Optional[float] = num_q(None, gt=0, le=10),
               stop_minutes: Optional[float] = num_q(None, ge=0, le=480)):
    """Where you can walk to AND get back from, with the same mission settings as the plan."""
    s = site(slope_limit, site_id).with_settings(o2_hours=o2_hours, o2_reserve=o2_reserve, walk_speed_kmh=walk_speed_kmh,
                                                stop_minutes=stop_minutes)
    cell_of(s, lon, lat, "base")
    try:
        s._check(s.lonlat_to_cell(lon, lat), "base")
    except ValueError as e:
        raise HTTPException(422, str(e))
    ok = s.safe_range((lon, lat))
    rgba = np.zeros(ok.shape + (4,), "uint8")
    rgba[~ok] = (0, 0, 0, 140)  # darken what you can't reach and come back from
    return png(rgba)


# serve the built frontend from the same server when it exists (one public link for everything)
from pathlib import Path as _P  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_DIST = _P(__file__).resolve().parents[1] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")
