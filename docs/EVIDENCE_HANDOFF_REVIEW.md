## Evidence Handoff Review

Phase 9B completes the deferred evidence-handoff path that Phase 9A left at `pending_evidence_review`.

Flow:

- load one pending handoff review workspace
- validate citation provenance, locator, and current source revision
- find deterministic existing binder candidates
- save one explicit decision: `approve_binder_insert`, `approve_proposal_draft`, `defer`, or `reject`
- require exact execution confirmation: `INSERT` for binder insertion, `DRAFT` for proposal-draft creation
- create one pending revalidation queue item for each successful completed action
- close the handoff with exactly one completed action

Storage:

- reviews: `data/source_documents/evidence_handoff_reviews/`
- review index: `data/source_documents/indexes/evidence_handoff_review_index.json`
- existing binder, proposal, and source-impact queue storage are reused

Validation:

- handoff must exist and use the supported handoff schema
- citation must exist and match handoff citation, workspace, draft, and review provenance
- current source revision must still match the citation revision
- citation locator must validate against the canonical manifest locator rules
- completed handoffs must retain exactly one completed action

Binder candidates:

- same-document linked citations
- same-document binder scope when present
- exact controlled-topic overlap when present
- deterministic ordering by already-present citation, same-document match, exact topic match, then binder ID

Decision rules:

- `approve_binder_insert` requires a valid target binder and a citation not already in that binder
- `approve_proposal_draft` requires no existing linked proposal for the same handoff
- `defer` requires a reviewer note
- `reject` requires a reviewer note

Execution:

- binder insertion updates the selected binder, binder index, handoff, review, and one pending revalidation item
- proposal-draft creation updates the proposal store, proposal index, handoff, review, and one pending revalidation item
- both execution paths use a built write set, atomic JSON writes, rollback on failure, and rollback verification
- repeated successful execution is idempotent and returns the already-applied result instead of duplicating work

Handoff status lifecycle:

- `pending_evidence_review`
- `approved_for_binder`
- `approved_for_proposal`
- `deferred`
- `rejected`
- `completed`
- `blocked`
- `stale`

Health checks:

- review index readability
- duplicate review detection
- missing revalidation detection
- divergent completed binder/proposal state detection
- pending and deferred handoff counts

Public-safe reporting:

- omits absolute paths, citation text, chunk text, source text, reviewer notes, secrets, and stack traces

Desktop UI:

- one compact Evidence Handoff Review section in the PDF intake area
- supports loading a handoff, finding binder candidates, approving binder/proposal actions, deferring, rejecting, executing INSERT or DRAFT actions, and copying a public-safe report

Remaining deferred work:

- citation promotion
- proposal promotion
- batch handoff review
- batch binder insertion
- batch proposal creation
- automatic duplicate merging
- multi-reviewer workflow
- collaboration
- citation deletion
- PDF modification

Targeted testing policy:

- run only `backend/tests/test_evidence_handoff_review.py`
- use focused temporary fixtures
- do not run the broad project-wide suite in this phase
