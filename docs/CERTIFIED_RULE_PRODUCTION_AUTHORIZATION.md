# Certified Rule Production Authorization

Phase 9U records an explicit decision that a certified rule may be deployed to production later. It does not deploy the rule, execute the production adapter, change live scoring, write production state, or reopen Phase 9T integration.

## Scope

- Input: one canonical mutable rule, one completed controlled-integration result, and one registered read-only production target descriptor.
- Dependency: the upstream Phase 9R decision must be exactly `authorize_for_later_integration`.
- Decision values:
  - `authorize_for_later_production_deployment`
  - `defer_production_deployment`
  - `reject_production_deployment`
- Authorized outcome:
  - `decision = authorize_for_later_production_deployment`
  - `status = authorized`

## Storage

Separate immutable records are stored under `data/source_documents/`:

- `certified_rule_production_authorization_plans/`
- `certified_rule_production_authorization_results/`
- `certified_rule_production_authorization_receipts/`

Derived indexes:

- `indexes/certified_rule_production_authorization_plan_index.json`
- `indexes/certified_rule_production_authorization_result_index.json`
- `indexes/certified_rule_production_authorization_receipt_index.json`

Writes use the project atomic JSON helpers. The controlled-integration result, release-candidate result, integration-authorization result, scoring preview, Fast Lane preview, production descriptor, and committed isolated namespace remain unchanged.

## Eligibility rules

Eligibility revalidates the current active rule and current certification, then independently verifies:

- the Phase 9T controlled integration result is loaded, current, non-stale, and completed;
- pending verification is `verified_pending`;
- committed verification is `verified_committed`;
- rollback status is `not_required`;
- production safety status is `passed`;
- the Phase 9S release candidate is still qualified and fingerprint-aligned;
- the Phase 9R authorization is still current, `authorized`, and uses the exact decision `authorize_for_later_integration`;
- the Phase 9P scoring preview and Phase 9Q Fast Lane preview IDs and fingerprints still match the 9T result;
- the production target descriptor is loaded, read-only, production-scoped, and limited to `later_production_deployment_only`;
- the isolated committed namespace can be read back independently and matches the stored committed-state fingerprint.

If any dependency drifts, the plan/result is treated as blocked or stale and the caller falls back to review rather than mutation.

## Planning and decision persistence

`build_certified_rule_production_authorization_plan(...)` stores a deterministic immutable plan fingerprinted over the current verified evidence set.

`save_certified_rule_production_authorization_decision(...)` requires the exact confirmation string `SAVE_PRODUCTION_AUTHORIZATION`. It revalidates the current evidence set and rechecks the plan fingerprint before writing the immutable result and receipt.

Equivalent reruns are idempotent:

- identical current authorization returns the existing result;
- no new deployment happens;
- no Phase 9T target write happens;
- no new production-side commit is attempted.

## API helpers

- `build_certified_rule_production_authorization_workspace`
- `validate_certified_rule_production_authorization_eligibility`
- `build_certified_rule_production_authorization_plan`
- `save_certified_rule_production_authorization_decision`
- `format_certified_rule_production_authorization_report`

## Desktop controls

The right panel exposes compact controls for:

- Load Production Authorization Workspace
- Validate Production Authorization
- Build Production Authorization Plan
- Save Production Authorization
- Production Authorization Health
- Copy Production Authorization Report

These controls display only public-safe status and reporting fields and do not expose production filesystem paths or raw production state payloads.

## Explicit non-goals

Phase 9U does not implement:

- production deployment execution;
- live adapter invocation;
- production rollback execution;
- activation changes to the controlled integration target;
- direct modification of scoring, Fast Lane, or release-candidate evidence.
