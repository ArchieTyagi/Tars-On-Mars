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
    assert r.status_code == 422 and "outside the map" in r.json()["detail"]


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
    assert abs(slow["walk_hours"] - 2 * a["walk_hours"]) < 0.05  # half the speed, double the walking time
    assert slow["stop_hours"] == a["stop_hours"]  # time at the stops does not change
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
    body = {"base": BASE, "stops": [[77.46, 18.47]]}
    a = c.post("/api/plan", json=body).json()
    mid = a["path"][len(a["path"]) // 4]
    seen = [{"lonlat": mid, "finding": "blocked", "radius_m": 30}]
    b = c.post("/api/plan", json={**body, "observations": seen}).json()
    assert b["path"] != a["path"] and len(b["observations"]) == 1
    bad = c.post("/api/plan", json={**body, "observations": [{"lonlat": mid, "finding": "maybe"}]})
    assert bad.status_code == 422
    # reports belong to one request only: the next plain plan is unchanged
    assert c.post("/api/plan", json=body).json()["path"] == a["path"]


def test_bad_inputs_get_clear_422_not_crash():
    nan = '{"base":[NaN,18.4],"stops":[[77.46,18.47]]}'
    bodies = [{"base": BASE, "stops": [[77.46]]}, {"base": BASE, "stops": [[77.46, 18.47, 5]]},
              {"base": [1e308, 1e308], "stops": [[77.46, 18.47]]},
              {"base": BASE, "stops": [[77.46, 18.47]], "observations": [{"lonlat": [0, 0], "finding": "safe"}]}]
    for b in bodies:
        r = c.post("/api/plan", json=b)
        assert r.status_code == 422 and "integer" not in r.json()["detail"], (b, r.text)
    r = c.post("/api/plan", content=nan, headers={"content-type": "application/json"})
    assert r.status_code == 422 and "real number" in r.json()["detail"]
    for u in ["/api/point?lon=nan&lat=1", "/api/convert?lon=inf&lat=1", "/api/sun?ls=400&ltst_h=12",
              "/api/sol_to_ls?sol=inf", "/api/terrain?step=0", "/api/layers/zones.png?slope_limit=1000",
              "/api/layers/safe_range.png?lon=0&lat=0", "/api/layers/radio.png?lon=77.45&lat=18.44&base_antenna_m=-1"]:
        assert c.get(u).status_code == 422, u
    assert c.get("/api/point?lon=0&lat=0").json() == {"inside": False}


def test_safe_range_uses_mission_settings():
    u = f"/api/layers/safe_range.png?lon={BASE[0]}&lat={BASE[1]}"
    assert c.get(u + "&o2_hours=0.2").content != c.get(u + "&o2_hours=12").content


def test_radio_in_plan_and_layer():
    r = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]]}).json()["radio"]
    assert r["base_antenna_m"] == 3.0 and len(r["in_contact"]) > 0 and 0 <= r["share_in_contact"] <= 1
    tall = c.post("/api/plan", json={"base": BASE, "stops": [[77.405, 18.47]], "base_antenna_m": 60}).json()["radio"]
    short = c.post("/api/plan", json={"base": BASE, "stops": [[77.405, 18.47]], "base_antenna_m": 1}).json()["radio"]
    assert tall["share_in_contact"] >= short["share_in_contact"]
    img = c.get(f"/api/layers/radio.png?lon={BASE[0]}&lat={BASE[1]}")
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"


def test_errors_are_plain_sentences():
    r = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]] * 7})
    assert r.status_code == 422 and r.json()["detail"].startswith("Too many stops")
    r = c.post("/api/plan", json={"base": ["x", 18.4], "stops": [[77.46, 18.47]]})
    assert "must be a number" in r.json()["detail"]
    r = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]], "o2_reserve": 1.0})
    assert "oxygen reserve" in r.json()["detail"]


def test_sun_check_needs_both_inputs():
    r = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]], "ls": 10})
    assert r.status_code == 422 and "both" in r.json()["detail"]


def test_slider_copies_share_the_big_arrays():
    from api.main import site
    a, b = site(None), site(12.0)
    assert a.slope is b.slope and a.zone is not b.zone


def test_convert_round_trip():
    xy = c.get(f"/api/convert?lon={BASE[0]}&lat={BASE[1]}").json()
    ll = c.get(f"/api/convert?x={xy['x']}&y={xy['y']}").json()
    assert abs(ll["lon"] - BASE[0]) < 1e-9 and abs(ll["lat"] - BASE[1]) < 1e-9


def test_time_at_stops_counts_against_oxygen():
    body = {"base": BASE, "stops": [[77.46, 18.47], [77.43, 18.455]]}
    a = c.post("/api/plan", json={**body, "stop_minutes": 0}).json()
    b = c.post("/api/plan", json={**body, "stop_minutes": 60}).json()
    assert abs(b["hours"] - (b["walk_hours"] + 2.0)) < 0.02 and b["stop_hours"] == 2.0
    assert abs(b["o2_margin_h"] - (a["o2_margin_h"] - 2.0)) < 0.02
    assert abs(b["elapsed_h"][-1] - a["elapsed_h"][-1] - 2.0) < 0.01
    first = b["stop_arrivals"][0]
    assert abs(first["leave_h"] - first["arrive_h"] - 1.0) < 0.01


def test_night_start_is_not_called_sunset():
    j = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]], "ls": 0, "start_ltst_h": 2}).json()
    assert j["light"]["starts_in_dark"] and not j["light"]["sunset_before_home"]
    k = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]], "ls": 0, "start_ltst_h": 16.5}).json()
    assert k["light"]["sunset_before_home"] and not k["light"]["starts_in_dark"]
