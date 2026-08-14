# Model Selection Results (Phase A)

> **Scope**: the outcome of MODEL_SELECTION_PROTOCOL.md — is this model
> fit to serve as the fixed workload for Phase B? Raw per-run data (all
> 36 observations, full output text, per-criterion scores, device state)
> is in `data/model_selection/MODEL_SELECTION_SCORING.xlsx` (Raw Scores
> sheet). This document reports the summary, not a copy of the raw data.

**Decision: MODEL RETAINED.** Gemma 4 E2B
(`litert-community/gemma-4-E2B-it.litertlm`) is confirmed suitable as the
fixed workload model. Model, prompt and workload are now frozen.

## Sample composition

15 documents, 36 observations: `doc_01` and `doc_02` at 5 runs each,
`doc_03` … `doc_15` at 2 runs each, following the documented one-time
run-count reduction (MODEL_SELECTION_PROTOCOL.md, "Run count").

Within every document, all runs produced **byte-identical output text** —
15/15 documents deterministic under fixed input, fixed prompt and
`--backend=cpu`.

## Per-document results

| Document | Category | Runs | Mean score | Critical errors | Result |
|---|---|---|---|---|---|
| doc_01 | Arm architecture (big.LITTLE) | 5 | 4.50 | 0 | PASS |
| doc_02 | Android CPU affinity (API) | 5 | 5.00 | 0 | PASS |
| doc_03 | Android Thermal API | 2 | 4.25 | 0 | PASS |
| doc_04 | Academic paper (arXiv, scheduling) | 2 | 2.75 | 0 | **FAIL** |
| doc_05 | Linux kernel (CFS scheduler) | 2 | 4.50 | 0 | PASS |
| doc_06 | Bazel (sandboxing) | 2 | 3.40 | 0 | **FAIL** |
| doc_07 | TCP congestion control (RFC 5681) | 2 | 4.00 | 0 | PASS |
| doc_08 | Virtual memory (Apple docs) | 2 | 3.60 | 0 | PASS |
| doc_09 | Git internals (data model) | 2 | 3.60 | 0 | PASS |
| doc_10 | Linux kernel (cgroup v2) | 2 | 5.00 | 0 | PASS |
| doc_11 | WebAssembly (W3C spec) | 2 | 5.00 | 0 | PASS |
| doc_12 | Vulkan (command buffers) | 2 | 4.40 | 0 | PASS |
| doc_13 | LLVM (IR reference) | 2 | 3.80 | 0 | PASS |
| doc_14 | CUDA (thread/block/grid) | 2 | 3.00 | 0 | **FAIL** |
| doc_15 | DNS (recursive resolver) | 2 | 4.40 | 0 | PASS |

PASS threshold: mean score ≥ 3.5.

## Aggregate

| Metric | Value |
|---|---|
| Mean score, per-document (n=15, unweighted) | **4.08 / 5** |
| Mean score, per-observation (n=36, run-weighted) | 4.19 / 5 |
| Median score (per-document) | 4.25 / 5 |
| Critical semantic errors | **0** across all 15 documents and 36 observations |
| Proportion meeting threshold, per-document | **12/15 = 80.0%** |
| Proportion meeting threshold, per-observation | 30/36 = 83.3% |

The two proportions diverge because of the asymmetric run counts. The
three FAIL documents (`doc_04`, `doc_06`, `doc_14`) carry 2 runs each, so
6 of 36 observations fall below threshold.
**The per-document figure (80.0%) is the primary retention metric**: it
weights every document equally regardless of how many times it happened
to be run, which is the document-level quality judgment the protocol
called for. The per-observation figure is diagnostic only, and is higher
because `doc_01` and `doc_02` are both above-average PASS documents
carrying 5 runs each — a byproduct of the run-count reduction, not an
intentional weighting scheme.

Both figures clear the 80% threshold set in
`MODEL_SELECTION_SCORING.xlsx` (Summary!B5) before scoring began, so the
decision does not depend on resolving the ambiguity. It is documented for
transparency, not because it changes the outcome. Note that the primary
figure clears the threshold **exactly**, with no margin.

## Observations

Stated as measured, with interpretation kept separate below.

1. **Opening-sentence translation failure.** On 5/15 documents (doc_04,
   doc_06, doc_08, doc_09, doc_12) the first line reproduced the source's
   opening sentence in English instead of translating it, despite an
   explicit prompt instruction. On 2 of these (doc_08, doc_09) the
   failure extended to several non-jargon noun phrases throughout.
2. **Non-conformant arrow notation** on 1 document (doc_13): LaTeX
   `$\rightarrow$` instead of the specified `→`, consistently across both
   runs.
3. **Single-chain structure** on 1 document (doc_14): the whole response
   as one continuous 8-arrow chain rather than separated line-by-line
   relationships, reducing readability.
4. **No inventions.** Across all 36 observations, no run introduced a
   relationship, transition or fact absent from the source. Where content
   was incomplete it was an omission, never a fabrication.
5. **Identifier preservation was reliable.** Technical identifiers
   requiring exact reproduction (`rq->cfs.min_vruntime`, `cwnd`,
   `ssthresh`, `execroot/`, `vkEndCommandBuffer`,
   `VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT`) were correct in every
   document where they appeared.

## Interpretation

The opening-sentence failure is the most consequential recurring defect:
it directly reduced semantic-preservation scores on 5/15 documents and
was the main driver of one FAIL (doc_06), with doc_08 and doc_09 held to
narrow PASSes. Because the prompt does not get revisited after Phase A
begins, this is carried forward as a **known, accepted limitation** of
the retained model's output quality. Phase B is not expected to fix it —
Phase B does not touch the prompt.

The 3 FAILs have no single shared cause: doc_04 failed on an explicit
admission of missing information that was in fact present in context;
doc_06 on the opening-sentence defect plus redundant phrasing; doc_14 on
structural degradation unrelated to translation. That diversity suggests
three independent low-probability failure modes rather than one systemic
defect.

## Limitations

- **Small sample.** n=15 documents / 36 observations. Sufficient for a
  go/no-go decision on this project, not a statistically powered claim
  about model quality. No confidence intervals or significance tests are
  computed or claimed.
- **Determinism is observed, not guaranteed.** No sampling flags exist on
  this binary and the default strategy is unconfirmed from source
  (ISSUE_LOG.md #5). The 15/15 byte-identical result is empirical.
- **Scoring is not fully independent.** Scores were proposed by the same
  LLM that authored the frozen prompt, then validated or corrected by the
  author on every observation. The mitigation is documented in
  MODEL_SELECTION_PROTOCOL.md; the residual risk is not zero.
- **Known output defects are accepted, not fixed** — see Observations 1-3
  and ISSUE_LOG.md #9.

## Retention criteria — verdict

| Criterion | Result |
|---|---|
| Output technically meaningful | Met — 12/15 documents, failures isolated rather than systemic |
| No unacceptable proportion of critical semantic errors | Met — 0% observed |
| Predefined quality threshold met | Met — 80.0% per-document against an 80% threshold fixed before scoring |
| Local execution feasible on the Pixel 7 | Met — 36/36 runs completed, no crashes, no OOM, stable ~13-17 tok/s decode (AC-powered, no session isolation — a feasibility signal, not comparable to Phase B's figures; see MODEL_SELECTION_PROTOCOL.md) |

**Phase B workload**: `doc_07` was selected as the single frozen
measurement document — its 4.00/5 score sits 0.08 from the 15-document
mean, the closest of any PASS document. Rationale in
../02_protocols/OPTIMIZATION_PARAMETERS.md.
