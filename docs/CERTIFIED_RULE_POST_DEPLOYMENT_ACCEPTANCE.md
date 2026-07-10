# Certified Rule Post-Deployment Acceptance

Phase 9W is a read-only observation and decision layer over one completed Phase 9V production deployment.

## Dependency on Phase 9V

Phase 9W requires an authoritative completed Phase 9V deployment result and validates the linked:

- deployment plan
- deployment result
- deployment receipt
- production transaction
- deployed-rule instance
- canonical certified source rule

If required Phase 9V evidence is missing, stale, or fingerprint-mismatched, Phase 9W blocks.

## Current-State Reread

Phase 9W does not treat the stored Phase 9V result as independent proof of current production state.

It rereads:

- the current production transaction state through the production deployment adapter
- the current deployed-rule instance through canonical-rule runtime loading
- the current canonical certified source rule through canonical-rule runtime loading

Acceptance is blocked if these rereads do not match the stored Phase 9V bindings and fingerprints.

## Canonical Source Rule vs Deployed Instance

Phase 9W preserves the Phase 9V.0B lifecycle split:

- the canonical rule remains the certified source rule
- the deployed rule remains the transaction-owned production instance

Phase 9W verifies that:

- the canonical source rule still exists, remains active, and keeps the expected fingerprint
- the deployed instance still exists, remains active, and keeps the expected fingerprint
- the deployed instance still points back to the canonical source rule and production transaction

Phase 9W does not deploy, roll back, activate, deactivate, or mutate either rule.

## Mandatory Integrity Observations

The deterministic baseline observation uses only authoritative repository evidence:

- Phase 9V plan integrity
- Phase 9V result integrity
- Phase 9V receipt integrity
- current production transaction state
- current committed verification state
- deployed-rule identity and fingerprint
- canonical source-rule identity and fingerprint
- document ID and source revision
- certification identity and fingerprint
- production authorization identity and fingerprint
- production target identity
- deployment package fingerprint
- committed production-state fingerprint
- rollback and stale indicators

These checks are mandatory for `accept`.

## Optional Observations

Phase 9W currently records optional telemetry as unavailable when no authoritative repository telemetry exists.

Optional telemetry absence:

- does not fabricate data
- does not block baseline integrity acceptance
- does not imply operational effectiveness

## Deterministic Observation Plans

Phase 9W persists immutable observation plans under:

- `data/source_documents/certified_rule_post_deployment_acceptance_plans/`

Each plan is deterministic for one Phase 9V deployment result and binds:

- Phase 9V result / plan / receipt fingerprints
- canonical rule identity and fingerprint
- deployed rule identity and fingerprint
- current production transaction identity and verification state
- current source and deployed rule fingerprints
- production target identity
- committed and current production-state fingerprints
- decision options

Equivalent rereads reuse the same stored plan.

## Decisions

Supported decisions:

- `accept`
- `reject`
- `continue_observation`

Acceptance means deployment-integrity acceptance only. It does not certify:

- scoring effectiveness
- prediction quality
- profitability
- Fast Lane effectiveness
- long-term operational success

`reject` and `continue_observation` record an immutable decision but do not roll back or mutate deployment state.

## Immutable Results and Receipts

Phase 9W persists immutable decision results and receipts under:

- `data/source_documents/certified_rule_post_deployment_acceptance_results/`
- `data/source_documents/certified_rule_post_deployment_acceptance_receipts/`

Indexes are maintained under `data/source_documents/indexes/`.

Conflicting later decisions do not overwrite an existing immutable result for the same observation plan.

## Idempotency

Reapplying the same decision to the same current plan returns zero writes.

Conflicting decisions against an already-recorded immutable result return a conflict instead of overwriting records.

## Stale and Corruption Handling

Phase 9W returns stale or blocked outcomes when:

- the Phase 9V result becomes stale
- the current production transaction is no longer verified committed
- the committed production-state fingerprint no longer matches
- the deployed instance becomes inactive, missing, or rebound
- the canonical source rule changes, disappears, or no longer matches
- required Phase 9V plan/result/receipt records are missing or mismatched

Phase 9W does not automatically repair or roll back stale production state.

## Production-Safety Limits

Phase 9W is read-only with respect to deployment state.

It does not invoke:

- production deployment
- production rollback
- chart or production scoring
- live Fast Lane

## API and UI Boundaries

Backend module:

- `backend/electional/certified_rule_post_deployment_acceptance.py`

API exposure:

- build workspace
- validate eligibility
- build plan
- save decision
- format report

Desktop panel provides compact controls for:

- load workspace
- validate
- build observation plan
- save decision
- health
- copy report

These controls report backend state only and do not mutate production deployment.
