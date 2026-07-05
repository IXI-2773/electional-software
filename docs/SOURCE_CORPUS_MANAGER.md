# Source Corpus Manager

The Source Corpus Manager is the corpus-level control layer for registered source documents. It only uses controlled source records under `data/source_documents/`; it does not crawl folders, scan raw PDFs directly, or create sources from arbitrary files.

## What It Tracks

Corpus inventory records summarize each registered document:

- source registration status
- preflight status
- extraction status
- chunking status
- page diagnostics and structure-map status
- reliability band and staleness status
- linked evidence binder count
- proposal and citation counts
- duplicate and supersession status
- missing pipeline steps

Inventory summaries omit local paths and source text.

## Missing-Step Detection

Missing-step checks report gaps only. They do not run preflight, extraction, chunking, diagnostics, structure analysis, reliability recalculation, or evidence refresh automatically.

Checked steps include:

- registered
- preflight
- extracted text
- chunked text
- page diagnostics
- structure map
- reliability record
- evidence binder when proposals exist
- review records and citation strength where applicable

## Corpus Health

Corpus health reports coverage and risks:

- preflight, extraction, chunk, structure, reliability, and evidence coverage
- duplicate source risk
- superseded source risk
- stale source risk
- failed-source risk
- privacy-warning risk

Health can be `healthy`, `warning`, `critical`, `empty`, or `unknown`. It is not marked healthy unless the controlled indexes and records support that status.

## Batch Plans

Batch plans are controlled records. Creating a plan does not execute it.

Allowed actions:

- run_preflight
- extract_text
- chunk_text
- build_page_diagnostics
- build_structure_map
- recalculate_reliability
- refresh_evidence_binders
- detect_duplicates
- detect_missing_steps
- generate_corpus_report

Batch execution defaults to `dry_run=True` and has a default item limit. It only operates on registered document IDs.

## Phase 8K Execution Safety

Phase 8K keeps the same corpus manager and extends it with:

- batch locks that prevent duplicate concurrent execution
- per-item execution receipts
- atomic checkpoints written after each final receipt
- idempotency checks for completed work
- stale-start detection and explicit interruption marking
- bounded retry behavior
- receipt-based execution history
- public-safe execution reports

See:

- `docs/CORPUS_EXECUTION_RECOVERY.md`
- `docs/CORPUS_INDEX_INTEGRITY.md`
- `docs/SOURCE_IMPACT_ANALYSIS.md`
- `docs/DOCUMENT_MANIFEST.md`

## Failed, Duplicate, and Superseded Queues

The manager can list failed-source tasks, duplicate source identity candidates, and superseded source relationships. These queues are review aids only. They do not delete, merge, rewrite, or trust sources automatically.

## Bulk Rechecks

Bulk reliability recheck and evidence binder refresh default to dry-run. Controlled execution recalculates existing metadata or refreshes existing binders only. It does not create citations, proposals, rules, or promotions.

## Public-Safe Corpus Report

Public-safe corpus reports include counts, coverage percentages, risk counts, and recommended action. They omit local paths, full source text, chunk text, private notes, exact sensitive values, and source file paths.

## Unsupported Here

The corpus manager does not implement OCR, AI extraction, semantic search, embeddings, background scanning, cloud sync, automatic source deletion, automatic duplicate merging, rule mutation, Fast Lane changes, scoring changes, or automatic proposal/citation creation.

## Targeted Testing Policy

Use only the targeted corpus test file for this feature:

```powershell
scripts/run_targeted_tests.py --file backend/tests/test_source_corpus_manager.py
```

Do not run broad project-wide test discovery for this phase.
