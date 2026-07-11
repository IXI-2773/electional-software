# Deployed Rule Effectiveness Scoring Result

This feature is a persisted scoped accuracy-like exact-match scoring result. It is not a broad rule-effectiveness verdict, not a deployment-safety verdict, and not a profitability or prediction-quality score.

Phase 9Z.2 adds persisted backend storage for one narrow scoring-result scope in [backend/electional/deployed_rule_effectiveness_scoring_result.py](/C:/Users/Drago/Documents/Codex/2026-05-26/need-to-connectt-my-github-to/backend/electional/deployed_rule_effectiveness_scoring_result.py).

Final release packet: [docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT_RELEASE_PACKET.md](/C:/Users/Drago/Documents/Codex/2026-05-26/need-to-connectt-my-github-to/docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT_RELEASE_PACKET.md)

## Scope

The only persisted authority scope is:

- `registered_outcome_truth_exact_match_accuracy_like`

The module persists only:

- `persisted_accuracy_like_score_ratio`
- `persisted_accuracy_like_score_percentage`
- `exact_match_count`
- `mismatch_count`
- `denominator_count`

It does not persist:

- `effectiveness_score`
- `correctness_score`
- `success_rate`
- `failure_rate`
- `production_score`
- `profitability_score`
- `prediction_quality_score`
- `deployment_safety_score`
- `overall_score`
- `final_score`
- `quality_score`

## Required Confirmation

Recording requires the exact confirmation string:

- `RECORD_EFFECTIVENESS_SCORING_RESULT`

Wrong confirmation returns a blocked result and performs no writes.

## Dry-Run Recalculation

The persisted scoring-result backend does not trust caller-supplied dry-run outputs.

It recomputes the dry run internally from:

- the scoring-contract result,
- outcome-truth records,
- readiness and evaluation-spec bindings,
- the telemetry snapshot,
- the explicit observation window.

Only the exact-match accuracy-like fields are lifted into the persisted result.

## Storage

Files are stored under:

- `data/source_documents/deployed_rule_effectiveness_scoring_result/plans/`
- `data/source_documents/deployed_rule_effectiveness_scoring_result/results/`
- `data/source_documents/deployed_rule_effectiveness_scoring_result/receipts/`

Indexes are stored under:

- `data/source_documents/indexes/deployed_rule_effectiveness_scoring_result_plan_index.json`
- `data/source_documents/indexes/deployed_rule_effectiveness_scoring_result_index.json`
- `data/source_documents/indexes/deployed_rule_effectiveness_scoring_result_receipt_index.json`

Plan, result, and receipt payloads are fingerprinted deterministically and written atomically.

Read-only loads, health checks, and reports do not create storage folders or index files when the scoring-result store is absent.

Persisted-result loads and health checks validate:

- result fingerprint integrity
- receipt presence and receipt-to-result fingerprint match
- authority-scope match
- absence of forbidden generic scoring fields

## Boundary Preservation

This phase does not claim:

- deployment safety,
- production correctness,
- profitability,
- prediction quality.

It also preserves these boundaries:

- Phase 9W acceptance is not scoring input.
- Runtime completion is not correctness.
- Source availability is not effectiveness.

## Public Surface

Phase 9Z.3 adds a controlled write seam on top of the 9Z.2C read-only seam.

Read-only API wrappers exist for:

- `get_deployed_rule_effectiveness_scoring_result_manifest`
- `build_deployed_rule_effectiveness_scoring_result_workspace`
- `validate_deployed_rule_effectiveness_scoring_result_eligibility`
- `load_deployed_rule_effectiveness_scoring_result`
- `build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack`
- `build_deployed_rule_effectiveness_scoring_result_summary_surface`
- `get_deployed_rule_effectiveness_scoring_result_health`
- `format_deployed_rule_effectiveness_scoring_result_public_safe_export_report`
- `format_deployed_rule_effectiveness_scoring_result_report`
- `format_deployed_rule_effectiveness_scoring_result_summary_surface_report`

Controlled write API wrappers now also exist for:

- `build_deployed_rule_effectiveness_scoring_result_plan`
- `record_deployed_rule_effectiveness_scoring_result`

The desktop panel exposes only:

- build persisted scoring-result plan
- record persisted scoring result with exact confirmation
- load persisted scoring result
- load public-safe scoring export pack
- load persisted scoring result summary
- validate persisted scoring-result eligibility
- persisted scoring-result health
- copy public-safe scoring export report
- copy persisted scoring-result report
- copy persisted scoring-result summary report

Recording requires the exact confirmation string:

- `RECORD_EFFECTIVENESS_SCORING_RESULT`

Wrong confirmation blocks before the record wrapper call with:

- `scoring_result_confirmation_exact_match_required`

Missing plan ID blocks before the record wrapper call with:

- `scoring_result_plan_id_required`

The desktop seam does not expose:

- score overrides
- forced recalculation
- any generic effectiveness score

## Operator Workflow

1. Validate eligibility.
2. Build a persisted scoring-result plan.
3. Record only with exact confirmation: `RECORD_EFFECTIVENESS_SCORING_RESULT`.
4. Load the recorded result and inspect health.
5. Use the public-safe export pack when a public-safe read-only handoff is needed.
6. Use summary/report as read-only views.

This workflow records and displays persisted scoped accuracy-like exact-match scoring results only.

It does not establish broad rule effectiveness, deployment safety, production correctness, profitability, prediction quality, aggregate effectiveness, ranking quality, or future performance.

## Read-Only Summary Surface

## Public-Safe Export Pack

Phase 10D adds a read-only public-safe export pack for one persisted scoring result.

The export pack:

- performs zero writes;
- loads one persisted scoring result by ID;
- exposes only the scoped persisted accuracy-like fields:
  - `persisted_accuracy_like_score_ratio`
  - `persisted_accuracy_like_score_percentage`
  - `exact_match_count`
  - `mismatch_count`
  - `denominator_count`
  - `eligible_record_count`
  - `excluded_record_count`
  - `duplicate_collapsed_count`
  - `conflict_count`
- preserves the existing false boundary flags for deployment safety, production correctness, profitability, prediction quality, Phase 9W scoring input, runtime-completion correctness, and source-availability effectiveness;
- excludes raw outcome-truth payloads, raw telemetry payloads, filesystem paths, stack traces, and raw JSON storage content.

Corrupt or missing persisted scoring results are reported as blocked/corrupt export state and are not valid public-scoring authority.

The export pack does not add a new score family, does not calculate a generic effectiveness score, and does not widen authority beyond registered outcome-truth exact-match accuracy-like evidence.

Phase 9Z.4A adds a read-only summary surface over persisted scoring results.

The summary surface:

- performs zero writes;
- does not create plans, results, or receipts;
- does not recalculate or persist a new score;
- reports repository-wide counts for valid and corrupt persisted scoring results;
- can load one persisted scoring result into a scoped summary view;
- treats corrupt persisted scoring-result records as not valid authority.

The summary surface does not add:

- aggregate effectiveness scoring;
- result ranking;
- cross-result comparison;
- score overrides;
- any generic effectiveness, correctness, profitability, prediction-quality, or deployment-safety score.

The API/UI seam does not accept caller-supplied score values, metric overrides, numerator overrides, denominator overrides, or authority-scope overrides. The backend still recomputes the dry run internally and remains scoped to `registered_outcome_truth_exact_match_accuracy_like`.

This seam does not claim deployment safety, broad production correctness, profitability, or prediction quality. Dashboard or reporting work should remain a later read-only phase after the write-seam boundary audit passes.

## Public-Safe Reporting

Public-safe persisted scoring-result reports and summary reports are limited to the registered outcome-truth exact-match accuracy-like scope.

They do not copy:

- raw telemetry JSON
- raw outcome-truth records
- secrets
- credentials
- absolute paths
- stack traces

## Focused Validation Limits

Validation for this feature has been intentionally focused on exact scoring-result nodes rather than broad project-wide suites.

Focused validation does not establish:

- global regression safety
- broad deployment safety
- broad production correctness
- profitability
- prediction quality

## Final Release Handoff Notes

This feature records and displays persisted scoped accuracy-like exact-match scoring results only.

It does not establish broad rule effectiveness, deployment safety, production correctness, profitability, prediction quality, future performance, ranking quality, or aggregate effectiveness.

Focused exact-node tests were run by policy; broad regression coverage was intentionally not claimed.

Known risks remain limited to prerequisite modules outside this feature path that may still create storage eagerly in their own read paths. That behavior was not redesigned here.
