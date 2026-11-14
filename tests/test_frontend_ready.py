"""Things the web app needs from the server beyond the planner itself."""
import io
import json
from pathlib import Path

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from api import main
from api.main import app, site

c = TestClient(app)
BASE = [77.4508, 18.4447]


def web_app(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>TARS</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path.parent / "secret.txt").write_text("keep out")
    a = FastAPI()

    @a.get("/api/health")
    def health():
        return {"ok": True}
    main.attach_frontend(a, tmp_path)
    return TestClient(a)


def test_any_page_of_the_web_app_survives_a_refresh(tmp_path):
    w = web_app(tmp_path)
    for page in ("/", "/planner", "/planner/moon", "/about"):
        r = w.get(page)
        assert r.status_code == 200 and "TARS" in r.text, page
    assert "console.log" in w.get("/assets/app.js").text
    assert w.get("/api/health").json() == {"ok": True}          # the API still answers first


def test_missing_files_and_wrong_api_addresses_are_real_404s(tmp_path):
    w = web_app(tmp_path)
    assert w.get("/assets/missing.js").status_code == 404       # not the home page pretending to be a script
    r = w.get("/api/nope")
    assert r.status_code == 404 and "api" in r.json()["detail"].lower()


def test_nothing_outside_the_web_folder_can_be_read(tmp_path):
    web_app(tmp_path)
    assert main.web_file(tmp_path, "../secret.txt") is None
    assert main.web_file(tmp_path, "assets/../../secret.txt") is None
    assert main.web_file(tmp_path, "assets/app.js") == (tmp_path / "assets" / "app.js").resolve()


def test_big_answers_are_compressed_but_pictures_are_left_alone():
    r = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]]})
    assert r.headers.get("content-encoding") == "gzip" and r.json()["km"] > 0
    assert c.get("/api/rover").headers.get("content-encoding") == "gzip"
    assert c.get("/api/layers/zones.png").headers.get("content-encoding") is None   # PNG and JPEG are already compressed
    assert c.get("/api/health").headers.get("content-encoding") is None             # tiny answers are not worth it


def rgba(url):
    r = c.get(url)
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG", url
    return np.array(Image.open(io.BytesIO(r.content)).convert("RGBA"))


def legend_of(layer_id, site_id="jezero"):
    layers = c.get(f"/api/site?site={site_id}").json()["layers"]
    return next(l for l in layers if l["id"] == layer_id)["legend"]


def hex_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def test_slope_layer_colors_match_its_legend():
    s = site(None, "jezero")
    img = rgba("/api/layers/slope.png")
    assert img.shape[:2] == s.slope.shape
    leg = legend_of("slope")
    assert [l["from_deg"] for l in leg] == [0, 5, 10, 15, 20, 25]
    for l in leg:   # one real cell from every class must be drawn in that class's color
        hi = l.get("to_deg", 91)
        cells = np.argwhere((s.slope >= l["from_deg"]) & (s.slope < hi))
        r, col = cells[len(cells) // 2]
        assert tuple(img[r, col, :3]) == hex_rgb(l["color"]), l
    gap = np.argwhere(np.isnan(s.slope))
    if len(gap):
        assert img[gap[0][0], gap[0][1], 3] == 0      # no data: see-through


def test_ground_type_layer_colors_match_its_legend():
    from pipeline.costmap import GROUND
    s = site(None, "jezero")
    img = rgba("/api/layers/ground.png")
    leg = {l["label"]: l["color"] for l in legend_of("ground")}
    assert len(leg) >= 3
    for i, name in enumerate(GROUND):
        cells = np.argwhere(s.ground == i)
        if len(cells) and name != "default":
            r, col = cells[len(cells) // 2]
            match = [lab for lab in leg if name in lab.lower() or (name == "regolith" and "delta" in lab.lower())]
            assert match and tuple(img[r, col, :3]) == hex_rgb(leg[match[0]]), name
    r = c.get("/api/layers/ground.png?site=moon")
    assert r.status_code == 404 and "ground" in r.json()["detail"].lower()


def test_moon_slope_risk_layer_is_the_22_8_percent_finding():
    s = site(None, "moon")
    img = rgba("/api/layers/slope_risk.png?site=moon")
    assert img.shape[:2] == s.zone.shape
    share = (img[..., 3] > 0).mean()
    assert abs(share - 0.228) < 0.005, share     # README: 22.8% of the map looks walkable but could be over the limit
    r = c.get("/api/layers/slope_risk.png")
    assert r.status_code == 404 and "slope error" in r.json()["detail"].lower()


def test_site_lists_every_layer_it_can_draw_and_every_one_works():
    for sid in ("jezero", "moon"):
        info = c.get(f"/api/site?site={sid}").json()
        ids = [l["id"] for l in info["layers"]]
        assert len(ids) == len(set(ids)) and {"hillshade", "zones", "slope", "safe_range", "radio"} <= set(ids)
        assert ("photo" in ids) == info["has_photo"] and ("minerals" in ids) == info["has_minerals"]
        assert ("ground" in ids) == info["has_ground_types"] and ("slope_risk" in ids) == info["has_slope_error"]
        b = info["default_base"]
        for l in info["layers"]:
            url = l["url"] + (f"&lon={b[0]}&lat={b[1]}" if l["needs_base"] else "")
            r = c.get(url)
            assert r.status_code == 200 and r.headers["content-type"] in ("image/png", "image/jpeg"), url
            assert l["name"] and l["about"]
            for item in l.get("legend", []):
                assert len(item["color"]) == 7 and item["color"][0] == "#" and item["label"]


def test_warm_up_gets_the_slow_pictures_ready():
    main._hillshade_png.cache_clear()
    main.warm_up()
    assert main._hillshade_png.cache_info().currsize == len(main.SITES)


def test_every_site_names_its_source():
    for sid in ("jezero", "moon"):
        assert c.get(f"/api/site?site={sid}").json()["source"], sid


def test_the_api_guide_covers_every_address_and_every_plan_field():
    guide = (Path(__file__).resolve().parents[1] / "docs" / "API.md").read_text()
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith("/api/"):
            assert path in guide, f"{path} is missing from docs/API.md"
    plan = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]], "ls": 120, "start_ltst_h": 9}).json()
    for field in plan:
        assert f"`{field}`" in guide, f"plan field {field} is missing from docs/API.md"
    for field in main.PlanIn.model_fields:
        assert f"`{field}`" in guide, f"plan input {field} is missing from docs/API.md"
