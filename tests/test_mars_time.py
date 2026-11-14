from datetime import datetime, timezone

import pytest

from pipeline.mars_time import ls_from_m20_sol, ls_from_utc


def utc(y, m, d, h=12):
    return datetime(y, m, d, h, tzinfo=timezone.utc)


# Mars Year 36 season starts and mission events, from The Planetary Society's Mars calendar
@pytest.mark.parametrize("when, ls", [
    (utc(2021, 2, 7), 0), (utc(2021, 8, 25), 90), (utc(2022, 2, 24), 180), (utc(2022, 7, 21), 270),
    (utc(2021, 2, 18, 20), 5),    # Perseverance lands
    (utc(2021, 4, 19), 33),       # Ingenuity first flight
    (utc(2021, 5, 14), 45),       # Zhurong lands
])
def test_known_dates(when, ls):
    got = ls_from_utc(when)
    diff = min(abs(got - ls), 360 - abs(got - ls))
    assert diff < 1.0, (when, got, ls)


def test_season_moves_forward_with_sols():
    a, b, c = ls_from_m20_sol(0), ls_from_m20_sol(120), ls_from_m20_sol(300)
    assert a < b < c
