# Objective Outcome Scoring

Phase 9P.1 adds a separate read-only scoring foundation for objective outcomes. It does not reuse or modify the chart-scoring engine.

Implemented public functions:

- `validate_objective_outcome_scoring_config(...)`
- `save_objective_outcome_scoring_config(...)`
- `load_objective_outcome_scoring_config(...)`
- `get_objective_outcome_scoring_config_fingerprint(...)`
- `evaluate_objective_outcomes(...)`
- `get_objective_outcome_scoring_evaluator_fingerprint(...)`

Storage:

- Configs: `data/source_documents/objective_outcome_scoring_configs/<scoring_config_id>.json`
- Index: `data/source_documents/indexes/objective_outcome_scoring_config_index.json`

Configuration contract:

- `schema_version`
- `scoring_config_id`
- `objective_pack_id`
- `objective_pack_evaluation_fingerprint`
- `score_direction`
- `unmapped_objective_behavior`
- `entries`

Optional:

- `minimum_score`
- `maximum_score`

Each scoring entry requires:

- `objective_id`
- `score_when_satisfied`
- `score_when_unsatisfied`
- `missing_behavior`
- `unsupported_behavior`

Supported score directions:

- `higher_is_better`
- `lower_is_better`
- `neutral_unspecified`

Supported behaviors:

- component missing / unsupported:
  - `error`
  - `ignore`
  - `zero`
- unmapped objectives:
  - `ignore`
  - `error`

Evaluation behavior:

- Matches objective IDs exactly.
- Scores `satisfied` and `not_satisfied` outcomes explicitly.
- Does not silently treat missing or unsupported objectives as unsatisfied.
- Supports optional score bounds through clamped `bounded_score`.
- Returns component-level results plus aggregate `raw_score` and `bounded_score`.

Aggregate statuses:

- `completed`
- `completed_with_ignored_components`
- `no_scored_components`
- `blocked`
- `scoring_failed`

Read-only guarantees:

- Evaluation performs no file writes.
- Evaluation does not mutate scoring configuration input.
- Evaluation does not mutate objective outcomes input.
- Evaluation does not mutate objective packs, rules, Fast Lane, or production scoring state.

This phase does not implement:

- Phase 9P orchestration
- preview plans/results/receipts
- API wrappers
- desktop UI
- production scoring updates
- chart scoring changes
