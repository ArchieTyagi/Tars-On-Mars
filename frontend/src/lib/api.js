// Talks to the python server. Every address and field used here is listed in docs/API.md.

export class ApiError extends Error {}

// The server writes its error text for the person using the app, so it is shown as it is.
export function detailText(body, status) {
  const d = body && body.detail;
  if (typeof d === "string" && d) return d;
  if (Array.isArray(d)) {
    const parts = d.map((x) => (typeof x === "string" ? x : x && x.msg)).filter(Boolean);
    if (parts.length) return parts.join(" ");
  }
  if (status === 404) return "The server does not have that.";
  return "The server could not answer. Check that it is running.";
}

export function query(params) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== null && v !== undefined && v !== "") q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function call(url, init) {
  let r;
  try {
    r = await fetch(url, init);
  } catch (e) {
    if (e && e.name === "AbortError") throw e;
    throw new ApiError("Cannot reach the server. Is it running?");
  }
  let body = null;
  try {
    body = await r.json();
  } catch {
    body = null;
  }
  if (!r.ok) throw new ApiError(detailText(body, r.status));
  if (body === null) throw new ApiError("The server sent an answer the app cannot read.");
  return body;
}

export const getJson = (path, params, signal) => call(path + query(params), { signal });

export const postJson = (path, body, signal) =>
  call(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });

// ---- mission settings ------------------------------------------------------

// Starting values come from the server's own rules, so the app never invents a default.
export function missionFromRules(rules) {
  return {
    slopeLimit: null, // null = limits by ground type
    o2Hours: rules.o2_hours,
    reservePct: Math.round(rules.o2_reserve * 100),
    speed: rules.walk_speed_kmh,
    stopMinutes: rules.stop_minutes,
    baseAntenna: rules.base_antenna_m,
    suitAntenna: rules.suit_antenna_m,
    useSun: false,
    ls: 120,
    startLtst: 9,
  };
}

const isNum = (x) => typeof x === "number" && Number.isFinite(x);

// Same limits as the server (api/main.py, PlanIn). Returns a list of problems, empty when all is fine.
export function missionProblems(m) {
  const out = [];
  if (m.slopeLimit !== null && !(isNum(m.slopeLimit) && m.slopeLimit >= 5 && m.slopeLimit <= 35)) out.push("Slope limit must be 5 to 35 degrees.");
  if (!(isNum(m.o2Hours) && m.o2Hours > 0 && m.o2Hours <= 24)) out.push("Oxygen supply must be above 0 and at most 24 hours.");
  if (!(isNum(m.reservePct) && m.reservePct >= 0 && m.reservePct < 100)) out.push("Reserve must be 0 to 99 percent.");
  if (!(isNum(m.speed) && m.speed > 0 && m.speed <= 10)) out.push("Walking speed must be above 0 and at most 10 km/h.");
  if (!(isNum(m.stopMinutes) && m.stopMinutes >= 0 && m.stopMinutes <= 480)) out.push("Time at each stop must be 0 to 480 minutes.");
  if (!(isNum(m.baseAntenna) && m.baseAntenna >= 0 && m.baseAntenna <= 100)) out.push("Base antenna must be 0 to 100 m high.");
  if (!(isNum(m.suitAntenna) && m.suitAntenna >= 0 && m.suitAntenna <= 10)) out.push("Suit antenna must be 0 to 10 m high.");
  if (m.useSun) {
    if (!(isNum(m.ls) && m.ls >= 0 && m.ls < 360)) out.push("Season (Ls) must be 0 to 359.9 degrees.");
    if (!(isNum(m.startLtst) && m.startLtst >= 0 && m.startLtst < 24)) out.push("Start time must be 0 to 23.9 hours.");
  }
  return out;
}

// Mission settings under the names the server uses.
export function missionParams(m) {
  return {
    slope_limit: m.slopeLimit,
    o2_hours: m.o2Hours,
    o2_reserve: m.reservePct / 100,
    walk_speed_kmh: m.speed,
    stop_minutes: m.stopMinutes,
    base_antenna_m: m.baseAntenna,
    suit_antenna_m: m.suitAntenna,
  };
}

// The JSON for POST /api/plan. The sun is only sent when the site has a sun model and the user switched it on.
export function planBody({ siteId, base, stops, mission, observations = [], sunCheck = false }) {
  const body = { site: siteId, base, stops, ...missionParams(mission) };
  if (observations.length) body.observations = observations;
  if (sunCheck && mission.useSun) {
    body.ls = mission.ls;
    body.start_ltst_h = mission.startLtst;
  }
  return body;
}

// Address of one map layer. Layers that depend on the base return null until a base is set.
// Only the settings a layer lists under "options" are added, so the address stays cacheable.
export function layerUrl(layer, base, mission) {
  if (layer.needs_base && !base) return null;
  const extra = {};
  if (layer.needs_base) {
    extra.lon = base[0];
    extra.lat = base[1];
  }
  if (mission && layer.options) {
    const all = missionParams(mission);
    for (const k of layer.options) if (k in all) extra[k] = all[k];
  }
  const q = query(extra);
  if (!q) return layer.url;
  return layer.url + (layer.url.includes("?") ? "&" + q.slice(1) : q);
}
