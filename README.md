# TARS on Mars

Plan a Mars walk: route, time, oxygen.

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

## Did we check it?

- **Against Perseverance's real drive**: we took every point of the rover's path inside our map (sols 14 to 731). With a single 20 deg limit our map calls 98.6% of it GO and only 0.3% NO-GO, so it almost never blocks ground the rover actually drove on. With the stricter ground-type limits it's 95.2% GO and 1.3% NO-GO, all of that on the delta fan where we ask a person on foot to be more careful than a six-wheeled rover. The rover never drove on a single square of the mapped sand. Our slope also matches the tilt the rover measured itself at 201 stops: the medians are the same (3.1 deg) and we're off by 1.5 deg on average. Run `python -m validation.rover_check`.
- **AI height map vs measured**: the 50 cm MADNet map looks sharper, but it misses about 21.5% of the spots the measured map says are over 20 deg. So we only use it for looks, never for safety. Run `python -m validation.madnet_check`.
- **Tests**: `python -m pytest` (slope math, routing around cliffs, point of no return, sun position, shadows, radio horizon, scouting, the API).

Honest limits: a rover isn't a person, so the rover check proves our slope numbers, not the 20 deg limit itself (that follows NASA's Artemis guidance and you can change it). The radio check is straight line only, real radio does a bit better. The geologic map is 1:75,000 so its borders can be tens of meters off.

## Run it

```
pip install -r requirements.txt
python -m pipeline.loader        # downloads the height map piece, first time only (~430 MB read)
python -m pipeline.geology       # ground types from the geologic map
python -m pipeline.costmap       # slope + zones
uvicorn api.main:app --reload    # server, docs at http://localhost:8000/docs

cd frontend && npm install && npm run dev   # app at http://localhost:5173
```

## Data and credits

- Mars 2020 Terrain Relative Navigation HiRISE DTM (1 m) and ortho mosaic of Jezero, USGS Astrogeology Science Center / NASA. Public domain.
- Sun, V.Z., and Stack, K.M., 2020, Geologic map of Jezero crater and the Nili Planum region, Mars: USGS Scientific Investigations Map 3464. Public domain.
- Perseverance rover traverse and waypoints (M20_traverse.json, M20_waypoints.json), NASA/JPL-Caltech.
- MADNet 50 cm DTM of Jezero (Tao et al.), Freie Universitaet Berlin Refubium, CC BY 4.0. Used for visuals only.
- Sun position on Mars: Allison, M., and McEwen, M., 2000, Planetary and Space Science 48, the formulas behind NASA GISS Mars24.
- Libraries: numpy, scikit-image, rasterio, geopandas, pyogrio, matplotlib, pillow, FastAPI, React, Leaflet, three.js, Vite.

No NASA, JPL or USGS logos are used. This is a student project, not an official NASA product.

## Team

Piyush Thakkar, Archi Tyagi
