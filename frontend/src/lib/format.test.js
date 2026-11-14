import { describe, expect, it } from "vitest";
import { clock, hm, lonlatText, num, parseLatLon, pct, seasonName, sentence } from "./format.js";

describe("hm", () => {
  it("writes hours and minutes", () => expect(hm(4.35)).toBe("4 h 21 min"));
  it("never shows 60 minutes", () => expect(hm(0.9999)).toBe("1 h 00 min"));
  it("keeps the minus sign for a shortfall", () => expect(hm(-2.33)).toBe("-2 h 20 min"));
  it("handles zero", () => expect(hm(0)).toBe("0 h 00 min"));
  it("does not crash on missing numbers", () => {
    expect(hm(null)).toBe("n/a");
    expect(hm(undefined)).toBe("n/a");
    expect(hm(NaN)).toBe("n/a");
  });
});

describe("clock", () => {
  it("formats a Mars local time", () => expect(clock(9.5)).toBe("09:30"));
  it("wraps past midnight", () => expect(clock(25.25)).toBe("01:15"));
  it("rounds 23:59:40 up to 00:00, not 24:00", () => expect(clock(23.9999)).toBe("00:00"));
  it("handles missing", () => expect(clock(null)).toBe("n/a"));
});

describe("num and pct", () => {
  it("rounds", () => expect(num(14.44)).toBe("14.4"));
  it("pct", () => expect(pct(0.413)).toBe("41%"));
  it("pct with digits", () => expect(pct(0.9521664, 1)).toBe("95.2%"));
  it("missing", () => { expect(num(null)).toBe("n/a"); expect(pct(undefined)).toBe("n/a"); });
});

describe("lonlatText", () => {
  it("north east", () => expect(lonlatText([77.4508, 18.4447])).toBe("18.4447°N, 77.4508°E"));
  it("south west (Moon site)", () => expect(lonlatText([-137.5144, -89.4632])).toBe("89.4632°S, 137.5144°W"));
  it("missing", () => expect(lonlatText(null)).toBe("n/a"));
});

describe("parseLatLon", () => {
  it("reads lat, lon and returns [lon, lat]", () => expect(parseLatLon("18.4447, 77.4508")).toEqual([77.4508, 18.4447]));
  it("reads compass letters", () => expect(parseLatLon("89.46 S 137.51 W")).toEqual([-137.51, -89.46]));
  it("reads degree signs", () => expect(parseLatLon("18.4447°N, 77.4508°E")).toEqual([77.4508, 18.4447]));
  it("reads minus signs", () => expect(parseLatLon("-89.46, -137.51")).toEqual([-137.51, -89.46]));
  it("rejects one number", () => expect(parseLatLon("18.4")).toBeNull());
  it("rejects three numbers", () => expect(parseLatLon("1, 2, 3")).toBeNull());
  it("rejects words", () => expect(parseLatLon("hello")).toBeNull());
});

describe("seasonName", () => {
  it("matches the server's season names", () => {
    expect(seasonName(0)).toBe("northern spring"); expect(seasonName(89.9)).toBe("northern spring");
    expect(seasonName(90)).toBe("northern summer"); expect(seasonName(120)).toBe("northern summer");
    expect(seasonName(180)).toBe("northern autumn"); expect(seasonName(359.9)).toBe("northern winter");
  });
  it("out of range or missing", () => { expect(seasonName(360)).toBe("n/a"); expect(seasonName(-1)).toBe("n/a"); expect(seasonName("")).toBe("n/a"); });
});

describe("sentence", () => {
  it("adds a capital and a full stop", () => expect(sentence("typical conditions, not a forecast")).toBe("Typical conditions, not a forecast."));
  it("leaves a finished sentence alone", () => expect(sentence("Suit shielding is not modelled.")).toBe("Suit shielding is not modelled."));
  it("empty or missing", () => { expect(sentence("")).toBe(""); expect(sentence(null)).toBe(""); });
});
