# Fast Lane Compatibility Foundation

Phase 9Q.0 adds a machine-readable Fast Lane contract manifest and a pure read-only compatibility evaluator. It does not execute Fast Lane and it does not authorize activation.

## Purpose

- expose the authoritative Fast Lane backend contract in machine-readable form
- compare one active certified canonical rule against that contract
- detect exact compatibility, incompatibility, and semantic loss
- provide stable capability, evaluator, and result fingerprints

## Compatibility Versus Execution

This foundation is compatibility-only.

- Fast Lane execution is not invoked.
- No production state is written.
- Compatibility does not authorize activation or deployment.

## Authoritative Contract Source

The authoritative Fast Lane contract comes from the real backend report builder in:

- `backend/electional/analysis/fast_lane.py`

The manifest is grounded in the dataclass inputs and output fields that `build_fast_lane_report(...)` actually consumes and emits.

## Capability Manifest

The manifest declares:

- contract ID and version
- accepted tactical input schema versions
- supported canonical rule schema version
- supported condition operators
- supported exact input fields
- supported field families
- supported action type
- supported result type
- required provenance fields
- value types by field
- active-rule requirement
- certification requirement
- read-only support
- determinism

## Fingerprints

- `get_fast_lane_capability_fingerprint(...)` hashes only compatibility semantics from the manifest.
- `get_fast_lane_compatibility_evaluator_fingerprint()` hashes the evaluator rules, dimension order, and overall-status logic.

No timestamps, paths, or runtime state are included in deterministic fingerprints.

## Compatibility Inputs

The evaluator requires:

- one canonical rule
- one certification receipt/record
- one source-context record
- one Fast Lane capability manifest

Required provenance includes canonical rule ID, document ID, source revision, rule fingerprint, certification identity, and certification fingerprint.

## Compatibility Dimensions

The evaluator reports these dimensions independently:

1. lifecycle
2. provenance
3. rule schema
4. condition structure
5. condition operators
6. input fields
7. value types
8. action or output type
9. determinism
10. read-only support

## Exact Matching Rules

- operators are matched exactly
- input fields are matched exactly
- unsupported fields are not renamed or approximated
- unsupported operators are not translated
- unsupported actions are not invented

## Value-Type Compatibility

The evaluator checks explicit value types per field.

- boolean is distinct from integer and number
- string and timestamp are checked explicitly
- list and enum-like fields are handled only when declared by the manifest

## Action Compatibility

This foundation checks canonical action compatibility against the actual Fast Lane output contract. It does not synthesize action mappings from labels or descriptions.

## Semantic Loss

Semantic loss is reported when compatibility would require:

- dropping a condition
- flattening nested logic
- changing operators
- renaming unsupported fields
- coercing unsupported value types
- inventing or weakening action behavior

Confirmed semantic loss prevents `compatible` status.

## Overall Statuses

- `compatible`
- `compatible_with_warnings`
- `partially_compatible`
- `incompatible`
- `blocked`
- `unknown`

## Read-Only Guarantees

The evaluator is pure and read-only. It does not mutate:

- canonical rules
- certifications
- source context
- Fast Lane manifest data
- Fast Lane state
- scoring
- objective results
- production outputs

## Reporting

The public-safe compatibility report includes:

- rule identity
- document and source revision
- certification status
- Fast Lane contract identity
- dimension statuses
- supported and unsupported operators
- supported and unsupported fields
- supported and unsupported actions
- semantic-loss status
- blockers and warnings
- recommended next action

It omits full rule payloads, paths, stack traces, and secrets.

## Relationship to Phase 9Q

Phase 9Q.0 only establishes the contract and evaluator foundation that a later Phase 9Q preview can consume. It does not build Phase 9Q plans, results, or receipts.
