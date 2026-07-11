# Phase 10B.2 Operational Telemetry Partial/Corrupt Read-Path Audit

Phase 10B.1 proved that operational telemetry read-only paths do not create storage when the root is missing. This follow-up audits a narrower remaining risk: partial or corrupt telemetry storage that already exists.

Cases covered:

- malformed event index
- event index entry pointing to a missing event file
- malformed event file referenced by the index
- malformed snapshot index

Audited read-only functions:

- `list_deployed_rule_operational_events`
- `get_deployed_rule_operational_telemetry_health`
- `format_deployed_rule_operational_telemetry_report`

Write-capable functions intentionally excluded:

- `record_deployed_rule_operational_event`
- `build_deployed_rule_operational_snapshot`

Implemented behavior:

- malformed telemetry indexes are surfaced as corrupt blockers instead of silently collapsing to empty lists
- read-only telemetry paths do not repair malformed indexes, rewrite bytes, create placeholder files, or create new storage during corruption handling
- telemetry report output now includes health-level blockers and warnings so corrupt index state is visible through the read-only report path
- execution runtime telemetry remains opt-in and unchanged

Focused validation command:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_deployed_rule_operational_telemetry_read_path_no_write.DeployedRuleOperationalTelemetryReadPathNoWriteTest.test_operational_telemetry_partial_corrupt_storage_read_paths_do_not_repair_or_write
```

Known risks:

- this phase audits only a focused corrupt-storage subset, not every possible mixed valid/stale/corrupt telemetry combination
- no telemetry storage redesign or migration was performed
- broad regression coverage is still not claimed
