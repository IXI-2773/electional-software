# Autonomous PDF Corrective Action

Phase 9M executes one approved corrective action for one reviewed Phase 9L remediation case.

Scope:

- one `remediation_case_id`
- one `document_id`
- one `source_revision`
- one approved action type
- optional same-revision benchmark verification

Phase 9M does not automatically patch application code, mutate source PDFs, or tune benchmark thresholds.

## Supported actions

- `close_expected_behavior`
- `close_no_action`
- `apply_benchmark_manifest_amendment`
- `request_new_source_revision`
- `create_phase_9j_fix_package`
- `create_phase_9k_fix_package`

Review-to-action compatibility remains explicit and bounded.

## Authorization

- execute requires `EXECUTE_ACTION`
- verify requires `VERIFY_ACTION`
- close requires `CLOSE_ACTION`

Authorization is bound to one corrective action only.

## Storage

- `data/source_documents/autonomous_pdf_corrective_actions/`
- `data/source_documents/autonomous_pdf_corrective_action_receipts/`
- `data/source_documents/indexes/autonomous_pdf_corrective_action_index.json`
- `data/source_documents/indexes/autonomous_pdf_corrective_action_receipt_index.json`

## Manifest amendments

- limited to one allowed expected collection record at a time
- top-level benchmark identity fields remain immutable
- manifest fingerprint is recalculated deterministically
- the previous manifest state remains auditable through amendment evidence
- failed amendment writes must restore the prior manifest or report rollback failure

## Verification and closure

- verification reuses Phase 9L remediation verification rather than introducing a second resolution algorithm
- verification remains same-document and same-revision only
- closure preserves resolved, partially resolved, persists, regressed, unavailable, or stale outcomes honestly
- no-action and expected-behavior closures do not claim benchmark improvement

## Public-safe reporting

Reports include:

- document and revision
- remediation case
- action type and status
- review decision
- verification requirement and outcome
- closure status
- metric deltas when available

Reports omit:

- absolute paths
- full PDF text
- citation text
- proposal content
- rule payloads
- developer-private notes
- stack traces
- secrets
