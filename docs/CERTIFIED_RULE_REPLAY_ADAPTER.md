# Certified Rule Replay Adapter

Phase 9N adds a bounded, shadow-only historical replay adapter for one active certified canonical rule and one historical dataset.

Implemented public helpers:

- `build_certified_rule_replay_workspace`
- `validate_certified_rule_replay_eligibility`
- `build_certified_rule_replay_plan`
- `run_certified_rule_replay`
- `load_certified_rule_replay_result`
- `get_certified_rule_replay_health`
- `format_certified_rule_replay_report`
- `get_certified_rule_replay_summary`

Storage:

- Plans: `data/source_documents/certified_rule_replay_plans/<plan_id>.json`
- Results: `data/source_documents/certified_rule_replay_results/<result_id>.json`
- Receipts: `data/source_documents/certified_rule_replay_receipts/<receipt_id>.json`
- Indexes:
  - `data/source_documents/indexes/certified_rule_replay_plan_index.json`
  - `data/source_documents/indexes/certified_rule_replay_result_index.json`
  - `data/source_documents/indexes/certified_rule_replay_receipt_index.json`

Behavior:

- Reuses the canonical single-rule evaluator.
- Reuses the historical replay foundation in dry-run mode through synthetic shadow snapshots.
- Requires an active canonical rule, a matching completed certification receipt, and a current source revision.
- Rejects datasets with unsupported schema, fingerprint mismatch, ordering errors, duplicate record IDs, foreign record dataset IDs, missing timestamps, count mismatch, more than 10,000 records, or a range longer than 10 years.
- Creates a deterministic replay plan tied to the rule fingerprint, certification fingerprint, dataset fingerprint, evaluator fingerprint, and bounded record count.
- Runs in `shadow_read_only` mode only.
- Produces immutable replay result and replay receipt records.
- Re-running the same current plan returns `already_completed` instead of writing another result.
- Health marks results stale when the rule, certification, dataset, source revision, evaluator fingerprint, or plan fingerprint changes.

Desktop controls:

- `Load Replay Workspace`
- `Validate Replay Eligibility`
- `Build Replay Plan`
- `Run Shadow Replay`
- `Replay Health`
- `Copy Replay Report`

Deferred in this phase:

- multi-rule replay
- production activation changes
- scoring changes
- objective-pack changes
- Fast Lane changes
- automatic remediation
