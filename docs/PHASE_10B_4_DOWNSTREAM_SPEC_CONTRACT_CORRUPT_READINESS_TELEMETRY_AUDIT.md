# Phase 10B.4 Downstream Spec/Contract Corrupt Readiness/Telemetry Audit

Phase 10B.3 hardened the direct readiness consumer. This follow-up audits the next downstream read-only consumers before scoring work: `backend/electional/deployed_rule_effectiveness_evaluation_spec.py` and `backend/electional/deployed_rule_effectiveness_scoring_contract.py`.

Consumers audited:

- effectiveness evaluation spec
- scoring contract

Corrupt or missing prerequisite scenarios checked:

- corrupt telemetry storage present in the repository root
- missing readiness result
- missing evaluation-spec result
- missing outcome-truth result and record set

Read-only functions audited:

- `get_deployed_rule_effectiveness_evaluation_spec_manifest`
- `build_deployed_rule_effectiveness_evaluation_spec_workspace`
- `validate_deployed_rule_effectiveness_evaluation_spec_eligibility`
- `load_deployed_rule_effectiveness_evaluation_spec_result`
- `get_deployed_rule_effectiveness_evaluation_spec_health`
- `format_deployed_rule_effectiveness_evaluation_spec_report`
- `get_deployed_rule_effectiveness_scoring_contract_manifest`
- `build_deployed_rule_effectiveness_scoring_contract_workspace`
- `validate_deployed_rule_effectiveness_scoring_contract_eligibility`
- `load_deployed_rule_effectiveness_scoring_contract_result`
- `get_deployed_rule_effectiveness_scoring_contract_health`
- `format_deployed_rule_effectiveness_scoring_contract_report`

Write functions intentionally excluded:

- `build_deployed_rule_effectiveness_evaluation_spec_plan`
- `record_deployed_rule_effectiveness_evaluation_spec_result`
- `build_deployed_rule_effectiveness_scoring_contract_plan`
- `record_deployed_rule_effectiveness_scoring_contract_result`

Implemented behavior:

- evaluation-spec read-only result loading, health, and context setup no longer create storage under missing or corrupt prerequisite roots
- downstream spec and contract consumers remain blocked when prerequisite readiness/spec/truth evidence is missing
- no downstream report text claims runtime completion is correctness, telemetry availability is effectiveness, or Phase 9W is outcome truth
- no storage repair or rewrite is performed through these read-only paths

Focused validation command:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_operational_telemetry_read_path_no_write.DeployedRuleOperationalTelemetryReadPathNoWriteTest.test_downstream_spec_and_contract_consumers_do_not_convert_corrupt_telemetry_readiness_into_ready_or_scoreable
```

Limitations:

- this pass uses missing prerequisite result IDs to prove the read-only downstream paths remain blocked and non-writing; it does not fabricate a full valid readiness/spec chain just to force later telemetry corruption through every branch
- broader downstream consumers were not audited here
- broad regression coverage is still not claimed
