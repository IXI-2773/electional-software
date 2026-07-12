## 1. Purpose

Phase 14C.1 hardens the read-only target-state observation boundary used by transaction-plan construction, binding validation, and dry run.

## 2. Scope

This phase is backend-only, read-only, deterministic, and non-persistent. It does not expose API/UI seams or execute registration.

## 3. Phase 14C Risk Addressed

The remaining Phase 14C risk was narrow: unavailable roots, malformed target storage, and natural observer-path semantics needed to stay distinct from confirmed target absence.

## 4. Production Target-State Observer

The production observer remains the shared private helper used by transaction-plan construction and by the Phase 14C binding validator through the target-state snapshot builder.

## 5. Safe Read-Path Audit

The observer uses only safe non-creating reads and does not call registration, directory creation, write helpers, or persistence helpers.

## 6. Root and Observation Semantics

A missing or unavailable root is not automatically confirmed target absence.

## 7. Confirmed Target Absence

Target absence is confirmed only when a safe read-only lookup establishes that the exact target is not present.

## 8. Present Equivalent Target

Equivalent target classification remains limited to stable structural identity and does not claim factual correctness.

## 9. Present Conflicting Target

Conflicting target state remains blocking and invalidates the transaction-plan binding and dry run.

## 10. Unknown, Unreadable, and Malformed Target States

Unknown target state is not current target state.

Matching unknown-state snapshots do not prove target freshness.

Observation errors and malformed target data are not treated as absence.

## 11. Observation Basis

The snapshot includes a deterministic public-safe observation basis such as `root_unavailable`, `safe_direct_target_file_read`, `safe_existing_root_target_lookup`, `target_unreadable`, or `target_malformed`.

## 12. Snapshot Determinism

Snapshot identity excludes paths, timestamps, temporary-root names, and random values. Material observed state changes change the snapshot fingerprint.

## 13. Binding-Validator Propagation

The binding validator reuses the same observer path and only proves freshness when the target state is safely observed and matches the plan-bound snapshot.

## 14. Dry-Run Propagation

Dry run continues to rely on the transaction-plan binding validator and fails conservatively for unknown, stale, or conflicting target state.

## 15. Natural-Path Test Coverage

The focused test exercises unavailable-root, confirmed-absent, malformed-target, equivalent-target, conflicting-target, and material-state-change cases through the production observer path wherever practical.

## 16. No-Write Filesystem Evidence

Production target-state observation creates no files or directories and performs no writes.

Fixture setup writes are isolated from the audited production calls.

## 17. Structural Validity Versus Authorization

A valid target-state binding does not authorize execution.

A valid target-state binding does not authorize registration.

## 18. Public-Safe Limits

Snapshots and reports exclude absolute paths, temporary paths, raw target records, raw candidate records, tracebacks, and local storage roots.

## 19. Explicit Non-Claims

Phase 14C.1 does not call the registration function.

Phase 14C.1 does not accept or enforce confirmation.

Phase 14C.1 does not enforce idempotency.

A structural target comparison does not prove factual correctness of outcome-truth records.

## 20. Exact Test Command

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_outcome_truth_controlled_registration_workflow.DeployedRuleOutcomeTruthControlledRegistrationWorkflowPlanningGateTest.test_controlled_registration_target_state_observer_distinguishes_unknown_absent_present_and_changed_without_writes
```

## 21. Known Risks

- target-state visibility may remain unavailable for unsupported roots
- storage-schema changes may require observer updates
- equivalent-content classification remains limited to stable structural identity
- fixture coverage remains narrow
- no write boundary is exercised
- no idempotency registry exists
- no ambiguous-outcome recovery exists
- no rollback support is claimed
- factual truth remains out of scope
- broad regression coverage remains unclaimed

## 22. Recommended Next Phase

Phase 14D - Controlled Registration Transaction-Plan Identity/Binding and Dry-Run API/UI Seam

Once the natural target-state observer distinguishes unavailable, absent, present, conflicting, and changed states without writes, the transaction-plan and dry-run seam can be exposed safely.
