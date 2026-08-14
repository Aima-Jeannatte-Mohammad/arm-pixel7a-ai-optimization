# Issue Log

Technical issues encountered while building and running this project,
with root cause and resolution for each. Annex document — not part of
the protocol, but the audit trail behind several protocol decisions.

**Scope**: an entry earns its place only if it changed a technical
decision, invalidated data, or would have silently corrupted a
measurement. Ordinary environment friction, repository administration,
clerical slips, and behaviour that is documented platform basics are
deliberately *not* logged — a log that records everything records
nothing. Where such a case still produced a durable constraint, the
constraint is documented where it applies (for example the mandatory
`LD_LIBRARY_PATH` on every invocation, in
[01_research/RUNTIME_SELECTION.md](01_research/RUNTIME_SELECTION.md))
rather than as an issue here.

Issue numbers are stable and referenced from other documents. They are
grouped by phase; within a group they are chronological.

---

## A. Runtime selection and deployment

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 1 | The `pip`-installed `litert-lm` CLI has no way to target the connected Pixel 7 | That CLI runs inference on the host machine only; Android execution needs a separately built, device-targeted binary | Built from source via Bazel `--config=android_arm64` (WSL2 + NDK r28b) and pushed to the device with `adb`. This is what committed the project to a native build toolchain rather than a packaged CLI |
| 2 | `CANNOT LINK EXECUTABLE`: `libGemmaModelConstraintProvider.so` not found | The binary depends on a shared library its own Bazel target does not produce — it is a prebuilt referenced via `//prebuilt/android_arm64:...` in the BUILD file | Located it in the clone's `prebuilt/android_arm64/`, confirmed it was a real ELF object and not a Git LFS pointer, pushed it alongside the binary |
| 3 | `--max_output_tokens` and `--max_num_tokens` had no effect on generation length: 5 consecutive runs produced exactly 920 tokens regardless of flag value (250, 20, unset) | Source verification (`grep` on `runtime/engine/litert_lm_main.cc`) showed that entry point never reads the benchmark token settings — that logic exists only in `litert_lm_advanced_main.cc`. What actually stopped generation at 920 tokens (EOS vs. an internal limit) was not diagnosed further: the binary was the wrong tool regardless | Switched the measurement binary to `litert_lm_advanced_main`, which implements the length control and `--benchmark` mode the fixed workload requires |
| 4 | `--benchmark=true --benchmark_prefill_tokens=15 --input_prompt=...` produced 0 prefill turns and 0 decode turns — no generation at all | Source verification (`runtime/engine/litert_lm_lib.cc`): `benchmark_prefill_tokens > 0` activates a synthetic fake-token mode that discards the real input prompt and suppresses output (`should_print_output = benchmark_prefill_tokens == 0`) | Froze the working combination: `--benchmark=true` alone plus `--max_output_tokens`, which limits real-prompt generation while still emitting `BenchmarkInfo` metrics |

## B. Model and prompt validation (Phase A)

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 5 | Prompt variants tested on the same document produced inconsistent output between runs — unclear whether the variance came from the prompt changes or from non-deterministic sampling | No `--seed`, `--temperature`, `--top_k` or `--top_p` flags exist in `litert_lm_advanced_main` (unlike the `pip` CLI). The default sampling strategy could not be confirmed from a brief source inspection | Investigation stopped deliberately rather than pursued to exhaustion. Documented as an open uncertainty, mitigated by the multi-run-per-document design, which averages over generations regardless of the underlying cause. Determinism was later confirmed empirically: 15/15 documents byte-identical across their runs |
| 6 | Needed to confirm the arrow-schema output format was a sound choice, not a lucky first result | — | Compared 4 structurally distinct alternatives (table, SI/ALORS conditional, two-section concepts+relations, guided Q&A) against it on the same source document under the same 400-token budget, across 6 criteria. Arrow-schema was the only format to pass all 6: the table format embedded whole English clauses in "concept" cells, SI/ALORS and Q&A each dropped a source relationship, and the two-section format truncated mid-word at the token ceiling |
| 7 | The prompt omitted the source document's general context, and a first fix asking for contextual synthesis made the model invent a relationship absent from the source | Requesting synthesis — even briefly — gave the model latitude to extrapolate, turning a possible omission into a possible critical semantic error | Replaced synthesis with a bounded literal instruction (translate the source's own opening sentence as-is) plus an explicit "do not infer or add" guard. Verified line-by-line against the source: no omissions, no inventions. This is the frozen prompt |
| 8 | `Failed to get decode profile summary: INVALID_ARGUMENT` warning on every run, from the first inference test onward | Source-confirmed (`runtime/core/tasks.cc:760-766`): the warning fires when `executor.GetProfileSummary()` fails, and is called only *after* decode timing has completed. It affects one optional profiling metadata field, with no error propagation | Confirmed non-blocking by source inspection rather than by observed behaviour alone. Documented as a known harmless warning; no timing metric is affected |
| 9 | The 15-document corpus exposed recurring output defects not visible during prompt pre-validation: opening-sentence translation failure (5/15 documents), LaTeX arrow notation instead of `→` (1 document), single-chain structure instead of separated relationships (1 document) | The frozen prompt had been validated on 2 self-authored test documents; the larger corpus covered content those two did not | Documented as accepted limitations of the retained model in MODEL_SELECTION_RESULTS.md, not corrected — the prompt freezes when validation begins, and revisiting it would restart validation from zero. Not a blocker: 12/15 documents still met the quality threshold |

## C. Measurement instrumentation

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 10 | `peak_rss_kb` and `cpu_pct` were always `None`: `/proc/<PID>` polling never found the process | The PID captured from the background launch belonged to an intermediate shell, not to the binary — so the harness polled a process that was not doing the work | Forced `exec` in the launch command so the background job's own PID is the binary's. Without this the harness produces complete, plausible, wrong resource numbers |
| 11 | On an adb-level failure (e.g. two devices attached and the target ambiguous), the harness looped indefinitely without progressing or surfacing the real problem | adb-level errors were being caught by the same path as a normal "device not ready" readiness result, so the fix-the-connection case was retried forever instead of raised | Introduced an explicit `AdbError`, raised immediately and never retried, distinguishing "cannot talk to the device" from "device not ready yet". The run aborts and reports how many runs completed |

## D. Campaign execution (Phase B)

| # | Issue | Root cause | Resolution |
|---|---|---|---|
| 12 | A pilot run reported `status: 4` (not charging) in `dumpsys battery` while `Charging state: 1` (AC powered) was also true — an apparent contradiction | `status` reflects the battery's actual charging behaviour, which can read "not charging" near full even while plugged in (charge-protection throttling). It is a different signal from physical power connection | Prompted a broader decision: run Phase B entirely on battery over wireless ADB, removing simultaneous charging as an uncontrolled second heat source, and raise the battery floor from 20% to 50% to limit within-campaign drift |
| 13 | A pilot run's prefill token count (447) did not match Phase A's `doc_07` count (464), initially suspected as file corruption | Methodological, not a file defect: the comparison was made against a reference text reconstructed from memory, not against the actual historical Phase A file, which cannot be byte-verified retroactively | Reframed the requirement — Phase B needs internal consistency across its own configurations, not byte-parity with Phase A's history. Locked `phase_b_prompt.txt` (SHA256 `7edcb837…`) as the canonical reference, verified identical on host and device. All 220 Phase B rows subsequently report prefill = 447 tokens, confirming the input never drifted |
| 14 | Two otherwise-identical runs of the unset-cache-flag "default" configuration reported 10,769 ms and 941 ms Init Executor — an 11x swing | Uncontrolled cache state between runs, almost certainly a stale on-disk compilation cache left by a prior run. `--cache_dir` unset and `--disable_weight_cache=true` are handled by the same code branch (`executor_settings_base.cc:312`), consistent with their similar Init Executor values | Both cache flags are now set explicitly on every Phase B run, including the thread-count sweep, so cache state cannot vary during a comparison. The cache itself was promoted to a measured lever (Lever 2) rather than left as an unexplained confound |
| 15 | The first stabilization window on baseline (6 warm-up runs) was discarded before completing | A ~4-hour gap opened between run 5 and run 6, breaking the consecutive-run assumption behind the stabilization criterion, and the battery had drained to 23% — well below the 50% floor | Discarded the whole batch rather than patch it, and restarted from run 1 once the device was back above the floor and disconnected from power |
| 16 | Baseline stabilization was restarted again after a first attempt ran with normal connectivity (cellular, Bluetooth, notifications all active) | Background radios and notification events are uncontrolled variables that can wake device components and consume CPU unpredictably. The readiness gate (thermal + battery) does not detect them | Adopted a session-level device isolation procedure — Airplane Mode with Wi-Fi re-enabled, auto-updates off, no physical interaction, other apps closed — documented in MEASUREMENT_PROCEDURE.md as a per-session precondition. The partial batch was discarded and restarted |

---

## Deviations found after the campaign

Issues above were found and resolved *during* the work. Three further
findings came out of auditing `data/raw/*.csv` against the protocol after
the campaign closed, so they are recorded as deviations rather than as
resolved issues: the realized configuration order, the replication's
session separation, and the stabilization criterion. All three are
documented in
[03_experiments_results/OPTIMIZATION_RESULTS.md](03_experiments_results/OPTIMIZATION_RESULTS.md),
"Realized vs. specified".
