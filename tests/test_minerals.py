import numpy as np
from fastapi.testclient import TestClient

from api.main import app
from pipeline.minerals import KEY, UNIDENTIFIED, classify_rgb, name_of

c = TestClient(app)


def rgb(*cols):
    a = np.array(cols, np.uint8).T.reshape(3, 1, len(cols))
    return a


def test_key_colors_and_shades():
    codes = classify_rgb(rgb((255, 0, 0), (153, 0, 0), (148, 74, 66), (255, 255, 255), (0, 0, 0), (60, 60, 60)))[0]
    assert codes[0] == 1 and codes[1] == 101            # olivine high / medium
    assert codes[2] == 104                              # a smoothed shade of olivine+smectite medium (153,77,68)
    assert codes[3] == 0 and codes[4] == UNIDENTIFIED   # white = no data, black = not identified
    assert codes[5] == 0                                # not in the key -> no data, never guessed


def test_names():
    assert name_of(2) == ("Mg-carbonate", "high") and name_of(102) == ("Mg-carbonate", "medium")
    assert name_of(0) == (None, None) and name_of(UNIDENTIFIED) == ("not identified", None)


def test_api_minerals():
    j = c.get("/api/minerals").json()
    assert len(j["classes"]) == len(KEY) and "further analysis" in j["caveat"]
    assert c.get("/api/layers/minerals.png").content[:4] == b"\x89PNG"
    assert c.get("/api/site").json()["has_minerals"]
    assert c.get("/api/layers/minerals.png?site=moon").status_code == 404
    r = c.post("/api/plan", json={"base": [77.4508, 18.4447], "stops": [[77.46, 18.47]]}).json()
    assert r["stop_minerals"] and r["stop_minerals"][0]["stop"] == 1
