# Rule Effectiveness Recommendation

Phase 9H adds a deterministic recommendation layer on top of Phase 9G rule-effectiveness analyses.

It loads one current analysis, validates its receipt, current rule fingerprint, certification receipt, dataset fingerprint, optional comparison-rule fingerprint, and one explicit recommendation policy. It then produces exactly one primary recommendation with condition-level explanations and fixed thresholds.

## Default Policy

`default_v1` uses schema `rule_effectiveness_recommendation_policy_v1` and fixed thresholds:

- `minimum_records_evaluated`: `30`
- `maximum_evaluation_error_rate`: `0.05`
- `minimum_evaluation_completion_rate`: `0.95`
- `minimum_match_coverage`: `0.01`
- `maximum_match_coverage`: `0.95`
- `rollback.minimum_labeled_records`: `30`
- `rollback.maximum_balanced_accuracy`: `0.40`
- `rollback.maximum_precision`: `0.35`
- `rollback.minimum_version_regression`: `0.15`
- `supersession_review.maximum_balanced_accuracy`: `0.55`
- `supersession_review.minimum_version_disagreement_rate`: `0.10`
- `supersession_review.minimum_version_regression`: `0.05`
- `monitor.minimum_balanced_accuracy`: `0.55`
- `monitor.maximum_balanced_accuracy`: `0.70`

Policy fingerprints are deterministic and are part of recommendation staleness checks.

## Recommendation Priority

Primary recommendation priority is fixed:

1. `review_data_quality`
2. `insufficient_evidence`
3. `rollback_candidate`
4. `supersession_review_candidate`
5. `monitor`
6. `continue`

Every evaluated condition is recorded. Missing metrics are marked unavailable and are never treated as zero.

## Human Review

Recommendations support these decisions:

- `accept`
- `reject`
- `defer`
- `request_more_evidence`

`reject`, `defer`, and `request_more_evidence` require a non-empty reviewer note.

Review records are stored separately from recommendation records.

## Action Candidates

Accepted recommendations may create one controlled action candidate only after confirmation exactly equal to `QUEUE`.

Candidates are queue records only. They do not execute rollback, supersession, activation, deactivation, scoring, objective-pack changes, Fast Lane changes, or replay.

Mapped candidate actions:

- `rollback_candidate` -> `rollback_review`
- `supersession_review_candidate` -> `supersession_review`
- `monitor` -> `monitoring`
- `continue` -> `no_action`
- `review_data_quality` -> `data_quality_review`
- `insufficient_evidence` / `request_more_evidence` -> `evidence_collection`

Action-candidate creation also writes one immutable decision receipt.

## Staleness

Recommendations are stale when the underlying analysis is stale or when any of these change:

- current rule fingerprint
- certification receipt or certification hash
- dataset fingerprint
- policy fingerprint
- comparison-rule fingerprint

Stale recommendations are not actionable and cannot queue candidates.

## Storage

Phase 9H stores records under:

- `data/source_documents/rule_effectiveness_recommendations/`
- `data/source_documents/rule_effectiveness_recommendation_reviews/`
- `data/source_documents/rule_action_candidates/`
- `data/source_documents/rule_effectiveness_recommendation_receipts/`
- `data/source_documents/indexes/rule_effectiveness_recommendation_index.json`
- `data/source_documents/indexes/rule_effectiveness_recommendation_review_index.json`
- `data/source_documents/indexes/rule_action_candidate_index.json`
- `data/source_documents/indexes/rule_effectiveness_recommendation_receipt_index.json`

## API Helpers

Phase 9H exposes these wrappers through `backend/electional/api.py`:

- `build_rule_effectiveness_recommendation_workspace`
- `generate_rule_effectiveness_recommendation`
- `save_rule_effectiveness_recommendation_decision`
- `create_rule_action_candidate_from_recommendation`
- `format_rule_effectiveness_recommendation_report`

## Desktop UI

The desktop right panel adds one compact `Rule Effectiveness Recommendation` control surface using:

- analysis ID
- policy ID
- recommendation ID
- decision
- reviewer note
- recommendation review ID
- action candidate ID
- queue confirmation

Buttons:

- `Load Recommendation Workspace`
- `Generate Recommendation`
- `Accept Recommendation`
- `Reject Recommendation`
- `Defer Recommendation`
- `Request More Evidence`
- `Queue Action Candidate`
- `Copy Recommendation Report`

## Public-Safe Reporting

Reports omit absolute paths, full historical contexts, full rule payloads, private reviewer notes, and stack traces.

## Deferred

Deferred by timebox or later policy:

- batch recommendation generation
- automatic rollback execution
- automatic supersession execution
- scoring integration
- objective-pack integration
- Fast Lane integration
- production historical replay integration
