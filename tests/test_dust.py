"""How hazy the sky is over Jezero by season: optical depth measured by Perseverance's Mastcam-Z."""
import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from pipeline import dust

c = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "dust" / "m20-ztau-merged-1717.txt"
BASE = [77.4508, 18.4447]

SAMPLE = """PRELIMINARY*****
Optical depth (tau) as measured with M2020 Mastcam-Z
Eye,Type,Sol,LTST,  SCLK_L, Sequence, FL,      Sol,   L_s, tau-B, tau-G, tau-R, tau-I, sig-B, sig-G, sig-R, sig-I,  SZA, Interval
B,N,0010,15.249,0818841314,ZCAM01064,110,  10.6354,  10.0, 0.435, 0.400, 0.440, 0.450, 0.024, 0.024, 0.024, 0.024, 52.70,  24.0
B,N,0011,11.789,0819361167,ZCAM01082,110,  11.4912,  11.0, 0.507,-1.000, 0.515, 0.528, 0.034,-1.000, 0.034, 0.034, 23.55,  24.0
S,N,0012,16.233,0819377610,ZCAM01019,034,  12.6764,  12.0, 0.494, 0.600, 0.502, 0.519, 0.020, 0.020, 0.020, 0.019, 66.73,   0.0
S,N,0700,16.233,0819377610,ZCAM01019,034, 700.6764, 359.9, 0.494, 1.000, 0.502, 0.519, 0.020, 0.020, 0.020, 0.019, 66.73,   0.0
"""


def test_parse_keeps_valid_green_readings_only():
    rows = dust.parse(SAMPLE)
    assert rows == [(10, 10.0, 0.4), (12, 12.0, 0.6), (700, 359.9, 1.0)]   # (sol, Ls, optical depth); the -1 row is dropped


def test_bins_are_30_degrees_of_season():
    b = dust.bins(dust.parse(SAMPLE))
    assert len(b) == 12 and b[0]["ls_from"] == 0 and b[0]["ls_to"] == 30
    assert b[0]["n"] == 2 and b[0]["median"] == 0.5 and b[0]["max"] == 0.6 and b[0]["sols"] == 2
    assert b[11]["n"] == 1 and b[11]["median"] == 1.0
    assert b[5]["n"] == 0 and b[5]["median"] is None


def test_season_lookup_wraps_around_the_year():
    assert dust.bin_index(0) == 0 and dust.bin_index(29.99) == 0 and dust.bin_index(30) == 1
    assert dust.bin_index(359.99) == 11 and dust.bin_index(360) == 0


def test_direct_sunlight_is_the_textbook_formula():
    # optical depth 1 with the sun overhead lets exp(-1) = 36.8% of the direct beam through
    assert abs(dust.direct_sun_share(1.0, 90) - math.exp(-1)) < 1e-9
    assert abs(dust.direct_sun_share(0.5, 30) - math.exp(-0.5 / math.sin(math.radians(30)))) < 1e-9
    assert dust.direct_sun_share(0.5, 0) == 0.0 and dust.direct_sun_share(0.5, -10) == 0.0


def test_table_covers_the_whole_year_with_sane_numbers():
    t = dust.load()
    assert len(t["bins"]) == 12 and "PRELIMINARY" in t["status"].upper() and "Lemmon" in t["source"]
    for b in t["bins"]:
        assert b["n"] >= 20, b                                   # every part of the year was actually measured
        assert 0.1 < b["p10"] <= b["median"] <= b["p90"] <= b["max"] < 10, b


def test_table_shows_what_is_known_about_mars():
    b = dust.load()["bins"]
    med = lambda lo, hi: sorted(x["median"] for x in b if lo <= x["ls_from"] < hi)
    dusty, clear = med(210, 330), med(30, 150)
    # the second half of the Mars year is the dusty season
    assert sum(dusty) / len(dusty) > sum(clear) / len(clear)
    # the regional dust storm that hit Jezero in January 2022 (Ls ~153, Lemmon et al. 2022) must show up
    storm_bin = b[dust.bin_index(153)]
    assert storm_bin["max"] > 2 * storm_bin["median"]


@pytest.mark.skipif(not RAW.exists(), reason="raw file not downloaded")
def test_table_is_exactly_what_the_raw_file_gives():
    assert dust.bins(dust.parse(RAW.read_text())) == dust.load()["bins"]


def test_api_gives_the_year_and_the_season():
    j = c.get("/api/dust").json()
    assert len(j["bins"]) == 12 and "dust" in j["meaning"] and "ice" in j["meaning"]
    w = c.get("/api/weather?ls=200").json()
    assert w["sky"]["optical_depth_typical"] == j["bins"][6]["median"]
    assert abs(w["sky"]["direct_sun_share_overhead"] - round(math.exp(-j["bins"][6]["median"]), 2)) < 1e-9


def test_plan_carries_the_sky_for_its_season():
    j = c.post("/api/plan", json={"base": BASE, "stops": [[77.46, 18.47]], "ls": 250, "start_ltst_h": 10}).json()
    sky = j["weather"]["sky"]
    b = dust.load()["bins"][dust.bin_index(250)]
    assert sky["optical_depth_typical"] == b["median"] and sky["optical_depth_highest_seen"] == b["max"]
    assert "PRELIMINARY" in sky["status"].upper()
