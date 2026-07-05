## Proposal Rule Activation

Phase 9D adds the controlled review layer for converting a Phase 9C promoted proposal into a canonical rule candidate.

Repository reality:

- promoted proposals can be validated for explicit structured rule mapping
- free-form proposal interpretation remains prohibited
- the current repository does not expose a mutable canonical persisted rule store or active-rule index
- Phase 9D therefore blocks activation with `rule_activation_storage_unavailable` instead of inventing a parallel rule repository

Structured rule-mapping requirement:

- proposals must already contain explicit `rule_mapping` fields
- required fields:
  - rule type
  - target
  - scope
  - condition
  - operator
  - value
  - priority when present
  - enabled intent

Why free-form proposal interpretation is prohibited:

- no AI interpretation
- no regex guessing from prose
- no semantic inference
- no topic-similarity-based conversion

Current behavior implemented in Phase 9D:

- load one promoted proposal into a rule-activation workspace
- validate promotion provenance, accepted citation evidence, source revision, and explicit rule mapping
- validate a candidate against a narrow canonical field contract
- analyze duplicate/conflict state against canonical storage availability
- save approve, reject, or request-changes review decisions
- require explicit `ACTIVATE` confirmation for activation attempts
- require explicit `ROLLBACK` confirmation for rollback attempts
- block activation and rollback when canonical mutable rule storage is unavailable
- provide health and public-safe reporting

Canonical rule-schema validation:

- supported rule type
- target
- scope
- operator
- priority range
- enabled field

Exact duplicate detection:

- implemented only through the canonical-rule-analysis path
- currently blocked by absent mutable canonical rule storage

Inactive equivalent handling:

- review support is present in the decision layer
- actual inactive-equivalent rule comparison remains blocked until canonical mutable rule storage exists

Conflict handling:

- noncritical conflict acknowledgement field is supported
- critical conflict blocking field is supported
- actual persisted active-rule conflict checks remain blocked by missing canonical mutable rule storage

Review decisions:

- `approve`
- `reject`
- `request_changes`

Rules:

- reject requires a reviewer note
- request changes requires a reviewer note
- approval performs no activation

Add-only activation policy:

- no in-place editing of an existing active rule
- no automatic replacement or supersession
- no rewriting Python source files

Atomic writes and rollback:

- review records use atomic JSON writes
- activation and rollback remain blocked before any canonical rule mutation because writable canonical rule storage is unavailable

Activation receipts:

- storage directories and index support are present for future canonical activation
- no receipts are created while activation is blocked by unavailable canonical storage

Rule-integration revalidation:

- remains deferred until a canonical mutable rule activation path exists

Idempotency:

- repeated blocked activation attempts remain non-mutating

Verified rollback behavior:

- rollback requires exact `ROLLBACK`
- rollback is blocked when no activation receipt exists

Activation health:

- reports repository-level activation-storage unavailability
- counts pending reviews and promoted proposals waiting on a canonical mutable rule store

Public-safe reporting:

- omits paths
- omits proposal content
- omits citation text
- omits reviewer notes
- omits stack traces and secrets

Remaining supersession and analytics work:

- existing-rule supersession
- in-place rule editing
- rule version chains
- activation analytics
- historical performance validation

Targeted testing policy:

- run only `backend/tests/test_proposal_rule_activation.py`
- use focused temporary controlled fixtures
- do not run the broad project-wide suite in this phase
