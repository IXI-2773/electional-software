# Phase 10B.1 Operational Telemetry Read-Path No-Write Audit

Phase 10B removed hidden writes from scoring-contract and outcome-truth read paths. This follow-up audits the next transitive dependency directly: `backend/electional/deployed_rule_operational_telemetry.py`, plus the execution-runtime telemetry opt-in gate in `backend/electional/deployed_rule_execution_runtime.py`.

Audited read-only telemetry functions:

- `get_deployed_rule_operational_telemetry_manifest`
- `build_deployed_rule_operational_telemetry_workspace`
- `validate_deployed_rule_operational_telemetry_eligibility`
- `list_deployed_rule_operational_events`
- `get_deployed_rule_operational_telemetry_health`
- `format_deployed_rule_operational_telemetry_report`

Explicit write-capable telemetry functions intentionally excluded:

- `record_deployed_rule_operational_event`
- `build_deployed_rule_operational_snapshot`

Implemented behavior:

- missing-root read-only telemetry calls no longer create telemetry directories, event files, snapshot files, or indexes
- read-only calls return in-memory missing or blocked results instead of creating storage just to report absence
- execution runtime telemetry remains opt-in through `execute_deployed_rule(..., record_operational_telemetry=False)`

Focused validation command:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_operational_telemetry_read_path_no_write.DeployedRuleOperationalTelemetryReadPathNoWriteTest.test_operational_telemetry_read_paths_do_not_create_storage_when_missing_and_runtime_telemetry_is_opt_in
```

Known risks:

- this phase audits operational telemetry read paths only; it does not claim every later consumer has been audited
- write-path behavior was preserved intentionally and not revalidated beyond compile and focused no-write assertions
- telemetry storage design was not redesigned or migrated in this phase
