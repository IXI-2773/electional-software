# Deployed Rule Outcome-Truth Source

Phase 9Y.4 adds a backend-only outcome-truth source foundation in [backend/electional/deployed_rule_outcome_truth_source.py](/C:/Users/Drago/Documents/Codex/2026-05-26/need-to-connectt-my-github-to/backend/electional/deployed_rule_outcome_truth_source.py).

It does not calculate effectiveness, correctness, success rate, failure rate, prediction quality, profitability, or operational value.

## Why Outcome Truth Is Required

Execution telemetry can prove only that a deployed rule ran and whether runtime execution completed or failed.

Readiness can prove only that enough execution evidence exists to attempt a later evaluation phase.

Effectiveness scoring requires a separate authoritative outcome-truth source that binds expected or target conditions to actual or adjudicated outcomes for specific deployed-rule execution attempts.

## Valid Outcome Truth

A valid source must provide an authoritative relation between:

- one execution attempt or equivalent input fingerprint;
- one expected output, target condition, or prediction target;
- one actual or adjudicated outcome;
- one observation window;
- one source identity and source fingerprint;
- one authority class;
- one deterministic binding to deployed execution evidence.

Accepted source types are limited to:

- `adjudicated_ground_truth`
- `verified_actual_outcome`
- `labeled_evaluation_record`
- `external_authoritative_result`

Accepted authority classes are:

- `authoritative`
- `adjudicated`
- `verified`
- `provisional`

## What Is Not Outcome Truth

These are explicitly rejected as substitutes:

- runtime returned normally
- runtime failed
- readiness passed
- Phase 9W acceptance succeeded
- deployed rule is active
- no failures were observed
- user-facing status text
- documentation claims

Registration also rejects substitute source types such as:

- `phase9w_acceptance`
- `runtime_completion`
- `readiness_status`
- `absence_of_failures`

## Source Statuses

- `outcome_truth_source_available`
- `outcome_truth_source_unavailable`
- `outcome_truth_source_incomplete`
- `outcome_truth_source_unsupported`
- `outcome_truth_source_stale`
- `outcome_truth_source_corrupt`
- `blocked`

The current repository baseline is expected to remain `outcome_truth_source_unavailable` until a real authoritative source exists.

## Record-Set Contract

Phase 9Y.4B extends the same backend module with immutable outcome-truth record-set ingestion.

Additional storage:

- `data/source_documents/deployed_rule_outcome_truth_sources/record_sets/`
- `data/source_documents/deployed_rule_outcome_truth_sources/records/`
- `data/source_documents/indexes/deployed_rule_outcome_truth_record_set_index.json`
- `data/source_documents/indexes/deployed_rule_outcome_truth_record_index.json`

Each ingested record must include:

- `outcome_truth_record_id`
- `outcome_truth_record_set_id`
- `source_id`
- `source_type`
- `source_authority_class`
- `source_fingerprint`
- `canonical_rule_id`
- `production_deployment_result_id`
- `production_target_id`
- `deployed_rule_id`
- `telemetry_snapshot_id`
- `execution_event_id` or `input_fingerprint`
- `observation_window_start`
- `observation_window_end`
- `expected_outcome`
- `actual_or_adjudicated_outcome`
- `outcome_observed_at`
- `truth_status`
- `confidence_class`
- `record_fingerprint`

Registration requires exact confirmation:

- `REGISTER_OUTCOME_TRUTH_RECORD_SET`

Registration is immutable and idempotent:

- identical record-set registration is zero-write idempotent
- conflicting record-set IDs or record IDs are rejected and not overwritten

## Criteria

The module records explicit criteria for:

- effectiveness spec result presence and fingerprint validation
- readiness result presence and readiness/spec blocker compatibility
- telemetry snapshot presence
- execution attempt presence
- candidate outcome-truth source discovery
- source authority
- execution-attempt binding
- expected value availability
- actual or adjudicated value availability
- observation window availability
- source fingerprint availability
- explicit non-substitution of Phase 9W acceptance
- explicit absence of effectiveness scoring

## Persistence

The module persists only its own immutable records:

- `data/source_documents/deployed_rule_outcome_truth_sources/plans/`
- `data/source_documents/deployed_rule_outcome_truth_sources/results/`
- `data/source_documents/deployed_rule_outcome_truth_sources/receipts/`
- `data/source_documents/indexes/deployed_rule_outcome_truth_source_plan_index.json`
- `data/source_documents/indexes/deployed_rule_outcome_truth_source_result_index.json`
- `data/source_documents/indexes/deployed_rule_outcome_truth_source_receipt_index.json`

It does not mutate telemetry, readiness, effectiveness-spec, deployment, rollback, canonical-rule, or deployed-rule state.

## Why No Effectiveness Score Is Calculated

This phase validates only whether a real outcome-truth source exists and can bind safely to execution evidence.

Phase 9Y.4B can now ingest authoritative record sets and surface them back through source discovery only when:

- the record set binds to the requested deployed rule and deployment result
- the record set binds to the requested telemetry snapshot or execution evidence
- expected and actual/adjudicated values are present
- authority class is acceptable

It still does not calculate effectiveness, correctness, or any score.

If no real source exists, scoring remains blocked.

If an inspectable candidate is incomplete or unsupported, scoring remains blocked.

Only a later scoring engine may use this foundation, and only after real authoritative source evidence exists.

Outcome-truth source availability only unblocks future scoring-contract work. It does not mean effectiveness has been evaluated, correctness has been calculated, or any success/failure rate exists.

## API And Desktop Seam

Phase 9Y.4D exposes the existing backend contract through API wrappers for:

- outcome-truth manifest
- workspace loading
- eligibility validation
- plan building
- result recording and loading
- health
- public-safe report formatting
- record-set validation
- record-set registration
- record-set loading
- record-set listing

The desktop right panel now includes a compact `Deployed Rule Outcome Truth Source` section with explicit required identifiers:

- canonical rule ID
- Phase 9V deployment result ID
- production target ID
- deployed rule ID
- telemetry snapshot ID
- readiness result ID
- effectiveness spec result ID
- observation start
- observation end
- outcome-truth source ID
- outcome-truth record-set ID
- outcome-truth record JSON

Record-set validation and registration require explicit JSON input for one object or a list of objects. Registration requires exact confirmation:

- `REGISTER_OUTCOME_TRUTH_RECORD_SET`

Outcome-truth result recording uses a separate exact confirmation:

- `RECORD_OUTCOME_TRUTH_SOURCE_RESULT`

Only write actions require confirmation:

- `Register Record Set`
- `Record Outcome Truth Result`

Read-only actions do not require either confirmation:

- workspace load
- eligibility validation
- plan building
- result loading
- record-set validation
- record-set loading
- record-set listing
- health
- public-safe report copy

If any outcome-truth input changes, the displayed workspace, eligibility, plan/result, record-set, health, and report state are marked stale until refreshed.

`Copy Outcome Truth Report` copies only the backend public-safe report. It does not copy raw record JSON, telemetry JSON, snapshot JSON, credentials, stack traces, or absolute paths.
