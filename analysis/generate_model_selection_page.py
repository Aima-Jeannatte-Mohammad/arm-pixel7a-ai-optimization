"""
analysis/generate_model_selection_page.py

Generates webapp/model-selection/index.html from the Phase A model
selection results. Data below is transcribed directly from
docs/03_experiments_results/MODEL_SELECTION_RESULTS.md -- not
recomputed here, since the raw per-run scores live in
data/model_selection/MODEL_SELECTION_SCORING.xlsx, not a machine-
readable file this script reads. If MODEL_SELECTION_RESULTS.md is
ever revised, this DOCUMENTS array must be updated to match.

Usage:
    python analysis/generate_model_selection_page.py
"""

import json
from pathlib import Path

OUT = Path("webapp/model-selection/index.html")

# Transcribed verbatim from MODEL_SELECTION_RESULTS.md
DOCUMENTS = [
    {"id": "doc_01", "category": "Arm architecture (big.LITTLE)", "runs": 5, "mean_score": 4.50, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_02", "category": "Android CPU affinity (API)", "runs": 5, "mean_score": 5.00, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_03", "category": "Android Thermal API", "runs": 2, "mean_score": 4.25, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_04", "category": "Academic paper (arXiv, scheduling)", "runs": 2, "mean_score": 2.75, "critical_errors": 0, "result": "FAIL"},
    {"id": "doc_05", "category": "Linux kernel (CFS scheduler)", "runs": 2, "mean_score": 4.50, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_06", "category": "Bazel (sandboxing)", "runs": 2, "mean_score": 3.40, "critical_errors": 0, "result": "FAIL"},
    {"id": "doc_07", "category": "TCP congestion control (RFC 5681)", "runs": 2, "mean_score": 4.00, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_08", "category": "Virtual memory (Apple docs)", "runs": 2, "mean_score": 3.60, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_09", "category": "Git internals (data model)", "runs": 2, "mean_score": 3.60, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_10", "category": "Linux kernel (cgroup v2)", "runs": 2, "mean_score": 5.00, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_11", "category": "WebAssembly (W3C spec)", "runs": 2, "mean_score": 5.00, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_12", "category": "Vulkan (command buffers)", "runs": 2, "mean_score": 4.40, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_13", "category": "LLVM (IR reference)", "runs": 2, "mean_score": 3.80, "critical_errors": 0, "result": "PASS"},
    {"id": "doc_14", "category": "CUDA (thread/block/grid)", "runs": 2, "mean_score": 3.00, "critical_errors": 0, "result": "FAIL"},
    {"id": "doc_15", "category": "DNS (recursive resolver)", "runs": 2, "mean_score": 4.40, "critical_errors": 0, "result": "PASS"},
]

AGGREGATE = {
    "mean_per_doc": 4.08,
    "mean_per_observation": 4.19,
    "median_per_doc": 4.25,
    "pass_count": 12,
    "total_docs": 15,
    "pass_rate_per_doc": 80.0,
    "valid_observations": 36,
    "pass_observations": 30,
    "pass_rate_per_observation": 83.3,
    "critical_errors_total": 0,
    "threshold": 3.5,
    "threshold_pass_rate": 80.0,
}

PATTERNS = [
    ("Opening-sentence translation failure",
     ("On 5 of 15 documents (doc_04, doc_06, doc_08, doc_09, doc_12), the model's "
      "first line reproduced the source's opening sentence in English rather than "
      "translating it, despite an explicit prompt instruction. On 2 of these "
      "(doc_08, doc_09), the failure extended to several non-jargon noun phrases "
      "throughout the response.")),
    ("Isolated non-conformant arrow notation",
     ("On doc_13, the model used LaTeX notation ($\\rightarrow$) instead of the "
      "plain arrow character specified in the prompt, consistently across both runs.")),
    ("Isolated single-chain structure",
     ("On doc_14, the response was one continuous chain of 8 arrows rather than "
      "separated, line-by-line relationships seen on every other document, "
      "reducing readability.")),
    ("No inventions observed",
     ("Across all 36 observations, no run introduced a relationship, transition, "
      "or fact absent from the source. Incomplete content was always an omission, "
      "never a fabrication.")),
    ("Numerical/identifier preservation was reliable",
     ("Technical identifiers requiring exact preservation "
      "(rq->cfs.min_vruntime, cwnd, ssthresh, execroot/, vkEndCommandBuffer, "
      "VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT) were reproduced correctly "
      "in every document where they appeared.")),
]

NAV_HTML = """
<nav class="topnav">
  <div class="navbrand">Tech-Explique-Moi</div>
  <a href="../model-selection/index.html" class="navlink">Model Selection (Phase A)</a>
  <a href="../dashboard/index.html" class="navlink">Optimization Results (Phase B)</a>
  <a href="../try_it/index.html" class="navlink">Try It</a>
</nav>
"""

SHARED_CSS = """
  * { box-sizing: border-box; }
  body { font-family: -apple-system, sans-serif; max-width: 1000px; margin: 0 auto 60px; padding: 0 20px;
         background: #0d1117; color: #e6edf3; overflow-x: hidden; }
  .topnav { display: flex; align-items: center; gap: 6px; padding: 14px 0; margin-bottom: 20px;
            border-bottom: 1px solid #30363d; flex-wrap: wrap; }
  .navbrand { font-weight: 700; margin-right: 20px; color: #58a6ff; }
  .navlink { color: #8b949e; text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 0.9rem; }
  .navlink:hover { background: #161b22; color: #e6edf3; }
  h1 { font-size: 1.5rem; margin-bottom: 4px; }
  .subtitle { color: #8b949e; font-size: 0.95rem; margin-top: 0; }
  .intro { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 16px 20px; margin: 20px 0; font-size: 0.9rem; line-height: 1.6; }
  h2 { font-size: 1.2rem; margin-top: 44px; padding: 10px 14px; background: #161b22; border-left: 4px solid #58a6ff; border-radius: 4px; }
  h3 { font-size: 1.0rem; margin-top: 28px; color: #8b949e; }
  .section-intro { font-size: 0.88rem; color: #8b949e; margin: 8px 0 20px; }
  .caveat { background: #3d2b00; border-left: 4px solid #d29922; padding: 12px 16px; margin: 16px 0; border-radius: 4px; font-size: 0.9rem; }
  .leader { background: #0d3d1c; border-left: 4px solid #3fb950; padding: 12px 16px; margin: 16px 0; border-radius: 4px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; font-weight: 600; margin-left: 8px; }
  .badge.ok { background: #1b4d2a; color: #3fb950; }
  .badge.warn { background: #4d3a1b; color: #d29922; }
  .badge.bad { background: #4d1b1b; color: #f85149; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0 20px; font-size: 0.8rem; }
  th, td { padding: 7px 8px; text-align: right; border-bottom: 1px solid #30363d; }
  th:first-child, td:first-child { text-align: left; }
  th { color: #8b949e; font-weight: 600; }
  .chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 16px 0; }
  .chart-box { position: relative; height: 280px; background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; }
  ul.commentary li, ul.patterns li { margin: 10px 0; line-height: 1.55; font-size: 0.92rem; }
  .stat-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 16px 0; }
  .stat-card { background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 14px; text-align: center; }
  .stat-card .value { font-size: 1.6rem; font-weight: 700; color: #58a6ff; }
  .stat-card .label { font-size: 0.75rem; color: #8b949e; margin-top: 4px; }
  @media (max-width: 700px) { .chart-row { grid-template-columns: 1fr; } }
"""


def main():
    pass_count = sum(1 for d in DOCUMENTS if d["result"] == "PASS")
    fail_count = len(DOCUMENTS) - pass_count
    labels = [d["id"] for d in DOCUMENTS]
    scores = [d["mean_score"] for d in DOCUMENTS]
    colors = ["'#3fb950'" if d["result"] == "PASS" else "'#f85149'" for d in DOCUMENTS]
    colors_js = "[" + ",".join(colors) + "]"

    rows_html = "".join(
        f'<tr><td>{d["id"]}</td><td style="text-align:left">{d["category"]}</td>'
        f'<td>{d["runs"]}</td><td>{d["mean_score"]:.2f}</td><td>{d["critical_errors"]}</td>'
        f'<td><span class="badge {"ok" if d["result"]=="PASS" else "bad"}">{d["result"]}</span></td></tr>'
        for d in DOCUMENTS
    )

    patterns_html = "".join(
        f"<li><strong>{title}.</strong> {desc}</li>" for title, desc in PATTERNS
    )

    decision_class = "ok" if AGGREGATE["pass_rate_per_doc"] >= AGGREGATE["threshold_pass_rate"] else "bad"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tech-Explique-Moi -- Model Selection (Phase A)</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>{SHARED_CSS}</style>
</head>
<body>
{NAV_HTML}

<h1>Model Selection Results -- Phase A</h1>
<p class="subtitle">Feasibility validation of Gemma 4 E2B before Phase B optimization</p>

<div class="intro">
Before testing any execution-level optimization, the project first validated
that the chosen model (Gemma 4 E2B, via LiteRT-LM) produces technically
meaningful, faithful output on the fixed workload -- translating English
technical documentation into compact French arrow-schemas. This page reports
that validation: 15 frozen technical documents, scored against a fixed
rubric (technical correctness, meaningfulness, semantic preservation,
terminology handling, critical errors), with an 80% pass-rate threshold set
<em>before</em> any output was scored. Full protocol:
<code>docs/02_protocols/MODEL_SELECTION_PROTOCOL.md</code>. Full results:
<code>docs/03_experiments_results/MODEL_SELECTION_RESULTS.md</code>.
</div>

<div class="leader">
Decision: <strong>MODEL RETAINED</strong>
<span class="badge {decision_class}">{AGGREGATE['pass_rate_per_doc']}% PASS RATE</span>
<br><small>{AGGREGATE['pass_count']}/{AGGREGATE['total_docs']} documents passed
(threshold: {AGGREGATE['threshold_pass_rate']}%), zero critical semantic errors
across {AGGREGATE['valid_observations']} observations.</small>
</div>

<div class="stat-cards">
  <div class="stat-card"><div class="value">{AGGREGATE['mean_per_doc']}</div><div class="label">Mean score /5 (per-document)</div></div>
  <div class="stat-card"><div class="value">{AGGREGATE['median_per_doc']}</div><div class="label">Median score /5</div></div>
  <div class="stat-card"><div class="value">{AGGREGATE['pass_count']}/{AGGREGATE['total_docs']}</div><div class="label">Documents PASS</div></div>
  <div class="stat-card"><div class="value">{AGGREGATE['critical_errors_total']}</div><div class="label">Critical errors (of {AGGREGATE['valid_observations']} runs)</div></div>
</div>

<h2>Per-Document Scores</h2>
<div class="chart-box"><canvas id="chartScores"></canvas></div>

<h3>Full Results Table</h3>
<table>
<tr><th>Document</th><th>Category</th><th>Runs</th><th>Mean score</th><th>Critical errors</th><th>Result</th></tr>
{rows_html}
</table>

<h2>Recurring Output Patterns (Observations)</h2>
<p class="section-intro">Documented for transparency, per the project's
observation/interpretation discipline -- these are what was measured, not
corrected, since the model and prompt are frozen once Phase A validation
begins.</p>
<ul class="patterns">{patterns_html}</ul>

<script>
new Chart(document.getElementById('chartScores'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(labels)},
    datasets: [{{ label: 'Mean score (/5)', data: {json.dumps(scores)}, backgroundColor: {colors_js} }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'Green = PASS, Red = FAIL (threshold: {AGGREGATE["threshold"]}/5)', color: '#e6edf3' }} }},
    scales: {{ y: {{ beginAtZero: true, max: 5, title: {{ display: true, text: 'Score', color: '#8b949e' }} }},
               x: {{ ticks: {{ color: '#e6edf3' }} }} }}
  }}
}});
</script>
</body>
</html>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"Written to {OUT}")
    print(f"Pass: {pass_count}/{len(DOCUMENTS)}, Fail: {fail_count}/{len(DOCUMENTS)}")


if __name__ == "__main__":
    main()
