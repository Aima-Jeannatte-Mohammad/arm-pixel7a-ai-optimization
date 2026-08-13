# Optimization Parameters

> **Scope**: WHAT is tested and WHY — frozen parameters, thresholds,
> and decisions, fixed before any measurement. For the step-by-step
> procedure that uses these parameters, see MEASUREMENT_PROCEDURE.md.

## Fixed workload for Phase B

**doc_07** (TCP congestion control, RFC 5681 excerpt — see
`data/documents/doc_07.txt`) is the single, frozen document used for
every Phase B measurement, per §5 of the master prompt ("the same
workload must be used for baseline, thread-count configurations...").
Phase A used 15 documents deliberately to test model robustness across
varied content; Phase B measures latency across configurations, which
requires holding content constant so thread-count is the only variable
that changes between runs.

**Why doc_07**: it was selected as the closest match to Phase A's
overall average, not a best- or worst-case document. Its Phase A score
(4.00/5) sits 0.08 points from the 15-document mean (4.08/5) — the
smallest gap of any PASS document — and its source length (~214
tokens, verified via Prefill Turn measurement) is within the
project's typical range, not at either extreme (`doc_04` and `doc_14`,
both FAILs, were excluded from consideration on this basis alone; very
short documents like `doc_10`/`doc_11`, both 5.0/5, were excluded as
unrepresentatively favorable). A workload chosen for being typical,
rather than a best or worst case, gives Phase B's latency comparisons
the best chance of reflecting normal operating conditions rather than
an edge case.

System prompt, output format, and `--max_output_tokens=400` are
unchanged from MODEL_SELECTION_PROTOCOL.md — frozen alongside the
model per §11 of the master prompt.

## Measurement binary

`litert_lm_advanced_main`, built from source via Bazel
(`android_arm64` config). See RUNTIME_SELECTION.md for the full
build/deployment record.

## Confirmed flag combination (frozen)

```
LD_LIBRARY_PATH=/data/local/tmp
--backend=cpu
--max_output_tokens=400
--benchmark=true
--num_cpu_threads=<N>   (varies per configuration, see below)
--model_path=/data/local/tmp/gemma-4-E2B-it.litertlm
--input_prompt_file=/data/local/tmp/<frozen doc_07 prompt file>
```

`--num_cpu_threads` is the only parameter that changes between
configurations. All other flags are fixed across every run in Phase B.

## Backend / XNNPACK — already resolved, no separate lever

Per RUNTIME_SELECTION.md, no independent XNNPACK toggle exists in this
runtime — `--backend=cpu` is the only CPU execution path, and it uses
XNNPACK internally. Consequently:

- The "XNNPACK experiment" described in §24-25 of the master prompt is
  **not run as a separate configuration** in this project. There is no
  non-XNNPACK CPU baseline to compare against.
- The "combined" experiment (§52 of the master prompt, thread-count +
  XNNPACK) **collapses into the thread-count sweep itself** — since
  XNNPACK is always active on the CPU backend, every thread-count
  configuration already includes it.
- This is stated explicitly here so it is not rediscovered mid-campaign:
  Phase B has **one lever, not two** (thread-count), contrary to the
  two-lever design originally set out in §17 of the master prompt. This
  deviation is sourced directly from RUNTIME_SELECTION.md's empirical
  verification, not a late scope change.

## Thread-count configurations

Tensor G2 topology (confirmed in DEVICE_CHARACTERIZATION.md): 8 cores,
heterogeneous 4× Cortex-A55 (cores 0-3) / 2× Cortex-A78 (cores 4-5) /
2× Cortex-X1 (cores 6-7).

Configurations to test:

| Configuration | `--num_cpu_threads` | Rationale |
|---|---|---|
| Baseline (auto) | not set (runtime default, 0) | Documented default behavior — see baseline note below |
| Threads = 1 | 1 | Single-thread floor, no parallelism |
| Threads = 2 | 2 | Matches the X1 (big) cluster size |
| Threads = 4 | 4 | Matches the A78+X1 (mid+big) combined cluster size |
| Threads = 8 | 8 | Matches full device core count |

Per §23 of the master prompt, no claim will be made about which
specific cores the scheduler assigns to these threads — the
heterogeneity confound is addressed separately below.

## Baseline thread configuration — documented default vs. explicit value

Per §30 of the master prompt: the baseline configuration runs with
`--num_cpu_threads` **not set on the command line**, relying on the
runtime's own default (documented in RUNTIME_SELECTION.md as `0`,
meaning runtime-decided/auto). This is recorded explicitly as an
**automatic default**, not an explicitly configured thread count — it
must not be silently compared against the manually-set configurations
(1/2/4/8) as if it were just another fixed value on the same footing.

## CPU heterogeneity confound — mandatory caveat

The Tensor G2's heterogeneous 2+2+4 topology means thread-count results
reflect a mixture of the configured parameter and unobserved Android
scheduler core-placement decisions (per §19, CPU affinity is out of
scope — no attempt is made to control which cores execute which
threads). This caveat must appear first in any RESULTS.md section
presenting thread-count comparisons, per the master prompt's own
§23-bis discipline established during planning. A robustness
replication (best configuration re-run in a separate session) is
required before any configuration is reported as final — see
MEASUREMENT_PROCEDURE.md.

## Charging state — resolved

Phase B measurements are taken with the device disconnected from USB
power (wireless ADB), not while charging. Rationale: simultaneous
charging and CPU-bound inference introduces an uncontrolled thermal
confound (two independent heat sources) not present in normal
standalone execution. This differs from Phase A, which ran while
charging (a choice made for setup convenience, not deliberate control,
per ISSUE_LOG.md).

Battery floor raised from ≥20% to ≥50% specifically to limit
within-campaign battery-level drift across the ~2.5-4h estimated
campaign duration — configurations tested later in the campaign should
not run under meaningfully different battery conditions than those
tested first. If battery drops below 50% mid-campaign, pause and
recharge before continuing; do not lower this threshold retroactively.

"Charging state" is removed as a separate readiness-gate parameter —
the gate becomes: thermal status (NONE/LIGHT) + battery ≥50%. Device
is confirmed disconnected from USB power for the entire campaign, not
checked per-run (it is a session-level condition, not a per-run one).

## Readiness gate thresholds

| Parameter | Accepted range | Rationale |
|---|---|---|
| Thermal status | NONE or LIGHT only | Phase A never observed MODERATE or above across 36 runs; MODERATE+ is treated as a stop condition, not a tested state |
| Battery level | ≥ 50% | Raised from an initial 20% floor to limit within-campaign battery-level drift over the ~2.5-4h estimated campaign, given the device runs unplugged (see Charging state note above) |

A run may begin only when both parameters pass. Device disconnection
from USB power is a session-level precondition confirmed once at
campaign start, not re-checked per run.

## Stabilization criterion

Based on Phase A's observed decode speed variance on doc_07-length
outputs (13.97–15.44 tokens/sec across repeated runs, a ~10% band):

- **Window size**: 5 consecutive runs.
- **Tolerance**: stabilization is reached when the rolling median
  latency across the current 5-run window changes by less than 10%
  from the previous 5-run window's median.
- This criterion is applied identically to every configuration before
  its 30 valid measurement runs begin (§32-34 of the master prompt).

## Valid run count and time budget

**Nominal target: 30 valid runs per configuration** (§35-36 of the
master prompt), with the documented 20-run fallback available if the
time budget calculation below does not hold in practice.

Time budget estimate, from Phase A's real measured timings on
doc_07-length content:
- Per-run latency (post-warm-up, cache warm): ~0.5s init + ~3s TTFT +
  ~13s decode (200 tokens @ ~15 tok/s) ≈ **16-17s per run**.
- 5 configurations (baseline + 4 thread counts) × 30 runs × ~17s ≈
  **42.5 minutes of pure inference time**, before accounting for the
  stabilization phase (5-10 extra runs per configuration) and recovery
  intervals between batches.
- With stabilization and recovery, total campaign time is estimated at
  **2.5-4 hours**, feasible within the project's time budget without
  invoking the 20-run fallback. This estimate will be confirmed
  empirically with a pilot run before the full campaign begins (see
  MEASUREMENT_PROCEDURE.md).

## Recovery interval

A minimum of 60 seconds between measurement batches (per configuration
change), before the readiness gate is re-checked. This is a starting
value, not empirically derived from Phase A (Phase A's device-state
logs do not include recovery-interval data, since Phase A did not use
the strict Phase B gate) — to be adjusted if the pilot run shows
thermal status frequently failing to return to NONE/LIGHT within this
window.

## Frozen input file — canonical reference

`phase_b_prompt.txt` (system prompt + doc_07, as pushed to
`/data/local/tmp/`) is the exact, unchanging input for every Phase B
run. Canonical reference:
- Size: 2163 bytes
- SHA256: 7edcb8370dfb3b31b90e148b579dabcc488da9eb61b53838a1c2703212e4e606

This file's Prefill Turn token count (447, confirmed via a verified
run) is the Phase B baseline reference -- it is not required to match
Phase A's doc_07 prefill count (464), since Phase A's exact historical
file could not be byte-verified retroactively. Phase B's internal
consistency (same file across all configurations) is what matters for
valid relative comparisons, not parity with a prior phase's number.
Before every future measurement, verify `sha256sum` on-device matches
the value above -- do not regenerate this file at any point during
the campaign.
