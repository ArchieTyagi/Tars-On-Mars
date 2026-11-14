import math

import numpy as np

from pipeline.sun import cast_shadow, sun_declination_deg, sun_position


def test_declination_limits():
    # northern summer solstice (Ls 90) = sun at +obliquity, winter (Ls 270) at minus
    assert abs(sun_declination_deg(90) - 25.44) < 0.01
    assert abs(sun_declination_deg(270) + 25.44) < 0.01
    assert abs(sun_declination_deg(0)) < 1e-9


def test_noon_at_equinox():
    # at the equinox, noon sun height = 90 - latitude, and it's due south for a northern site
    el, az = sun_position(18.4, 0, 12)
    assert abs(el - (90 - 18.4)) < 1e-6
    assert abs(az - 180) < 1e-6


def test_morning_sun_is_east_evening_west():
    _, az_am = sun_position(18.4, 0, 8)
    _, az_pm = sun_position(18.4, 0, 16)
    assert 45 < az_am < 135 and 225 < az_pm < 315


def test_sunrise_near_6am_at_equinox():
    assert abs(sun_position(0, 0, 6)[0]) < 1e-6


def test_wall_casts_shadow_on_the_far_side():
    h = np.zeros((40, 40))
    h[:, 20] = 10.0  # 10 m wall running north-south
    # sun low in the east (az 90, 30 deg): ground just west of the wall is dark
    s = cast_shadow(h, 1.0, 1.0, 30, 90)
    shadow_len = 10 / math.tan(math.radians(30))  # 17.3 m
    assert s[20, 19] and s[20, 20 - int(shadow_len) + 1]
    assert not s[20, 20 - int(shadow_len) - 2]
    assert not s[20, 25]  # sunny side


def test_dark_at_matches_full_map_shadow():
    from pipeline.sun import dark_at
    h = np.zeros((40, 40)); h[:, 20] = 10.0
    rows, cols = np.array([20, 20, 20]), np.array([15, 25, 30])
    d = dark_at(h, 1.0, 1.0, rows, cols, np.full(3, 30.0), np.full(3, 90.0))
    assert d[0] and not d[1] and not d[2]
    # night is always dark
    assert dark_at(h, 1.0, 1.0, rows, cols, np.full(3, -5.0), np.full(3, 90.0)).all()


def test_slope_facing_away_from_low_sun_is_dark():
    from pipeline.sun import dark_at
    x = np.arange(60) * 1.0
    h = np.tile(-x * np.tan(np.radians(20)), (60, 1))  # ground drops toward the east at 20 deg = faces east
    # low sun in the east lights it; low sun (10 deg) in the west can't reach a 20 deg slope facing away
    assert dark_at(h, 1.0, 1.0, np.array([30]), np.array([30]), np.array([10.0]), np.array([90.0]))[0] == False
    assert dark_at(h, 1.0, 1.0, np.array([30]), np.array([30]), np.array([10.0]), np.array([270.0]))[0] == True
