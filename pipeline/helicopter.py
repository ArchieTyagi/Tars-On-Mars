"""Where the Ingenuity helicopter really flew: all of its flights at Jezero, as lines for the map.

Our planner sends a scout helicopter to look at uncertain ground. Ingenuity is the real helicopter
that flew ahead of Perseverance here, so its flights are worth showing next to our plan.

Source: NASA/JPL-Caltech, Mars 2020 mission helicopter location data
(m20_heli_flight_path.json and m20_heli_waypoints.json, from the same place as the rover files:
https://mars.nasa.gov/mmgis-maps/M20/Layers/json/).

Run: python -m pipeline.helicopter   (needs the two files in data/rover/, writes assets/helicopter.json)
"""
import json

from pipeline.loader import ROOT
from pipeline.rover import MARS_RADIUS_M, _inside, _meters, thin

FILE = ROOT / "assets" / "helicopter.json"
SOURCE = ("NASA/JPL-Caltech, Mars 2020 mission helicopter location data "
          "(m20_heli_flight_path.json and m20_heli_waypoints.json, the files behind NASA's 'Where is Perseverance' map)")
SPACING_M = 3.0
NOTE = ("Ingenuity's real flights. The numbers for each flight (length, height, time) are NASA's own. "
        "Our planner does not use them: they are shown so you can compare a planned scouting hop with real ones.")


def flight(path, way, spacing_m=SPACING_M):
    """One flight for the map: NASA's facts from the waypoint record, and the flight line thinned
    to one point every few meters. NASA's length is measured along its much finer line, every small
    wobble included, so it is longer than our thinned line. We show NASA's number, not ours."""
    dist = lambda a, b: _meters(a, b, MARS_RADIUS_M)
    pts = [[round(x, 7), round(y, 7)] for x, y, *_ in path["geometry"]["coordinates"]]
    return {"flight": int(path["properties"]["Flight"]), "sol": int(path["properties"]["Sol"]),
            "date": way["Earth_Date"], "length_m": round(float(path["properties"]["Length_m"]), 1),
            "max_alt_m": float(way["Max_Alt_m"]), "duration_s": float(way["Duration_s"]),
            "from": way["FromAirfld"], "to": way["ToAirfld"], "points": thin(pts, spacing_m, dist)}


def match(paths, ways):
    """Pair every flight line with its record of facts. NASA's two files agree on the flight number
    for all flights but two: the lines numbered 12 and 13 are swapped. In both files a flight's
    length is the same number to the millimeter, so the pairing is done by length, and the number
    is taken from the record of facts (whose dates and lengths match NASA's flight log)."""
    by_len = {}
    for w in ways:
        by_len.setdefault(round(float(w["Dist_m"]), 3), []).append(w)
    out = []
    for p in paths:
        hits = by_len.get(round(float(p["properties"]["Length_m"]), 3), [])
        if len(hits) != 1:
            raise ValueError(f"flight line {p['properties']['Flight']} has no single record with its length")
        out.append((p, hits[0]))
    return out


def build(name="jezero"):
    src = ROOT / "data" / "rover"
    paths = json.load(open(src / "m20_heli_flight_path.json"))["features"]
    ways = [f["properties"] for f in json.load(open(src / "m20_heli_waypoints.json"))["features"] if f["properties"]["Flight"] > 0]
    flights = []
    for p, w in match(paths, ways):
        f = flight(p, w)
        f["flight"], f["sol"] = int(w["Flight"]), int(w["Sol"])
        flights.append(f)
    flights.sort(key=lambda f: f["flight"])
    ways = {int(w["Flight"]): w for w in ways}
    last = ways[max(ways)]
    out = {"source": SOURCE, "site": name, "flights": flights,
           "total": {"flights": len(flights), "km": float(last["Total_km"]), "minutes": float(last["total_min"])},
           "sols": [flights[0]["sol"], flights[-1]["sol"]]}
    FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(flights)} flights, {sum(len(f['points']) for f in flights)} points, {out['total']['km']} km, "
          f"{FILE.stat().st_size // 1024} KB")
    return FILE


def load(name="jezero"):
    if not FILE.exists():
        return None
    t = json.loads(FILE.read_text())
    return t if t.get("site") == name else None


def with_box(site, data):
    """Mark each flight that stayed inside the planning box from takeoff to landing, and count them."""
    inside = _inside(site)
    flights = [{**f, "inside_box": all(inside(p) for p in f["points"])} for f in data["flights"]]
    return {**data, "flights": flights, "inside_planning_box": sum(f["inside_box"] for f in flights), "note": NOTE}


if __name__ == "__main__":
    build()
