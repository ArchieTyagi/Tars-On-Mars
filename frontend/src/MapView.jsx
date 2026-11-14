import { useEffect, useRef } from "react";
import L from "leaflet";

// Leaflet wants [lat, lon], our API uses [lon, lat]
const ll = ([lon, lat]) => [lat, lon];

// plain lon/lat grid, but distances use Mars' radius (so the scale bar is right)
const MarsCRS = L.extend({}, L.CRS.EPSG4326, { R: 3396190, distance: L.CRS.Earth.distance });

function pin(label, kind) {
  return L.divIcon({ className: "", html: `<div class="pin ${kind}">${label}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] });
}

export default function MapView({ site, base, stops, showZones, onClick, flyTo }) {
  const box = useRef(null);
  const map = useRef(null);
  const zones = useRef(null);
  const pins = useRef(null);
  const clickRef = useRef(onClick);
  const flyRef = useRef(null);
  clickRef.current = onClick;

  // build the map once
  useEffect(() => {
    const b = site.bounds;
    const bounds = [[b.south, b.west], [b.north, b.east]];
    const m = L.map(box.current, {
      crs: MarsCRS,
      zoomSnap: 0.25,
      minZoom: 0,
      maxZoom: 22,
      attributionControl: false,
    });
    m.setView(L.latLngBounds(bounds).getCenter(), 12); // start near Jezero, refined below
    L.imageOverlay("/api/layers/hillshade.png", bounds).addTo(m);
    zones.current = L.imageOverlay("/api/layers/zones.png", bounds, { opacity: 0.85 });
    pins.current = L.layerGroup().addTo(m);
    // fit once the box has its real size on screen
    const fit = () => {
      m.invalidateSize();
      m.fitBounds(bounds, { animate: false });
      m.setMinZoom(m.getZoom());
      m.setMaxBounds(L.latLngBounds(bounds).pad(0.05));
    };
    requestAnimationFrame(fit);

    // reset view button (under the zoom buttons)
    const Reset = L.Control.extend({
      onAdd: () => {
        const b = L.DomUtil.create("button", "map-btn");
        b.title = "Reset view";
        b.textContent = "⤢";
        L.DomEvent.disableClickPropagation(b);
        b.onclick = () => m.fitBounds(bounds, { animate: true });
        return b;
      },
    });
    new Reset({ position: "topleft" }).addTo(m);

    // live readout of what's under the mouse
    const Info = L.Control.extend({
      onAdd: () => {
        const d = L.DomUtil.create("div", "readout");
        d.innerHTML = "Hover the map";
        return d;
      },
    });
    const info = new Info({ position: "bottomright" }).addTo(m);
    let timer = null;
    let last = 0;
    m.on("mousemove", (e) => {
      const { lat, lng } = e.latlng;
      const el = info.getContainer();
      const coords = `${lat.toFixed(5)}°N  ${lng.toFixed(5)}°E`;
      el.innerHTML = `<div class="coords">${coords}</div><div class="muted">…</div>`;
      clearTimeout(timer);
      const ask = () => {
        const id = ++last;
        fetch(`/api/point?lon=${lng}&lat=${lat}`).then((r) => r.json()).then((p) => {
          if (id !== last) return;
          el.innerHTML = p.inside
            ? `<div class="coords">${coords}</div>
               <div>Height <b>${p.height_m} m</b> · Slope <b>${p.slope_deg}°</b></div>
               <div class="zone ${p.zone.toLowerCase()}">${p.zone}</div>`
            : `<div class="coords">${coords}</div><div class="muted">outside the map data</div>`;
        }).catch(() => {});
      };
      timer = setTimeout(ask, 80);
    });
    m.on("mouseout", () => { info.getContainer().innerHTML = "Hover the map"; });
    flyRef.current = (lon, lat) => m.setView([lat, lon], Math.max(m.getZoom(), 16));

    m.on("click", (e) => clickRef.current([e.latlng.lng, e.latlng.lat]));
    L.control.scale({ imperial: false }).addTo(m);
    map.current = m;
    return () => m.remove();
  }, [site]);

  useEffect(() => {
    if (!map.current) return;
    if (showZones) zones.current.addTo(map.current);
    else zones.current.remove();
  }, [showZones]);

  useEffect(() => {
    const g = pins.current;
    if (!g) return;
    g.clearLayers();
    if (base) L.marker(ll(base), { icon: pin("B", "base") }).addTo(g);
    stops.forEach((s, i) => L.marker(ll(s), { icon: pin(String(i + 1), "stop") }).addTo(g));
  }, [base, stops]);

  // jump to a spot when the panel asks
  useEffect(() => {
    if (flyTo && flyRef.current) flyRef.current(flyTo[0], flyTo[1]);
  }, [flyTo]);

  return <div ref={box} className="map" />;
}
