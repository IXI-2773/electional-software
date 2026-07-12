## 1. Purpose

Phase 15C validates deterministic binding between the current candidate, backend plan, transaction plan, target state, dry-run evidence, authorization preview, confirmation policy, and confirmation evidence.

## 2. Scope

Phase 15C is backend-only, read-only, deterministic, non-persistent, and non-authoritative.

## 3. Phase 15B Prerequisite

Phase 15C treats supplied previews and confirmation dry-run results as untrusted.

## 4. Backend Functions

- `validate_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding`
- `format_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding_report`

## 5. Binding-Gate Inputs

The binding gate accepts an authorization preview, confirmation dry-run result, confirmation text, transaction plan, backend plan, and candidate record set only as untrusted inputs.

## 6. Input Validation

Missing or malformed preview, confirmation result, transaction plan, backend plan, or candidate input blocks validation. Empty confirmation text is valid missing-confirmation input. Non-string confirmation text is malformed.

## 7. Expected Preview Reconstruction

Phase 15C rebuilds the expected authorization preview from the current candidate, backend plan, transaction plan, and current root.

## 8. Authorization-Preview Integrity

Modified previews fail integrity validation. A valid fingerprint proves integrity against the defined canonical representation only.

## 9. Current Identity Rebinding

Phase 15C rebinds candidate, planning-gate, backend-plan, transaction-plan, target-identity, target-state snapshot, dry-run evidence, and idempotency-preview identity.

## 10. Authorization-Scope Binding

The authorization scope is rebound and must preserve one-attempt, single-use, non-repair, non-migration, non-scoring, and non-rollback behavior.

## 11. Confirmation-Policy Binding

The required phrase remains `REGISTER_OUTCOME_TRUTH_RECORD_SET` and the confirmation policy remains exact literal, case-sensitive, no trimming, no normalization, no substring matching, and no implicit confirmation.

## 12. Dry-Run Evidence Binding

Phase 15C recomputes dry-run evidence and requires it to match the current preview contract.

## 13. Confirmation Dry-Run Integrity

The supplied confirmation dry-run result is rebuilt and validated as untrusted evidence.

## 14. Confirmation-Evidence Binding

Confirmation evidence is recomputed from current stable evidence and the supplied confirmation text's match outcome.

## 15. Modified Preview Behavior

Modified previews fail integrity validation and are not repaired in place.

## 16. Stale Preview Behavior

Stale previews may remain internally intact but no longer match current prerequisites. Modified and stale previews are not repaired in place.

## 17. Unknown, Stale-Target, and Conflict Behavior

An exact confirmation match cannot override a stale, modified, conflicting, unknown, or otherwise blocked prerequisite state.

## 18. Status Precedence

Stronger stale, modified, conflict, and unknown-target blockers remain conservative and take precedence over confirmation-match outcomes.

## 19. Valid Binding Versus Authorization

A valid authorization-preview binding does not create an authorization artifact. A valid authorization-preview binding does not grant execution authorization. A valid authorization-preview binding does not grant registration authorization. Confirmation remains unaccepted and unenforced.

## 20. Read-Only / Non-Persistent Boundary

The raw confirmation text is not persisted, echoed, returned, or included in public-safe reports. Idempotency remains unenforced. Phase 15C does not call the registration function. Phase 15C performs zero writes.

## 21. Public-Safe Report Limits

Reports exclude raw confirmation text, raw candidate payloads, raw plan dictionaries, raw target records, local paths, temp paths, and tracebacks.

## 22. Explicit Non-Claims

It does not prove factual correctness of outcome-truth records. Phase 15C does not grant authority, execute registration, persist authorization state, enforce idempotency, or claim rollback support.

## 23. Exact Test Command

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_outcome_truth_controlled_registration_workflow.DeployedRuleOutcomeTruthControlledRegistrationWorkflowPlanningGateTest.test_controlled_registration_authorization_preview_identity_confirmation_evidence_binding_and_stale_preview_gate_is_deterministic_read_only_and_non_authoritative
```

## 24. Known Risks

- binding gate remains non-authoritative
- authorization preview remains unpersisted
- no authorization artifact or registry exists
- no accepted-confirmation mechanism exists
- no authoritative idempotency registry exists
- no authorization-consumption mechanism exists
- no registration write boundary is exercised
- no ambiguous-outcome recovery exists
- no rollback support is claimed
- preview/evidence canonicalization remains schema-sensitive
- fixture coverage remains narrow
- factual truth remains out of scope
- broad regression coverage remains unclaimed

## 25. Recommended Next Phase

Phase 15D - Controlled Registration Authorization Preview, Confirmation Dry Run, and Evidence-Binding API/UI Seam.
