# Certified Rule Scoring Preview

Phase 9P adds a one-PDF, one-revision, one-rule, one-config read-only scoring preview over persisted Phase 9O.2 objective outcomes.

## Purpose

- Reuse one current compatible Phase 9O.2 result.
- Reuse one persisted Phase 9P.1 objective-outcome scoring configuration.
- Score stored baseline and rule-enabled objective outcomes directly.
- Compare raw and bounded score changes without mutating production scoring, chart scoring, Fast Lane, or active rule state.

## Phase Relationships

- Phase 9O.2 must already have persisted `baseline_objective_outcomes` and `rule_enabled_objective_outcomes` with `objective_outcome_persistence = "baseline_and_rule_enabled_v1"`.
- Phase 9P.1 supplies the persisted scoring configuration, scoring-config fingerprint, and scoring evaluator fingerprint.

## Scope

- One PDF
- One current source revision
- One active certified canonical rule
- One completed current Phase 9O result
- One scoring configuration
- One bounded controlled record set
- Shadow/read-only scoring only

## Compatibility Requirements

The selected Phase 9O result must be current, receipt-backed, Phase 9P-compatible, and non-legacy. The selected scoring configuration must load by exact `scoring_config_id`, validate successfully, and bind to the exact Phase 9O objective-pack ID and evaluation fingerprint.

## Scoring Behavior

- Baseline scoring consumes stored `baseline_objective_outcomes` directly.
- Rule-enabled scoring consumes stored `rule_enabled_objective_outcomes` directly.
- Phase 9P does not rerun canonical rule evaluation, objective evaluation, or Phase 9O orchestration.
- Raw and bounded scores are preserved per record.
- Component changes are tracked through changed and unchanged objective IDs.

## Persistence

Phase 9P writes only:

- `certified_rule_scoring_preview_plans/`
- `certified_rule_scoring_preview_results/`
- `certified_rule_scoring_preview_receipts/`
- their matching indexes

Plans, results, and receipts use deterministic IDs and fingerprints. Identical reruns return `already_completed` with zero writes.

## Staleness and Health

Preview state becomes stale when the Phase 9O result fingerprint, Phase 9O receipt relationship, rule fingerprint, certification fingerprint, source revision, objective-pack fingerprint, controlled-input fingerprint, scoring-config fingerprint, or scoring-evaluator fingerprint changes.

Health checks validate:

- plan/result/receipt relationships
- record and comparison counts
- score-delta arithmetic
- stale dependency state
- receipt/result fingerprint agreement

## Read-Only Protections

Phase 9P verifies that it does not mutate:

- canonical rules
- certifications
- objective packs
- Phase 9O plans, results, or receipts
- controlled inputs
- scoring configurations
- chart-scoring state
- Fast Lane state
- production outputs

Detected mutation is reported as `mutation_detected`.

## API and UI

API wrappers expose:

- workspace load
- eligibility validation
- plan build
- read-only execution
- public-safe reporting

The desktop right panel exposes one compact `Certified Rule Scoring Preview` section with workspace, eligibility, plan, run, health, and report actions.

## Reporting

Public-safe reports include:

- identities
- status
- coverage
- comparison counts
- mean and median deltas
- stale or blocker state
- next action

They omit full objective payloads, full rule payloads, full controlled inputs, paths, stack traces, and secrets.

## Interpretation Limits

Numerical score changes are shadow scoring only. They do not prove profitability, production effectiveness, safety, or deployment readiness.
