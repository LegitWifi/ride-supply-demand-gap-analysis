"""Static charts (matplotlib) used in the notebook and README."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Validated categorical slots (light mode): 1 blue, 2 orange, 3 aqua
BLUE, ORANGE, AQUA = "#257de0", "#f47230", "#00b894"
GRAY, INK, INK2, GRID = "#c9c9c9", "#191919", "#666666", "#ececec"
STATUS_COLORS = {"Trip Completed": BLUE, "Cancelled": ORANGE, "No Cars Available": AQUA}
SEQ = ["#cce3fd", "#9dc8f7", "#6aabf1", "#338ced", "#2370cd", "#1757ac", "#0e3d7e"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 11, "axes.titlecolor": INK, "figure.dpi": 110,
})


def _grid(ax):
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def hourly_demand_supply(h, path=None):
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8), sharey=True)
    for ax, pp in zip(axes, ["City", "Airport"]):
        s = h[h.pickup_point == pp]
        ax.bar(s.hour, s.demand, width=0.8, color=GRAY, label="Requests (demand)")
        ax.bar(s.hour, s.supply, width=0.5, color=BLUE, label="Completed trips (supply)")
        ax.set_title(f"Pickup: {pp}", loc="left")
        ax.set_xticks(range(0, 24, 2)); ax.set_xlabel("Hour of request")
        _grid(ax)
    axes[0].set_ylabel("Requests over 5 days")
    axes[0].legend(frameon=False, loc="upper right")
    fig.suptitle("Demand vs supply by hour: the gap opens at different times for city and airport pickups",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout()
    if path: fig.savefig(path, bbox_inches="tight")
    return fig


def status_mix(t, slots, path=None):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, pp in zip(axes, ["City", "Airport"]):
        s = t[t.pickup_point == pp].set_index("slot").reindex(slots)
        x = np.arange(len(slots)); bottom = np.zeros(len(slots))
        for st, col in [("completed", "Trip Completed"), ("cancelled_n", "Cancelled"), ("no_cars_n", "No Cars Available")]:
            v = s[st].values
            ax.bar(x, v, bottom=bottom, color=STATUS_COLORS[col], width=0.62, label=col, edgecolor="white", linewidth=2)
            bottom += v
        for i, (tot, f) in enumerate(zip(s.requests.values, s.fulfilment_pct.values)):
            ax.text(i, tot + 25, f"{f:.0f}% done", ha="center", fontsize=9, color=INK)
        ax.set_xticks(x); ax.set_xticklabels([sl.split(" (")[0].replace(" ", "\n", 1) for sl in slots], fontsize=9)
        ax.set_title(f"Pickup: {pp}", loc="left"); _grid(ax)
    axes[0].set_ylabel("Requests over 5 days")
    axes[1].legend(frameon=False, loc="upper left")
    fig.suptitle("What happens to requests in each time slot", x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout()
    if path: fig.savefig(path, bbox_inches="tight")
    return fig


def fulfilment_heatmap(t, slots, path=None):
    pv = t.pivot(index="pickup_point", columns="slot", values="fulfilment_pct").reindex(columns=slots).loc[["City", "Airport"]]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", SEQ)
    fig, ax = plt.subplots(figsize=(10, 2.6))
    im = ax.imshow(pv.values, cmap=cmap, vmin=0, vmax=100, aspect="auto")
    for i in range(pv.shape[0]):
        for j in range(pv.shape[1]):
            v = pv.values[i, j]
            ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=11, fontweight="bold",
                    color="white" if v > 55 else INK)
    ax.set_xticks(range(len(slots))); ax.set_xticklabels([s.replace(" (", "\n(") for s in slots], fontsize=9)
    ax.set_yticks([0, 1]); ax.set_yticklabels(["City pickup", "Airport pickup"])
    for sp in ax.spines.values(): sp.set_visible(False)
    ax.set_title("Fulfilment % (completed / requested) by pickup point and time slot", loc="left")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02).outline.set_visible(False)
    fig.tight_layout()
    if path: fig.savefig(path, bbox_inches="tight")
    return fig


def imbalance(di, path=None):
    fig, ax = plt.subplots(figsize=(8, 3.4))
    x = np.arange(len(di))
    ax.bar(x, di.city_airport_ratio, color=BLUE, width=0.55)
    ax.axhline(1, color=INK2, lw=1, ls="--", label="1.0 = balanced in both directions")
    ax.legend(frameon=False, loc="upper right", fontsize=8.5)
    ax.set_ylim(0, di.city_airport_ratio.max() * 1.15)
    for i, v in enumerate(di.city_airport_ratio):
        ax.text(i, v + 0.08, f"{v:.2f}x", ha="center", fontsize=10, color=INK)
    ax.set_xticks(x); ax.set_xticklabels([s.split(" (")[0] for s in di.slot], fontsize=9)
    ax.set_ylabel("City-to-airport requests\nper airport-to-city request"); _grid(ax)
    ax.set_title("Demand runs one way: to the airport in the morning, from it in the evening", loc="left")
    fig.tight_layout()
    if path: fig.savefig(path, bbox_inches="tight")
    return fig


def driver_quintiles(q, path=None):
    fig, ax = plt.subplots(figsize=(8, 3.4))
    x = np.arange(len(q))
    ax.bar(x, q.pct_of_all_cancels, color=BLUE, width=0.55)
    for i, (v, r) in enumerate(zip(q.pct_of_all_cancels, q.cancel_rate_pct)):
        ax.text(i, v + 0.8, f"{v:.1f}%\n(cancel rate {r:.0f}%)", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(x); ax.set_xticklabels([f"Q{i}\n{'most cancels' if i == 1 else ('fewest' if i == 5 else '')}" for i in q.quintile], fontsize=9)
    ax.set_ylabel("Share of all driver cancellations"); ax.set_ylim(0, max(q.pct_of_all_cancels) * 1.35); _grid(ax)
    ax.set_title("Drivers grouped into fifths by cancellation rate (60 drivers each)", loc="left")
    fig.tight_layout()
    if path: fig.savefig(path, bbox_inches="tight")
    return fig
