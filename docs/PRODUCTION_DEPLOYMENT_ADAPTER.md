# Production Deployment Adapter

Phase 9V.0 adds a stable deployment adapter contract over two existing foundations:

- Phase 9U.0 read-only production target descriptors
- Phase 9V.0A authoritative production activation transactions

## Current foundations

- Production state owner: `canonical_rule_runtime`
- Transaction foundation: `production_activation_transaction`
- Production target metadata: `production_target_descriptor`

The adapter does not implement Phase 9V orchestration. It wraps one-rule deployment boundaries only.

## Public adapter contract

- `get_production_deployment_adapter_manifest(...)`
- `get_production_deployment_target_workspace(...)`
- `validate_production_deployment_package(...)`
- `preflight_production_deployment(...)`
- `read_production_deployment_state(...)`
- `apply_production_deployment(...)`
- `verify_production_deployment(...)`
- `commit_production_deployment(...)`
- `rollback_production_deployment(...)`

## Target workspace

Workspace loading reuses Phase 9U.0 helpers and validates:

- production environment class
- intended production target kind
- metadata-only access mode
- no operational entrypoints
- current descriptor fingerprints
- descriptor health
- current canonical production-state fingerprint

Workspace loading performs zero writes and creates no transaction.

## Deployment package

The adapter validates one deterministic deployment package containing:

- one canonical rule
- one document
- one source revision
- one certification identity
- one controlled integration binding
- one production authorization binding
- one production target binding
- one adapter binding

The adapter rejects prohibited fields such as callbacks, scripts, credentials, secrets, routing controls, confirmation tokens, and unsupported package fields.

## Transaction-package binding

The adapter converts a validated deployment package into the Phase 9V.0A transaction package schema. The conversion preserves:

- canonical rule identity and fingerprint
- canonical rule payload
- document and source revision
- certification identity
- production authorization identity and fingerprint
- production target identity
- production descriptor fingerprint
- deployment package fingerprint

## Read-only preflight

Preflight:

1. loads the target workspace
2. validates the deployment package
3. builds the exact transaction package
4. calls the Phase 9V.0A preflight
5. performs zero writes

## Pending apply

Pending apply requires the exact confirmation:

- `APPLY_AUTHORIZED_PRODUCTION_DEPLOYMENT`

The adapter calls only the Phase 9V.0A pending-apply boundary. It does not create a canonical rule directly and does not commit automatically.

## Independent verification

Verification independently reads persisted transaction state and requires:

- transaction state `pending_verification`
- independent persisted pending-state fingerprint verification
- canonical rule still absent from active production state

## Explicit commit

Commit requires the exact confirmation:

- `COMMIT_AUTHORIZED_PRODUCTION_DEPLOYMENT`

Before commit, the adapter revalidates:

- current target descriptor health
- current descriptor fingerprints
- independent pending state
- expected pending-state fingerprint
- current production-state fingerprint

Commit then calls only the Phase 9V.0A explicit commit boundary and independently verifies the committed canonical rule afterward.

## Rollback

Rollback requires the exact confirmation:

- `ROLLBACK_AUTHORIZED_PRODUCTION_DEPLOYMENT`

Rollback calls only the Phase 9V.0A rollback boundary, then independently verifies:

- pending state removal when rolling back a pending deployment
- inactive committed rule state when rolling back a committed deployment
- no unrelated canonical rule changes

## Deterministic fingerprints

The adapter uses deterministic fingerprints for:

- the adapter manifest
- the deployment package
- the bound transaction package

They exclude timestamps, paths, usernames, process IDs, and mutable production state.

## Scope and idempotency

The adapter is limited to:

- one rule
- one document
- one source revision
- one production target
- one transaction

Identical preflight is deterministic. Drift and conflicts are blocked rather than retried automatically.

## Production-safety limits

The adapter does not invoke:

- proposal activation
- chart scoring
- production scoring
- live Fast Lane execution
- promotion
- supersession
- other Phase 9P–9U workflows

It only reuses the Phase 9U.0 descriptor contract, the Phase 9V.0A transaction contract, and authoritative canonical-rule readback.

## Relationship to later Phase 9V orchestration

Phase 9V.0 provides the stable adapter contract only.

Later Phase 9V orchestration remains deferred and is responsible for:

- evidence-chain orchestration
- authorization-chain orchestration
- broader deployment sequencing
- retries or operator workflow around the adapter
