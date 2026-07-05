# Locator Migration Planner

## Purpose

Phase 8U adds a non-destructive planner for auditing stale or invalid document locators against the current controlled document revision.

It answers:

- whether a locator is still valid
- whether a deterministic replacement candidate exists
- whether the case is ambiguous or cross-document
- which downstream controlled records would be affected
- what a proposed corrected locator would look like

It does not apply any correction.

## Audit Statuses

The planner classifies locator-bearing records with statuses such as:

- `valid`
- `stale_revision`
- `missing_chunk`
- `missing_page`
- `page_chunk_mismatch`
- `invalid_offset`
- `ambiguous_target`
- `cross_document_reference`
- `unsupported_locator`
- `corrupt_record`
- `unknown`

## Deterministic Candidate Evidence

Phase 8U uses controlled metadata only:

- same document ID
- exact current chunk identity
- unique current chunk on the same page
- valid page/chunk relationship
- exact stored locator metadata already present in the record

The planner does not use:

- fuzzy text rematching
- semantic matching
- topic similarity
- embeddings
- AI reconstruction

## Safe Candidate Requirements

A proposal is a `safe_candidate` only when:

- exactly one candidate exists
- the candidate belongs to the selected document
- the target revision is current
- the page/chunk relationship is valid
- no cross-document contradiction exists

`apply_allowed` remains `false` in every Phase 8U output.

## Ambiguous and Cross-Document Handling

- multiple candidates become `manual_review`
- cross-document cases become `blocked`
- zero-candidate cases remain unresolved

The planner never guesses among multiple candidates.

## Migration Plan Fingerprinting

Each saved plan includes a deterministic fingerprint based on:

- document ID
- current source revision
- document-scoped fingerprint
- scope
- audited before-state locators
- proposal classifications
- proposed targets
- dependency IDs

Volatile timestamps are excluded from the stable fingerprint.

## Dependency Impact

Each proposal includes a read-only dependency summary covering:

- citations
- proposals
- proposal reviews
- evidence binders
- impact items
- revalidation resolutions

No impact or revalidation records are created in Phase 8U.

## Proposal Validation and Preview

Validation checks that:

- the plan still exists and is current
- the record still exists
- the before-state still matches
- the target locator still validates
- the candidate count is still exactly one

Preview returns a before/proposed-after diff without mutating any record.

## Plan Staleness

A plan becomes stale when:

- the current source revision changes
- the document-scoped fingerprint changes
- the stored fingerprint no longer matches the current proposal set

Stale plans are not silently reused.

## Public-Safe Reporting

Public-safe reports omit:

- absolute paths
- source paths
- source text
- chunk text
- citation text
- proposal text
- private review notes
- private taxonomy notes
- tokens
- API keys
- stack traces

## Deferred

P1 deferred by timebox:

- applying locator corrections
- atomic multi-record mutation
- automatic revalidation creation
- automatic impact-queue creation
- migration rollback
- migration execution receipts
- batch document migration
- manual correction editing
- approval workflow
- migration history

P2 not attempted by policy:

- fuzzy text rematching
- semantic rematching
- embeddings
- AI locator reconstruction
- OCR-assisted rematching
- PDF viewport integration

## Targeted Testing Policy

Run only:

```powershell
.\.venv\Scripts\python.exe scripts/run_targeted_tests.py --file backend/tests/test_locator_migration_planner.py
```

Do not run the broad project-wide test suite for this phase.
