# Optimization Parameters (Phase B)

> **Scope**: WHAT is measured and WHY — the frozen workload, flags,
> thresholds and decision rules, all fixed *before* measurement began.
> For the step-by-step execution procedure see MEASUREMENT_PROCEDURE.md.
> For why these levers and not others, see
> ../01_research/OPTIMIZATION_PRE_SCREENING.md.

## Frozen workload

**`doc_07`** (TCP congestion control, RFC 5681 excerpt —
`data/documents/doc_07.txt`) is the single document used for every Phase B
run. Phase A deliberately used 15 documents to test model robustness
across varied content; Phase B measures latency across configurations,
which requires holding content constant so the tested parameter is the
only variable.

**Why `doc_07`**: closest match to Phase A's overall average — its score
(4.00/5) sits 0.08 from the 15-document mean (4.08/5), the smallest gap
of any PASS document — and its length (~214 tokens of source text) is
mid-range. Deliberately neither a best nor a worst case.

The system prompt, output format and `--max_output_tokens=400` are
unchanged from MODEL_SELECTION_PROTOCOL.md, frozen alongside the model.

### Canonical input file

`phase_b_prompt.txt` (system prompt + `doc_07`, as pushed to
`/data/local/tmp/`) is the exact, unchanging input for every run.

```
Size:   2163 bytes
SHA256: 7edcb8370dfb3b31b90e148b579dabcc488da9eb61b53838a1c2703212e4e606
```

Verify `sha256sum` on-device before every session. **Do not regenerate
this file at any point during the campaign** — a re-typed "identical"
file is not identical, and the resulting token-count mismatch is not
retroactively diagnosable (ISSUE_LOG.md #13).

The file is **not committed to this repository**: it is a build artefact
of the frozen system prompt plus `data/documents/doc_07.txt`, and the SHA256
above is what makes it verifiable rather than a copy in Git. Regenerating
it by re-concatenating those two sources is not guaranteed to reproduce
the hash (line endings and trailing whitespace both matter at byte level),
which is exactly why the original file is preserved on the measurement
host and device rather than rebuilt. Anyone reproducing the campaign on a
new device builds their own canonical file **once**, records its hash, and
then never touches it again — the requirement is a frozen, hash-locked
input, not this specific hash. That every one of the 220 rows in
`data/raw/` reports prefill = 447 tokens is the evidence that the input
held constant across this campaign.

## Frozen invocation

```
LD_LIBRARY_PATH=/data/local/tmp
--backend=cpu
--max_output_tokens=400
--benchmark=true
--cache_dir=:memory
--disable_weight_cache=false
--num_cpu_threads=<N>   # varies for Lever 1; fixed at the winner for Lever 2
--model_path=/data/local/tmp/gemma-4-E2B-it.litertlm
--input_prompt_file=/data/local/tmp/phase_b_prompt.txt
```

Both cache flags are set explicitly on **every** run, including Lever 1's
thread-count sweep, rather than relying on either flag's default. This
follows from an 11x Init Executor variance observed on the unset-flag
"default" configuration (10,769 ms vs. 941 ms on two otherwise-identical
runs) — an uncontrolled state dependency, almost certainly a stale
on-disk compilation cache, that must not be allowed to vary silently
during a comparison. See ISSUE_LOG.md #14.

Measurement binary: `litert_lm_advanced_main`, built from source
(`--config=android_arm64`). Build and deployment record in
../01_research/RUNTIME_SELECTION.md.

## Two-lever design

Two levers, tested **sequentially, not as a full factorial grid**.

### Lever 1 — CPU thread count (`--num_cpu_threads`)

Five configurations, all run with `--cache_dir=:memory
--disable_weight_cache=false` fixed, to isolate thread count from cache
state.

| Configuration | `--num_cpu_threads` | Rationale (topology from DEVICE_CHARACTERIZATION.md) |
|---|---|---|
| baseline (auto) | not set | Runtime default (0 = runtime-decided) |
| threads_1 | 1 | Single-thread floor, no parallelism |
| threads_2 | 2 | Matches the X1 (big) cluster size |
| threads_4 | 4 | Matches the A78+X1 (mid+big) cluster size |
| threads_8 | 8 | Matches full device core count |

**Baseline is an automatic default, not a configured value.** The
baseline runs with `--num_cpu_threads` *omitted from the command line*.
`0` is not passed as a stand-in, because it is not confirmed equivalent
to omitting the flag. This distinction is recorded explicitly: baseline
must not be silently compared against 1/2/4/8 as though it were another
fixed value on the same footing.

No claim is made about which specific cores the scheduler assigns to
these threads — see the heterogeneity caveat below.

### Lever 2 — Weight cache mode

Tested **only at Lever 1's winning thread count**, not across all five.

| Configuration | Setting |
|---|---|
| Cache active | `--cache_dir=:memory --disable_weight_cache=false` — already measured as Lever 1's winner, not re-run |
| Cache disabled | `--disable_weight_cache=true` — new configuration |

Empirical basis for retaining this lever, plus the source-level
confirmation that it is an XNNPACK compiled-kernel cache rather than a
model-loading optimization: see
../01_research/OPTIMIZATION_PRE_SCREENING.md.

**Documented tradeoff.** The sequential design assumes no interaction
between thread count and cache setting — an assumption *not* tested by
running the full 5×2 grid, in order to keep the campaign inside its time
budget. Planned partial mitigation: spot-check the winning and losing
thread-count configurations once under both cache settings (4 runs,
outside the valid sample) to confirm the cache effect's direction and
rough magnitude at both extremes. **Status: not executed** — no
spot-check data exists in `data/raw/`, so this assumption currently
stands untested. A full factorial remains the documented follow-up.

## Heterogeneity caveat (mandatory)

The Tensor G2's heterogeneous 2+2+4 topology means thread-count results
reflect a mixture of the configured parameter and unobserved Android
scheduler core-placement decisions. CPU affinity is out of scope, so no
attempt is made to control which cores execute which threads.

This caveat must appear **first** in any section presenting thread-count
comparisons. A robustness replication of the best configuration is
mandatory before any configuration is reported as final.

## Device and session conditions

| Parameter | Value | Rationale |
|---|---|---|
| Power | On battery, wireless ADB, USB disconnected | Simultaneous charging and CPU-bound inference are two independent heat sources — an uncontrolled thermal confound absent from normal standalone execution (ISSUE_LOG.md #12) |
| Battery floor | ≥ 50% | Raised from an initial 20% to limit within-campaign battery drift over a multi-hour session. Below 50%: pause, recharge between configurations (never during a run), resume |
| Thermal status | NONE or LIGHT only | Phase A never observed MODERATE or above across 36 runs. MODERATE+ is a stop condition, not a tested state |

Power connection is a **session-level** precondition confirmed once at
session start. Thermal status and battery level are a **per-run** gate: a
run may begin only when both pass. Session-level device isolation
(radios, updates, other apps, no physical interaction) is specified in
MEASUREMENT_PROCEDURE.md.

## Sampling rules

**Stabilization criterion**, specified to apply identically to every
configuration before its valid runs begin:

- Window: 5 consecutive runs
- Reached when the rolling median latency of the current 5-run window
  differs from the previous window's median by less than 10%
- Basis: decode-speed variance of roughly 9-16 tok/s observed on
  `doc_07`-length outputs during pilot runs
- Warm-up runs are retained in the raw log, tagged `warmup`, never
  silently discarded
- The window must run without major time gaps and with the battery floor
  holding throughout — a first attempt was discarded for breaking both
  (ISSUE_LOG.md #15)

> **Realized: not as specified.** The criterion compares the current
> window against the *previous* one, so it needs at least 10 warm-up runs
> to evaluate at all. Every configuration in `data/raw/` has exactly 5
> warm-up rows, so no comparison was ever possible — what ran was a fixed
> 5-run warm-up batch, and steady state was assumed rather than
> demonstrated. See
> ../03_experiments_results/OPTIMIZATION_RESULTS.md, "Realized vs.
> specified", deviation 3.

**Valid run count**: nominal target **30 valid runs per configuration**,
with a documented 20-run fallback if the time budget proves infeasible.
The fallback decision is made once, before the campaign, and applies
uniformly to all configurations. Realized: 30 per configuration; the
fallback was not invoked.

**Recovery interval**: minimum 60 s between configurations, before the
readiness gate is re-checked. Realized: met everywhere except the
`threads_2` → `threads_4` transition (38 s).

**Configuration order**: avoid a fixed, always-identical order — a
monotonic sweep makes thermal and battery drift correlate with the tested
parameter.

> **Realized: not as specified.** Run timestamps give
> `baseline → 1 → 2 → 4 → 8`, i.e. ascending thread count, which is the
> pattern this rule exists to prevent. Thread count is therefore
> confounded with position in the session for this campaign. Deviation 1
> in ../03_experiments_results/OPTIMIZATION_RESULTS.md.

**Time budget**: estimated pre-campaign at ~15-20 s per run with the cache
in memory (~25-30 s cache-disabled). Five Lever-1 configurations ×
(warm-up + 30 valid), plus one Lever-2 configuration × 30, plus the 10-run
replication, plus recovery intervals — several hours in total.

> **Realized: the estimate was low.** Median end-to-end latency came in at
> 24.9-37.0 s with the cache in memory and 38.2 s cache-disabled. The
> estimate was drawn from `BenchmarkInfo` inference timings, whereas the
> reported metric is host wall-clock around the whole `adb shell`
> launch-and-wait cycle. The campaign still fit its budget (~4.6 h of
> wall-clock across all seven batches), so the 20-run fallback was never
> needed, but anyone re-deriving a budget should start from ~25-40 s per
> run, not 15-20 s.

## Replication decision rule

**ROBUST requires both:**

1. The configuration still outperforms baseline in the replication
   session, **and**
2. the original and replication speedups fall on the same side of 1.0x
   (both real improvements, not one improvement and one regression).

This matches the "ranking and approximate magnitude hold" requirement
rather than an arbitrary percentage tolerance. A replication that is
*more* favourable than the original still counts as ROBUST — magnitude
drift alone does not invalidate a result whose direction and ranking are
confirmed.

If the ranking flips or the effect collapses into the original noise
band: mark NOT ROBUST, do not report that configuration as final, and
either fall back to the next-strongest replicated configuration or report
that no reproducible effect was established.

**Signal check.** Alongside the rule above, each configuration's median
gap to baseline is expressed in baseline standard deviations, and a gap is
called distinguishable only at **≥ 1.0 SD**. This is a disclosed
convention for separating a real difference from run-to-run noise, not a
statistical test — no inferential statistics are computed anywhere in this
project.

## Campaign outcome

Summary only. Full results, resource behaviour and the realized-versus-
specified audit are in
../03_experiments_results/OPTIMIZATION_RESULTS.md. The generated view is
`webapp/dashboard/index.html` (built from `data/raw/*.csv` by
`analysis/compute_stats.py`); the headline table is also in the root
README.

- **Lever 1: `threads_4` — ROBUST.** 24.874 s median vs. baseline's
  29.561 s (1.188x, 15.9% latency reduction, n=30 each), a 1.18 SD gap.
  Re-measurement: 20.682 s median, 1.429x (n=10). Ranking held, both
  speedups above 1.0x — ROBUST under the rule above. **Caveat**: that
  re-measurement ran ~5 minutes after the previous configuration in the
  same session, not in a genuinely separate one, so it is weaker evidence
  than the protocol asked for (deviation 2 in OPTIMIZATION_RESULTS.md). A
  true separate-session replication is still outstanding.
- **Lever 2: cache-disabled rejected.** At `threads_4`, disabling the
  weight cache gave 38.177 s median (0.652x, i.e. 53.5% slower) and
  nearly doubled peak RSS (4,017 MB vs. 2,231 MB). The Lever 1
  configuration with the cache active remains the best combination found.
  That batch was recharged and idled between its warm-up and valid runs
  (deviation 4), which inflates its median — the direction of the
  conclusion is safe, the magnitude is not precise.

Both results carry the heterogeneity caveat above, and both are scoped to
this one device.
