"""
API Evaluation Report Generator
Reads eval_results.csv produced by eval_api.py and outputs:
  - Console summary (latency stats + success rate)
  - eval_report.png  (2-panel chart)

Usage: python eval_report.py [--csv FILE] [--out FILE]
"""

import argparse

import matplotlib.pyplot as plt
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_CSV = "eval_results.csv"
DEFAULT_OUT = "eval_report.png"


# ── Load & validate ───────────────────────────────────────────────────────────

def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"latency_s", "success", "travel_pace", "destination"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {missing}")
    df["success"] = df["success"].astype(str).str.lower() == "true"
    df["latency_s"] = pd.to_numeric(df["latency_s"], errors="coerce")
    return df


# ── Stats ─────────────────────────────────────────────────────────────────────

def print_summary(df: pd.DataFrame) -> None:
    total = len(df)
    ok = df["success"].sum()
    lat = df.loc[df["success"], "latency_s"].dropna()

    print("=" * 48)
    print("  API Evaluation Summary")
    print("=" * 48)
    print(f"  Total requests : {total}")
    print(f"  Success        : {ok}  ({100 * ok / total:.1f}%)")
    print(f"  Failure        : {total - ok}")
    if not lat.empty:
        sorted_lat = lat.sort_values()
        p95 = sorted_lat.iloc[int(len(sorted_lat) * 0.95)]
        print(f"  Latency avg    : {lat.mean():.3f} s")
        print(f"  Latency min    : {lat.min():.3f} s")
        print(f"  Latency max    : {lat.max():.3f} s")
        print(f"  Latency p95    : {p95:.3f} s")
        print(f"  Latency std    : {lat.std():.3f} s")
    print("=" * 48)


# ── Charts ────────────────────────────────────────────────────────────────────

PACE_ORDER  = ["relaxed", "moderate", "intensive"]
PACE_COLORS = ["#4C9BE8", "#F5A623", "#E85C5C"]

def build_charts(df: pd.DataFrame, out_path: str) -> None:
    lat_all = df["latency_s"].dropna()
    lat_ok  = df.loc[df["success"], "latency_s"].dropna()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Trip Planner API — Performance Report", fontsize=14, fontweight="bold", y=1.01)

    # ── Panel 1: Latency distribution histogram ────────────────────────────────
    ax1 = axes[0]
    n_bins = min(15, max(5, len(lat_all) // 3))
    ax1.hist(lat_all, bins=n_bins, color="#4C9BE8", edgecolor="white", alpha=0.85, label="All")
    if not lat_ok.empty:
        ax1.axvline(lat_ok.mean(), color="#E85C5C", linewidth=1.8,
                    linestyle="--", label=f"Mean {lat_ok.mean():.2f}s")
        p95 = lat_ok.sort_values().iloc[int(len(lat_ok) * 0.95)]
        ax1.axvline(p95, color="#F5A623", linewidth=1.5,
                    linestyle=":", label=f"p95  {p95:.2f}s")
    ax1.set_title("Response Time Distribution", fontsize=12)
    ax1.set_xlabel("Latency (s)")
    ax1.set_ylabel("Request count")
    ax1.legend(fontsize=9)
    ax1.grid(axis="y", alpha=0.3)

    # ── Panel 2: Avg latency by travel_pace ───────────────────────────────────
    ax2 = axes[1]
    pace_stats = (
        df[df["success"]]
        .groupby("travel_pace")["latency_s"]
        .agg(mean="mean", count="count")
        .reindex([p for p in PACE_ORDER if p in df["travel_pace"].unique()])
    )

    if pace_stats.empty:
        ax2.text(0.5, 0.5, "No successful requests", ha="center", va="center",
                 transform=ax2.transAxes)
    else:
        bars = ax2.bar(
            pace_stats.index,
            pace_stats["mean"],
            color=PACE_COLORS[: len(pace_stats)],
            edgecolor="white",
            width=0.5,
        )
        # Value labels on bars
        for bar, (_, row) in zip(bars, pace_stats.iterrows()):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                f"{row['mean']:.2f}s\n(n={int(row['count'])})",
                ha="center", va="bottom", fontsize=9,
            )
        ax2.set_title("Avg Response Time by Travel Pace", fontsize=12)
        ax2.set_xlabel("Travel Pace")
        ax2.set_ylabel("Avg Latency (s)")
        ax2.set_ylim(0, pace_stats["mean"].max() * 1.35)
        ax2.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"\nChart saved → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate API eval report from CSV")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Input CSV file")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output PNG file")
    args = parser.parse_args()

    df = load(args.csv)
    print_summary(df)
    build_charts(df, args.out)


if __name__ == "__main__":
    main()
