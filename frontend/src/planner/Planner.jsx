import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import { getJson, layerUrl, missionFromRules, missionParams, missionProblems, planBody, postJson } from "../lib/api.js";
import { makeGeo } from "../lib/geo.js";
import { KEY_STYLE, availableModes } from "../lib/route.js";
import Controls from "./Controls.jsx";
import MapView from "./MapView.jsx";
import Results from "./Results.jsx";
import "../styles/planner.css";

// three.js is only downloaded when someone opens the 3D walk
const Walk3D = lazy(() => import("./Walk3D.jsx"));

const MAX_STOPS = 6;
const convert = (siteId, params) => getJson("/api/convert", { site: siteId, ...params });
const near = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]) < 1; // closer than 1 m = the same click

function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export default function Planner({ onHome }) {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("jezero");
  const [site, setSite] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [retry, setRetry] = useState(0);
  const [mission, setMission] = useState(null);
  const [base, setBase] = useState(null); // { lonlat: [lon, lat], xy: [x, y] in map meters }
  const [stops, setStops] = useState([]);
  const [plan, setPlan] = useState(null);
  const [planError, setPlanError] = useState("");
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState(false);
  const [notice, setNotice] = useState("");
  const [baseLayerId, setBaseLayerId] = useState(null);
  const [overlayIds, setOverlayIds] = useState([]);
  const [routeMode, setRouteMode] = useState("margin");
  const [view, setView] = useState("2d");
  const [observations, setObservations] = useState([]);
  const [science, setScience] = useState(null);
  const [scienceBusy, setScienceBusy] = useState(false);
  const [scienceError, setScienceError] = useState("");
  const [showRover, setShowRover] = useState(false);
  const [rover, setRover] = useState(null);
  const [roverError, setRoverError] = useState("");
  const [cursor, setCursor] = useState(null);
  const [flyTo, setFlyTo] = useState(null);

  const reqId = useRef(0);
  const sciId = useRef(0);
  const latest = useRef({});
  latest.current = { siteId, site, base, stops, mission, observations, plan, planError };

  const geo = useMemo(() => (site ? makeGeo(site, convert) : null), [site]);
  const problems = useMemo(() => (mission ? missionProblems(mission) : []), [mission]);
  const ready = Boolean(site && base && stops.length > 0 && problems.length === 0);

  // ---- loading a site --------------------------------------------------------

  useEffect(() => {
    getJson("/api/sites").then(setSites).catch(() => setSites([]));
  }, []);

  function dropPlan() {
    reqId.current++;
    setPlan(null);
    setPlanError("");
    setBusy(false);
    setStale(false);
    setObservations([]);
    setCursor(null);
  }
  function dropScience() {
    sciId.current++;
    setScience(null);
    setScienceBusy(false);
    setScienceError("");
  }

  useEffect(() => {
    let dead = false;
    setSite(null);
    setMission(null);
    setLoadError("");
    setBase(null);
    setStops([]);
    setNotice("");
    setShowRover(false);
    setRover(null);
    setRoverError("");
    setFlyTo(null);
    dropPlan();
    dropScience();
    getJson("/api/site", { site: siteId })
      .then((s) => {
        if (dead) return;
        setSite(s);
        setMission(missionFromRules(s.rules));
        const firstBase = s.layers.find((l) => l.kind === "base");
        setBaseLayerId(firstBase ? firstBase.id : null);
        setOverlayIds(s.layers.some((l) => l.id === "zones") ? ["zones"] : []);
      })
      .catch((e) => {
        if (!dead) setLoadError(e.message);
      });
    return () => {
      dead = true;
    };
  }, [siteId, retry]);

  // ---- base and stops --------------------------------------------------------

  function putBase(point) {
    setBase(point);
    dropPlan();
    dropScience();
  }
  function putStops(next) {
    setStops(next);
    dropPlan();
  }

  async function pick(xy) {
    const at = latest.current;
    if (!geo || !at.site) return;
    if (!geo.inside(xy)) {
      setNotice(at.site.context && at.site.context.length
        ? "That spot is not mapped for walking yet. Pick a point inside the outlined box."
        : "That spot is outside the map data. Pick a point on the terrain.");
      return;
    }
    let lonlat;
    try {
      lonlat = await geo.toLonLat(xy);
    } catch (e) {
      setNotice(e.message);
      return;
    }
    const now = latest.current;
    if (now.siteId !== at.siteId) return; // the site changed while we waited
    const point = { lonlat, xy };
    if (!now.base) {
      setNotice("");
      putBase(point);
      return;
    }
    if (near(now.base.xy, xy) || now.stops.some((s) => near(s.xy, xy))) return; // double click on the same spot
    if (now.stops.length >= MAX_STOPS) {
      setNotice(`${MAX_STOPS} stops is the most one walk can have. Remove one to add another.`);
      return;
    }
    setNotice("");
    putStops([...now.stops, point]);
  }

  async function useDefaultBase() {
    if (!site || !geo) return;
    const at = siteId;
    try {
      const xy = await geo.toXY(site.default_base);
      if (latest.current.siteId !== at) return;
      setNotice("");
      putBase({ lonlat: site.default_base, xy });
    } catch (e) {
      setNotice(e.message);
    }
  }

  async function goTo(lonlat) {
    if (!geo) return "The map is not loaded yet.";
    try {
      const xy = await geo.toXY(lonlat);
      if (!geo.inside(xy)) return "That position is outside this map.";
      setView("2d");
      setFlyTo({ xy, n: Date.now() });
      return "";
    } catch (e) {
      return e.message;
    }
  }

  function clearAll() {
    setBase(null);
    setStops([]);
    setNotice("");
    dropPlan();
    dropScience();
  }

  // ---- planning --------------------------------------------------------------

  async function runPlan(override = {}) {
    const now = { ...latest.current, ...override };
    if (!now.site || !now.base || now.stops.length === 0 || missionProblems(now.mission).length) return;
    const id = ++reqId.current;
    setBusy(true);
    setPlanError("");
    try {
      const p = await postJson(
        "/api/plan",
        planBody({
          siteId: now.siteId,
          base: now.base.lonlat,
          stops: now.stops.map((s) => s.lonlat),
          mission: now.mission,
          observations: now.observations,
          sunCheck: now.site.sun_check,
        })
      );
      if (id !== reqId.current) return;
      setPlan(p);
      setStale(false);
      setCursor(null);
      setRouteMode((m) => (availableModes(p).some((x) => x.id === m) ? m : "margin"));
    } catch (e) {
      if (id !== reqId.current) return;
      setPlan(null);
      setStale(false);
      setCursor(null);
      setPlanError(e.message);
    } finally {
      if (id === reqId.current) setBusy(false);
    }
  }

  // a change of mission settings re-plans by itself when a result is already on screen
  const firstMission = useRef(true);
  useEffect(() => {
    if (!mission) {
      firstMission.current = true;
      return;
    }
    if (firstMission.current) {
      firstMission.current = false;
      return;
    }
    dropScience();
    const at = latest.current;
    if (at.plan === null && at.planError === "") return;
    setStale(true);
    const t = setTimeout(() => runPlan(), 450);
    return () => clearTimeout(t);
  }, [mission]);

  function report(target, finding) {
    const rest = observations.filter((o) => !(o.lonlat[0] === target.lonlat[0] && o.lonlat[1] === target.lonlat[1]));
    const next = [...rest, { lonlat: target.lonlat, finding, radius_m: 20 }];
    setObservations(next);
    setStale(true);
    runPlan({ observations: next });
  }
  function removeReport(i) {
    const next = observations.filter((_, j) => j !== i);
    setObservations(next);
    setStale(true);
    runPlan({ observations: next });
  }

  // ---- science stops and the rover track ---------------------------------------

  async function suggestScience() {
    if (!site || !base || !geo || problems.length) return;
    const id = ++sciId.current;
    setScienceBusy(true);
    setScienceError("");
    try {
      const m = missionParams(mission);
      const r = await getJson("/api/science_stops", {
        site: siteId, lon: base.lonlat[0], lat: base.lonlat[1], slope_limit: m.slope_limit, o2_hours: m.o2_hours,
        o2_reserve: m.o2_reserve, walk_speed_kmh: m.walk_speed_kmh, stop_minutes: m.stop_minutes,
      });
      const withXy = await Promise.all(r.stops.map(async (s) => ({ ...s, xy: await geo.toXY(s.lonlat) })));
      if (id !== sciId.current) return;
      setScience({ ...r, stops: withXy });
    } catch (e) {
      if (id !== sciId.current) return;
      setScienceError(e.message);
    } finally {
      if (id === sciId.current) setScienceBusy(false);
    }
  }

  function addScienceStop(s) {
    if (stops.length >= MAX_STOPS || stops.some((p) => near(p.xy, s.xy))) return;
    putStops([...stops, { lonlat: s.lonlat, xy: s.xy }]);
  }

  useEffect(() => {
    if (!showRover || rover || !site || !site.has_rover_track) return;
    let dead = false;
    setRoverError("");
    getJson("/api/rover", { site: siteId })
      .then((r) => {
        if (!dead) setRover(r);
      })
      .catch((e) => {
        if (!dead) {
          setRoverError(e.message);
          setShowRover(false);
        }
      });
    return () => {
      dead = true;
    };
  }, [showRover, rover, site, siteId]);

  // ---- layers -----------------------------------------------------------------

  const layerMission = useDebounced(mission, 350);
  const baseLayer = site ? site.layers.find((l) => l.id === baseLayerId) : null;
  const overlays = useMemo(() => {
    if (!site || !layerMission) return [];
    return site.layers
      .filter((l) => l.kind === "overlay" && overlayIds.includes(l.id))
      .map((l) => ({ id: l.id, name: l.name, url: layerUrl(l, base ? base.lonlat : null, layerMission) }))
      .filter((l) => l.url);
  }, [site, overlayIds, base, layerMission]);
  const zonesOn = overlays.find((l) => l.id === "zones");

  const modes = plan ? availableModes(plan) : [];
  const mode = modes.find((m) => m.id === routeMode) || modes[0];

  const home = (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    onHome();
  };

  return (
    <div className="planner">
      <header className="ptop">
        <a className="wordmark" href="/" onClick={home}>
          <span className="mark" aria-hidden="true" />
          TARS on Mars
        </a>
        <span className="label ptop-title">Route planner</span>
        {sites.length > 1 && (
          <div className="seg" role="group" aria-label="Site">
            {sites.map((s) => (
              <button key={s.id} className={s.id === siteId ? "on" : ""} aria-pressed={s.id === siteId} onClick={() => setSiteId(s.id)}>
                {s.body === "moon" ? "Moon" : "Mars"}: {s.id === "moon" ? "south pole" : s.name}
              </button>
            ))}
          </div>
        )}
        <div className="seg" role="group" aria-label="View">
          <button className={view === "2d" ? "on" : ""} aria-pressed={view === "2d"} onClick={() => setView("2d")}>2D map</button>
          <button className={view === "3d" ? "on" : ""} aria-pressed={view === "3d"} onClick={() => setView("3d")}>3D walk</button>
        </div>
      </header>

      <Controls
        site={site} mission={mission} setMission={setMission} problems={problems}
        base={base} stops={stops} maxStops={MAX_STOPS}
        onUseDefaultBase={useDefaultBase} onRemoveStop={(i) => putStops(stops.filter((_, j) => j !== i))}
        onRemoveBase={() => putBase(null)} onClear={clearAll} onGoTo={goTo}
        baseLayerId={baseLayerId} setBaseLayerId={setBaseLayerId} overlayIds={overlayIds} setOverlayIds={setOverlayIds}
        showRover={showRover} setShowRover={setShowRover} rover={rover} roverError={roverError}
        science={science} scienceBusy={scienceBusy} scienceError={scienceError}
        onSuggestScience={suggestScience} onAddScience={addScienceStop}
        ready={ready} busy={busy} onPlan={() => runPlan()}
      />

      <main className="stage">
        {!site && !loadError && <div className="stage-msg"><p className="label">Loading the map</p></div>}
        {loadError && (
          <div className="stage-msg">
            <p className="label">No connection to the server</p>
            <p>{loadError}</p>
            <button className="btn small" onClick={() => setRetry((n) => n + 1)}>Try again</button>
          </div>
        )}
        {site && geo && view === "2d" && (
          <MapView
            site={site} geo={geo} base={base} stops={stops} plan={plan} routeMode={mode ? mode.id : "margin"}
            baseUrl={baseLayer ? layerUrl(baseLayer, null, null) : null} overlays={overlays}
            rover={showRover ? rover : null} science={science} cursor={cursor} flyTo={flyTo}
            onPick={pick} onLayerError={(name) => setNotice(`The layer "${name}" could not be loaded.`)}
          />
        )}
        {site && geo && view === "3d" && (
          <Suspense fallback={<div className="stage-msg"><p className="label">Loading the 3D view</p></div>}>
            <Walk3D
              site={site} geo={geo} base={base} stops={stops} plan={plan} routeMode={mode ? mode.id : "margin"}
              textureUrl={baseLayer ? layerUrl(baseLayer, null, null) : null} zonesUrl={zonesOn ? zonesOn.url : null}
            />
          </Suspense>
        )}
        {site && plan && mode && (
          <div className="routekey">
            <div className="seg small" role="group" aria-label="Color the route by">
              {modes.map((m) => (
                <button key={m.id} className={m.id === mode.id ? "on" : ""} aria-pressed={m.id === mode.id} onClick={() => setRouteMode(m.id)}>{m.name}</button>
              ))}
            </div>
            <ul className="keylist">
              {mode.keys.map((k) => (
                <li key={k}><i style={{ background: KEY_STYLE[k].color }} />{KEY_STYLE[k].label}</li>
              ))}
            </ul>
          </div>
        )}
        {notice && (
          <div className="toast" role="status">
            <span>{notice}</span>
            <button aria-label="Close message" onClick={() => setNotice("")}>×</button>
          </div>
        )}
      </main>

      <Results
        site={site} plan={plan} planError={planError} busy={busy} stale={stale} problems={problems}
        base={base} stops={stops} cursor={cursor} setCursor={setCursor}
        observations={observations} onReport={report} onRemoveReport={removeReport}
      />
    </div>
  );
}
