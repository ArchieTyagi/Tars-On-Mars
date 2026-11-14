from fastapi.testclient import TestClient

from api.main import app

c = TestClient(app)
BASE = [77.4508, 18.4447]


def test_site():
    r = c.get("/api/site").json()
    assert r["shape"] == [1250, 1250]
    assert r["bounds"]["west"] < BASE[0] < r["bounds"]["east"]


def test_plan_ok():
    r = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]]})
    assert r.status_code == 200
    j = r.json()
    assert j["km"] > 0 and len(j["path"]) > 10 and j["o2_ok"]


def test_plan_bad_stop_gives_clear_error():
    r = c.post("/api/plan", json={"base": BASE, "stops": [[10.0, 10.0]]})
    assert r.status_code == 422 and "outside" in r.json()["detail"]


def test_slider_changes_route_risk():
    a = c.post("/api/plan", json={"base": BASE, "stops": [[77.43, 18.485]]}).json()
    b = c.post("/api/plan", json={"base": BASE, "stops": [[77.43, 18.485]], "slope_limit": 12}).json()
    assert b["max_slope"] <= 12 <= a["max_slope"] or b["km"] >= a["km"]


def test_layers_are_png():
    for u in ["/api/layers/zones.png", "/api/layers/hillshade.png",
              f"/api/layers/safe_range.png?lon={BASE[0]}&lat={BASE[1]}"]:
        r = c.get(u)
        assert r.status_code == 200 and r.content[:4] == b"\x89PNG"


def test_point_lookup():
    j = c.get(f"/api/point?lon={BASE[0]}&lat={BASE[1]}").json()
    assert j["inside"] and j["zone"] == "GO" and -2700 < j["height_m"] < -2400
    assert c.get("/api/point?lon=10&lat=10").json() == {"inside": False}
