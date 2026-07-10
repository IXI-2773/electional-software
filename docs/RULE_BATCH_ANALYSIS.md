# Rule Batch Analysis

Phase 9I.1 restricts batch rule analysis to one submitted PDF and one current `source_revision` at a time.

## Single-PDF operating model

Every workspace and plan now requires:

- `document_id`
- `source_revision`
- `dataset_id`
- `policy_id`

The batch engine validates the existing document manifest before rule discovery. A batch is blocked when the document is missing, the manifest is missing or blocked, the requested revision is not current, or the document is quarantined.

Repository-wide batch selection is not available. `include_document_certified_rules=True` means:

- scan active certified rules
- keep only rules whose authoritative provenance resolves to the requested `document_id`
- keep only rules whose authoritative provenance resolves to the requested `source_revision`

## Provenance and explicit rule IDs

Each selected rule must preserve a compact provenance trace containing:

- `rule_id`
- `document_id`
- `source_revision`
- `proposal_id`
- `proposal_promotion_receipt_id`
- `activation_receipt_id`
- `certification_receipt_id`
- `provenance_status`

Explicit rule IDs are deduplicated and sorted deterministically. Mixed-document and mixed-revision explicit lists are not silently narrowed; plan creation is blocked instead.

## Plans, runs, and receipts

Phase 9I.1 writes:

- `rule_batch_plan_v2`
- `rule_batch_run_v2`
- `rule_batch_receipt_v2`

Each plan, run, item, and receipt stores:

- `document_id`
- `source_revision`
- `document_manifest_fingerprint`

The plan fingerprint now includes:

- document and revision scope
- manifest fingerprint
- dataset and policy fingerprints
- ordered rule IDs
- ordered rule fingerprints
- ordered provenance fingerprints
- certification receipt IDs
- bounded resource limits

Legacy unscoped `rule_batch_plan_v1` records remain readable as historical records but cannot execute or resume. They return `legacy_unscoped_batch_plan` and must be rebuilt.

## Revision locking

Execution and resume are revision-locked. Before the first item and before each subsequent item, the batch engine re-checks:

- current document revision
- current manifest fingerprint
- rule fingerprint
- per-item provenance fingerprint
- certification receipt binding

If the PDF changes revision or the manifest fingerprint changes, the run becomes `stale` and stops before processing the next item. The batch is not automatically rebuilt.

## Analysis and recommendation reuse

Phase 9G analysis reuse is accepted only when the current in-scope rule and dataset still match the planned fingerprints.

Phase 9H recommendation reuse is accepted only when the recommendation references the accepted analysis and still matches the in-scope rule and policy fingerprints.

No recommendation review, action-candidate creation, rollback, supersession, scoring change, objective-pack change, Fast Lane action, or replay execution occurs in this phase.

## Resource limits

Per submitted PDF batch:

- default maximum rules: `10`
- hard maximum rules: `25`
- default maximum records per rule: `200`
- hard maximum records per rule: `500`
- hard total evaluations: `5000`

When more eligible rules exist than the selected `max_rules`, the batch plan uses the first deterministic bounded subset and reports the omitted count.

## Public-safe reporting

Public-safe reports begin with the single-PDF scope and include:

- document
- source revision
- eligible rules discovered
- rules selected
- rules omitted by limit
- foreign-document count
- foreign-revision count

Reports omit absolute paths, PDF text, citation text, proposal content, private dataset payloads, stack traces, and secrets.

## API and desktop UI

The existing Phase 9I wrappers remain the same functions, but the relevant calls now require `document_id` and `source_revision`.

The existing desktop `Batch Rule Analysis` section now uses:

- Document ID
- Source Revision
- Dataset ID
- Policy ID
- optional rule IDs
- Include Certified Rules from This PDF
- Maximum Rules
- Maximum Records per Rule
- Batch Plan ID
- Batch Run ID
- Stop After Items
- Cancellation Reason

## Targeted testing policy

Phase 9I.1 uses one focused file:

- `backend/tests/test_rule_batch_analysis.py`

Broad project-wide suites remain out of scope for this corrective pass.
