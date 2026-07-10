# Certified Rule Fast Lane Preview

Phase 9Q adds a stored, read-only Fast Lane compatibility preview for one certified rule.

## Purpose

- load one active certified canonical rule
- validate one current document and source revision
- load the authoritative Phase 9Q.0 Fast Lane capability manifest
- run one compatibility-only evaluation
- store one deterministic preview result and one immutable receipt

## Scope

- one PDF
- one source revision
- one active certified rule
- one Fast Lane contract
- one compatibility preview at a time

## Compatibility-Only Mode

Preview mode is `compatibility_only_read_only`.

- Fast Lane execution is prohibited.
- Activation is prohibited.
- Rule conversion or compatibility overrides are prohibited.

## Eligibility

The preview requires:

- an active canonical rule
- a current certification that matches the same rule fingerprint
- current document/source provenance
- a valid deterministic Fast Lane capability manifest
- the Phase 9Q.0 compatibility evaluator
- no unresolved critical remediation blocker
- no pending supersession

## Deterministic Plans

Plans bind:

- canonical rule ID
- document and source revision
- rule schema version
- rule fingerprint
- certification identity and fingerprint
- Fast Lane contract identity and version
- Fast Lane capability fingerprint
- compatibility evaluator fingerprint
- preview mode

Identical current inputs produce the same plan ID and plan fingerprint.

## Evaluation

Phase 9Q reuses the Phase 9Q.0 compatibility evaluator directly. It does not duplicate operator, field, action, or semantic-loss logic.

## Result and Receipt Behavior

The result stores:

- dimension results
- supported and unsupported operators
- supported and unsupported fields
- supported and unsupported actions
- semantic-loss status
- overall compatibility
- blockers and warnings
- deterministic fingerprints
- final preview status

The receipt stores only safe identifiers, fingerprints, compatibility summary counts, status, and creation time.

## Incompatible and Partial Results

The preview may complete technically while still concluding:

- `partially_compatible`
- `incompatible`

That outcome is preserved honestly and is not converted into a successful compatibility claim.

## Idempotency and Staleness

- identical rerun returns `already_completed` with zero writes
- changed rule, certification, source revision, contract version, capability fingerprint, evaluator fingerprint, or schema version makes stored state stale
- stale previews are not rerun automatically

## Health Checks

Health checks validate:

- plan/result/receipt relationships
- duplicate IDs
- impossible compatibility combinations
- stale previews
- receipt/result fingerprint consistency
- mutation indicators

## Public-Safe Reporting

The public report includes:

- rule/document/revision identity
- certification status
- Fast Lane contract identity
- preview status
- overall compatibility
- semantic loss
- dimension statuses
- supported and unsupported operators, fields, and actions
- blockers, warnings, and recommended next action

It omits full rule payloads, source payloads, paths, stack traces, and secrets.

## API and UI Boundaries

Phase 9Q adds:

- workspace
- eligibility
- plan
- run
- report API wrappers

and one compact desktop section for the same read-only workflow.

It does not add execution, activation, or override controls.

## Safety Boundary

Compatibility preview does not establish deployment readiness, activation safety, or production effectiveness.
