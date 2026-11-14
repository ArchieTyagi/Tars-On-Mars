import numpy as np

from planner.route import Site
from planner.scout import apply_observations, flight_plan

from tests.test_route import flat_site, ll


def test_blocked_report_reroutes_around_it():
    s = flat_site(n=80)
    s.rules["scout_range_m"] = 700.0
    base, stop = ll(s, 40, 5), ll(s, 40, 75)
    r1 = s.plan(base, [stop])
    mid = ll(s, 40, 40)  # straight line goes right through here
    s2 = apply_observations(s, [{"lonlat": mid, "finding": "blocked", "radius_m": 20}])
    r2 = s2.plan(base, [stop])
    cells = [s.lonlat_to_cell(*p) for p in r2["path"]]
    assert all(s2.zone[c] != 2 for c in cells)  # new route never enters the blocked spot
    assert r2["path"] != r1["path"] and r2["km"] > r1["km"]
    assert s.zone[s.lonlat_to_cell(*mid)] == 0  # original map untouched


def test_safe_report_never_overrides_a_too_steep_slope():
    s = flat_site(n=40, slope=30.0)  # everything over the 20 deg limit
    s2 = apply_observations(s, [{"lonlat": ll(s, 20, 20), "finding": "safe", "radius_m": 20}])
    assert (s2.zone == 2).all()


def test_flight_plan_splits_long_hops():
    s = flat_site(n=600)
    fp = flight_plan(s, ll(s, 300, 10), [{"lonlat": list(ll(s, 300, 400))}], range_m=700)
    # base -> target is 390 cells * 4 m = 1560 m -> 3 hops each way
    assert fp["flights"] == 6 and all(h["m"] <= 700 for h in fp["hops"])
