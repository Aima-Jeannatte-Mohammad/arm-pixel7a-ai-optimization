# Model Selection Protocol

> **Scope**: the Phase A design — what was tested, how it was scored,
> and what would have caused rejection. This is a feasibility gate for
> the workload model, not an optimization phase. Outcome is reported in
> ../03_experiments_results/MODEL_SELECTION_RESULTS.md, not here.

Once this protocol completes, the model, prompt and workload are
**frozen**: Phase B varies execution parameters only, never the prompt.

## Candidate model

```
litert-community/gemma-4-E2B-it.litertlm
Format: .litertlm (generic CPU/XNNPACK variant, not SoC-targeted)
Size:   2.59 GB
SHA256: 181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c
Source: https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm
```

Rationale: most-downloaded, most recent generation (Gemma 4) generic
CPU-path model in the LiteRT Community catalog at time of selection. The
lightweight **E2B** variant was chosen over 4B/12B/26B/31B to fit the
Pixel 7's ~2 GB available RAM headroom (see DEVICE_CHARACTERIZATION.md).

Translation-specialized models (TranslateGemma family) were considered
and rejected: the workload requires concept explanation with terminology
*preservation*, not literal translation — a translation-tuned model would
work against it.

Measurement binary: `litert_lm_advanced_main`, built from source. See
../01_research/RUNTIME_SELECTION.md for the build record and why the
simpler `litert_lm_main` was abandoned.

## Frozen workload

- **Task**: English technical documentation → compact French schema
  using arrows (→) for cause-and-effect relationships between concepts,
  not flowing prose. Established technical terminology preserved in
  English where conventionally used. Complex relationships get at most
  1-2 short French clarifying sentences. The response opens with a
  literal French translation of the source's opening/title sentence.
- **Context length observed**: ~350-560 tokens (source + system prompt).
- **Output constraint**: `--max_output_tokens=400`. Observed usage on
  successful formats: 153-311 tokens — comfortable margin.
- **Generation settings**: `--backend=cpu --benchmark=true
  --max_output_tokens=400`. `--num_cpu_threads` is left at its runtime
  default (0 = auto) throughout Phase A: thread count is the *Phase B*
  variable and is not varied here.

### Frozen system prompt (exact text)

```
You are explaining technical documentation to a French-speaking engineer. Read the following English technical documentation excerpt, then explain it in French.

Do NOT write long flowing French prose. Instead:
- Begin with a direct French translation of the source text's opening/title sentence (the sentence that typically defines what the document is about), translated as-is — do not add interpretation, context, or synthesis beyond what that single sentence states.
- Then build a compact schema using arrows (→) connecting technical concepts.
- Keep established technical terms in English where conventionally used (e.g., "cache", "thread", "scheduler", "pipeline").
- Between each pair of connected terms, write IN FRENCH the specific relationship or action linking them, based on what the source text actually describes. This French text goes directly between the arrows, for example: "Exclusive state → est modifié quand un second core lit la même donnée → Shared state".
- Only where a relationship is too complex to express as a single arrow chain, add a maximum of 1-2 short French sentences of clarification.
- Do not infer or add any relationship, transition, or conclusion that is not explicitly stated in the source text.
- The full response must fit within 400 tokens and reach a complete conclusion within that budget — do not start a chain of reasoning you cannot finish.
```

**How this wording was reached**: 10 iterative empirical tests on two
structurally different source documents (a heterogeneous-CPU-architecture
excerpt and a MESI cache-coherency excerpt), comparing 5 structurally
distinct output formats (arrow schema, table, SI/ALORS conditional,
two-section concepts+relations, guided Q&A), plus targeted fixes for two
defects found by manual fidelity verification: a missing general-context
opening sentence, and a tendency to invent an unsupported relationship
when asked for open-ended context. Trail: ISSUE_LOG.md #6-7.

## Document set (frozen before evaluation)

15 technical documents, `data/documents/doc_01.txt` … `doc_15.txt`.
Categories: Arm documentation, CPU documentation, systems documentation,
software/runtime documentation, APIs, technical papers, implementation
documentation.

## Run count: planned, then reduced once

**Planned**: 15 documents × 5 runs = 75 evaluations.

**Actual**: 36 evaluations — `doc_01` and `doc_02` at 5 runs each,
`doc_03` … `doc_15` at 2 runs each.

The reduction was decided **once, in advance of scoring `doc_03`**, not
applied retroactively. Justification: the original reason for 5 runs was
to average over sampling noise, and determinism was empirically confirmed
on `doc_01` (5/5 byte-identical) and `doc_02` (5/5 byte-identical) — 10
confirmations across two structurally different documents, under varying
thermal status (NONE/LIGHT) and battery state, with no divergence. The
default sampling strategy could not be confirmed from source
(ISSUE_LOG.md #5), so this rests on observed behaviour, not on a
documented guarantee.

**Void condition**: if any run on any document had diverged from its
sibling, the reduction was void and 5-run scoring resumed for all
subsequent documents, with the divergence investigated and logged. The
condition was never triggered: the one apparent divergence was traced to
the run having been given the wrong source text, so the two runs did not
share an input and were not a divergence. That run was excluded as a
documented experimental error rather than scored, and the remaining
observations were byte-identical within every document.

## Scoring

Numeric only, no free-form commentary, recorded in
`data/model_selection/MODEL_SELECTION_SCORING.xlsx` (exact rubric on the
Instructions sheet):

1. Technical correctness (1-5)
2. Technical meaningfulness (1-5)
3. Semantic preservation (1-5)
4. Appropriate handling of established technical terminology (1-5)
5. Critical semantic errors (count) — an error that inverts or
   seriously distorts meaning

**Two-step, human-validated process.** For each output, an LLM (Claude)
proposes all 5 scores, applying the rubric line-by-line against the
source document — verifying fidelity, checking for omissions or invented
content, and justifying each score against specific textual evidence
rather than holistic impression. The project author then reviews and
validates or corrects every proposed score before it is recorded. The
author is the final decision-maker on every score.

**Why**: the same LLM authored the frozen system prompt, and is
therefore not independent of the protocol being evaluated — a risk of
bias favouring outputs produced by a prompt it designed. Human
validation of every score is the control for that risk. Purely automated
scoring would inherit the bias; fully manual scoring was impractical at
this sample size given bilingual-evaluator availability. Carried forward
as a stated limitation in MODEL_SELECTION_RESULTS.md.

## Device state during Phase A

Phase A does **not** use Phase B's strict readiness gate: the measured
variable here is output content, not latency, and content is expected to
be independent of thermal/battery state under deterministic decoding.

Thermal status, battery level and charging state are nevertheless
*recorded* before each run, for two reasons: to allow a post-hoc check
for correlation between device state and output anomalies (given the
unresolved determinism question), and to identify runs that failed or
truncated because of an extreme device state, so they can be excluded as
instrumentation failures rather than counted as model-quality signals.

## Retention criteria

The model is retained if, across all scored observations:

1. Output is technically meaningful (criteria 1-4).
2. No unacceptable proportion of critical semantic errors.
3. The predefined quality threshold is met, as configured in
   `MODEL_SELECTION_SCORING.xlsx` (Summary sheet, cells B3-B5) —
   per-output mean-score threshold, critical-error tolerance, and minimum
   proportion of passing outputs, each **set before scoring began**.
4. Local execution on the Pixel 7 is technically feasible — loads, runs,
   completes in reasonable time. Already demonstrated during prompt
   validation (Init ~0.4-13.7 s depending on cache state, decode ~15-17
   tok/s, no memory failures across 10+ runs).

Those Phase A timings are a **feasibility signal, not a Phase B
baseline**, and the two are not comparable: Phase A ran USB-connected and
AC-powered without session-level device isolation, while Phase B runs on
battery in Airplane Mode (OPTIMIZATION_PARAMETERS.md). Phase B's measured
decode throughput is 7.4-13.0 tok/s across configurations — lower than
Phase A's range, consistent with the stricter power and isolation
conditions rather than with any change to the model or prompt. Nothing in
Phase A is used as a latency reference.

The decision uses every observation, not a single favourable output.

## Statistical treatment

Small validation sample. Report individual scores, mean, median,
distribution, proportion meeting threshold, and critical-error count and
proportion. No inferential statistics — this is model-selection
evidence supporting a go/no-go decision for this project, not a
population-level claim about model quality.
