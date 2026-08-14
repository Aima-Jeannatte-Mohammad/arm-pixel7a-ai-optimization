# analysis/

Statistics and page generation. Both scripts are Python standard library
only and are run from the repository root.

## `compute_stats.py`

```bash
python analysis/compute_stats.py     # -> webapp/dashboard/index.html
```

**Input**: every `data/raw/*.csv`, keeping only rows where
`run_type=valid` **and** `validity=valid`.

**Computes per configuration**: n, median / mean / SD / min / max
end-to-end latency, speedup and latency reduction vs. baseline, mean
decode throughput, mean CPU %, mean peak RSS.

**Output**: a self-contained dashboard — Lever 1 sweep (charts, table,
signal check, replication verdict) and Lever 2 comparison, each with the
mandatory heterogeneity caveat and the engineering commentary.

Two behaviours to know before adding your own CSVs:

- Any `config` value **outside** `CONFIG_ORDER`
  (`baseline, threads_1, threads_2, threads_4, threads_8`) is
  auto-treated as a **Lever 2 candidate** and compared against the
  Lever 1 winner rather than against baseline. Name new configurations
  accordingly, or extend `CONFIG_ORDER` and `THREAD_COUNT_MAP` at the top
  of the file.
- The replication is matched by config name (`threads_4_replication`
  pattern), not by a column. Keep that naming convention.
- The script computes statistics; it does **not** validate that the campaign
  followed the protocol. It cannot tell that a batch ran in the wrong order
  or was recharged mid-configuration — it will happily report a clean median
  for a compromised batch. Audit the raw timestamps separately
  (`docs/03_experiments_results/OPTIMIZATION_RESULTS.md`).

Statistics are never computed by hand — the dashboard is regenerated from
the raw CSVs instead of being edited.

## `generate_model_selection_page.py`

```bash
python analysis/generate_model_selection_page.py   # -> webapp/model-selection/index.html
```

**Input**: a `DOCUMENTS` array transcribed verbatim from
`docs/03_experiments_results/MODEL_SELECTION_RESULTS.md`. It does **not**
read `data/model_selection/MODEL_SELECTION_SCORING.xlsx`, because the raw
per-criterion scores live in that workbook rather than in a
machine-readable file.

**Consequence**: if `MODEL_SELECTION_RESULTS.md` is ever revised, the
`DOCUMENTS` array **and** the `AGGREGATE` dict must be updated to match.
This coupling is deliberate and documented rather than hidden — the
alternative was parsing a spreadsheet for a static page — but it has already
drifted once: `AGGREGATE` carried a per-observation pass rate of 32/36
(88.9%) when the correct figure from the same table is 30/36 (83.3%), since
the three FAIL documents hold 2 runs each. Recheck the derived aggregates,
not just the per-document rows.

## Lint

CI runs `ruff check scripts/ analysis/` on every push and pull request
(`.github/workflows/ci.yml`). There are no unit tests: correctness here
rests on device verification and raw-data retention, not on a test suite.
