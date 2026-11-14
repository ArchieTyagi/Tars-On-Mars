# API guide (for the web app)

Start the server with `uvicorn api.main:app --reload`. Everything lives under `/api`.
A clickable version of this list, where you can try every call, is at `/docs` on the running server.

Things that are true everywhere:

- A position is always `[longitude, latitude]` in degrees, in that order.
- Every call takes `site` (`jezero` or `moon`). Leave it out and you get `jezero`.
- When something is wrong you get status 422 (bad input) or 404 (does not exist) and a body like
  `{"detail": "Stop 2 is on NO-GO ground (27 deg slope). Pick a spot nearby."}`. The `detail` text is written
  for the person using the app, so show it as it is.
- Hours are Earth hours. Only `start_ltst_h` and `end_ltst_h` are Mars clock time (0 to 24, 12 = local noon).
- Big answers come gzip-compressed. The browser unpacks them by itself.
- All pictures cover exactly the same ground box, so they stack on the map with the same corners.

## What exists

| Address | What it gives |
|---|---|
| `/api/health` | `{"ok": true}` |
| `/api/sites` | the list of sites (id, name, body) |
| `/api/site` | everything about one site: corners, grid, default base, rules, which layers it has (see below) |
| `/api/point` | what is under one spot: height, slope, zone, mineral. Needs `lon`, `lat` |
| `/api/convert` | lon/lat to map meters and back. Needed to draw the Moon site (see the Moon note) |
| `/api/plan` | the route planner (POST). The main call, described below |
| `/api/science_stops` | mineral spots worth a stop that you can reach on your oxygen. Needs `lon`, `lat` of the base |
| `/api/rover` | where Perseverance really drove, its stops, and what our map says there. `whole` is the whole drive, also outside the box, for drawing only |
| `/api/helicopter` | where the Ingenuity helicopter really flew: all 72 flights as lines, with NASA's facts for each. Jezero only |
| `/api/weather` | typical temperature and wind for every hour of a season, plus the sky. Needs `ls` |
| `/api/dust` | how hazy the sky is through the Mars year (12 slices) |
| `/api/sun` | where the sun is. Needs `ls`, `ltst_h` |
| `/api/sol_to_ls` | season (`ls`) for a Perseverance mission day. Needs `sol` |
| `/api/minerals` | legend for the mineral layer, with the authors' caveat |
| `/api/terrain` | the height grid for the 3D view (binary, see below) |
| `/api/layers/photo.jpg` | the real photo of the ground. `m_per_px` = 1, 2 or 4 |
| `/api/layers/hillshade.png` | shaded relief |
| `/api/layers/zones.png` | CAUTION and NO-GO ground. Optional `slope_limit` |
| `/api/layers/slope.png` | slope in six color steps |
| `/api/layers/ground.png` | ground type (sand, delta fan, bedrock). Jezero only |
| `/api/layers/minerals.png` | minerals. Jezero only |
| `/api/layers/slope_risk.png` | looks walkable but could be too steep. Moon only |
| `/api/layers/safe_range.png` | where you can walk to and back on your oxygen. Needs `lon`, `lat` of the base |
| `/api/layers/radio.png` | where the suit has direct radio to base. Needs `lon`, `lat` of the base |
| `/api/layers/context.jpg` | a wider picture of the ground around the planning box. `level` picks which one (see below) |

## Layers: do not hardcode them

`/api/site` returns `layers`: every layer this site can draw. Build the layer switcher from that list.
Each entry has `id`, `name`, `about` (one line to show the user), `kind` (`base` or `overlay`), `url`,
`needs_base` (true = add `&lon=..&lat=..` of the base), `options` (extra settings the layer accepts)
and `legend` (a list of `color` and `label`).

To place a picture on the map use `bounds` from `/api/site` (`west`, `south`, `east`, `north`).

## The ground around the box: `context`

`/api/site` also returns `context`: wider pictures around the planning box, from far to near. For Jezero that is
`planet` (all of Mars), `region` (about 237 km around Jezero) and `mosaic` (the 21 km photo mosaic the box is cut from).
A site with none (the Moon) gives an empty list.

Each entry has `id`, `name`, `url`, `extent_xy` (`left`, `top`, `right`, `bottom` in the same map meters as the
site's own `extent_xy`, so the pictures stack under the map with no conversion), `m_per_px`, `about`, `note` and `source`.

The planner does not use these pictures. No checked height map is loaded out there, so draw them darkened and tell
the user that ground is not mapped for walking. A base or stop outside the planning box is still refused by `/api/plan`.

`/api/layers/context.jpg?level=planet` serves one picture. Without `level` you get the nearest one.

## Planning a route: POST `/api/plan`

Send JSON. Only `base` and `stops` are required.

| Field | Meaning |
|---|---|
| `site` | `jezero` or `moon` |
| `base` | `[lon, lat]` where the walk starts and ends |
| `stops` | 1 to 6 positions to visit. The planner picks the best order |
| `slope_limit` | 5 to 35 degrees on firm ground. Looser ground scales with it (at 30, sand is 15) |
| `o2_hours` | suit oxygen supply in hours |
| `o2_reserve` | share kept untouched, 0.25 = 25% |
| `walk_speed_kmh` | walking speed on flat ground |
| `stop_minutes` | time spent working at each stop |
| `base_antenna_m`, `suit_antenna_m` | antenna heights for the radio check |
| `ls`, `start_ltst_h` | season and Mars clock time at the start. Give both or neither. They switch on sun, weather and sky |
| `observations` | helicopter reports: a list of `{"lonlat": [lon, lat], "finding": "safe" or "blocked", "radius_m": 20}` |

What comes back:

| Field | Meaning |
|---|---|
| `site` | the site you asked for |
| `order` | the order the stops are visited in (1 = your first stop) |
| `km` | length of the whole loop |
| `hours` | the whole outing: walking plus time at the stops |
| `walk_hours`, `stop_hours` | the two parts of `hours` |
| `stop_arrivals` | for each stop: when you arrive and leave, and its index in `path` |
| `legs` | each stretch between stops: km, hours, steepest slope, climb and descent |
| `max_slope` | steepest ground on the route, degrees |
| `settings` | the mission settings that were used (yours, or the defaults) |
| `usable_o2_h` | oxygen you may use: supply minus reserve |
| `o2_ok` | true when the outing fits the usable oxygen |
| `o2_margin_h` | hours of usable oxygen left at the end (negative = short) |
| `point_of_no_return` | null, or where you must turn back to still reach base |
| `path` | the route as a list of `[lon, lat]` |
| `path_xy` | the same route in map meters (for the Moon and for 3D) |
| `elapsed_h`, `home_h`, `margin_h` | for every point of `path`: time since the start, time to walk straight home, oxygen margin |
| `slope_deg`, `height_m`, `dist_m` | for every point of `path`: slope, height, distance walked so far |
| `elevation` | start, highest and lowest height, total climb and descent |
| `light` | sun at start and end, warnings (low sun, sunset, dark start), and dark stretches. Null without `ls` or on the Moon |
| `weather` | air and ground temperature, wind, and `sky` (haze) for your season and hours. Null without `ls` or on the Moon |
| `radiation` | dose for the outing in microsieverts, and where the rate was measured |
| `radio` | for every point: in contact or not, the blackouts, the longest one |
| `scout` | spots where the map is least sure, and helicopter hops to check them |
| `stop_minerals` | the mineral at each stop (Jezero) |
| `observations` | the helicopter reports that were applied |

All the per-point lists have the same length as `path`, so index `i` means the same spot in each of them.

## The 3D height grid: `/api/terrain`

Raw numbers, not JSON: 32-bit floats, little-endian, row by row from the north edge.
`step` (1 to 16, default 4) takes every Nth cell. The size comes in the response headers:
`X-Rows`, `X-Cols`, `X-Dx-M`, `X-Dy-M` (meters between points east-west and north-south).

```js
const r = await fetch("/api/terrain?step=4");
const rows = +r.headers.get("X-Rows"), cols = +r.headers.get("X-Cols");
const heights = new Float32Array(await r.arrayBuffer());   // heights[row * cols + col]
```

The photo layer covers the same box, so it can be used as the ground texture.

## The Moon note

Jezero is a plain lon/lat grid, so `bounds` gives its true edges. The Moon site is at the south pole, where
lon/lat lines curve, so draw it in map meters instead: use `extent_xy` from `/api/site`, `path_xy` from the plan,
and `/api/convert` to turn a click (x, y) into lon/lat before sending it to the planner.
The sun, weather and sky are Mars only. `/api/site` says so with `sun_check`.
