Phase 9S adds a qualification-only release-candidate evaluator for one authorized certified-rule evidence package.

Implemented behavior:

- Storage:
  - `certified_rule_release_candidate_plans/`
  - `certified_rule_release_candidate_results/`
  - `certified_rule_release_candidate_receipts/`
  - matching indexes under `indexes/`
- Inputs:
  - one `canonical_rule_id`
  - one Phase 9R `integration_authorization_result_id`
  - bound 9P and 9Q evidence is read from the selected authorization
- Validation:
  - current active rule required
  - current completed certification required
  - current document/source revision required
  - no pending rollback
  - no pending supersession
  - no unresolved critical remediation
  - current immutable Phase 9R authorization result and receipt required
  - bound Phase 9P result/receipt must remain current and complete
  - bound Phase 9Q result/receipt must remain current and compatible with semantic loss `none`
- Gates:
  - fixed ordered gate results are persisted with status, evidence summary, blockers, and warnings
- Outputs:
  - deterministic qualification plan
  - immutable qualification result
  - immutable receipt
  - evidence digest with safe authorization, scoring, and Fast Lane summaries
- Idempotency:
  - identical rerun returns `already_qualified` with zero writes
- Safety:
  - no activation
  - no Fast Lane execution
  - no production scoring
  - no mutation of 9P, 9Q, or 9R evidence
- API helpers:
  - `build_certified_rule_release_candidate_workspace`
  - `validate_certified_rule_release_candidate_eligibility`
  - `build_certified_rule_release_candidate_plan`
  - `qualify_certified_rule_release_candidate`
  - `format_certified_rule_release_candidate_report`
- Desktop UI:
  - Load Release Candidate Workspace
  - Validate Release Candidate
  - Build Release Plan
  - Qualify Release Candidate
  - Copy Release Report

Deferred:

- controlled integration execution
- activation or deployment
- rule promotion or rollback execution
- batch or cross-document qualification
