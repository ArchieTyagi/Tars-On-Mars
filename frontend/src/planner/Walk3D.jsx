import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { hm } from "../lib/format.js";
import { KEY_STYLE, hudAt, indexAtTime, routeKeys } from "../lib/route.js";

// The real terrain in 3D with the planned route on it, and a walk along the route with the numbers
// an astronaut would want in the helmet: oxygen, time home, slope ahead, radio.

async function loadTerrain(siteId) {
  const r = await fetch(`/api/terrain?site=${encodeURIComponent(siteId)}&step=4`);
  if (!r.ok) throw new Error("The server did not send the height grid.");
  const rows = Number(r.headers.get("X-Rows"));
  const cols = Number(r.headers.get("X-Cols"));
  const dx = Number(r.headers.get("X-Dx-M"));
  const dy = Number(r.headers.get("X-Dy-M"));
  const h = new Float32Array(await r.arrayBuffer());
  if (!(rows > 1 && cols > 1 && dx > 0 && dy > 0) || h.length !== rows * cols) throw new Error("The height grid from the server is not the size it says.");
  return { h, rows, cols, dx, dy };
}

function loadImg(src) {
  return new Promise((ok, bad) => {
    const i = new Image();
    i.onload = () => ok(i);
    i.onerror = () => bad(new Error("A ground picture could not be loaded."));
    i.src = src;
  });
}

// the ground picture, with the walk zones painted over it when that layer is on
async function makeTexture(groundUrl, zonesUrl, maxSize) {
  const ground = await loadImg(groundUrl);
  const zones = zonesUrl ? await loadImg(zonesUrl).catch(() => null) : null;
  const size = Math.min(maxSize, Math.max(ground.width, ground.height));
  const c = document.createElement("canvas");
  c.width = size;
  c.height = size;
  const ctx = c.getContext("2d");
  ctx.drawImage(ground, 0, 0, size, size);
  if (zones) {
    ctx.globalAlpha = 0.7;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(zones, 0, 0, size, size);
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

export default function Walk3D({ site, geo, base, stops, plan, routeMode, textureUrl, zonesUrl }) {
  const box = useRef(null);
  const world = useRef(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(600); // mission seconds per real second
  const [i, setI] = useState(0); // index along the path
  const [follow, setFollow] = useState(true);
  const [stretch, setStretch] = useState(1); // heights drawn 1x, 2x or 3x
  const iRef = useRef(0);
  const tRef = useRef(0);
  iRef.current = i;
  const moon = site.body === "moon";

  // ---- scene, once per site -----------------------------------------------------
  useEffect(() => {
    let dead = false;
    const el = box.current;
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      setError("This browser cannot show 3D here (WebGL is switched off). The 2D map has everything the 3D view has.");
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(el.clientWidth || 1, el.clientHeight || 1);
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const sky = moon ? "#010101" : "#b89479";
    scene.background = new THREE.Color(sky);
    const span = Math.max(geo.width, geo.height);
    if (!moon) scene.fog = new THREE.Fog(sky, span * 0.5, span * 1.9);
    const camera = new THREE.PerspectiveCamera(55, (el.clientWidth || 1) / (el.clientHeight || 1), 1, span * 6);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.maxPolarAngle = Math.PI * 0.49;
    controls.maxDistance = span * 2;
    scene.add(new THREE.HemisphereLight("#ffffff", moon ? "#202020" : "#5a3a2a", moon ? 0.9 : 1.25));
    const sun = new THREE.DirectionalLight("#ffffff", 1.5);
    sun.position.set(-span, span * 0.8, -span * 0.6);
    scene.add(sun);

    const W = { renderer, scene, camera, controls, span, group: null, pts: null, astro: null, mesh: null, T: null };
    world.current = W;

    loadTerrain(site.id)
      .then((T) => {
        if (dead) return;
        const width = (T.cols - 1) * T.dx;
        const depth = (T.rows - 1) * T.dy;
        let min = Infinity;
        for (let k = 0; k < T.h.length; k++) if (T.h[k] < min) min = T.h[k];
        const geom = new THREE.PlaneGeometry(width, depth, T.cols - 1, T.rows - 1);
        geom.rotateX(-Math.PI / 2); // lay it flat: x east, y up, z south
        const pos = geom.attributes.position;
        const uv = geom.attributes.uv;
        // the grid points are the centers of grid squares, so the picture (which covers the whole box)
        // has to be shifted in by half a square
        const half = site.grid_m / 2;
        for (let r = 0; r < T.rows; r++) {
          for (let c = 0; c < T.cols; c++) {
            const k = r * T.cols + c;
            pos.setY(k, T.h[k] - min);
            uv.setXY(k, (half + c * T.dx) / geo.width, 1 - (half + r * T.dy) / geo.height);
          }
        }
        geom.computeVertexNormals();
        const mesh = new THREE.Mesh(geom, new THREE.MeshStandardMaterial({ color: "#8a8a86", roughness: 1, metalness: 0 }));
        scene.add(mesh);
        const e = site.extent_xy;
        // map meters -> a spot on the terrain (height read from the grid, between its four nearest points)
        const toXYZ = ([x, y], lift, scale) => {
          const c = Math.min(T.cols - 1, Math.max(0, (x - (e.left + half)) / T.dx));
          const r = Math.min(T.rows - 1, Math.max(0, (e.top - half - y) / T.dy));
          const c0 = Math.floor(c), r0 = Math.floor(r);
          const c1 = Math.min(c0 + 1, T.cols - 1), r1 = Math.min(r0 + 1, T.rows - 1);
          const tx = c - c0, tz = r - r0;
          const H = (rr, cc) => T.h[rr * T.cols + cc];
          const hgt = (H(r0, c0) * (1 - tx) + H(r0, c1) * tx) * (1 - tz) + (H(r1, c0) * (1 - tx) + H(r1, c1) * tx) * tz;
          return new THREE.Vector3(c * T.dx - width / 2, (hgt - min) * scale + lift, r * T.dy - depth / 2);
        };
        Object.assign(W, { T, mesh, toXYZ, width, depth });
        camera.position.set(0, span * 0.5, depth * 0.8);
        controls.target.set(0, 0, 0);
        controls.update();
        setReady(true);
      })
      .catch((err) => {
        if (!dead) setError(err.message);
      });

    let raf;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
    };
    loop();
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth || 1;
      const h = el.clientHeight || 1;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    });
    ro.observe(el);

    return () => {
      dead = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      scene.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) {
          if (o.material.map) o.material.map.dispose();
          o.material.dispose();
        }
      });
      renderer.dispose();
      if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
      world.current = null;
      setReady(false);
    };
  }, [site, geo, moon]);

  // ---- ground picture ---------------------------------------------------------------
  useEffect(() => {
    const W = world.current;
    if (!ready || !W || !textureUrl) return;
    let dead = false;
    const max = Math.min(4096, W.renderer.capabilities.maxTextureSize || 2048);
    makeTexture(textureUrl, zonesUrl, max)
      .then((t) => {
        if (dead || !world.current) {
          t.dispose();
          return;
        }
        const mat = W.mesh.material;
        if (mat.map) mat.map.dispose();
        mat.map = t;
        mat.color.set("#ffffff");
        mat.needsUpdate = true;
      })
      .catch((err) => {
        if (!dead) setError(err.message);
      });
    return () => {
      dead = true;
    };
  }, [ready, textureUrl, zonesUrl]);

  // ---- heights drawn taller ------------------------------------------------------------
  useEffect(() => {
    const W = world.current;
    if (ready && W && W.mesh) W.mesh.scale.y = stretch;
  }, [ready, stretch]);

  // ---- base, stops, route, astronaut -----------------------------------------------------
  useEffect(() => {
    const W = world.current;
    if (!ready || !W) return;
    if (W.group) {
      W.scene.remove(W.group);
      W.group.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) o.material.dispose();
      });
    }
    const u = W.span / 5000; // sizes that read the same on a 5 km and a 16 km site
    const grp = new THREE.Group();
    // base = a cube on a tall pole, stops = a diamond on a shorter one
    const pin = (xy, height, isBase) => {
      const color = "#f1f0ea";
      const p = W.toXYZ(xy, 0, stretch);
      const pole = new THREE.Mesh(new THREE.CylinderGeometry(1.5 * u, 1.5 * u, height), new THREE.MeshBasicMaterial({ color }));
      pole.position.copy(p).add(new THREE.Vector3(0, height / 2, 0));
      const shape = isBase ? new THREE.BoxGeometry(18 * u, 18 * u, 18 * u) : new THREE.OctahedronGeometry(11 * u);
      const head = new THREE.Mesh(shape, new THREE.MeshBasicMaterial({ color }));
      head.position.copy(p).add(new THREE.Vector3(0, height, 0));
      grp.add(pole, head);
    };
    if (base) pin(base.xy, 90 * u, true);
    stops.forEach((s) => pin(s.xy, 60 * u, false));

    W.pts = null;
    W.astro = null;
    if (plan) {
      const pts = plan.path_xy.map((xy) => W.toXYZ(xy, 3 * u, stretch));
      W.pts = pts;
      const keys = routeKeys(plan, routeMode);
      const colors = [];
      for (const k of keys) {
        const c = new THREE.Color(KEY_STYLE[k].color);
        colors.push(c.r, c.g, c.b);
      }
      const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
      lineGeo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
      grp.add(new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ vertexColors: true })));
      // a ribbon under the thin line so the route reads from far away
      if (pts.length >= 2) {
        const thin = pts.filter((_, k) => k % 3 === 0 || k === pts.length - 1);
        const curve = new THREE.CatmullRomCurve3(thin.length >= 2 ? thin : pts);
        const tube = new THREE.Mesh(
          new THREE.TubeGeometry(curve, Math.max(8, pts.length), 3.5 * u, 6),
          new THREE.MeshBasicMaterial({ color: "#f1f0ea", transparent: true, opacity: 0.4 })
        );
        grp.add(tube);
      }
      const p = plan.point_of_no_return;
      if (p && pts[p.index]) {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(30 * u, 4 * u, 8, 32), new THREE.MeshBasicMaterial({ color: "#ff3b30" }));
        ring.position.copy(pts[p.index]).add(new THREE.Vector3(0, 4 * u, 0));
        ring.rotation.x = Math.PI / 2;
        grp.add(ring);
      }
      const astro = new THREE.Group();
      const body = new THREE.Mesh(new THREE.CapsuleGeometry(6 * u, 14 * u, 4, 8), new THREE.MeshStandardMaterial({ color: "#f1f0ea" }));
      body.position.y = 13 * u;
      const visor = new THREE.Mesh(new THREE.SphereGeometry(4.5 * u), new THREE.MeshStandardMaterial({ color: "#f5a623", metalness: 0.6, roughness: 0.2 }));
      visor.position.set(0, 24 * u, -3 * u);
      astro.add(body, visor);
      grp.add(astro);
      W.astro = astro;
    }
    W.scene.add(grp);
    W.group = grp;
  }, [ready, plan, base, stops, routeMode, stretch]);

  // a new plan starts the walk from the beginning
  useEffect(() => {
    setI(0);
    tRef.current = 0;
    setPlaying(false);
  }, [plan]);

  // ---- put the astronaut and the camera at point i ------------------------------------------
  useEffect(() => {
    const W = world.current;
    if (!ready || !W || !W.pts || !W.astro) return;
    const k = Math.min(i, W.pts.length - 1);
    const u = W.span / 5000;
    const p = W.pts[k];
    const q = W.pts[Math.min(k + 8, W.pts.length - 1)];
    const back = W.pts[Math.max(k - 8, 0)];
    W.astro.position.copy(p).add(new THREE.Vector3(0, -3 * u, 0));
    const dir = q.clone().sub(p).setY(0);
    if (dir.lengthSq() === 0) dir.copy(p.clone().sub(back).setY(0)); // at the very end, keep facing the way we came
    if (dir.lengthSq() > 0) {
      dir.normalize();
      W.astro.lookAt(p.x + dir.x, W.astro.position.y, p.z + dir.z);
      if (follow) {
        W.camera.position.copy(p).add(dir.clone().multiplyScalar(-140 * u)).add(new THREE.Vector3(0, 70 * u, 0));
        W.controls.target.copy(p).add(dir.clone().multiplyScalar(60 * u));
      }
    }
  }, [i, ready, follow, plan, stretch, routeMode, base, stops]);

  // ---- play: move along the path at `speed` mission seconds per real second ------------------
  useEffect(() => {
    if (!playing || !plan) return;
    const el = plan.elapsed_h;
    const end = el[el.length - 1];
    let last = performance.now();
    let raf;
    const tick = (now) => {
      tRef.current += (((now - last) / 1000) * speed) / 3600;
      last = now;
      if (tRef.current >= end) {
        tRef.current = end;
        setI(el.length - 1);
        setPlaying(false);
        return;
      }
      const k = indexAtTime(el, tRef.current);
      if (k !== iRef.current) setI(k);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, plan]);

  const hud = plan ? hudAt(plan, i) : null;
  const atEnd = plan ? i >= plan.path.length - 1 : false;

  function toggle() {
    if (!plan) return;
    if (atEnd) {
      setI(0);
      tRef.current = 0;
    }
    setPlaying(!playing);
  }
  function scrub(e) {
    const k = Number(e.target.value);
    setPlaying(false);
    setI(k);
    tRef.current = plan.elapsed_h[k];
  }

  return (
    <div className="walk3d">
      <div ref={box} className="walk3d-canvas" />
      {error && <div className="stage-msg"><p className="label">3D view</p><p>{error}</p></div>}
      {!error && !ready && <div className="stage-msg"><p className="label">Loading the terrain</p></div>}
      {!error && ready && !plan && <div className="walk3d-note label">Plan a walk to follow it here. Drag to turn, scroll to zoom.</div>}
      {!error && ready && (
        <label className="stretch label">
          Heights drawn
          <select value={stretch} onChange={(e) => setStretch(Number(e.target.value))}>
            <option value={1}>true to scale</option>
            <option value={2}>2x taller</option>
            <option value={3}>3x taller</option>
          </select>
        </label>
      )}
      {!error && hud && (
        <>
          <div className={`hud ${hud.state}`}>
            <div><span>Mission time</span><b>{hm(hud.elapsed)} of {hm(hud.total)}</b></div>
            <div><span>Oxygen supply left</span><b>{hm(hud.supplyLeft)}</b></div>
            <div className="o2bar"><i style={{ width: `${hud.supplyShare * 100}%` }} /></div>
            <div><span>Walk home from here</span><b>{hm(hud.home)}</b></div>
            <div><span>Spare if you turn back</span><b>{hm(hud.margin)}</b></div>
            <div><span>Steepest in the next 60 m</span><b>{hud.steepestAhead === null ? "n/a" : `${hud.steepestAhead} deg`}</b></div>
            <div><span>Height</span><b>{hud.height} m</b></div>
            <div><span>Walked</span><b>{(hud.walked / 1000).toFixed(2)} km</b></div>
            <div><span>Radio to base</span><b className={hud.inContact ? "" : "warnc"}>{hud.inContact ? "in contact" : "no direct radio"}</b></div>
            {hud.dark !== null && <div><span>Sun</span><b className={hud.dark ? "warnc" : ""}>{hud.dark ? "down" : "up"}</b></div>}
          </div>
          {hud.state === "over" && <div className="hudalert over" role="alert"><strong>Past the point of no return</strong><span>Not enough usable oxygen to walk home from here</span></div>}
          {hud.state === "tight" && <div className="hudalert tight" role="status"><strong>Low margin</strong><span>Under 1 h to spare if you turn back now</span></div>}
          <div className="walkbar">
            <button className="btn small" onClick={toggle}>{playing ? "Pause" : atEnd ? "Walk again" : "Walk"}</button>
            <input type="range" min="0" max={plan.path.length - 1} value={i} onChange={scrub} aria-label="Position along the walk" />
            <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))} aria-label="Playback speed">
              <option value={120}>2 min per second</option>
              <option value={600}>10 min per second</option>
              <option value={1800}>30 min per second</option>
            </select>
            <label className="check"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} /><span>Follow</span></label>
          </div>
        </>
      )}
    </div>
  );
}
