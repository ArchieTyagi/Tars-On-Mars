"""Climb and descent along the walk."""
import numpy as np
from fastapi.testclient import TestClient

from api.main import app
from tests.test_route import flat_site, ll

c = TestClient(app)
BASE = [77.4508, 18.4447]


def ramp_site():
    s = flat_site()
    s.height = np.tile(np.arange(60, dtype="float32"), (60, 1))  # 1 m higher every cell to the east
    return s


def test_out_and_back_on_a_ramp():
    s = ramp_site()
    r = s.plan(ll(s, 30, 10), [ll(s, 30, 40)])
    e = r["elevation"]
    assert e["climb_m"] == 30.0 and e["descent_m"] == 30.0   # up 30 m going east, down 30 m coming back
    assert e["start_m"] == 10.0 and e["highest_m"] == 40.0 and e["lowest_m"] == 10.0
    assert e["highest_above_start_m"] == 30.0 and e["lowest_below_start_m"] == 0.0
    out, back = r["legs"]
    assert (out["climb_m"], out["descent_m"]) == (30.0, 0.0) and (back["climb_m"], back["descent_m"]) == (0.0, 30.0)


def test_small_wiggles_in_the_map_are_not_counted_as_climbing():
    """A height map is never perfectly smooth. On a gentle slope (10 cm up per cell) with 10 cm of
    jitter, the ground seems to go up 30 cm, down 10 cm, up 30 cm... Adding every rise would
    report 4.5 m of climb for a real 3 m."""
    s = flat_site()
    jitter = np.where(np.arange(60) % 2 == 0, 0.1, -0.1)
    s.height = np.tile((0.1 * np.arange(60) + jitter).astype("float32"), (60, 1))
    e = s.plan(ll(s, 30, 10), [ll(s, 30, 40)])["elevation"]
    assert abs(e["climb_m"] - 3.0) <= 0.25 and e["climb_m"] == e["descent_m"]


def test_turning_points_keep_real_hills_and_drop_ripples():
    from planner.route import turning_points
    h = np.array([0, 0.2, 0.1, 0.3, 5.0, 4.8, 4.9, 2.0, 2.2, 6.0, 6.0])
    assert turning_points(h, 0.5) == [0, 4, 7, 9, 10]    # start, top of hill, bottom of dip, top, end
    assert turning_points(np.zeros(5), 0.5) == [0, 4]
    assert turning_points(np.array([1.0]), 0.5) == [0]


def test_flat_ground_has_no_climb():
    s = flat_site()
    e = s.plan(ll(s, 30, 10), [ll(s, 30, 40)])["elevation"]
    assert e["climb_m"] == 0.0 and e["descent_m"] == 0.0


def test_profile_on_the_real_map():
    j = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47], [77.43, 18.455]]}).json()
    h, d, e = j["height_m"], j["dist_m"], j["elevation"]
    assert len(h) == len(d) == len(j["path"])
    assert d[0] == 0 and all(b >= a for a, b in zip(d, d[1:])) and abs(d[-1] / 1000 - j["km"]) < 0.01
    # a loop ends where it starts, so what goes up must come down
    assert h[0] == h[-1] and abs(e["climb_m"] - e["descent_m"]) < 0.11
    assert e["highest_m"] == max(h) and e["lowest_m"] == min(h) and e["start_m"] == h[0]
    # each leg is measured on its own, so a ripple at a stop can count in a leg but not in the whole: under 0.5 m per stop
    assert abs(sum(l["climb_m"] for l in j["legs"]) - e["climb_m"]) < 0.6 * len(j["legs"])
    assert e["climb_m"] >= e["highest_m"] - e["start_m"]  # you climb at least as much as the highest point is above you
    # independent look-up of the same spots
    for i in (0, len(h) // 3, len(h) // 2):
        lon, lat = j["path"][i]
        assert abs(c.get(f"/api/point?lon={lon}&lat={lat}").json()["height_m"] - h[i]) < 0.051


def test_profile_on_the_moon_too():
    import json
    from pathlib import Path
    demo = json.loads((Path(__file__).parent / "moon_demo.json").read_text())
    j = c.post("/api/plan", json={"site": "moon", **demo}).json()
    e = j["elevation"]
    assert len(j["height_m"]) == len(j["path"]) and e["climb_m"] > 0 and abs(e["climb_m"] - e["descent_m"]) < 0.11
