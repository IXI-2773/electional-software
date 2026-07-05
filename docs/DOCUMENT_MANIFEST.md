# Document Manifest

Phase 8N adds one canonical backend manifest per registered document. The manifest reports current controlled state, stale components, locator validity, consistency issues, and backend readiness without executing or repairing anything automatically.

## Manifest Schema

Each manifest is stored under `data/source_documents/document_manifests/` and indexed by `data/source_documents/indexes/document_manifest_index.json`.

Core fields:

- `document_id`
- `source_revision`
- `source_hash`
- `previous_source_hash`
- `revision_changed`
- `lifecycle_status`
- `pipeline`
- `record_references`
- `record_hashes`
- `stale_components`
- `consistency`
- `backend_readiness`

## Pipeline Status Meanings

- `complete`: a controlled record exists and supports completion
- `missing`: no controlled record proves completion
- `stale`: an existing record belongs to an older source state
- `blocked`: a controlled gate prevents safe use
- `failed`: a controlled record shows execution failure
- `unknown`: state could not be determined safely
- `not_applicable`: the stage does not currently apply

## Source Revision Rules

- first manifest with a readable source hash starts at revision `1`
- unchanged source hash preserves the existing revision
- changed source hash increments the revision by `1`
- missing source hash leaves revision state unknown instead of guessing

## Shared Locator Contract

Locators use `source_locator_v1`:

```json
{
  "schema_version": "source_locator_v1",
  "document_id": "pdf_abc123",
  "source_revision": 1,
  "page_number": 12,
  "chunk_id": "chunk_pdf_abc123_0001",
  "character_start": 140,
  "character_end": 275
}
```

Validation normalizes numeric strings, removes empty optional fields, and warns when optional fields cannot be verified. It does not guess page numbers, chunk IDs, or character offsets.

## Stale-Component Detection

The manifest marks stale components when:

- the controlled source hash changes
- extracted text record hashes change
- chunk-record identity changes

This is advisory only. Phase 8N does not rebuild stale components or create revalidation items automatically.

## Cross-Subsystem Reconciliation

Reconciliation checks only existing controlled records and indexes, including:

- source, preflight, extraction, chunk, diagnostics, structure, and reliability document linkage
- citation locator chunk linkage
- proposal citation references when present
- evidence binder citation and proposal references when present
- impact queue and revalidation resolution linkage

It is read-only and reports issues rather than repairing them.

## Backend Readiness

Readiness statuses:

- `ready`
- `ready_with_warnings`
- `not_ready`
- `blocked`
- `stale`
- `corrupt`
- `unknown`

Core readiness requires registered source state, readable source record, complete preflight, complete extraction, available chunks, current revision, and no critical consistency issues.

## Public-Safe Reports

Public-safe manifest reports omit:

- absolute paths
- source file paths
- source text
- chunk text
- citation or proposal text
- private notes
- stack traces
- secrets or tokens

## What Phase 8N Does Not Do

This phase does not:

- execute preflight, extraction, chunking, diagnostics, structure, reliability, or evidence steps automatically
- rewrite citations, proposals, reviews, or binders
- repair indexes or records
- render PDF pages

## Deferred Work

- P1 deferred by timebox: orchestration, stale rebuilds, manifest timelines, batch manifest rebuilds, automatic downstream revalidation, locator migration, deep repair
- P2 not attempted by policy: rendered PDF viewport, OCR, semantic search, AI interpretation

## Targeted Testing Policy

Only the focused Phase 8N test file is intended for this pass:

- `scripts/run_targeted_tests.py --file backend/tests/test_document_manifest.py`

Broad project-wide testing is intentionally skipped in this phase.
