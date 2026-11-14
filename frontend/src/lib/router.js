// Two pages, so no routing library: "/" is the front page, "/planner" is the route planner.
// The python server sends index.html for any address that is not a file, so a refresh works on both.

export function routeOf(pathname) {
  const p = (pathname || "/").replace(/\/+$/, "") || "/";
  if (p === "/") return "landing";
  if (p === "/planner") return "planner";
  return "missing";
}
