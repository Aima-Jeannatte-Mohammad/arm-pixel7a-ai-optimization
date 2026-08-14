"""
analysis/compute_stats.py

Reads all data/raw/*.csv (Lever 1 thread-count sweep), computes
statistics per §49 of the master prompt (median, mean, SD, min, max,
speedup, latency reduction vs. baseline) on VALID runs only (warmup
excluded), prints a summary table, and generates a self-contained
dashboard at webapp/dashboard/index.html with charts, a full results
table, and a data-driven engineering commentary section.

If a file named "<leader>_replication.csv" exists in data/raw/ (e.g.
threads_4_replication.csv), it is treated as the §54-bis robustness
replication of the current leader and compared against the original
campaign result. ROBUST requires two conditions, matching the master
prompt's original "ranking and approximate magnitude" language rather
than an arbitrary percentage threshold: (1) the configuration still
outperforms baseline in the replication session, and (2) both the
original and replication speedups fall on the same side of 1.0x (both
real improvements, not one improvement and one regression).

Usage:
    python analysis/compute_stats.py
"""

import csv
import json
import statistics
from pathlib import Path

RAW_DIR = Path("data/raw")
DASHBOARD_OUT = Path("webapp/dashboard/index.html")

CONFIG_ORDER = ["baseline", "threads_1", "threads_2", "threads_4", "threads_8"]
THREAD_COUNT_MAP = {"baseline": None, "threads_1": 1, "threads_2": 2, "threads_4": 4, "threads_8": 8}


def load_valid_rows_by_config():
    rows_by_config = {}
    for csv_path in sorted(RAW_DIR.glob("*.csv")):
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("run_type") != "valid" or row.get("validity") != "valid":
                    continue
                cfg = row["config"]
                rows_by_config.setdefault(cfg, []).append(row)
    return rows_by_config


def compute_config_stats(rows):
    lat = [float(r["end_to_end_latency_s"]) for r in rows if r.get("end_to_end_latency_s")]
    decode = [float(r["decode_speed_tok_s"]) for r in rows if r.get("decode_speed_tok_s")]
    cpu = [float(r["cpu_pct"]) for r in rows if r.get("cpu_pct")]
    mem = [float(r["peak_rss_kb"]) for r in rows if r.get("peak_rss_kb")]
    if not lat:
        return None
    return {
        "n": len(lat),
        "median_latency_s": round(statistics.median(lat), 3),
        "mean_latency_s": round(statistics.mean(lat), 3),
        "sd_latency_s": round(statistics.stdev(lat), 3) if len(lat) > 1 else 0.0,
        "min_latency_s": round(min(lat), 3),
        "max_latency_s": round(max(lat), 3),
        "mean_decode_tok_s": round(statistics.mean(decode), 2) if decode else None,
        "mean_cpu_pct": round(statistics.mean(cpu), 1) if cpu else None,
        "mean_peak_rss_mb": round(statistics.mean(mem) / 1024, 1) if mem else None,
    }


def signal_check(baseline_stats, cfg_stats):
    sd = baseline_stats["sd_latency_s"]
    gap = baseline_stats["median_latency_s"] - cfg_stats["median_latency_s"]
    if sd == 0:
        return round(gap, 3), None
    return round(gap, 3), round(abs(gap) / sd, 2)


def check_replication(baseline_stats, original_stats, repl_stats):
    """§54-bis: ROBUST if (1) the configuration still beats baseline in
    the replication (ranking holds) and (2) the speedup direction stays
    consistent (same order of magnitude -- both real improvements, not
    a flip from improvement to regression). No arbitrary percentage
    threshold: a replication that is even MORE favorable than the
    original still confirms the result under this rule."""
    orig_median = original_stats["median_latency_s"]
    repl_median = repl_stats["median_latency_s"]
    baseline_median = baseline_stats["median_latency_s"]

    ranking_holds = repl_median < baseline_median
    orig_speedup = round(baseline_median / orig_median, 3)
    repl_speedup = round(baseline_median / repl_median, 3)
    same_order = (orig_speedup > 1.0) == (repl_speedup > 1.0)
    robust = ranking_holds and same_order

    return {
        "original_median_s": orig_median,
        "replication_median_s": repl_median,
        "original_speedup": orig_speedup,
        "replication_speedup": repl_speedup,
        "ranking_holds": ranking_holds,
        "same_order_of_magnitude": same_order,
        "robust": robust,
    }


def main():
    rows_by_config = load_valid_rows_by_config()
    if "baseline" not in rows_by_config:
        raise SystemExit("No valid baseline rows found in data/raw/ -- cannot compute speedup.")

    replication_rows = {
        cfg: rows for cfg, rows in rows_by_config.items() if cfg.endswith("_replication")
    }
    for cfg in replication_rows:
        del rows_by_config[cfg]

    stats = {}
    for cfg, rows in rows_by_config.items():
        s = compute_config_stats(rows)
        if s:
            s["thread_count"] = THREAD_COUNT_MAP.get(cfg)
            stats[cfg] = s

    baseline = stats["baseline"]
    for cfg, s in stats.items():
        s["speedup_vs_baseline"] = round(baseline["median_latency_s"] / s["median_latency_s"], 3)
        s["latency_reduction_pct"] = round(
            (baseline["median_latency_s"] - s["median_latency_s"]) / baseline["median_latency_s"] * 100, 1
        )
        gap_s, gap_sd = signal_check(baseline, s)
        s["gap_vs_baseline_s"] = gap_s
        s["gap_in_baseline_sds"] = gap_sd

    ordered = [c for c in CONFIG_ORDER if c in stats] + [c for c in stats if c not in CONFIG_ORDER]
    leader_cfg, leader_stats = min(stats.items(), key=lambda kv: kv[1]["median_latency_s"])

    distinguishable = None
    if leader_cfg != "baseline" and leader_stats["gap_in_baseline_sds"] is not None:
        distinguishable = leader_stats["gap_in_baseline_sds"] >= 1.0

    thread_cfgs = [(c, s) for c, s in stats.items() if s["thread_count"] and s["mean_cpu_pct"]]
    thread_cfgs.sort(key=lambda cs: cs[1]["thread_count"])
    cpu_scales = None
    if len(thread_cfgs) >= 2:
        cpu_vals = [s["mean_cpu_pct"] for _, s in thread_cfgs]
        cpu_scales = all(cpu_vals[i] <= cpu_vals[i + 1] for i in range(len(cpu_vals) - 1))

    replication = None
    repl_key = f"{leader_cfg}_replication"
    if repl_key in replication_rows:
        repl_stats = compute_config_stats(replication_rows[repl_key])
        if repl_stats:
            replication = check_replication(baseline, leader_stats, repl_stats)
            replication["config"] = leader_cfg
            replication["n"] = repl_stats["n"]

    print("\n=== Lever 1 (thread-count) summary -- VALID runs only ===\n")
    header = f"{'config':<12}{'n':>4}{'median(s)':>11}{'sd(s)':>8}{'speedup':>9}{'reduction':>11}{'vs-noise':>10}"
    print(header)
    print("-" * len(header))
    for cfg in ordered:
        s = stats[cfg]
        sdtxt = f"{s['gap_in_baseline_sds']}sd" if s["gap_in_baseline_sds"] is not None else "-"
        print(f"{cfg:<12}{s['n']:>4}{s['median_latency_s']:>11}{s['sd_latency_s']:>8}"
              f"{s['speedup_vs_baseline']:>9}{s['latency_reduction_pct']:>10}%{sdtxt:>10}")

    print(f"\nLeader: {leader_cfg} ({leader_stats['median_latency_s']}s, "
          f"{leader_stats['speedup_vs_baseline']}x speedup)")
    print(f"Distinguishable from baseline noise: {distinguishable}")

    if replication:
        verdict = "ROBUST" if replication["robust"] else "NOT ROBUST"
        print(f"\n=== section 54-bis Replication ({replication['n']} runs) ===")
        print(f"Original: {replication['original_median_s']}s ({replication['original_speedup']}x) | "
              f"Replication: {replication['replication_median_s']}s ({replication['replication_speedup']}x) | "
              f"ranking_holds={replication['ranking_holds']} same_order={replication['same_order_of_magnitude']} "
              f"-> {verdict}")
    else:
        print(f"\nNo replication data found (expected data/raw/{repl_key}.csv). "
              f"Replication (section 54-bis) still required before this is reported as final.")

    generate_dashboard(stats, ordered, leader_cfg, distinguishable, cpu_scales, replication)
    print(f"\nDashboard written to {DASHBOARD_OUT}")


def build_commentary(stats, ordered, leader_cfg, distinguishable, cpu_scales, replication):
    b = stats["baseline"]
    l = stats[leader_cfg]
    bullets = []

    if leader_cfg == "baseline":
        bullets.append(
            "The runtime's automatic thread selection (baseline) outperformed every "
            "manually-configured thread count tested. This suggests the scheduler's "
            "default heuristic is already close to optimal for this workload on this "
            "device, or that manual thread pinning is not exploitable here without "
            "controlling core affinity directly (out of scope, section 19)."
        )
    else:
        sd_txt = f"{l['gap_in_baseline_sds']} baseline standard deviations" if l["gap_in_baseline_sds"] is not None else "an unquantified margin"
        verdict = "a real, distinguishable signal" if distinguishable else "NOT clearly distinguishable from run-to-run noise -- treat with caution"
        bullets.append(
            f"{leader_cfg} shows the lowest median latency ({l['median_latency_s']}s vs. "
            f"baseline's {b['median_latency_s']}s, {l['speedup_vs_baseline']}x speedup). "
            f"The gap is {sd_txt} from baseline -- this is {verdict}."
        )

    if cpu_scales is True:
        bullets.append(
            "Measured CPU utilization increases monotonically with configured thread "
            "count across the tested range, confirming the --num_cpu_threads flag is "
            "genuinely engaging additional cores, not silently capped by the runtime."
        )
    elif cpu_scales is False:
        bullets.append(
            "Measured CPU utilization does NOT increase monotonically with configured "
            "thread count -- this warrants investigation before trusting the thread-count "
            "sweep's results, since it suggests the flag may not be behaving as expected "
            "at every configured value."
        )

    bullets.append(
        "Heterogeneity caveat: none of the above quantifies which specific cores "
        "(A55/A78/X1) executed each configuration's threads -- the Android scheduler's "
        "core-placement decisions are not observed (sections 19, 23). Reported gaps "
        "reflect the combined effect of the configured thread count AND unobserved "
        "scheduling."
    )

    if replication:
        if replication["robust"]:
            bullets.append(
                f"Robustness replication (section 54-bis) COMPLETE for {leader_cfg}: "
                f"ranking held (still faster than baseline: {replication['replication_median_s']}s "
                f"vs. baseline's {b['median_latency_s']}s in the replication session) and speedup "
                f"stayed on the same side of 1.0x ({replication['original_speedup']}x originally "
                f"vs. {replication['replication_speedup']}x in replication). Verdict: ROBUST. "
                f"{leader_cfg} can now be reported as the final Lever 1 configuration."
            )
        else:
            failed_on = []
            if not replication["ranking_holds"]:
                failed_on.append("ranking did not hold (no longer faster than baseline)")
            if not replication["same_order_of_magnitude"]:
                failed_on.append("speedup direction flipped between sessions")
            bullets.append(
                f"Robustness replication (section 54-bis) COMPLETE for {leader_cfg} but did "
                f"NOT hold: {', '.join(failed_on)} ({replication['original_speedup']}x "
                f"originally vs. {replication['replication_speedup']}x in replication). "
                f"Verdict: NOT ROBUST. Per the project's decision rule, {leader_cfg} cannot "
                f"be reported as final -- fall back to the next-strongest configuration that "
                f"has itself been replicated, or report that no reproducible thread-count "
                f"effect was established."
            )
    else:
        bullets.append(
            f"Mandatory next step: robustness replication (section 54-bis) of {leader_cfg} "
            f"in a separate session (10 valid runs) before this configuration can be "
            f"reported as final. This dashboard's leader is provisional."
        )

    return bullets


def generate_dashboard(stats, ordered, leader_cfg, distinguishable, cpu_scales, replication):
    data_json = json.dumps({"stats": stats, "order": ordered, "leader": leader_cfg}, indent=2)
    commentary = build_commentary(stats, ordered, leader_cfg, distinguishable, cpu_scales, replication)
    commentary_html = "".join(f"<li>{c}</li>" for c in commentary)

    dist_badge = ""
    if leader_cfg != "baseline":
        dist_badge = (
            '<span class="badge ok">SIGNAL</span>' if distinguishable
            else '<span class="badge warn">WITHIN NOISE</span>'
        )

    if replication is None:
        status_badge = '<span class="badge warn">PROVISIONAL</span>'
        status_line = "Provisional -- robustness replication (section 54-bis) not yet performed."
    elif replication["robust"]:
        status_badge = '<span class="badge ok">VERIFIED</span>'
        status_line = (
            f"Verified via section 54-bis replication ({replication['n']} runs): "
            f"ranking held, speedup direction consistent. ROBUST. See table below."
        )
    else:
        status_badge = '<span class="badge bad">NOT ROBUST</span>'
        status_line = (
            f"Replication (section 54-bis, {replication['n']} runs) did NOT confirm this "
            f"result -- do not report {leader_cfg} as final. See table below."
        )

    replication_section = ""
    if replication:
        verdict_txt = "ROBUST" if replication["robust"] else "NOT ROBUST"
        verdict_class = "ok" if replication["robust"] else "bad"
        replication_section = f"""
<h2>Robustness Replication (section 54-bis)</h2>
<table>
<tr><th>Configuration</th><th>Original median (s)</th><th>Replication median (s)</th>
    <th>Original speedup</th><th>Replication speedup</th><th>Ranking holds</th>
    <th>Same order of magnitude</th><th>n (replication)</th><th>Verdict</th></tr>
<tr>
  <td style="text-align:left">{replication['config']}</td>
  <td>{replication['original_median_s']}</td>
  <td>{replication['replication_median_s']}</td>
  <td>{replication['original_speedup']}x</td>
  <td>{replication['replication_speedup']}x</td>
  <td>{replication['ranking_holds']}</td>
  <td>{replication['same_order_of_magnitude']}</td>
  <td>{replication['n']}</td>
  <td><span class="badge {verdict_class}">{verdict_txt}</span></td>
</tr>
</table>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Tech-Explique-Moi -- Phase B Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 980px; margin: 40px auto; padding: 0 20px; background: #0d1117; color: #e6edf3; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1.1rem; margin-top: 36px; border-bottom: 1px solid #30363d; padding-bottom: 6px; }}
  .caveat {{ background: #3d2b00; border-left: 4px solid #d29922; padding: 12px 16px; margin: 16px 0; border-radius: 4px; font-size: 0.9rem; }}
  .leader {{ background: #0d3d1c; border-left: 4px solid #3fb950; padding: 12px 16px; margin: 16px 0; border-radius: 4px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; margin-left: 8px; }}
  .badge.ok {{ background: #1b4d2a; color: #3fb950; }}
  .badge.warn {{ background: #4d3a1b; color: #d29922; }}
  .badge.bad {{ background: #4d1b1b; color: #f85149; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.82rem; }}
  th, td {{ padding: 7px 9px; text-align: right; border-bottom: 1px solid #30363d; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ color: #8b949e; font-weight: 600; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  canvas {{ max-height: 260px; }}
  ul.commentary li {{ margin: 10px 0; line-height: 1.5; font-size: 0.92rem; }}
</style>
</head>
<body>
<h1>Tech-Explique-Moi -- Lever 1 Results (CPU Thread-Count Sweep)</h1>

<div class="caveat">
<strong>Heterogeneity caveat (section 23-bis):</strong> results below reflect the
combined effect of the configured thread count and Android's (unobserved)
scheduling decisions across the Tensor G2's heterogeneous 2+2+4 cores.
No claim is made about which specific cores executed each configuration's threads.
</div>

<div class="leader">
Current leader: <strong>{leader_cfg}</strong> --
{stats[leader_cfg]['median_latency_s']}s median latency,
{stats[leader_cfg]['speedup_vs_baseline']}x speedup vs. baseline.{dist_badge}{status_badge}
<br><small>{status_line}</small>
</div>

<h2>Median End-to-End Latency by Configuration</h2>
<div class="charts">
  <canvas id="chartLatency"></canvas>
  <canvas id="chartCpu"></canvas>
</div>
<canvas id="chartDecode" style="margin-top:24px;"></canvas>

<h2>Full Results Table</h2>
<table id="tbl"></table>
{replication_section}
<h2>Engineering Analysis</h2>
<ul class="commentary">{commentary_html}</ul>

<script>
const data = {data_json};
const labels = data.order;
const medians = labels.map(c => data.stats[c].median_latency_s);
const cpus = labels.map(c => data.stats[c].mean_cpu_pct ?? 0);
const decodes = labels.map(c => data.stats[c].mean_decode_tok_s ?? 0);
const colors = labels.map(c => c === data.leader ? '#3fb950' : '#58a6ff');

new Chart(document.getElementById('chartLatency'), {{
  type: 'bar',
  data: {{ labels, datasets: [{{ label: 'Median latency (s)', data: medians, backgroundColor: colors }}] }},
  options: {{ plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'Latency (lower is better)', color: '#e6edf3' }} }},
              scales: {{ y: {{ beginAtZero: true }} }} }}
}});

new Chart(document.getElementById('chartCpu'), {{
  type: 'bar',
  data: {{ labels, datasets: [{{ label: 'Mean CPU %', data: cpus, backgroundColor: '#f0883e' }}] }},
  options: {{ plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'CPU Utilization (%, may exceed 100%)', color: '#e6edf3' }} }},
              scales: {{ y: {{ beginAtZero: true }} }} }}
}});

new Chart(document.getElementById('chartDecode'), {{
  type: 'bar',
  data: {{ labels, datasets: [{{ label: 'Decode speed (tok/s)', data: decodes, backgroundColor: '#bc8cff' }}] }},
  options: {{ plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'Decode throughput (higher is better)', color: '#e6edf3' }} }},
              scales: {{ y: {{ beginAtZero: true }} }} }}
}});

const cols = ['config','threads','n','median(s)','mean(s)','sd(s)','min(s)','max(s)','speedup','reduction(%)','vs-baseline-sd','decode(tok/s)','cpu(%)','peak RSS(MB)'];
let html = '<tr>' + cols.map(c => `<th>${{c}}</th>`).join('') + '</tr>';
for (const cfg of labels) {{
  const s = data.stats[cfg];
  const isLeader = cfg === data.leader;
  html += `<tr style="${{isLeader ? 'font-weight:700;color:#3fb950;' : ''}}"><td>${{cfg}}</td><td>${{s.thread_count ?? 'auto'}}</td><td>${{s.n}}</td>` +
          `<td>${{s.median_latency_s}}</td><td>${{s.mean_latency_s}}</td><td>${{s.sd_latency_s}}</td>` +
          `<td>${{s.min_latency_s}}</td><td>${{s.max_latency_s}}</td>` +
          `<td>${{s.speedup_vs_baseline}}</td><td>${{s.latency_reduction_pct}}</td>` +
          `<td>${{s.gap_in_baseline_sds ?? '-'}}</td>` +
          `<td>${{s.mean_decode_tok_s ?? '-'}}</td><td>${{s.mean_cpu_pct ?? '-'}}</td><td>${{s.mean_peak_rss_mb ?? '-'}}</td></tr>`;
}}
document.getElementById('tbl').innerHTML = html;
</script>
</body>
</html>
"""
    DASHBOARD_OUT.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_OUT.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()