// Turning a plan from the server into things to draw. No drawing library in here, so it can be tested.

// What each stretch of the route can be colored by, and what the colors mean.
export const KEY_STYLE = {
  ok: { color: "#f1f0ea", label: "1 h or more to spare" },
  tight: { color: "#f5a623", label: "under 1 h to spare" },
  over: { color: "#ff3b30", label: "past the point of no return" },
  contact: { color: "#f1f0ea", label: "direct radio to base" },
  blackout: { color: "#b085ff", label: "no direct radio" },
  lit: { color: "#f1f0ea", label: "sun is up" },
  dark: { color: "#5b7cff", label: "sun is down" },
  s0: { color: "#1a9850", label: "0 to 5 deg" },
  s1: { color: "#91cf60", label: "5 to 10 deg" },
  s2: { color: "#fee08b", label: "10 to 15 deg" },
  s3: { color: "#fc8d59", label: "15 to 20 deg" },
  s4: { color: "#d73027", label: "20 to 25 deg" },
  s5: { color: "#7f0000", label: "25 deg and steeper" },
  nodata: { color: "#8a8a86", label: "no number here" },
};

export const ROUTE_MODES = [
  { id: "margin", name: "Oxygen", keys: ["ok", "tight", "over"] },
  { id: "radio", name: "Radio", keys: ["contact", "blackout"] },
  { id: "slope", name: "Slope", keys: ["s0", "s1", "s2", "s3", "s4", "s5"] },
  { id: "light", name: "Daylight", keys: ["lit", "dark"] },
];

// Oxygen margin = spare usable oxygen if you turned around right here and walked straight home.
export function band(marginH) {
  if (typeof marginH !== "number" || !Number.isFinite(marginH)) return "nodata";
  if (marginH < 0) return "over";
  if (marginH < 1) return "tight";
  return "ok";
}

export function slopeKey(deg) {
  if (typeof deg !== "number" || !Number.isFinite(deg)) return "nodata";
  return `s${Math.min(5, Math.max(0, Math.floor(deg / 5)))}`;
}

// The daylight coloring only exists when the plan was made with a season and a start time.
export function availableModes(plan) {
  return ROUTE_MODES.filter((m) => m.id !== "light" || (plan && plan.light && Array.isArray(plan.light.dark)));
}

// One key per point of the path.
export function routeKeys(plan, mode) {
  const n = plan.path.length;
  if (mode === "radio") return plan.radio.in_contact.map((c) => (c === true ? "contact" : c === false ? "blackout" : "nodata"));
  if (mode === "slope") return plan.slope_deg.map(slopeKey);
  if (mode === "light" && plan.light && Array.isArray(plan.light.dark)) return plan.light.dark.map((d) => (d ? "dark" : "lit"));
  const keys = plan.margin_h.map(band);
  return keys.length === n ? keys : Array.from({ length: n }, (_, i) => keys[i] ?? "nodata");
}

// Group the path into stretches of one color. Each step between two points takes the key of the point
// it arrives at, so a step that ends past the point of no return is already drawn as past it.
// Neighbouring stretches share their joining point, so the line has no gaps.
export function runs(keys) {
  const out = [];
  if (!keys || keys.length < 2) return out;
  let start = 0;
  let cur = keys[1];
  for (let i = 2; i < keys.length; i++) {
    if (keys[i] !== cur) {
      out.push({ key: cur, start, end: i - 1 });
      start = i - 1;
      cur = keys[i];
    }
  }
  out.push({ key: cur, start, end: keys.length - 1 });
  return out;
}

// Height profile for a small chart: x = distance walked, y = height. Thinned to at most maxPoints,
// always keeping the first and the last point.
export function profile(distM, heightM, width, height, maxPoints = 300) {
  const n = Math.min(distM.length, heightM.length);
  if (n < 2) return { points: [], index: [], min: null, max: null, total: 0 };
  const step = Math.max(1, Math.ceil(n / maxPoints));
  const index = [];
  for (let i = 0; i < n; i += step) index.push(i);
  if (index[index.length - 1] !== n - 1) index.push(n - 1);
  let min = Infinity;
  let max = -Infinity;
  for (let i = 0; i < n; i++) {
    const h = heightM[i];
    if (typeof h === "number" && Number.isFinite(h)) {
      if (h < min) min = h;
      if (h > max) max = h;
    }
  }
  if (!Number.isFinite(min)) return { points: [], index: [], min: null, max: null, total: 0 };
  const total = distM[n - 1] - distM[0];
  const span = max - min;
  const points = index.map((i) => {
    const x = total > 0 ? ((distM[i] - distM[0]) / total) * width : 0;
    const h = typeof heightM[i] === "number" && Number.isFinite(heightM[i]) ? heightM[i] : min;
    const y = span > 0 ? height - ((h - min) / span) * height : height / 2;
    return [x, y];
  });
  return { points, index, min, max, total };
}

// The numbers an astronaut would want at point i of the walk.
export function hudAt(plan, i, lookAheadM = 60) {
  const s = plan.settings;
  const last = plan.path.length - 1;
  const k = Math.min(Math.max(0, i), last);
  const t = plan.elapsed_h[k];
  let steepest = null;
  for (let j = k; j <= last && plan.dist_m[j] - plan.dist_m[k] <= lookAheadM; j++) {
    const d = plan.slope_deg[j];
    if (typeof d === "number" && Number.isFinite(d) && (steepest === null || d > steepest)) steepest = d;
  }
  const supplyLeft = s.o2_hours - t;
  return {
    elapsed: t,
    total: plan.hours,
    home: plan.home_h[k],
    margin: plan.margin_h[k],
    state: band(plan.margin_h[k]),
    supplyLeft,
    supplyShare: Math.max(0, Math.min(1, supplyLeft / s.o2_hours)),
    steepestAhead: steepest,
    height: plan.height_m[k],
    walked: plan.dist_m[k],
    inContact: plan.radio ? plan.radio.in_contact[k] : null,
    dark: plan.light && Array.isArray(plan.light.dark) ? plan.light.dark[k] : null,
  };
}

// Index of the last path point reached by mission time t (hours). elapsed is never decreasing.
export function indexAtTime(elapsed, t) {
  let lo = 0;
  let hi = elapsed.length - 1;
  if (hi < 0) return 0;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (elapsed[mid] <= t) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}
