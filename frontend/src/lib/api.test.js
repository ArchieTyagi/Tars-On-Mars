import { describe, expect, it } from "vitest";
import { detailText, layerUrl, missionFromRules, missionParams, missionProblems, planBody, query } from "./api.js";

const rules = { o2_hours: 8, o2_reserve: 0.25, walk_speed_kmh: 2.0, stop_minutes: 15, base_antenna_m: 3.0, suit_antenna_m: 2.0 };
const mission = missionFromRules(rules);

describe("detailText", () => {
  it("shows the server's own words", () => expect(detailText({ detail: "Stop 1 is the same spot as the base." }, 422)).toBe("Stop 1 is the same spot as the base."));
  it("joins a list of problems", () => expect(detailText({ detail: [{ msg: "a" }, "b"] }, 422)).toBe("a b"));
  it("has a fallback for 404", () => expect(detailText(null, 404)).toBe("The server does not have that."));
  it("has a fallback for anything else", () => expect(detailText({}, 500)).toMatch(/could not answer/));
  it("does not show an empty detail", () => expect(detailText({ detail: "" }, 500)).toMatch(/could not answer/));
});

describe("query", () => {
  it("skips empty values but keeps zero", () => expect(query({ a: 1, b: null, c: undefined, d: "", e: 0 })).toBe("?a=1&e=0"));
  it("is empty for nothing", () => expect(query({})).toBe(""));
});

describe("missionFromRules", () => {
  it("takes its numbers from the server rules", () => {
    expect(mission).toMatchObject({ slopeLimit: null, o2Hours: 8, reservePct: 25, speed: 2, stopMinutes: 15, baseAntenna: 3, suitAntenna: 2, useSun: false });
  });
});

describe("missionProblems", () => {
  it("accepts the defaults", () => expect(missionProblems(mission)).toEqual([]));
  it("rejects an empty field", () => expect(missionProblems({ ...mission, o2Hours: "" })).toHaveLength(1));
  it("rejects zero oxygen", () => expect(missionProblems({ ...mission, o2Hours: 0 })).toHaveLength(1));
  it("rejects 100 percent reserve", () => expect(missionProblems({ ...mission, reservePct: 100 })).toHaveLength(1));
  it("accepts zero minutes at stops", () => expect(missionProblems({ ...mission, stopMinutes: 0 })).toEqual([]));
  it("checks the slope range", () => {
    expect(missionProblems({ ...mission, slopeLimit: 4 })).toHaveLength(1);
    expect(missionProblems({ ...mission, slopeLimit: 35 })).toEqual([]);
  });
  it("only checks the sun when it is on", () => {
    expect(missionProblems({ ...mission, ls: 400 })).toEqual([]);
    expect(missionProblems({ ...mission, useSun: true, ls: 400 })).toHaveLength(1);
    expect(missionProblems({ ...mission, useSun: true, startLtst: 24 })).toHaveLength(1);
  });
  it("rejects NaN", () => expect(missionProblems({ ...mission, speed: NaN })).toHaveLength(1));
});

describe("planBody", () => {
  const base = [77.4508, 18.4447];
  const stops = [[77.46, 18.47]];
  it("uses the server's field names", () => {
    expect(planBody({ siteId: "jezero", base, stops, mission })).toEqual({
      site: "jezero", base, stops, slope_limit: null, o2_hours: 8, o2_reserve: 0.25, walk_speed_kmh: 2,
      stop_minutes: 15, base_antenna_m: 3, suit_antenna_m: 2,
    });
  });
  it("sends the sun only when switched on and the site has a sun model", () => {
    const m = { ...mission, useSun: true, ls: 120, startLtst: 9 };
    expect(planBody({ siteId: "jezero", base, stops, mission: m, sunCheck: true })).toMatchObject({ ls: 120, start_ltst_h: 9 });
    expect(planBody({ siteId: "moon", base, stops, mission: m, sunCheck: false })).not.toHaveProperty("ls");
    expect(planBody({ siteId: "jezero", base, stops, mission, sunCheck: true })).not.toHaveProperty("start_ltst_h");
  });
  it("sends helicopter reports when there are any", () => {
    const obs = [{ lonlat: [77.4, 18.48], finding: "blocked", radius_m: 20 }];
    expect(planBody({ siteId: "jezero", base, stops, mission, observations: obs }).observations).toEqual(obs);
    expect(planBody({ siteId: "jezero", base, stops, mission })).not.toHaveProperty("observations");
  });
});

describe("layerUrl", () => {
  const zones = { url: "/api/layers/zones.png?site=jezero", options: ["slope_limit"], needs_base: false };
  const reach = { url: "/api/layers/safe_range.png?site=jezero", needs_base: true, options: ["slope_limit", "o2_hours", "o2_reserve", "walk_speed_kmh", "stop_minutes"] };
  const photo = { url: "/api/layers/photo.jpg?site=jezero&m_per_px=2", needs_base: false };
  it("leaves a plain layer alone", () => expect(layerUrl(photo, null, mission)).toBe("/api/layers/photo.jpg?site=jezero&m_per_px=2"));
  it("leaves out a slope limit that is not set", () => expect(layerUrl(zones, null, mission)).toBe("/api/layers/zones.png?site=jezero"));
  it("adds the slope limit when set", () => expect(layerUrl(zones, null, { ...mission, slopeLimit: 25 })).toBe("/api/layers/zones.png?site=jezero&slope_limit=25"));
  it("waits for a base when the layer needs one", () => expect(layerUrl(reach, null, mission)).toBeNull());
  it("adds the base and only the listed settings", () => {
    expect(layerUrl(reach, [77.4508, 18.4447], mission)).toBe(
      "/api/layers/safe_range.png?site=jezero&lon=77.4508&lat=18.4447&o2_hours=8&o2_reserve=0.25&walk_speed_kmh=2&stop_minutes=15");
  });
  it("works for an address without a question mark", () => expect(layerUrl({ url: "/x.png", needs_base: true }, [1, 2], mission)).toBe("/x.png?lon=1&lat=2"));
});

describe("missionParams", () => {
  it("turns percent into a share", () => expect(missionParams({ ...mission, reservePct: 30 }).o2_reserve).toBeCloseTo(0.3));
});
