// Small text helpers. No rounding surprises: 59.6 minutes becomes "1 h 00 min", never "0 h 60 min".

export function hm(hours) {
  if (hours == null || !Number.isFinite(hours)) return "n/a";
  const sign = hours < 0 ? "-" : "";
  const total = Math.round(Math.abs(hours) * 60);
  return `${sign}${Math.floor(total / 60)} h ${String(total % 60).padStart(2, "0")} min`;
}

// 9.5 -> "09:30". Wraps past midnight, because a Mars day is treated as 24 local hours.
export function clock(hours) {
  if (hours == null || !Number.isFinite(hours)) return "n/a";
  const total = ((Math.round(hours * 60) % 1440) + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function num(x, digits = 1) {
  if (x == null || !Number.isFinite(x)) return "n/a";
  return x.toFixed(digits);
}

export function pct(share, digits = 0) {
  if (share == null || !Number.isFinite(share)) return "n/a";
  return `${(share * 100).toFixed(digits)}%`;
}

// [lon, lat] -> "18.4447°N, 77.4508°E". South and west get their own letters instead of a minus sign.
export function lonlatText(lonlat, digits = 4) {
  if (!lonlat) return "n/a";
  const [lon, lat] = lonlat;
  const ns = lat < 0 ? "S" : "N";
  const ew = lon < 0 ? "W" : "E";
  return `${Math.abs(lat).toFixed(digits)}°${ns}, ${Math.abs(lon).toFixed(digits)}°${ew}`;
}

// "18.4447, 77.4508" or "18.4447 N 77.4508 E" -> [lon, lat]. Returns null when it is not two numbers.
export function parseLatLon(text) {
  const parts = String(text).match(/-?\d+(?:\.\d+)?\s*°?\s*[NSEWnsew]?/g);
  if (!parts || parts.length !== 2) return null;
  const read = (p, negative) => {
    const v = parseFloat(p);
    return new RegExp(`[${negative}]`, "i").test(p) ? -Math.abs(v) : v;
  };
  const lat = read(parts[0], "S");
  const lon = read(parts[1], "W");
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return [lon, lat];
}

// Season on Mars from Ls (the sun's position along the Mars year, 0 to 360 degrees). Named for the
// northern half of the planet, where Jezero is.
export function seasonName(ls) {
  if (typeof ls !== "number" || !Number.isFinite(ls) || ls < 0 || ls >= 360) return "n/a";
  return ["northern spring", "northern summer", "northern autumn", "northern winter"][Math.floor(ls / 90)];
}

// Server notes are written as fragments ("typical conditions ..., not a forecast"). This makes one a sentence.
export function sentence(text) {
  const t = String(text ?? "").trim();
  if (!t) return "";
  const head = t[0].toUpperCase() + t.slice(1);
  return /[.!?]$/.test(head) ? head : head + ".";
}
