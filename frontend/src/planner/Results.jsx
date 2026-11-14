import { clock, hm, pct, sentence } from "../lib/format.js";
import Profile from "./Profile.jsx";

function Part({ n, title, children }) {
  return (
    <section className="block">
      <header className="block-head">
        <span className="label">{n}</span>
        <h2>{title}</h2>
      </header>
      {children}
    </section>
  );
}

function Rows({ items }) {
  return (
    <dl className="rows">
      {items.filter(Boolean).map(([k, v]) => (
        <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
      ))}
    </dl>
  );
}

const who = (n) => (n === 0 ? "Base" : String(n));

export default function Results({ site, plan, planError, busy, stale, problems, base, stops, cursor, setCursor, observations, onReport, onRemoveReport }) {
  if (!plan) {
    return (
      <aside className="side right">
        <div className="side-scroll">
          {planError ? (
            <div className="verdict bad" role="alert">
              <p className="label">The planner says no</p>
              <strong>No route</strong>
              <p>{planError}</p>
            </div>
          ) : (
            <div className="empty">
              <p className="label">{busy ? "Planning" : "Result"}</p>
              <h2>{busy ? "Working out the walk." : "No walk planned yet."}</h2>
              <ol className="steps">
                <li className={base ? "done" : ""}><span className="label">01</span>Click the map to set your base.</li>
                <li className={stops.length ? "done" : ""}><span className="label">02</span>Click again to add up to six stops.</li>
                <li><span className="label">03</span>Set your oxygen and speed, then press Plan the walk.</li>
              </ol>
              <p className="fine">
                You get the safest loop, the time, whether it fits your oxygen, the point of no return, radio blackouts,
                the radiation dose and, on Mars, the sun, weather and sky for your season and start time.
              </p>
            </div>
          )}
        </div>
      </aside>
    );
  }

  const s = plan.settings;
  const el = plan.elevation;
  const light = plan.light;
  const weather = plan.weather;
  const radio = plan.radio;
  const rad = plan.radiation;
  const scout = plan.scout;
  const ponr = plan.point_of_no_return;
  const minerals = new Map((plan.stop_minerals || []).map((m) => [m.stop, m]));
  const flags = light
    ? [
        light.starts_in_dark && "You set off in the dark.",
        light.sunset_before_home && "The sun sets before you are back at base.",
        light.ends_in_dark && !light.sunset_before_home && "You get back in the dark.",
        light.low_sun && "The sun is low for part of the walk, so shadows are long.",
      ].filter(Boolean)
    : [];

  return (
    <aside className={`side right${stale ? " stale" : ""}`}>
      <div className="side-scroll">
        {stale && (
          <p className="label updating" role="status">
            {problems.length ? "Fix the mission settings to update this plan" : "Updating the plan"}
          </p>
        )}

        <div className={`verdict ${plan.o2_ok ? "ok" : "bad"}`}>
          <p className="label">Oxygen</p>
          <strong>{plan.o2_ok ? "Fits" : "Does not fit"}</strong>
          <p>
            {plan.o2_ok ? `${hm(plan.o2_margin_h)} of usable oxygen to spare at the end.` : `${hm(-plan.o2_margin_h)} short of usable oxygen.`}
          </p>
          <p className="fine">
            The outing takes {hm(plan.hours)}. Usable oxygen is {hm(plan.usable_o2_h)}: a {s.o2_hours} h supply
            with {Math.round(s.o2_reserve * 100)}% kept in reserve.
          </p>
        </div>

        {ponr && (
          <button className="alert" onClick={() => setCursor(ponr.index)}>
            <span className="label">Point of no return</span>
            <span>Turn back before {hm(ponr.elapsed_h)} into the walk. Past that point the usable oxygen does not get you home. Click to see it on the map.</span>
          </button>
        )}

        <Part n="01" title="The walk">
          <Rows
            items={[
              ["Distance", `${plan.km} km`],
              ["Whole outing", hm(plan.hours)],
              ["Walking", hm(plan.walk_hours)],
              ["Working at stops", `${hm(plan.stop_hours)} (${s.stop_minutes} min each)`],
              ["Walking speed on flat ground", `${s.walk_speed_kmh} km/h`],
              ["Steepest ground", `${plan.max_slope} deg`],
              ["Climb / descent", `${el.climb_m} m / ${el.descent_m} m`],
              ["Highest point", `${el.highest_m} m (${el.highest_above_start_m} m above the start)`],
              ["Lowest point", `${el.lowest_m} m (${el.lowest_below_start_m} m below the start)`],
            ]}
          />
          <p className="order mono">Base → {plan.order.join(" → ")} → Base</p>
          <p className="fine">The planner picked this order of your stops. {sentence(el.note)}</p>
          <Profile plan={plan} cursor={cursor} setCursor={setCursor} />
        </Part>

        <Part n="02" title="Stops and legs">
          <table className="tbl">
            <thead><tr><th>Stop</th><th>Arrive</th><th>Leave</th>{minerals.size > 0 && <th>Mineral</th>}</tr></thead>
            <tbody>
              {plan.stop_arrivals.map((a) => {
                const m = minerals.get(a.stop);
                return (
                  <tr key={a.stop} onMouseEnter={() => setCursor(a.index)} onMouseLeave={() => setCursor(null)}>
                    <td>{a.stop}</td><td>{hm(a.arrive_h)}</td><td>{hm(a.leave_h)}</td>
                    {minerals.size > 0 && <td>{m ? `${m.mineral}${m.confidence ? ` (${m.confidence})` : ""}` : "n/a"}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
          <table className="tbl">
            <thead><tr><th>Leg</th><th>km</th><th>Time</th><th>Steepest</th><th>Up / down</th></tr></thead>
            <tbody>
              {plan.legs.map((l, i) => (
                <tr key={i}>
                  <td>{who(l.from)} → {who(l.to)}</td><td>{l.km}</td><td>{hm(l.hours)}</td><td>{l.max_slope} deg</td><td>{l.climb_m} / {l.descent_m} m</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="fine">Times count from the moment you leave base.</p>
        </Part>

        <Part n="03" title="Radio">
          <Rows
            items={[
              ["In direct contact with base", pct(radio.share_in_contact)],
              ["Longest blackout", hm(radio.longest_blackout_h)],
              ["Antennas", `base ${radio.base_antenna_m} m, suit ${radio.suit_antenna_m} m`],
            ]}
          />
          {radio.blackouts.length > 0 ? (
            <ul className="events">
              {radio.blackouts.map((b, i) => (
                <li key={i}>
                  <button onMouseEnter={() => setCursor(b.from)} onMouseLeave={() => setCursor(null)} onFocus={() => setCursor(b.from)} onBlur={() => setCursor(null)} onClick={() => setCursor(b.from)}>
                    Blackout {i + 1}: starts {hm(b.elapsed_h)} in, lasts {hm(b.duration_h)}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="fine">No blackouts on this route.</p>
          )}
          <p className="fine">Straight line of sight only, including the curve of the ground. Real radio does a little better.</p>
        </Part>

        {site.sun_check && (
          <Part n="04" title="Sun, weather and sky">
            {!light && <p className="fine">Switch on "Check the sun, weather and sky" under Mission to see daylight, temperature, wind and haze for your season and start time.</p>}
            {light && (
              <>
                <Rows
                  items={[
                    ["Mars clock, start to end", `${clock(light.start_ltst_h)} to ${clock(light.end_ltst_h)}`],
                    ["Sun height, start to end", `${light.sun_el_start} deg to ${light.sun_el_end} deg`],
                    ["Drops hidden in shadow", String(light.hidden_hazards.length)],
                  ]}
                />
                {flags.length > 0 ? <ul className="flags">{flags.map((f) => <li key={f}>{f}</li>)}</ul> : <p className="fine">Daylight for the whole walk, and the sun is never low.</p>}
                {light.hidden_hazards.length > 0 && (
                  <ul className="events">
                    {light.hidden_hazards.map((h, i) => (
                      <li key={i}>
                        <button onMouseEnter={() => setCursor(h.from)} onMouseLeave={() => setCursor(null)} onFocus={() => setCursor(h.from)} onBlur={() => setCursor(null)} onClick={() => setCursor(h.from)}>
                          {hm(h.elapsed_h)} in: {h.note}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
            {weather && (
              <>
                <Rows
                  items={[
                    ["Season", weather.season],
                    ["Air temperature", `${weather.air_c_min} to ${weather.air_c_max} °C`],
                    ["Ground temperature", `${weather.ground_c_min} to ${weather.ground_c_max} °C`],
                    ["Strongest typical wind", `${weather.wind_ms_max} m/s`],
                    weather.sky && ["Sky haze (optical depth)", `${weather.sky.optical_depth_typical} typical, ${weather.sky.optical_depth_low} to ${weather.sky.optical_depth_high} usual`],
                    weather.sky && ["Direct sunlight that gets through, sun overhead", pct(weather.sky.direct_sun_share_overhead)],
                  ]}
                />
                {weather.wind_note && <p className="fine">{sentence(weather.wind_note)}</p>}
                <p className="fine">{sentence(weather.note)} Source: {weather.source}</p>
                {weather.sky && <p className="fine">{sentence(weather.sky.meaning)} {sentence(weather.sky.note)} {sentence(weather.sky.status)} Source: {weather.sky.source}</p>}
              </>
            )}
          </Part>
        )}

        <Part n={site.sun_check ? "05" : "04"} title="Radiation">
          <Rows
            items={[
              ["Dose for this outing", `${rad.dose_usv} µSv (microsieverts)`],
              ["Rate used", `${rad.rate_usv_per_h} µSv per hour`],
              ["Measured at", rad.measured_at],
            ]}
          />
          <p className="fine">{sentence(rad.note)} Source: {rad.source}</p>
        </Part>

        <Part n={site.sun_check ? "06" : "05"} title="Scout helicopter">
          <Rows
            items={[
              ["Share of the route where the map is unsure", pct(scout.uncertain_share, 1)],
              ["Spots worth a look", String(scout.targets.length)],
              ["Helicopter flights planned", `${scout.flights}, ${scout.total_km} km in all`],
              ["Range per flight", `${scout.range_m} m`],
            ]}
          />
          {scout.targets.length > 0 && (
            <ul className="targets">
              {scout.targets.map((t, i) => {
                const letter = String.fromCharCode(65 + (i % 26));
                return (
                  <li key={i} onMouseEnter={() => setCursor(t.index)} onMouseLeave={() => setCursor(null)}>
                    <div>
                      <strong>Target {letter}</strong>
                      <span className="fine">{t.reasons.join(", ")}. {t.km_along} km along, {hm(t.elapsed_h)} in.</span>
                    </div>
                    <div className="pair">
                      <button className="btn ghost small" disabled={busy} onClick={() => onReport(t, "safe")}>Safe</button>
                      <button className="btn ghost small" disabled={busy} onClick={() => onReport(t, "blocked")}>Blocked</button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          {scout.targets.length === 0 && <p className="fine">Nothing on this route is uncertain enough to need a look.</p>}
          {observations.length > 0 && (
            <>
              <p className="label gap">Helicopter reports in this plan</p>
              <ul className="targets">
                {observations.map((o, i) => (
                  <li key={i}>
                    <div><strong>{o.finding === "safe" ? "Safe" : "Blocked"}</strong><span className="fine">within {o.radius_m} m of the reported spot</span></div>
                    <button className="btn ghost small" disabled={busy} onClick={() => onRemoveReport(i)}>Remove</button>
                  </li>
                ))}
              </ul>
            </>
          )}
          <p className="fine">Press Safe or Blocked for what the helicopter saw at a target. The walk is planned again with that report.</p>
        </Part>
      </div>
    </aside>
  );
}
