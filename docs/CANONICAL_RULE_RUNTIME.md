Canonical Rule Runtime
======================

This corrective Phase 9D.1 foundation closes the shared blockers that left Phase 9D activation and Phase 9E runtime revalidation partial. It adds one canonical mutable rule repository, one compact active-rule index, and one pure single-rule read-only evaluator.

Storage paths
-------------
- `data/source_documents/canonical_rules/`
- `data/source_documents/indexes/canonical_rule_index.json`

Canonical rule records
----------------------
Required persisted fields:
- `schema_version`
- `rule_id`
- `rule_type`
- `target`
- `scope`
- `condition`
- `operator`
- `value`
- `priority`
- `enabled`
- `status`
- `source_proposal_id`
- `source_revision`
- `rule_fingerprint`
- `created_at_utc`
- `updated_at_utc`

Rule fingerprints
-----------------
`rule_fingerprint` is stable sha256 content hashing over canonical rule content. Volatile timestamps are excluded.

Active-rule index
-----------------
The index stores:
- `schema_version`
- `rule_ids`
- `active_rule_ids`
- `rule_fingerprints`
- `updated_at_utc`

Atomic creation and idempotency
-------------------------------
- Creation validates the record first.
- One rule record and one compact index are written atomically with rollback on failure.
- Identical `rule_id` plus identical canonical content returns `already_created`.
- Reusing a `rule_id` with different canonical content is blocked.

Controlled deactivation
-----------------------
Rollback-compatible deactivation marks the rule `rolled_back`, preserves the rule record, removes the rule from `active_rule_ids`, and records deactivation metadata.

Supported evaluator operators
-----------------------------
- `equals`
- `not_equals`
- `greater_than`
- `greater_than_or_equal`
- `less_than`
- `less_than_or_equal`
- `between`
- `in`
- `contains`

Operator semantics
------------------
- `equals`: `actual == expected`
- `not_equals`: `actual != expected`
- `greater_than`: `actual > expected`
- `greater_than_or_equal`: `actual >= expected`
- `less_than`: `actual < expected`
- `less_than_or_equal`: `actual <= expected`
- `between`: inclusive `lower <= actual <= upper`
- `in`: `actual in expected_collection`
- `contains`: `expected in actual`

Normalized evaluator result
---------------------------
The evaluator returns:
- `schema_version`
- `rule_id`
- `rule_status`
- `operator`
- `result`
- `matched`
- `evaluated_field`
- `persistent_writes`
- `warnings`
- `blockers`

Read-only evaluator guarantees
------------------------------
The evaluator does not write rule records, change indexes, execute scoring, execute objective packs, execute Fast Lane, or execute historical replay.

Compatibility
-------------
- Phase 9D now activates canonical rules through this shared runtime.
- Phase 9D rollback now deactivates canonical rules through this shared runtime.
- Phase 9E now discovers and uses the canonical evaluator through this shared runtime.

Health checks
-------------
Runtime health reports on counts, fingerprint mismatches, orphaned index references, and unsupported active operators without repairing storage.

Unsupported for now
-------------------
- rule effectiveness analytics
- historical performance backtesting
- batch activation or certification
- automatic scoring, objective-pack, Fast Lane, or replay execution

Targeted testing policy
-----------------------
This corrective phase uses one focused test file:
- `backend/tests/test_canonical_rule_runtime.py`
