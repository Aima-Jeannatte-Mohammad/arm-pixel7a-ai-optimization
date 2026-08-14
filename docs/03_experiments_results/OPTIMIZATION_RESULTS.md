# Optimization Results (Phase B)

> **Scope**: the outcome of the two-lever campaign specified in
> ../02_protocols/OPTIMIZATION_PARAMETERS.md and executed per
> ../02_protocols/MEASUREMENT_PROCEDURE.md — plus an audit of where the
> realized campaign departed from that specification. Per-run raw data is
> in `data/raw/*.csv`; the generated view is
> `webapp/dashboard/index.html`. This document reports the summary and the
> deviations, not a copy of the raw rows.

Every number here is produced by `python analysis/compute_stats.py` from
the CSVs, on rows where `run_type=valid` **and** `validity=valid`. None of
it is hand-transcribed arithmetic.

## Heterogeneity caveat (first, per protocol)

The Tensor G2 CPU is heterogeneous (4x Cortex-A55, 2x Cortex-A78,
2x Cortex-X1). CPU affinity is out of scope by design, so every
thread-count result below reflects **the configured parameter mixed with
unobserved Android scheduler core-placement decisions**. No claim is made
about which cores executed any configuration's threads.

## Lever 1 — CPU thread count

30 valid runs per configuration, 5 retained warm-up runs each, single
frozen input (`phase_b_prompt.txt`, prefill = 447 tokens on all 220 rows).

| Config | threads | n | median (s) | mean (s) | SD (s) | min (s) | max (s) | speedup | reduction | gap vs. baseline |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline (auto) | auto | 30 | 29.561 | 27.711 | 3.981 | 19.771 | 32.880 | 1.000x | — | — |
| threads_1 | 1 | 30 | 37.007 | 38.269 | 6.761 | 29.167 | 52.479 | 0.799x | -25.2% | 1.87 SD (slower) |
| threads_2 | 2 | 30 | 28.252 | 27.350 | 4.252 | 21.479 | 34.081 | 1.046x | +4.4% | 0.33 SD |
| **threads_4** | **4** | **30** | **24.874** | **24.308** | **2.123** | **18.337** | **26.783** | **1.188x** | **+15.9%** | **1.18 SD** |
| threads_8 | 8 | 30 | 30.038 | 29.852 | 1.867 | 26.250 | 32.811 | 0.984x | -1.6% | 0.12 SD |

**Winner: `threads_4`.** The gap to baseline is 1.18 baseline standard
deviations, which clears the project's own ≥ 1 SD bar for calling a
difference distinguishable from run-to-run noise rather than a rounding
artefact. `threads_2` (0.33 SD) and `threads_8` (0.12 SD) do **not** clear
it and are reported as indistinguishable from baseline, regardless of the
direction their medians happen to point.

**The reported speedup depends on choosing the median.** Baseline is
left-skewed — mean 27.711 s sits below median 29.561 s, with a fast tail
down to 19.771 s — so on means the same comparison gives 1.140x rather
than 1.188x. Median is the primary statistic throughout this project
(fixed before measurement, and the more robust choice on n=30 with visible
tails), but the mean-based figure is stated here so the choice is visible
rather than convenient. Both agree on direction and on the ranking.

### Resource behaviour

| Config | decode (tok/s) | CPU (%) | peak RSS (MB) |
|---|---|---|---|
| baseline | 11.61 | 283.7 | 2214.0 |
| threads_1 | 7.40 | 96.7 | 2162.7 |
| threads_2 | 11.03 | 166.1 | 2236.3 |
| threads_4 | 12.98 | 284.5 | 2230.9 |
| threads_8 | 10.02 | 499.8 | 2130.1 |

Two observations, kept separate from interpretation:

1. **CPU utilization is monotonic in thread count; latency is not.**
   96.7% → 166.1% → 284.5% → 499.8% confirms `--num_cpu_threads` genuinely
   engages more cores. Yet 8 threads is slower than 4. This is *consistent
   with* the A55 little cores landing on the critical path once all
   clusters are engaged, but core placement is not observed here, so that
   remains a hypothesis, not a finding.
2. **`baseline` and `threads_4` draw nearly identical total CPU**
   (283.7% vs. 284.5%) while differing in median latency (29.561 s vs.
   24.874 s) and in spread (SD 3.981 s vs. 2.123 s). Same CPU budget,
   different outcome and different stability. Again: an observation, with
   no mechanism claimed.

Peak RSS is flat across all five configurations (2130–2236 MB), so thread
count is not a memory lever on this workload.

## Lever 1 — replication

| | n | median (s) | mean (s) | SD (s) | speedup vs. baseline |
|---|---|---|---|---|---|
| Original campaign | 30 | 24.874 | 24.308 | 2.123 | 1.188x |
| Replication | 10 | 20.682 | 22.107 | 2.934 | 1.429x |

**Verdict: ROBUST**, under the rule in OPTIMIZATION_PARAMETERS.md —
`threads_4` still beat baseline, and both speedups fall on the same side
of 1.0x. A replication that is *more* favourable does not invalidate a
confirmed ranking and direction.

**But the replication's independence is weaker than the protocol asked
for.** See "Realized vs. specified" below: it was run inside the same
session, roughly 5 minutes after the previous configuration, not on a
separate day or after a reboot. The 17% median gap between 24.874 s and
20.682 s is itself evidence of how much between-batch state matters on
this device, which is precisely what a genuinely separate session was
supposed to probe. The verdict stands as recorded; its evidential weight
is lower than the protocol intended.

## Lever 2 — weight cache mode

Tested only at Lever 1's winning thread count, so this compares against
`threads_4`, not against baseline.

| Config | median (s) | SD (s) | vs. threads_4 | decode (tok/s) | peak RSS (MB) |
|---|---|---|---|---|---|
| threads_4 (cache in memory) | 24.874 | 2.123 | 1.000x | 12.98 | 2230.9 |
| threads_4_nocache | 38.177 | 2.289 | 0.652x (53.5% slower) | 9.19 | 4017.4 |

**Outcome: cache-disabled rejected.** Disabling the weight cache costs
53.5% latency, drops decode throughput by 29%, and nearly doubles peak
RSS. The best combination found is **4 threads with the weight cache in
memory** — Lever 2 does not improve on Lever 1's winner, it confirms it.

The peak-RSS near-doubling (2231 → 4017 MB) is the more interesting
result: without the XNNPACK weight cache the runtime holds substantially
more resident memory, on a device with ~7.3 GB total and roughly 2 GB
typically available. This is a memory-*and*-latency regression, not a
tradeoff.

## Realized vs. specified

Auditing `data/raw/*.csv` timestamps against the protocol after the
campaign closed surfaced four deviations. They are recorded here rather
than corrected, because the data cannot be re-collected retroactively and
silently restating the specification would be worse than disclosing the
gap.

**1. Configuration order was ascending, not interleaved.** The protocol
requires avoiding a fixed, monotonic order so that thermal and battery
drift do not correlate with the tested parameter. Realized order, from
run timestamps (all on 2026-08-14):

| Order | Config | First run | Last run ends |
|---|---|---|---|
| 1 | baseline | 18:51:49 | 19:14:28 |
| 2 | threads_1 | 19:16:35 | 19:48:10 |
| 3 | threads_2 | 21:03:01 | 21:29:39 |
| 4 | threads_4 | 21:30:17 | 21:51:23 |
| 5 | threads_8 | 21:53:00 | 22:13:58 |

That is `baseline → 1 → 2 → 4 → 8` — monotonically increasing in thread
count, exactly the pattern the rule exists to prevent. Earlier revisions
of this repo recorded the realized order as `baseline → 4 → 1 → 8 → 2`;
the timestamps do not support that, and the ascending order is the correct
record. **Consequence**: thread count is confounded with position in the
session for this campaign. The winner `threads_4` ran fourth, after ~2.6 h
of device use, and still produced the lowest median and the second-lowest
SD — the confound therefore does not obviously favour it, but it is not
controlled.

**2. The replication was not a separate session.** The protocol defines
that as a different day, a device reboot, or an idle period substantially
longer than the recovery interval, and requires recording which condition
applied. Realized: the replication's 10 valid runs ran 22:19:09–22:23:53,
**311 s (~5.2 min) after `threads_8`'s last run ended**, on the same day,
in the same uninterrupted session, and *before* the Lever 2 configuration.
No reboot is recorded. 5.2 minutes is about 5x the 60 s recovery interval,
which does not meet "substantially longer", and no condition was recorded
at the time. **Consequence**: the ROBUST verdict rests on a within-session
re-measurement. A true separate-session replication remains outstanding
and is the first thing to run if this campaign is picked up again.

**3. The stabilization criterion was never actually evaluated.** As
specified, it compares the median of the current 5-run window against the
*previous* 5-run window and requires < 10% change — which needs at least
10 warm-up runs. Every configuration in `data/raw/` has exactly 5 warm-up
rows, so no second window exists and no comparison was possible. What was
realized is a **fixed 5-run warm-up batch**, not the specified convergence
test. **Consequence**: steady state was assumed at 5 runs rather than
demonstrated. The one configuration where this visibly mattered is
`threads_4_nocache` (below).

**4. `threads_4_nocache` was recharged between its warm-up and valid
batches.** Its 5 warm-up runs ran 22:41:57–22:44:57 at 58→55% battery;
its 30 valid runs began 23:07:09 at **70%** — a ~22 min gap during which
the device was charged, contradicting the session-level "on battery, USB
disconnected" precondition and separating the valid sample from its own
stabilization window. The effect is visible in the data: the first two
valid runs are 33.3 s and 32.6 s, latency then climbs to ~42 s by run 10
and settles near 37–38 s. The configuration was warming up *during* its
valid sample. **Consequence**: `threads_4_nocache`'s 38.177 s median is
inflated relative to a properly stabilized batch. Since Lever 2's
conclusion is that cache-disabled is 53.5% *slower*, this deviation works
against the reported effect rather than manufacturing it — the direction
of the conclusion is safe, the magnitude is not precise.

One further minor gap: the recovery interval between `threads_2`'s last
valid run (ends 21:29:39) and `threads_4`'s first warm-up run (21:30:17)
is 38 s, below the specified 60 s minimum. Every other
configuration-to-configuration gap meets or exceeds it.

## What this does not establish

- **Nothing about other devices.** One physical Pixel 7 (`panther`),
  Tensor G2 (`gs201`), Android 16, SDK 36. A different SoC, Android
  version, or thermal envelope may invert these results.
- **No inferential statistics.** Medians, means, SD, speedup, latency
  reduction and an SD-based signal check only. No confidence intervals, no
  significance tests, no error bars. The 1 SD bar is a disclosed
  convention, not a statistical test.
- **No mechanism for the thread-count result.** Core placement is not
  observed. The A55-on-the-critical-path reading is a hypothesis.
- **No interaction between the two levers.** The design is sequential.
  The 4-run interaction spot-check specified in OPTIMIZATION_PARAMETERS.md
  was never executed and no such data exists in `data/raw/`, so the
  no-interaction assumption is untested.
- **Only `threads_4` was re-measured at all**, and only within-session
  (deviation 2). The other four configurations have one batch each.

## Next steps, in priority order

1. **A genuine separate-session replication of `threads_4`** — different
   day, device rebooted, condition recorded. This closes deviation 2 and
   is the cheapest way to raise confidence in the headline result.
2. **Re-run the campaign in a randomized or counterbalanced order** to
   break the thread-count/session-position confound (deviation 1).
3. **Implement the stabilization criterion as specified** (≥ 10 warm-up
   runs, two comparable windows), or amend the protocol to specify the
   fixed 5-run warm-up that was actually used (deviation 3).
4. **Re-measure `threads_4_nocache`** with an uninterrupted warm-up →
   valid sequence on battery (deviation 4), to get a clean magnitude for
   the cache effect.
5. **CPU affinity**, if the "runtime-exposed parameters only" constraint
   is ever relaxed — the only lever that would resolve the heterogeneity
   caveat rather than disclose it. See
   ../01_research/OPTIMIZATION_PRE_SCREENING.md.
