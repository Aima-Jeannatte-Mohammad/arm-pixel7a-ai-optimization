# Measurement Procedure (Phase B)

> **Scope**: HOW a measurement is executed, in chronological order. The
> frozen parameters, thresholds and decision rules it applies are defined
> in OPTIMIZATION_PARAMETERS.md and are not redefined here.

Order of this document = order of execution: one-time setup → per-session
preconditions → per-run procedure → per-configuration sampling →
campaign-level steps.

## 1. One-time setup

1. `adb devices` reports the device as `device` (not `unauthorized`).
2. `litert_lm_advanced_main` and `libGemmaModelConstraintProvider.so`
   pushed to `/data/local/tmp/`, binary made executable. See
   ../01_research/RUNTIME_SELECTION.md for the build record and the
   mandatory `LD_LIBRARY_PATH` constraint.
3. `gemma-4-E2B-it.litertlm` pushed to `/data/local/tmp/`, SHA256 verified
   against MODEL_SELECTION_PROTOCOL.md.
4. `phase_b_prompt.txt` pushed to `/data/local/tmp/`, SHA256 verified
   against OPTIMIZATION_PARAMETERS.md.
5. One manual run executed end-to-end and inspected by hand, before any
   automated batch: confirm a French arrow-schema output and a populated
   `BenchmarkInfo` block. A `Failed to get decode profile summary:
   INVALID_ARGUMENT` warning is expected and harmless (ISSUE_LOG.md #8).

## 2. Per-session preconditions

Confirmed **once** at session start, not re-checked per run. Two batches
were discarded for violating these (ISSUE_LOG.md #15, #16) — they are not
optional.

1. **Wireless ADB, device disconnected from power.** `adb tcpip 5555`,
   then `adb connect <device-ip>:5555`, then unplug USB. Measurements run
   on battery: charging plus CPU-bound inference is a second,
   uncontrolled heat source.
2. **Battery ≥ 50%** at session start, and expected to hold for the
   session's duration.
3. **Airplane Mode on, then Wi-Fi re-enabled on top.** Disables cellular
   and Bluetooth — both can wake device components and consume CPU
   unpredictably — while preserving wireless ADB. Re-confirm `adb devices`
   afterwards.
4. **Automatic app updates disabled** (Play Store). A background download
   or install during a 30-minute batch is an uncontrolled CPU and network
   confound.
5. **Other apps closed.** A competing process corrupts both latency and
   the `cpu_pct` reading.
6. **No physical interaction with the device during measurement.** No
   screen wake, no touch, no app switching. The screen may time out and
   turn off on its own — that is expected and does not affect the run,
   since the binary executes independently of display state.

If the device is handled or reconnected mid-session (for example after a
battery pause), re-confirm all six before resuming, and note the
interruption in the raw log rather than continuing silently.

## 3. Per-run procedure

Every run, in every configuration, follows this sequence. All of it is
implemented by `scripts/run_config.py` — steps are listed here because
the harness is the executable form of this protocol, not a replacement
for it.

1. **Readiness gate.** Read thermal status (`dumpsys thermalservice`) and
   battery level (`dumpsys battery`). Proceed only when thermal status is
   NONE or LIGHT **and** battery ≥ 50%. Otherwise wait and re-check; do
   not proceed on a partial pass.
   An adb-level failure (ambiguous device, offline, daemon unreachable)
   is a **hard stop**, never treated as "not ready" and never retried in
   a loop (ISSUE_LOG.md #11).
2. **Record device state** — thermal status, battery %, timestamp — for
   every run, not only for gate failures.
3. **Run the measurement** with the frozen invocation from
   OPTIMIZATION_PARAMETERS.md. Omit `--num_cpu_threads` entirely for the
   baseline configuration; do not pass `0` as a stand-in.
4. **Capture the full output**, including the `BenchmarkInfo` block (init
   phases, time to first token, prefill and decode turns, tokens/sec).
5. **Collect resource metrics** by polling `/proc/<PID>/status` (`VmHWM`
   → peak RSS) and `/proc/<PID>/stat` (`utime`+`stime` → CPU %) at ~1 Hz
   for the process's lifetime. The PID must be the binary's own — the
   launch uses `exec` so the background job's PID is not an intermediate
   shell's (ISSUE_LOG.md #10).
6. **Verify output integrity** before logging: the generated text must
   match the expected `doc_07` explanation structure. Garbled or empty
   output is an instrumentation failure, not a data point.
7. **Log the run** to `data/raw/<configuration>.csv` with the full
   schema: timestamp, configuration, thread count, run type, thermal
   status (start and end), battery %, end-to-end latency, init total,
   TTFT, prefill tokens and speed, decode tokens and speed, peak RSS, CPU
   %, validity, exclusion reason. A run that fails `BenchmarkInfo`
   parsing is written as `invalid` **with** a reason — never dropped.
8. **Recovery interval** before the next readiness check.

## 4. Per-configuration sampling

1. **Stabilization first.** Run the per-run procedure repeatedly, tagged
   `warmup`, until the rolling 5-run median latency changes by less than
   10% from the previous 5-run window. Record the stabilization run count.
   Warm-up rows stay in the raw CSV, excluded from statistics but never
   deleted. Note that comparing two windows takes a **minimum of 10**
   warm-up runs — this campaign ran a fixed 5 per configuration and so
   never actually evaluated the criterion (deviation 3 in
   ../03_experiments_results/OPTIMIZATION_RESULTS.md).
2. **Then the valid sample**: 30 runs tagged `valid` (or 20, only if the
   pilot showed 30 to be infeasible — decided once, before the campaign,
   and applied uniformly).
3. The stabilization window must run without major time gaps and with the
   battery floor holding throughout. If either breaks, discard the batch
   and restart from run 1 rather than patching it.

**Configuration order**: do not run all configurations in a fixed,
always-identical order, and in particular not in ascending or descending
parameter order — that makes session-position drift indistinguishable from
the parameter's effect. Log the realized order, and verify it against the
CSV timestamps rather than from memory: this campaign's logged order turned
out to disagree with its own data (deviation 1 in
../03_experiments_results/OPTIMIZATION_RESULTS.md).

**Pilot**: run stabilization once on baseline before the full campaign and
use its real timings to confirm or revise the time-budget estimate in
OPTIMIZATION_PARAMETERS.md, and therefore whether the 20-run fallback is
needed.

## 5. Robustness replication (mandatory)

After the campaign identifies the best-performing configuration, replicate
it — 10 valid runs, identical procedure — in a **genuinely separate
session**, defined as: a different day, **or** after a device reboot,
**or** after an idle period substantially longer than the standard
recovery interval. Record which condition applied.

Compare median latency and ranking against the original campaign result
for that configuration and for baseline, then apply the ROBUST decision
rule in OPTIMIZATION_PARAMETERS.md.

No configuration may be reported as final without this step.

> **Realized: the separation condition was not met.** The `threads_4`
> re-measurement ran 311 s after the previous configuration's last run, on
> the same day and in the same uninterrupted session, with no reboot and no
> condition recorded. It is a within-session re-measurement, not a
> replication in the sense defined above. Deviation 2 in
> ../03_experiments_results/OPTIMIZATION_RESULTS.md.

## 6. Post-campaign

1. Confirm every configuration's CSV in `data/raw/` contains the expected
   number of valid runs plus its full stabilization log.
2. Compute aggregate statistics with `python analysis/compute_stats.py` —
   median, mean, SD, min, max, speedup, latency reduction, decode
   throughput, CPU %, peak RSS. Never by hand. The script consumes only
   rows where `run_type=valid` and `validity=valid`, and regenerates
   `webapp/dashboard/index.html`.
3. Report results in this order: configuration → readiness → warm-up →
   steady state → CPU/thread behaviour (**heterogeneity caveat first**) →
   replication → memory → thermal → quality → comparison → final
   decision. This order is realized on the generated dashboard, in
   ../03_experiments_results/OPTIMIZATION_RESULTS.md, and in summary in the
   root README.
4. **Audit the realized campaign against this protocol** before publishing
   any figure: re-read `data/raw/*.csv` timestamps and battery columns and
   check the actual configuration order, the gap and power state around the
   replication batch, the warm-up run count per configuration, and the
   inter-configuration recovery intervals. Doing this after the fact on
   this campaign surfaced four deviations that the run logs alone did not
   make obvious — they are recorded in
   ../03_experiments_results/OPTIMIZATION_RESULTS.md, "Realized vs.
   specified". Deviations get disclosed, not smoothed over.
