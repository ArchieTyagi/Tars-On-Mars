"""Where the sun is on Mars, and which ground is in shadow.

Sun position: standard Mars formulas (Allison & McEwen 2000, the ones behind
NASA GISS Mars24). Inputs are the season (Ls, degrees, 0 = northern spring)
and local true solar time (LTST, Mars hours 0-24, 12 = local noon).

Shadows: for every cell we walk toward the sun and check whether any terrain
rises above the sun's line. Cast shadow = terrain blocks the sun.
"""
import math

import numpy as np

MARS_OBLIQUITY_DEG = 25.19


def sun_declination_deg(ls_deg):
    """Allison & McEwen 2000, eq. 7: arcsin(0.42565 sin Ls) + 0.25 deg sin Ls."""
    ls = math.radians(ls_deg)
    return math.degrees(math.asin(0.42565 * math.sin(ls))) + 0.25 * math.sin(ls)


def sun_position(lat_deg, ls_deg, ltst_h):
    """Sun elevation and azimuth (degrees, azimuth clockwise from north) at a place."""
    lat = math.radians(lat_deg)
    dec = math.radians(sun_declination_deg(ls_deg))
    hour_angle = math.radians((ltst_h - 12.0) * 15.0)
    sin_el = math.sin(lat) * math.sin(dec) + math.cos(lat) * math.cos(dec) * math.cos(hour_angle)
    el = math.asin(max(-1.0, min(1.0, sin_el)))
    az = math.atan2(math.sin(hour_angle),
                    math.cos(hour_angle) * math.sin(lat) - math.tan(dec) * math.cos(lat))
    az = (math.degrees(az) + 180.0) % 360.0  # 0 = north, 90 = east
    return math.degrees(el), az


def cast_shadow(height, dx, dy, sun_el_deg, sun_az_deg, max_dist_m=3000.0):
    """True where terrain blocks the sun. height: 2D grid, row 0 = north.
    dx, dy = real cell size in meters (east-west, north-south)."""
    if sun_el_deg <= 0:
        return np.ones(height.shape, bool)  # night
    h = np.nan_to_num(height, nan=float(np.nanmin(height)))
    az = math.radians(sun_az_deg)
    # one step toward the sun, in cells (east = +col, north = -row)
    step_m = min(dx, dy)
    sc, sr = math.sin(az) * step_m / dx, -math.cos(az) * step_m / dy
    rise = math.tan(math.radians(sun_el_deg)) * step_m
    # beyond this height difference nothing in the map can block the sun
    span = float(h.max() - h.min())
    n = int(min(max_dist_m, span / max(rise / step_m, 1e-6)) / step_m) + 1
    rows, cols = np.indices(h.shape)
    shadow = np.zeros(h.shape, bool)
    for k in range(1, n + 1):
        r = np.rint(rows + sr * k).astype(int)
        c = np.rint(cols + sc * k).astype(int)
        ok = (r >= 0) & (r < h.shape[0]) & (c >= 0) & (c < h.shape[1])
        if not ok.any():
            break
        hit = np.zeros(h.shape, bool)
        hit[ok] = h[r[ok], c[ok]] > h[ok] + rise * k
        shadow |= hit
    return shadow


MARS_HOUR_IN_EARTH_HOURS = 1.0275  # a Mars solar day (sol) is 24 h 39 min 35 s


def sun_positions(lat_deg, ls_deg, ltst_h):
    """Vector version of sun_position: ltst_h can be an array. Returns (el, az) arrays."""
    lat = math.radians(lat_deg)
    dec = math.radians(sun_declination_deg(ls_deg))
    ha = np.radians((np.asarray(ltst_h, float) % 24.0 - 12.0) * 15.0)
    sin_el = np.sin(lat) * np.sin(dec) + np.cos(lat) * np.cos(dec) * np.cos(ha)
    el = np.degrees(np.arcsin(np.clip(sin_el, -1, 1)))
    az = (np.degrees(np.arctan2(np.sin(ha), np.cos(ha) * np.sin(lat) - np.tan(dec) * np.cos(lat))) + 180) % 360
    return el, az


def dark_at(height, dx, dy, rows, cols, el, az, max_dist_m=3000.0):
    """For a list of cells, each with its own sun (el, az arrays): True if the cell is dark,
    either in a cast shadow or on a slope facing away from the sun (sun below ~3 deg on it)."""
    h = np.nan_to_num(height, nan=float(np.nanmin(height)))
    rows, cols = np.asarray(rows), np.asarray(cols)
    el, az = np.asarray(el, float), np.asarray(az, float)
    night = el <= 0
    elr, azr = np.radians(np.maximum(el, 0.01)), np.radians(az)

    # 1) slope facing away: angle between sun and ground surface
    gy, gx = np.gradient(h, dy, dx)  # gy = change per meter going south (row down)
    de, dn = gx[rows, cols], -gy[rows, cols]  # height change per meter east / north
    sun_e, sun_n, sun_u = np.cos(elr) * np.sin(azr), np.cos(elr) * np.cos(azr), np.sin(elr)
    cos_i = (-de * sun_e - dn * sun_n + sun_u) / np.sqrt(de ** 2 + dn ** 2 + 1)
    self_shade = cos_i < math.sin(math.radians(3))

    # 2) cast shadow: march toward the sun
    step_m = min(dx, dy)
    sc, sr = np.sin(azr) * step_m / dx, -np.cos(azr) * step_m / dy
    rise = np.tan(elr) * step_m
    cast = np.zeros(len(rows), bool)
    base_h = h[rows, cols]
    span = float(h.max() - h.min())
    for k in range(1, int(max_dist_m / step_m) + 1):
        live = ~cast & ~night & (rise * k <= span)
        if not live.any():
            break
        r = np.rint(rows + sr * k).astype(int)
        c = np.rint(cols + sc * k).astype(int)
        ok = live & (r >= 0) & (r < h.shape[0]) & (c >= 0) & (c < h.shape[1])
        cast[ok] = h[r[ok], c[ok]] > base_h[ok] + rise[ok] * k
    return night | self_shade | cast
