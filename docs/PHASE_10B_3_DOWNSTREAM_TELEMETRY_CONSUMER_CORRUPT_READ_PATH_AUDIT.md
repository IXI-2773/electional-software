# Phase 10B.3 Downstream Telemetry Consumer Corrupt Read-Path Audit

Phase 10B.2 hardened operational telemetry read paths themselves. This follow-up audits the direct downstream consumer that uses telemetry before any later scoring work: `backend/electional/deployed_rule_effectiveness_readiness.py`.

Scope covered:

- readiness workspace and eligibility behavior when telemetry storage is corrupt
- readiness report behavior when telemetry storage is corrupt
- readiness read-only no-write behavior under corrupt telemetry fixtures
- execution runtime telemetry remains opt-in

Corrupt telemetry scenarios checked:

- malformed indexed event file behind a telemetry snapshot
- telemetry health corruption propagated into readiness blockers

Read-only readiness functions audited:

- `get_deployed_rule_effectiveness_readiness_manifest`
- `build_deployed_rule_effectiveness_readiness_workspace`
- `validate_deployed_rule_effectiveness_readiness_eligibility`
- `load_deployed_rule_effectiveness_readiness_result`
- `get_deployed_rule_effectiveness_readiness_health`
- `format_deployed_rule_effectiveness_readiness_report`

Write functions intentionally excluded:

- `build_deployed_rule_effectiveness_readiness_plan`
- `record_deployed_rule_effectiveness_readiness_result`

Implemented behavior:

- readiness read-only paths no longer create readiness storage when loading or checking health
- corrupt telemetry health is surfaced into readiness blockers as `telemetry_storage_corrupt_or_incomplete`
- corrupt telemetry does not become readiness
- runtime completion remains runtime completion only; it is not correctness
- telemetry availability remains a prerequisite signal only; it is not effectiveness
- Phase 9W remains integrity evidence only and not outcome truth

Focused validation command:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_operational_telemetry_read_path_no_write.DeployedRuleOperationalTelemetryReadPathNoWriteTest.test_downstream_readiness_consumers_surface_corrupt_telemetry_without_writes_or_false_readiness
```

Known risks:

- this phase audited the direct readiness consumer only, not every later telemetry consumer
- readiness health remains a health check for readiness storage, not a full telemetry-integrity summary
- broad regression coverage is still not claimed
