"""Plan random trips and check rules that must hold for every single one.

For each trip (random base, 1 to 4 stops, random oxygen, reserve, speed, stop time, slope
slider, and on Mars a random season and start time) the answer is checked against the map and
against plain arithmetic: the route never touches NO-GO ground or a data gap, never reaches a
slope limit, distance equals the true distance on the sphere, time never runs backwards, a
turn-back point exists exactly when oxygen runs short, the loop ends at base and climbs as much
as it descends, radiation is rate x hours, and the same input gives the same answer.

Run: python -m validation.random_trips jezero 40 1      (site, how many trips, random seed)
"""
import json
import math
import random
import sys
import time

import numpy as np
from fastapi.testclient import TestClient
from api.main import app, site as get_site
from pipeline.costmap import NOGO
c=TestClient(app, raise_server_exceptions=False)
SITE = sys.argv[1] if len(sys.argv) > 1 else "jezero"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
rnd = random.Random(seed)
s0=get_site(None,SITE); R=s0.radius
def gc(a,b):
    (l1,p1),(l2,p2)=[(math.radians(u),math.radians(v)) for u,v in (a,b)]
    h=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin((l2-l1)/2)**2
    return 2*R*math.asin(math.sqrt(min(1,h)))
go=np.argwhere(s0.zone!=NOGO)
fails=[]; n_ok=n_422=0; t0=time.time()
for trial in range(N):
    base_cell=go[rnd.randrange(len(go))]
    # stops within ~1.5 km of base so most trips are plausible
    k=rnd.randint(1,4); stops=[]
    for _ in range(k):
        d=rnd.randint(20,int(1500/s0.dy)); a=rnd.random()*2*math.pi
        r_,c_=int(base_cell[0]+d*math.sin(a)), int(base_cell[1]+d*math.cos(a))
        r_=min(max(r_,0),s0.zone.shape[0]-1); c_=min(max(c_,0),s0.zone.shape[1]-1)
        stops.append(list(s0.cell_to_lonlat(r_,c_)))
    body={"site":SITE,"base":list(s0.cell_to_lonlat(*base_cell)),"stops":stops,
          "o2_hours":rnd.choice([2,4,8]),"o2_reserve":rnd.choice([0,0.25,0.5]),"walk_speed_kmh":rnd.choice([1,2,3.5]),
          "stop_minutes":rnd.choice([0,15,45]),"slope_limit":rnd.choice([None,12,20,30])}
    if SITE=="jezero" and rnd.random()<0.5: body.update(ls=rnd.uniform(0,359.9),start_ltst_h=rnd.uniform(0,23.9))
    r=c.post("/api/plan",json=body)
    if r.status_code==422:
        n_422+=1; msg=r.json()["detail"]
        if not any(x in msg for x in ("NO-GO","no safe way","outside the map","boxed in","same spot")): fails.append(("odd 422",msg))
        continue
    if r.status_code!=200: fails.append(("status",r.status_code,r.text[:200])); continue
    j=r.json(); n_ok+=1
    s=get_site(body["slope_limit"],SITE).with_settings(**{k:body[k] for k in ("o2_hours","o2_reserve","walk_speed_kmh","stop_minutes")})
    P=j["path"]; cells=np.array([s.lonlat_to_cell(*p) for p in P]); n=len(P)
    def bad(what): fails.append((trial,what,json.dumps(body)[:300]))
    if np.abs(np.diff(cells,axis=0)).max()>1: bad("path jumps")
    if (s.zone[cells[:,0],cells[:,1]]==NOGO).any(): bad("path on NO-GO")
    sl=s.slope[cells[:,0],cells[:,1]]
    if not np.isfinite(sl).all(): bad("path over a data gap")
    if (sl>=s.limit[cells[:,0],cells[:,1]]).any(): bad("path at/over slope limit")
    d=sum(gc(P[i],P[i+1]) for i in range(n-1))/1000
    if abs(d-j["km"])>max(0.01,0.003*d): bad(f"km {j['km']} vs geodesic {d:.3f}")
    spd=body["walk_speed_kmh"]*1000; kk=s.rules["slope_slowdown_per_deg"]
    wh=sum(gc(P[i],P[i+1])/spd*(1+kk*(sl[i]+sl[i+1])/2) for i in range(n-1))
    if abs(wh-j["walk_hours"])>max(0.02,0.005*wh): bad(f"walk_hours {j['walk_hours']} vs {wh:.3f}")
    sh=body["stop_minutes"]/60*len(stops)
    if abs(j["hours"]-(j["walk_hours"]+sh))>0.02: bad("hours != walk+stops")
    el=np.array(j["elapsed_h"]); hm=np.array([x if x is not None else np.inf for x in j["home_h"]])
    if len(el)!=n or len(hm)!=n or len(j["slope_deg"])!=n: bad("per-point lengths")
    if (np.diff(el)< -1e-9).any(): bad("elapsed goes backwards")
    if abs(el[-1]-j["hours"])>0.03: bad(f"elapsed end {el[-1]} vs hours {j['hours']}")
    if hm[0]>1e-6 or hm[-1]>1e-6: bad("home time at base not 0")
    usable=body["o2_hours"]*(1-body["o2_reserve"])
    if abs(j["usable_o2_h"]-usable)>0.01: bad("usable")
    if j["o2_ok"]!=(j["hours"]<=usable+1e-9) and abs(j["hours"]-usable)>0.01: bad("o2_ok wrong")
    mg=usable-el-hm
    pn=j["point_of_no_return"]
    if j["o2_ok"] and pn: bad("o2 ok but has point of no return")
    if pn:
        i=pn["index"]
        if not (mg[i]<1e-6 and (i==0 or (mg[:i]>=-1e-6).all())): bad("point of no return misplaced")
    if not j["o2_ok"] and not pn: bad("not enough oxygen but no turn-back point")
    if sorted(j["order"])!=list(range(1,len(stops)+1)): bad("order not a permutation")
    stop_cells=[tuple(s.lonlat_to_cell(*st)) for st in stops]
    for a in j["stop_arrivals"]:
        if tuple(cells[a["index"]])!=stop_cells[a["stop"]-1]: bad("stop arrival index not at the stop")
    if tuple(cells[0])!=tuple(s.lonlat_to_cell(*body["base"])) or tuple(cells[-1])!=tuple(cells[0]): bad("loop not closed at base")
    rc=j["radio"]
    if "in_contact" in rc and len(rc["in_contact"])!=n: bad("radio length")
    if "in_contact" in rc and not rc["in_contact"][0]: bad("no radio at base itself")
    if j["light"]:
        if len(j["light"]["dark"])!=n: bad("light length")
        if j["light"]["sunset_before_home"] and j["light"]["starts_in_dark"]: bad("sunset+starts dark")
    if j["weather"] and len(j["weather"].get("per_point",{}).get("air_c",[]) or [])not in (0,n): bad("weather length")
    h=j["height_m"]; dm=j["dist_m"]; e=j["elevation"]
    if len(h)!=n or len(dm)!=n: bad("profile lengths")
    if h[0]!=h[-1] or abs(e["climb_m"]-e["descent_m"])>0.11: bad(f"loop climb {e['climb_m']} != descent {e['descent_m']}")
    if any(b_<a_ for a_,b_ in zip(dm,dm[1:])) or abs(dm[-1]/1000-j["km"])>0.011: bad("dist profile")
    if e["highest_m"]!=max(h) or e["lowest_m"]!=min(h): bad("highest/lowest")
    hh=s.height[cells[:,0],cells[:,1]]
    if np.abs(np.array(h)-hh).max()>0.051: bad("height profile not the map's height")
    rate={"mars":640.0,"moon":1369.0}[s.body]/24
    if abs(j["radiation"]["dose_usv"]-rate*j["hours"])>0.05+rate*0.005: bad("radiation dose")
    if j["weather"] and not j["weather"]["sky"]: bad("no sky with weather")
    if abs(sum(l["climb_m"] for l in j["legs"])-e["climb_m"])>0.6*len(j["legs"]): bad("leg climbs")
    if trial%5==0:
        r2=c.post("/api/plan",json=body).json()
        if r2["path"]!=j["path"] or r2["hours"]!=j["hours"]: bad("not deterministic")
print(f"{SITE}: {N} random trips in {time.time()-t0:.0f}s | planned {n_ok}, refused with a clear reason {n_422} | rule breaks: {len(fails)}")
for f in fails[:12]:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
