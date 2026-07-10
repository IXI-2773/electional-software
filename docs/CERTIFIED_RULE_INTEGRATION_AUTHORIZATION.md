Phase 9R adds a human-reviewed integration authorization gate over one current Phase 9P scoring preview and one current Phase 9Q Fast Lane preview.

Implemented behavior:

- Storage:
  - `certified_rule_integration_authorization_plans/`
  - `certified_rule_integration_authorization_results/`
  - `certified_rule_integration_authorization_receipts/`
  - matching index files under `indexes/`
- Evidence validation:
  - current active canonical rule required
  - current completed certification required
  - current document/source revision required
  - exact matching 9P scoring preview result and receipt required
  - exact matching 9Q Fast Lane preview result and receipt required
  - pending supersession and unresolved critical remediation block review
- Plan:
  - deterministic plan fingerprint over rule, certification, scoring-preview, and fast-lane-preview provenance
- Decision contract:
  - `authorize_for_later_integration`
  - `reject_integration`
  - `defer_integration`
  - reviewer identity required
  - rationale required
  - acknowledgements required
  - authorization requires explicit read-only acknowledgements and compatible Fast Lane evidence without confirmed semantic loss
- Persistence:
  - one immutable result per current plan
  - identical resubmission returns zero writes
  - divergent resubmission against an already-recorded current result is blocked
- Safety:
  - no scoring writes
  - no Fast Lane execution
  - no rule activation or production mutation
- Staleness:
  - result becomes stale when current rule, certification, source revision, or referenced 9P/9Q fingerprints change
- API helpers:
  - `build_certified_rule_integration_authorization_workspace`
  - `validate_certified_rule_integration_authorization_eligibility`
  - `build_certified_rule_integration_authorization_plan`
  - `save_certified_rule_integration_authorization_decision`
  - `format_certified_rule_integration_authorization_report`
- Desktop UI:
  - Load Authorization Workspace
  - Validate Authorization Eligibility
  - Build Authorization Plan
  - Save Authorization Decision
  - Copy Authorization Report

Deferred:

- production activation
- Fast Lane execution
- automatic authorization
- score-based automatic decisioning
- batch or cross-document authorization
