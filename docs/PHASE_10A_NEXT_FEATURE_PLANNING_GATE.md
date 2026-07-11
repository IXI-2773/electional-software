# Phase 10A Next Feature Planning Gate

## Frozen Phase 9Z Summary

The persisted scoring-result feature is frozen as a persisted scoped accuracy-like exact-match scoring result.

Frozen surface:

- backend persisted scoring-result planning
- backend persisted scoring-result recording
- exact confirmation-gated recording
- immutable result, receipt, and index persistence
- fingerprint, receipt, and corruption validation
- read-only load, health, and report paths
- read-only summary surface
- API wrappers for read-only and controlled-write actions
- desktop section for controlled plan or record and read-only inspection
- focused boundary tests
- final release handoff notes

Frozen authority scope:

- `registered_outcome_truth_exact_match_accuracy_like`

Allowed scoped persisted fields:

- `persisted_accuracy_like_score_ratio`
- `persisted_accuracy_like_score_percentage`
- `exact_match_count`
- `mismatch_count`
- `denominator_count`
- `eligible_record_count`
- `excluded_record_count`
- `duplicate_collapsed_count`
- `conflict_count`

Verified boundaries remain:

- no broad rule-effectiveness claim
- no deployment-safety claim
- no broad production-correctness claim
- no profitability claim
- no prediction-quality claim
- no aggregate effectiveness
- no ranking or comparison
- no new metric family
- no caller-supplied score authority

## Known Risks

- Broad regression coverage remains intentionally unclaimed because only focused exact-node validation was run by policy.
- Prerequisite modules outside the persisted scoring-result path may still create storage eagerly in their own read paths.
- The persisted scoring-result feature now guards its own read-only path against one hidden-write case, but upstream prerequisite read paths are not yet fully audited.

## Candidate Next Feature Tracks

### Option A — Preflight Release Health for Prerequisite Read Paths

Purpose:

- audit one or two prerequisite modules for read-only paths that still create storage
- reduce release risk before expanding scoring or reporting

Pros:

- addresses the clearest known post-freeze risk
- narrow and safety-oriented
- focused testability is good
- minimal product-surface ambiguity

Risks:

- can sprawl into prerequisite-module redesign if not tightly scoped

Verdict:

- recommended

### Option B — Operator Workflow Polish for Persisted Scoring Result

Purpose:

- improve plan to record to load to summary flow
- refine blocked and corrupt-state messaging

Pros:

- helpful for operators using the current desktop surface
- low semantic risk

Risks:

- lower safety value than closing known hidden-write risk
- easier to drift into cosmetic work before foundational risk is closed

Verdict:

- rejected for immediate next step because known read-path write risk is more important

### Option C — Outcome-Truth Record Management QA

Purpose:

- inspect outcome-truth ingestion quality and duplicate handling

Pros:

- upstream evidence quality matters

Risks:

- can reopen earlier frozen phases
- likely broader than the currently known persisted scoring-result risk

Verdict:

- rejected for immediate next step because it is less directly tied to the frozen feature’s known release risk

### Option D — Reporting/Export Pack for Persisted Scoring Result

Purpose:

- add read-only export convenience for persisted scoring results

Pros:

- operator-facing value
- focused testing is feasible

Risks:

- cosmetic before safety closure
- may tempt aggregate scoring or ranking expansion

Verdict:

- rejected for immediate next step because release safety outranks export convenience

### Option E — New Metric Family Design

Purpose:

- expand scoring beyond the frozen exact-match accuracy-like scope

Pros:

- potential future utility

Risks:

- premature after freeze
- high semantic and contract risk
- would expand authority and scoring boundaries too early

Verdict:

- explicitly rejected as the immediate next step

## Recommended Next Track

Selected option:

- Option A

Recommended Phase 10B title:

- `Phase 10B — Prerequisite Read-Path No-Write Audit`

Reason:

- It addresses the clearest known frozen risk with the narrowest and safest next scope.
- It improves release stability without broadening persisted scoring authority or introducing new scoring logic.
- It is more foundational than UI polish and safer than beginning a new metric family.

## Phase 10B Implementation Scope

Objective:

- audit one or two prerequisite modules used by the persisted scoring-result feature for hidden writes on read-only paths, and fix only narrow proven read-path storage creation defects.

Files to inspect:

- `backend/electional/deployed_rule_effectiveness_scoring_contract.py`
- `backend/electional/deployed_rule_outcome_truth_source.py`
- `backend/electional/deployed_rule_effectiveness_scoring_result.py`
- `backend/tests/test_deployed_rule_effectiveness_scoring_result.py`

Optional narrow lookup only if required:

- `backend/electional/deployed_rule_effectiveness_evaluation_spec.py`
- `backend/electional/deployed_rule_effectiveness_readiness.py`

Allowed changes:

- narrow read-path no-write guards
- narrow helper checks before delegating to eager prerequisite loaders
- one focused regression test proving no-write behavior for the selected prerequisite module path
- concise docs clarification if behavior changes

## Phase 10B Non-Goals

- no new scoring family
- no new score calculation
- no aggregate effectiveness
- no ranking or comparison
- no operator workflow redesign
- no desktop launch or broad UI polish
- no broad prerequisite-module redesign
- no “fix all read paths” mandate
- no broad project-wide test suite

## Phase 10B Acceptance Criteria

- at least one prerequisite read-only path used by persisted scoring-result flow is proven not to create storage on missing-data reads
- any narrow fix is limited to read-only no-write safety
- persisted scoring-result authority remains scoped to `registered_outcome_truth_exact_match_accuracy_like`
- no new score family is added
- no aggregate effectiveness, ranking, or comparison is added
- focused exact-node validation passes
- broad regression coverage remains explicitly unclaimed

## Phase 10B Focused Test Strategy

Focused test node:

- `test_phase_10b_prerequisite_read_path_no_write_audit_preserves_scoring_result_boundaries`

Validation commands:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_effectiveness_scoring_result.DeployedRuleEffectivenessScoringResultTest.test_phase_10b_prerequisite_read_path_no_write_audit_preserves_scoring_result_boundaries
```

If Python files change:

```powershell
.\.venv\Scripts\python.exe -m py_compile <changed-python-files>
```

Then:

```powershell
git diff --check -- <changed-files>
```

## Release Safety Notes

- Do not treat persisted scoring-result freeze as proof of broad rule effectiveness.
- Do not recommend new metric-family work before prerequisite read-path no-write risks are narrowed.
- Do not propose aggregate effectiveness, ranking, or comparison in Phase 10B.
- Do not claim broad regression coverage from the focused 9Z validation history.
