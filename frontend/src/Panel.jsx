import { useState } from "react";

const fmt = ([lon, lat]) => `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`;

export default function Panel({
  site, error, base, stops, maxStops, showZones,
  onToggleZones, onUseLandingSite, onRemoveStop, onClear, onGoTo, children,
}) {
  const [q, setQ] = useState("");
  const [qErr, setQErr] = useState("");

  function goTo(e) {
    e.preventDefault();
    // accepts "18.4447, 77.4508" (lat, lon) or with N / E
    const n = q.match(/-?\d+(\.\d+)?/g);
    if (!n || n.length < 2) return setQErr("Type lat, lon like 18.4447, 77.4508");
    const lat = parseFloat(n[0]), lon = parseFloat(n[1]);
    const b = site?.bounds;
    if (b && (lon < b.west || lon > b.east || lat < b.south || lat > b.north)) {
      return setQErr(`Outside the map. Lat ${b.south.toFixed(3)} to ${b.north.toFixed(3)}, lon ${b.west.toFixed(3)} to ${b.east.toFixed(3)}`);
    }
    setQErr("");
    onGoTo([lon, lat]);
  }

  const hint = !base
    ? "Click the map to set your base."
    : stops.length < maxStops
      ? `Click the map to add stops (${stops.length}/${maxStops}).`
      : "Max stops reached.";

  return (
    <aside className="panel">
      <header>
        <h1>TARS on Mars</h1>
        <p className="sub">Plan a Mars walk: route, time, oxygen.</p>
      </header>

      {error && <p className="error">{error}</p>}
      {site && <p className="muted">{site.name} · 1 m NASA/USGS height map · {site.grid_m} m grid</p>}

      <form className="search" onSubmit={goTo}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Go to: 18.4447, 77.4508" />
        <button type="submit">Go</button>
      </form>
      {qErr && <p className="error small">{qErr}</p>}

      <section>
        <h2>Base</h2>
        {base ? <p className="row"><span className="dot base" /> {fmt(base)}</p> : <p className="muted">not set</p>}
        {!base && <button onClick={onUseLandingSite} disabled={!site}>Use Perseverance landing site</button>}
      </section>

      <section>
        <h2>Stops</h2>
        {stops.length === 0 && <p className="muted">none yet</p>}
        <ol>
          {stops.map((s, i) => (
            <li key={i} className="row">
              <span className="dot stop">{i + 1}</span> {fmt(s)}
              <button className="x" onClick={() => onRemoveStop(i)} aria-label="remove stop">×</button>
            </li>
          ))}
        </ol>
        <p className="hint">{hint}</p>
      </section>

      <section>
        <h2>Map layers</h2>
        <label className="row"><input type="checkbox" checked={showZones} onChange={onToggleZones} /> Show GO / CAUTION / NO-GO</label>
        <div className="legend">
          <span><i className="sw go" /> GO</span>
          <span><i className="sw caution" /> CAUTION</span>
          <span><i className="sw nogo" /> NO-GO</span>
        </div>
      </section>

      {children}

      <footer>
        <button className="ghost" onClick={onClear}>Clear all</button>
      </footer>
    </aside>
  );
}
