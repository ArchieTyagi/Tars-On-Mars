import { useState } from "react";
import { CHECKS, DATA, FACTS, LIMITS, SYSTEM } from "./content.js";
import "../styles/landing.css";

function Section({ n, title, children, id }) {
  return (
    <section className="lsec" id={id}>
      <header className="lsec-head">
        <span className="label">{n}</span>
        <h2>{title}</h2>
      </header>
      <div className="lsec-body">{children}</div>
    </section>
  );
}

export default function Landing({ onOpen }) {
  const [photo, setPhoto] = useState(true);
  const open = (e) => {
    // let ctrl/cmd click open a new tab like any link
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    onOpen();
  };

  return (
    <div className="landing">
      <div className="grain" aria-hidden="true" />

      <nav className="lnav">
        <a className="wordmark" href="/" aria-label="TARS on Mars, front page">
          <span className="mark" aria-hidden="true" />
          TARS on Mars
        </a>
        <div className="lnav-links">
          <a href="#system">System</a>
          <a href="#checks">Checks</a>
          <a href="#limits">Limits</a>
          <a href="#data">Data</a>
        </div>
        <a className="btn small" href="/planner" onClick={open}>Open planner</a>
      </nav>

      <header className="hero">
        <div className="hero-meta">
          <span className="label">NASA Space Apps Challenge 2026</span>
          <span className="label">Interplanetary Survival Guide: Martian Map</span>
          <span className="label">Jezero Crater, 18.44°N 77.45°E</span>
        </div>
        <h1>
          Know the way home <span className="thin">before you leave.</span>
        </h1>
        <div className="hero-foot">
          <p className="lede">
            A route planner for a person on foot on Mars. Put down a base and a few stops at Jezero Crater.
            It finds the safest loop, how long it takes, whether it fits your oxygen, and the last point
            where you can still turn back and make it home.
          </p>
          <div className="hero-cta">
            <a className="btn big" href="/planner" onClick={open}>
              Open the route planner <span aria-hidden="true">→</span>
            </a>
            <span className="label">2D map and 3D walk, in the browser</span>
          </div>
        </div>
      </header>

      {photo && (
        <figure className="plate">
          <div className="plate-frame">
            <img
              src="/api/layers/photo.jpg?site=jezero&m_per_px=4"
              alt="Orbital photo of the 5 by 5 km planning area in Jezero Crater"
              onError={() => setPhoto(false)}
            />
            <div className="plate-grain" aria-hidden="true" />
            <span className="tick tl label">Jezero Crater, Mars</span>
            <span className="tick br label">Cropped view of the planning area</span>
          </div>
          <figcaption className="label">
            <span>Fig. 01</span>
            <span>The planning area is 5 x 5 km around the Perseverance landing site. HiRISE orbital photo, NASA/JPL/University of Arizona.</span>
          </figcaption>
        </figure>
      )}

      <ul className="facts">
        {FACTS.map((f) => (
          <li key={f.value}>
            <strong>{f.value}</strong>
            <span>{f.text}</span>
          </li>
        ))}
      </ul>

      <Section n="01" title="The problem">
        <p className="big">
          A walk outside on Mars has three hard limits: the ground you can stand on, the oxygen on your back,
          and the way home.
        </p>
        <p className="body">
          A terrain map answers only the first one. This planner answers all three for the same walk. It works
          on measured NASA data, and it says where it is not sure.
        </p>
      </Section>

      <Section n="02" title="What it works out" id="system">
        <dl className="spec">
          {SYSTEM.map(([k, v], i) => (
            <div key={k} className="spec-row">
              <dt><span className="label">{String(i + 1).padStart(2, "0")}</span>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section n="03" title="Checked against reality" id="checks">
        <ul className="checks">
          {CHECKS.map((c) => (
            <li key={c.title}>
              <span className="label">{c.title}</span>
              <strong>{c.value}</strong>
              <p>{c.text}</p>
            </li>
          ))}
        </ul>
        <p className="body note">
          Every check is a script or a test in the project that anyone can run again.
        </p>
      </Section>

      <Section n="04" title="Honest limits" id="limits">
        <ol className="limits">
          {LIMITS.map((t, i) => (
            <li key={i}><span className="label">{String(i + 1).padStart(2, "0")}</span><p>{t}</p></li>
          ))}
        </ol>
      </Section>

      <Section n="05" title="Data" id="data">
        <dl className="spec small">
          {DATA.map(([k, v]) => (
            <div key={k} className="spec-row">
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <section className="closer">
        <h2>Plan a walk.</h2>
        <a className="btn big" href="/planner" onClick={open}>
          Open the route planner <span aria-hidden="true">→</span>
        </a>
      </section>

      <footer className="lfoot label">
        <span>TARS on Mars</span>
        <span>Piyush Thakkar, Archi Tyagi</span>
        <span>NASA Space Apps Challenge 2026, Ahmedabad</span>
        <span>A student project, not an official NASA product. No NASA, JPL or USGS logos are used.</span>
      </footer>
    </div>
  );
}
