# Tech-Explique-Moi

Execution-level optimization of a fixed local LLM inference workload on
Arm mobile silicon: **Gemma 4 E2B via LiteRT-LM on a Google Pixel 7
(Google Tensor G2)**, measured on-device, with a frozen protocol and
per-run raw data.

Two runtime-exposed levers are tested sequentially:

1. **CPU thread count** (`--num_cpu_threads`) across the Tensor G2's
   heterogeneous 2+2+4 topology (4x Cortex-A55, 2x Cortex-A78, 2x Cortex-X1).
2. **Weight-cache mode** (`--cache_dir` / `--disable_weight_cache`),
   tested at Lever 1's winning thread count.

The workload itself (English technical documentation -> compact French
arrow-schema, technical terminology preserved in English) is a **fixed
instrument**, not the research subject. It is held byte-identical across
every measurement so the tested parameter is the only variable.

---

## Results (this device only)

Latency is end-to-end wall-clock per run, 30 valid runs per configuration
(plus 5 retained warm-up runs each), readiness-gated, single frozen input.

| Config | threads | n | median (s) | SD (s) | speedup | decode (tok/s) | CPU (%) | peak RSS (MB) |
|---|---|---|---|---|---|---|---|---|
| baseline (auto) | auto | 30 | 29.561 | 3.981 | 1.000x | 11.61 | 283.7 | 2214.0 |
| threads_1 | 1 | 30 | 37.007 | 6.761 | 0.799x | 7.40 | 96.7 | 2162.7 |
| threads_2 | 2 | 30 | 28.252 | 4.252 | 1.046x | 11.03 | 166.1 | 2236.3 |
| **threads_4** | **4** | **30** | **24.874** | **2.123** | **1.188x** | **12.98** | **284.5** | **2230.9** |
| threads_8 | 8 | 30 | 30.038 | 1.867 | 0.984x | 10.02 | 499.8 | 2130.1 |
| threads_4_nocache (Lever 2) | 4 | 30 | 38.177 | 2.289 | 0.652x | 9.19 | 214.5 | 4017.4 |

**Lever 1 winner: `threads_4`** — 1.188x vs. the runtime's own auto
default (15.9% latency reduction), a 1.18 baseline-SD gap. Re-measured in
a second batch (10 valid runs): 20.682s median, 1.429x. Ranking and
direction held, so it is reported **ROBUST** per the replication rule in
[OPTIMIZATION_PARAMETERS.md](docs/02_protocols/OPTIMIZATION_PARAMETERS.md)
— but that batch ran ~5 minutes after the previous configuration in the
same session, not in the genuinely separate session the protocol asks for,
so it is weaker evidence than intended. See
[OPTIMIZATION_RESULTS.md](docs/03_experiments_results/OPTIMIZATION_RESULTS.md),
"Realized vs. specified".

**Lever 2 outcome:** disabling the weight cache does *not* improve on the
Lever 1 winner — it costs 53.5% latency and nearly doubles peak RSS. The
best combination found is 4 threads with the weight cache in memory.

Two observations an Arm engineer will care about:

- **CPU utilization is monotonic in thread count; latency is not.**
  96.7% -> 166.1% -> 284.5% -> 499.8% confirms `--num_cpu_threads`
  genuinely engages more cores, yet 8 threads is slower than 4 —
  consistent with the A55 littles landing on the critical path.
- **`baseline` and `threads_4` draw nearly identical total CPU**
  (283.7% vs. 284.5%) but differ in median latency and in spread
  (SD 3.981s vs. 2.123s). Same CPU budget, different outcome. Core
  placement is *not observed* here (see the caveat below), so this is
  reported as an observation, not an explanation.

Interactive dashboard: [webapp/dashboard/index.html](webapp/dashboard/index.html)
(generated from raw CSVs, not hand-transcribed).

### Mandatory caveat

CPU affinity is out of scope (no scheduler/affinity modification —
runtime-exposed parameters only). On a heterogeneous 2+2+4 CPU,
thread-count results therefore reflect **the configured parameter mixed
with unobserved Android scheduler core-placement decisions**. No claim is
made about which cores (A55/A78/X1) executed any configuration's threads.
This caveat precedes every thread-count result in the docs and on the
dashboard, and is the reason the winning configuration was replicated in
a separate session before being reported as final.

### What this repo does not claim

- **Not generalized to Arm devices broadly.** Every number is scoped to
  one physical Pixel 7 (`panther`), Tensor G2 (`gs201`), Android 16,
  SDK 36. A different SoC, Android version, or thermal envelope may
  invert these results.
- **No inferential statistics.** Medians, means, SD, speedup, and
  latency reduction only — no confidence intervals or significance tests.
- **Phase A model validation is a feasibility gate**, n=15 documents /
  36 observations, not a population-level quality claim.
- **The Lever 1 / Lever 2 design is sequential, not factorial.** The
  4-run interaction spot-check described in
  [OPTIMIZATION_PARAMETERS.md](docs/02_protocols/OPTIMIZATION_PARAMETERS.md)
  is not present in `data/raw/`, so the no-interaction assumption is
  currently untested.
- **Only `threads_4` was re-measured at all**, and only within the same
  session. The other configurations have one batch each.
- **Three further protocol deviations** — ascending configuration order, a
  never-evaluated stabilization criterion, and a mid-batch recharge during
  the Lever 2 configuration — are documented in
  [OPTIMIZATION_RESULTS.md](docs/03_experiments_results/OPTIMIZATION_RESULTS.md).
  Read that section before quoting any figure here.

---

## Repository layout

```
docs/
  01_research/
    RUNTIME_SELECTION.md          Runtime choice, both entry points, build/deploy record
    OPTIMIZATION_PRE_SCREENING.md Every lever considered, retained or rejected, with reasons
  02_protocols/
    DEVICE_CHARACTERIZATION.md    Reference device: SoC, topology, memory, thermal/battery access
    MODEL_SELECTION_PROTOCOL.md   Phase A design, frozen system prompt (exact text), model SHA256
    OPTIMIZATION_PARAMETERS.md    WHAT is measured and WHY: frozen flags, thresholds, decision rules
    MEASUREMENT_PROCEDURE.md      HOW to measure, step by step, incl. session-level device isolation
  03_experiments_results/
    MODEL_SELECTION_RESULTS.md    Phase A outcome, defect patterns, retention decision
    OPTIMIZATION_RESULTS.md       Phase B outcome + audit of where the realized campaign
                                  departed from the protocol (read this before trusting a number)
  ISSUE_LOG.md                    Every issue hit and how it was resolved (read this one)

data/
  documents/doc_01..15.txt        Phase A corpus (doc_07 is the frozen Phase B workload)
  model_selection/*.xlsx          Phase A raw per-criterion scores
  raw/*.csv                       Phase B per-run raw data (one row per run, warm-up rows kept)

scripts/run_config.py             Measurement harness (readiness gate, launch, /proc polling, CSV)
analysis/compute_stats.py         Raw CSVs -> statistics -> webapp/dashboard/index.html
analysis/generate_model_selection_page.py  Phase A results -> static page

webapp/dashboard/index.html       Phase B results dashboard (generated)
webapp/try_it/index.html          Shows the frozen prompt for your own input + a real measured
                                  example. Does NOT run inference (a browser cannot drive adb).

build-artifacts/                  gitignored: built binary, prebuilt .so, model (~2.6 GB)
```

**Not in the repo**: `phase_b_prompt.txt`, THE frozen Phase B input
(2163 bytes, SHA256
`7edcb8370dfb3b31b90e148b579dabcc488da9eb61b53838a1c2703212e4e606`). It is
the frozen system prompt concatenated with `data/documents/doc_07.txt`, and
the hash — not a copy in Git — is what makes it verifiable. Re-concatenating
the two sources is not guaranteed to reproduce that exact hash (line endings
and trailing whitespace matter at byte level), so the original is preserved
on the measurement host rather than rebuilt. Reproducing on a new device
means building your own canonical file **once**, recording its hash, and
never touching it again; the requirement is a frozen hash-locked input, not
this particular hash. All 220 rows in `data/raw/` report prefill = 447
tokens, which is the evidence the input held constant here.

`data/raw/` file naming: `<config>.csv` for the campaign,
`threads_4_replication.csv` for the winner's re-measurement,
`threads_4_nocache.csv` for Lever 2.

---

## Reproducing on the same device class

### 0. Requirements

| Component | Version used here | Notes |
|---|---|---|
| Device | Google Pixel 7 (`panther`), Tensor G2 (`gs201`), Android 16 / SDK 36 | Verify with `adb shell getprop ro.product.model ro.board.platform` — do not assume |
| Host | Windows 11 + WSL2 (Ubuntu 26.04) | Any Linux host works for the Bazel build |
| Bazel | 7.6.1 (via Bazelisk) | Newer Bazel may need upstream `.bazelversion` changes |
| Android NDK | r28b | Build targets Android API 31 |
| Python | 3.12 (3.11 in CI) | Standard library only — `requirements.txt` is intentionally empty |
| adb | Platform-tools on `PATH` | Wireless ADB required for the measurement campaign |

No root access is used anywhere. Everything runs from `/data/local/tmp`
via `adb shell`.

### 1. Build the runtime binary

In WSL2 (or any Linux host), clone upstream LiteRT-LM
(`google-ai-edge/LiteRT-LM`) and build the **advanced** entry point:

```bash
export ANDROID_NDK_HOME=/path/to/android-ndk-r28b
bazel build --config=android_arm64 //runtime/engine:litert_lm_advanced_main
```

Use `litert_lm_advanced_main`, **not** `litert_lm_main`. The simpler demo
binary never reads the output-length settings — it silently ignored
`--max_output_tokens` for 5 consecutive runs here (always exactly 920
tokens) until source inspection explained why. See
[ISSUE_LOG.md](docs/ISSUE_LOG.md) #3.

The binary also needs a **prebuilt** shared library that its own build
target does not produce: `prebuilt/android_arm64/libGemmaModelConstraintProvider.so`
from the same clone. Confirm it is a real ELF object and not a Git LFS
pointer (`file` on it) before pushing.

The `pip install litert-lm` CLI is host-only and exposes a *different*
flag set (`--cpu-thread-count`, not `--num_cpu_threads`). It cannot
target a connected device and is not used for any measurement here.

### 2. Get the model

```
litert-community/gemma-4-E2B-it.litertlm   (2.59 GB)
SHA256 181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c
https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm
```

Verify the hash before pushing. It is gitignored (`*.litertlm`) and never
committed.

### 3. Push everything to the device

```powershell
adb push litert_lm_advanced_main            /data/local/tmp/
adb push libGemmaModelConstraintProvider.so /data/local/tmp/
adb push gemma-4-E2B-it.litertlm           /data/local/tmp/
adb push phase_b_prompt.txt                /data/local/tmp/
adb shell chmod +x /data/local/tmp/litert_lm_advanced_main
adb shell sha256sum /data/local/tmp/phase_b_prompt.txt   # must match the hash above
```

Android's linker does not search an executable's own directory on
`/data/local/tmp`, so **every** invocation must set `LD_LIBRARY_PATH`
explicitly or you get `CANNOT LINK EXECUTABLE`. The prebuilt `.so` is also
not produced by the binary's own Bazel target
([ISSUE_LOG.md](docs/ISSUE_LOG.md) #2).

Smoke test one run by hand before automating anything:

```powershell
adb shell "cd /data/local/tmp && LD_LIBRARY_PATH=/data/local/tmp ./litert_lm_advanced_main --backend=cpu --max_output_tokens=400 --benchmark=true --cache_dir=:memory --disable_weight_cache=false --model_path=/data/local/tmp/gemma-4-E2B-it.litertlm --input_prompt_file=/data/local/tmp/phase_b_prompt.txt"
```

You should get a French arrow-schema plus a `BenchmarkInfo` block
(Init phases, Time to first token, Prefill/Decode Turn, tokens/sec).
A `Failed to get decode profile summary: INVALID_ARGUMENT` warning is
expected and harmless — it fires after decode timing has already
completed and only affects an unused optional profiling field
([ISSUE_LOG.md](docs/ISSUE_LOG.md) #8).

### 4. Prepare the measurement session

These are **session-level preconditions**, confirmed once before a
session, not per run. Two batches were discarded and restarted here for
violating them.

1. **Wireless ADB, USB unplugged.** `adb tcpip 5555` then
   `adb connect <device-ip>:5555`, then disconnect the cable. Charging
   while running CPU-bound inference adds a second, uncontrolled heat
   source.
2. **Battery >= 50%** at the start and throughout. Charge between
   configurations, never during a run.
3. **Airplane Mode on, then Wi-Fi back on.** Kills cellular and
   Bluetooth, keeps wireless ADB alive. Re-check `adb devices` after.
4. **Play Store auto-updates off**, other apps closed.
5. **Do not touch the device during measurement.** The screen may time
   out on its own; that is fine.

The per-run readiness gate (thermal status NONE/LIGHT, battery >= 50%) is
enforced by the harness and blocks until it passes.

### 5. Run one configuration

`scripts/run_config.py` runs N measurements of a single configuration and
appends one row per run to a CSV.

```powershell
# stabilization batch first (retained in the CSV, tagged warmup)
python scripts/run_config.py --config threads_4 --threads 4 --n-runs 5  --run-type warmup --output data/raw/threads_4.csv
# then the valid sample
python scripts/run_config.py --config threads_4 --threads 4 --n-runs 30 --run-type valid  --output data/raw/threads_4.csv
```

| Flag | Meaning |
|---|---|
| `--config` | Name written to the CSV and used as the dashboard label |
| `--threads` | `--num_cpu_threads` value. **Omit entirely for baseline** — passing `0` is not confirmed equivalent to omitting the flag |
| `--cache-dir` | Default `:memory` (Lever 1 fixed value) |
| `--disable-weight-cache` | Lever 2 configuration |
| `--n-runs` | Runs in this invocation |
| `--run-type` | `warmup` or `valid` — warm-up rows are kept in the CSV and excluded from statistics, never deleted |
| `--output` | CSV to append to (header written if new) |

Both cache flags are set explicitly on **every** run, including the
thread-count sweep. This is not redundancy: two nominally identical runs
of the unset-flag "default" returned 10,769ms and 941ms Init Executor —
an 11x swing from uncontrolled on-disk cache state. Never let that vary
during a comparison.

Run the sweep in an **interleaved order**, not a fixed one — a monotonic
sweep makes thermal and battery drift correlate with the parameter you are
testing. Do better than this campaign did: the realized order here was
`baseline -> 1 -> 2 -> 4 -> 8`, i.e. ascending, which is exactly what the
rule exists to prevent. Thread count is therefore confounded with position
in the session in the numbers above.

**Stabilization criterion** before each configuration's valid sample: run
warm-up runs until the rolling 5-run median latency changes by less than
10% from the previous 5-run window. That needs **at least 10** warm-up runs
to evaluate; this campaign ran a fixed 5 per configuration, so it assumed
steady state rather than demonstrating it.

**Replication** (mandatory before calling any configuration final): re-run
the winner for 10 valid runs in a genuinely separate session — different
day, or after a reboot, or after an idle period well beyond the recovery
interval. Record which condition applied. This campaign did not: its
re-measurement ran ~5 minutes into the same session, and no condition was
recorded.

```powershell
python scripts/run_config.py --config threads_4_replication --threads 4 --n-runs 10 --run-type valid --output data/raw/threads_4_replication.csv
```

Verdict rule: **ROBUST** requires (1) the configuration still beats
baseline in the replication and (2) both speedups on the same side of
1.0x. A replication that is *more* favorable still counts — magnitude
drift alone does not invalidate a confirmed ranking and direction.

### 6. Compute statistics and regenerate the dashboard

```powershell
python analysis/compute_stats.py                     # -> webapp/dashboard/index.html
python analysis/generate_model_selection_page.py     # -> webapp/model-selection/index.html
```

`compute_stats.py` reads **every** `data/raw/*.csv`, keeps only rows with
`run_type=valid` **and** `validity=valid`, and computes n, median, mean,
SD, min, max, speedup vs. baseline, latency reduction, mean decode
throughput, mean CPU%, and mean peak RSS.

Two behaviors to know before you add your own CSVs:

- Any config name **outside** `CONFIG_ORDER`
  (`baseline, threads_1, threads_2, threads_4, threads_8`) is
  auto-treated as a **Lever 2 candidate** and compared against the Lever 1
  winner rather than against baseline. Name new configurations
  accordingly, or edit `CONFIG_ORDER` / `THREAD_COUNT_MAP` at the top of
  the script.
- `generate_model_selection_page.py` **transcribes** Phase A results from
  `MODEL_SELECTION_RESULTS.md` into a `DOCUMENTS` array; it does not read
  the scoring workbook. If the results doc changes, update that array.

CI (`.github/workflows/ci.yml`) runs `ruff check scripts/ analysis/` on
every push and PR. There are no unit tests — correctness here rests on
device verification and raw-data retention, not on a test suite.

---

## Measured quantities and their limits

One CSV row per run, schema in `scripts/run_config.py` (`FIELDNAMES`):

| Field | How it is obtained | Limit to keep in mind |
|---|---|---|
| `end_to_end_latency_s` | Host wall-clock around the whole `adb shell` launch-and-wait cycle | Includes process startup and adb round-trip, not just inference. This is the primary reported metric; it is deliberately end-to-end |
| `init_total_ms`, `time_to_first_token_s`, `prefill_tokens`, `prefill_speed_tok_s`, `decode_tokens`, `decode_speed_tok_s` | Parsed from the binary's own `BenchmarkInfo` block | Runtime-reported, not independently instrumented |
| `peak_rss_kb` | Max `VmHWM` from `/proc/<PID>/status`, polled ~1 Hz | 1 Hz over wireless adb can miss a short spike |
| `cpu_pct` | `(utime+stime)` delta from `/proc/<PID>/stat` over wall-clock, `CLK_TCK` read from the device | Percent of **one** core, top-style (up to ~800% on 8 cores). Diagnostic, not a profiler. Says nothing about *which* cores |
| `thermal_status_start/end`, `battery_pct_start` | `dumpsys thermalservice` / `dumpsys battery` | Aggregate Android thermal status integer only, never raw degC or per-sensor HAL values |
| `run_type`, `validity`, `exclusion_reason` | Set by the harness | A run that fails `BenchmarkInfo` parsing is written as `invalid` with a reason, not dropped |

Design details worth knowing if you modify the harness:

- The binary is launched with `exec` so `$!` is the **binary's** PID, not
  an intermediate shell's. Without it, `/proc/<PID>` polling silently
  measures the wrong process — and produces clean, wrong numbers.
- adb-level failures (`more than one device/emulator`, `device offline`,
  ...) raise `AdbError` and abort immediately. They are never treated as
  "device not ready", which previously caused an infinite retry loop that
  hid the real problem.
- Tunable constants live at the top of `scripts/run_config.py`:
  `THERMAL_OK`, `BATTERY_MIN`, `READINESS_POLL_INTERVAL_S`,
  `READINESS_MAX_WAIT_S`, `PROC_POLL_INTERVAL_S`, `INTER_RUN_DELAY_S`,
  plus the `/data/local/tmp` paths and the model filename.

---

## Porting this to a different Arm device

The protocol is device-agnostic; the *numbers* are not. To re-run it on
your own silicon:

1. **Re-characterize the device first.** `getprop` for model/SoC/Android
   version, `/proc/cpuinfo` for cluster layout and feature flags,
   `/proc/meminfo` for headroom, `dumpsys thermalservice` and
   `dumpsys battery` to confirm both readiness signals are queryable
   without root. Write it down before measuring anything —
   [DEVICE_CHARACTERIZATION.md](docs/02_protocols/DEVICE_CHARACTERIZATION.md)
   is the template.
2. **Re-derive the thread-count grid from the real topology.** The
   `1/2/4/8` grid here maps to Tensor G2's clusters (2 = X1 big cluster,
   4 = A78+X1, 8 = all cores). A different big/mid/little split needs a
   different grid, plus new `CONFIG_ORDER` / `THREAD_COUNT_MAP` entries in
   `analysis/compute_stats.py`.
3. **Check for extensions this device lacks.** Tensor G2's cores are
   Armv8.2-A with dot product (`asimddp`), with **no** `i8mm` and no SVE
   in `/proc/cpuinfo` — which is exactly why i8mm/KleidiAI was rejected
   here rather than benchmarked. On Armv8.6-A+ or Armv9 cores that lever
   becomes real and worth adding.
4. **Rebuild the binary for your ABI/API level.** A binary built for
   Android API 31 with NDK r28b may simply refuse to run elsewhere.
5. **Re-verify the flag surface on your build.** Do not trust this
   README's flag list — run
   `adb shell "LD_LIBRARY_PATH=/data/local/tmp /data/local/tmp/litert_lm_advanced_main --helpfull"`.
   Flag names differ between entry points and across versions
   (`--num_cpu_threads` vs. `--cpu-thread-count`), and at least one lever
   documented elsewhere (local-attention ringbuffers) does not exist on
   this binary at all.
6. **Recompute the time budget from wall-clock, not from `BenchmarkInfo`.**
   The pre-campaign estimate here was 15-20s/run; realized end-to-end
   medians were 24.9-37.0s with the cache in memory and 38.2s
   cache-disabled, because the reported metric wraps the whole `adb shell`
   launch-and-wait cycle. Budget ~25-40s/run. Five configurations x
   (5 warm-up + 30 valid) plus recovery intervals took ~4.6h here. A
   documented 20-run fallback exists — decide once, before starting, and
   apply it uniformly.
7. **Keep the input frozen and hash-locked.** Re-verify `sha256sum`
   on-device each session. Do not regenerate the prompt file mid-campaign;
   a re-typed "identical" file is not identical.

Levers already screened out here, with reasons, so you do not spend the
time twice: i8mm/KleidiAI (hardware absent), `prefill_chunk_size` (no
observable effect at this prompt length), YNNPACK (undocumented,
off-by-default upstream), speculative decoding (functional, deterministic
43.8% drafter success rate, no measurable decode gain), constant tensor
sharing (within noise), CPU affinity (out of scope by design). Full
rationale: [OPTIMIZATION_PRE_SCREENING.md](docs/01_research/OPTIMIZATION_PRE_SCREENING.md).

---

## Phase A: why this model and prompt are frozen

Before any latency measurement, the model had to be shown fit for the
workload — and then frozen, so Phase B changes execution parameters only.

- **Corpus:** 15 English technical documents (Arm big.LITTLE, Android
  CPU affinity and Thermal APIs, Linux CFS and cgroup v2, RFC 5681,
  WebAssembly, Vulkan, LLVM IR, DNS, CUDA, Git internals, Bazel, virtual
  memory, an arXiv scheduling paper), 36 scored observations.
- **Determinism:** all runs of a given document produced byte-identical
  output, on 15/15 documents — which is what justified reducing from 5 to
  2 runs per document from `doc_03` onward. One apparent divergence was
  traced to a mis-pasted input file, not to sampling.
- **Result:** mean 4.08/5, **0 critical semantic errors** in 36
  observations, 12/15 documents PASS = **80.0%** against an 80% threshold
  fixed before scoring began. Cleared by exactly nothing, and reported
  that way.
- **Known accepted defect:** on 5/15 documents the model reproduced the
  source's opening sentence in English instead of translating it. Carried
  forward as a limitation rather than patched, because the prompt freezes
  when validation starts.
- **Prompt:** exact frozen text in
  [MODEL_SELECTION_PROTOCOL.md](docs/02_protocols/MODEL_SELECTION_PROTOCOL.md).
  Chosen after 10 empirical iterations comparing 5 structurally distinct
  output formats (arrow-schema, table, SI/ALORS conditional,
  concepts+relations, guided Q&A) across 6 criteria; arrow-schema was the
  only format to pass all six.
- **Scoring honesty note:** scores were proposed by an LLM and validated
  or corrected by the author on every observation, precisely because the
  same LLM authored the prompt being evaluated. The bias risk and its
  mitigation are documented rather than glossed over.

**Phase B workload = `doc_07`** (RFC 5681 congestion control), chosen
because its Phase A score sat 0.08 from the corpus mean — the closest
match of any PASS document. Deliberately not a best case.

---

## Documentation map

Read in this order to pick the project up cold:

1. [docs/02_protocols/DEVICE_CHARACTERIZATION.md](docs/02_protocols/DEVICE_CHARACTERIZATION.md) — what the hardware is
2. [docs/01_research/RUNTIME_SELECTION.md](docs/01_research/RUNTIME_SELECTION.md) — what is being run and how it was built
3. [docs/01_research/OPTIMIZATION_PRE_SCREENING.md](docs/01_research/OPTIMIZATION_PRE_SCREENING.md) — which levers exist and which were rejected
4. [docs/02_protocols/OPTIMIZATION_PARAMETERS.md](docs/02_protocols/OPTIMIZATION_PARAMETERS.md) — frozen parameters, thresholds, decision rules
5. [docs/02_protocols/MEASUREMENT_PROCEDURE.md](docs/02_protocols/MEASUREMENT_PROCEDURE.md) — the step-by-step procedure
6. [docs/02_protocols/MODEL_SELECTION_PROTOCOL.md](docs/02_protocols/MODEL_SELECTION_PROTOCOL.md) + [docs/03_experiments_results/MODEL_SELECTION_RESULTS.md](docs/03_experiments_results/MODEL_SELECTION_RESULTS.md) — Phase A
7. [docs/03_experiments_results/OPTIMIZATION_RESULTS.md](docs/03_experiments_results/OPTIMIZATION_RESULTS.md) — Phase B results and the realized-vs-specified audit
8. [docs/ISSUE_LOG.md](docs/ISSUE_LOG.md) — every issue, root cause, and resolution

`ISSUE_LOG.md` is the highest-value document in the repo if you intend to
rebuild this. Several documented "fixes" are cases where the terminal
looked correct and the device disagreed.

## License

See [LICENSE](LICENSE).
