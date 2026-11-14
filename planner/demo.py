import json
import time

from planner.route import Site

t = time.time()
site = Site()
print(f"loaded in {time.time() - t:.2f}s")
base = (77.4508, 18.4447)  # Octavia E. Butler landing site
stops = [(77.405, 18.470), (77.43, 18.485), (77.46, 18.47), (77.415, 18.43)]
t = time.time()
r = site.plan(base, stops)
print(f"planned in {time.time() - t:.2f}s")
print(json.dumps({k: v for k, v in r.items() if k != "path"}, indent=1))
print("path points:", len(r["path"]))
