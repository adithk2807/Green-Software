#!/usr/bin/env python3
"""
run_benchmark.py — Windows-compatible nginx energy benchmark.
Uses psutil CPU percent + time as energy proxy when RAPL unavailable.
Falls back to: Energy (J) = Power (W) * Time (s)
where Power is estimated from CPU% * TDP.
"""

import os, sys, time, subprocess, csv, json
import psutil, requests, pandas as pd
from datetime import datetime

# ── Settings ──────────────────────────────────────────────────────────────────
CONFIGS = {
    "default":   "http://localhost:8080",
    "optimized": "http://localhost:8081",
}
LOAD_LEVELS       = [10, 100, 500]
RUN_DURATION_S    = 60
N_VALID_RUNS      = 9        # 9 valid runs after discarding 1 warm-up
IDLE_DURATION_S   = 15
RESULTS_DIR       = os.path.join(os.path.dirname(__file__), "..", "results")
LOCUST_FILE       = os.path.join(os.path.dirname(__file__), "..", "locust", "locustfile.py")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Estimate CPU TDP in watts — adjust if you know your CPU's TDP
# Common values: laptop i5/i7 = 15-28W, desktop = 65-125W
CPU_TDP_WATTS = 45.0

# ── Energy via psutil ─────────────────────────────────────────────────────────
def measure_energy_joules(duration_s: int, label: str = "") -> tuple[float, float]:
    """
    Sample CPU usage every 0.5s for duration_s seconds.
    Returns (energy_joules, mean_cpu_percent).
    Energy = sum(cpu_fraction * TDP * interval)
    """
    samples = []
    interval = 0.5
    steps = int(duration_s / interval)
    # warm up the first reading (psutil needs one call before accurate readings)
    psutil.cpu_percent(interval=None)
    for _ in range(steps):
        pct = psutil.cpu_percent(interval=interval)
        samples.append(pct)
    mean_pct = sum(samples) / len(samples) if samples else 0.0
    energy_j = (mean_pct / 100.0) * CPU_TDP_WATTS * duration_s
    if label:
        print(f"      [{label}] mean CPU={mean_pct:.1f}%  energy={energy_j:.3f}J")
    return energy_j, mean_pct

def run_locust(host: str, users: int, duration_s: int, prefix: str) -> dict:
    """Run Locust headlessly. Returns {requests, failures}."""
    spawn_rate = max(1, users // 5)
    cmd = [
        sys.executable, "-m", "locust",
        "-f", LOCUST_FILE,
        "--headless",
        "--host", host,
        "-u", str(users),
        "-r", str(spawn_rate),
        "--run-time", f"{duration_s}s",
        "--csv", prefix,
        "--only-summary",
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=duration_s + 90)
    except subprocess.TimeoutExpired:
        print("      [locust] TIMEOUT — skipping run")
        return {"requests": 0, "failures": 0}

    total_req = total_fail = 0
    stats_file = prefix + "_stats.csv"
    if os.path.exists(stats_file):
        with open(stats_file) as f:
            for row in csv.DictReader(f):
                if row.get("Name") == "Aggregated":
                    total_req  = int(float(row.get("Request Count", 0)))
                    total_fail = int(float(row.get("Failure Count", 0)))
    return {"requests": total_req, "failures": total_fail}

def single_run(host: str, users: int, run_id: int, config: str) -> dict | None:
    """One full benchmark run. Returns result dict or None on failure."""
    prefix = os.path.join(RESULTS_DIR, f"{config}_{users}u_run{run_id}")

    print(f"    pre-idle ({IDLE_DURATION_S}s)…")
    idle_pre_j, idle_pre_pct = measure_energy_joules(IDLE_DURATION_S, "pre-idle")

    print(f"    locust {users} users × {RUN_DURATION_S}s…")

    # Measure energy DURING the locust run using psutil in parallel
    import threading
    locust_result = {}
    energy_samples = []

    def locust_thread():
        locust_result.update(run_locust(host, users, RUN_DURATION_S, prefix))

    def energy_thread():
        psutil.cpu_percent(interval=None)
        interval = 0.5
        steps = int(RUN_DURATION_S / interval)
        for _ in range(steps):
            pct = psutil.cpu_percent(interval=interval)
            energy_samples.append(pct)

    t_locust = threading.Thread(target=locust_thread)
    t_energy = threading.Thread(target=energy_thread)
    t_locust.start()
    t_energy.start()
    t_locust.join()
    t_energy.join()

    mean_run_pct = sum(energy_samples) / len(energy_samples) if energy_samples else 0.0
    gross_j = (mean_run_pct / 100.0) * CPU_TDP_WATTS * RUN_DURATION_S
    print(f"      [run]  mean CPU={mean_run_pct:.1f}%  gross_energy={gross_j:.3f}J")

    print(f"    post-idle ({IDLE_DURATION_S}s)…")
    idle_post_j, idle_post_pct = measure_energy_joules(IDLE_DURATION_S, "post-idle")

    # Net energy = remove idle baseline
    avg_idle_j   = (idle_pre_j + idle_post_j) / 2
    idle_rate_j  = avg_idle_j / IDLE_DURATION_S
    baseline_j   = idle_rate_j * RUN_DURATION_S
    net_j        = max(0.0, gross_j - baseline_j)

    reqs     = locust_result.get("requests", 0)
    failures = locust_result.get("failures", 0)
    j_per_1k = (net_j / reqs * 1000) if reqs > 0 else float("nan")

    print(f"    → gross={gross_j:.3f}J  baseline={baseline_j:.3f}J  "
          f"net={net_j:.3f}J  reqs={reqs}  J/1k={j_per_1k:.4f}")

    if reqs == 0:
        print("    [SKIP] 0 requests recorded — discarding run")
        return None

    return {
        "config":       config,
        "users":        users,
        "run_id":       run_id,
        "gross_j":      round(gross_j, 4),
        "baseline_j":   round(baseline_j, 4),
        "net_j":        round(net_j, 4),
        "requests":     reqs,
        "failures":     failures,
        "j_per_1k_req": round(j_per_1k, 6),
        "mean_cpu_pct": round(mean_run_pct, 2),
        "warmup":       False,
        "timestamp":    datetime.utcnow().isoformat(),
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(" NGINX ENERGY BENCHMARK (Windows / psutil mode)")
    print(f" CPU TDP assumed: {CPU_TDP_WATTS}W  — edit CPU_TDP_WATTS if needed")
    print("=" * 60)

    for name, host in CONFIGS.items():
        try:
            r = requests.get(host + "/small.html", timeout=5)
            print(f"[ok] {name}: {host} → HTTP {r.status_code}")
        except Exception as e:
            print(f"[FAIL] {name}: {host} — {e}")
            print("  Run:  docker compose up -d")
            sys.exit(1)

    all_results = []

    for config, host in CONFIGS.items():
        for users in LOAD_LEVELS:
            print(f"\n{'─'*50}")
            print(f" Config={config}  Users={users}")
            print(f"{'─'*50}")
            valid = []
            attempt = 0
            while len(valid) < N_VALID_RUNS + 1:  # +1 for warm-up
                attempt += 1
                print(f"\n  Run #{attempt}  (have {max(0,len(valid)-1)}/{N_VALID_RUNS} valid)…")
                r = single_run(host, users, attempt, config)
                if r is None:
                    continue
                if len(valid) == 0:
                    r["warmup"] = True
                    print("  (warm-up run — excluded from stats)")
                valid.append(r)
                all_results.append(r)

    df = pd.DataFrame(all_results)
    raw_path = os.path.join(RESULTS_DIR, "raw_results.csv")
    df.to_csv(raw_path, index=False)
    print(f"\n[saved] {raw_path}")

    df_v = df[df["warmup"] == False]
    summary = (
        df_v.groupby(["config", "users"])["j_per_1k_req"]
        .agg(mean="mean", std="std", n="count")
        .reset_index()
    )
    summary.columns = ["config", "users", "mean_j_per_1k", "std_j_per_1k", "n"]
    summary_path = os.path.join(RESULTS_DIR, "summary.csv")
    summary.to_csv(summary_path, index=False)

    print("\n" + "=" * 60)
    print(" RESULTS — J per 1000 requests")
    print("=" * 60)
    print(summary.to_string(index=False))
    print(f"\n[saved] {summary_path}")
    print("\nNext: python scripts\\generate_charts.py")

if __name__ == "__main__":
    main()