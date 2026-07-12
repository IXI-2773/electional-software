# Phase 13C - Controlled Outcome-Truth Registration Backend Plan Identity, Determinism, and Stale-Candidate Gate

## 1. Purpose

Phase 13C adds deterministic identity and binding to the non-executing controlled registration backend plan.

## 2. Scope

This phase remains backend-only, read-only, non-persistent, and non-executing.

It does not register records.

It does not persist plans.

It does not accept or enforce confirmation.

It performs no writes and creates no storage.

## 3. Identity Model

The backend plan now carries explicit identity metadata, a candidate fingerprint, a planning-gate fingerprint, and a backend-plan fingerprint.

## 4. Candidate Canonicalization

Candidate identity uses deterministic canonicalization of mappings by sorted keys, stable JSON hashing, UTF-8 encoding, and preserved list order.

List ordering remains significant unless future schema semantics explicitly define otherwise.

## 5. Candidate Fingerprint

`candidate_fingerprint` uses `sha256:<hex>` over the canonical candidate payload.

Equivalent mapping content with different key insertion order produces the same fingerprint.

## 6. Planning-Gate Fingerprint

`planning_gate_fingerprint` binds the backend plan to the public-safe planning-gate result used to build it.

## 7. Backend-Plan Fingerprint

`backend_plan_fingerprint` binds the stable backend-plan content, including the candidate fingerprint, planning-gate fingerprint, structural readiness, future steps, safeguards, blockers, warnings, and no-overclaim boundary flags.

A valid backend-plan fingerprint proves integrity against the defined canonical representation only.

It does not prove factual correctness of the underlying outcome-truth records.

## 8. Binding Validator

The binding validator recomputes the current candidate fingerprint, planning-gate fingerprint, and expected backend-plan fingerprint, then detects stale candidates, modified plans, missing identity fields, and malformed fingerprint values.

## 9. Stale-Candidate Behavior

Stale or modified plans must be rebuilt rather than repaired in place.

When the current candidate fingerprint changes, the old plan becomes stale and is treated as non-authoritative.

## 10. Plan-Modification Detection

If covered backend-plan fields change after construction, the backend-plan fingerprint no longer matches and integrity validation fails.

## 11. Input-Mutation Protection

The builder performs a candidate-input mutation check and reports whether the caller-provided candidate was mutated during plan construction.

## 12. Structural Readiness Versus Authorization

`backend_plan_ready_for_future_execution` is structural readiness only.

backend_plan_ready_for_future_execution is structural readiness only.

It is not execution authorization.

It is not registration authorization.

## 13. Read-Only / Non-Persistent Boundary

- execution authorized: no
- registration authorized: no
- confirmation accepted: no
- confirmation enforced: no
- backend plan persisted: no
- controlled registration implemented: no
- registration performed: no
- record set written: no
- records repaired: no
- records migrated: no
- `writes_performed = 0`

## 14. Public-Safe Binding Report

The binding report includes only sanitized validity fields, public-safe hashes, blockers, warnings, recommended action, limitation notes, and `writes_performed = 0`.

It excludes raw candidate payloads, raw candidate records, local paths, temp roots, tracebacks, raw telemetry, and full source documents.

## 15. What Fingerprints Do Not Prove

Fingerprints prove deterministic integrity against the defined canonical representation only.

They do not prove factual truth, execution authorization, registration authorization, broad effectiveness, deployment safety, production correctness, profitability, prediction quality, future performance, aggregate effectiveness, or ranking quality.

## 16. Exact Test Command

`.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_outcome_truth_controlled_registration_workflow.DeployedRuleOutcomeTruthControlledRegistrationWorkflowPlanningGateTest.test_controlled_outcome_truth_registration_backend_plan_identity_is_deterministic_candidate_bound_and_stale_safe`

## 17. Known Risks

- canonicalization covers the current candidate schema only
- future schema expansion may require identity-schema version changes
- list ordering remains significant unless existing schema semantics explicitly change
- fixture coverage remains narrow
- no live registration workflow is exercised
- factual truth remains out of scope

## 18. Recommended Next Phase

Phase 13D - Controlled Outcome-Truth Registration Backend Plan API/UI Seam

Final release packet:
docs/PHASE_13F_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_RELEASE_PACKET.md
