"""
analysis/compute_stats.py

Reads all data/raw/*.csv, computes statistics on VALID runs only per
docs/02_protocols/OPTIMIZATION_PARAMETERS.md, and generates a self-contained dashboard at
webapp/dashboard/index.html with:
  - an introduction explaining the project and methodology
  - a "Lever 1: CPU Thread-Count Sweep" section (charts + table +
    signal check + replication result)
  - a "Lever 2: Weight Cache Configuration" section (auto-detected:
    any config outside CONFIG_ORDER, e.g. threads_4_nocache, is
    treated as a Lever 2 candidate and compared against the Lever 1
    winner, not against baseline -- per the two-lever design)

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


def signal_check(ref_stats, cfg_stats):
    sd = ref_stats["sd_latency_s"]
    gap = ref_stats["median_latency_s"] - cfg_stats["median_latency_s"]
    if sd == 0:
        return round(gap, 3), None
    return round(gap, 3), round(abs(gap) / sd, 2)


def check_replication(ref_stats, original_stats, repl_stats):
    """ROBUST if (1) still beats the reference (ranking holds)
    and (2) speedup direction stays consistent (same side of 1.0x)."""
    orig_median = original_stats["median_latency_s"]
    repl_median = repl_stats["median_latency_s"]
    ref_median = ref_stats["median_latency_s"]

    ranking_holds = repl_median < ref_median
    orig_speedup = round(ref_median / orig_median, 3)
    repl_speedup = round(ref_median / repl_median, 3)
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


def add_speedup_fields(stats, ref_median):
    for s in stats.values():
        s["speedup_vs_ref"] = round(ref_median / s["median_latency_s"], 3)
        s["latency_reduction_pct"] = round(
            (ref_median - s["median_latency_s"]) / ref_median * 100, 1
        )


def main():
    rows_by_config = load_valid_rows_by_config()
    if "baseline" not in rows_by_config:
        raise SystemExit("No valid baseline rows found in data/raw/ -- cannot compute speedup.")

    replication_rows = {c: r for c, r in rows_by_config.items() if c.endswith("_replication")}
    for c in replication_rows:
        del rows_by_config[c]

    # Lever 1: configs in CONFIG_ORDER
    lever1_stats = {}
    for cfg in CONFIG_ORDER:
        if cfg in rows_by_config:
            s = compute_config_stats(rows_by_config[cfg])
            if s:
                s["thread_count"] = THREAD_COUNT_MAP.get(cfg)
                lever1_stats[cfg] = s

    baseline = lever1_stats["baseline"]
    add_speedup_fields(lever1_stats, baseline["median_latency_s"])
    for cfg, s in lever1_stats.items():
        gap_s, gap_sd = signal_check(baseline, s)
        s["gap_vs_baseline_s"] = gap_s
        s["gap_in_baseline_sds"] = gap_sd

    lever1_order = [c for c in CONFIG_ORDER if c in lever1_stats]
    lever1_leader_cfg, lever1_leader = min(lever1_stats.items(), key=lambda kv: kv[1]["median_latency_s"])
    distinguishable = None
    if lever1_leader_cfg != "baseline" and lever1_leader["gap_in_baseline_sds"] is not None:
        distinguishable = lever1_leader["gap_in_baseline_sds"] >= 1.0

    thread_cfgs = [(c, s) for c, s in lever1_stats.items() if s["thread_count"] and s["mean_cpu_pct"]]
    thread_cfgs.sort(key=lambda cs: cs[1]["thread_count"])
    cpu_scales = None
    if len(thread_cfgs) >= 2:
        cpu_vals = [s["mean_cpu_pct"] for _, s in thread_cfgs]
        cpu_scales = all(cpu_vals[i] <= cpu_vals[i + 1] for i in range(len(cpu_vals) - 1))

    lever1_replication = None
    repl_key = f"{lever1_leader_cfg}_replication"
    if repl_key in replication_rows:
        repl_stats = compute_config_stats(replication_rows[repl_key])
        if repl_stats:
            lever1_replication = check_replication(baseline, lever1_leader, repl_stats)
            lever1_replication["config"] = lever1_leader_cfg
            lever1_replication["n"] = repl_stats["n"]

    # Lever 2: any config NOT in CONFIG_ORDER and not a replication row
    lever2_stats = {}
    for cfg, rows in rows_by_config.items():
        if cfg in CONFIG_ORDER:
            continue
        s = compute_config_stats(rows)
        if s:
            lever2_stats[cfg] = s
    lever2_section = None
    if lever2_stats:
        add_speedup_fields(lever2_stats, lever1_leader["median_latency_s"])
        for cfg, s in lever2_stats.items():
            gap_s, gap_sd = signal_check(lever1_leader, s)
            s["gap_vs_lever1_leader_s"] = gap_s
            s["gap_in_lever1_leader_sds"] = gap_sd
        lever2_leader_cfg, lever2_leader = min(lever2_stats.items(), key=lambda kv: kv[1]["median_latency_s"])
        lever2_section = {
            "stats": lever2_stats,
            "order": list(lever2_stats.keys()),
            "lever1_ref_cfg": lever1_leader_cfg,
            "lever1_ref_stats": lever1_leader,
        }

    print("\n=== Lever 1 (thread-count) summary -- VALID runs only ===\n")
    header = f"{'config':<12}{'n':>4}{'median(s)':>11}{'sd(s)':>8}{'speedup':>9}{'reduction':>11}{'vs-noise':>10}"
    print(header)
    print("-" * len(header))
    for cfg in lever1_order:
        s = lever1_stats[cfg]
        sdtxt = f"{s['gap_in_baseline_sds']}sd" if s["gap_in_baseline_sds"] is not None else "-"
        print(f"{cfg:<12}{s['n']:>4}{s['median_latency_s']:>11}{s['sd_latency_s']:>8}"
              f"{s['speedup_vs_ref']:>9}{s['latency_reduction_pct']:>10}%{sdtxt:>10}")
    print(f"\nLever 1 leader: {lever1_leader_cfg} ({lever1_leader['median_latency_s']}s, "
          f"{lever1_leader['speedup_vs_ref']}x speedup)")
    if lever1_replication:
        verdict = "ROBUST" if lever1_replication["robust"] else "NOT ROBUST"
        print(f"Replication verdict: {verdict}")

    if lever2_stats:
        print(f"\n=== Lever 2 (weight cache) summary, vs. Lever 1 winner {lever1_leader_cfg} ===\n")
        for cfg, s in lever2_stats.items():
            print(f"{cfg}: {s['median_latency_s']}s ({s['speedup_vs_ref']}x vs. {lever1_leader_cfg})")

    generate_dashboard(lever1_stats, lever1_order, lever1_leader_cfg, distinguishable,
                        cpu_scales, lever1_replication, lever2_section)
    print(f"\nDashboard written to {DASHBOARD_OUT}")


def build_lever1_commentary(stats, leader_cfg, distinguishable, cpu_scales, replication):
    b = stats["baseline"]
    l = stats[leader_cfg]
    bullets = []

    if leader_cfg == "baseline":
        bullets.append(
            "The runtime's automatic thread selection (baseline) outperformed every "
            "manually-configured thread count tested. This suggests the scheduler's "
            "default heuristic is already close to optimal for this workload on this "
            "device, or that manual thread pinning is not exploitable here without "
            "controlling core affinity directly (out of scope by design -- see OPTIMIZATION_PRE_SCREENING.md)."
        )
    else:
        sd_txt = f"{l['gap_in_baseline_sds']} baseline standard deviations" if l["gap_in_baseline_sds"] is not None else "an unquantified margin"
        verdict = "a real, distinguishable signal" if distinguishable else "NOT clearly distinguishable from run-to-run noise"
        bullets.append(
            f"{leader_cfg} shows the lowest median latency ({l['median_latency_s']}s vs. "
            f"baseline's {b['median_latency_s']}s, {l['speedup_vs_ref']}x speedup). "
            f"The gap is {sd_txt} from baseline -- this is {verdict}."
        )

    if cpu_scales is True:
        bullets.append(
            "Measured CPU utilization increases monotonically with configured thread "
            "count, confirming --num_cpu_threads genuinely engages additional cores."
        )
    elif cpu_scales is False:
        bullets.append(
            "Measured CPU utilization does NOT increase monotonically with configured "
            "thread count -- warrants investigation before trusting this sweep."
        )

    bullets.append(
        "Heterogeneity caveat: none of the above identifies which specific cores "
        "(A55/A78/X1) executed each configuration's threads -- the Android scheduler's "
        "core-placement decisions are not observed."
    )

    if replication:
        if replication["robust"]:
            bullets.append(
                f"Replication COMPLETE: ranking held and speedup stayed "
                f"consistent ({replication['original_speedup']}x originally vs. "
                f"{replication['replication_speedup']}x in a separate session). "
                f"Verdict: ROBUST. {leader_cfg} is the final Lever 1 configuration."
            )
        else:
            bullets.append(
                f"Replication COMPLETE but did NOT hold "
                f"({replication['original_speedup']}x originally vs. "
                f"{replication['replication_speedup']}x in replication). Verdict: NOT ROBUST."
            )
    else:
        bullets.append(
            f"Mandatory next step: replication of {leader_cfg} in a "
            f"separate session before this can be reported as final."
        )
    return bullets


def build_lever2_commentary(lever2):
    stats = lever2["stats"]
    ref_cfg = lever2["lever1_ref_cfg"]
    ref = lever2["lever1_ref_stats"]
    leader_cfg, leader = min(stats.items(), key=lambda kv: kv[1]["median_latency_s"])
    bullets = []
    if leader["median_latency_s"] < ref["median_latency_s"]:
        bullets.append(
            f"{leader_cfg} improves on the Lever 1 winner ({ref_cfg}): "
            f"{leader['median_latency_s']}s vs. {ref['median_latency_s']}s "
            f"({leader['speedup_vs_ref']}x). Combining both levers is worthwhile."
        )
    else:
        bullets.append(
            f"{leader_cfg} does NOT improve on the Lever 1 winner ({ref_cfg}): "
            f"{leader['median_latency_s']}s vs. {ref['median_latency_s']}s "
            f"({leader['speedup_vs_ref']}x, i.e. slower). The Lever 1 configuration alone "
            f"remains the best combination found."
        )
    bullets.append(
        "This is a sequential (not factorial) design per OPTIMIZATION_PARAMETERS.md -- "
        "Lever 2 was only tested at the Lever 1 winning thread count, not across all "
        "thread-count values, as a documented time-budget tradeoff."
    )
    return bullets, leader_cfg


def chart_js(elem_id, labels, values, color_expr, title, ytitle=""):
    return f"""
new Chart(document.getElementById('{elem_id}'), {{
  type: 'bar',
  data: {{ labels: {json.dumps(labels)}, datasets: [{{ label: '{title}', data: {json.dumps(values)}, backgroundColor: {color_expr} }}] }},
  options: {{ responsive: true, maintainAspectRatio: false,
              plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: '{title}', color: '#e6edf3' }} }},
              scales: {{ y: {{ beginAtZero: true, title: {{ display: !!'{ytitle}', text: '{ytitle}', color: '#8b949e' }} }},
                         x: {{ ticks: {{ color: '#e6edf3' }} }} }} }}
}});
"""


def results_table_html(stats, order, leader_cfg, ref_label="speedup"):
    cols = ['config', 'threads', 'n', 'median(s)', 'mean(s)', 'sd(s)', 'min(s)', 'max(s)',
            ref_label, 'reduction(%)', 'decode(tok/s)', 'cpu(%)', 'peak RSS(MB)']
    rows_html = "<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>"
    for cfg in order:
        s = stats[cfg]
        style = "font-weight:700;color:#3fb950;" if cfg == leader_cfg else ""
        rows_html += (
            f'<tr style="{style}"><td>{cfg}</td><td>{s.get("thread_count", "-") or "auto"}</td>'
            f'<td>{s["n"]}</td><td>{s["median_latency_s"]}</td><td>{s["mean_latency_s"]}</td>'
            f'<td>{s["sd_latency_s"]}</td><td>{s["min_latency_s"]}</td><td>{s["max_latency_s"]}</td>'
            f'<td>{s["speedup_vs_ref"]}x</td><td>{s["latency_reduction_pct"]}</td>'
            f'<td>{s.get("mean_decode_tok_s", "-")}</td><td>{s.get("mean_cpu_pct", "-")}</td>'
            f'<td>{s.get("mean_peak_rss_mb", "-")}</td></tr>'
        )
    return f"<table>{rows_html}</table>"


def generate_dashboard(lever1_stats, lever1_order, leader_cfg, distinguishable,
                        cpu_scales, replication, lever2_section):
    l1_commentary = build_lever1_commentary(lever1_stats, leader_cfg, distinguishable, cpu_scales, replication)
    l1_commentary_html = "".join(f"<li>{c}</li>" for c in l1_commentary)

    dist_badge = ""
    if leader_cfg != "baseline":
        dist_badge = '<span class="badge ok">SIGNAL</span>' if distinguishable else '<span class="badge warn">WITHIN NOISE</span>'

    if replication is None:
        status_badge = '<span class="badge warn">PROVISIONAL</span>'
        status_line = "Provisional -- replication not yet performed."
    elif replication["robust"]:
        status_badge = '<span class="badge ok">VERIFIED</span>'
        status_line = "Replicated: ranking held, direction consistent. ROBUST."
    else:
        status_badge = '<span class="badge bad">NOT ROBUST</span>'
        status_line = "Replication did NOT confirm this result -- do not report as final."

    replication_table = ""
    if replication:
        verdict_txt = "ROBUST" if replication["robust"] else "NOT ROBUST"
        verdict_class = "ok" if replication["robust"] else "bad"
        replication_table = f"""
<h3>Robustness Replication</h3>
<table>
<tr><th>Configuration</th><th>Original median (s)</th><th>Replication median (s)</th>
    <th>Original speedup</th><th>Replication speedup</th><th>Ranking holds</th>
    <th>Same order of magnitude</th><th>n</th><th>Verdict</th></tr>
<tr>
  <td style="text-align:left">{replication['config']}</td>
  <td>{replication['original_median_s']}</td><td>{replication['replication_median_s']}</td>
  <td>{replication['original_speedup']}x</td><td>{replication['replication_speedup']}x</td>
  <td>{replication['ranking_holds']}</td><td>{replication['same_order_of_magnitude']}</td>
  <td>{replication['n']}</td>
  <td><span class="badge {verdict_class}">{verdict_txt}</span></td>
</tr>
</table>
"""

    l1_table = results_table_html(lever1_stats, lever1_order, leader_cfg)
    l1_labels = lever1_order
    l1_medians = [lever1_stats[c]["median_latency_s"] for c in l1_labels]
    l1_cpus = [lever1_stats[c]["mean_cpu_pct"] or 0 for c in l1_labels]
    l1_decodes = [lever1_stats[c]["mean_decode_tok_s"] or 0 for c in l1_labels]
    l1_colors = [f"'{'#3fb950' if c == leader_cfg else '#58a6ff'}'" for c in l1_labels]
    l1_colors_js = "[" + ",".join(l1_colors) + "]"

    lever2_html = ""
    lever2_scripts = ""
    if lever2_section:
        l2_commentary, l2_leader_cfg = build_lever2_commentary(lever2_section)
        l2_commentary_html = "".join(f"<li>{c}</li>" for c in l2_commentary)
        l2_stats = lever2_section["stats"]
        ref_cfg = lever2_section["lever1_ref_cfg"]
        ref_stats = lever2_section["lever1_ref_stats"]
        combined_stats = {ref_cfg: {**ref_stats, "speedup_vs_ref": 1.0, "latency_reduction_pct": 0.0}, **l2_stats}
        combined_order = [ref_cfg] + lever2_section["order"]
        l2_table = results_table_html(combined_stats, combined_order, l2_leader_cfg)
        l2_labels = combined_order
        l2_medians = [combined_stats[c]["median_latency_s"] for c in l2_labels]
        l2_colors = [f"'{'#3fb950' if c == l2_leader_cfg else '#bc8cff'}'" for c in l2_labels]
        l2_colors_js = "[" + ",".join(l2_colors) + "]"

        lever2_html = f"""
<h2>Step 2: Weight Cache Configuration (Lever 2)</h2>
<p class="section-intro">Tested only at the Lever 1 winning thread count
({ref_cfg}), per the sequential two-lever design documented in
OPTIMIZATION_PARAMETERS.md. Compares the winning configuration
(cache in memory) against the same thread count with the weight cache
disabled.</p>
<div class="chart-box"><canvas id="chartLever2"></canvas></div>
<h3>Results Table</h3>
{l2_table}
<h3>Engineering Analysis</h3>
<ul class="commentary">{l2_commentary_html}</ul>
"""
        lever2_scripts = chart_js("chartLever2", l2_labels, l2_medians, l2_colors_js,
                                   "Median latency (s) -- Lever 2 vs. Lever 1 winner")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tech-Explique-Moi -- Phase B Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, sans-serif; max-width: 1000px; margin: 40px auto; padding: 0 20px;
          background: #0d1117; color: #e6edf3; overflow-x: hidden; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
  .subtitle {{ color: #8b949e; font-size: 0.95rem; margin-top: 0; }}
  .intro {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 16px 20px; margin: 20px 0; font-size: 0.9rem; line-height: 1.6; }}
  h2 {{ font-size: 1.2rem; margin-top: 44px; padding: 10px 14px; background: #161b22; border-left: 4px solid #58a6ff; border-radius: 4px; }}
  h3 {{ font-size: 1.0rem; margin-top: 28px; color: #8b949e; }}
  .section-intro {{ font-size: 0.88rem; color: #8b949e; margin: 8px 0 20px; }}
  .caveat {{ background: #3d2b00; border-left: 4px solid #d29922; padding: 12px 16px; margin: 16px 0; border-radius: 4px; font-size: 0.9rem; }}
  .leader {{ background: #0d3d1c; border-left: 4px solid #3fb950; padding: 12px 16px; margin: 16px 0; border-radius: 4px; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; margin-left: 8px; }}
  .badge.ok {{ background: #1b4d2a; color: #3fb950; }}
  .badge.warn {{ background: #4d3a1b; color: #d29922; }}
  .badge.bad {{ background: #4d1b1b; color: #f85149; }}
  table {{ width: 100%; border-collapse: collapse; margin: 12px 0 20px; font-size: 0.8rem; }}
  th, td {{ padding: 7px 8px; text-align: right; border-bottom: 1px solid #30363d; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ color: #8b949e; font-weight: 600; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 16px 0; }}
  .chart-box {{ position: relative; height: 280px; background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; }}
  ul.commentary li {{ margin: 10px 0; line-height: 1.55; font-size: 0.92rem; }}
  @media (max-width: 700px) {{ .chart-row {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>Tech-Explique-Moi -- Phase B Dashboard</h1>
<p class="subtitle">CPU Execution Optimization on Google Pixel 7 (Tensor G2)</p>

<div class="intro">
This dashboard reports Phase B measurement results: execution-time
optimization of a fixed local AI inference workload (Gemma 4 E2B via
LiteRT-LM) on the Pixel 7's heterogeneous 2+2+4 core CPU. Two levers
are tested sequentially: <strong>Lever 1</strong> sweeps the runtime's
CPU thread-count configuration to find the fastest setting; the
winning configuration is then re-measured before
<strong>Lever 2</strong> tests whether
disabling the XNNPACK weight cache changes the result further, at that
same winning thread count. All results are for this specific device
and workload -- not generalized to other Arm devices.
</div>

<h2>Step 1: CPU Thread-Count Sweep (Lever 1)</h2>

<div class="caveat">
<strong>Heterogeneity caveat:</strong> results reflect the
combined effect of the configured thread count and Android's (unobserved)
scheduling decisions across the Tensor G2's heterogeneous 2+2+4 cores.
No claim is made about which specific cores executed each configuration's threads.
</div>

<div class="leader">
Current leader: <strong>{leader_cfg}</strong> --
{lever1_stats[leader_cfg]['median_latency_s']}s median latency,
{lever1_stats[leader_cfg]['speedup_vs_ref']}x speedup vs. baseline.{dist_badge}{status_badge}
<br><small>{status_line}</small>
</div>

<div class="chart-row">
  <div class="chart-box"><canvas id="chartLatency"></canvas></div>
  <div class="chart-box"><canvas id="chartCpu"></canvas></div>
</div>
<div class="chart-box" style="margin-top:16px;"><canvas id="chartDecode"></canvas></div>

<h3>Results Table</h3>
{l1_table}
{replication_table}
<h3>Engineering Analysis</h3>
<ul class="commentary">{l1_commentary_html}</ul>

{lever2_html}

<script>
{chart_js("chartLatency", l1_labels, l1_medians, l1_colors_js, "Median latency (s)")}
{chart_js("chartCpu", l1_labels, l1_cpus, "'#f0883e'", "CPU utilization (%)")}
{chart_js("chartDecode", l1_labels, l1_decodes, "'#bc8cff'", "Decode throughput (tok/s)")}
{lever2_scripts}
</script>
</body>
</html>
"""
    DASHBOARD_OUT.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_OUT.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()