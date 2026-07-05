## Phase 9A

Phase 9A connects Phase 8Z reader-workspace citation drafts to the existing controlled citation repository through an explicit review step. It validates provenance, checks exact and controlled near duplicates, requires explicit approval, requires explicit `CREATE` confirmation for real citation creation, and creates a pending evidence-handoff record without modifying evidence binders or proposals.

## Relationship to Reader Workspace

Citation drafts remain stored in the revision-bound PDF reader workspace. Review records and evidence handoffs are separate controlled records:

- `data/source_documents/citation_draft_reviews/`
- `data/source_documents/citation_evidence_handoffs/`
- `data/source_documents/indexes/citation_draft_review_index.json`
- `data/source_documents/indexes/citation_evidence_handoff_index.json`

## Provenance Validation

Reviewable drafts must match the current reader workspace document and source revision. Validation checks:

- workspace currentness
- selected text present
- selected-text hash matches selected text
- page validity
- chunk existence and document/page agreement when present
- offset ordering

Validation is read-only.

## Duplicate Detection

Duplicate detection is deterministic and controlled-field-only.

Exact duplicate:

- same document
- same source revision
- same page
- same chunk when present
- same offsets
- same selected-text hash

Near duplicate:

- same document
- same source revision
- same page
- same selected-text hash
- overlapping locator offsets

Exact duplicates block creation. Near duplicates require explicit reviewer override.

## Review Decisions

Supported decisions:

- `approve`
- `reject`
- `request_changes`

Reject and request-changes require a reviewer note. Approval never creates a citation by itself.

## Explicit CREATE Confirmation

Citation creation is a separate operation. It succeeds only when:

- the review is approved
- provenance still validates
- duplicates still allow creation
- confirmation exactly equals `CREATE`

## Atomic Citation Creation

Successful creation writes:

- one real citation record in the existing citation repository
- the citation index
- the review record
- the matching workspace draft state
- one evidence-handoff record
- the evidence-handoff index

If a later write fails, created records are removed and prior records are restored.

## Draft State Update

The matching workspace draft is preserved and updated in place with:

- `status = created`
- `real_citation_id`
- `review_id`
- `evidence_handoff_id`
- `created_as_citation_at_utc`

## Evidence Handoff

The handoff record is a queue-only record with status `pending_evidence_review`. Phase 9A does not modify evidence binders, does not create proposals, and does not promote evidence.

## Idempotency

Repeating creation for a review that already created a citation returns `already_created` when the citation still exists. Divergent review/citation state is blocked rather than repaired automatically.

## Health Checks

Health reporting summarizes review counts, approved-but-not-created items, pending handoffs, and divergent creation states without mutating storage.

## Public-Safe Reporting

Public-safe reports omit:

- absolute paths
- cache paths
- full page text
- unselected source text
- private reviewer notes
- stack traces

## Deferred

Deferred by timebox:

- automatic evidence-binder insertion
- automatic proposal creation
- batch approval and batch creation
- citation editing history

Not attempted by policy:

- OCR
- semantic duplicate detection
- PDF modification

## Targeted Testing Policy

Phase 9A uses one focused file:

- `backend/tests/test_citation_draft_review.py`

The focused tests cover provenance validation, exact and near duplicates, reviewer note requirements, explicit creation confirmation, atomic citation creation updates, idempotent second creation, and proof that no evidence binder or proposal record is created automatically.
