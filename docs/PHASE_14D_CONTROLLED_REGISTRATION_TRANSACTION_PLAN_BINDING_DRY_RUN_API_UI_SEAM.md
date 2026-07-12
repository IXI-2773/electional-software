## 1. Purpose

Phase 14D exposes the deterministic transaction plan, transaction-plan binding validator, and transaction dry run through a read-only API/UI seam.

## 2. Scope

This phase is read-only, non-executing, non-persistent, in-memory only, no-registration, no-confirmation input, no-confirmation acceptance, no-confirmation enforcement, no-execution authorization, no-registration authorization, no-idempotency enforcement, no-target-state override, no-repair, no-migration, no-scoring, and no factual-truth claim.

## 3. Phase 14C.1 Prerequisite

Phase 14C.1 remains the target-state observation prerequisite. Unknown target state is not current target state. A missing or unavailable root is not confirmed target absence. Matching unknown-state snapshots do not prove target freshness.

## 4. Backend Functions Exposed

- `build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan`
- `format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report`
- `validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding`
- `format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report`
- `run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run`
- `format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report`

## 5. API Wrappers

Phase 14D adds six narrow read-only API wrappers with candidate input, current Phase 13 backend plan, current transaction plan, and optional `root` only. No caller fingerprint authority is accepted. No caller target-state authority is accepted. No caller idempotency authority is accepted. Phase 14D does not accept or enforce confirmation.

## 6. Desktop Section

The desktop adds a compact `Controlled Registration Transaction Plan` subsection beside the existing controlled-registration backend-plan seam.

## 7. Build Transaction-Plan Workflow

The desktop reuses the current `Outcome Truth Record JSON` candidate input and the current in-memory Phase 13 backend plan, builds one deterministic transaction-plan preview, stores it in memory only, clears older binding and dry-run state, and renders transaction-plan identity, target-state observation, blockers, warnings, and limitations.

## 8. Validate Transaction-Plan Binding Workflow

Binding validation reuses the current candidate, current backend plan, and current in-memory transaction plan. A valid transaction-plan binding does not authorize execution. A valid transaction-plan binding does not authorize registration.

## 9. Run Transaction Dry-Run Workflow

The dry run revalidates transaction binding through the frozen backend path and surfaces current target-state freshness, stale-target blocking, target-conflict blocking, idempotency-preview consistency, `planned_write_count = 1`, and `writes_performed = 0`. A passing dry run does not authorize execution. A passing dry run does not authorize registration.

## 10. In-Memory State

Transaction plans, binding results, target-state snapshots, dry-run results, idempotency previews, and receipts remain unpersisted.

## 11. Candidate and Backend-Plan Stale-State Handling

Candidate edits mark the in-memory transaction plan, transaction-plan binding result, and dry-run result stale. Backend-plan replacement clears transaction-plan, binding, and dry-run state so old derived state is not treated as current.

## 12. Target-State Observation Display

The seam surfaces candidate fingerprint, backend-plan fingerprint, target-identity fingerprint, target-state snapshot fingerprint, transaction-plan fingerprint, target-state observation status, target-state observation basis, target-state freshness status, target-state freshness proven, stale-target detection, target-state change detection, and target-conflict detection.

## 13. Unknown Target-State Behavior

Unknown target state is not current target state. Matching unknown-state snapshots do not prove target freshness.

## 14. Confirmed-Absent Target Behavior

A missing or unavailable root is not confirmed target absence. Confirmed absence requires the safe observer basis established in Phase 14C.1.

## 15. Present Equivalent and Conflicting Target Behavior

Present equivalent target state remains non-authoritative readback only. Conflicting target state remains blocking.

## 16. Equivalent Candidate JSON Revalidation

Equivalent candidate JSON can revalidate after rebuilding the backend plan and transaction plan from the current candidate representation.

## 17. Transaction-Plan Identity Display

The desktop shows candidate fingerprint, backend-plan fingerprint, target-identity fingerprint, target-state snapshot fingerprint, and transaction-plan fingerprint without recomputing or editing them in UI code.

## 18. Idempotency Preview Display

The idempotency-key preview is non-authoritative and unenforced.

## 19. Structural Readiness and Dry Run Versus Authorization

`transaction_plan_ready` is structural readiness only. `dry_run_passed` is a read-only modeled pass only. planned_write_count = 1 is future intent only. writes_performed = 0 is actual Phase 14D behavior.

## 20. Public-Safe Copy Reports

The desktop copy actions call the formatter-backed API wrappers only. Raw transaction plans, raw candidate JSON, raw target records, absolute paths, and tracebacks are not copied.

## 21. Missing and Malformed Input Statuses

The seam preserves explicit statuses for `candidate_record_set_required`, `candidate_record_set_malformed`, `backend_plan_required`, `backend_plan_malformed`, `transaction_plan_required`, and `transaction_plan_malformed`.

## 22. Read-Only / Non-Persistent Boundary

Phase 14D does not call the registration function. Phase 14D does not accept or enforce confirmation. No transaction plan, binding result, target-state snapshot, dry-run result, idempotency preview, plan ID, transaction ID, receipt, directory, or file is persisted by this seam.

## 23. Forbidden Controls

No register, execute, commit, confirm, authorize, approve, auto-register, force-register, persist-transaction, reserve-idempotency, create-receipt, repair, migrate, override, score, ranking, or aggregate controls are added.

## 24. Explicit Non-Claims

A valid fingerprint proves integrity against the defined canonical representation only. It does not prove factual correctness of outcome-truth records.

## 25. Exact Test Command

`.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_outcome_truth_controlled_registration_workflow.DeployedRuleOutcomeTruthControlledRegistrationWorkflowPlanningGateTest.test_controlled_registration_transaction_plan_binding_and_dry_run_api_ui_seam_preserves_target_freshness_and_non_authorization`

## 26. Known Risks

- desktop behavior remains source-tested/mixin-tested without live launch
- candidate input reuses Outcome Truth Record JSON
- transaction-plan state depends on the existing in-memory Phase 13 backend plan
- target-state visibility may remain unavailable for unsupported roots
- storage-schema changes may require observer updates
- equivalent-content classification remains structural
- idempotency preview remains unenforced
- no write boundary is exercised
- no transaction or receipt registry exists
- no ambiguous-outcome recovery exists
- no rollback support is claimed
- fixture coverage remains narrow
- factual truth remains out of scope
- broad regression coverage remains unclaimed

## 27. Recommended Next Phase

Phase 14E - Controlled Registration Transaction-Plan/Dry-Run API/UI Boundary Audit and Operator Handoff

Reason: the new API/UI seam should receive a focused stale-state, target-state, copy-report, in-memory, and non-authorization audit before any final freeze or execution-contract work.
