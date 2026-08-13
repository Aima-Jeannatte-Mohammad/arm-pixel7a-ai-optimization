# Webapp Design Notes

Design decisions for Phase 12 (research dashboard + live-run interface),
recorded ahead of implementation so they are not lost or re-litigated
later. Not part of the 13 required protocol documents — this is a
working note for the webapp specifically.

## Long user-document handling (live-run view, master prompt §73-75)

The live-run view lets the user paste or provide their own English
technical documentation of arbitrary length. Unlike the frozen Phase A/B
corpus (15 documents, 150-350 tokens each, see
../docs/02_protocols/MODEL_SELECTION_PROTOCOL.md), user-provided
documents are not length-constrained.

### Mechanism: chunking, not a variable output budget

The frozen prompt and the 400-token output budget (`--max_output_tokens=400`)
must NEVER be altered for the live-run view — they stay identical to
what was validated in Phase A/B. Instead, long user documents are split
into sequential chunks of ~150-350 tokens each, respecting natural text
boundaries (paragraph/section breaks, not a hard token cutoff), and the
frozen prompt is run once per chunk. Outputs are displayed in order,
one schema per chunk.

Rationale for chunking over widening the output budget: it reuses the
exact prompt/budget combination already validated (10 prompt-design
iterations, see ../docs/ISSUE_LOG.md #8-14) rather than introducing an
untested code path. It also avoids reproducing the truncation/omission
failure modes already diagnosed and fixed during prompt design.

### Known limitation — NOT scientifically validated

The 10 prompt-design iterations were all tested on self-contained
excerpts (no cross-reference to content outside the excerpt itself).
Chunking an arbitrary user document may cut across a cause-and-effect
relationship that spans two chunks (e.g. a chunk referencing "the
previous section" with no access to that section's content). This
could reproduce the omission or invention failure modes already seen
during prompt validation (../docs/ISSUE_LOG.md #14) — but this specific
scenario (chunked, cross-referencing content) was never tested.

This must be stated plainly in the UI before running a chunked
document, not silently assumed to inherit Phase A/B's validated
reliability:

> "This document was split into N sections to match the validated
> format. Output quality on automatically-chunked documents has not
> been formally tested (unlike the project's 15-document reference
> corpus) — links between adjacent sections may be less precise."

### UI implications

- No token/length limit imposed on user input.
- A per-section progress indicator ("Section 2 of 6 processing...") in
  the live measurement view (§74) — chunked documents take
  proportionally longer (observed ~15-17 tokens/sec decode per chunk).
- The disclaimer above shown before the first run of any document
  requiring more than 1 chunk.
- Chunked live-run results are illustrative only and are never mixed
  into the frozen Phase A/B measurement corpus or