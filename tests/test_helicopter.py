"""Where the Ingenuity helicopter really flew, as a map layer. Our planner has a scout helicopter;
this is the real one that did that job at Jezero."""
import json
import math
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app, site
from pipeline import helicopter, rover

c = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "helicopter.json"
R = 3396190.0


def meters(a, b):
    (l1, p1), (l2, p2) = [(math.radians(x), math.radians(y)) for x, y in (a, b)]
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def path_m(points):
    return sum(meters(a, b) for a, b in zip(points, points[1:]))


# ---- thinning a path (shared with the rover's whole drive) ----------------------------------

def test_thin_keeps_both_ends_and_drops_points_closer_than_the_spacing():
    d = lambda a, b: abs(a[0] - b[0])
    pts = [[0, 0], [1, 0], [2, 0], [5, 0], [6, 0], [11, 0], [12, 0]]
    assert rover.thin(pts, 4, d) == [[0, 0], [5, 0], [11, 0], [12, 0]]


def test_thin_never_loses_the_last_point():
    d = lambda a, b: abs(a[0] - b[0])
    assert rover.thin([[0, 0], [1, 0], [2, 0]], 10, d) == [[0, 0], [2, 0]]


def test_thin_leaves_short_paths_alone():
    d = lambda a, b: abs(a[0] - b[0])
    assert rover.thin([[0, 0], [9, 0]], 100, d) == [[0, 0], [9, 0]]
    assert rover.thin([[0, 0]], 100, d) == [[0, 0]]
    assert rover.thin([], 100, d) == []


def test_thin_stays_close_to_the_path_and_never_makes_it_longer():
    # a wobbly path with 1 m steps
    pts = [[i * 1.7e-5, math.sin(i / 9) * 6e-5] for i in range(1500)]
    kept = rover.thin(pts, 3, meters)
    assert path_m(kept) <= path_m(pts) and len(kept) < len(pts) / 2
    k = 0
    for p in pts:  # every point that was dropped is closer than the spacing to a point that was kept
        while k + 1 < len(kept) and kept[k + 1] != p and meters(kept[k], p) >= 3:
            k += 1
        assert min(meters(kept[k], p), meters(kept[min(k + 1, len(kept) - 1)], p)) < 3


# ---- the flights ------------------------------------------------------------------------------

def test_all_72_flights_are_there_in_order():
    h = json.loads(ASSET.read_text())
    assert [f["flight"] for f in h["flights"]] == list(range(1, 73))
    assert h["total"]["flights"] == 72 and h["sols"] == [58, 1036]
    assert all(len(f["points"]) >= 2 for f in h["flights"])
    assert ASSET.stat().st_size < 400_000


def test_totals_are_nasas_own_numbers():
    h = json.loads(ASSET.read_text())
    # NASA's last waypoint record: 18.139 km and 128.92 minutes in the air after flight 72
    assert h["total"]["km"] == 18.139 and h["total"]["minutes"] == 128.92
    assert abs(sum(f["length_m"] for f in h["flights"]) - 18138.8) < 1.0


def test_our_thinned_lines_are_never_longer_than_nasas_and_reach_as_far():
    """NASA measures a flight along a very fine line, wobbles included, so its length is the upper
    limit for our thinned line. The straight distance from takeoff to landing is the lower limit."""
    h = json.loads(ASSET.read_text())
    for f in h["flights"]:
        ours = path_m(f["points"])
        assert ours <= f["length_m"] + 0.5, f["flight"]
        assert ours >= meters(f["points"][0], f["points"][-1]) - 0.01, f["flight"]


def test_flight_numbers_follow_nasas_record_of_facts_where_its_two_files_disagree():
    """In NASA's line file the lines numbered 12 and 13 are swapped. Paired by length, flight 12 is the
    long one (NASA's record: 469.3 m on sol 174) and flight 13 the shorter (226.9 m on sol 193)."""
    h = {f["flight"]: f for f in json.loads(ASSET.read_text())["flights"]}
    assert (h[12]["length_m"], h[12]["sol"]) == (469.3, 174)
    assert (h[13]["length_m"], h[13]["sol"]) == (226.9, 193)


def test_match_pairs_by_length_and_refuses_a_line_with_no_record():
    paths = [{"properties": {"Flight": 1, "Length_m": 5.0}}, {"properties": {"Flight": 2, "Length_m": 7.25}}]
    ways = [{"Flight": 2, "Dist_m": 5.0}, {"Flight": 1, "Dist_m": 7.25}]
    assert [(p["properties"]["Flight"], w["Flight"]) for p, w in helicopter.match(paths, ways)] == [(1, 2), (2, 1)]
    import pytest
    with pytest.raises(ValueError):
        helicopter.match(paths, ways[:1])


def test_first_flight_took_off_next_to_where_the_rover_landed():
    h = json.loads(ASSET.read_text())
    f1 = h["flights"][0]
    assert f1["sol"] == 58 and f1["from"] == "Wright Brothers Field" and f1["to"] == "Wright Brothers Field"
    landing = json.loads((ROOT / "assets" / "rover_track.json").read_text())["landing"]["lonlat"]
    assert meters(f1["points"][0], landing) < 100


def test_each_flight_starts_where_the_one_before_ended():
    h = json.loads(ASSET.read_text())
    for a, b in zip(h["flights"], h["flights"][1:]):
        assert meters(a["points"][-1], b["points"][0]) < 15, (a["flight"], b["flight"])


def test_flight_facts_are_sane():
    h = json.loads(ASSET.read_text())
    for f in h["flights"]:
        assert 0 < f["max_alt_m"] <= 30 and 0 < f["duration_s"] < 300 and f["length_m"] >= 0
        assert f["date"] and f["from"] and f["to"]
    assert max(f["max_alt_m"] for f in h["flights"]) == 24.0  # the highest flight in NASA's file (flight 61)


def test_inside_box_count_matches_the_points():
    s = site(None, "jezero")
    h = c.get("/api/helicopter").json()
    Rn, Cn = s.zone.shape

    def inside(p):
        r, col = s.lonlat_to_cell(p[0], p[1])
        return 0 <= r < Rn and 0 <= col < Cn
    n = sum(all(inside(p) for p in f["points"]) for f in h["flights"])
    assert h["inside_planning_box"] == n and 0 < n < 72
    assert [f["flight"] for f in h["flights"] if f["inside_box"]] == [f["flight"] for f in h["flights"] if all(inside(p) for p in f["points"])]


# ---- the API ---------------------------------------------------------------------------------------

def test_api_gives_the_flights_with_source_and_note():
    r = c.get("/api/helicopter")
    assert r.status_code == 200
    j = r.json()
    assert len(j["flights"]) == 72 and "NASA/JPL-Caltech" in j["source"] and j["note"]
    assert set(j["flights"][0]) >= {"flight", "sol", "date", "length_m", "max_alt_m", "duration_s", "from", "to", "points", "inside_box"}


def test_site_info_says_which_site_has_helicopter_flights():
    assert c.get("/api/site").json()["has_helicopter_flights"] is True
    assert c.get("/api/site?site=moon").json()["has_helicopter_flights"] is False


def test_a_site_without_flights_says_so():
    r = c.get("/api/helicopter?site=moon")
    assert r.status_code == 404 and r.json()["detail"] == "No helicopter flights for this site."
    assert c.get("/api/helicopter?site=nowhere").status_code == 404


def test_helicopter_module_reads_nasas_fields():
    way = {"Flight": 3, "Sol": 64, "Earth_Date": "April 25, 2021", "Max_Alt_m": 5.0, "Duration_s": 80.3,
           "FromAirfld": "Wright Brothers Field", "ToAirfld": "Wright Brothers Field"}
    path = {"properties": {"Flight": 3, "Sol": 64, "Length_m": 100.0},
            "geometry": {"coordinates": [[77.451, 18.4448], [77.4511, 18.4449], [77.4512, 18.4455]]}}
    f = helicopter.flight(path, way, spacing_m=1)
    assert f == {"flight": 3, "sol": 64, "date": "April 25, 2021", "length_m": 100.0, "max_alt_m": 5.0,
                 "duration_s": 80.3, "from": "Wright Brothers Field", "to": "Wright Brothers Field",
                 "points": [[77.451, 18.4448], [77.4511, 18.4449], [77.4512, 18.4455]]}
