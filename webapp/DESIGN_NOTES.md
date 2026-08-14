# Webapp Design Notes

Design decisions for the three static pages under `webapp/`, recorded so
they are not re-litigated later. This is a working note for the webapp
specifically, not a protocol document — nothing here defines or constrains
a measurement.

## What the webapp is

| Page | Source | Generated? |
|---|---|---|
| `dashboard/index.html` | `analysis/compute_stats.py` from `data/raw/*.csv` | Yes — regenerate, never hand-edit |
| `model-selection/index.html` | `analysis/generate_model_selection_page.py` | Yes — regenerate, never hand-edit |
| `try_it/index.html` | Hand-written static page | No |

All three are plain static HTML with no build step and no backend. The two
generated pages are committed so the repository can be read without running
Python; if a figure on them disagrees with `data/raw/`, the CSVs win and
the page is stale — rerun the generator.

## The `try_it` page does not run inference

This is the decision most likely to be misread, so it is stated plainly on
the page itself: **a browser cannot execute `adb shell`**, cannot reach a
USB- or Wi-Fi-attached Android device, and cannot run the LiteRT-LM binary.
There is no hosted inference endpoint behind this project either.

`try_it` therefore does two honest things instead of one dishonest one:

1. Shows the exact frozen system prompt
   (`docs/02_protocols/MODEL_SELECTION_PROTOCOL.md`) applied to whatever
   text the visitor pastes, so they can copy the assembled prompt and run
   it themselves.
2. Shows one real, previously measured `doc_07` run — output text plus its
   actual `BenchmarkInfo` figures — labelled as a recorded measurement, not
   as something produced live in the browser.

An earlier plan had a `live-run/` page that would stream a real on-device
run to the browser. It was removed rather than faked: it needs a host-side
service holding an `adb` connection, which is outside this project's scope
and would have shipped as a mock that looked like a measurement. The empty
directory was deleted so nothing implies the feature exists.

## Long user documents: chunking, not a wider output budget

If a visitor's pasted text is longer than the corpus documents (~150-350
tokens of source each), the assembled prompt is split into sequential
chunks at natural paragraph or section boundaries — not at a hard token
cutoff — and the frozen prompt is shown once per chunk.

The frozen prompt and the 400-token output budget
(`--max_output_tokens=400`) are **never** altered for this page. Widening
the budget would create an untested code path and risk reproducing the
truncation and omission failure modes already diagnosed during prompt
design (ISSUE_LOG.md #6-7); chunking reuses the exact prompt/budget
combination Phase A validated.

### This is not scientifically validated

Prompt design was tested only on self-contained excerpts, with no
cross-references to content outside the excerpt. Chunking arbitrary text
can cut a cause-and-effect relationship across a boundary — a chunk saying
"as described in the previous section" has no access to that section. That
could reproduce the omission failure mode seen in Phase A
(MODEL_SELECTION_RESULTS.md, Observation 1), and this specific scenario was
never tested.

So the page must say so before showing a chunked document, rather than let
Phase A's validated reliability be assumed to carry over:

> "This document was split into N sections to match the validated format.
> Output quality on automatically-chunked documents has not been formally
> tested (unlike the project's 15-document reference corpus) — links
> between adjacent sections may be less precise."

### UI consequences

- No length limit on visitor input.
- Per-section indicator ("Section 2 of 6") when a document needs more than
  one chunk.
- The disclaimer above shown before the first chunked document.
- Nothing a visitor pastes is ever measured, scored, or mixed into the
  frozen Phase A/B corpus. The corpus is fixed at 15 documents and
  `doc_07`; visitor input is illustrative only.

## Presentation constraints inherited from the protocol

- **The heterogeneity caveat appears before any thread-count result**, on
  the dashboard as well as in the docs
  (`docs/02_protocols/OPTIMIZATION_PARAMETERS.md`).
- **No inferential statistics are displayed** — no error bars, no
  confidence intervals, no p-values. Medians, means, SD, min/max, speedup,
  latency reduction and the SD-based signal check only.
- **Replication status is shown as a badge, never implied.** If a result is
  not replicated the dashboard says PROVISIONAL. The current `threads_4`
  badge reflects a within-session re-measurement — see
  `docs/03_experiments_results/OPTIMIZATION_RESULTS.md`, "Realized vs.
  specified", for why that is weaker than the badge alone suggests.
- **Directory naming**: `try_it` uses an underscore. Cross-page nav links
  must match exactly; a `../try-it/` hyphen typo previously shipped as a
  broken link on every page.
