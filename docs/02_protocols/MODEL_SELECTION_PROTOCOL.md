# Model Selection Protocol

## Objective

Determine whether a candidate Gemma-family model is suitable as the
fixed workload model for the execution-optimization study (Phase B).
This is a feasibility gate, not an optimization phase.

## Candidate model

`litert-community/gemma-4-E2B-it.litertlm`
Format: `.litertlm` (generic CPU/XNNPACK variant, not SoC-targeted),
per ../01_research/RUNTIME_SELECTION.md.
Size: 2.59 GB.
SHA256: `181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c`.
Source: https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm

Rationale: most-downloaded, most recent generation (Gemma 4) generic
CPU-path model in the LiteRT Community catalog at time of selection;
"E2B" (lightweight) variant chosen over larger variants (4B/12B/26B/31B)
to fit within the Pixel 7's ~2 GB available RAM headroom (see
../02_protocols/DEVICE_CHARACTERIZATION.md). Translation-specialized
models (TranslateGemma family) were considered and rejected: the
workload requires concept explanation with terminology preservation,
not literal translation (see Workload section below), which a
translation-tuned model would work against.

## Measurement binary

`litert_lm_advanced_main`, built from source via Bazel
(`android_arm64` config). See ../01_research/RUNTIME_SELECTION.md for
the full build/deployment record and the binary-selection history
(an earlier `litert_lm_main` build was abandoned — it did not support
output-length control).

## Workload (frozen)

- Task: English technical documentation -> compact French schema
  explanation using arrows (→) to represent cause-and-effect
  relationships between concepts, not flowing prose. Established
  technical terminology preserved in English where conventionally
  used. Complex relationships get a maximum of 1-2 short French
  clarifying sentences. Response opens with a literal French
  translation of the source document's opening/title sentence.
- Context: ~350-560 tokens observed (source document + system prompt
  combined) across validation tests.
- Output constraint: max 400 tokens (`--max_output_tokens=400`).
  Observed usage across validation tests: 153-311 tokens on
  successful formats — comfortable margin under the ceiling.
- System prompt (frozen, exact text):

You are explaining technical documentation to a French-speaking engineer. Read the following English technical documentation excerpt, then explain it in French.

Do NOT write long flowing French prose. Instead:
- Begin with a direct French translation of the source text's opening/title sentence (the sentence that typically defines what the document is about), translated as-is — do not add interpretation, context, or synthesis beyond what that single sentence states.
- Then build a compact schema using arrows (→) connecting technical concepts.
- Keep established technical terms in English where conventionally used (e.g., "cache", "thread", "scheduler", "pipeline").
- Between each pair of connected terms, write IN FRENCH the specific relationship or action linking them, based on what the source text actually describes. This French text goes directly between the arrows, for example: "Exclusive state → est modifié quand un second core lit la même donnée → Shared state".
- Only where a relationship is too complex to express as a single arrow chain, add a maximum of 1-2 short French sentences of clarification.
- Do not infer or add any relationship, transition, or conclusion that is not explicitly stated in the source text.
- The full response must fit within 400 tokens and reach a complete conclusion within that budget — do not start a chain of reasoning you cannot finish.

- Generation settings: `--backend=cpu --benchmark=true --max_output_tokens=400`.
  Thread count (`--num_cpu_threads`) left at its runtime default (0 =
  auto) during Phase A model validation — thread count itself is the
  Phase B optimization variable, not varied during Phase A.
- Prompt design history: this exact wording is the result of 10
  iterative empirical tests on two structurally different source
  documents (a heterogeneous-CPU-architecture excerpt and a MESI
  cache-coherency excerpt), comparing 5 structurally distinct output
  formats (arrow schema, table, SI/ALORS conditional, two-section
  concepts+relations, guided Q&A) plus targeted fixes for two defects
  found by manual fidelity verification (a missing general-context
  opening sentence, and a since-corrected tendency to invent an
  unsupported relationship when asked for open-ended context). Full
  investigation trail: see ISSUE_LOG.md entries #8-14.

## Document set (frozen before evaluation)

15 technical documents, categories: Arm documentation, CPU
documentation, systems documentation, software/runtime documentation,
APIs, technical papers, implementation documentation.
List: `data/documents/doc_01.txt` ... `doc_15.txt` (see repo).

## Evaluation design

15 documents x 5 runs = 75 output evaluations.

## Scoring (numeric only, no free-form comments)

Each output scored on, using `data/model_selection/MODEL_SELECTION_SCORING.xlsx`:
1. Technical correctness
2. Technical meaningfulness
3. Semantic preservation
4. Appropriate handling of established technical terminology
5. Critical semantic errors (count)

Scale: 1-5 per criterion 1-4 (see the workbook's Instructions sheet
for the exact rubric). Critical error definition: an error that
inverts or seriously distorts meaning (e.g. a negation dropped, a
causal relationship reversed, or a relationship invented that is not
present in the source text — see ISSUE_LOG.md #14 for a concrete
example of this last failure mode, corrected in the frozen prompt
above).

## Retention criteria

The model is retained if, across all 75 observations:
1. Output is technically meaningful (per criteria 1-4 above).
2. No unacceptable proportion of critical semantic errors.
3. Predefined quality threshold is met: as configured in
   `MODEL_SELECTION_SCORING.xlsx` (Summary sheet, cells B3-B5) —
   per-output mean-score threshold, critical-error tolerance, and
   minimum proportion of outputs required to pass, each set before
   scoring begins.
4. Local execution on the Pixel 7 is technically feasible (loads,
   runs, completes within a reasonable time) — already demonstrated
   during prompt-design validation testing (Init ~0.4-13.7s depending
   on cache state, decode ~15-17 tokens/sec, no memory failures
   observed across 10+ runs).

Decision uses all 75 observations — not a single favorable output.

## Statistical treatment

Small validation dataset (n=75). Report: individual scores, mean,
median, score distribution, proportion meeting threshold, critical-error
count and proportion. This is model-selection evidence, not
population-level statistical validation.

## Next step

Results of this protocol are reported in
../03_experiments_results/MODEL_SELECTION_RESULTS.md, not in this
document.