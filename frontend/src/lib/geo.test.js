import { describe, expect, it } from "vitest";
import { isPlainGrid, makeGeo } from "./geo.js";

// real numbers from /api/site
const jezero = {
  id: "jezero",
  bounds: {
    west: 77.38782636885463, south: 18.41283120121982, east: 77.47217939314521, north: 18.497184225510395,
    corners: [[77.38782636885463, 18.497184225510395], [77.47217939314521, 18.497184225510395],
              [77.38782636885463, 18.41283120121982], [77.47217939314521, 18.41283120121982]],
  },
  extent_xy: { left: 4587140.0, top: 1096415.0, right: 4592140.0, bottom: 1091415.0 },
};
const moon = {
  id: "moon",
  bounds: {
    west: -171.46923439005187, south: -89.83511068271815, east: -101.88865803962798, north: -89.0902836089219,
    corners: [[-101.88865803962798, -89.3596919374833], [-143.13010235415598, -89.83511068271815],
              [-136.46880071438582, -89.0902836089219], [-171.46923439005187, -89.333071056255]],
  },
  extent_xy: { left: -19000.0, top: -4000.0, right: -3000.0, bottom: -20000.0 },
};

describe("isPlainGrid", () => {
  it("Jezero is a plain lon/lat grid", () => expect(isPlainGrid(jezero)).toBe(true));
  it("the Moon pole site is not", () => expect(isPlainGrid(moon)).toBe(false));
});

describe("Jezero conversion", () => {
  const g = makeGeo(jezero, () => { throw new Error("must not ask the server"); });
  it("matches the server's own answer for a point (from /api/convert)", () => {
    const [lon, lat] = g.toLonLatSync([4590000, 1094000]);
    expect(lon).toBeCloseTo(77.43607629874884, 9);
    expect(lat).toBeCloseTo(18.456441714778048, 9);
  });
  it("puts the landing site where the planner puts it (path_xy[0]) within one 4 m square", () => {
    const [x, y] = g.toXYSync([77.4508, 18.4447]);
    expect(Math.abs(x - 4590874)).toBeLessThan(4);
    expect(Math.abs(y - 1093305)).toBeLessThan(4);
  });
  it("goes there and back without drift", () => {
    const xy = g.toXYSync([77.43, 18.45]);
    const [lon, lat] = g.toLonLatSync(xy);
    expect(lon).toBeCloseTo(77.43, 10);
    expect(lat).toBeCloseTo(18.45, 10);
  });
  it("maps the corners of the box to the corners of the extent", () => {
    expect(g.toXYSync([jezero.bounds.west, jezero.bounds.north])).toEqual([4587140, 1096415]);
    const [x, y] = g.toXYSync([jezero.bounds.east, jezero.bounds.south]);
    expect(x).toBeCloseTo(4592140, 6);
    expect(y).toBeCloseTo(1091415, 6);
  });
  it("the async form gives the same answer", async () => {
    expect(await g.toXY([77.43, 18.45])).toEqual(g.toXYSync([77.43, 18.45]));
  });
  it("knows its size in meters", () => { expect(g.width).toBe(5000); expect(g.height).toBe(5000); });
});

describe("local coordinates", () => {
  const g = makeGeo(jezero, null);
  it("count from the bottom-left corner", () => expect(g.local([4587140, 1091415])).toEqual([0, 0]));
  it("go back", () => expect(g.unlocal(g.local([4590000, 1094000]))).toEqual([4590000, 1094000]));
  it("inside and outside", () => {
    expect(g.inside([4590000, 1094000])).toBe(true);
    expect(g.inside([4587139, 1094000])).toBe(false);
    expect(g.inside([4590000, 1096416])).toBe(false);
  });
});

describe("Moon conversion", () => {
  const asked = [];
  const convert = (siteId, params) => {
    asked.push([siteId, params]);
    return Promise.resolve("x" in params ? { lon: -137.4, lat: -89.46 } : { x: -10995, y: -12005 });
  };
  const g = makeGeo(moon, convert);
  it("has no straight-line shortcut", () => { expect(g.plain).toBe(false); expect(g.toXYSync).toBeNull(); });
  it("asks the server for lon/lat to meters", async () => {
    expect(await g.toXY([-137.5, -89.46])).toEqual([-10995, -12005]);
    expect(asked.at(-1)).toEqual(["moon", { lon: -137.5, lat: -89.46 }]);
  });
  it("asks the server for meters to lon/lat", async () => {
    expect(await g.toLonLat([-11000, -12000])).toEqual([-137.4, -89.46]);
    expect(asked.at(-1)).toEqual(["moon", { x: -11000, y: -12000 }]);
  });
  it("is 16 km wide", () => expect(g.width).toBe(16000));
});
