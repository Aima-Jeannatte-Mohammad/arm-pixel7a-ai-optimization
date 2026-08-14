# data/

Raw, un-aggregated evidence. Nothing here is edited by hand after a run.

```
documents/       Phase A corpus, doc_01.txt .. doc_15.txt (doc_07 = frozen Phase B workload)
model_selection/ MODEL_SELECTION_SCORING.xlsx -- per-criterion scores for all 36 Phase A observations
raw/             Phase B per-run measurement CSVs, one row per run
```

## `raw/` files

| File | Contents |
|---|---|
| `baseline.csv`, `threads_1.csv`, `threads_2.csv`, `threads_4.csv`, `threads_8.csv` | Lever 1 sweep. 5 warm-up + 30 valid runs each |
| `threads_4_replication.csv` | Robustness re-measurement of the Lever 1 winner. 10 valid runs |
| `threads_4_nocache.csv` | Lever 2, `--disable_weight_cache=true` at the winning thread count. 5 warm-up + 30 valid runs |

220 rows total, all recorded on 2026-08-14 between 18:51 and 23:29 local
time. Every row reports `prefill_tokens=447`, confirming the frozen input
never changed.

**Read the timestamp and battery columns before trusting a batch.** They
are what revealed the four protocol deviations documented in
`docs/03_experiments_results/OPTIMIZATION_RESULTS.md` — the ascending
configuration order, `threads_4_replication.csv` running only ~5 minutes
after the previous configuration in the same session, exactly 5 warm-up rows
everywhere (too few to evaluate the stabilization criterion), and
`threads_4_nocache.csv` jumping from 55% to 70% battery between its warm-up
and valid batches, i.e. recharged mid-configuration. None of that is visible
in the latency column alone.

Written by `scripts/run_config.py` (append-only). Consumed by
`analysis/compute_stats.py`, which keeps only rows where
`run_type=valid` **and** `validity=valid`.

## Row schema

| Column | Meaning |
|---|---|
| `timestamp` | Local time the run started |
| `config` | Configuration name, also the dashboard label |
| `threads` | `--num_cpu_threads` value, or `auto` when the flag was omitted |
| `run_type` | `warmup` (stabilization, excluded from statistics) or `valid` |
| `thermal_status_start` / `thermal_status_end` | Android aggregate thermal status (`0`=NONE, `1`=LIGHT) |
| `battery_pct_start` | Battery level at the readiness gate |
| `end_to_end_latency_s` | Host wall-clock for the full launch-and-wait cycle. **Primary metric** |
| `init_total_ms`, `time_to_first_token_s` | From the binary's `BenchmarkInfo` block |
| `prefill_tokens`, `prefill_speed_tok_s`, `decode_tokens`, `decode_speed_tok_s` | From `BenchmarkInfo` |
| `peak_rss_kb` | Max `VmHWM` from `/proc/<PID>/status`, polled ~1 Hz |
| `cpu_pct` | `(utime+stime)` delta over wall-clock. Percent of **one** core, top-style — up to ~800% on this 8-core device |
| `validity` | `valid`, or `invalid` for an instrumentation failure |
| `exclusion_reason` | Populated only when `validity=invalid` |

Retention rule: warm-up runs and invalid runs are **kept**, labelled, and
excluded at analysis time. Nothing is deleted to make a result look
cleaner.

Measurement limits for each column (what these numbers can and cannot
support) are documented in the root README, section "Measured quantities
and their limits".

## Not in Git

The model (`*.litertlm`, 2.59 GB) and built binaries are gitignored. See
the root README for how to obtain and verify them.
