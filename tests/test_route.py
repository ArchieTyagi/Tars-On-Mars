import numpy as np
import pytest

from planner.route import Site


def flat_site(n=60, slope=2.0, wall_col=None):
    s = Site.__new__(Site)
    s.slope = np.full((n, n), slope, "float32")
    if wall_col is not None:
        s.slope[5:, wall_col] = 40.0  # cliff with a gap at the top
    s.rough = s.height = np.zeros((n, n), "float32")
    s.a, s.b, s.x0, s.d, s.e, s.y0 = 4.0, 0, 0.0, 0, -4.0, 0.0
    s.dx = s.dy = 4.0
    s.ground = None
    s.radius = 3396190.0
    s.rules = {"slope_limit_deg": {"default": 20}, "caution_from": 0.75, "caution_cost": 8,
               "walk_speed_kmh": 2.0, "slope_slowdown_per_deg": 0.03, "o2_hours": 8, "o2_reserve": 0.25}
    s.set_limit(None)
    return s


def ll(s, r, c):
    return s.cell_to_lonlat(r, c)


def test_route_goes_around_cliff():
    s = flat_site(wall_col=30)
    r = s.plan(ll(s, 50, 10), [ll(s, 50, 50)])
    cells = [s.lonlat_to_cell(*p) for p in r["path"]]
    assert all(s.zone[c] != 2 for c in cells)          # never steps on no-go
    assert min(c[0] for c in cells) < 5                  # had to use the gap at the top
    assert r["max_slope"] < 20


def test_stop_on_cliff_is_rejected():
    s = flat_site(wall_col=30)
    with pytest.raises(ValueError):
        s.plan(ll(s, 50, 10), [ll(s, 40, 30)])


def test_slider_blocks_more():
    s = flat_site(slope=12.0)
    s.set_limit(10)
    assert (s.zone == 2).all()


def test_point_of_no_return():
    s = flat_site(n=600)
    s.rules["o2_hours"] = 1.0  # 0.75 h usable = ~1.4 km out and back
    r = s.plan(ll(s, 300, 10), [ll(s, 300, 590)])  # 2.3 km out, too far
    assert not r["o2_ok"]
    assert r["point_of_no_return"] is not None
    assert 0.3 < r["point_of_no_return"]["elapsed_h"] < 0.45


def test_short_walk_has_no_ponr():
    s = flat_site()
    r = s.plan(ll(s, 30, 10), [ll(s, 30, 40)])
    assert r["o2_ok"] and r["point_of_no_return"] is None


def test_sand_is_stricter_than_rock():
    from pipeline.costmap import classify
    rules = {"slope_limit_deg": {"default": 20, "bedrock": 20, "regolith": 15, "sand": 10}, "caution_from": 0.75}
    slope = np.full((2, 2), 12.0, "float32")
    ground = np.array([[1, 3], [2, 0]], "uint8")  # bedrock, sand / regolith, default
    zone, lim = classify(slope, rules, ground)
    assert zone[0, 0] == 0 and zone[0, 1] == 2 and zone[1, 0] == 1  # rock GO, sand NO-GO, regolith CAUTION
    zone2, _ = classify(slope, rules, ground, limit_override=20)  # slider ignores ground
    assert (zone2 == 0).all()
