# Phase 13D - Controlled Outcome-Truth Registration Backend Plan API/UI Seam

## 1. Purpose

Phase 13D exposes the deterministic backend plan and its binding validator through a read-only API/UI seam.

## 2. Scope

The seam is read-only, non-executing, and non-persistent.

No plan is persisted.

No registration is executed.

No confirmation is accepted or enforced.

## 3. Backend Functions Exposed

- `build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan`
- `format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report`
- `validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding`
- `format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report`

## 4. API Wrappers

The API exposes narrow wrappers for the four backend functions above.

The wrappers accept only the candidate record set, an untrusted backend plan for binding validation, and optional `root` for test compatibility.

## 5. Desktop Operator Workflow

1. Enter candidate JSON in the existing `Outcome Truth Record JSON` field.
2. Build the controlled registration backend plan.
3. Review fingerprints, status, blockers, warnings, and limitation notes.
4. Validate binding against the current candidate when input changes or equivalence needs to be proven.
5. Copy the public-safe backend-plan report.
6. Copy the public-safe binding report.

## 6. Backend-Plan Build Action

The build action parses candidate JSON, rejects missing or malformed input explicitly, calls the read-only API wrapper, stores the plan in memory only, and surfaces fingerprints plus non-authorization fields.

## 7. Binding Validation Action

The binding action requires a loaded in-memory backend plan and current candidate JSON, validates binding through the read-only API wrapper, and surfaces stale or modified plan states without authorizing execution.

## 8. Candidate Input and Parsing

Phase 13D continues to use the existing `Outcome Truth Record JSON` field.

Missing input blocks with `candidate_record_set_required`.

Malformed JSON blocks with `candidate_record_set_malformed`.

## 9. Stale-State Behavior

Candidate input changes make the displayed plan stale until deterministic binding is validated or the plan is rebuilt.

Stale or modified plans must be rebuilt rather than repaired in place.

## 10. Semantically Equivalent Candidate JSON

UI text changes may mark the current display stale immediately.

Deterministic binding validation is authoritative for candidate equivalence.

Equivalent mappings with different key order can validate successfully and restore current binding state.

## 11. Identity and Fingerprint Display

The desktop surfaces:

- identity schema version
- candidate fingerprint
- planning-gate fingerprint
- backend-plan fingerprint
- binding status

Copied reports preserve full public-safe fingerprint values.

## 12. Structural Readiness Versus Authorization

`backend_plan_ready_for_future_execution` is structural readiness only.

backend_plan_ready_for_future_execution is structural readiness only.

It is not execution authorization.

It is not registration authorization.

Structural readiness is not execution authorization.

Structural readiness is not registration authorization.

## 13. Public-Safe Copy Reports

Plan-copy actions use the backend-plan report formatter.

Binding-copy actions use the binding-report formatter.

No raw backend-plan or binding dictionaries are copied.

## 13A. Explicit Status and Blocker Rendering

Backend/API status codes are rendered explicitly in the desktop seam.

Primary blocker codes remain visible.

Warnings remain distinct from blockers.

Recommended action remains visible.

Stale candidate status is explicit.

Fingerprint mismatches are explicit.

Generic failure text does not replace specific codes.

Stale plans are not copied as current.

Valid binding remains non-authoritative.

Structural readiness remains distinct from authorization.

The current seam explicitly renders these status or blocker codes when applicable:

- `candidate_record_set_required`
- `candidate_record_set_malformed`
- `backend_plan_required`
- `backend_plan_malformed`
- `backend_plan_candidate_input_stale`
- `backend_plan_candidate_fingerprint_mismatch`
- `backend_plan_planning_gate_fingerprint_mismatch`
- `backend_plan_fingerprint_mismatch`
- `backend_plan_identity_field_missing:<field>`
- `backend_plan_identity_field_malformed:<field>`
- `valid`
- `stale`
- `modified`
- `malformed`
- `blocked`

## 14. In-Memory-Only Plan State

The backend plan remains in memory only.

No plan ID is created.

No plan index is created.

No receipt is created.

## 15. Read-Only / No-Execution Boundary

Phase 13D does not register records.

Phase 13D does not persist plans.

Phase 13D does not accept or enforce confirmation.

Phase 13D performs no writes and creates no storage.

## 16. What the API/UI Seam Does Not Prove

A valid fingerprint proves integrity against the defined canonical representation only.

It does not prove factual correctness of outcome-truth records.

It does not prove broad rule effectiveness, production correctness, deployment safety, profitability, prediction quality, future performance, aggregate effectiveness, or ranking quality.

## 17. Exact Test Command

`.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_outcome_truth_controlled_registration_workflow.DeployedRuleOutcomeTruthControlledRegistrationWorkflowPlanningGateTest.test_controlled_outcome_truth_registration_backend_plan_api_ui_seam_preserves_identity_binding_stale_state_and_non_authorization`

## 18. Known Risks

- desktop behavior is source-tested and mixin-tested without a live launch
- candidate input uses the existing Outcome Truth Record JSON field
- canonicalization covers the current candidate schema only
- list ordering remains significant unless schema semantics change
- fixture coverage remains narrow
- no live registration workflow is exercised
- factual truth remains out of scope

## 19. Recommended Next Phase

Phase 13E - Controlled Outcome-Truth Registration Backend Plan API/UI Boundary Audit and Operator Handoff

Boundary audit/operator handoff:
docs/PHASE_13E_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_BOUNDARY_AUDIT_OPERATOR_HANDOFF.md

Final release packet:
docs/PHASE_13F_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_RELEASE_PACKET.md
