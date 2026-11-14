import { useEffect, useState } from "react";
import MapView from "./MapView.jsx";
import Panel from "./Panel.jsx";

const MAX_STOPS = 6;

export default function App() {
  const [site, setSite] = useState(null);
  const [error, setError] = useState("");
  const [base, setBase] = useState(null); // [lon, lat]
  const [stops, setStops] = useState([]); // [[lon, lat], ...]
  const [showZones, setShowZones] = useState(true);
  const [flyTo, setFlyTo] = useState(null);

  useEffect(() => {
    fetch("/api/site")
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setSite)
      .catch(() => setError("Can't reach the server. Is it running on port 8000?"));
  }, []);

  function handleMapClick(lonlat) {
    if (!base) return setBase(lonlat);
    if (stops.length >= MAX_STOPS) return;
    setStops([...stops, lonlat]);
  }

  return (
    <div className="app">
      <Panel
        site={site}
        error={error}
        base={base}
        stops={stops}
        maxStops={MAX_STOPS}
        showZones={showZones}
        onToggleZones={() => setShowZones(!showZones)}
        onUseLandingSite={() => site && setBase(site.default_base)}
        onRemoveStop={(i) => setStops(stops.filter((_, j) => j !== i))}
        onClear={() => { setBase(null); setStops([]); }}
        onGoTo={(lonlat) => setFlyTo([...lonlat])}
      />
      {site && (
        <MapView site={site} base={base} stops={stops} showZones={showZones} onClick={handleMapClick} flyTo={flyTo} />
      )}
    </div>
  );
}
