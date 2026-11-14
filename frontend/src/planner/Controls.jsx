import { useState } from "react";
import { getJson } from "../lib/api.js";
import { hm, lonlatText, parseLatLon, pct, seasonName } from "../lib/format.js";

function Block({ n, title, children, aside }) {
  return (
    <section className="block">
      <header className="block-head">
        <span className="label">{n}</span>
        <h2>{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  );
}

function Num({ label, unit, value, onChange, min, max, step }) {
  return (
    <label className="field">
      <span>{label}</span>
      <span className="field-in">
        <input
          type="number" inputMode="decimal" value={value} min={min} max={max} step={step}
          onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
        />
        <i>{unit}</i>
      </span>
    </label>
  );
}

function Legend({ items }) {
  if (!items || !items.length) return null;
  return (
    <ul className="keylist col">
      {items.map((x) => (
        <li key={x.color + x.label}><i style={{ background: x.color }} />{x.label}</li>
      ))}
    </ul>
  );
}

export default function Controls(props) {
  const {
    site, mission, setMission, problems, base, stops, maxStops, onUseDefaultBase, onRemoveStop, onRemoveBase, onClear, onGoTo,
    baseLayerId, setBaseLayerId, overlayIds, setOverlayIds, showRover, setShowRover, rover, roverError,
    science, scienceBusy, scienceError, onSuggestScience, onAddScience, ready, busy, onPlan,
  } = props;
  const [q, setQ] = useState("");
  const [qErr, setQErr] = useState("");
  const [sol, setSol] = useState("");
  const [solMsg, setSolMsg] = useState("");

  if (!site || !mission) {
    return <aside className="side left"><p className="label pad">Loading</p></aside>;
  }

  const set = (k) => (v) => setMission({ ...mission, [k]: v });
  // start time as whole hours and minutes in steps of five
  const startTotal = typeof mission.startLtst === "number" ? Math.round(mission.startLtst * 12) * 5 : 9 * 60;
  const startH = Math.floor(startTotal / 60) % 24;
  const startM = startTotal % 60;
  const limits = site.rules.slope_limit_deg;
  const usable = typeof mission.o2Hours === "number" && typeof mission.reservePct === "number"
    ? mission.o2Hours * (1 - mission.reservePct / 100) : null;

  async function search(e) {
    e.preventDefault();
    const lonlat = parseLatLon(q);
    if (!lonlat) return setQErr("Type latitude, longitude. For example 18.4447, 77.4508");
    setQErr(await onGoTo(lonlat));
  }

  async function fromSol(e) {
    e.preventDefault();
    const n = Number(sol);
    if (sol === "" || !Number.isFinite(n) || n < 0 || n > 100000) return setSolMsg("Type a mission day from 0 to 100000.");
    try {
      const r = await getJson("/api/sol_to_ls", { sol: n });
      setMission({ ...mission, ls: Math.round(r.ls * 10) / 10 });
      setSolMsg(`Sol ${n} is Ls ${r.ls.toFixed(1)}.`);
    } catch (err) {
      setSolMsg(err.message);
    }
  }

  const toggleOverlay = (id) =>
    setOverlayIds(overlayIds.includes(id) ? overlayIds.filter((x) => x !== id) : [...overlayIds, id]);

  const hint = !base
    ? "Click the map to set your base."
    : stops.length === 0
      ? "Now click the map to add a stop."
      : stops.length < maxStops
        ? `Click the map to add more stops (${stops.length} of ${maxStops}).`
        : `${maxStops} of ${maxStops} stops. Remove one to add another.`;

  const bases = site.layers.filter((l) => l.kind === "base");
  const overlays = site.layers.filter((l) => l.kind === "overlay");
  const track = rover ? rover.our_map_on_the_track : null;

  return (
    <aside className="side left">
      <div className="side-scroll">
        <div className="sitecard">
          <p className="label">{site.body === "moon" ? "The Moon" : "Mars"}</p>
          <h1>{site.name}</h1>
          <p className="fine">{(site.shape[1] * site.grid_m / 1000).toFixed(0)} x {(site.shape[0] * site.grid_m / 1000).toFixed(0)} km, {site.grid_m} m grid. {site.source}</p>
        </div>

        <Block n="01" title="Base and stops" aside={(base || stops.length > 0) && <button className="linkbtn" onClick={onClear}>Clear</button>}>
          <ol className="points">
            <li>
              <span className="mk base">B</span>
              {base ? <span className="mono">{lonlatText(base.lonlat)}</span> : <span className="dim">Base not set</span>}
              {base && <button className="x" aria-label="Remove the base" onClick={onRemoveBase}>×</button>}
            </li>
            {stops.map((s, i) => (
              <li key={i}>
                <span className="mk stop">{i + 1}</span>
                <span className="mono">{lonlatText(s.lonlat)}</span>
                <button className="x" aria-label={`Remove stop ${i + 1}`} onClick={() => onRemoveStop(i)}>×</button>
              </li>
            ))}
          </ol>
          <p className="hint">{hint}</p>
          {!base && (
            <button className="btn ghost small wide" onClick={onUseDefaultBase}>
              {site.has_rover_track ? "Use the Perseverance landing site" : "Use the suggested base"}
            </button>
          )}
          <form className="search" onSubmit={search}>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Go to latitude, longitude" aria-label="Go to latitude, longitude" />
            <button className="btn ghost small" type="submit">Go</button>
          </form>
          {qErr && <p className="err">{qErr}</p>}

          {site.has_minerals && (
            <div className="science">
              <button className="btn ghost small wide" disabled={!base || scienceBusy || problems.length > 0} onClick={onSuggestScience}>
                {scienceBusy ? "Looking for mineral patches" : "Suggest science stops"}
              </button>
              {!base && <p className="hint">Set a base first. The suggestions depend on where you start.</p>}
              {scienceError && <p className="err">{scienceError}</p>}
              {science && science.stops.length === 0 && <p className="hint">No mineral patch can be reached and returned from on this oxygen.</p>}
              {science && science.stops.length > 0 && (
                <>
                  <ul className="scilist">
                    {science.stops.map((s, i) => {
                      const added = stops.some((p) => Math.hypot(p.xy[0] - s.xy[0], p.xy[1] - s.xy[1]) < 1);
                      return (
                        <li key={i}>
                          <div>
                            <strong>{s.mineral}</strong>
                            <span className="fine">{s.why}. About {hm(s.round_trip_h)} there and back.</span>
                          </div>
                          <button className="btn ghost small" disabled={added || stops.length >= maxStops} onClick={() => onAddScience(s)}>
                            {added ? "Added" : "Add"}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                  <p className="fine">{science.note}</p>
                  <p className="fine">{science.caveat} Source: {science.source}</p>
                </>
              )}
            </div>
          )}
        </Block>

        <Block n="02" title="Mission">
          <Num label="Suit oxygen supply" unit="h" value={mission.o2Hours} onChange={set("o2Hours")} min="0.5" max="24" step="0.5" />
          <Num label="Kept in reserve" unit="%" value={mission.reservePct} onChange={set("reservePct")} min="0" max="99" step="5" />
          <Num label="Walking speed on flat ground" unit="km/h" value={mission.speed} onChange={set("speed")} min="0.5" max="10" step="0.1" />
          <Num label="Work time at each stop" unit="min" value={mission.stopMinutes} onChange={set("stopMinutes")} min="0" max="480" step="5" />
          <p className="hint">
            {usable !== null && usable > 0 ? `Usable oxygen: ${hm(usable)}. ` : ""}
            These are your inputs. The starting values are placeholders, set them for your suit and crew.
          </p>

          <div className="sub">
            <label className="check">
              <input type="checkbox" checked={mission.slopeLimit !== null} onChange={(e) => set("slopeLimit")(e.target.checked ? limits.default : null)} />
              <span>Set my own slope limit</span>
            </label>
            {mission.slopeLimit === null ? (
              <p className="hint">
                {site.has_ground_types
                  ? `Limits by ground type: sand ${limits.sand} deg, delta fan ${limits.regolith} deg, rock ${limits.bedrock} deg.`
                  : `Slope limit: ${limits.default} deg everywhere.`}
              </p>
            ) : (
              <>
                <label className="range">
                  <span>{mission.slopeLimit} deg on firm ground</span>
                  <input type="range" min="5" max="35" step="1" value={mission.slopeLimit} onChange={(e) => set("slopeLimit")(Number(e.target.value))} />
                </label>
                {site.has_ground_types && <p className="hint">Looser ground scales with it. At 30 deg on rock, sand is 15 deg.</p>}
              </>
            )}
          </div>

          <div className="sub">
            <p className="label">Radio antennas</p>
            <Num label="Base antenna height" unit="m" value={mission.baseAntenna} onChange={set("baseAntenna")} min="0" max="100" step="0.5" />
            <Num label="Suit antenna height" unit="m" value={mission.suitAntenna} onChange={set("suitAntenna")} min="0" max="10" step="0.5" />
          </div>

          {site.sun_check ? (
            <div className="sub">
              <label className="check">
                <input type="checkbox" checked={mission.useSun} onChange={(e) => set("useSun")(e.target.checked)} />
                <span>Check the sun, weather and sky</span>
              </label>
              {mission.useSun && (
                <>
                  <Num label="Season (Ls)" unit="deg" value={mission.ls} onChange={set("ls")} min="0" max="359.9" step="1" />
                  <p className="hint">
                    Ls is where Mars is on its way around the sun, 0 to 360 degrees.
                    {seasonName(mission.ls) !== "n/a" ? ` Ls ${mission.ls} is ${seasonName(mission.ls)}.` : ""}
                  </p>
                  <form className="search" onSubmit={fromSol}>
                    <input value={sol} onChange={(e) => setSol(e.target.value)} inputMode="numeric" placeholder="Or a Perseverance mission day (sol)" aria-label="Perseverance mission day, sol" />
                    <button className="btn ghost small" type="submit">Set</button>
                  </form>
                  {solMsg && <p className="hint">{solMsg}</p>}
                  <div className="field">
                    <span id="start-label">Start time on the Mars clock</span>
                    <span className="field-in" role="group" aria-labelledby="start-label">
                      <select aria-label="Start hour" value={startH} onChange={(e) => set("startLtst")(Number(e.target.value) + startM / 60)}>
                        {Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, "0")}</option>)}
                      </select>
                      <b>:</b>
                      <select aria-label="Start minute" value={startM} onChange={(e) => set("startLtst")(startH + Number(e.target.value) / 60)}>
                        {Array.from({ length: 12 }, (_, k) => <option key={k} value={k * 5}>{String(k * 5).padStart(2, "0")}</option>)}
                      </select>
                    </span>
                  </div>
                  <p className="hint">Mars local solar time: 12:00 is when the sun is highest.</p>
                </>
              )}
            </div>
          ) : (
            <p className="hint">The sun, weather and sky checks are built for Mars only.</p>
          )}
          {problems.length > 0 && <ul className="err list">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}
        </Block>

        <Block n="03" title="Map layers">
          <p className="label">Ground picture</p>
          {bases.map((l) => (
            <label key={l.id} className="check">
              <input type="radio" name="baselayer" checked={baseLayerId === l.id} onChange={() => setBaseLayerId(l.id)} />
              <span>{l.name}</span>
            </label>
          ))}
          <p className="label gap">On top</p>
          {overlays.map((l) => {
            const on = overlayIds.includes(l.id);
            const blocked = l.needs_base && !base;
            return (
              <div key={l.id} className="layer">
                <label className="check">
                  <input type="checkbox" checked={on} disabled={blocked} onChange={() => toggleOverlay(l.id)} />
                  <span>{l.name}</span>
                </label>
                {blocked && <p className="hint">Set a base first.</p>}
                {on && !blocked && (
                  <>
                    <p className="fine">{l.about}</p>
                    <Legend items={l.legend} />
                  </>
                )}
              </div>
            );
          })}
          {site.has_rover_track && (
            <div className="layer">
              <label className="check">
                <input type="checkbox" checked={showRover} onChange={(e) => setShowRover(e.target.checked)} />
                <span>Where Perseverance really drove</span>
              </label>
              {roverError && <p className="err">{roverError}</p>}
              {showRover && rover && (
                <>
                  <p className="fine">
                    {rover.km_on_map} km inside this map, sols {rover.sols[0]} to {rover.sols[1]}. Our map calls {pct(track.go, 1)} of
                    the {track.squares.toLocaleString("en-US")} squares it crossed GO, {pct(track.caution, 1)} CAUTION and {pct(track.nogo, 1)} NO-GO.
                  </p>
                  <p className="fine">{rover.note}</p>
                  <ul className="keylist col"><li><i style={{ background: "#39d0d8" }} />rover path and stops</li></ul>
                </>
              )}
            </div>
          )}
        </Block>
      </div>

      <div className="side-foot">
        <button className="btn wide" disabled={!ready || busy} onClick={onPlan}>{busy ? "Planning" : "Plan the walk"}</button>
        {!ready && <p className="hint">{problems.length ? "Fix the mission settings above." : "Set a base and at least one stop."}</p>}
      </div>
    </aside>
  );
}
