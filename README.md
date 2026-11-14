# TARS on Mars

Plan a Mars walk: route, time, oxygen.

**Try it live: https://tars-on-mars.vercel.app**

The engine behind it runs on a small free server, so a plan takes around 15 seconds. To run it fast on your own machine, see the run steps below.

NASA Space Apps Challenge 2026, challenge "Interplanetary Survival Guide: Martian Map". Team TARS on Mars, Ahmedabad local event.

You put down a base and a few stops at Jezero Crater. It finds the safest walking loop, tells you how long it takes, whether it fits your oxygen, and where the point of no return is (past it you can't make it home). It also checks the sun along the walk, where you lose radio contact with base, and which parts of the route a scout helicopter should look at first.

## How it works

- **Height map**: the measured 1 m HiRISE height map of Jezero from USGS (5 x 5 km around the Perseverance landing site).
- **Slope**: worked out from the heights, then shrunk to a 4 m grid keeping the steepest value in each square, so a cliff can't hide inside an average.
- **Ground type**: from the USGS geologic map of Jezero. Sand ripples get a 10 deg limit, the delta fan 15 deg (loose debris), rock 20 deg. All limits live in `config/rules.json`.
- **Zones**: every 4 m square is GO, CAUTION (close to its limit) or NO-GO. Gaps in the data count as NO-GO.
- **Route**: tries every stop order and picks the cheapest safe loop.
- **Oxygen**: suit supply, reserve and walking speed are inputs. Walking is slower on slopes.
- **Point of no return**: from every square we know the walking time back to base, so we can tell the exact moment you have to turn around.
- **Sun**: the sun moves during a long walk, so each point uses the sun at the time you get there (season + Mars local time). Flags spots next to a drop that is in shadow right then, low sun, and sunset before you're back.
- **Radio**: straight line of sight between the suit and the base antenna, including the curve of Mars.
- **Scouting**: finds where the map is least sure (slope right at the limit, rough ground, near a ground-type border, hazards in shadow), plans helicopter hops within flight range, and re-plans after the helicopter reports safe or blocked.
- **Time at stops**: you set how long you work at each stop. It counts toward oxygen, sunset and radio like walking does.
- **Climb**: height along the route, total climb and descent. Ripples under half a meter are not counted, the height map can't tell them from noise.
- **Real photo**: the HiRISE photo of the same 5 x 5 km box, as a layer under everything else.
- **The rest of Mars**: zoom out and you see the 21 km photo mosaic around the box, then the region, then the whole planet. All of it is darkened and marked as not mapped for walking, because we only plan where a checked 1 m height map is loaded.
- **Rover track**: where Perseverance really drove inside our box (17 km), with its stops and the tilt it measured.
- **Minerals and science stops**: the CRISM mineral map on our grid. The planner suggests mineral patches you can reach and get back from on your oxygen, water-made minerals first.
- **Weather**: typical air temperature, ground temperature and wind for your season and hours, from Perseverance's MEDA station. Not a forecast.
- **Sky haze**: how much dust and thin ice cloud dims the sun in each part of the Mars year, from the rover's Mastcam-Z sun images.
- **Radiation**: the dose for the outing, using the rate Curiosity measured at Gale crater (not at Jezero, nobody has measured it there). Background cosmic rays only, no solar storms.
- **Moon mode**: the same planner on NASA's LOLA map of a south pole site. That map comes with its own slope error, so we also show ground that looks walkable but could be over the limit (22.8% of that map).

## Did we check it?

- **Against Perseverance's real drive**: we took every point of the rover's path inside our map (sols 14 to 731). With a single 20 deg limit our map calls 98.6% of it GO and only 0.3% NO-GO, so it almost never blocks ground the rover actually drove on. With the stricter ground-type limits it's 95.2% GO and 1.3% NO-GO, all of that on the delta fan where we ask a person on foot to be more careful than a six-wheeled rover. The rover never drove on a single square of the mapped sand. Our slope also matches the tilt the rover measured itself at 201 stops: the medians are the same (3.1 deg) and we're off by 1.5 deg on average. Run `python -m validation.rover_check`.
- **AI height map vs measured**: the 50 cm MADNet map looks sharper, but it misses about 21.5% of the spots the measured map says are over 20 deg. So we only use it for looks, never for safety. Run `python -m validation.madnet_check`.
- **Slope against NASA's own**: on the Moon site LOLA publishes its own slope map. Over 10.2 million cells the typical difference from ours is 0.0001 deg, and the two agree on which cells are over 20 deg for 99.999% of them.
- **Routes against a second solver**: a separate shortest-path solver (scipy Dijkstra) on all 1.56 million cells gives the same costs and the same stop order.
- **Sun, shadows, radio**: sunrise, sunset and noon height match the textbook formulas, a 10 m test wall casts the right shadow length, and radio over flat ground ends at the horizon distance (8.2 km for a 3 m mast and a 2 m suit antenna).
- **Backdrop pictures**: inside the box the 21 km backdrop matches our sharp site photo best with no shift at all, and the region picture matches the planet picture the same way. On the web map the box lands on Jezero's longitude and latitude on the planet picture. These are tests (`tests/test_context.py`).
- **Photo on the height map**: we shade the height map from every sun direction and slide the photo around. The best fit is with the sun in the west and the photo within one 4 m grid square of where it already is.
- **Heights**: our height at the landing site is -2569.91 m, the rover's own position file says -2569.91 m.
- **Re-run them**: the slope, second-solver, photo and height checks are one script, `python -m validation.independent_checks` (results in `docs/independent_checks.json`). The sun, shadow and radio checks are in the tests.
- **Random trips**: `python -m validation.random_trips jezero 40 1` (or `moon`) plans random trips and checks rules that must always hold (never on NO-GO, time never runs backwards, a loop climbs as much as it descends, and so on).
- **Tests**: `python -m pytest` (slope math, routing around cliffs, point of no return, sun position, shadows, radio horizon, scouting, bad input, every layer and the API).

Honest limits: a rover isn't a person, so the rover check proves our slope numbers, not the 20 deg limit itself (that follows NASA's Artemis guidance and you can change it). The radio check is straight line only, real radio does a bit better. The geologic map is 1:75,000 so its borders can be tens of meters off. Oxygen is used at a steady rate per hour, walking uphill and downhill slow you down the same, and rocks smaller than 4 m only show up as roughness. Mineral pixels are 36 m, so a science stop is a patch, not an exact rock. The sky haze data is marked preliminary by its author. Weather and haze are typical values for a season, not a forecast.

## Run it

```
pip install -r requirements.txt
python -m pipeline.loader        # downloads the height map piece, first time only (~430 MB read)
python -m pipeline.geology       # ground types from the geologic map
python -m pipeline.costmap       # slope + zones
python -m pipeline.photo         # the real photo of the same box (reads ~1.7 GB, can be re-run if it stops)
uvicorn api.main:app --reload    # server, docs at http://localhost:8000/docs

cd frontend && npm install && npm run dev   # app at http://localhost:5173
```

The weather, haze and rover tables and the three backdrop pictures are small and already in `assets/`. The scripts that made them are `pipeline/weather_fetch.py` + `weather_build.py`, `pipeline/dust.py`, `pipeline/rover.py` and `pipeline/context.py` (run it once per level: `python -m pipeline.context jezero planet`, then `region`, then `mosaic`). The mineral layer needs `jezeroFinal.tif` from the Zenodo record below in `data/minerals/`, then `python -m pipeline.minerals`. The Moon site needs the LOLA Site01 files in `data/moon/`, then `python -m pipeline.loader moon` and `python -m pipeline.costmap moon`.

For the web app: `docs/API.md` lists every call and every field.

## Data and credits

- Mars 2020 Terrain Relative Navigation HiRISE DTM mosaic (1 m), Fergason et al. 2020, USGS Astrogeology Science Center, doi:10.5066/P9REJ9JN. Height map.
- Mars 2020 Terrain Relative Navigation HiRISE Orthorectified Image Mosaic (25 cm), Fergason et al. 2020, USGS Astrogeology Science Center, doi:10.5066/P9QJDP48, CC0. Photo layer. Image data: NASA/JPL/University of Arizona.
- Mars Viking Colorized Global Mosaic 232m (MDIM 2.1), USGS Astrogeology Science Center, colorized by NASA Ames, public domain. Image data: NASA/JPL/USGS. Only used as the darkened backdrop around the planning box.
- Sun, V.Z., and Stack, K.M., 2020, Geologic map of Jezero crater and the Nili Planum region, Mars: USGS Scientific Investigations Map 3464. Public domain.
- Perseverance rover traverse and waypoints (M20_traverse.json, M20_waypoints.json), NASA/JPL-Caltech.
- Ingenuity helicopter flight paths and waypoints (m20_heli_flight_path.json, m20_heli_waypoints.json), NASA/JPL-Caltech. In the flight path file the lines numbered 12 and 13 are swapped; we pair lines and facts by their length, which is the same number in both files.
- CRISM mineral map of Jezero: Parente, Saranathan, Itoh, Tarnas, Seelos, Mustard (2021), Zenodo, doi:10.5281/zenodo.5575824, CC BY 4.0. Mineral names are the closest match to known minerals.
- Perseverance MEDA weather station data (air and ground temperature, wind), Rodriguez-Manfredi et al., NASA Planetary Data System.
- Mark Lemmon, The Perseverance Rover's Mastcam-Z Visible Aerosol Optical Depth Record, Mendeley Data v2 (2026), doi:10.17632/gktjp9jptb.2, CC BY 4.0. Marked preliminary by the author. Sky haze.
- Radiation on Mars: Hassler et al. 2014, Science 343, doi:10.1126/science.1244797 (Curiosity RAD at Gale crater). On the Moon: Zhang et al. 2020, Science Advances 6, doi:10.1126/sciadv.aaz1334 (Chang'E-4 LND).
- LOLA 5 m south pole landing site maps (Site01: height, slope, slope error), Barker et al. 2021, NASA Goddard. Moon mode.
- Mars season from the date: Allison and McEwen 2000 (same paper as the sun position).
- MADNet 50 cm DTM of Jezero (Tao et al.), Freie Universitaet Berlin Refubium, CC BY 4.0. Used for visuals only.
- Sun position on Mars: Allison, M., and McEwen, M., 2000, Planetary and Space Science 48, the formulas behind NASA GISS Mars24.
- Libraries: numpy, scipy, scikit-image, rasterio, pyproj, geopandas, pyogrio, matplotlib, pillow, FastAPI, React, Leaflet, three.js, Vite.

No NASA, JPL or USGS logos are used. This is a student project, not an official NASA product.

## Team

Piyush Thakkar, Archi Tyagi, Diksha Chauhan, Anushka Sharma
