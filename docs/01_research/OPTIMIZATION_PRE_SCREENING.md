# Optimization Pre-Screening

> **Scope**: which optimization levers exist on this runtime and this
> device, which were retained, and why each rejection was a rejection.
> The frozen values and thresholds for the retained levers live in
> ../02_protocols/OPTIMIZATION_PARAMETERS.md.

Screening criteria: the lever must be exposed by the runtime itself
(no scheduler or affinity modification), reachable without root,
measurable on this workload, backed by a reliable source, and carry low
semantic risk to output quality.

## Retained levers

| Lever | Flag | Why retained |
|---|---|---|
| **Lever 1** — CPU thread count | `--num_cpu_threads` | Directly exposed, measurable, no semantic risk. The project's primary question |
| **Lever 2** — Weight cache mode | `--cache_dir` / `--disable_weight_cache` | Discovered from an uncontrolled 11x Init Executor variance (see below); large, reproducible effect confirmed by pilot runs and by source inspection |

Note on flag names: `--num_cpu_threads` is the flag on the natively
built binary used for measurement. The `pip`-installed CLI exposes
`--cpu-thread-count` instead — a different tool, not an alias. See
RUNTIME_SELECTION.md.

## Lever 2 — how it was found and verified

While planning the thread-count sweep, two otherwise-identical runs of
the unset-flag "default" configuration reported **10,769 ms and 941 ms**
Init Executor: an 11x swing on a configuration that was supposed to be
one configuration (ISSUE_LOG.md #14). That is not noise, it is
uncontrolled state.

`--helpfull` on the measurement binary confirmed two relevant flags:
`--cache_dir` ("Directory for cache. Use `:memory` for in-memory cache.
CPU path only") and `--disable_weight_cache` ("Disable only the weight
cache. Applies to both CPU and GPU.").

**Mechanism, source-verified.**
`runtime/executor/litert_compiled_model_executor_utils.cc:917` passes
the cache path straight to XNNPACK via
`cpu_options.SetXNNPackWeightCachePath()`. This is an XNNPACK-level
compiled-kernel cache, not merely a model-loading optimization at the
LiteRT-LM level — which is why disabling it degrades both Init Executor
(initial compilation) and Decode Speed (forward passes re-touching
uncached kernels), rather than startup alone.
`executor_settings_base.cc:312` further confirms that
`disable_weight_cache` and an unset/`:nocache` `cache_dir` are handled by
the same branch, consistent with their similar observed Init Executor
values (~10,800-11,000 ms in both cases).

**Pilot evidence** (2 runs per setting):

| Setting | Init Executor | Decode Speed |
|---|---|---|
| `--cache_dir=:memory` (run 1) | 4,981 ms | 13.71 tok/s |
| `--cache_dir=:memory` (run 2) | 5,003 ms | 14.87 tok/s |
| `--disable_weight_cache=true` (run 1) | 10,845 ms | 8.93 tok/s |
| `--disable_weight_cache=true` (run 2) | 10,987 ms | 9.73 tok/s |

Both settings were internally stable and reproducible across their pilot
runs — unlike the unset-flag "default", which was not. The gap is large
and consistent: roughly 54% faster Init Executor and ~40% faster decode
with the cache active. This justified retaining it as Lever 2 and, just
as importantly, pinning both cache flags explicitly on **every** Phase B
run so cache state cannot drift during the thread-count comparison.

## Rejected levers

Grouped by rejection ground. Each was screened before any campaign time
was spent on it, or dropped after a bounded pilot.

### Hardware not present

**i8mm / KleidiAI (Arm I8MM matrix-multiply extension).** The Tensor
G2's cores (Cortex-X1, Cortex-A78, Cortex-A55) implement Armv8.2-A with
extensions up to Armv8.4-A dot product. I8MM requires Armv8.6-A, which
none of them support — confirmed against `/proc/cpuinfo`, which reports
`asimddp` but no `i8mm` and no SVE (see
../02_protocols/DEVICE_CHARACTERIZATION.md). Enabling this path would
compile code that silently falls back to generic kernels at runtime.
The optimization does not exist on this hardware. Relevant again on
Armv8.6-A+ / Armv9 silicon.

### Flag does not exist on this binary

**Local-attention ringbuffers.** Considered on the basis of
documentation describing a memory-versus-latency tradeoff for
local-attention KV cache handling. `--helpfull` on
`litert_lm_advanced_main` returns no flag matching "ring" or
"attention". Likely specific to the `pip` CLI or another backend
configuration. No further investigation: a lever that fails a basic
accessibility check does not get experimental time.

### Not measurable on this workload

**`prefill_chunk_size`.** This CPU config parameter only produces an
observable effect when the prompt exceeds the runtime's default chunk
size; otherwise prefill is processed in a single chunk regardless of the
configured limit. At this project's workload length (~450 tokens of
prompt plus document, measured),
producing a measurable effect would have meant inflating the workload
well beyond what Phase A validated — cascading into re-validation and a
re-derived time budget, purely to manufacture a measurable effect for a
secondary lever.

### Not documented well enough to adopt

**YNNPACK (`--enable_ynnpack`).** Found via `--helpfull` and confirmed
in source (`runtime/engine/shared_flags.cc`,
`runtime/executor/llm_executor_settings.h`) as a CPU delegate that
operates "before XNNPACK"; the spelling is consistent across 13
locations in the source tree, so it is not a typo for XNNPACK. No public
documentation was identified, and it is disabled by default upstream
(`enable_ynnpack = false`), suggesting its own maintainers do not treat
it as a stable general-purpose path. Adopting an undocumented,
off-by-default delegate would violate this project's
reliable-source requirement. Worth re-examining if it becomes
documented.

### Pilot-tested, no demonstrated gain

**Speculative decoding (`--enable_speculative_decoding`).** Verified
functional: a log line not seen in any prior test appeared (`MTP Drafter
- Success rate: 0.438095`), with an identical rate across both pilot
runs. But decode speed was 14.47 and 14.51 tok/s with it enabled versus
13.71-14.88 tok/s already observed without it — fully overlapping
ranges, not a distinguishable effect. Functional and deterministic, but
no gain to justify a third campaign dimension.

**Constant tensor sharing (`--share_constant_tensors`).** Enabled by
default, with no GPU-only caveat in its description — unlike
`--gpu_external_tensor_mode`, which was excluded for being explicitly
GPU-backend-only and therefore inapplicable to this CPU-only path.
Pilot-tested with `--cache_dir=:memory` fixed: `true` gave 5,296 ms Init
Executor and 15.72 tok/s; `false` gave 4,816 ms and 15.01 tok/s. That
~9% / ~5% gap sits inside the run-to-run noise already documented on an
unchanged configuration (4,981 ms vs. 5,003 ms on two `:memory` runs).
Not a distinguishable effect.

### Out of scope by design

**CPU affinity (pinning threads to a cluster).** The only lever that
would have directly resolved the CPU heterogeneity confound below. It
requires controlling Android's scheduler, which falls outside this
project's "runtime-exposed parameters only" constraint. Documented as
the highest-value future direction, not as an oversight.

## Not a lever: the CPU backend / XNNPACK

An earlier plan treated "XNNPACK on vs. off" as a second lever. That is
not possible on this runtime: **no independent XNNPACK toggle exists**
in either entry point, verified via `--helpfull` on the measurement
binary and in the runtime's source. `--backend=cpu` *is* the XNNPACK
path. There is therefore no non-XNNPACK CPU baseline to compare
against, and no separate XNNPACK or "combined" configuration is run.
The weight-cache lever above replaced it.

## Consequence for the thread-count experiment

Because CPU affinity is out of scope, thread-count results on the Tensor
G2's heterogeneous 2+2+4 CPU reflect a mixture of the configured
parameter and unobserved Android scheduler core-placement decisions.
This is not resolved, it is controlled for and disclosed:

1. The caveat is stated first in every section presenting thread-count
   results, in the docs and on the dashboard.
2. The best configuration is independently replicated in a separate
   session before being reported as final.

See ../02_protocols/OPTIMIZATION_PARAMETERS.md (decision rule) and
../02_protocols/MEASUREMENT_PROCEDURE.md (replication procedure).
