import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource, ListedColormap

from planner.route import Site

site = Site()
base = (77.4508, 18.4447)
stops = [(77.405, 18.470), (77.43, 18.485), (77.46, 18.47), (77.415, 18.43)]
r = site.plan(base, stops)
shade = LightSource(315, 45).hillshade(np.nan_to_num(site.height), dx=4, dy=4, vert_exag=2)
fig, ax = plt.subplots(figsize=(9, 9))
ax.imshow(shade, cmap="gray")
z = np.ma.masked_where(site.zone == 0, site.zone)
ax.imshow(z, cmap=ListedColormap(["#f5a623", "#d0021b"]), alpha=0.55, vmin=1, vmax=2)
rc = np.array([site.lonlat_to_cell(*p) for p in r["path"]])
ax.plot(rc[:, 1], rc[:, 0], color="#00e5ff", lw=1.6)
for i, p in enumerate([base] + stops):
    rr, cc = site.lonlat_to_cell(*p)
    ax.scatter(cc, rr, s=90, c="white" if i == 0 else "#00e5ff", edgecolors="k", zorder=5)
    ax.annotate("BASE" if i == 0 else str(i), (cc, rr), xytext=(6, 6), textcoords="offset points",
                color="white", fontsize=11, weight="bold")
ax.set_title(f"{r['km']} km, {r['hours']} h, max {r['max_slope']} deg | orange = caution, red = no-go")
ax.axis("off")
fig.savefig("out/route_demo.png", dpi=110, bbox_inches="tight")
print("ok")
