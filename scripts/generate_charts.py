#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(BASE_DIR, "results")

print(f"Reading from: {RESULTS_DIR}")

summary = pd.read_csv(os.path.join(RESULTS_DIR, "summary.csv"))
raw     = pd.read_csv(os.path.join(RESULTS_DIR, "raw_results.csv"))
raw     = raw[raw["warmup"] == False]

print("Summary loaded:")
print(summary.to_string(index=False))
print(f"\nRaw rows (excl warmup): {len(raw)}")

# ── Colours ───────────────────────────────────────────────────────────────────
C_DEF = "#e07b54"
C_OPT = "#01696f"

users_vals = sorted(summary["users"].unique())
x     = np.arange(len(users_vals))
width = 0.35

# ── 1. Grouped Bar — mean J/1000 requests ─────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
for i, (cfg, color) in enumerate([("default", C_DEF), ("optimized", C_OPT)]):
    sub   = summary[summary["config"] == cfg].set_index("users")
    means = [sub.loc[u, "mean_j_per_1k"]  if u in sub.index else 0 for u in users_vals]
    stds  = [sub.loc[u, "std_j_per_1k"]   if u in sub.index else 0 for u in users_vals]
    ax.bar(x + (i - 0.5)*width, means, width,
           label=cfg.capitalize(), color=color, alpha=0.88, zorder=3)
    ax.errorbar(x + (i - 0.5)*width, means, yerr=stds,
                fmt="none", color="black", capsize=4, linewidth=1.2, zorder=4)

ax.set_xlabel("Concurrent Users")
ax.set_ylabel("J / 1000 Requests")
ax.set_title("Energy per 1000 Requests — Default vs Optimized\n(lower is better)",
             fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels([str(u) for u in users_vals])
ax.legend()
ax.yaxis.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()
out = os.path.join(RESULTS_DIR, "chart_bar_comparison.png")
plt.savefig(out, dpi=150)
plt.close()
print(f"Saved: {out}")

# ── 2. Box Plot ────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(1, len(users_vals), figsize=(4*len(users_vals), 5), sharey=True)
for ax, u in zip(axes, users_vals):
    d_def = raw[(raw["config"]=="default")   & (raw["users"]==u)]["j_per_1k_req"].dropna()
    d_opt = raw[(raw["config"]=="optimized") & (raw["users"]==u)]["j_per_1k_req"].dropna()
    bp = ax.boxplot([d_def, d_opt], patch_artist=True,
                    medianprops=dict(color="black", linewidth=2))
    for patch, color in zip(bp["boxes"], [C_DEF, C_OPT]):
        patch.set_facecolor(color); patch.set_alpha(0.75)
    ax.set_title(f"{u} users", fontweight="bold")
    ax.set_xticks([1, 2])
    ax.set_xticklabels(["Default", "Optimized"], fontsize=9)
axes[0].set_ylabel("J / 1000 Requests")
fig.suptitle("Distribution of Energy per 1000 Requests (9 runs each)",
             fontweight="bold")
plt.tight_layout()
out = os.path.join(RESULTS_DIR, "chart_boxplot.png")
plt.savefig(out, dpi=150)
plt.close()
print(f"Saved: {out}")

# ── 3. Energy Savings % ────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4))
pivoted = summary.pivot(index="users", columns="config", values="mean_j_per_1k")
savings = ((pivoted["default"] - pivoted["optimized"]) / pivoted["default"] * 100)
colors  = [C_OPT if v >= 0 else C_DEF for v in savings.values]
bars    = ax.bar(savings.index.astype(str), savings.values,
                 color=colors, alpha=0.85, width=0.5, zorder=3)
ax.axhline(0, color="black", linewidth=0.8)
for bar, val in zip(bars, savings.values):
    ypos = bar.get_height() + 0.5 if val >= 0 else bar.get_height() - 2.5
    ax.text(bar.get_x() + bar.get_width()/2, ypos,
            f"{val:.1f}%", ha="center", va="bottom", fontweight="bold")
ax.set_xlabel("Concurrent Users")
ax.set_ylabel("Energy Saving (%)")
ax.set_title("% Energy Reduction: Optimized vs Default\n(positive = optimized uses less energy)",
             fontweight="bold")
ax.yaxis.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()
out = os.path.join(RESULTS_DIR, "chart_savings_pct.png")
plt.savefig(out, dpi=150)
plt.close()
print(f"Saved: {out}")

# ── 4. Requests per Second ─────────────────────────────────────────────────────
raw["rps"] = raw["requests"] / 60.0
rps = raw.groupby(["config","users"])["rps"].agg(mean="mean", std="std").reset_index()

fig, ax = plt.subplots(figsize=(9, 5))
for i, (cfg, color) in enumerate([("default", C_DEF), ("optimized", C_OPT)]):
    sub   = rps[rps["config"]==cfg].set_index("users")
    means = [sub.loc[u,"mean"] if u in sub.index else 0 for u in users_vals]
    stds  = [sub.loc[u,"std"]  if u in sub.index else 0 for u in users_vals]
    ax.bar(x + (i - 0.5)*width, means, width,
           label=cfg.capitalize(), color=color, alpha=0.88, zorder=3)
    ax.errorbar(x + (i - 0.5)*width, means, yerr=stds,
                fmt="none", color="black", capsize=4, linewidth=1.2, zorder=4)
ax.set_xlabel("Concurrent Users")
ax.set_ylabel("Requests / Second")
ax.set_title("Throughput: Default vs Optimized\n(higher is better)", fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels([str(u) for u in users_vals])
ax.legend()
ax.yaxis.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()
out = os.path.join(RESULTS_DIR, "chart_rps.png")
plt.savefig(out, dpi=150)
plt.close()
print(f"Saved: {out}")

# ── 5. CPU % comparison ────────────────────────────────────────────────────────
cpu = raw.groupby(["config","users"])["mean_cpu_pct"].agg(mean="mean", std="std").reset_index()

fig, ax = plt.subplots(figsize=(9, 5))
for i, (cfg, color) in enumerate([("default", C_DEF), ("optimized", C_OPT)]):
    sub   = cpu[cpu["config"]==cfg].set_index("users")
    means = [sub.loc[u,"mean"] if u in sub.index else 0 for u in users_vals]
    stds  = [sub.loc[u,"std"]  if u in sub.index else 0 for u in users_vals]
    ax.bar(x + (i - 0.5)*width, means, width,
           label=cfg.capitalize(), color=color, alpha=0.88, zorder=3)
    ax.errorbar(x + (i - 0.5)*width, means, yerr=stds,
                fmt="none", color="black", capsize=4, linewidth=1.2, zorder=4)
ax.set_xlabel("Concurrent Users")
ax.set_ylabel("Mean CPU Usage (%)")
ax.set_title("CPU Utilisation During Benchmark\n(lower = more efficient)", fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels([str(u) for u in users_vals])
ax.legend()
ax.yaxis.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()
out = os.path.join(RESULTS_DIR, "chart_cpu_usage.png")
plt.savefig(out, dpi=150)
plt.close()
print(f"Saved: {out}")

print("\n All 5 charts saved to results/")
print("Open the results/ folder in VS Code Explorer to view them!")
