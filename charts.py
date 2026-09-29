"""Draw the VLSM plan as an address-space map, plus the classic hosts-per-prefix curve. Writes docs/*.png."""
import matplotlib.pyplot as plt

import subnet as s

net, prefix = s.ip_to_int("192.168.10.0"), 24
needs = [("Staff", 100), ("Students", 50), ("Servers", 20), ("Guest", 10), ("Mgmt", 5), ("WAN", 2)]
plan = s.vlsm(net, prefix, needs)

fig, ax = plt.subplots(figsize=(11, 2.8))
colors = plt.cm.tab10.colors
for i, (name, hosts, n, p) in enumerate(plan):
    start, size = n - net, 2 ** (32 - p)
    ax.barh(0, size, left=start, color=colors[i], edgecolor="white")
    ax.barh(0, hosts, left=start + 1, color="black", alpha=0.18, height=0.35)
    if size >= 16:
        ax.text(start + size / 2, 0.52, f"{name}\n/{p}", ha="center", va="bottom", fontsize=9)
    else:
        ax.text(start + size / 2, -0.45 - 0.35 * (i % 2), f"{name} /{p}", ha="right" if i % 2 == 0 else "left", va="top", fontsize=8)
used = sum(2 ** (32 - p) for *_, p in plan)
ax.barh(0, 256 - used, left=used, color="#dddddd", edgecolor="white")
ax.text(used + (256 - used) / 2, 0.52, "free", ha="center", va="bottom", fontsize=9, color="gray")
ax.set(xlim=(0, 256), ylim=(-1.2, 1.4), yticks=[], xlabel="Offset in 192.168.10.0/24 (dark stripe = hosts actually needed)")
ax.set_xticks(range(0, 257, 32))
ax.set_title("VLSM plan: 6 subnets packed into one /24 with 98% of addresses allocated")
for sp in ("top", "right", "left"):
    ax.spines[sp].set_visible(False)
fig.tight_layout(); fig.savefig("docs/vlsm_map.png", dpi=110)

fig, ax = plt.subplots(figsize=(9, 4))
prefixes = list(range(16, 31))
usable = [s.info(0, p)["usable"] for p in prefixes]
bars = ax.bar([f"/{p}" for p in prefixes], usable, color="#3a6ea5")
ax.bar_label(bars, fontsize=8, padding=2)
ax.set_yscale("log")
ax.set(title="Each extra prefix bit halves the usable hosts", ylabel="Usable hosts (log scale)")
fig.tight_layout(); fig.savefig("docs/hosts_per_prefix.png", dpi=110)
