"""The real HiRISE photo under the map: cut to the same box as the height map, and proven to line up with it."""
import io
from pathlib import Path

import numpy as np
import pytest
from affine import Affine
from fastapi.testclient import TestClient
from PIL import Image

from api.main import app, site
from pipeline import photo

c = TestClient(app)
PHOTO = Path(__file__).resolve().parents[1] / "data" / "jezero" / "photo.npz"
needs_photo = pytest.mark.skipif(not PHOTO.exists(), reason="photo not downloaded (python -m pipeline.photo)")


def test_block_mean_averages_each_block():
    a = np.array([[10, 20, 0, 0], [30, 40, 0, 4]], "uint8")
    out = photo.block_mean(a, 2)
    assert out.dtype == np.uint8 and out.tolist() == [[25, 4]]  # empty (0) pixels are left out of the average


def test_block_mean_keeps_fully_empty_blocks_empty():
    assert photo.block_mean(np.zeros((4, 4), "uint8"), 4).tolist() == [[0]]


def test_window_is_the_same_ground_box_as_the_height_map():
    cfg = photo.load_config("jezero")
    # origin and pixel size of the USGS mosaic (from its own label file)
    win = photo.window_for(cfg, Affine(0.25, 0, 4577366.0, 0, -0.25, 1106618.0))
    assert (win.width, win.height) == (20000, 20000)  # 5 km at 25 cm
    left, top = 4577366.0 + win.col_off * 0.25, 1106618.0 - win.row_off * 0.25
    assert (left, top) == (4587140.0, 1096415.0)  # the height map's own top-left corner


@needs_photo
def test_photo_covers_the_whole_map_at_1_m():
    p = np.load(PHOTO)["gray"]
    s = site(None, "jezero")
    assert p.shape == (s.zone.shape[0] * 4, s.zone.shape[1] * 4) and p.dtype == np.uint8
    assert (p == 0).mean() < 0.01 and p.std() > 10  # a real picture, not blank


@needs_photo
def test_photo_lines_up_with_the_height_map():
    """Shade the height map with the same sun as the photo: the two must match best
    with zero shift. A photo that sat even 2 cells (8 m) off would fail this."""
    best = photo.registration_check("jezero")
    assert abs(best["shift_rows"]) <= 1 and abs(best["shift_cols"]) <= 1, best
    assert best["match"] > 0.2, best


@needs_photo
def test_photo_layer_sizes():
    for q, size in (("", 2500), ("?m_per_px=4", 1250), ("?m_per_px=1", 5000)):
        r = c.get("/api/layers/photo.jpg" + q)
        assert r.status_code == 200 and r.content[:2] == b"\xff\xd8", q
        assert Image.open(io.BytesIO(r.content)).size == (size, size)


def test_photo_layer_refuses_what_it_cannot_do():
    assert c.get("/api/layers/photo.jpg?m_per_px=3").status_code == 422
    r = c.get("/api/layers/photo.jpg?site=moon")
    assert r.status_code == 404 and "photo" in r.json()["detail"].lower()
    assert c.get("/api/layers/photo.jpg?site=venus").status_code == 404


def test_site_info_says_whether_there_is_a_photo():
    assert c.get("/api/site?site=moon").json()["has_photo"] is False
    assert c.get("/api/site").json()["has_photo"] is PHOTO.exists()
