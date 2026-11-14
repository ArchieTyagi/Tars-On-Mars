"""Science stops the planner suggests: mineral spots worth visiting that you can actually reach."""
import math

import numpy as np
from fastapi.testclient import TestClient

from api.main import app
from planner import science
from tests.test_route import flat_site, ll

c = TestClient(app)
BASE = [77.4508, 18.4447]
OLIVINE, CARBONATE, SMECTITE = 1, 2, 3   # codes in pipeline/minerals.py (high confidence)


def mineral_site():
    s = flat_site(n=120)                       # 480 m x 480 m, 4 m cells, all walkable
    m = np.full((120, 120), 255, "uint8")      # 255 = looked at, nothing identified
    m[54:67, 20:33] = OLIVINE                  # near the base, 52 m x 52 m (bigger than 2 mineral-map pixels)
    m[54:67, 95:108] = CARBONATE               # far from the base
    m[10, 10] = SMECTITE                       # one lonely cell: too small to trust
    m[100:113, 55:68] = 100 + CARBONATE        # medium confidence: not suggested
    s.minerals = m
    return s


def test_water_minerals_come_first_then_the_rest():
    s = mineral_site()
    got = science.suggest(s, ll(s, 60, 5))
    assert [g["mineral"] for g in got] == ["Mg-carbonate", "Olivine"]   # carbonate formed in water: first
    assert all(g["confidence"] == "high" for g in got)
    for g in got:
        r, col = s.lonlat_to_cell(*g["lonlat"])
        assert s.minerals[r, col] in (OLIVINE, CARBONATE) and s.zone[r, col] != 2


def test_the_spot_is_the_edge_of_the_patch_nearest_your_walk():
    s = mineral_site()
    g = [x for x in science.suggest(s, ll(s, 60, 5)) if x["mineral"] == "Olivine"][0]
    r, col = s.lonlat_to_cell(*g["lonlat"])
    assert col == 20   # the patch starts at column 20, the base is to the west


def test_nothing_suggested_inside_no_go_ground():
    s = mineral_site()
    s.slope[50:70, 15:36] = 40.0   # the olivine patch is now inside a cliff area
    s.set_limit(None)
    assert [g["mineral"] for g in science.suggest(s, ll(s, 60, 5))] == ["Mg-carbonate"]


def test_too_little_oxygen_means_fewer_suggestions():
    s = mineral_site().with_settings(o2_hours=0.2, o2_reserve=0.0, stop_minutes=0)  # 0.2 h: 200 m out and back at most
    assert [g["mineral"] for g in science.suggest(s, ll(s, 60, 5))] == ["Olivine"]
    s = mineral_site().with_settings(o2_hours=0.01, o2_reserve=0.0, stop_minutes=0)
    assert science.suggest(s, ll(s, 60, 5)) == []


def test_two_patches_close_together_give_one_suggestion():
    s = mineral_site()
    s.minerals[70:83, 20:33] = OLIVINE   # a second olivine patch 12 m south of the first
    got = science.suggest(s, ll(s, 60, 5), min_sep_m=250)
    assert [g["mineral"] for g in got].count("Olivine") == 1


def meters(a, b, R=3396190.0):
    (l1, p1), (l2, p2) = [(math.radians(x), math.radians(y)) for x, y in (a, b)]
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def test_real_map_suggestions_are_real_reachable_and_spread_out():
    r = c.get(f"/api/science_stops?lon={BASE[0]}&lat={BASE[1]}&n=6")
    assert r.status_code == 200
    j = r.json()
    stops = j["stops"]
    assert 1 <= len(stops) <= 6 and "closest match" in j["caveat"]
    for s_ in stops:
        pt = c.get(f"/api/point?lon={s_['lonlat'][0]}&lat={s_['lonlat'][1]}").json()
        assert pt["mineral"] == s_["mineral"] and pt["mineral_confidence"] == "high" and pt["zone"] != "NO-GO"
        assert s_["why"] and s_["round_trip_h"] > 0 and s_["patch_m2"] >= 2 * 36 * 36
        # the planner agrees you can go there and back on your oxygen
        p = c.post("/api/plan", json={"base": BASE, "stops": [s_["lonlat"]]}).json()
        assert p["o2_ok"] and abs(p["walk_hours"] - s_["round_trip_h"]) < 0.05
    for i, a in enumerate(stops):
        for b in stops[:i]:
            assert meters(a["lonlat"], b["lonlat"]) >= 250
    names = [s_["mineral"] for s_ in stops]
    k = len(set(names))
    assert len(set(names[:k])) == k   # one of each kind before any kind repeats
    assert c.get(f"/api/science_stops?lon={BASE[0]}&lat={BASE[1]}&n=6").json() == j   # same answer every time


def test_suggestions_respect_your_oxygen():
    a = c.get(f"/api/science_stops?lon={BASE[0]}&lat={BASE[1]}&n=10").json()["stops"]
    b = c.get(f"/api/science_stops?lon={BASE[0]}&lat={BASE[1]}&n=10&o2_hours=1").json()["stops"]
    assert all(s_["round_trip_h"] + 0.25 <= 0.75 + 1e-6 for s_ in b)   # 1 h supply, 25% reserve, 15 min at the stop
    assert len(b) <= len(a)


def test_science_stops_refuses_what_it_cannot_do():
    assert c.get(f"/api/science_stops?lon={BASE[0]}&lat={BASE[1]}&n=0").status_code == 422
    assert c.get(f"/api/science_stops?lon={BASE[0]}&lat={BASE[1]}&n=50").status_code == 422
    assert c.get("/api/science_stops?lon=0&lat=0").status_code == 422
    m = c.get("/api/site?site=moon").json()["default_base"]
    r = c.get(f"/api/science_stops?lon={m[0]}&lat={m[1]}&site=moon")
    assert r.status_code == 404 and "mineral" in r.json()["detail"].lower()
