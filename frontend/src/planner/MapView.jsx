import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { getJson } from "../lib/api.js";
import { hm, lonlatText } from "../lib/format.js";
import { KEY_STYLE, routeKeys, runs } from "../lib/route.js";

// The map is drawn in meters from the bottom-left corner of the site box (see lib/geo.js).
// Leaflet wants [y, x].

const mark = (cls, text) =>
  L.divIcon({ className: "", html: `<div class="mk ${cls}">${text}</div>`, iconSize: [24, 24], iconAnchor: [12, 12] });

// Tooltip text comes from the server, so it is put in as plain text, never as HTML.
function tip(lines) {
  const el = document.createElement("div");
  for (const line of lines) {
    const row = document.createElement("div");
    row.textContent = line;
    el.appendChild(row);
  }
  return el;
}

export default function MapView({ site, geo, base, stops, plan, routeMode, baseUrl, overlays, rover, science, cursor, flyTo, onPick, onLayerError }) {
  const box = useRef(null);
  const mapRef = useRef(null);
  const g = useRef({});
  const baseImg = useRef(null);
  const overlayImgs = useRef(new Map());
  const pickRef = useRef(onPick);
  const errRef = useRef(onLayerError);
  const hoverId = useRef(0);
  const hoverTimer = useRef(null);
  pickRef.current = onPick;
  errRef.current = onLayerError;
  const [hover, setHover] = useState(null);
  const [loading, setLoading] = useState(0);
  const viewRef = useRef({});
  // wider pictures around the planning box, far to near (all of Mars first). Not used by the planner.
  const context = site.context || [];

  const ll = (xy) => {
    const [lx, ly] = geo.local(xy);
    return [ly, lx];
  };
  const box2 = () => L.latLngBounds([[0, 0], [geo.height, geo.width]]);
  const boundsOf = (e) => L.latLngBounds(ll([e.left, e.bottom]), ll([e.right, e.top]));

  // an image layer that reports when it is loading and when it fails
  function image(url, name, options, bounds) {
    const layer = L.imageOverlay(url, bounds || box2(), options);
    let open = true;
    const close = (failed) => {
      if (!open) return;
      open = false;
      setLoading((n) => Math.max(0, n - 1));
      if (failed) errRef.current(name);
    };
    setLoading((n) => n + 1);
    layer.on("load", () => close(false));
    layer.on("error", () => close(true));
    layer.on("remove", () => close(false));
    return layer;
  }

  // ---- build the map once per site -------------------------------------------
  useEffect(() => {
    const bounds = box2();
    const m = L.map(box.current, {
      crs: L.CRS.Simple, minZoom: -20, maxZoom: 3, zoomSnap: 0.25, zoomDelta: 0.5,
      attributionControl: false, doubleClickZoom: false, maxBoundsViscosity: 0.8,
    });
    m.createPane("context").style.zIndex = 100;
    m.createPane("ground").style.zIndex = 200;
    m.createPane("layers").style.zIndex = 300;
    m.createPane("frame").style.zIndex = 350;
    m.getPane("frame").style.pointerEvents = "none";
    m.setView(bounds.getCenter(), -3, { animate: false }); // a first view; the real fit happens once the box has a size
    const outer = context.length ? boundsOf(context[0].extent_xy) : null;
    m.setMaxBounds(outer ? outer.pad(0.02) : bounds.pad(0.3));

    if (context.length) {
      // A picture is only kept on the map while it is a sane size on screen. Zoomed far in, the planet
      // picture would be hundreds of millions of pixels wide, which browsers cannot draw.
      const MAX_PX = 12e6;
      const shown = new Map();
      const sync = () => {
        const scale = Math.pow(2, m.getZoom()); // screen pixels per meter
        context.forEach((c, i) => {
          const fits = (c.extent_xy.right - c.extent_xy.left) * scale <= MAX_PX;
          if (fits && !shown.has(c.id)) {
            shown.set(c.id, image(c.url, c.name, { pane: "context", className: "img-context", zIndex: i + 1 }, boundsOf(c.extent_xy)).addTo(m));
          } else if (!fits && shown.has(c.id)) {
            shown.get(c.id).remove();
            shown.delete(c.id);
          }
        });
      };
      m.on("zoomend", sync);
      sync();
      L.rectangle(bounds, { pane: "frame", color: "#f1f0ea", weight: 1.5, fill: false, interactive: false }).addTo(m);
      // a name tag standing on the top-left corner of the box, so the box can be found from far away
      L.marker(bounds.getNorthWest(), {
        pane: "frame", interactive: false, keyboard: false,
        icon: L.divIcon({ className: "boxlabel", html: "Planning area", iconSize: null, iconAnchor: [1, 22] }),
      }).addTo(m);
    }
    viewRef.current = { outer };
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(m);

    g.current = {
      rover: L.layerGroup().addTo(m),
      route: L.layerGroup().addTo(m),
      science: L.layerGroup().addTo(m),
      pins: L.layerGroup().addTo(m),
      cursor: L.layerGroup().addTo(m),
    };

    const here = (e) => geo.unlocal([e.latlng.lng, e.latlng.lat]);
    m.on("click", (e) => pickRef.current(here(e)));
    m.on("mousemove", (e) => {
      const xy = here(e);
      const id = ++hoverId.current;
      clearTimeout(hoverTimer.current);
      if (!geo.inside(xy)) {
        setHover({ outside: true, lonlat: geo.plain ? geo.toLonLatSync(xy) : null });
        return;
      }
      // keep the last numbers on screen, greyed out, until the new ones arrive
      setHover((h) => ({ lonlat: geo.plain ? geo.toLonLatSync(xy) : null, point: h && h.point ? h.point : null, pending: true }));
      hoverTimer.current = setTimeout(async () => {
        try {
          const lonlat = await geo.toLonLat(xy);
          const point = await getJson("/api/point", { site: site.id, lon: lonlat[0], lat: lonlat[1] });
          if (id === hoverId.current) setHover({ lonlat, point });
        } catch {
          if (id === hoverId.current) setHover({ lonlat: null, point: null, failed: true });
        }
      }, 120);
    });
    m.on("mouseout", () => {
      hoverId.current++;
      clearTimeout(hoverTimer.current);
      setHover(null);
    });

    // Keep the whole site in view while the box changes size (window resized, panels stacking on a narrow
    // screen, or the page opened in a hidden tab that had no size yet). Once the person has zoomed or
    // moved the map themselves, their view is left alone.
    let touched = false;
    let auto = false;
    m.on("zoomstart movestart", () => {
      if (!auto) touched = true;
    });
    const ro = new ResizeObserver(() => {
      m.invalidateSize({ pan: false });
      const size = m.getSize();
      if (touched || size.x < 2 || size.y < 2) return;
      auto = true;
      m.setMinZoom(-20);
      m.fitBounds(bounds, { animate: false });
      m.setMinZoom(outer ? Math.min(m.getBoundsZoom(outer, false), m.getZoom() - 1) : m.getZoom() - 1);
      auto = false;
    });
    ro.observe(box.current);

    mapRef.current = m;
    return () => {
      ro.disconnect();
      hoverId.current++;
      clearTimeout(hoverTimer.current);
      baseImg.current = null;
      overlayImgs.current = new Map();
      mapRef.current = null;
      m.remove();
    };
  }, [site, geo]);

  // ---- ground picture -----------------------------------------------------------
  useEffect(() => {
    const m = mapRef.current;
    if (!m) return;
    if (baseImg.current) {
      baseImg.current.remove();
      baseImg.current = null;
    }
    if (baseUrl) baseImg.current = image(baseUrl, "ground picture", { pane: "ground", className: "img-ground" }).addTo(m);
  }, [baseUrl, geo]);

  // ---- layers on top --------------------------------------------------------------
  useEffect(() => {
    const m = mapRef.current;
    if (!m) return;
    const have = overlayImgs.current;
    const want = new Map(overlays.map((o, i) => [o.id, { ...o, z: i + 1 }]));
    for (const [id, old] of have) {
      const w = want.get(id);
      if (!w || w.url !== old.url) {
        old.layer.remove();
        have.delete(id);
      }
    }
    for (const [id, w] of want) {
      const old = have.get(id);
      if (old) {
        old.layer.setZIndex(w.z);
      } else {
        const layer = image(w.url, w.name || id, { pane: "layers", className: "img-layer", opacity: 0.8, zIndex: w.z }).addTo(m);
        have.set(id, { url: w.url, layer });
      }
    }
  }, [overlays, geo]);

  // ---- base and stops ---------------------------------------------------------------
  useEffect(() => {
    const grp = g.current.pins;
    if (!grp) return;
    grp.clearLayers();
    if (base) L.marker(ll(base.xy), { icon: mark("base", "B"), zIndexOffset: 500, keyboard: false }).bindTooltip(tip(["Base", lonlatText(base.lonlat)])).addTo(grp);
    stops.forEach((s, i) =>
      L.marker(ll(s.xy), { icon: mark("stop", String(i + 1)), zIndexOffset: 400, keyboard: false }).bindTooltip(tip([`Stop ${i + 1}`, lonlatText(s.lonlat)])).addTo(grp)
    );
  }, [base, stops, geo]);

  // ---- the planned route ------------------------------------------------------------
  useEffect(() => {
    const grp = g.current.route;
    if (!grp) return;
    grp.clearLayers();
    if (!plan) return;
    const pts = plan.path_xy.map(ll);
    L.polyline(pts, { color: "#010101", weight: 8, opacity: 0.7, interactive: false }).addTo(grp);
    const keys = routeKeys(plan, routeMode);
    for (const r of runs(keys)) {
      L.polyline(pts.slice(r.start, r.end + 1), { color: KEY_STYLE[r.key].color, weight: 4, interactive: false }).addTo(grp);
    }
    const p = plan.point_of_no_return;
    if (p && pts[p.index]) {
      L.marker(pts[p.index], { icon: mark("ponr", "!"), zIndexOffset: 900, keyboard: false })
        .bindTooltip(tip(["Point of no return", `${hm(p.elapsed_h)} into the walk. Turn back before here.`]))
        .addTo(grp);
    }
    if (plan.light && plan.light.hidden_hazards) {
      for (const h of plan.light.hidden_hazards) {
        if (!pts[h.from]) continue;
        L.marker(pts[h.from], { icon: mark("hazard", "▲"), zIndexOffset: 300, keyboard: false })
          .bindTooltip(tip(["Drop in shadow", h.note, `${hm(h.elapsed_h)} into the walk, sun ${h.sun_el} deg high`]))
          .addTo(grp);
      }
    }
    if (plan.scout && plan.scout.targets) {
      plan.scout.targets.forEach((t, i) => {
        if (!pts[t.index]) return;
        L.marker(pts[t.index], { icon: mark("scout", String.fromCharCode(65 + (i % 26))), zIndexOffset: 200, keyboard: false })
          .bindTooltip(tip([`Scout target ${String.fromCharCode(65 + (i % 26))}`, t.reasons.join(", ")]))
          .addTo(grp);
      });
    }
  }, [plan, routeMode, geo]);

  // ---- suggested science stops --------------------------------------------------------
  useEffect(() => {
    const grp = g.current.science;
    if (!grp) return;
    grp.clearLayers();
    if (!science) return;
    for (const s of science.stops) {
      L.marker(ll(s.xy), { icon: mark("sci", "◆"), zIndexOffset: 100, keyboard: false })
        .bindTooltip(tip([s.mineral, s.why, `About ${hm(s.round_trip_h)} there and back`]))
        .addTo(grp);
    }
  }, [science, geo]);

  // ---- where Perseverance really drove --------------------------------------------------
  useEffect(() => {
    const grp = g.current.rover;
    if (!grp) return;
    grp.clearLayers();
    if (!rover || !geo.plain) return;
    const to = (lonlat) => ll(geo.toXYSync(lonlat));
    for (const seg of rover.segments) {
      L.polyline(seg.points.map(to), { color: "#39d0d8", weight: 2, opacity: 0.95, interactive: false }).addTo(grp);
    }
    for (const s of rover.stops) {
      L.circleMarker(to(s.lonlat), { radius: 2.5, color: "#39d0d8", weight: 1, fillColor: "#010101", fillOpacity: 1 })
        .bindTooltip(tip([`Rover stop, sol ${s.sol}`, `Tilt it measured: ${s.tilt_deg.toFixed(1)} deg`]))
        .addTo(grp);
    }
    if (rover.landing) {
      L.circleMarker(to(rover.landing.lonlat), { radius: 6, color: "#39d0d8", weight: 2, fillOpacity: 0 })
        .bindTooltip(tip([rover.landing.name, rover.landing.note]))
        .addTo(grp);
    }
  }, [rover, geo]);

  // ---- the spot picked on the height chart or in a list ---------------------------------
  useEffect(() => {
    const grp = g.current.cursor;
    if (!grp) return;
    grp.clearLayers();
    if (cursor === null || !plan || !plan.path_xy[cursor]) return;
    L.circleMarker(ll(plan.path_xy[cursor]), { radius: 8, color: "#010101", weight: 3, fillColor: "#f1f0ea", fillOpacity: 1, interactive: false }).addTo(grp);
  }, [cursor, plan, geo]);

  // ---- jump to a spot ----------------------------------------------------------------------
  useEffect(() => {
    const m = mapRef.current;
    if (!m || !flyTo) return;
    m.setView(ll(flyTo.xy), Math.max(m.getZoom(), -1), { animate: true });
  }, [flyTo, geo]);

  const fit = () => {
    const m = mapRef.current;
    if (!m) return;
    if (plan) m.fitBounds(L.latLngBounds(plan.path_xy.map(ll)).pad(0.25));
    else m.fitBounds(box2());
  };

  const fitAll = () => {
    const m = mapRef.current;
    if (m && viewRef.current.outer) m.fitBounds(viewRef.current.outer);
  };

  const pt = hover && hover.point;
  return (
    <div className="mapwrap">
      <div ref={box} className="map" />
      <div className="mapbtns">
        <button className="mapbtn" onClick={fit}>{plan ? "Fit route" : "Fit map"}</button>
        {context.length > 0 && <button className="mapbtn" onClick={fitAll}>All of {context[0].name}</button>}
      </div>
      {context.length > 0 && (
        <div className="mapnote label">Dark ground: not mapped for walking yet</div>
      )}
      {loading > 0 && <div className="mapstatus label" role="status">Loading layer</div>}
      <div className="readout" aria-live="off">
        {!hover && <span className="dim">Move over the map</span>}
        {hover && hover.outside && (
          <>
            {hover.lonlat && Math.abs(hover.lonlat[1]) <= 90 && Math.abs(hover.lonlat[0]) <= 180 && <span className="mono">{lonlatText(hover.lonlat, 3)}</span>}
            <span className="dim">{context.length ? "Not mapped for walking yet" : "Outside the map data"}</span>
          </>
        )}
        {hover && hover.failed && <span className="dim">No answer from the server</span>}
        {hover && !hover.outside && !hover.failed && (
          <>
            <span className="mono">{hover.lonlat ? lonlatText(hover.lonlat, 5) : "…"}</span>
            {pt && pt.inside && (
              <span className={hover.pending ? "vals pending" : "vals"}>
                <span>Height <b>{pt.height_m} m</b></span>
                <span>Slope <b>{pt.slope_deg} deg</b>{pt.slope_err_deg != null ? ` (map error ${pt.slope_err_deg} deg)` : ""}</span>
                {pt.mineral && <span>Mineral <b>{pt.mineral}</b>{pt.mineral_confidence ? ` (${pt.mineral_confidence})` : ""}</span>}
                <span className={`zone ${pt.zone === "GO" ? "go" : pt.zone === "CAUTION" ? "caution" : "nogo"}`}>{pt.zone}</span>
              </span>
            )}
            {pt && !pt.inside && <span className="dim">Outside the map data</span>}
          </>
        )}
      </div>
    </div>
  );
}
