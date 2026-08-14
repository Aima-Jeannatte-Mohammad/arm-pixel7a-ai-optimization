# Runtime Selection

> **Scope**: which inference runtime is used, which executable is used
> for measurement, and the exact build and deployment record for it.

## Runtime: LiteRT-LM

| Candidate | Outcome |
|---|---|
| **MediaPipe LLM Inference API** | Rejected. Google's own documentation states the API is in maintenance-only mode, with new features and optimizations directed to LiteRT-LM. Source: https://developers.google.com/edge/mediapipe/solutions/genai/llm_inference |
| **LiteRT-LM** | **Selected.** Actively developed, official successor for on-device LLM inference |

## Two entry points, two different flag sets

This distinction must not be collapsed — the two executables expose
different flags, and several published flag names apply to only one of
them.

### A. `pip`-installed CLI (`litert-lm`, v0.16.0) — reconnaissance only

- Runs inference **on the host machine only**. No flag exists to target
  a connected Android device (no `--device`, `--adb`, or equivalent) —
  ISSUE_LOG.md #1.
- Exposes `--cpu-thread-count`, `--backend [cpu|gpu|npu]`, and sampling
  flags (`--temperature`, `--top_k`, ...).
- **Not used for any measurement.** Informational only.

### B. Natively built `litert_lm_advanced_main` — all measurements

This is the binary used for every Phase A and Phase B measurement.

```bash
bazel build --config=android_arm64 //runtime/engine:litert_lm_advanced_main
```

- Build environment: WSL2 (Ubuntu 26.04 LTS), Bazel 7.6.1 via Bazelisk,
  Android NDK r28b.
- Build output verified: ELF 64-bit LSB PIE executable, ARM aarch64, for
  Android 31, built by NDK r28b (~39 MB).
- Deployed by `adb push` to `/data/local/tmp/`.

**Why this entry point and not `litert_lm_main`.** An earlier attempt
used the simpler `litert_lm_main` demo binary. It does not implement
generation-length control: `--max_output_tokens` had no effect across 5
consecutive runs, source-confirmed as never being read by that entry
point (ISSUE_LOG.md #3). `litert_lm_advanced_main` implements
`--benchmark` and the `benchmark_prefill_tokens` /
`benchmark_decode_tokens` settings, which is what makes the project's
fixed output-length constraint enforceable.

Only the length-control mechanism differs between the two entry points.
`--num_cpu_threads`, `--backend` and `--enable_ynnpack` are declared in
`runtime/engine/shared_flags.cc`, shared by both — so findings about
those flags survived the binary switch.

## Configuration surface of the measurement binary

Verified via `--helpfull` on-device, not from published documentation.

| Flag | Finding |
|---|---|
| `--num_cpu_threads` | "If greater than 0, the number of CPU threads to use for the LLM execution with CPU backend." **Default: 0** (auto / runtime-decided) — *not* a fixed default of 4 as documented for `CpuConfig` elsewhere. Recorded as an automatic default, never treated as an explicitly configured value |
| `--backend` | `[cpu|gpu|...]`, **default `gpu`** in this binary. Must be explicitly overridden to `cpu` on every run |
| XNNPACK | **No independent toggle exists** — consistent with the `pip` CLI. XNNPACK is not a switchable path, it is the CPU backend's implementation. See OPTIMIZATION_PRE_SCREENING.md, "Not a lever" |
| `--cache_dir`, `--disable_weight_cache` | Weight cache control. Retained as Lever 2 — see OPTIMIZATION_PRE_SCREENING.md |
| `--max_output_tokens`, `--benchmark` | The working length-control combination (ISSUE_LOG.md #4) |
| `--model_path`, `--input_prompt` / `--input_prompt_file` | Model and prompt input |
| Sampling flags | **Absent** on this binary (no `--seed`, `--temperature`, `--top_k`, `--top_p`), unlike the `pip` CLI. The default sampling strategy is an open uncertainty — ISSUE_LOG.md #5 |
| `--enable_ynnpack` | Undocumented CPU delegate ("Delegate supported CPU operations to YNNPACK before XNNPACK"), default `false`, confirmed in source across 13 locations. Evaluated and rejected for V1 — see OPTIMIZATION_PRE_SCREENING.md |

## Deployment constraints

**1. Prebuilt shared library.** The binary depends on
`libGemmaModelConstraintProvider.so`, which its own Bazel target does not
produce. It is distributed as a prebuilt in the cloned repository at
`prebuilt/android_arm64/libGemmaModelConstraintProvider.so` (verified: real
ELF shared object, ARM aarch64, for Android 23, built by NDK r29 — not a
Git LFS pointer). It must be pushed to the device alongside the binary
(ISSUE_LOG.md #2).

**2. `LD_LIBRARY_PATH` on every invocation.** Android's dynamic linker
does not search an executable's own directory for shared libraries under
`/data/local/tmp/`, so every call must set it explicitly or fail with
`CANNOT LINK EXECUTABLE`:

```bash
adb shell "cd /data/local/tmp && LD_LIBRARY_PATH=/data/local/tmp ./litert_lm_advanced_main --backend=cpu ..."
```

The full frozen invocation used for measurement is in
../02_protocols/OPTIMIZATION_PARAMETERS.md.
