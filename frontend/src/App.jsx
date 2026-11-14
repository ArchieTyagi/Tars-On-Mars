import { Component, lazy, Suspense, useCallback, useEffect, useState } from "react";
import Landing from "./landing/Landing.jsx";
import { routeOf } from "./lib/router.js";

// The planner brings the map and the 3D code with it, so it is only downloaded when someone opens it.
const Planner = lazy(() => import("./planner/Planner.jsx"));

class Catch extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="fullmsg">
        <p className="label">Something broke</p>
        <h1>The planner stopped.</h1>
        <p>Reload the page to start it again. Your base and stops are not saved.</p>
        <button className="btn" onClick={() => window.location.reload()}>Reload</button>
      </main>
    );
  }
}

export default function App() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const go = useCallback((to) => {
    if (to !== window.location.pathname) window.history.pushState(null, "", to);
    setPath(to);
    window.scrollTo(0, 0);
  }, []);

  const route = routeOf(path);

  useEffect(() => {
    document.title = route === "planner" ? "Route planner · TARS on Mars" : "TARS on Mars";
  }, [route]);

  if (route === "landing") return <Landing onOpen={() => go("/planner")} />;
  if (route === "planner") {
    return (
      <Catch>
        <Suspense fallback={<main className="fullmsg"><p className="label">Loading the planner</p></main>}>
          <Planner onHome={() => go("/")} />
        </Suspense>
      </Catch>
    );
  }
  return (
    <main className="fullmsg">
      <p className="label">404</p>
      <h1>No such page.</h1>
      <button className="btn" onClick={() => go("/")}>Back to the front page</button>
    </main>
  );
}
