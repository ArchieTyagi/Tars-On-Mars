---
title: TARS on Mars
emoji: 🛰️
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: "Plan a safe walk on Mars: route, time, oxygen"
---

# TARS on Mars

Plan a Mars walk: route, time, oxygen.

NASA Space Apps Challenge 2026, challenge "Interplanetary Survival Guide: Martian Map". Team TARS on Mars, Ahmedabad local event.

Put down a base and a few stops at Jezero Crater. It finds the safest walking loop on the measured 1 m height map, tells you how long it takes, whether it fits your oxygen, and where you have to turn back. It also checks the sun along the walk, where you lose radio contact with base, the climb, typical weather and sky haze for the season, radiation for the outing, and which mineral spots are worth a stop. The same planner runs on a Moon south pole site.

Every call the app makes is listed at `/docs`.

Typical values are not forecasts. Radiation is the rate measured at Gale crater (Mars) and at the Chang'E-4 site (Moon), not at these sites, and does not include solar storms. This is a student project, not an official NASA product. No NASA, JPL or USGS logos are used.

## Data and credits

- Mars 2020 Terrain Relative Navigation HiRISE DTM mosaic (1 m), Fergason et al. 2020, USGS Astrogeology Science Center, doi:10.5066/P9REJ9JN.
- Mars 2020 Terrain Relative Navigation HiRISE Orthorectified Image Mosaic (25 cm), Fergason et al. 2020, USGS Astrogeology Science Center, doi:10.5066/P9QJDP48, CC0. Image data: NASA/JPL/University of Arizona.
- Sun, V.Z., and Stack, K.M., 2020, Geologic map of Jezero crater and the Nili Planum region, Mars: USGS Scientific Investigations Map 3464.
- CRISM mineral map of Jezero: Parente, Saranathan, Itoh, Tarnas, Seelos, Mustard (2021), Zenodo, doi:10.5281/zenodo.5575824, CC BY 4.0. Mineral names are the closest match to known minerals.
- Perseverance rover traverse and waypoints, NASA/JPL-Caltech.
- Perseverance MEDA weather station data, Rodriguez-Manfredi et al., NASA Planetary Data System.
- Mark Lemmon, The Perseverance Rover's Mastcam-Z Visible Aerosol Optical Depth Record, Mendeley Data v2 (2026), doi:10.17632/gktjp9jptb.2, CC BY 4.0. Marked preliminary by the author.
- Radiation on Mars: Hassler et al. 2014, Science 343, doi:10.1126/science.1244797. On the Moon: Zhang et al. 2020, Science Advances 6, doi:10.1126/sciadv.aaz1334.
- LOLA 5 m south pole landing site maps (Site01), Barker et al. 2021, NASA Goddard.
- Sun position and Mars season: Allison and McEwen 2000, Planetary and Space Science 48.

## Team

Piyush Thakkar, Archi Tyagi
