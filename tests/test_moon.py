"""Moon mode: same planner on NASA's LOLA south pole map (polar stereographic)."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / "data" / "moon" / "layers.npz").exists(),
                                reason="moon data not built (python -m pipeline.loader moon && python -m pipeline.costmap moon)")
c = TestClient(app)
DEMO = json.loads((ROOT / "tests" / "moon_demo.json").read_text())


def test_moon_site_info():
    j = c.get("/api/site?site=moon").json()
    assert j["body"] == "moon" and j["has_slope_error"] and not j["sun_check"]
    assert -90 < j["bounds"]["south"] < j["bounds"]["north"] < -89  # right by the south pole


def test_lonlat_round_trip_in_polar_map():
    from planner.route import Site
    m = Site("moon")
    rc = m.lonlat_to_cell(*DEMO["base"])
    lon, lat = m.cell_to_lonlat(*rc)
    assert m.lonlat_to_cell(lon, lat) == rc


def test_moon_plan_and_honest_flags():
    r = c.post("/api/plan", json={"site": "moon", "base": DEMO["base"], "stops": DEMO["stops"][:1],
                                  "ls": 0, "start_ltst_h": 9}).json()
    assert r["site"] == "moon" and r["km"] > 0
    assert r["light"] is None and "Mars" in r["light_note"]  # says so instead of faking it
    reasons = {x for t in r["scout"]["targets"] for x in t["reasons"]}
    assert any("slope error" in x for x in reasons)


def test_moon_point_has_slope_error():
    j = c.get(f"/api/point?site=moon&lon={DEMO['base'][0]}&lat={DEMO['base'][1]}").json()
    assert j["inside"] and j["slope_err_deg"] is not None


def test_unknown_site_is_404():
    assert c.get("/api/site?site=venus").status_code == 404
