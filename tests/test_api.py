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


def test_mission_settings_change_the_answer():
    body = {"base": BASE, "stops": [[77.46, 18.47]]}
    a = c.post("/api/plan", json=body).json()
    b = c.post("/api/plan", json={**body, "o2_hours": 2, "o2_reserve": 0.5}).json()
    assert a["settings"]["o2_hours"] == 8 and b["settings"]["o2_hours"] == 2
    assert b["usable_o2_h"] == 1.0 and b["o2_margin_h"] < a["o2_margin_h"]
    slow = c.post("/api/plan", json={**body, "walk_speed_kmh": 1}).json()
    assert abs(slow["hours"] - 2 * a["hours"]) < 0.05  # half the speed, double the time
    assert c.post("/api/plan", json={**body, "o2_reserve": 1.5}).status_code == 422


def test_terrain_grid():
    r = c.get("/api/terrain?step=5")
    rows, cols = int(r.headers["X-Rows"]), int(r.headers["X-Cols"])
    assert rows == cols == 250 and len(r.content) == rows * cols * 4
    assert abs(float(r.headers["X-Dx-M"]) - 20 * 0.9486) < 0.05


def test_sun_check_in_plan():
    body = {"base": BASE, "stops": [[77.46, 18.47]]}
    assert c.post("/api/plan", json=body).json()["light"] is None
    late = c.post("/api/plan", json={**body, "ls": 0, "start_ltst_h": 17.5}).json()["light"]
    assert late["sunset_before_home"] and late["start_ltst_h"] == 17.5
    noon = c.post("/api/plan", json={**body, "ls": 0, "start_ltst_h": 11}).json()["light"]
    assert not noon["sunset_before_home"] and not noon["low_sun"]
    s = c.get("/api/sun?ls=0&ltst_h=12").json()
    assert s["up"] and abs(s["elevation_deg"] - (90 - 18.455)) < 0.1


def test_observe_changes_the_next_plan():
    c.delete("/api/observe")
    body = {"base": BASE, "stops": [[77.46, 18.47]]}
    a = c.post("/api/plan", json=body).json()
    mid = a["path"][len(a["path"]) // 4]
    assert c.post("/api/observe", json={"lonlat": mid, "finding": "blocked", "radius_m": 30}).status_code == 200
    b = c.post("/api/plan", json=body).json()
    assert b["path"] != a["path"] and len(b["observations"]) == 1
    assert c.post("/api/observe", json={"lonlat": mid, "finding": "maybe"}).status_code == 422
    c.delete("/api/observe")
    assert c.post("/api/plan", json=body).json()["path"] == a["path"]


def test_radio_in_plan_and_layer():
    r = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]]}).json()["radio"]
    assert r["base_antenna_m"] == 3.0 and len(r["in_contact"]) > 0 and 0 <= r["share_in_contact"] <= 1
    tall = c.post("/api/plan", json={"base": BASE, "stops": [[77.405, 18.47]], "base_antenna_m": 60}).json()["radio"]
    short = c.post("/api/plan", json={"base": BASE, "stops": [[77.405, 18.47]], "base_antenna_m": 1}).json()["radio"]
    assert tall["share_in_contact"] >= short["share_in_contact"]
    img = c.get(f"/api/layers/radio.png?lon={BASE[0]}&lat={BASE[1]}")
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
