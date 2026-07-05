## Proposal Promotion

Phase 9C completes the deferred Phase 9B proposal path.

Flow:

- load one Phase 9B proposal draft for promotion review
- validate proposal, citation, handoff, handoff-review, locator, current source revision, and matching revalidation provenance
- analyze deterministic exact duplicates, near duplicates, and conflicts
- save one explicit decision: `approve`, `reject`, or `request_changes`
- require exact `PROMOTE` confirmation before promotion
- promote exactly one approved proposal
- record the linked citation as accepted evidence through proposal metadata
- create one immutable promotion receipt
- resolve only the matching pending revalidation item

Storage:

- reviews: `data/source_documents/proposal_promotion_reviews/`
- receipts: `data/source_documents/proposal_promotion_receipts/`
- indexes:
  - `data/source_documents/indexes/proposal_promotion_review_index.json`
  - `data/source_documents/indexes/proposal_promotion_receipt_index.json`

Relationship to Phase 9B:

- proposal drafts must come from `created_from = citation_evidence_handoff`
- promotion reuses the Phase 9B handoff, handoff review, citation, and pending revalidation record

Duplicate and conflict analysis:

- exact duplicate: same document, source revision, source citation, target signature, normalized claim hash, and locator identity
- near duplicate: same document and citation with the same target signature but different non-critical wording
- conflict: same controlled target signature with opposing proposal category
- exact duplicates block promotion
- near duplicates require explicit acknowledgement
- noncritical conflicts require explicit acknowledgement
- critical conflicts block promotion

Review decisions:

- `approve`
- `reject`
- `request_changes`

Rules:

- reject requires a reviewer note
- request changes requires a reviewer note
- approval performs no promotion

Promotion:

- requires exact confirmation `PROMOTE`
- changes proposal status to `promoted`
- records:
  - `promotion_review_id`
  - `promotion_receipt_id`
  - `accepted_citation_ids`
  - `promoted_at_utc`
  - provenance digest metadata

Citation evidence acceptance:

- the least invasive supported representation is used
- accepted citation linkage is stored on the promoted proposal
- citation text, locator, offsets, document ID, source revision, and hash remain unchanged

Promotion receipts:

- append-only immutable records
- no full citation or proposal text is stored in the receipt

Matching revalidation resolution:

- only the matching Phase 9B pending revalidation item is resolved
- resolution recorded as `proposal_promoted`

Atomic writes and rollback:

- proposal record
- proposal index
- promotion review record
- promotion receipt
- promotion receipt index
- matching revalidation record
- revalidation index

If any write or post-write validation fails:

- all changed records are restored
- incomplete new records are removed
- affected indexes are restored
- rollback verification determines whether the result is `failed_rolled_back` or `rollback_failed`

Idempotency:

- repeated promotion of the same approved proposal returns `already_promoted`
- duplicate receipts are not created
- divergent proposal/receipt/revalidation state is blocked instead of auto-repaired

Health:

- review and receipt index readability
- duplicate review IDs
- duplicate receipt IDs
- approved reviews waiting for promotion
- promoted proposals missing receipts
- resolved revalidation mismatches
- divergent promotion states

Public-safe reporting:

- omits absolute paths
- omits full citation text
- omits full proposal content
- omits reviewer notes
- omits source text, chunk text, stack traces, and secrets

Why rule mutation remains deferred:

- promotion makes a proposal provenance-backed and available for later controlled integration
- it does not mutate election rules, scoring, Fast Lane, or objective-pack behavior

Targeted testing policy:

- run only `backend/tests/test_proposal_promotion.py`
- use focused temporary controlled fixtures
- do not run the broad project-wide suite in this phase
