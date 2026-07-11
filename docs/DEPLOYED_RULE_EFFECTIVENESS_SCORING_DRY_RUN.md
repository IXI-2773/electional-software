# Deployed Rule Effectiveness Scoring Dry Run

Phase 9Z.1 follows Phase 9Z.0C and creates the first controlled scoring work in [backend/electional/deployed_rule_effectiveness_scoring_dry_run.py](/C:/Users/Drago/Documents/Codex/2026-05-26/need-to-connectt-my-github-to/backend/electional/deployed_rule_effectiveness_scoring_dry_run.py).

This phase is dry-run only.

It does not persist an effectiveness score, correctness value, rate, result, receipt, or scoring index.

## Dry-Run Versus Persisted Scoring

This phase may calculate candidate metrics in memory only.

Every dry-run result is explicitly labeled:

- `dry_run_only = true`
- `authoritative_result = false`
- `persistence_performed = false`
- `writes_performed = 0`

These values are:

- non-authoritative
- not deployment safety evidence
- not a persisted production effectiveness result
- not a production correctness result

## Required Evidence

The dry run requires explicit bound inputs for:

- canonical rule
- Phase 9V deployment result
- production target
- deployed rule
- telemetry snapshot
- readiness result
- effectiveness-spec result
- outcome-truth source result
- outcome-truth record set
- scoring-contract result
- observation window

It does not auto-select newer records.

## Eligible-Record Selection

Only records that bind to the explicit identity set and observation window are eligible.

Eligible records must also have:

- `expected_outcome`
- `actual_or_adjudicated_outcome`
- source identity
- source fingerprint
- execution binding through `execution_event_id` or `input_fingerprint`
- valid record fingerprint
- `truth_status = valid`

Records with missing bindings, missing outcomes, mismatched identity, mismatched window, or unsupported substitute status are excluded with explicit reasons.

## Duplicate And Conflict Handling

Deterministic handling is enforced:

- exact duplicate record fingerprints collapse
- identical duplicate execution bindings collapse
- conflicting duplicate execution bindings block the dry run

The result surfaces:

- eligible record count
- excluded record count
- duplicate collapsed count
- conflict count
- exclusion reasons

## Exact-Match Comparison

The first dry-run comparison is deterministic only:

- exact type-aware equality
- canonical JSON equality for JSON-like values
- normalized string equality when both values are strings

No fuzzy, semantic, or manual comparison is allowed.

## Candidate Accuracy-Like Calculation

The current implemented metric family is:

- `accuracy_like_contract`

It may calculate:

- candidate exact match count
- candidate mismatch count
- candidate denominator count
- candidate accuracy ratio
- candidate accuracy percentage

The calculation scope is always `dry_run_only`.

Candidate metrics are not final.

## Unsupported Metric Families

The first pass keeps these blocked explicitly:

- `runtime_reliability_contract`
  - `runtime_reliability_inputs_not_loaded_in_dry_run`
- `false_positive_false_negative_contract`
  - `class_semantics_not_defined`
- `precision_recall_like_contract`
  - `positive_class_semantics_not_defined`
- `calibration_like_contract`
  - `confidence_or_probability_evidence_missing`

## Boundary Preservation

This phase preserves the scoring boundary:

- runtime completion is not correctness
- Phase 9W acceptance is not scoring input
- source availability is not effectiveness
- no API or desktop seam exists yet for this dry-run layer

## No Persistence

This phase creates no:

- scoring result folders
- scoring receipt folders
- scoring indexes
- scoring history
- dry-run history

## Expected Next Phase

The next safe step is a dry-run scoring boundary audit.

Do not persist scoring results until that audit passes.
