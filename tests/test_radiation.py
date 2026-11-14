"""Radiation picked up during the outing, from the rates measured on the surface."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from planner import radiation

c = TestClient(app)
BASE = [77.4508, 18.4447]


def test_rates_are_the_published_measurements():
    assert radiation.outing("mars", 24)["dose_usv"] == 640.0     # Curiosity RAD: 0.64 mSv per day (Hassler et al. 2014)
    assert radiation.outing("moon", 24)["dose_usv"] == 1369.0    # Chang'E-4 LND: 1369 uSv per day (Zhang et al. 2020)


def test_dose_grows_in_step_with_time_outside():
    a, b = radiation.outing("mars", 2), radiation.outing("mars", 6)
    assert abs(b["dose_usv"] - 3 * a["dose_usv"]) < 0.11 and radiation.outing("mars", 0)["dose_usv"] == 0
    assert abs(a["dose_usv"] - 2 * a["rate_usv_per_h"]) < 0.11


def test_unknown_body_gets_no_made_up_number():
    assert radiation.outing("venus", 5) is None


def test_plan_says_where_the_number_was_measured():
    j = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]], "stop_minutes": 30}).json()
    r = j["radiation"]
    # whole outing: walking + time at stops ("hours" is shown rounded to 0.01 h, hence the small allowance)
    assert abs(r["dose_usv"] - 640.0 * j["hours"] / 24) < 0.05 + 640.0 / 24 * 0.005
    assert "Gale" in r["measured_at"] and "not" in r["note"] and "solar" in r["note"].lower()
    k = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]], "stop_minutes": 120}).json()
    assert k["radiation"]["dose_usv"] > r["dose_usv"]


def test_moon_plan_uses_the_moon_measurement():
    demo = json.loads((Path(__file__).parent / "moon_demo.json").read_text())
    j = c.post("/api/plan", json={"site": "moon", **demo}).json()
    assert abs(j["radiation"]["dose_usv"] - 1369.0 * j["hours"] / 24) < 0.05 + 1369.0 / 24 * 0.005
    assert "Chang" in j["radiation"]["measured_at"]
