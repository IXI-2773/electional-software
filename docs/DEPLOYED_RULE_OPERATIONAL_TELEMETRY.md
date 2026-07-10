# Deployed Rule Operational Telemetry

Phase 9X implements a read-heavy telemetry foundation for one deployed production rule instance.

## Dependencies

- Requires one completed Phase 9V deployment result loaded through `load_certified_rule_production_deployment_result(...)`.
- Optionally accepts one Phase 9W post-deployment acceptance result as context only.
- Phase 9W acceptance is not treated as effectiveness evidence.

## Lifecycle Binding

- The canonical rule remains the certified source rule.
- The deployed rule remains the production instance created by Phase 9V.
- Telemetry binds one canonical source rule, one deployed rule instance, one production deployment result, one production transaction, and one production target.

## Runtime Contracts Used

- Phase 9V loader:
  - `backend/electional/certified_rule_production_deployment.py`
  - `load_certified_rule_production_deployment_result(...)`
- Production transaction readback:
  - `backend/electional/production_deployment_adapter.py`
  - `read_production_deployment_state(...)`
- Canonical and deployed rule readback:
  - `backend/electional/canonical_rule_runtime.py`
  - `load_canonical_rule(...)`

## Persistence Helpers Reused

- Storage-root resolver: `SOURCE_DOCUMENT_ROOT`
- Directory helper: `_ensure_analysis_dirs(...)`
- Atomic JSON writer: `_atomic_write_json(...)`
- JSON loader: `_read_json(...)`
- Deterministic fingerprint helper: `_hash_payload(...)`
- Rollback helper: `_restore_json(...)`
- Relative-path convention: index entries store repository-relative paths only

## Storage Model

- Events:
  - `data/source_documents/deployed_rule_operational_telemetry/events/<event_id>.json`
- Snapshots:
  - `data/source_documents/deployed_rule_operational_telemetry/snapshots/<snapshot_id>.json`
- Indexes:
  - `data/source_documents/indexes/deployed_rule_operational_event_index.json`
  - `data/source_documents/indexes/deployed_rule_operational_snapshot_index.json`

## Trust Boundary

- `record_deployed_rule_operational_event(...)` is the trusted internal producer boundary.
- No unrestricted API wrapper is exposed for arbitrary event ingestion.
- Desktop/UI support is intended to remain read-only for telemetry review.

## Producers

- Implemented state producer:
  - `authoritative_deployment_state_observer`
- Supported state event types:
  - `deployment_state_observed`
  - `deployed_instance_active_observed`
  - `deployed_instance_inactive_observed`
  - `deployment_state_mismatch_observed`
  - `deployment_state_corruption_observed`
- Execution telemetry:
  - `execution_telemetry_available = false`
  - missing producer path:
    - `no_repository_execution_producer_for_deployed_rule_instances`

## Event Schema

- Schema version:
  - `deployed_rule_operational_event_v1`
- Event records bind:
  - producer identity and fingerprint
  - canonical source-rule identity and fingerprint
  - deployed-rule identity and fingerprint
  - Phase 9V result identity
  - production target
  - production transaction
  - document ID and source revision
  - certification identity and fingerprint
  - production authorization identity
  - deployment-package fingerprint
  - committed production-state fingerprint
  - current production-state fingerprint
  - observation timestamp
  - event status
  - immutable event identity and fingerprint

## Timestamp Authority

- State observations generate `observed_at` internally.
- A private testing timestamp hook exists only for deterministic focused tests.

## Immutable Behavior

- Event writes are immutable.
- Identical retries return `already_recorded` with zero writes.
- Conflicting reuse of an existing immutable event ID returns `conflict` and preserves the original event.

## Event and Index Failure Handling

- Event and snapshot writes use atomic JSON persistence.
- If index update fails after an attempted new record write, the backend restores the prior record/index state where its existing rollback helper can do so safely.
- Health surfaces orphan and index mismatch conditions instead of silently treating them as success.

## Historical Integrity Versus Current Staleness

- Historical event integrity is separate from current deployment state.
- A historically valid event is not reclassified as corrupt solely because the deployed instance later changes state.

## Event Listing

- `list_deployed_rule_operational_events(...)` requires exact:
  - `deployed_rule_id`
  - `production_deployment_result_id`
- Supported bounded filters:
  - `event_type`
  - `producer_id`
  - `start_timestamp`
  - `end_timestamp`
  - `max_results`
- Deterministic ordering:
  1. `observed_at`
  2. producer ID
  3. per-producer sequence
  4. event ID

## Snapshot Schema

- Schema version:
  - `deployed_rule_operational_snapshot_v1`
- Snapshots store:
  - validated event IDs
  - validated, invalid, corrupt, stale-historical, and current-binding mismatch counts
  - producer IDs and producer fingerprints
  - per-producer sequence gap counts
  - metric availability
  - `effectiveness_evaluation_status = not_performed`

## Snapshot Completeness

- Snapshot construction refuses to silently truncate matching events.
- If total matching events exceed the supported snapshot bound, snapshot construction returns `blocked` and writes no snapshot.

## Evolving Immutable Snapshots

- Snapshot identity binds:
  - deployed-rule ID
  - Phase 9V result ID
  - observation window
  - manifest fingerprint
  - validated event IDs
  - producer fingerprints
- New matching events inside the same window produce a new immutable snapshot ID instead of overwriting an older snapshot.

## Duplicate Definitions

- Idempotent duplicate attempts are reported only through immutable event-id reuse handling.
- Conflicting immutable IDs are surfaced as conflicts.
- No speculative retry-attempt metric is fabricated.

## Corruption Classifications

- Health distinguishes:
  - unreadable event files
  - unreadable snapshot files
  - fingerprint mismatch
  - index-to-file missing
  - index identity mismatch
  - unsupported producer
  - unsupported event type
  - missing deployment binding
  - snapshot references missing event

## Metric Availability

- Phase 9X does not perform effectiveness evaluation.
- Execution-derived metrics remain unavailable without a real execution producer.
- Unsupported execution metrics are reported as `unsupported_by_producer`.

## Health Depth

- Health validates:
  - manifest fingerprint
  - producer definitions
  - Phase 9V plan/result/receipt integrity
  - production transaction binding
  - deployed-rule binding
  - canonical-rule binding
  - event files and event index
  - snapshot files and snapshot index
  - snapshot event references
  - orphan records
  - current binding mismatches
  - execution telemetry availability limits

## API Boundary

- Read-oriented wrappers exposed in `backend/electional/api.py`:
  - `build_deployed_rule_operational_telemetry_workspace`
  - `validate_deployed_rule_operational_telemetry_eligibility`
  - `list_deployed_rule_operational_events`
  - `build_deployed_rule_operational_snapshot`
  - `format_deployed_rule_operational_telemetry_report`

## UI Boundary

- Phase 9X is intended to expose a compact read-only telemetry review surface.
- Event ingestion remains backend-only and is not a user-facing manual operation.

## Effectiveness Boundary

- Phase 9X establishes authoritative telemetry storage and deterministic snapshots only.
- It does not prove operational effectiveness, scoring quality, profitability, routing correctness, or Fast Lane effectiveness.

## Production-Safety Restrictions

- No production deployment is invoked by Phase 9X.
- No rollback is invoked by Phase 9X.
- No canonical rule is mutated.
- No deployed-rule state is mutated.
- No scoring semantics, routing behavior, fallback behavior, or Fast Lane behavior is changed.
