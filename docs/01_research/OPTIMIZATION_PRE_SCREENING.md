# Optimization Pre-Screening

## Retained for V1

1. **Inference-runtime CPU thread-count tuning** (`--num_cpu_threads`
   on the natively-built binary used for measurement — see
   RUNTIME_SELECTION.md for the distinction from `--cpu-thread-count`
   on the `pip`-installed CLI) — measurable, accessible, low semantic
   risk, directly exposed by the runtime.
2. **CPU backend execution path** (effectively XNNPACK, see
   RUNTIME_SELECTION.md) — same criteria.

## Alternatives considered and rejected

### 1. i8mm / KleidiAI (Arm I8MM matrix-multiply extension)

Rejected on hardware-availability grounds. The Pixel 7's Tensor G2 CPU
cores (Cortex-X1, Cortex-A78, Cortex-A55) implement Armv8.2-A with
extensions up to Armv8.4-A dot product. The I8MM extension requires
Armv8.6-A, which none of these cores support. Enabling this path would
compile code that silently falls back to generic kernels at runtime on
this specific device — the optimization does not exist on this
hardware.

Sources: Arm/Wikichip architecture references for Cortex-X1, Cortex-A78,
Cortex-A55.

### 2. prefill_chunk_size tuning

Rejected on measurability grounds. This LiteRT-LM CPU config parameter
only produces an observable effect when the prompt exceeds the
runtime's default chunk size — otherwise prefill is processed in a
single chunk regardless of the configured limit. At the project's
planned workload length (~500-1000 tokens), this could not be assumed
without inflating the workload well beyond what Phase A model
validation would cover, cascading into re-validation and a re-derived
time budget — solely to manufacture a measurable effect for a secondary
lever.

### 3. YNNPACK (`--enable_ynnpack`, discovered via `litert_lm_main --helpfull`)

Rejected on documentation-accessibility grounds. Found in the
LiteRT-LM source code (runtime/engine/shared_flags.cc,
runtime/executor/llm_executor_settings.h) as a CPU delegate described
as operating "before XNNPACK," but with no public documentation
identified as of this writing (verified via web search). Disabled by
default (`enable_ynnpack = false`) in the codebase itself, suggesting
it is not yet considered a stable, general-purpose path by its
maintainers. Adopting an undocumented, off-by-default delegate would
violate the project's requirement for reliable-source-backed
pre-screening (§14 criterion 2) and its quality-preservation principle
(§16). Not adopted for V1; worth re-examining in V2 once (or if) it
becomes publicly documented.

Weight cache mode (--cache_dir / --disable_weight_cache) — RETAINED as Lever 2

Discovered while investigating an 11x Init Executor variance on the unset-flag "default" configuration during thread-count planning (10,769ms vs 941ms across two otherwise-identical runs of the same nominal configuration). Confirmed via --helpfull on the native binary: --cache_dir ("Directory for cache. Use ':memory' for in-memory cache. CPU path only") and --disable_weight_cache ("Disable only the weight cache. Applies to both CPU and GPU.").

Pilot-tested (2 runs per setting, both with --cache_dir=:memory fixed as applicable):

Setting	Init Executor	Decode Speed
--cache_dir=:memory (run 1)	4,981 ms	13.71 tok/s
--cache_dir=:memory (run 2)	5,003 ms	14.87 tok/s
--disable_weight_cache=true (run 1)	10,845 ms	8.93 tok/s
--disable_weight_cache=true (run 2)	10,987 ms	9.73 tok/s

Both settings were internally stable and reproducible across their 2 pilot runs — unlike the unset-flag "default," which was not (see above). The gap is large and consistent: roughly 54% faster Init Executor and ~40% faster decode with the weight cache active via :memory. The underlying mechanism has not yet been confirmed against the runtime's source code (shared_flags.cc / llm_litert_lib.cc) — this is an empirical finding, not yet a source-verified one, and is flagged as a follow-up before RESULTS.md is finalized.

Retained as Lever 2, tested sequentially at Lever 1's winning thread-count only, with a documented tradeoff (no full factorial grid) — see OPTIMIZATION_PARAMETERS.md, "Two-lever design," for the mitigation (a 4-run interaction spot-check at both the winning and losing Lever-1 configurations).

Speculative decoding (--enable_speculative_decoding)

Explored as a candidate third lever alongside thread-count and weight caching. The CLI flag name differs from the pip-installed tool's --speculative-decoding; on litert_lm_advanced_main it is --enable_speculative_decoding, confirmed via --help=.

Verified functional: a new log line not seen in any prior test appeared ("MTP Drafter - Success rate: 0.438095"), with an identical success rate across both pilot runs — consistent with the deterministic behavior observed everywhere else in this project. However, decode speed showed no measurable improvement over the same configuration without it: 14.47 and 14.51 tok/s with speculative decoding enabled, versus 13.71-14.88 tok/s already observed without it — fully overlapping ranges, not a distinguishable effect.

Not adopted. Functional and deterministic, but no demonstrated gain to justify a third campaign dimension, unlike the weight-cache lever's confirmed ~54%/~40% improvement.

Local-attention ringbuffers

Considered as a candidate third lever based on documentation referencing a memory-versus-latency tradeoff for local-attention KV cache handling. Verified via --helpfull on the actual measurement binary (litert_lm_advanced_main): no flag matching "ring" or "attention" exists anywhere in the full flag list.

Not adopted — the lever does not exist on this binary. Likely specific to the pip-installed CLI or a different backend configuration; not available on the native binary used for measurement. No further investigation performed, consistent with §15 of the master prompt (do not spend experimental time chasing a lever that fails a basic accessibility check).

Constant tensor sharing (--share_constant_tensors)

Considered as a candidate third lever: enabled by default (true), controls whether the executor shares constant tensors, with no GPU-specific caveat in its description (unlike a neighboring flag, --gpu_external_tensor_mode, which was excluded for being explicitly GPU-backend-only and therefore inapplicable to this project's CPU-only measurement path).

Pilot-tested (2 runs per setting, both with --cache_dir=:memory fixed): true gave 5,296 ms Init Executor and 15.72 tok/s decode; false gave 4,816 ms and 15.01 tok/s. The observed gap (~9% on Init Executor, ~5% on decode) falls within the range of ordinary run-to-run noise already documented elsewhere in this project (e.g. 4,981ms vs 5,003ms on two runs of an otherwise-identical :memory configuration) — not a distinguishable effect.

Not adopted. No demonstrated gain, unlike the weight-cache lever.

### 4. CPU affinity (pinning threads to the performance cluster)

The only lever that would have directly resolved the CPU heterogeneity
confound in the thread-count experiment (see EXPERIMENTAL_METHOD.md).
Not adopted for V1 — out of scope per the "runtime-exposed parameters
only, no scheduler/affinity modification" principle. Documented as a
V2 direction.

## Consequence for the thread-count experiment

Because CPU affinity is out of scope, thread-count results on the
Tensor G2's heterogeneous 2+2+4 CPU reflect a mixture of the configured
parameter and unobserved Android scheduler core-placement decisions.
This is addressed by: (1) stating this caveat first in every
thread-count result section, and (2) an independent replication of the
best configuration in a separate session before it is reported as
final. See ../02_protocols/MEASUREMENT_PROCEDURE.md and
../03_experiments_results/RESULTS.md.


### Constant tensor sharing (`--share_constant_tensors`)

Explored as a candidate third lever. Tested true vs. false (both with
--cache_dir=:memory fixed): Init Executor 5296ms vs 4816ms, Decode
Speed 15.72 vs 15.01 tok/s. The observed gap is within the range of
run-to-run noise already seen on an otherwise-identical configuration
(e.g. 4981ms vs 5003ms on two runs of :memory alone), not a
distinguishable effect. Not adopted: no demonstrated gain, unlike the
weight-cache lever's confirmed 53.7% Init Executor improvement.