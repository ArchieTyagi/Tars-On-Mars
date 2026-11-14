// Positions. The map is drawn in map meters, counted from the bottom-left corner of the site box,
// because that works for every site. Jezero is a plain lon/lat grid, so there lon/lat and meters are
// a straight-line conversion. The Moon site sits at the pole where lon/lat lines curve, so there the
// server does the conversion (/api/convert).

// True when the four corners of the box are exactly its west/east/south/north edges.
export function isPlainGrid(site) {
  const b = site.bounds;
  const want = [[b.west, b.north], [b.east, b.north], [b.west, b.south], [b.east, b.south]];
  if (!Array.isArray(b.corners) || b.corners.length !== 4) return false;
  return b.corners.every((c, i) => Math.abs(c[0] - want[i][0]) < 1e-9 && Math.abs(c[1] - want[i][1]) < 1e-9);
}

// convert(siteId, params) asks the server; it is passed in so this file can be tested without one.
export function makeGeo(site, convert) {
  const e = site.extent_xy;
  const b = site.bounds;
  const width = e.right - e.left;
  const height = e.top - e.bottom;
  const plain = isPlainGrid(site);

  const local = ([x, y]) => [x - e.left, y - e.bottom];
  const unlocal = ([lx, ly]) => [lx + e.left, ly + e.bottom];
  const inside = ([x, y]) => x >= e.left && x <= e.right && y >= e.bottom && y <= e.top;

  const toXYSync = plain
    ? ([lon, lat]) => [
        e.left + ((lon - b.west) / (b.east - b.west)) * width,
        e.top - ((b.north - lat) / (b.north - b.south)) * height,
      ]
    : null;
  const toLonLatSync = plain
    ? ([x, y]) => [
        b.west + ((x - e.left) / width) * (b.east - b.west),
        b.north - ((e.top - y) / height) * (b.north - b.south),
      ]
    : null;

  const toXY = plain
    ? (lonlat) => Promise.resolve(toXYSync(lonlat))
    : (lonlat) => convert(site.id, { lon: lonlat[0], lat: lonlat[1] }).then((r) => [r.x, r.y]);
  const toLonLat = plain
    ? (xy) => Promise.resolve(toLonLatSync(xy))
    : (xy) => convert(site.id, { x: xy[0], y: xy[1] }).then((r) => [r.lon, r.lat]);

  return { plain, width, height, local, unlocal, inside, toXY, toLonLat, toXYSync, toLonLatSync };
}
