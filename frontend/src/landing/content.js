// Every number on the front page comes from the project's own checks (README, docs/independent_checks.json,
// validation/rover_check.py) or straight from the server's answers. Nothing here is an estimate.

export const FACTS = [
  { value: "1 m", text: "measured height map of Jezero Crater (HiRISE, USGS)" },
  { value: "4 m", text: "planning grid, with the steepest value kept in every square" },
  { value: "1.56 M", text: "grid squares, each one GO, CAUTION or NO-GO" },
  { value: "17 km", text: "of Perseverance's real drive used to check the map" },
];

export const SYSTEM = [
  ["Route", "Tries every order of your stops and picks the cheapest safe loop. It never crosses NO-GO ground."],
  ["Zones", "Every 4 m square is GO, CAUTION or NO-GO. Sand gets a 10 degree slope limit, the delta fan 15, rock 20. Gaps in the data count as NO-GO."],
  ["Oxygen", "Suit supply, reserve and walking speed are your inputs. Walking is slower on slopes, and the time you work at each stop counts too."],
  ["Point of no return", "From every square the planner knows the walking time back to base, so it marks the exact spot where you have to turn around."],
  ["Sun", "Each point uses the sun at the time you get there. It flags low sun, drops hidden in shadow, and sunset before you are back."],
  ["Radio", "Straight line of sight between the suit and the base antenna, including the curve of Mars. Every blackout on the route is listed."],
  ["Scout", "Finds where the map is least sure, plans helicopter hops to look there, and plans again after the helicopter reports safe or blocked."],
  ["Science stops", "Mineral patches from the CRISM orbital map that you can reach and get back from on your oxygen. Water-made minerals come first."],
  ["Weather and sky", "Typical temperature, wind and haze for your season and hours, from Perseverance's own instruments. Typical values, not a forecast."],
  ["Radiation", "The dose for the outing at the rate Curiosity measured at Gale crater. Nobody has measured it at Jezero yet."],
  ["Moon mode", "The same planner on NASA's LOLA map of a lunar south pole site, with the map's own slope error shown as a layer."],
];

export const CHECKS = [
  { value: "98.6%", title: "Perseverance's real drive", text: "of the ground the rover drove on between sols 14 and 731 is GO on our map with one 20 degree limit. With our stricter on-foot limits it is 95.2%." },
  { value: "3.1°", title: "Rover tilt", text: "is the middle slope our map gives at 201 rover stops. The middle tilt the rover measured itself at those stops is also 3.1 degrees." },
  { value: "99.999%", title: "NASA's own slope map", text: "agreement with the LOLA slope map on which cells are steeper than 20 degrees, over 10.2 million cells on the Moon site." },
  { value: "Same", title: "A second solver", text: "A separate shortest-path solver, run on all 1.56 million squares, gives the same costs and the same stop order." },
  { value: "-2569.91 m", title: "Height", text: "is our height at the landing site. The rover's own position file says -2569.91 m." },
  { value: "8.2 km", title: "Radio horizon", text: "is where radio over flat ground ends for a 3 m mast and a 2 m suit antenna, the distance the horizon formula gives." },
  { value: "21.5%", title: "Why not the sharper map", text: "of the spots steeper than 20 degrees are missed by the sharper 50 cm height map made by a neural network (MADNet). So safety uses only the measured one." },
];

export const LIMITS = [
  "A rover is not a person. The rover check proves the slope numbers, not the 20 degree limit itself. That limit is an input you can change.",
  "The radio check is straight line only. Real radio does a little better.",
  "The geologic map is 1:75,000, so the borders between ground types can be tens of meters off.",
  "Oxygen is used at a steady rate per hour. Uphill and downhill slow you down the same.",
  "Rocks smaller than 4 m only show up as roughness.",
  "Mineral pixels are 36 m, so a science stop is a patch, not an exact rock.",
  "Weather and haze are typical values for a season, not a forecast. The haze data is marked preliminary by its author.",
];

export const DATA = [
  ["Height map", "Mars 2020 Terrain Relative Navigation HiRISE DTM mosaic, 1 m. Fergason et al. 2020, USGS. doi:10.5066/P9REJ9JN"],
  ["Photo", "Mars 2020 Terrain Relative Navigation HiRISE orthorectified image mosaic. Fergason et al. 2020, USGS. doi:10.5066/P9QJDP48. Image data: NASA/JPL/University of Arizona"],
  ["Ground types", "Geologic map of Jezero crater and the Nili Planum region. Sun and Stack 2020, USGS SIM 3464"],
  ["Rover track", "Perseverance traverse and waypoints, NASA/JPL-Caltech"],
  ["Minerals", "CRISM mineral map of Jezero. Parente et al. 2021, Zenodo. doi:10.5281/zenodo.5575824, CC BY 4.0"],
  ["Weather", "Perseverance MEDA weather station, Rodriguez-Manfredi et al., NASA Planetary Data System"],
  ["Sky haze", "Mastcam-Z visible aerosol optical depth record. Lemmon 2026, Mendeley Data. doi:10.17632/gktjp9jptb.2, CC BY 4.0"],
  ["Radiation", "Hassler et al. 2014, Science 343 (Curiosity RAD). Zhang et al. 2020, Science Advances 6 (Chang'E-4 LND)"],
  ["Sun position", "Allison and McEwen 2000, Planetary and Space Science 48"],
  ["Moon site", "LOLA 5 m south pole landing site maps, Barker et al. 2021, NASA Goddard"],
];
