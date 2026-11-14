from fastapi.testclient import TestClient

from api.main import app
from pipeline.weather import along, season_of, summary

c = TestClient(app)


def test_seasons():
    assert [season_of(x) for x in (0, 89.9, 90, 180, 270, 359.9, 360)] == [0, 0, 1, 2, 3, 3, 0]


def test_night_is_colder_than_afternoon_every_season():
    for ls in (45, 135, 225, 315):
        a = along(ls, [5.0, 14.0])
        assert a["air"][0] < a["air"][1] and a["ground"][0] < a["ground"][1]


def test_no_sensor_glare_spike_at_4pm():
    # the sun-in-view glare made 15:00-16:00 look ~30 C too warm; real afternoon drift is a couple of degrees
    for ls in (45, 135, 225, 315):
        a = along(ls, [14.0, 16.0])
        assert a["air"][1] <= a["air"][0] + 5


def test_midnight_wraps():
    a = along(45, [23.9, 0.1])
    assert abs(a["air"][0] - a["air"][1]) < 3


def test_wind_gap_is_explained_not_faked():
    s = summary(200, [10, 11, 12])
    assert s["wind_ms_max"] is None and "damaged" in s["wind_note"]
    assert summary(45, [10, 11])["wind_note"] is None


def test_weather_endpoint_and_plan():
    j = c.get("/api/weather?ls=45").json()
    assert len(j["air"]["mean"]) == 24 and "spring" in j["season"]
    r = c.post("/api/plan", json={"base": [77.4508, 18.4447], "stops": [[77.46, 18.47]], "ls": 45, "start_ltst_h": 9}).json()
    w = r["weather"]
    assert w and len(w["per_point"]["air"]) == len(r["path"]) and w["air_c_min"] < w["air_c_max"]


def test_sol_to_ls():
    j = c.get("/api/sol_to_ls?sol=0").json()
    assert 4 < j["ls"] < 7
