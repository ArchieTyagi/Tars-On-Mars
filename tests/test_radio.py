import numpy as np

from planner.radio import line_clear, route_contact


def test_flat_ground_short_range_is_clear():
    h = np.zeros((100, 100))
    assert line_clear(h, 1.0, 1.0, (50, 5), np.array([[50, 95]]), 3, 2).all()


def test_ridge_blocks():
    h = np.zeros((100, 100))
    h[:, 50] = 10.0
    assert not line_clear(h, 1.0, 1.0, (50, 5), np.array([[50, 95]]), 3, 2).any()
    # a taller mast at base sees over it from close enough
    assert line_clear(h, 1.0, 1.0, (50, 45), np.array([[50, 55]]), 30, 2).all()


def test_mars_curve_blocks_far_flat_ground():
    # flat ground, 3 m + 2 m antennas: radio horizon on Mars is about 8.2 km
    h = np.zeros((10, 2000))
    near = line_clear(h, 4.0, 4.0, (5, 0), np.array([[5, 1500]]), 3, 2)   # 6 km
    far = line_clear(h, 5.0, 5.0, (5, 0), np.array([[5, 1999]]), 3, 2)    # 10 km
    assert near.all() and not far.any()


def test_blackout_stretches():
    class S:  # tiny fake site
        dx = dy = 1.0
        height = np.zeros((20, 40)); height[:, 20] = 10
        def cell_to_lonlat(self, r, c): return (float(c), float(r))
    cells = [(10, c) for c in range(2, 38)]
    out = route_contact(S(), (10, 2), cells, np.arange(len(cells)) / 10, 3, 2)
    assert out["blackouts"] and out["blackouts"][0]["from"] > 0 and out["share_in_contact"] < 1
