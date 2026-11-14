"""Wider pictures around the planning box: all of Mars, the region around Jezero, and the 21 km photo
mosaic. The web app shows them darkened, so people see where the box sits and that the ground around
it is real but not mapped for walking. The planner never uses them."""
import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.main import app, site
from pipeline import context

c = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]
PHOTO = ROOT / "data" / "jezero" / "photo.npz"
LEVELS = {lv["id"]: lv for lv in context.info("jezero")}
needs_all = pytest.mark.skipif(set(LEVELS) != {"planet", "region", "mosaic"},
                               reason="context pictures not built (python -m pipeline.context jezero <level>)")
needs_photo = pytest.mark.skipif(not PHOTO.exists(), reason="photo not downloaded (python -m pipeline.photo)")
R_MARS = 3396190.0


def picture(level):
    return np.asarray(Image.open(ROOT / "assets" / f"context_jezero_{level}.jpg").convert("L"), "float64")


# ---- the small pieces of arithmetic ---------------------------------------------------

def test_sample_rows_spreads_rows_inside_each_block():
    # 200 source rows, blocks of 64: three whole blocks, the last 8 rows are left out
    assert context.sample_rows(200, 64, 2) == [[16, 48], [80, 112], [144, 176]]


def test_sample_rows_with_one_row_takes_the_middle_of_each_block():
    assert context.sample_rows(128, 64, 1) == [[32], [96]]


def test_sample_rows_at_full_sharpness_is_every_row():
    assert context.sample_rows(3, 1, 1) == [[0], [1], [2]]


def test_shrink_averages_rows_and_columns_and_skips_empty_pixels():
    a = np.array([[10, 20, 0, 0], [30, 40, 0, 8]], "uint8")
    out = context.shrink(a, 2)
    assert out.dtype == np.uint8 and out.tolist() == [25, 8]  # 0 = no data, left out of the average


def test_shrink_keeps_fully_empty_blocks_empty():
    assert context.shrink(np.zeros((2, 8), "uint8"), 4).tolist() == [0, 0]


def test_shrink_drops_columns_that_do_not_fill_a_block():
    assert context.shrink(np.full((1, 7), 9, "uint8"), 3).tolist() == [9, 9]


def test_shrink_by_one_changes_nothing():
    assert context.shrink(np.array([[3, 0, 250]], "uint8"), 1).tolist() == [3, 0, 250]


def test_extent_is_whole_blocks_counted_from_the_top_left_corner():
    # origin, pixel size and size of the USGS HiRISE mosaic (from the file itself)
    e = context.extent(left=4577366.0, top=1106618.0, res=0.25, width=85600, height=85952, k=64)
    assert e == {"left": 4577366.0, "top": 1106618.0, "right": 4598758.0, "bottom": 1085130.0,
                 "cols": 1337, "rows": 1343, "m_per_px": 16.0}


def test_window_without_a_size_is_the_whole_source():
    assert context.window(100, 50, 0.0, 0.0, 10.0) == (0, 0, 100, 50)


def test_window_is_a_square_around_the_center():
    # source: 100 x 100 pixels of 10 m, top-left at (0, 1000). Center (500, 500), half size 200 m
    assert context.window(100, 100, 0.0, 1000.0, 10.0, (500.0, 500.0), 200.0) == (30, 30, 40, 40)


def test_window_is_cut_where_the_source_ends():
    assert context.window(100, 100, 0.0, 1000.0, 10.0, (50.0, 950.0), 200.0) == (0, 0, 25, 25)


def test_levels_fill_in_the_address_and_credit_from_the_config():
    cfg = {"photo_url": "https://x/p.tif",
           "context": [{"id": "a", "url": "https://x/a.tif", "source": "S"},
                       {"id": "b", "url_key": "photo_url", "source_key": "photo"},
                       {"id": "c", "url_key": "missing"}]}
    out = context.levels(cfg)
    assert [lv["id"] for lv in out] == ["a", "b"]  # a level with no address is left out
    assert out[1]["url"] == "https://x/p.tif" and "HiRISE" in out[1]["source"]


def test_a_site_with_no_context_in_its_config_has_none():
    assert context.levels({}) == [] and context.info("moon") == []


# ---- the pictures themselves -------------------------------------------------------------

@needs_all
def test_levels_come_far_to_near_and_each_holds_the_next():
    order = [lv["id"] for lv in context.info("jezero")]
    assert order == ["planet", "region", "mosaic"]
    s = site(None, "jezero")
    box = {"left": s.x0, "top": s.y0, "right": s.x0 + s.a * s.zone.shape[1], "bottom": s.y0 + s.e * s.zone.shape[0]}
    chain = [LEVELS[i]["extent_xy"] for i in order] + [box]
    for outer, inner in zip(chain, chain[1:]):
        assert outer["left"] < inner["left"] and outer["right"] > inner["right"]
        assert outer["bottom"] < inner["bottom"] and outer["top"] > inner["top"]
        assert (outer["right"] - outer["left"]) > 3 * (inner["right"] - inner["left"])  # worth a level of its own


@needs_all
def test_the_planet_picture_is_the_whole_planet():
    e = LEVELS["planet"]["extent_xy"]
    half_around = np.pi * R_MARS  # 180 degrees of longitude in map meters
    px = LEVELS["planet"]["m_per_px"]
    assert abs(e["left"] + half_around) < px and abs(e["right"] - half_around) < px
    assert abs(e["top"] - half_around / 2) < px and abs(e["bottom"] + half_around / 2) < px


@needs_all
@pytest.mark.parametrize("level", ["planet", "region", "mosaic"])
def test_picture_size_matches_its_extent(level):
    i = LEVELS[level]
    e = i["extent_xy"]
    w, h = Image.open(ROOT / "assets" / f"context_jezero_{level}.jpg").size
    assert (w, h) == (i["cols"], i["rows"])
    assert (e["right"] - e["left"]) / w == pytest.approx(i["m_per_px"], rel=1e-9)
    assert (e["top"] - e["bottom"]) / h == pytest.approx(i["m_per_px"], rel=1e-9)


@needs_all
@needs_photo
def test_mosaic_lines_up_with_the_site_photo():
    """Inside the planning box the 21 km picture must show the same ground as the sharp site photo.
    Average the 1 m site photo over the exact footprint of every 16 m picture pixel and compare.
    The picture is built from 2 of every 64 source rows, so it is close but not identical."""
    i = LEVELS["mosaic"]
    e, m = i["extent_xy"], int(i["m_per_px"])
    s = site(None, "jezero")
    p = np.load(PHOTO)["gray"].astype("float64")  # 1 m per pixel, top-left at (s.x0, s.y0)
    ctx = picture("mosaic")
    c0 = int(np.ceil((s.x0 - e["left"]) / m)) + 2
    r0 = int(np.ceil((e["top"] - s.y0) / m)) + 2
    n = (p.shape[0] // m) - 6

    def site_mean(dr, dc):
        px = int(e["left"] + (c0 + dc) * m - s.x0)
        py = int(s.y0 - (e["top"] - (r0 + dr) * m))
        return p[py: py + n * m, px: px + n * m].reshape(n, m, n, m).mean(axis=(1, 3))

    a = ctx[r0: r0 + n, c0: c0 + n]
    match = {(dr, dc): float(np.corrcoef(a.ravel(), site_mean(dr, dc).ravel())[0, 1])
             for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
    assert match[(0, 0)] > 0.9
    assert max(match, key=match.get) == (0, 0)  # one pixel off in any direction fits worse


@needs_all
def test_region_and_planet_show_the_same_ground_in_the_same_place():
    """Both come from the same Viking mosaic. Average the region over the footprint of each planet
    pixel: it must match the planet picture there, and best with no shift."""
    reg, pla = LEVELS["region"], LEVELS["planet"]
    er, ep = reg["extent_xy"], pla["extent_xy"]
    k = int(round(pla["m_per_px"] / reg["m_per_px"]))
    r, p = picture("region"), picture("planet")
    c0 = int(np.ceil((er["left"] - ep["left"]) / pla["m_per_px"])) + 1
    r0 = int(np.ceil((ep["top"] - er["top"]) / pla["m_per_px"])) + 1
    n = r.shape[0] // k - 3

    def region_mean(dr, dc):
        px = int(round((ep["left"] + (c0 + dc) * pla["m_per_px"] - er["left"]) / reg["m_per_px"]))
        py = int(round((er["top"] - (ep["top"] - (r0 + dr) * pla["m_per_px"])) / reg["m_per_px"]))
        return r[py: py + n * k, px: px + n * k].reshape(n, k, n, k).mean(axis=(1, 3))

    a = p[r0: r0 + n, c0: c0 + n]
    match = {(dr, dc): float(np.corrcoef(a.ravel(), region_mean(dr, dc).ravel())[0, 1])
             for dr in (-1, 0, 1) for dc in (-1, 0, 1)}
    assert match[(0, 0)] > 0.9
    assert max(match, key=match.get) == (0, 0)


# ---- the API ---------------------------------------------------------------------------------

@needs_all
def test_site_info_lists_the_context_pictures():
    ctx = c.get("/api/site").json()["context"]
    assert [x["id"] for x in ctx] == ["planet", "region", "mosaic"]
    for x in ctx:
        assert x["url"] == f"/api/layers/context.jpg?site=jezero&level={x['id']}"
        assert set(x["extent_xy"]) == {"left", "top", "right", "bottom"}
        assert x["m_per_px"] > 0 and x["name"] and x["about"] and x["source"] and x["note"]


@needs_all
@pytest.mark.parametrize("level", ["planet", "region", "mosaic"])
def test_context_picture_is_served_as_a_cached_jpeg(level):
    r = c.get(f"/api/layers/context.jpg?level={level}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert "max-age" in r.headers["cache-control"] and r.headers["x-source"] == LEVELS[level]["source"]
    assert Image.open(io.BytesIO(r.content)).size == (LEVELS[level]["cols"], LEVELS[level]["rows"])


@needs_all
def test_without_a_level_you_get_the_nearest_picture():
    assert c.get("/api/layers/context.jpg").content == c.get("/api/layers/context.jpg?level=mosaic").content


@needs_all
def test_an_unknown_level_says_which_ones_exist():
    r = c.get("/api/layers/context.jpg?level=galaxy")
    assert r.status_code == 404 and r.json()["detail"] == "No such picture. This site has: planet, region, mosaic."


def test_a_site_without_context_pictures_says_so():
    assert c.get("/api/site?site=moon").json()["context"] == []
    r = c.get("/api/layers/context.jpg?site=moon")
    assert r.status_code == 404 and r.json()["detail"] == "No wider picture for this site."


def test_context_for_an_unknown_site_is_a_404():
    assert c.get("/api/layers/context.jpg?site=nowhere").status_code == 404
