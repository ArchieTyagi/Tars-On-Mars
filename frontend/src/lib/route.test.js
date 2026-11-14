import { describe, expect, it } from "vitest";
import { KEY_STYLE, ROUTE_MODES, availableModes, band, hudAt, indexAtTime, profile, routeKeys, runs, slopeKey } from "./route.js";

const plan = {
  path: [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]],
  margin_h: [3, 1.5, 0.5, -0.2, -1],
  elapsed_h: [0, 0.5, 1, 1.5, 2],
  home_h: [0, 0.5, 1, 1.5, 2],
  slope_deg: [1, 6, null, 21, 40],
  height_m: [-2570, -2565, -2560, -2562, -2570],
  dist_m: [0, 30, 55, 90, 200],
  hours: 2,
  settings: { o2_hours: 4 },
  radio: { in_contact: [true, true, false, false, true] },
  light: null,
};

describe("band", () => {
  it("1 h or more is fine", () => expect(band(1)).toBe("ok"));
  it("under 1 h is tight", () => expect(band(0.99)).toBe("tight"));
  it("zero spare is still tight, not over", () => expect(band(0)).toBe("tight"));
  it("below zero is past the point of no return", () => expect(band(-0.01)).toBe("over"));
  it("a missing number is never shown as fine", () => { expect(band(null)).toBe("nodata"); expect(band(NaN)).toBe("nodata"); });
});

describe("slopeKey", () => {
  it("uses the same 5 degree steps as the slope layer", () => {
    expect(slopeKey(0)).toBe("s0"); expect(slopeKey(4.9)).toBe("s0"); expect(slopeKey(5)).toBe("s1");
    expect(slopeKey(24.9)).toBe("s4"); expect(slopeKey(25)).toBe("s5"); expect(slopeKey(60)).toBe("s5");
  });
  it("missing slope", () => expect(slopeKey(null)).toBe("nodata"));
});

describe("routeKeys", () => {
  it("oxygen", () => expect(routeKeys(plan, "margin")).toEqual(["ok", "ok", "tight", "over", "over"]));
  it("radio", () => expect(routeKeys(plan, "radio")).toEqual(["contact", "contact", "blackout", "blackout", "contact"]));
  it("slope", () => expect(routeKeys(plan, "slope")).toEqual(["s0", "s1", "nodata", "s4", "s5"]));
  it("daylight falls back to oxygen when the plan has no sun", () => expect(routeKeys(plan, "light")).toEqual(routeKeys(plan, "margin")));
  it("daylight", () => expect(routeKeys({ ...plan, light: { dark: [false, false, true, true, true] } }, "light")).toEqual(["lit", "lit", "dark", "dark", "dark"]));
  it("every key has a color and a label", () => {
    for (const m of ROUTE_MODES) for (const k of m.keys) { expect(KEY_STYLE[k].color).toMatch(/^#/); expect(KEY_STYLE[k].label).toBeTruthy(); }
  });
});

describe("availableModes", () => {
  it("hides daylight without a sun check", () => expect(availableModes(plan).map((m) => m.id)).toEqual(["margin", "radio", "slope"]));
  it("shows daylight with one", () => expect(availableModes({ ...plan, light: { dark: [] } }).map((m) => m.id)).toContain("light"));
});

describe("runs", () => {
  it("groups steps by the point they arrive at and shares the joining point", () => {
    expect(runs(["a", "a", "b", "b", "a"])).toEqual([
      { key: "a", start: 0, end: 1 }, { key: "b", start: 1, end: 3 }, { key: "a", start: 3, end: 4 },
    ]);
  });
  it("one color is one run", () => expect(runs(["a", "a", "a"])).toEqual([{ key: "a", start: 0, end: 2 }]));
  it("the first point's own key does not matter", () => expect(runs(["z", "a", "a"])).toEqual([{ key: "a", start: 0, end: 2 }]));
  it("covers every step exactly once", () => {
    const keys = ["a", "b", "a", "b", "b", "c", "c", "a"];
    const r = runs(keys);
    expect(r[0].start).toBe(0);
    expect(r.at(-1).end).toBe(keys.length - 1);
    for (let i = 1; i < r.length; i++) expect(r[i].start).toBe(r[i - 1].end);
    for (const run of r) for (let i = run.start + 1; i <= run.end; i++) expect(keys[i]).toBe(run.key);
  });
  it("nothing to draw for one point or none", () => { expect(runs(["a"])).toEqual([]); expect(runs([])).toEqual([]); expect(runs(null)).toEqual([]); });
  it("two points", () => expect(runs(["a", "b"])).toEqual([{ key: "b", start: 0, end: 1 }]));
});

describe("profile", () => {
  const p = profile(plan.dist_m, plan.height_m, 200, 50);
  it("starts at the left and ends at the right", () => { expect(p.points[0][0]).toBe(0); expect(p.points.at(-1)[0]).toBe(200); });
  it("puts the highest point at the top and the lowest at the bottom", () => {
    expect(p.min).toBe(-2570); expect(p.max).toBe(-2560);
    expect(p.points[2][1]).toBe(0); expect(p.points[0][1]).toBe(50);
  });
  it("knows the distance", () => expect(p.total).toBe(200));
  it("thins long routes but keeps both ends", () => {
    const d = Array.from({ length: 1411 }, (_, i) => i * 4);
    const h = d.map((x) => Math.sin(x / 300));
    const q = profile(d, h, 300, 60, 300);
    expect(q.points.length).toBeLessThanOrEqual(302);
    expect(q.index[0]).toBe(0); expect(q.index.at(-1)).toBe(1410);
  });
  it("flat ground is a line in the middle, not a division by zero", () => {
    const q = profile([0, 10, 20], [5, 5, 5], 100, 40);
    expect(q.points.map((x) => x[1])).toEqual([20, 20, 20]);
  });
  it("too short to draw", () => expect(profile([0], [1], 10, 10).points).toEqual([]));
  it("skips a missing height instead of breaking the scale", () => {
    const q = profile([0, 10, 20], [1, null, 3], 100, 40);
    expect(q.min).toBe(1); expect(q.max).toBe(3);
    expect(q.points.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y))).toBe(true);
  });
});

describe("hudAt", () => {
  it("reads the numbers at one point", () => {
    const h = hudAt(plan, 1);
    expect(h).toMatchObject({ elapsed: 0.5, total: 2, home: 0.5, margin: 1.5, state: "ok", supplyLeft: 3.5, supplyShare: 0.875, height: -2565, walked: 30, inContact: true, dark: null });
  });
  it("steepest slope in the next 60 m, skipping missing values", () => {
    expect(hudAt(plan, 0).steepestAhead).toBe(6);
    expect(hudAt(plan, 1).steepestAhead).toBe(21);
  });
  it("turns red past the point of no return", () => expect(hudAt(plan, 3).state).toBe("over"));
  it("clamps the index", () => { expect(hudAt(plan, 99).elapsed).toBe(2); expect(hudAt(plan, -5).elapsed).toBe(0); });
  it("oxygen share never leaves 0..1", () => expect(hudAt({ ...plan, settings: { o2_hours: 1 } }, 4).supplyShare).toBe(0));
});

describe("indexAtTime", () => {
  const e = [0, 0.5, 0.5, 1, 2];
  it("start", () => expect(indexAtTime(e, 0)).toBe(0));
  it("between points stays on the last one reached", () => expect(indexAtTime(e, 0.7)).toBe(2));
  it("waiting at a stop (same time twice) moves to the later point", () => expect(indexAtTime(e, 0.5)).toBe(2));
  it("past the end", () => expect(indexAtTime(e, 9)).toBe(4));
  it("before the start", () => expect(indexAtTime(e, -1)).toBe(0));
  it("empty", () => expect(indexAtTime([], 1)).toBe(0));
});
