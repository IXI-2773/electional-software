# Deployed Rule Execution Runtime

Phase 9Y.0A exists because Phase 9Y.0 proved the repository had no authoritative deployed-rule execution entrypoint, only the generic canonical evaluator.

This phase adds a read-only deployed-rule execution wrapper in `backend/electional/deployed_rule_execution_runtime.py`.
It also enables a trusted execution telemetry producer in Phase 9X:

- `deployed_rule_execution_runtime_observer`
- supported event types:
  - `evaluation_completed`
  - `evaluation_failed`

## Purpose

It binds one completed Phase 9V deployment result and one deployed-rule instance to the existing canonical evaluator without mutating deployment state, canonical rule state, Phase 9V records, Phase 9W records, or telemetry storage.

## Required IDs

The runtime requires explicit:

- `canonical_rule_id`
- `production_deployment_result_id`
- `production_target_id`
- `deployed_rule_id`
- execution input accepted by `evaluate_canonical_rule(...)`

It does not auto-select the newest deployment, newest deployed instance, or latest acceptance/telemetry record.

## Binding checks

Before execution, the runtime verifies:

- the Phase 9V deployment result exists and completed;
- the deployment receipt matches the result fingerprint;
- the deployed-rule ID matches the Phase 9V committed deployed instance;
- the current production transaction is still committed and verified;
- the deployed rule belongs to the exact production transaction;
- the deployed rule binds back to the expected canonical source rule;
- the canonical source-rule fingerprint still matches deployment evidence;
- the production target matches deployment evidence;
- the canonical evaluator is available.

## Outcome semantics

Execution statuses:

- `completed`
- `failed`
- `skipped`
- `blocked`
- `unsupported`

These are runtime-only statuses. They do not mean correct, effective, profitable, or production-safe.

## Privacy boundaries

The runtime returns a public-safe envelope using identity fields and fingerprints.

It does not expose:

- raw private input;
- full serialized output payloads in reports;
- secrets;
- credentials;
- absolute paths;
- stack traces.

## Telemetry compatibility

The execution envelope includes:

- deployed-rule and Phase 9V identity bindings;
- transaction binding;
- input fingerprint;
- output fingerprint;
- runtime outcome status;
- duration when measured safely.

Telemetry event recording is now available through the runtime entrypoint when telemetry is explicitly requested.

The producer records only authoritative runtime execution events and keeps:

- `effectiveness_evaluation_status = not_performed`
- unsupported metrics unavailable when the producer does not authoritatively emit them

## Effectiveness boundary

This phase does not perform effectiveness evaluation.

Phase 9W acceptance is not used as effectiveness evidence.

Effectiveness evaluation remains blocked until real execution telemetry completeness rules, denominators, and sample-sufficiency rules exist.
