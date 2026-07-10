# Certified Rule Objective Preview

Phase 9O adds a shadow read-only comparison of one active certified rule against one evaluable objective pack and one bounded controlled input set.

Implemented public helpers:

- `build_certified_rule_objective_preview_workspace`
- `validate_certified_rule_objective_preview_eligibility`
- `build_certified_rule_objective_preview_plan`
- `run_certified_rule_objective_preview`
- `load_certified_rule_objective_preview_result`
- `get_certified_rule_objective_preview_health`
- `format_certified_rule_objective_preview_report`
- `get_certified_rule_objective_preview_summary`

Storage:

- Plans: `data/source_documents/certified_rule_objective_preview_plans/<plan_id>.json`
- Results: `data/source_documents/certified_rule_objective_preview_results/<result_id>.json`
- Receipts: `data/source_documents/certified_rule_objective_preview_receipts/<receipt_id>.json`
- Indexes:
  - `data/source_documents/indexes/certified_rule_objective_preview_plan_index.json`
  - `data/source_documents/indexes/certified_rule_objective_preview_result_index.json`
  - `data/source_documents/indexes/certified_rule_objective_preview_receipt_index.json`

Behavior:

- Reuses the canonical single-rule evaluator.
- Reuses the read-only objective-pack evaluator.
- Uses the same historical-rule dataset contract as the bounded controlled input set.
- Requires an explicit rule-effect mapping.
- Applies only explicitly named mapped fields.
- Preserves baseline values for unspecified fields.
- Does not mutate rules, certifications, objective packs, or controlled input records.
- Produces immutable preview result and preview receipt records.
- Persists the exact baseline objective-evaluation result and exact rule-enabled objective-evaluation result for each processed record.
- Stores persisted objective outcomes in Phase 9P.1-compatible shape, including `objective_pack_evaluation_fingerprint`.
- Preserves record order and declared objective order from the objective pack.
- Marks compatible results with `objective_outcome_persistence = "baseline_and_rule_enabled_v1"`.
- Re-running the same current plan returns `already_completed`.
- Staleness is triggered by rule, certification, revision, objective-pack, input, mapping, evaluator, or schema changes.
- Result fingerprints cover persisted baseline and rule-enabled objective outcomes.
- Receipts include safe compatibility evidence without duplicating full objective result payloads.
- Legacy comparison-only results remain readable but are not Phase 9P-compatible; a fresh Phase 9O result is required for scoring preview.

Statuses:

- `completed`
- `completed_with_unsupported_records`
- `no_eligible_records`
- `blocked`
- `stale`
- `rule_evaluator_failed`
- `objective_evaluator_failed`
- `mutation_detected`
- `corrupt`
- `already_completed`

Desktop controls:

- `Load Objective Preview Workspace`
- `Validate Objective Preview Eligibility`
- `Build Objective Preview Plan`
- `Run Read-Only Preview`
- `Objective Preview Health`
- `Copy Objective Preview Report`

This phase does not implement:

- production activation
- scoring
- Fast Lane changes
- multiple rules or packs
- batch preview
- cross-document preview
