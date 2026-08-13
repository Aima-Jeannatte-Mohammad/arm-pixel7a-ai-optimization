# Measurement Procedure

> **Scope**: HOW to execute a measurement, step by step, in
> chronological order. References the frozen parameters defined in
> OPTIMIZATION_PARAMETERS.md — does not redefine them here.

## Prerequisites (one-time setup, before the first measurement)

1. Pixel 7 connected via USB, `adb devices` confirms `device` status
   (not `unauthorized`).
2. `litert_lm_advanced_main` and `libGemmaModelConstraintProvider.so`
   pushed to `/data/local/tmp/` (see RUNTIME_SELECTION.md for the
   build/deployment record).
3. `gemma-4-E2B-it.litertlm` pushed to `/data/local/tmp/`, SHA256
   verified against the value recorded in MODEL_SELECTION_PROTOCOL.md.
4. The frozen doc_07 prompt file (system prompt + doc_07 source text,
   per OPTIMIZATION_PARAMETERS.md) pushed to `/data/local/tmp/` as
   `phase_b_prompt.txt`.
5. Device fully charged or charging, screen timeout disabled or
   device kept awake for the duration of the campaign (to avoid
   mid-run suspension).

## Per-run procedure

Every single measurement run, regardless of configuration, follows
this exact sequence:

1. **Readiness gate check.**
   ```
   adb shell dumpsys thermalservice | Select-String "Thermal Status"
   adb shell dumpsys battery | Select-String "level|status|Charging state"
   ```
   Compare against OPTIMIZATION_PARAMETERS.md thresholds (thermal
   status NONE/LIGHT, battery ≥20%, charging). If any parameter fails:
   wait, re-check, do not proceed until all three pass.

2. **Record device state** (thermal status, battery %, charging state,
   timestamp) — logged for every run, not just readiness-gate
   failures, per §76 of the master prompt's raw-data schema.

3. **Run the measurement.**
   ```
   adb shell "LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/litert_lm_advanced_main --backend=cpu --max_output_tokens=400 --benchmark=true --num_cpu_threads=<N> --model_path=/data/local/tmp/gemma-4-E2B-it.litertlm --input_prompt_file=/data/local/tmp/phase_b_prompt.txt"
   ```
   Omit `--num_cpu_threads=<N>` entirely for the baseline (auto)
   configuration — do not pass `--num_cpu_threads=0` as a stand-in,
   since that is not confirmed equivalent to omitting the flag (see
   OPTIMIZATION_PARAMETERS.md, baseline note).

4. **Capture the full output**, including the `BenchmarkInfo` block
   (Init phases, Time to first token, Prefill Turn, Decode Turn,
   tokens/sec for both).

5. **Verify output integrity** before logging: confirm the generated
   text matches the expected doc_07 explanation (same structure as
   Phase A's doc_07 runs) — a garbled or empty output is an
   instrumentation failure, excluded per §37 of the master prompt, not
   a valid data point.

6. **Log the run** to `data/raw/<configuration>.csv` with the full
   schema: timestamp, configuration, thread count, thermal status,
   battery %, charging state, latency (end-to-end), TTFT, prefill
   tokens/sec, decode tokens/sec, peak memory (if available), validity
   status.

7. **Recovery interval**: wait a minimum of 60 seconds (per
   OPTIMIZATION_PARAMETERS.md) before the next run's readiness check.

## Stabilization phase (per configuration)

Before the 30 valid measurement runs begin for a given configuration:

1. Run the per-run procedure above repeatedly, logging each run's
   latency into a rolling window.
2. After each run, compute the median latency of the current 5-run
   window and compare to the previous 5-run window's median.
3. Stabilization is reached when this change is under 10% (per
   OPTIMIZATION_PARAMETERS.md). Record the stabilization run count for
   this configuration.
4. All stabilization-phase runs are retained in the raw log (marked as
   `warmup`, not `valid`) — never discarded silently, per §34 of the
   master prompt.
5. Once stabilized, begin the 30 valid measurement runs (or 20, only
   if the pilot run below shows the 30-run target is infeasible within
   the project's time budget — this decision is made once, before the
   full campaign, not per-configuration).

## Configuration order

Per §45 of the master prompt, avoid running all configurations in a
fixed, always-identical order. Suggested alternating pattern for the 5
configurations (baseline, 1, 2, 4, 8 threads):

```
baseline → 4 → 1 → 8 → 2 → (repeat if multiple passes needed)
```

Record the actual order used — this is a suggested pattern, not a
requirement to follow exactly, but the realized order must be logged.

## Pilot run (before the full campaign)

Run the stabilization phase once on the baseline configuration only,
and use its actual timings to confirm or revise the OPTIMIZATION_PARAMETERS.md
time-budget estimate (~16-17s/run, ~2.5-4h total). If real timings
diverge meaningfully from the estimate, decide now — before starting
the full campaign — whether to invoke the documented 20-run fallback.
This decision, once made, applies uniformly to all 5 configurations.

## Thread-count robustness replication

After the full campaign identifies the best-performing thread-count
configuration, replicate it (10 valid runs, same procedure as above)
in a genuinely separate session — defined as: a different day, OR
after a device reboot, OR after an idle period longer than the
standard recovery interval. Record which condition applied. Compare
median latency and ranking against the original campaign's result for
that configuration and for baseline.

- If the ranking and approximate magnitude hold: mark ROBUST.
- If the ranking flips or the effect collapses within the original
  noise band: mark NOT ROBUST, and do not report this configuration as
  the final result — fall back to the next-strongest configuration
  that has itself been replicated, or report that no reproducible
  thread-count effect was established.

This step is mandatory before any final selection, per the project's
own continuation rules (do not report a thread-count "final"
configuration without this replication).

## Post-campaign

1. Confirm every configuration's raw CSV in `data/raw/` contains the
   expected number of valid runs (30, or 20 if the fallback was
   invoked) plus its full stabilization-phase log.
2. Proceed to `analysis/compute_stats.py` for aggregate statistics
   (median, mean, SD, speedup, latency reduction per §49 of the master
   prompt) — not computed manually.
3. Results, including the mandatory heterogeneity caveat and
   replication outcome, are written to
   `docs/03_experiments_results/RESULTS.md` following the presentation
   order fixed in the master prompt (§60): configuration → readiness →
   warm-up → steady-state → CPU/thread behavior (heterogeneity caveat
   first) → replication → memory → thermal → quality → comparison →
   final decision.