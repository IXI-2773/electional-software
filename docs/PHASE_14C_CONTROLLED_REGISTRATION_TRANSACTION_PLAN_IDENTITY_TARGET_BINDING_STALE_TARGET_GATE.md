## 1. Purpose

Phase 14C adds deterministic identity, target binding, and stale-target detection to the Phase 14B transaction plan.

## 2. Scope

This phase is backend-only, read-only, deterministic, non-executing, and non-persistent.

## 3. Phase 14B Prerequisite

Phase 14C assumes the Phase 14B transaction-plan builder and dry run already exist and remain non-authoritative.

## 4. Backend Functions

- `validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding`
- `format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report`

## 5. Transaction-Plan Binding Inputs

The binding validator accepts only the current transaction plan, frozen backend plan, current candidate record set, and optional root. All identity and target-state values are derived internally.

## 6. Target-State Read Policy

Target-state freshness is proven only when a safe non-creating read path is available and the current target-state snapshot matches the snapshot bound into the transaction plan.

## 7. Target-State Snapshot

The target-state snapshot is public-safe structural metadata only. It excludes raw records, paths, timestamps, tracebacks, and source payloads.

## 8. Target-State Snapshot Fingerprint

The snapshot fingerprint is deterministic `sha256` over canonicalized public-safe snapshot content.

## 9. Transaction-Plan Fingerprint Extension

The transaction-plan fingerprint now binds `target_state_at_plan_time`, `target_state_observation_status`, `target_state_observation_available`, and `target_state_snapshot_fingerprint`.

## 10. Candidate and Backend-Plan Binding

Phase 14C revalidates current candidate and frozen backend-plan identity before reporting a valid transaction-plan binding.

## 11. Target-Identity Binding

The current target identity is re-derived internally. Caller target authority is not accepted.

## 12. Idempotency-Preview Consistency

The idempotency preview is recomputed and compared for consistency only. Phase 14C does not enforce idempotency.

## 13. Transaction-Plan Integrity Validation

A valid fingerprint proves integrity against the defined canonical representation only.

It does not prove factual correctness of outcome-truth records.

## 14. Stale-Target Detection

When a safe read-only observation path is available and the current target-state snapshot no longer matches the stored transaction-plan snapshot, the plan is stale and must be rebuilt.

Stale or modified transaction plans must be rebuilt rather than repaired in place.

## 15. Unknown Target-State Behavior

Unknown target state must not be described as current.

Lack of detected staleness is not proof of freshness when target observation is unavailable.

## 16. Target-Conflict Behavior

Conflicting observed target state blocks the transaction-plan binding and the dry run.

## 17. Dry-Run Integration

Phase 14C reuses the transaction-plan binding gate inside the Phase 14B dry run so stale targets, target conflicts, modified plans, and unknown target state fail conservatively.

## 18. Structural Validity Versus Authorization

A valid transaction-plan binding does not authorize execution.

A valid transaction-plan binding does not authorize registration.

## 19. Read-Only / Non-Persistent Boundary

Phase 14C does not call the registration function.

Phase 14C does not accept or enforce confirmation.

Phase 14C does not enforce idempotency.

Phase 14C does not persist target-state snapshots, transaction plans, dry-run results, or receipts.

## 20. Public-Safe Binding Report

The binding report includes only public-safe fingerprints, status fields, blockers, warnings, and limitation notes.

## 21. Explicit Non-Claims

Phase 14C does not authorize registration, does not repair stale plans, does not create transactions, and does not claim factual correctness, broad effectiveness, or scoring authority.

## 22. Exact Test Command

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_outcome_truth_controlled_registration_workflow.DeployedRuleOutcomeTruthControlledRegistrationWorkflowPlanningGateTest.test_controlled_registration_transaction_plan_identity_target_binding_and_stale_target_gate_is_deterministic_read_only_and_non_authoritative
```

## 23. Known Risks

- safe target-state visibility may remain unavailable
- target-state snapshot coverage is structural only
- target-state test coverage may require a patched read-only observation helper
- no idempotency registry exists
- idempotency preview remains unenforced
- no write boundary is exercised
- no ambiguous-outcome recovery is implemented
- no rollback support is claimed
- candidate, target, and target-state canonicalization remain schema-sensitive
- fixture coverage remains narrow
- factual truth remains out of scope
- broad regression coverage remains unclaimed

## 24. Recommended Next Phase

Phase 14D - Controlled Registration Transaction-Plan Identity/Binding and Dry-Run API/UI Seam

The transaction plan and dry run should be exposed only after transaction-plan integrity, target binding, target-state freshness handling, and stale-target detection are frozen.

Narrow target-state observation follow-up:
docs/PHASE_14C_1_NARROW_TRANSACTION_PLAN_TARGET_STATE_OBSERVATION_BINDING_FOLLOW_UP.md
