# Evidence Binder

Phase 8H adds cross-document evidence governance for source-backed proposals.

Evidence binders are advisory review records. They do not promote rules, mutate scoring, change Fast Lane, create citations, create proposals, or judge truth.

## Storage

```text
data/source_documents/evidence_binders/
data/source_documents/source_reliability/
data/source_documents/indexes/evidence_binder_index.json
data/source_documents/indexes/source_reliability_index.json
```

## What a Binder Shows

A binder groups citations linked to a proposal by document, chunk, and excerpt preview. It summarizes:

- linked citation count
- unique document count
- source reliability bands
- citation bundle strength
- deterministic support findings
- deterministic conflict warnings
- evidence coverage
- weak or stale source warnings
- recommended manual review action

## Source Reliability

Source reliability metadata is explicit and conservative. Unknown is acceptable. The system does not fabricate publication dates, author names, authority levels, or source titles.

Manual metadata can set:

- source type
- authority level
- publication date
- modified date
- title
- author
- version label

## Support and Conflict Detection

Support/conflict detection is deterministic keyword and decision-category matching only. It does not use AI, embeddings, semantic matching, or truth judgment.

## Public Safety

Public-safe summaries omit local paths, full source text, full chunk text, exact emails, exact tokens, exact API keys, and private notes.

## Unsupported

OCR, AI extraction, semantic search, automatic citation creation, automatic proposal creation, source-backed production rule promotion, Fast Lane changes, and scoring changes are not supported here.

## Testing Policy

Use targeted tests only:

```text
scripts/run_targeted_tests.py --file backend/tests/test_evidence_binder.py
```

Do not run broad project-wide test discovery for evidence binder work.
## Phase 8I Source Reliability Manager

Source reliability records can now be edited, recalculated, versioned through history events, linked to replacement sources, checked for duplicate source identities, summarized in a quality dashboard, and used to refresh evidence binders. Reliability remains advisory only and does not mutate rules, scoring, Fast Lane, proposals, or citations.

## Corpus-Level Evidence Refresh

Phase 8J adds controlled bulk evidence binder refresh planning. Bulk refresh defaults to dry-run and refreshes existing binders only when explicitly executed. It does not create citations, create proposals, promote rules, mutate production rules, or run semantic matching.
