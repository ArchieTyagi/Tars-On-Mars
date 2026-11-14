import { describe, expect, it } from "vitest";
import { routeOf } from "./router.js";

describe("routeOf", () => {
  it("front page", () => { expect(routeOf("/")).toBe("landing"); expect(routeOf("")).toBe("landing"); expect(routeOf(undefined)).toBe("landing"); });
  it("planner, with or without a trailing slash", () => { expect(routeOf("/planner")).toBe("planner"); expect(routeOf("/planner/")).toBe("planner"); });
  it("anything else is a missing page, not a blank one", () => { expect(routeOf("/plan")).toBe("missing"); expect(routeOf("/planner/x")).toBe("missing"); });
});
