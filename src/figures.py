"""Draw the two figures from the CSVs written by src/market_power.py.

Usage:
    python src/figures.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "results"


def plots(monthly, bins):
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True)
    panels = [("CAISO", "ice_onpeak", "pcomp_onpeak", "CAISO, on-peak hours (ICE SP15 day-ahead index)"),
              ("ERCOT", "price", "pcomp", "ERCOT, all hours (day-ahead hub average)")]
    for ax, (name, pcol, ccol, title) in zip(axes, panels):
        m = monthly[monthly["market"] == name]
        x = m["ym"].dt.to_timestamp()
        ax.plot(x, m[pcol], color="#1f4e79", lw=1.8, label="Market price")
        ax.plot(x, m[ccol], color="#c55a11", lw=1.8, ls="--", label="Competitive benchmark")
        ax.set_ylabel("$ per MWh, monthly mean")
        ax.set_title(title, loc="left", fontsize=11)
        ax.grid(alpha=0.3)
        ax.set_ylim(0, min(m[[pcol, ccol]].max().max() * 1.05, 300))
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "price_vs_benchmark.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, name in zip(axes, ["CAISO", "ERCOT"]):
        b = bins[bins["market"] == name]
        for period, col in zip(sorted(b["period"].unique()), ["#7f7f7f", "#1f4e79"][-b["period"].nunique():]):
            bb = b[b["period"] == period]
            ax.plot(bb["bin"] / 1000 + 1.25, bb["lerner"], marker="o", color=col, label=f"Summers {period}")
        ax.set_title(name, loc="left", fontsize=11)
        ax.set_xlabel("Demand left for fossil plants (GW)")
        ax.grid(alpha=0.3)
        ax.legend(frameon=False)
    axes[0].set_ylabel("Mean hourly (P - Pcomp) / P, negatives at 0")
    fig.tight_layout()
    fig.savefig(OUT / "lerner_by_residual_demand.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    monthly = pd.read_csv(OUT / "monthly_benchmark.csv")
    monthly["ym"] = pd.PeriodIndex(monthly["ym"], freq="M")
    bins = pd.read_csv(OUT / "lerner_by_residual_demand.csv")
    print(f"loaded {len(monthly)} market-months and {len(bins)} residual-demand bins")
    plots(monthly, bins)
    print("wrote results/price_vs_benchmark.png and results/lerner_by_residual_demand.png")
