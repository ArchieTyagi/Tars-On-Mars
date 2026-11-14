import { useMemo } from "react";
import { hm } from "../lib/format.js";
import { profile } from "../lib/route.js";

const W = 320;
const H = 72;

// Height along the walk. Move over it to see that spot on the map.
export default function Profile({ plan, cursor, setCursor }) {
  const p = useMemo(() => profile(plan.dist_m, plan.height_m, W, H), [plan]);
  if (p.points.length < 2) return null;

  const line = p.points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${W},${H} L0,${H} Z`;
  const xOf = (i) => (p.total > 0 ? ((plan.dist_m[i] - plan.dist_m[0]) / p.total) * W : 0);
  const yOf = (i) => (p.max > p.min ? H - ((plan.height_m[i] - p.min) / (p.max - p.min)) * H : H / 2);

  function move(e) {
    const r = e.currentTarget.getBoundingClientRect();
    if (r.width <= 0) return;
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    const want = plan.dist_m[0] + f * p.total;
    let lo = 0;
    let hi = plan.dist_m.length - 1;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (plan.dist_m[mid] < want) lo = mid + 1;
      else hi = mid;
    }
    setCursor(lo);
  }

  const ponr = plan.point_of_no_return;
  const c = cursor !== null && plan.dist_m[cursor] !== undefined ? cursor : null;

  return (
    <div className="profile">
      <div className="profile-top label">
        <span>{p.max.toFixed(1)} m</span>
        <span>Height along the walk</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="Height along the walk" onMouseMove={move} onMouseLeave={() => setCursor(null)}>
        <path d={area} className="profile-area" />
        <path d={line} className="profile-line" vectorEffect="non-scaling-stroke" />
        {plan.stop_arrivals.map((s) => (
          <line key={s.stop} x1={xOf(s.index)} x2={xOf(s.index)} y1="0" y2={H} className="profile-stop" vectorEffect="non-scaling-stroke" />
        ))}
        {ponr && <line x1={xOf(ponr.index)} x2={xOf(ponr.index)} y1="0" y2={H} className="profile-ponr" vectorEffect="non-scaling-stroke" />}
        {c !== null && <line x1={xOf(c)} x2={xOf(c)} y1="0" y2={H} className="profile-cursor" vectorEffect="non-scaling-stroke" />}
        {c !== null && <circle cx={xOf(c)} cy={yOf(c)} r="2.5" className="profile-dot" />}
      </svg>
      <div className="profile-top label">
        <span>{p.min.toFixed(1)} m</span>
        <span>{(p.total / 1000).toFixed(2)} km</span>
      </div>
      <p className="fine">
        {c !== null
          ? `${(plan.dist_m[c] / 1000).toFixed(2)} km walked, ${hm(plan.elapsed_h[c])} in, height ${plan.height_m[c]} m, slope ${plan.slope_deg[c]} deg.`
          : "Thin lines are your stops. Move over the chart to see that spot on the map."}
        {ponr ? " The red line is the point of no return." : ""}
      </p>
    </div>
  );
}
