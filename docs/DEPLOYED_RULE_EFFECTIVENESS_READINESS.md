# Deployed Rule Effectiveness Readiness

Phase 9Y.1 adds a backend-only readiness gate in [backend/electional/deployed_rule_effectiveness_readiness.py](/C:/Users/Drago/Documents/Codex/2026-05-26/need-to-connectt-my-github-to/backend/electional/deployed_rule_effectiveness_readiness.py).

It decides whether one deployed rule has enough real execution telemetry to begin a later effectiveness-evaluation phase. It does not calculate effectiveness, quality, correctness, profitability, or prediction accuracy.

## Required IDs

- `canonical_rule_id`
- `production_deployment_result_id`
- `production_target_id`
- `deployed_rule_id`
- `telemetry_snapshot_id`
- `observation_window_start`
- `observation_window_end`

Optional:

- `post_deployment_result_id`

## Evidence used

The readiness gate binds:

- the completed Phase 9V deployment result and receipt;
- the current production transaction state;
- the current canonical source rule fingerprint;
- the current deployed-rule fingerprint;
- one explicit Phase 9X telemetry snapshot;
- the trusted execution producer:
  - `deployed_rule_execution_runtime_observer`

Phase 9W acceptance may be loaded as optional context, but it is not treated as effectiveness evidence.

## Statuses

- `ready_for_effectiveness_evaluation`
- `not_ready`
- `blocked_no_execution_events`
- `blocked_no_execution_producer`
- `blocked`
- `stale`
- `corrupt`

`ready_for_effectiveness_evaluation` is a gate only. It does not mean success, correctness, quality, profitability, or prediction accuracy.

## Readiness criteria

The module checks:

- Phase 9V deployment completed
- deployed instance still binds to the selected Phase 9V result
- canonical source rule remains unchanged
- telemetry snapshot exists and binds the expected deployed rule and deployment result
- explicit observation window matches the snapshot
- snapshot completeness is `complete`
- execution producer exists
- execution events are present and validated
- denominator semantics are available
- the sample-sufficiency rule is defined and met
- Phase 9W is not used as effectiveness evidence
- effectiveness status remains `not_performed`

## Denominator and sample sufficiency

Execution attempts count only:

- `evaluation_completed`
- `evaluation_failed`

`evaluation_completed` means only that the runtime returned normally.

`evaluation_failed` means only that the runtime failed.

The default minimum is:

- `minimum_execution_attempts = 30`

Unsupported skipped and fallback semantics remain marked unsupported. They are unavailable semantics, not zero effectiveness. This phase does not calculate any rate.

## Storage

The readiness module writes only its own immutable records:

- `data/source_documents/deployed_rule_effectiveness_readiness/plans/`
- `data/source_documents/deployed_rule_effectiveness_readiness/results/`
- `data/source_documents/deployed_rule_effectiveness_readiness/receipts/`
- `data/source_documents/indexes/deployed_rule_effectiveness_readiness_plan_index.json`
- `data/source_documents/indexes/deployed_rule_effectiveness_readiness_result_index.json`
- `data/source_documents/indexes/deployed_rule_effectiveness_readiness_receipt_index.json`

It does not mutate Phase 9V deployment state, Phase 9W records, Phase 9X events, Phase 9X snapshots, canonical rules, or deployed-rule lifecycle state.

## Persistence behavior

`build_deployed_rule_effectiveness_readiness_plan(...)` persists an immutable plan with deterministic identity and fingerprinting.

`record_deployed_rule_effectiveness_readiness_result(...)` requires exact confirmation:

- `RECORD_EFFECTIVENESS_READINESS_RESULT`

It reloads the plan and current evidence before writing immutable result and receipt records.

Identical reruns are zero-write idempotent. Conflicting immutable records are not overwritten.

## API seam

The readiness backend is exposed through project-consistent API imports for:

- `build_deployed_rule_effectiveness_readiness_workspace(...)`
- `validate_deployed_rule_effectiveness_readiness_eligibility(...)`
- `build_deployed_rule_effectiveness_readiness_plan(...)`
- `record_deployed_rule_effectiveness_readiness_result(...)`
- `load_deployed_rule_effectiveness_readiness_result(...)`
- `get_deployed_rule_effectiveness_readiness_health(...)`
- `format_deployed_rule_effectiveness_readiness_report(...)`
- `get_deployed_rule_effectiveness_readiness_manifest(...)`

## Desktop section

The desktop right panel now includes:

- `Deployed Rule Effectiveness Readiness`

Explicit inputs:

- Canonical Rule ID
- Phase 9V Deployment Result ID
- Production Target ID
- Deployed Rule ID
- Telemetry Snapshot ID
- Observation Start
- Observation End
- Optional Phase 9W Result ID
- Readiness Plan ID
- Confirmation

Read-only buttons:

- Load Readiness Workspace
- Validate Readiness Eligibility
- Build Readiness Plan
- Load Readiness Result
- Record Readiness Result
- Readiness Health
- Copy Readiness Report

The desktop section does not auto-select deployments, snapshots, deployed rules, or Phase 9W results.

## Desktop safety rules

Missing required identifiers block wrapper calls before execution.

Loading an existing readiness result requires an explicit readiness result ID. It does not rebuild a plan, recreate a result, or mutate readiness storage.

Recording a readiness result requires exact confirmation:

- `RECORD_EFFECTIVENESS_READINESS_RESULT`

When readiness inputs change, the displayed workspace, eligibility, plan, result, health, and copied-report state are marked stale.

`Readiness Health` is currently displayed as:

- `Health scope: repository-wide`

The desktop seam does not imply selected-rule health when the backend health function is repository-wide.

Copy Readiness Report uses the public-safe backend formatter. It does not copy raw telemetry event JSON, raw snapshot JSON, secrets, credentials, stack traces, or private payloads.

## Read-only boundary

This phase still does not perform effectiveness evaluation.

It does not add:

- effectiveness scoring
- success-rate or failure-rate calculation
- execution triggering
- telemetry event creation
- deployment controls
- rollback controls
- scoring controls
- Fast Lane controls

Phase 9W acceptance remains optional context only and is not effectiveness evidence.

Absence of failures is not treated as success, and execution-attempt counts are not correctness metrics.
