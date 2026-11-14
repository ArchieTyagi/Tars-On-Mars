import math

import numpy as np

from pipeline.layers import block_max, slope_deg


def test_ramp_is_5_71_degrees():
    # ground that rises 1 m for every 10 m walked
    x = np.arange(100) * 1.0
    dem = np.tile(x * 0.1, (100, 1))
    s = slope_deg(dem, 1.0)
    assert abs(s[50, 50] - math.degrees(math.atan(0.1))) < 1e-3
    assert abs(s[50, 50] - 5.71) < 0.01


def test_flat_is_zero():
    assert np.allclose(slope_deg(np.full((20, 20), 7.0), 1.0), 0)


def test_cell_size_matters():
    # same heights on a 2 m grid = half as steep
    dem = np.tile(np.arange(50) * 0.1, (50, 1))
    assert abs(slope_deg(dem, 2.0)[25, 25] - math.degrees(math.atan(0.05))) < 1e-3


def test_block_max_keeps_the_worst():
    a = np.zeros((8, 8), dtype="float32")
    a[1, 2] = 35.0  # one steep spot
    assert block_max(a, 4)[0, 0] == 35.0


def test_gap_poisons_block():
    a = np.zeros((8, 8), dtype="float32")
    a[5, 5] = np.nan
    assert np.isnan(block_max(a, 4)[1, 1])
