# Evaluable Objective Pack Schema

Phase 9O.1A extends the existing metadata-only objective-pack format so a pack can explicitly declare deterministic evaluation semantics without changing current action-moment behavior.

Backward compatibility:

- Existing packs without an `objectives` field remain valid.
- Existing metadata-only packs continue to load and save unchanged.
- Existing action-moment and Fast Lane text behavior is unchanged.
- Metadata-only packs are classified as `metadata_only`, not evaluable.

Capability classification:

- `metadata_only`: no `objectives` field, or an empty `objectives` list
- `evaluable`: one or more fully valid objective definitions
- `invalid`: malformed objective definitions or incompatible evaluation semantics

Objectives collection:

- Optional top-level `objectives`
- Must be an ordered list
- List order is the deterministic evaluation order

Required objective-definition fields:

- `objective_id`
- `input_field`
- `value_type`
- `operator`
- `success_semantics`

`expected_value` is required except for `exists` and `not_exists`.

Optional metadata:

- `label`
- `description`
- `required`
- `enum_values`

Supported value types:

- `boolean`
- `integer`
- `number`
- `string`
- `enum`
- `timestamp`

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

Supported success semantics:

- `condition_met`
- `condition_not_met`

Validation behavior:

- Duplicate `objective_id` values are rejected.
- `input_field` must be an explicit simple field name.
- Unknown operators and unsupported value types are rejected.
- Operator and value-type compatibility is checked.
- `enum` objectives require a non-empty `enum_values` list.
- `exists` and `not_exists` must not declare `expected_value`.
- Metadata-only packs remain valid and are not treated as malformed.

Required input derivation:

- Required input fields are derived only from evaluable packs.
- Fields are taken from objectives whose `required` flag is `true`.
- Omitted `required` defaults to `true`.
- First declared occurrence order is preserved.
- Exact duplicates are removed deterministically.

Evaluation-contract fingerprint:

- Only evaluable packs receive an evaluation fingerprint.
- The fingerprint includes only evaluation semantics:
  - objective pack identity/version
  - ordered objective IDs
  - input fields
  - value types
  - operators
  - expected values
  - success semantics
  - required flags
  - enum values when applicable
- Labels, descriptions, action-moment text, timestamps, and unrelated metadata do not affect the fingerprint.

Automatic migration is intentionally prohibited:

- No objectives are invented for legacy packs.
- `matter_houses`, `natural_significators`, and `action_moment` are not converted into objectives.
- Operators, thresholds, and success semantics are not inferred from prose.

Relationship to later phases:

- This phase defines the schema contract only.
- Phase 9O.1 will add the read-only evaluator.
- Phase 9O will build the certified-rule objective preview flow on top of this foundation.
