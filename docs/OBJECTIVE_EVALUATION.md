# Objective Evaluation

Phase 9O.1 adds a pure, read-only evaluator for explicit evaluable objective packs defined by Phase 9O.1A.

Implemented public functions:

- `validate_objective_evaluation_input(...)`
- `evaluate_objective(...)`
- `evaluate_objective_pack(...)`
- `get_objective_evaluator_fingerprint(...)`

Controlled input contract:

```json
{
  "schema_version": "objective_evaluation_input_v1",
  "record_id": "record_001",
  "timestamp": "2026-01-01T00:00:00Z",
  "values": {
    "moon_altitude": 25.5,
    "is_combust": false,
    "applying_aspect": "trine"
  }
}
```

Behavior:

- Requires an evaluable objective pack.
- Rejects metadata-only packs with `objective_pack_not_evaluable`.
- Validates input schema, record identity, values mapping, and optional timestamp shape.
- Evaluates objectives in declared list order.
- Does not infer missing fields.
- Does not coerce incompatible types.
- Supports only the Phase 9O.1A value types, operators, and success semantics.

Objective statuses:

- `satisfied`
- `not_satisfied`
- `unsupported_missing_field`
- `unsupported_invalid_type`
- `unsupported_operator`
- `invalid_objective`
- `evaluator_error`

Pack aggregate statuses:

- `completed`
- `completed_with_unsupported_objectives`
- `no_evaluable_objectives`
- `blocked`
- `evaluator_failed`

Supported operators:

- `equals`
- `not_equals`
- `greater_than`
- `greater_than_or_equal`
- `less_than`
- `less_than_or_equal`
- `in`
- `not_in`
- `exists`
- `not_exists`
- `between`

Success semantics:

- `condition_met`
- `condition_not_met`

Determinism:

- Evaluator fingerprint is stable for identical evaluator semantics.
- Pack result fingerprint is stable for identical pack semantics, input semantics, ordered objective results, and aggregate counts.
- Execution timestamps are not used in evaluator or result fingerprints.

Read-only guarantees:

- No files are written.
- No objective packs are mutated.
- No controlled inputs are mutated.
- No scoring, Fast Lane, rule state, or production output is modified.

This phase does not implement:

- rule-to-objective mapping
- baseline-versus-rule comparison
- preview plans, receipts, or persistence
- scoring
- API or desktop UI integration

Focused-test limitation:

- Validation was limited to in-memory objective-pack fixtures and the targeted evaluator test file only.
