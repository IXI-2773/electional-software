# Production Activation Transaction

Phase 9V.0A adds a separate authoritative production-activation transaction layer on top of the existing canonical-rule runtime.

## Authority

- Authoritative production state owner: `canonical_rule_runtime`
- Existing activation path preserved: `activate_rule_from_promoted_proposal(...)`
- Existing rollback path preserved: `rollback_proposal_rule_activation(...)`
- New transaction path is separate and does not reroute existing callers

## Storage

Transaction records are stored under:

- `data/source_documents/production_activation_transactions/pending/`
- `data/source_documents/production_activation_transactions/records/`
- `data/source_documents/production_activation_transactions/rollback_records/`
- `data/source_documents/indexes/production_activation_transaction_index.json`

Pending payloads are never stored in the active canonical-rule registry.

## Implemented flow

1. Deterministic preflight
2. Pending-only apply
3. Independent pending readback
4. Explicit commit through `create_canonical_rule(...)`
5. Independent committed-state verification through `load_canonical_rule(...)`
6. Rollback by pending cleanup or exact committed-rule deactivation

## Public functions

- `get_production_activation_transaction_manifest(...)`
- `preflight_production_activation_transaction(...)`
- `apply_production_activation_transaction(...)`
- `read_production_activation_transaction_state(...)`
- `commit_production_activation_transaction(...)`
- `rollback_production_activation_transaction(...)`
- `get_production_activation_transaction_health(...)`

## Transaction states

- `applying`
- `pending_verification`
- `committing`
- `committed`
- `apply_failed`
- `commit_failed`
- `rolling_back`
- `rolled_back`
- `rollback_failed`

Impossible transitions are blocked.

## Fingerprints

Deterministic fingerprints are used for:

- adapter manifest
- transaction package
- transaction identity
- pending state
- committed production-state snapshot

They exclude timestamps, paths, usernames, process IDs, and logging metadata.

## Scope limits

- one canonical rule
- one document
- one source revision
- one transaction
- one final canonical-rule activation

No batch behavior, no cross-document behavior, no proposal activation orchestration, no scoring, and no Fast Lane execution are performed here.

## Production-safety limits

Allowed mutations are limited to:

- pending transaction storage during apply
- one canonical-rule creation during explicit commit
- deactivation of that exact transaction-owned rule during rollback

Phase 9V.0A does not deploy anything beyond canonical-rule runtime state and does not implement the Phase 9V production deployment adapter or later orchestration.
