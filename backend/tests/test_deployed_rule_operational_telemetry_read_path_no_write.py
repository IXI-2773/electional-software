import json
import inspect
import tempfile
import unittest
from pathlib import Path

from backend.electional import deployed_rule_effectiveness_scoring_result as scoring_result
from backend.electional import deployed_rule_effectiveness_readiness as readiness
from backend.electional import deployed_rule_effectiveness_evaluation_spec as spec
from backend.electional import deployed_rule_effectiveness_scoring_contract as scoring_contract
from backend.electional import deployed_rule_execution_runtime as runtime
from backend.electional import deployed_rule_operational_telemetry as telemetry


class DeployedRuleOperationalTelemetryReadPathNoWriteTest(unittest.TestCase):
    def test_operational_telemetry_read_paths_do_not_create_storage_when_missing_and_runtime_telemetry_is_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "store"

            def snapshot_tree() -> tuple[list[str], dict[str, str]]:
                if not root.exists():
                    return [], {}
                dirs = sorted(str(path.relative_to(root)).replace("\\", "/") for path in root.rglob("*") if path.is_dir())
                files = {
                    str(path.relative_to(root)).replace("\\", "/"): path.read_text(encoding="utf-8")
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                }
                return dirs, files

            before_dirs, before_files = snapshot_tree()
            manifest = telemetry.get_deployed_rule_operational_telemetry_manifest(root=root)
            workspace = telemetry.build_deployed_rule_operational_telemetry_workspace(
                "rule-missing",
                "deployment-missing",
                phase_9w_result_id="acceptance-missing",
                production_target_id="target-missing",
                deployed_rule_id="deployed-missing",
                root=root,
            )
            eligibility = telemetry.validate_deployed_rule_operational_telemetry_eligibility(
                "rule-missing",
                "deployment-missing",
                phase_9w_result_id="acceptance-missing",
                production_target_id="target-missing",
                deployed_rule_id="deployed-missing",
                root=root,
            )
            listing = telemetry.list_deployed_rule_operational_events(
                "deployed-missing",
                "deployment-missing",
                root=root,
            )
            health = telemetry.get_deployed_rule_operational_telemetry_health(
                "rule-missing",
                "deployment-missing",
                phase_9w_result_id="acceptance-missing",
                production_target_id="target-missing",
                deployed_rule_id="deployed-missing",
                root=root,
            )
            report = telemetry.format_deployed_rule_operational_telemetry_report(
                "rule-missing",
                "deployment-missing",
                phase_9w_result_id="acceptance-missing",
                production_target_id="target-missing",
                deployed_rule_id="deployed-missing",
                root=root,
            )
            after_dirs, after_files = snapshot_tree()

        self.assertEqual(before_dirs, [])
        self.assertEqual(before_files, {})
        self.assertEqual(after_dirs, [])
        self.assertEqual(after_files, {})
        self.assertTrue(manifest["state_telemetry_available"])
        self.assertTrue(manifest["execution_telemetry_available"])
        self.assertIn(workspace["status"], {"blocked", "stale", "ready"})
        self.assertIn(eligibility["status"], {"blocked", "stale", "eligible", "eligible_with_warnings"})
        self.assertEqual(listing["status"], "listed")
        self.assertEqual(listing["items"], [])
        self.assertIn(health["status"], {"healthy", "warning", "blocked"})
        self.assertIn("Effectiveness evaluation remains not_performed.", report)
        self.assertIn("Phase 9W acceptance is not used as effectiveness evidence.", report)

        for payload in (workspace, eligibility, listing, health):
            if "writes_performed" in payload:
                self.assertEqual(payload["writes_performed"], 0)

        read_only_functions = [
            telemetry.get_deployed_rule_operational_telemetry_manifest,
            telemetry.build_deployed_rule_operational_telemetry_workspace,
            telemetry.validate_deployed_rule_operational_telemetry_eligibility,
            telemetry.list_deployed_rule_operational_events,
            telemetry.get_deployed_rule_operational_telemetry_health,
            telemetry.format_deployed_rule_operational_telemetry_report,
        ]
        forbidden_tokens = [
            "_ensure_dirs(",
            "record_deployed_rule_operational_event(",
            "build_deployed_rule_operational_snapshot(",
            "json.dump(",
            "write_text(",
            "atomic_write",
        ]
        for func in read_only_functions:
            source = inspect.getsource(func)
            for token in forbidden_tokens:
                self.assertNotIn(token, source, msg=f"{func.__name__} unexpectedly contains {token}")

        execute_source = inspect.getsource(runtime.execute_deployed_rule)
        self.assertIn("record_operational_telemetry: bool = False", execute_source)
        self.assertIn("if record_operational_telemetry:", execute_source)
        self.assertEqual(execute_source.count("telemetry_backend.record_deployed_rule_execution_event("), 2)
        self.assertEqual(scoring_result.AUTHORITY_SCOPE, "registered_outcome_truth_exact_match_accuracy_like")

    def test_operational_telemetry_partial_corrupt_storage_read_paths_do_not_repair_or_write(self) -> None:
        read_only_functions = [
            telemetry.get_deployed_rule_operational_telemetry_manifest,
            telemetry.build_deployed_rule_operational_telemetry_workspace,
            telemetry.validate_deployed_rule_operational_telemetry_eligibility,
            telemetry.list_deployed_rule_operational_events,
            telemetry.get_deployed_rule_operational_telemetry_health,
            telemetry.format_deployed_rule_operational_telemetry_report,
        ]
        forbidden_tokens = [
            "_ensure_dirs(",
            "record_deployed_rule_operational_event(",
            "build_deployed_rule_operational_snapshot(",
            "json.dump(",
            "write_text(",
            "atomic_write",
        ]
        for func in read_only_functions:
            source = inspect.getsource(func)
            for token in forbidden_tokens:
                self.assertNotIn(token, source, msg=f"{func.__name__} unexpectedly contains {token}")

        execute_source = inspect.getsource(runtime.execute_deployed_rule)
        self.assertIn("record_operational_telemetry: bool = False", execute_source)
        self.assertIn("if record_operational_telemetry:", execute_source)
        self.assertEqual(scoring_result.AUTHORITY_SCOPE, "registered_outcome_truth_exact_match_accuracy_like")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "store"

            def write_text(path: Path, text: str) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

            def snapshot_tree() -> tuple[list[str], dict[str, bytes]]:
                dirs = sorted(str(path.relative_to(root)).replace("\\", "/") for path in root.rglob("*") if path.is_dir()) if root.exists() else []
                files = {
                    str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                } if root.exists() else {}
                return dirs, files

            deployment_result_id = "deployment-missing"
            deployed_rule_id = "deployed-missing"

            event_index_path = root / "indexes" / telemetry.EVENT_INDEX
            snapshot_index_path = root / "indexes" / telemetry.SNAPSHOT_INDEX
            malformed_event_path = root / telemetry.EVENT_DIR / "broken-event.json"

            write_text(event_index_path, "{not-json")
            before_dirs, before_files = snapshot_tree()
            corrupt_listing = telemetry.list_deployed_rule_operational_events(deployed_rule_id, deployment_result_id, root=root)
            corrupt_health = telemetry.get_deployed_rule_operational_telemetry_health("rule-missing", deployment_result_id, deployed_rule_id=deployed_rule_id, root=root)
            corrupt_report = telemetry.format_deployed_rule_operational_telemetry_report("rule-missing", deployment_result_id, deployed_rule_id=deployed_rule_id, root=root)
            after_dirs, after_files = snapshot_tree()

            self.assertEqual(before_dirs, after_dirs)
            self.assertEqual(before_files, after_files)
            self.assertEqual(corrupt_listing["status"], "corrupt")
            self.assertIn("telemetry_event_index_corrupt", corrupt_listing["blockers"])
            self.assertIn("telemetry_event_index_corrupt", corrupt_health["blockers"])
            self.assertIn("Health Blockers:", corrupt_report)
            self.assertEqual(corrupt_listing["writes_performed"], 0)

            write_text(
                event_index_path,
                '{"schema_version":"deployed_rule_operational_event_index_v1","items":[{"event_id":"missing-event","relative_path":"deployed_rule_operational_telemetry/events/missing-event.json","deployed_rule_id":"deployed-missing","production_deployment_result_id":"deployment-missing","producer_id":"p","event_type":"evaluation_completed","observed_at":"2026-07-11T00:00:00Z","producer_sequence":null,"event_fingerprint":"x"}],"updated_at_utc":"2026-07-11T00:00:00Z"}',
            )
            before_dirs, before_files = snapshot_tree()
            missing_listing = telemetry.list_deployed_rule_operational_events(deployed_rule_id, deployment_result_id, root=root)
            missing_health = telemetry.get_deployed_rule_operational_telemetry_health("rule-missing", deployment_result_id, deployed_rule_id=deployed_rule_id, root=root)
            after_dirs, after_files = snapshot_tree()

            self.assertEqual(before_dirs, after_dirs)
            self.assertEqual(before_files, after_files)
            self.assertEqual(missing_listing["status"], "listed")
            self.assertEqual(missing_listing["items"], [])
            self.assertEqual(missing_listing["invalid_or_corrupt_records"][0]["reason"], "index_to_file_missing")
            self.assertIn("telemetry_event_index_points_to_missing_file", missing_health["blockers"])
            self.assertFalse((root / telemetry.EVENT_DIR / "missing-event.json").exists())

            write_text(malformed_event_path, '{"schema_version":"wrong","event_id":"broken-event"}')
            write_text(
                event_index_path,
                '{"schema_version":"deployed_rule_operational_event_index_v1","items":[{"event_id":"broken-event","relative_path":"deployed_rule_operational_telemetry/events/broken-event.json","deployed_rule_id":"deployed-missing","production_deployment_result_id":"deployment-missing","producer_id":"p","event_type":"evaluation_completed","observed_at":"2026-07-11T00:00:00Z","producer_sequence":null,"event_fingerprint":"x"}],"updated_at_utc":"2026-07-11T00:00:00Z"}',
            )
            before_dirs, before_files = snapshot_tree()
            malformed_listing = telemetry.list_deployed_rule_operational_events(deployed_rule_id, deployment_result_id, root=root)
            malformed_health = telemetry.get_deployed_rule_operational_telemetry_health("rule-missing", deployment_result_id, deployed_rule_id=deployed_rule_id, root=root)
            after_dirs, after_files = snapshot_tree()

            self.assertEqual(before_dirs, after_dirs)
            self.assertEqual(before_files, after_files)
            self.assertEqual(malformed_listing["invalid_or_corrupt_records"][0]["reason"], "telemetry_event_schema_unsupported")
            self.assertIn("telemetry_event_invalid", malformed_health["blockers"])
            self.assertEqual(before_files[str(malformed_event_path.relative_to(root)).replace("\\", "/")], after_files[str(malformed_event_path.relative_to(root)).replace("\\", "/")])

            write_text(snapshot_index_path, "{bad-snapshot-index")
            before_dirs, before_files = snapshot_tree()
            snapshot_health = telemetry.get_deployed_rule_operational_telemetry_health("rule-missing", deployment_result_id, deployed_rule_id=deployed_rule_id, root=root)
            snapshot_report = telemetry.format_deployed_rule_operational_telemetry_report("rule-missing", deployment_result_id, deployed_rule_id=deployed_rule_id, root=root)
            after_dirs, after_files = snapshot_tree()

            self.assertEqual(before_dirs, after_dirs)
            self.assertEqual(before_files, after_files)
            self.assertIn("telemetry_snapshot_index_corrupt", snapshot_health["blockers"])
            self.assertIn("telemetry_snapshot_index_corrupt", snapshot_report)

    def test_downstream_readiness_consumers_surface_corrupt_telemetry_without_writes_or_false_readiness(self) -> None:
        readiness_read_only_functions = [
            readiness.get_deployed_rule_effectiveness_readiness_manifest,
            readiness.build_deployed_rule_effectiveness_readiness_workspace,
            readiness.validate_deployed_rule_effectiveness_readiness_eligibility,
            readiness.load_deployed_rule_effectiveness_readiness_result,
            readiness.get_deployed_rule_effectiveness_readiness_health,
            readiness.format_deployed_rule_effectiveness_readiness_report,
        ]
        forbidden_tokens = [
            "_ensure_dirs(",
            "build_deployed_rule_effectiveness_readiness_plan(",
            "record_deployed_rule_effectiveness_readiness_result(",
            "record_deployed_rule_operational_event(",
            "build_deployed_rule_operational_snapshot(",
            "json.dump(",
            "write_text(",
            "atomic_write",
        ]
        for func in readiness_read_only_functions:
            source = inspect.getsource(func)
            for token in forbidden_tokens:
                self.assertNotIn(token, source, msg=f"{func.__name__} unexpectedly contains {token}")

        execute_source = inspect.getsource(runtime.execute_deployed_rule)
        self.assertIn("record_operational_telemetry: bool = False", execute_source)
        self.assertIn("if record_operational_telemetry:", execute_source)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "store"

            def write_text(path: Path, text: str) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

            def snapshot_tree() -> tuple[list[str], dict[str, bytes]]:
                dirs = sorted(str(path.relative_to(root)).replace("\\", "/") for path in root.rglob("*") if path.is_dir()) if root.exists() else []
                files = {
                    str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                } if root.exists() else {}
                return dirs, files

            canonical_rule_id = "rule-missing"
            deployment_result_id = "deployment-missing"
            production_target_id = "target-missing"
            deployed_rule_id = "deployed-missing"
            snapshot_id = "snapshot-missing"
            observation_start = "2026-07-11T00:00:00Z"
            observation_end = "2026-07-11T01:00:00Z"

            snapshot = {
                "schema_version": telemetry.SNAPSHOT_SCHEMA,
                "telemetry_schema_version": telemetry.TELEMETRY_SCHEMA_VERSION,
                "snapshot_id": snapshot_id,
                "deployed_rule_id": deployed_rule_id,
                "production_deployment_result_id": deployment_result_id,
                "phase_9w_result_id": None,
                "canonical_rule_id": canonical_rule_id,
                "production_target_id": production_target_id,
                "production_transaction_id": "txn-missing",
                "observation_start": observation_start,
                "observation_end": observation_end,
                "manifest_fingerprint": "manifest-fingerprint",
                "validated_event_ids": ["broken-event"],
                "validated_event_count": 1,
                "total_matching_event_count": 1,
                "invalid_event_count": 0,
                "corrupt_event_count": 0,
                "stale_historical_event_count": 0,
                "current_binding_mismatch_count": 0,
                "producer_ids": [telemetry.EXECUTION_PRODUCER_ID],
                "producer_fingerprints": ["producer-fingerprint"],
                "sequence_gap_count_by_producer": {},
                "execution_event_count": 1,
                "execution_telemetry_available": True,
                "effectiveness_evaluation_status": "not_performed",
                "metric_availability": {
                    "execution_completion_count": "available",
                    "execution_failure_count": "available",
                    "execution_skip_count": "unsupported_by_producer",
                    "fallback_count": "unsupported_by_producer",
                    "duration_statistics": "available",
                },
                "execution_completion_count": 1,
                "execution_failure_count": 0,
                "execution_skip_count": 0,
                "fallback_count": 0,
                "duration_summary_ms": {"count": 1, "min": 1, "max": 1},
                "invalid_or_corrupt_reasons": [],
                "snapshot_completeness_status": "complete",
            }
            snapshot["snapshot_fingerprint"] = telemetry._snapshot_fingerprint(snapshot)

            write_text(root / telemetry.EVENT_DIR / "broken-event.json", '{"schema_version":"wrong","event_id":"broken-event"}')
            write_text(
                root / "indexes" / telemetry.EVENT_INDEX,
                '{"schema_version":"deployed_rule_operational_event_index_v1","items":[{"event_id":"broken-event","relative_path":"deployed_rule_operational_telemetry/events/broken-event.json","deployed_rule_id":"deployed-missing","production_deployment_result_id":"deployment-missing","producer_id":"p","event_type":"evaluation_completed","observed_at":"2026-07-11T00:00:00Z","producer_sequence":null,"event_fingerprint":"x"}],"updated_at_utc":"2026-07-11T00:00:00Z"}',
            )
            write_text(root / telemetry.SNAPSHOT_DIR / f"{snapshot_id}.json", json.dumps(snapshot))

            before_dirs, before_files = snapshot_tree()
            workspace = readiness.build_deployed_rule_effectiveness_readiness_workspace(
                canonical_rule_id,
                deployment_result_id,
                production_target_id,
                deployed_rule_id,
                snapshot_id,
                observation_start,
                observation_end,
                root=root,
            )
            eligibility = readiness.validate_deployed_rule_effectiveness_readiness_eligibility(
                canonical_rule_id,
                deployment_result_id,
                production_target_id,
                deployed_rule_id,
                snapshot_id,
                observation_start,
                observation_end,
                root=root,
            )
            loaded = readiness.load_deployed_rule_effectiveness_readiness_result("missing-readiness-result", root=root)
            health = readiness.get_deployed_rule_effectiveness_readiness_health(root=root)
            report = readiness.format_deployed_rule_effectiveness_readiness_report(
                canonical_rule_id,
                deployment_result_id,
                production_target_id,
                deployed_rule_id,
                snapshot_id,
                observation_start,
                observation_end,
                root=root,
            )
            after_dirs, after_files = snapshot_tree()

        self.assertEqual(before_dirs, after_dirs)
        self.assertEqual(before_files, after_files)
        self.assertEqual(workspace["status"], "corrupt")
        self.assertEqual(eligibility["status"], "corrupt")
        self.assertIn("telemetry_storage_corrupt_or_incomplete", workspace["blockers"])
        self.assertIn("telemetry_storage_corrupt_or_incomplete", eligibility["blockers"])
        self.assertNotEqual(workspace["status"], "ready_for_effectiveness_evaluation")
        self.assertNotEqual(eligibility["status"], "ready_for_effectiveness_evaluation")
        self.assertEqual(loaded["status"], "blocked")
        self.assertEqual(health["status"], "healthy")
        self.assertIn("telemetry_storage_corrupt_or_incomplete", report)
        self.assertIn("this is not an effectiveness score", report)
        self.assertIn("evaluation_completed means runtime returned normally", report)
        self.assertNotIn("phase 9w is outcome truth", report.lower())
        self.assertEqual(scoring_result.AUTHORITY_SCOPE, "registered_outcome_truth_exact_match_accuracy_like")

    def test_downstream_spec_and_contract_consumers_do_not_convert_corrupt_telemetry_readiness_into_ready_or_scoreable(self) -> None:
        spec_read_only_functions = [
            spec.get_deployed_rule_effectiveness_evaluation_spec_manifest,
            spec.build_deployed_rule_effectiveness_evaluation_spec_workspace,
            spec.validate_deployed_rule_effectiveness_evaluation_spec_eligibility,
            spec.load_deployed_rule_effectiveness_evaluation_spec_result,
            spec.get_deployed_rule_effectiveness_evaluation_spec_health,
            spec.format_deployed_rule_effectiveness_evaluation_spec_report,
        ]
        contract_read_only_functions = [
            scoring_contract.get_deployed_rule_effectiveness_scoring_contract_manifest,
            scoring_contract.build_deployed_rule_effectiveness_scoring_contract_workspace,
            scoring_contract.validate_deployed_rule_effectiveness_scoring_contract_eligibility,
            scoring_contract.load_deployed_rule_effectiveness_scoring_contract_result,
            scoring_contract.get_deployed_rule_effectiveness_scoring_contract_health,
            scoring_contract.format_deployed_rule_effectiveness_scoring_contract_report,
        ]
        forbidden_tokens = [
            "_ensure_dirs(",
            "build_deployed_rule_effectiveness_evaluation_spec_plan(",
            "record_deployed_rule_effectiveness_evaluation_spec_result(",
            "build_deployed_rule_effectiveness_scoring_contract_plan(",
            "record_deployed_rule_effectiveness_scoring_contract_result(",
            "build_deployed_rule_effectiveness_readiness_plan(",
            "record_deployed_rule_effectiveness_readiness_result(",
            "record_deployed_rule_operational_event(",
            "build_deployed_rule_operational_snapshot(",
            "json.dump(",
            "write_text(",
            "atomic_write",
        ]
        for func in spec_read_only_functions + contract_read_only_functions:
            source = inspect.getsource(func)
            for token in forbidden_tokens:
                self.assertNotIn(token, source, msg=f"{func.__name__} unexpectedly contains {token}")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "store"

            def write_text(path: Path, text: str) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")

            def snapshot_tree() -> tuple[list[str], dict[str, bytes]]:
                dirs = sorted(str(path.relative_to(root)).replace("\\", "/") for path in root.rglob("*") if path.is_dir()) if root.exists() else []
                files = {
                    str(path.relative_to(root)).replace("\\", "/"): path.read_bytes()
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                } if root.exists() else {}
                return dirs, files

            write_text(root / "indexes" / telemetry.EVENT_INDEX, "{bad-event-index")

            canonical_rule_id = "rule-missing"
            deployment_result_id = "deployment-missing"
            production_target_id = "target-missing"
            deployed_rule_id = "deployed-missing"
            telemetry_snapshot_id = "snapshot-missing"
            readiness_result_id = "readiness-missing"
            spec_result_id = "spec-missing"
            truth_result_id = "truth-missing"
            truth_record_set_id = "truth-record-set-missing"
            observation_start = "2026-07-11T00:00:00Z"
            observation_end = "2026-07-11T01:00:00Z"

            before_dirs, before_files = snapshot_tree()
            spec_workspace = spec.build_deployed_rule_effectiveness_evaluation_spec_workspace(
                canonical_rule_id,
                deployment_result_id,
                production_target_id,
                deployed_rule_id,
                telemetry_snapshot_id,
                readiness_result_id,
                observation_start,
                observation_end,
                root=root,
            )
            spec_eligibility = spec.validate_deployed_rule_effectiveness_evaluation_spec_eligibility(
                canonical_rule_id,
                deployment_result_id,
                production_target_id,
                deployed_rule_id,
                telemetry_snapshot_id,
                readiness_result_id,
                observation_start,
                observation_end,
                root=root,
            )
            spec_loaded = spec.load_deployed_rule_effectiveness_evaluation_spec_result("spec-result-missing", root=root)
            spec_health = spec.get_deployed_rule_effectiveness_evaluation_spec_health(root=root)
            spec_report = spec.format_deployed_rule_effectiveness_evaluation_spec_report(
                canonical_rule_id,
                deployment_result_id,
                production_target_id,
                deployed_rule_id,
                telemetry_snapshot_id,
                readiness_result_id,
                observation_start,
                observation_end,
                root=root,
            )

            contract_workspace = scoring_contract.build_deployed_rule_effectiveness_scoring_contract_workspace(
                canonical_rule_id,
                deployment_result_id,
                production_target_id,
                deployed_rule_id,
                telemetry_snapshot_id,
                readiness_result_id,
                spec_result_id,
                truth_result_id,
                truth_record_set_id,
                observation_start,
                observation_end,
                root=root,
            )
            contract_eligibility = scoring_contract.validate_deployed_rule_effectiveness_scoring_contract_eligibility(
                canonical_rule_id,
                deployment_result_id,
                production_target_id,
                deployed_rule_id,
                telemetry_snapshot_id,
                readiness_result_id,
                spec_result_id,
                truth_result_id,
                truth_record_set_id,
                observation_start,
                observation_end,
                root=root,
            )
            contract_loaded = scoring_contract.load_deployed_rule_effectiveness_scoring_contract_result("contract-result-missing", root=root)
            contract_health = scoring_contract.get_deployed_rule_effectiveness_scoring_contract_health(root=root)
            contract_report = scoring_contract.format_deployed_rule_effectiveness_scoring_contract_report(
                canonical_rule_id,
                deployment_result_id,
                production_target_id,
                deployed_rule_id,
                telemetry_snapshot_id,
                readiness_result_id,
                spec_result_id,
                truth_result_id,
                truth_record_set_id,
                observation_start,
                observation_end,
                root=root,
            )
            after_dirs, after_files = snapshot_tree()

        self.assertEqual(before_dirs, after_dirs)
        self.assertEqual(before_files, after_files)

        self.assertNotEqual(spec_workspace["status"], "spec_ready_for_scoring_engine_design")
        self.assertNotEqual(spec_eligibility["status"], "spec_ready_for_scoring_engine_design")
        self.assertEqual(spec_loaded["status"], "blocked")
        self.assertEqual(spec_health["status"], "healthy")
        self.assertIn("This is specification only; no effectiveness score was calculated.", spec_report)
        self.assertIn("Execution completion is not correctness.", spec_report)
        self.assertIn("Phase 9W acceptance is not effectiveness evidence.", spec_report)

        self.assertEqual(contract_workspace["status"], "blocked")
        self.assertEqual(contract_eligibility["status"], "blocked")
        self.assertEqual(contract_loaded["status"], "blocked")
        self.assertEqual(contract_health["status"], "healthy")
        self.assertIn("This is a scoring contract only; no effectiveness score was calculated.", contract_report)
        self.assertIn("Source availability is not effectiveness.", contract_report)
        self.assertIn("Execution completion is not correctness.", contract_report)
        self.assertIn("Phase 9W acceptance is not scoring input.", contract_report)
        self.assertIn("effectiveness_readiness_result_missing", contract_workspace["blockers"])
        self.assertIn("effectiveness_evaluation_spec_result_missing", contract_workspace["blockers"])
        self.assertEqual(scoring_result.AUTHORITY_SCOPE, "registered_outcome_truth_exact_match_accuracy_like")


if __name__ == "__main__":
    unittest.main()
