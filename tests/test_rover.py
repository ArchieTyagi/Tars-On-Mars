"""Where Perseverance really drove, as a map layer. The rover drove it safely, so it is ground truth."""
import json
import math
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from api.main import app, site
from pipeline import rover

c = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets" / "rover_track.json"
R = 3396190.0


def meters(a, b):
    (l1, p1), (l2, p2) = [(math.radians(x), math.radians(y)) for x, y in (a, b)]
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def test_clip_keeps_inside_points_and_splits_where_the_line_leaves():
    inside = lambda p: 0 <= p[0] <= 10
    pts = [[1, 0], [2, 0], [11, 0], [12, 0], [9, 0], [8, 0]]
    assert rover.clip(pts, inside) == [[[1, 0], [2, 0]], [[9, 0], [8, 0]]]
    assert rover.clip([[11, 0], [5, 0], [12, 0]], inside) == []  # one lonely point is not a line


def test_track_file_is_small_and_ordered():
    t = json.loads(ASSET.read_text())
    assert ASSET.stat().st_size < 600_000
    sols = [s["sol"] for s in t["segments"]]
    assert sols == sorted(sols) and all(len(s["points"]) >= 2 for s in t["segments"])


def test_every_track_point_is_on_our_map_and_on_real_ground():
    s = site(None, "jezero")
    t = c.get("/api/rover").json()
    for seg in t["segments"]:
        for lon, lat in seg["points"]:
            r, col = s.lonlat_to_cell(lon, lat)
            assert 0 <= r < s.zone.shape[0] and 0 <= col < s.zone.shape[1]
            assert np.isfinite(s.height[r, col])


def test_track_length_is_what_the_points_add_up_to():
    t = c.get("/api/rover").json()
    km = sum(meters(a, b) for seg in t["segments"] for a, b in zip(seg["points"], seg["points"][1:])) / 1000
    assert abs(km - t["km_on_map"]) < 0.01 * km and km > 5  # the rover drove many km inside our box


def test_track_starts_at_the_landing_site():
    t = c.get("/api/rover").json()
    # NASA: Perseverance landed at 18.4446 N, 77.4509 E (Octavia E. Butler Landing)
    assert meters(t["landing"]["lonlat"], (77.4509, 18.4446)) < 30
    assert t["sols"][0] == 14  # first drive inside our box
    assert meters(t["segments"][0]["points"][0], t["landing"]["lonlat"]) < 30  # the first drive starts there


def test_layer_and_validation_use_the_same_track():
    """Every map square validation/rover_check.py saw the rover on must also be on the layer's track."""
    from validation.rover_check import drive_points
    s = site(None, "jezero")
    seen_by_check = {tuple(x) for x in drive_points(s)[0]}
    on_layer = rover.squares(s, rover.load())
    assert len(seen_by_check - on_layer) <= 0.005 * len(seen_by_check)
    assert len(on_layer) >= len(seen_by_check)  # the layer counts squares the line only clips, the check can miss them


def test_our_map_agrees_with_where_the_rover_drove():
    z = c.get("/api/rover").json()["our_map_on_the_track"]
    assert abs(z["go"] + z["caution"] + z["nogo"] - 1) < 1e-6
    assert z["nogo"] < 0.02 and z["go"] > 0.94  # README: 95.2% GO, 1.3% NO-GO with ground-type limits


def test_stops_carry_the_rovers_own_tilt():
    t = c.get("/api/rover").json()
    check = json.loads((ROOT / "docs" / "rover_check.json").read_text())
    assert len(t["stops"]) == check["rover_stops_on_map"]
    tilts = [s["tilt_deg"] for s in t["stops"]]
    assert abs(float(np.median(tilts)) - check["tilt_vs_slope"]["rover_tilt_median"]) < 0.01


def test_no_rover_on_the_moon():
    r = c.get("/api/rover?site=moon")
    assert r.status_code == 404 and "rover" in r.json()["detail"].lower()
    assert c.get("/api/site").json()["has_rover_track"] is True
    assert c.get("/api/site?site=moon").json()["has_rover_track"] is False


def test_squares_counts_every_square_a_line_touches():
    class Flat:  # 10 x 10 grid of 1 m squares, x right, y down, plain coordinates
        zone = np.zeros((10, 10))
        x0, y0, a, e = 0.0, 0.0, 1.0, 1.0

        class _to_xy:
            transform = staticmethod(lambda lon, lat: (np.asarray(lon, float), np.asarray(lat, float)))
    # a diagonal from the middle of square (0,0) to the middle of (3,3) touches exactly the 4 diagonal squares
    assert rover.squares(Flat, {"segments": [{"points": [[0.5, 0.5], [3.5, 3.5]]}]}) == {(0, 0), (1, 1), (2, 2), (3, 3)}
    # a shallow line clips the corner of (0,1): sampling every 2 m would miss it
    got = rover.squares(Flat, {"segments": [{"points": [[0.5, 0.9], [3.5, 1.2]]}]})
    assert got == {(0, 0), (0, 1), (1, 1), (1, 2), (1, 3)}


def test_landing_is_not_given_a_wrong_day():
    landing = c.get("/api/rover").json()["landing"]
    assert "sol" not in landing and "first drive" in landing["note"]   # the file's first record is sol 13, landing was sol 0


# ---- the whole drive, also outside our box (shown on the darkened ground around it) ---------------

WHOLE = ROOT / "assets" / "rover_whole.json"


def test_whole_drive_starts_at_the_landing_site_and_is_in_order():
    w = json.loads(WHOLE.read_text())
    t = json.loads(ASSET.read_text())
    sols = [s["sol"] for s in w["segments"]]
    assert sols == sorted(sols) and sols[0] == 14 and w["sols"] == [sols[0], sols[-1]]
    assert meters(w["segments"][0]["points"][0], t["landing"]["lonlat"]) < 30
    assert all(len(s["points"]) >= 2 for s in w["segments"]) and WHOLE.stat().st_size < 400_000


def test_whole_drive_length_is_nasas_odometer_and_the_path_agrees():
    w = json.loads(WHOLE.read_text())
    km_path = sum(meters(a, b) for s in w["segments"] for a, b in zip(s["points"], s["points"][1:])) / 1000
    assert w["km"] > 40  # NASA's own total at the last stop in the file
    assert abs(km_path - w["km"]) < 0.04 * w["km"]  # our thinned line is within 4% of the odometer


def test_whole_drive_goes_far_beyond_the_box_and_the_inside_part_matches_the_track():
    s = site(None, "jezero")
    w = json.loads(WHOLE.read_text())
    inside = rover._inside(s)
    pts = [p for seg in w["segments"] for p in seg["points"]]
    assert sum(not inside(p) for p in pts) > 0.3 * len(pts)
    km_in = sum(meters(a, b) for seg in w["segments"] for a, b in zip(seg["points"], seg["points"][1:])
                if inside(a) and inside(b)) / 1000
    assert abs(km_in - c.get("/api/rover").json()["km_on_map"]) < 0.04 * km_in


def test_last_position_is_the_end_of_the_last_drive():
    w = json.loads(WHOLE.read_text())
    assert w["last"]["sol"] == w["sols"][1]
    assert meters(w["last"]["lonlat"], w["segments"][-1]["points"][-1]) < 30


def test_api_carries_the_whole_drive():
    j = c.get("/api/rover").json()
    assert j["whole"]["km"] > j["km_on_map"] and j["whole"]["segments"] and j["whole"]["note"]
