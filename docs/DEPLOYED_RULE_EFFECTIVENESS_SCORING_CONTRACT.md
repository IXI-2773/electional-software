# Deployed Rule Effectiveness Scoring Contract

Phase 9Z.0 follows Phase 9Y.5 and adds only the scoring-contract layer in [backend/electional/deployed_rule_effectiveness_scoring_contract.py](/C:/Users/Drago/Documents/Codex/2026-05-26/need-to-connectt-my-github-to/backend/electional/deployed_rule_effectiveness_scoring_contract.py).

It does not execute a scoring engine.

It does not calculate:

- effectiveness scores
- correctness scores
- success rates
- failure rates
- prediction-quality values
- profitability values

## Required Evidence Chain

The contract requires explicit bound evidence for:

- readiness result
- effectiveness-evaluation spec result
- outcome-truth source result
- outcome-truth record set
- telemetry snapshot metadata
- execution-attempt bindings
- observation window

It does not auto-select newer records.

## Scoring Contract Versus Scoring Engine

This phase defines what a future engine would need.

It does not perform:

- expected-versus-actual comparison
- numerator calculation
- denominator calculation
- confusion-matrix calculation
- calibration calculation
- runtime-effectiveness calculation

## Metric Families

The scoring-contract module defines machine-readable contract families:

- `accuracy_like_contract`
- `false_positive_false_negative_contract`
- `precision_recall_like_contract`
- `calibration_like_contract`
- `runtime_reliability_contract`

Each family records required inputs, required truth fields, required execution-event fields, current support, unsupported reasons, and `calculation_performed = false`.

## Numerator And Denominator Contracts

The denominator contract defines:

- eligible attempts
- required execution binding
- required outcome-truth binding
- duplicate handling
- invalid/corrupt record exclusion
- unsupported-record exclusion
- observation-window matching
- denominator readiness

The numerator contract defines:

- what a future numerator would represent
- required comparison rule
- required expected/actual fields
- unsupported reason
- numerator readiness

Neither contract calculates a value or rate.

## Boundary Rules

The scoring contract preserves the outcome-truth boundary:

- Phase 9W acceptance is not scoring input
- runtime completion is not correctness
- source availability is not effectiveness

The contract may become ready for future engine design only when the evidence chain is valid. That still does not mean any score, correctness value, or rate has been calculated.

## Storage

Immutable storage only:

- `data/source_documents/deployed_rule_effectiveness_scoring_contract/plans/`
- `data/source_documents/deployed_rule_effectiveness_scoring_contract/results/`
- `data/source_documents/deployed_rule_effectiveness_scoring_contract/receipts/`
- `data/source_documents/indexes/deployed_rule_effectiveness_scoring_contract_plan_index.json`
- `data/source_documents/indexes/deployed_rule_effectiveness_scoring_contract_result_index.json`
- `data/source_documents/indexes/deployed_rule_effectiveness_scoring_contract_receipt_index.json`

## Confirmation

Recording a scoring-contract result requires exact confirmation:

- `RECORD_EFFECTIVENESS_SCORING_CONTRACT_RESULT`

Plan, result, and receipt records are immutable and idempotent.

## API And Desktop Seam

Phase 9Z.0B exposes the backend contract through API wrappers in [backend/electional/api.py](/C:/Users/Drago/Documents/Codex/2026-05-26/need-to-connectt-my-github-to/backend/electional/api.py) and one compact desktop section in [backend/electional/desktop_right_panel.py](/C:/Users/Drago/Documents/Codex/2026-05-26/need-to-connectt-my-github-to/backend/electional/desktop_right_panel.py).

Wrappers are provided for:

- manifest loading
- workspace loading
- eligibility validation
- plan creation
- result recording
- result loading
- repository-wide health
- public-safe report formatting

The desktop section is titled `Deployed Rule Effectiveness Scoring Contract` and requires explicit IDs for:

- canonical rule
- Phase 9V deployment result
- production target
- deployed-rule instance
- telemetry snapshot
- readiness result
- effectiveness-spec result
- outcome-truth source result
- outcome-truth record set
- observation window
- scoring-contract plan
- scoring-contract result

It does not auto-select newer readiness, spec, outcome-truth, telemetry, or scoring-contract records.

## Desktop Actions

Read-only actions:

- Load Scoring Contract Workspace
- Validate Scoring Contract Eligibility
- Load Scoring Contract Result
- Scoring Contract Health
- Copy Scoring Contract Report

Write actions:

- Build Scoring Contract Plan
- Record Scoring Contract Result

Repository-wide health remains explicit in the UI as `Health Scope: repository-wide`.

## Confirmation And Validation

Recording a scoring-contract result still requires the exact confirmation string:

- `RECORD_EFFECTIVENESS_SCORING_CONTRACT_RESULT`

Read-only actions require no confirmation.

Desktop validation blocks wrapper calls when required IDs are missing. Input changes mark displayed scoring-contract workspace, eligibility, plan, result, health, and copied-report state stale until refreshed again.

## Displayed Contract State

The desktop seam surfaces:

- scoring-contract status
- metric family count and metric-family statuses
- numerator and denominator contract readiness
- outcome-truth readiness
- scoring support status
- bound readiness/spec/outcome-truth IDs
- plan/result IDs
- blocker and warning counts
- recommended action

The UI always preserves the boundary lines:

- `Effectiveness Score Calculated: no`
- `Correctness Calculated: no`
- `Rates Calculated: no`

## Public-Safe Report Copy

`Copy Scoring Contract Report` uses only the backend public-safe formatter.

It does not copy raw telemetry payloads, raw outcome-truth payloads, raw snapshot JSON, secrets, credentials, or absolute paths.

## Expected Next Phase

The next safe step is Phase 9Z.0C: a scoring-contract seam boundary audit.

Do not implement a scoring engine until that audit passes and the contract remains clearly separate from score execution.
