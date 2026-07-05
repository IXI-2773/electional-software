Backend Contract Validation

Purpose

Phase 8W adds a read-only backend contract certification pass for one registered document at a time. It traces the controlled document chain, validates required reader-facing and provenance contracts, saves a validation record, and produces a public-safe report. It does not repair records, run missing pipeline stages, rebuild content maps, apply locator migrations, or close revalidation items.

Checks

Required checks validate source registration, manifest availability, extraction usability, chunk presence and page references, page diagnostics, structure-map presence, content-map currentness, reader-readiness consistency, citation and proposal references, evidence-binder references, locator migration receipt consistency, and critical revalidation blockers.

Recommended and optional checks cover curation safety, pending revalidation visibility, and topic-index contribution state. Missing topic-index support is treated as a warning when topic-tagged content exists and is otherwise not applicable.

Dependency tracing

The validator traces only records scoped to the selected document:

- source record
- manifest
- preflight
- chunks
- page diagnostics
- structure map
- content map
- curation overlay
- citations
- proposals
- proposal reviews
- evidence binders
- topic-index contributions when available
- locator migration plans and receipts
- revalidation queue items

Source and manifest validation

Certification requires a registered source and an existing manifest with a usable source revision and pipeline fingerprint. Validation uses the current document-scoped fingerprint and compares stored state without mutating manifest records.

Reader-foundation validation

Certification checks that preflight is not blocked, extracted text is usable, chunks exist and belong to the document, chunk page ranges are valid, page diagnostics exist, and a structure map exists. Missing required reader-foundation records prevent certification.

Content-map and curation validation

The validator checks that the content map exists, matches the current source revision, matches the current document-scoped fingerprint, and contains valid chapter and section ranges. Curation is validated as current or safely ignored. Stale or invalid curation is never treated as active certification evidence.

Provenance validation

Citation document IDs, chunk references, proposal citation references, proposal-review references, and evidence-binder links are validated. Cross-document locator contradictions block certification.

Topic-state validation

Topic-index contribution validation is optional. If topic-tagged content exists but cross-document topic-index support is unavailable, certification may still succeed with warnings.

Migration receipt validation

Completed locator migration receipts must use valid schemas, contain after-state hashes, and record migration-created revalidation items. Rollback-failed receipts block certification.

Revalidation-state validation

Pending revalidation items are reported. Closed items must have resolution records. Critical unresolved revalidation items block certification.

Certification statuses

- `certified`: all required checks pass
- `certified_with_warnings`: required checks pass and only warning-level issues remain
- `not_certified`: one or more required checks fail
- `blocked`: a required blocker exists, including cross-document contradictions, rollback-failed receipts, or critical unresolved revalidation
- `stale`: a stored validation no longer matches current document state
- `corrupt`: malformed validation storage
- `unknown`: a required state could not be determined safely

Validation fingerprinting and staleness

Validation records store a stable state signature derived from source revision, document-scoped fingerprint, manifest fingerprint, content-map fingerprint, curation state, citation/proposal/binder identities, locator migration receipt state, and revalidation state. Stored validations are only reused when that signature still matches. Stale validations are never presented as current certification.

Storage

Validation records are stored in:

- `data/source_documents/backend_contract_validations/`
- `data/source_documents/indexes/backend_contract_validation_index.json`

Writes use atomic JSON replacement. Validation is otherwise read-only across the rest of the backend.

API helpers

The API exposes:

- `build_backend_contract_validation_plan`
- `run_backend_contract_validation`
- `load_backend_contract_validation`
- `get_backend_contract_validation_health`
- `format_backend_contract_validation_report`

Desktop UI

The PDF Intake right panel includes a compact `Backend Contract Certification` section with:

- `Build Validation Plan`
- `Run Contract Validation`
- `Load Validation`
- `Validation Health`
- `Copy Certification Report`

The section shows certification status, freshness, pass/warning/failure counts, reader readiness, citation and binder counts, pending revalidation count, rollback failure count, and the recommended next action.

Public-safe reporting

Public-safe reports omit absolute paths, source text, chunk text, citation text, proposal text, private notes, stack traces, and secrets. Reporting is intended for release-gate visibility, not repair.

Deferred behavior

Deferred by design:

- automatic repair
- automatic pipeline stage execution
- automatic content-map rebuilding
- automatic locator repair
- automatic revalidation closure
- batch document validation
- continuous monitoring
- PDF rendering and viewport integration

Targeted testing policy

Phase 8W uses one focused fixture file:

- `backend/tests/test_backend_contract_validation.py`

The targeted tests validate certification outcomes, stale detection, non-mutation behavior, and public-safe API/report flow without running a broad project-wide suite.
