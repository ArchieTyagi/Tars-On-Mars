"""Mars season (Ls) from an Earth date or a Perseverance sol number.

Allison & McEwen 2000 (Planetary and Space Science 48), the algorithm behind
NASA GISS Mars24. Good to about 0.01 deg in Ls.
"""
import math
from datetime import datetime, timedelta, timezone

TT_MINUS_UTC_S = 69.184            # since 2017
SOL_S = 88775.244                  # one Mars solar day in seconds
MARS_HOUR_IN_EARTH_HOURS = SOL_S / 86400.0  # 1.0275
# Perseverance landed 2021-02-18 20:55 UTC, local mean solar time ~15:53 on sol 0
M20_LANDING_UTC = datetime(2021, 2, 18, 20, 55, tzinfo=timezone.utc)
M20_LANDING_LMST_H = 15.88

_PBS = [(0.0071, 2.2353, 49.409), (0.0057, 2.7543, 168.173), (0.0039, 1.1177, 191.837),
        (0.0037, 15.7866, 21.736), (0.0021, 2.1354, 15.704), (0.0020, 2.4694, 95.528),
        (0.0018, 32.8493, 49.095)]


def ls_from_utc(t):
    jd_ut = 2440587.5 + t.timestamp() / 86400.0
    dt = jd_ut + TT_MINUS_UTC_S / 86400.0 - 2451545.0
    m = math.radians(19.3871 + 0.52402073 * dt)
    alpha_fms = 270.3871 + 0.524038496 * dt
    pbs = sum(a * math.cos(math.radians(0.985626 * dt / tau + phi)) for a, tau, phi in _PBS)
    v_minus_m = ((10.691 + 3.0e-7 * dt) * math.sin(m) + 0.623 * math.sin(2 * m) + 0.050 * math.sin(3 * m)
                 + 0.005 * math.sin(4 * m) + 0.0005 * math.sin(5 * m) + pbs)
    return (alpha_fms + v_minus_m) % 360.0


def utc_from_m20_sol(sol, lmst_h=12.0):
    return M20_LANDING_UTC + timedelta(seconds=(sol + (lmst_h - M20_LANDING_LMST_H) / 24.0) * SOL_S)


def ls_from_m20_sol(sol, lmst_h=12.0):
    return ls_from_utc(utc_from_m20_sol(sol, lmst_h))
