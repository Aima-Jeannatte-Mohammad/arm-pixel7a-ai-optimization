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

Rejected on hardware-availability grounds. The Pixel 7a's Tensor G2 CPU
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