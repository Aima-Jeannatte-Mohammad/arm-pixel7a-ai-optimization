# Runtime Selection

## Candidates considered

1. **MediaPipe LLM Inference API** — rejected. Google's official
   documentation states this API is now in maintenance-only mode, with
   new features and optimizations focused on LiteRT-LM.
   Source: https://developers.google.com/edge/mediapipe/solutions/genai/llm_inference

2. **LiteRT-LM** — selected. Active development, official successor to
   MediaPipe LLM Inference API for on-device LLM inference.

## Selected runtime: LiteRT-LM

## Two distinct LiteRT-LM entry points identified

During verification, two separate executables were found to expose
different flag sets. This distinction matters and must not be
collapsed:

### A. `pip`-installed CLI (`litert-lm`, v0.16.0)

Installed via `pip install litert-lm` in a Python virtual environment.
Used for initial reconnaissance of available configuration surfaces.

- Runs inference **locally on the host machine only** — no flag exists
  to target a connected Android device (no `--device`, `--adb`, or
  equivalent).
- Exposes `--cpu-thread-count`, `--backend [cpu|gpu|npu]`.
- **Not used for actual on-device measurement** — informational only.

### B. Natively-built `litert_lm_advanced_main` (used for actual measurement)

Built from source via Bazel, targeting `android_arm64`, and deployed
directly to the Pixel 7 via `adb push`. **This is the binary used for
all Phase B measurements** — superseding an earlier attempt with the
simpler `litert_lm_main` demo binary, which does not implement
generation-length control (see ISSUE_LOG.md #8). `litert_lm_advanced_main`
implements `--benchmark`, `--benchmark_prefill_tokens`, and
`--benchmark_decode_tokens`, required to enforce the project's fixed
workload output-length constraint (§5).

Build command: `bazel build --config=android_arm64 //runtime/engine:litert_lm_advanced_main`
- Build environment: WSL2 (Ubuntu 26.04 LTS), Bazel 7.6.1 (via
  Bazelisk), Android NDK r28b.
- Build result verified: ELF 64-bit LSB pie executable, ARM aarch64,
  for Android 31, built by NDK r28b, 39,499,960 bytes.
- **Exposes a different flag set than the `pip` CLI** — see below.
  This binary corresponds to the simpler `litert_lm_main.cc` demo
  entry point, not the full-featured CLI.

## Configuration surfaces confirmed for the native binary (verified via `--helpfull` on-device)

- **CPU thread count**: `--num_cpu_threads` (NOT `--cpu-thread-count`
  as in the `pip` CLI). "If greater than 0, the number of CPU threads
  to use for the LLM execution with CPU backend." **Default: 0**
  (auto/runtime-decided), not a fixed default of 4 as documented for
  `CpuConfig` elsewhere. This distinction must be stated explicitly in
  OPTIMIZATION_PARAMETERS.md per §30 (documented default vs.
  automatic selection vs. explicitly configured value).
- **Backend selection**: `--backend [cpu|gpu|...]`, default `"gpu"`
  in this binary (not `cpu` — must be explicitly overridden for all
  V1 experiments).
- **XNNPACK**: confirmed again — no independent `--enable_xnnpack`
  toggle exists in this binary either. Consistent with the `pip` CLI
  finding: XNNPACK is not an independently switchable path, it is the
  CPU backend's implementation itself.
- **Model path**: `--model_path` (local file path to `.litertlm`) or
  `--input_prompt` / `--input_prompt_file` for the prompt.

Note: `--num_cpu_threads`, `--backend`, and `--enable_ynnpack` are
declared in `shared_flags.cc`, shared by both `litert_lm_main` and
`litert_lm_advanced_main` — findings about these flags remain valid
after the binary switch. Only the length-control mechanism
(`--max_output_tokens` / `--benchmark_*`) differs between the two.


## New finding: `--enable_ynnpack` flag (undocumented)

A flag named `--enable_ynnpack` (default: `false`) was found in the
native binary's `--helpfull` output and confirmed in source
(`runtime/engine/shared_flags.cc`,
`runtime/executor/llm_executor_settings.h`): "Delegate supported CPU
operations to YNNPACK before XNNPACK." Spelling confirmed consistent
(not a typo) across 13 locations in the source tree.

No public documentation for "YNNPack" was identified. This is treated
as a candidate optimization lever, evaluated and REJECTED for V1 on
documentation-accessibility grounds — see
OPTIMIZATION_PRE_SCREENING.md for the full rationale.

## Deployment constraint: dynamic library dependency

The native binary depends on `libGemmaModelConstraintProvider.so`, not
produced by the `bazel build` of the `litert_lm_main` target itself,
but distributed as a prebuilt shared library in the cloned repository
at `prebuilt/android_arm64/libGemmaModelConstraintProvider.so`
(verified: real ELF shared object, ARM aarch64, for Android 23, built
by NDK r29, 19,589,096 bytes — not a Git LFS pointer). Must be pushed
to the device alongside the main binary.

## Deployment constraint: `LD_LIBRARY_PATH` required at runtime

Android's dynamic linker does not automatically search the executable's
own directory for shared libraries on `/data/local/tmp/`. Every
invocation of the native binary on-device must set
`LD_LIBRARY_PATH=/data/local/tmp` explicitly: