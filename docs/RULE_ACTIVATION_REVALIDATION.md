## Rule Activation Revalidation

Phase 9E adds the runtime revalidation layer that follows Phase 9D rule activation.

Purpose:

- load one pending `proposal_rule_activation` revalidation item
- validate the active rule, activation receipt, promoted proposal, promotion receipt, citation evidence, and source revision
- build deterministic positive and negative contract cases from explicit canonical rule fields
- attempt read-only runtime validation only through an existing canonical evaluator
- save explicit review decisions
- either certify later when a canonical evaluator exists or coordinate verified Phase 9D rollback

Canonical evaluator requirement:

- Phase 9E must reuse a safe read-only canonical evaluator
- a second evaluator is prohibited
- if the repository does not expose a safe single-rule evaluator, Phase 9E returns `rule_runtime_evaluator_unavailable`

Current repository reality:

- a canonical mutable rule repository and active-rule index now exist from Phase 9D.1
- no discoverable single-rule canonical evaluator was found through the required targeted symbol search
- Phase 9E therefore supports honest blocked runtime validation plus explicit reject-and-rollback handling
- certification remains blocked until a canonical evaluator exists

Deterministic contract planning:

- plans use only explicit stored condition fields
- no proposal prose parsing
- no AI or semantic inference
- minimum required cases:
  - `positive_match`
  - `negative_nonmatch`
- optional boundary cases are added only for supported deterministic operators

Read-only runtime evaluation:

- persistent state hashes are captured before and after evaluation
- unsupported evaluator outputs are blocked
- exceptions are recorded as blocked or error results
- no scoring, objective-pack, Fast Lane, or historical replay workflow is executed

Review decisions:

- `certify`
- `request_changes`
- `reject_and_rollback`

Rules:

- `request_changes` requires a note
- `reject_and_rollback` requires a note
- decision save performs no completion action
- completion requires explicit confirmation:
  - `CERTIFY`
  - `ROLLBACK`

Rejected activation rollback:

- Phase 9E reuses the existing Phase 9D rollback helper
- it does not create a second rollback engine
- when rollback succeeds, the matching revalidation is resolved as `activation_rolled_back`
- when rollback fails, the revalidation remains unresolved

Certification receipts:

- immutable receipt storage exists for future successful certifications
- no certification receipt is created while runtime validation is blocked by missing canonical evaluator

Matching revalidation resolution:

- only the matching revalidation record is resolved
- unrelated queue items are not touched

Atomic writes and rollback:

- review records use atomic JSON writes
- completion paths restore changed files when later writes fail

Idempotency:

- repeated blocked runtime validations remain non-mutating
- repeated completed rollback returns `already_rolled_back`
- divergent state is blocked rather than repaired automatically

Health checks:

- count pending activation revalidations
- count blocked runtime validations
- count mutation detections
- count missing certification receipts on resolved certified states

Public-safe reporting:

- omits paths
- omits proposal content
- omits citation text
- omits reviewer notes
- omits stack traces and secrets

Remaining deferred work:

- real read-only canonical evaluator integration
- successful certification receipts
- certified revalidation closure
- analytics, backtesting, supersession, and integration work

Targeted testing policy:

- run only `backend/tests/test_rule_activation_revalidation.py`
- use focused temporary controlled fixtures
- do not run the broad project-wide suite in this phase
