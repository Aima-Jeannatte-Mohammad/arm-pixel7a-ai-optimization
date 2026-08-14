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
requires holding content constant so the tested parameter is the only
variable that changes between runs.

**Why doc_07**: it was selected as the closest match to Phase A's
overall average, not a best- or worst-case document. Its Phase A score
(4.00/5) sits 0.08 points from the 15-document mean (4.08/5) — the
smallest gap of any PASS document — and its source length (~214
tokens, verified via Prefill Turn measurement) is within the
project's typical range, not at either extreme.

System prompt, output format, and `--max_output_tokens=400` are
unchanged from MODEL_SELECTION_PROTOCOL.md — frozen alongside the
model per §11 of the master prompt.

## Measurement binary

`litert_lm_advanced_main`, built from source via Bazel
(`android_arm64` config). See RUNTIME_SELECTION.md for the full
build/deployment record.

## Confirmed flag combination (frozen) — two-lever design

```
LD_LIBRARY_PATH=/data/local/tmp
--backend=cpu
--max_output_tokens=400
--benchmark=true
--cache_dir=:memory
--disable_weight_cache=false
--num_cpu_threads=<N>   (varies per configuration for Lever 1; fixed at winning value for Lever 2)
--model_path=/data/local/tmp/gemma-4-E2B-it.litertlm
--input_prompt_file=/data/local/tmp/phase_b_prompt.txt
```

Both cache flags (`--cache_dir` and `--disable_weight_cache`) are set
explicitly on every Phase B run, including Lever 1's thread-count
sweep, rather than relying on either flag's documented default. This
follows directly from an 11x Init Executor variance observed on the
unset-flag "default" configuration during cache-lever testing
(10,769ms vs 941ms across two otherwise-identical runs) — an
unexplained, uncontrolled state dependency (almost certainly a stale
on-disk compilation cache left by a prior run) that must not be
allowed to silently vary during the thread-count comparison either.

## Backend / XNNPACK — already resolved, no separate lever

Per RUNTIME_SELECTION.md, no independent XNNPACK toggle exists in this
runtime — `--backend=cpu` is the only CPU execution path, and it uses
XNNPACK internally. Consequently, the "XNNPACK experiment" and
"combined" experiment described in §24-25 and §52 of the master prompt
are not run as separate configurations in this project — there is no
non-XNNPACK CPU baseline to compare against.

## Two-lever design

Two independent optimization levers are tested, in sequence, not as a
full factorial design.

### Lever 1: CPU thread-count (`--num_cpu_threads`)

Baseline (auto), 1, 2, 4, 8 threads — see "Thread-count
configurations" below. Run entirely under `--cache_dir=:memory
--disable_weight_cache=false` (fixed), to isolate the thread-count
effect from the cache-state variance described above.

### Lever 2: Weight cache mode (`--cache_dir` / `--disable_weight_cache`)

Tested only at the winning thread-count from Lever 1, not across all
five thread-count values. Two configurations:

- `--cache_dir=:memory --disable_weight_cache=false` (already measured
  as part of Lever 1's winning configuration — not re-run)
- `--disable_weight_cache=true` (new configuration)

**Documented tradeoff**: this sequential design assumes no interaction
effect between thread-count and cache setting — an assumption not
formally tested by running the full 5x2 factorial grid, chosen to keep
the campaign within the project's time budget. Partial mitigation: the
winning and losing thread-count configurations from Lever 1 will each
be spot-checked once under both cache settings (4 additional runs, not
part of the 30-run valid sample) specifically to confirm the cache
effect's direction and rough magnitude hold at both extremes before
trusting the sequential result. A full factorial design remains a
documented direction for future work if this spot-check suggests a
real interaction.

### Empirical basis for Lever 2 (pilot testing, 2 runs per setting)

| Setting | Init Executor | Decode Speed |
|---|---|---|
| `--cache_dir=:memory` (run 1) | 4,981 ms | 13.71 tok/s |
| `--cache_dir=:memory` (run 2) | 5,003 ms | 14.87 tok/s |
| `--disable_weight_cache=true` (run 1) | 10,845 ms | 8.93 tok/s |
| `--disable_weight_cache=true` (run 2) | 10,987 ms | 9.73 tok/s |

Both settings were stable and reproducible across their 2 pilot runs
(unlike the unset-flag "default," which was not — see above). The gap
is large and consistent: roughly 54% faster Init Executor and ~40%
faster decode with the weight cache active. The mechanism is not yet
confirmed against the runtime's source code (only observed
empirically) — this is noted as a limitation, not claimed as fully
understood. Verifying the mechanism in `shared_flags.cc` /
`llm_litert_lib.cc` is a documented follow-up before RESULTS.md is
finalized.

## Alternative levers considered and rejected (pilot testing)

Three additional candidates were evaluated as a possible third lever
and rejected, each on a "no demonstrated gain" basis:

- **Speculative decoding** (`--enable_speculative_decoding`): functional
  (confirmed via a deterministic 43.8% MTP Drafter success rate across
  2 runs), but no measurable decode-speed improvement (14.47-14.51
  tok/s with vs. 13.71-14.88 tok/s without — overlapping ranges).
- **Local-attention ringbuffers**: flag does not exist on this binary
  (`litert_lm_advanced_main --helpfull` returned no match for "ring"
  or "attention") — likely a `pip`-CLI-only flag, not available here.
- **Constant tensor sharing** (`--share_constant_tensors`): no
  distinguishable effect (Init Executor 5,296ms vs 4,816ms, Decode
  Speed 15.72 vs 15.01 tok/s — within normal run-to-run noise observed
  elsewhere in this project).

Full rationale for each: see OPTIMIZATION_PRE_SCREENING.md.

## Thread-count configurations

Tensor G2 topology (confirmed in DEVICE_CHARACTERIZATION.md): 8 cores,
heterogeneous 4x Cortex-A55 (cores 0-3) / 2x Cortex-A78 (cores 4-5) /
2x Cortex-X1 (cores 6-7).

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
presenting thread-count comparisons. A robustness replication (best
configuration re-run in a separate session) is required before any
configuration is reported as final — see MEASUREMENT_PROCEDURE.md.

## Charging state — resolved

Phase B measurements are taken with the device disconnected from USB
power (wireless ADB), not while charging. Rationale: simultaneous
charging and CPU-bound inference introduces an uncontrolled thermal
confound (two independent heat sources) not present in normal
standalone execution.

Battery floor: ≥50%, raised from an initial 20% floor to limit
within-campaign battery-level drift across the multi-hour estimated
campaign duration. If battery drops below 50% mid-campaign, pause and
recharge (device may charge between configurations, but not during a
run) before continuing.

## Readiness gate thresholds

Per the master prompt's resolved decision (§41), device temperature is
measured exclusively via Android thermal status
(`PowerManager.getCurrentThermalStatus()`), not raw °C.

| Parameter | Accepted range | Rationale |
|---|---|---|
| Thermal status | NONE or LIGHT only | Phase A never observed MODERATE or above across 36 runs; MODERATE+ is treated as a stop condition, not a tested state |
| Battery level | ≥ 50% | See "Charging state" above |

A run may begin only when both parameters pass. Device disconnection
from USB power is a session-level precondition confirmed once at
campaign start, not re-checked per run.

## Stabilization criterion

Based on Phase A/pilot observed decode speed variance on doc_07-length
outputs (roughly 9-16 tokens/sec depending on configuration):

- **Window size**: 5 consecutive runs.
- **Tolerance**: stabilization is reached when the rolling median
  latency across the current 5-run window changes by less than 10%
  from the previous 5-run window's median.
- This criterion is applied identically to every configuration before
  its 30 valid measurement runs begin.
- A first stabilization attempt on baseline was discarded after a
  ~4-hour gap broke run continuity and battery dropped below the
  floor mid-attempt — see ISSUE_LOG.md. The window must be run without
  major time gaps and while the battery-floor condition holds
  throughout.

## Valid run count and time budget

**Nominal target: 30 valid runs per configuration**, with the
documented 20-run fallback available if the time budget does not hold
in practice.

Revised time estimate from pilot/pre-campaign runs: per-run latency
ranges roughly 15-20s under the `:memory` cache setting (cache-disabled
runs are slower, ~25-30s). With 5 Lever-1 configurations x 30 runs,
plus stabilization and recovery, plus 1 new Lever-2 configuration x 30
runs, plus the 4-run interaction spot-check, plus the 10-run robustness
replication, total campaign time is estimated in the range of several
hours. This will be confirmed empirically with a pilot run before the
full campaign begins.

## Recovery interval

A minimum of 60 seconds between measurement batches (per configuration
change), before the readiness gate is re-checked.

## Frozen input file — canonical reference

`phase_b_prompt.txt` (system prompt + doc_07, as pushed to
`/data/local/tmp/`) is the exact, unchanging input for every Phase B
run. Canonical reference:
- Size: 2163 bytes
- SHA256: `7edcb8370dfb3b31b90e148b579dabcc488da9eb61b53838a1c2703212e4e606`

Before every measurement session, verify `sha256sum` on-device matches
the value above — do not regenerate this file at any point during the
campaign.

## Replication decision rule (§54-bis) — clarified

ROBUST requires two conditions, matching the master prompt's original
"ranking and approximate magnitude" language rather than an arbitrary
percentage threshold: (1) the configuration still outperforms baseline
in the replication session, and (2) both the original and replication
speedups fall on the same side of 1.0x (both real improvements, not
one improvement and one regression). A replication that is even more
favorable than the original still counts as ROBUST under this rule —
magnitude drift alone does not invalidate a result if the direction
and ranking are confirmed.

## Lever 1 result: threads_4 VERIFIED

threads_4 (24.874s median, 1.188x speedup vs. baseline) passed §54-bis
replication: 20.682s median in a separate session (1.429x speedup),
ranking held, same order of magnitude. Confirmed as the final Lever 1
configuration. Proceeding to Lever 2 (weight cache) at threads_4.