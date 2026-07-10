from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import certified_rule_fast_lane_preview as preview_backend
from backend.electional.analysis.fast_lane import get_fast_lane_capability_manifest
from backend.electional.canonical_rule_runtime import validate_canonical_rule_record
from backend.electional.api import (
    build_certified_rule_fast_lane_preview_plan as api_build_plan,
    build_certified_rule_fast_lane_preview_workspace as api_workspace,
    format_certified_rule_fast_lane_preview_report as api_report,
    run_certified_rule_fast_lane_preview as api_run,
    validate_certified_rule_fast_lane_preview_eligibility as api_validate,
)
from backend.tests.test_certified_rule_objective_preview import _setup_rule


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _rule_store(root: Path) -> dict[str, str]:
    stored = _setup_rule(root)
    stored["target"] = "fast_lane.command"
    stored["scope"] = "report_output"
    stored["condition"] = {"field": "final_command.command", "operator": "equals", "value": "USE"}
    stored["operator"] = "equals"
    stored["value"] = "USE"
    validation = validate_canonical_rule_record(stored, require_active=True)
    stored["rule_fingerprint"] = validation["rule_fingerprint"]
    _write_json(root / "canonical_rules" / f"{stored['rule_id']}.json", stored)
    cert_path = root / "rule_activation_certification_receipts" / f"cert_{stored['rule_id']}.json"
    cert_payload = json.loads(cert_path.read_text(encoding="utf-8"))
    cert_payload["rule_hash"] = stored["rule_fingerprint"]
    _write_json(cert_path, cert_payload)
    return {
        "rule_id": str(stored["rule_id"]),
        "document_id": str(stored["document_id"]),
        "source_revision": str(stored["source_revision"]),
        "rule_fingerprint": str(stored["rule_fingerprint"]),
    }


class CertifiedRuleFastLanePreviewTest(TestCase):
    def test_current_certified_rule_completes_fast_lane_compatibility_preview(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            workspace = preview_backend.build_certified_rule_fast_lane_preview_workspace(setup["rule_id"], root=root)
            eligibility = preview_backend.validate_certified_rule_fast_lane_preview_eligibility(setup["rule_id"], root=root)
            plan = preview_backend.build_certified_rule_fast_lane_preview_plan(setup["rule_id"], root=root)
            run = preview_backend.run_certified_rule_fast_lane_preview(plan["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
            rerun = preview_backend.run_certified_rule_fast_lane_preview(plan["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
            loaded = preview_backend.load_certified_rule_fast_lane_preview_result(run["fast_lane_preview_result_id"], root=root)
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(eligibility["status"], "eligible")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(rerun["status"], "already_completed")
        self.assertEqual(rerun["writes_performed"], 0)
        result = loaded["fast_lane_preview_result"]
        self.assertEqual(result["overall_compatibility"], "compatible")
        self.assertEqual(result["semantic_loss"], "none")

    def test_inactive_uncertified_stale_or_mismatched_rule_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            rule_path = root / "canonical_rules" / f"{setup['rule_id']}.json"
            rule_payload = json.loads(rule_path.read_text(encoding="utf-8"))
            rule_payload["status"] = "inactive"
            rule_payload["enabled"] = False
            _write_json(rule_path, rule_payload)
            inactive = preview_backend.validate_certified_rule_fast_lane_preview_eligibility(setup["rule_id"], root=root)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            cert_path = root / "rule_activation_certification_receipts" / f"cert_{setup['rule_id']}.json"
            cert_payload = json.loads(cert_path.read_text(encoding="utf-8"))
            cert_payload["certification_status"] = "stale"
            _write_json(cert_path, cert_payload)
            stale_cert = preview_backend.validate_certified_rule_fast_lane_preview_eligibility(setup["rule_id"], root=root)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            manifest_path = root / "document_manifests" / f"{setup['document_id']}.json"
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_payload["source_revision"] = 99
            _write_json(manifest_path, manifest_payload)
            stale_source = preview_backend.validate_certified_rule_fast_lane_preview_eligibility(setup["rule_id"], root=root)
        self.assertEqual(inactive["status"], "blocked")
        self.assertEqual(stale_cert["status"], "blocked")
        self.assertEqual(stale_source["status"], "stale")

    def test_manifest_or_evaluator_fingerprint_change_makes_preview_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            plan = preview_backend.build_certified_rule_fast_lane_preview_plan(setup["rule_id"], root=root)
            run = preview_backend.run_certified_rule_fast_lane_preview(plan["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
            manifest = get_fast_lane_capability_manifest()
            changed = deepcopy(manifest)
            changed["fast_lane_contract_version"] = int(changed["fast_lane_contract_version"]) + 1
            with patch("backend.electional.certified_rule_fast_lane_preview.get_fast_lane_capability_manifest", return_value=changed):
                health = preview_backend.get_certified_rule_fast_lane_preview_health(plan["fast_lane_preview_plan_id"], root=root)
                rerun = preview_backend.run_certified_rule_fast_lane_preview(plan["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(health["status"], "stale")
        self.assertEqual(rerun["status"], "stale")

    def test_unsupported_rule_semantics_are_preserved_as_incompatible(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            rule_path = root / "canonical_rules" / f"{setup['rule_id']}.json"
            rule_payload = json.loads(rule_path.read_text(encoding="utf-8"))
            rule_payload["condition"] = {
                "field": "final_command.command",
                "operator": "equals",
                "value": "USE",
                "all": [{"field": "final_command.confidence", "operator": "greater_than", "value": 80}],
            }
            rule_payload["rule_fingerprint"] = validate_canonical_rule_record(rule_payload, require_active=True)["rule_fingerprint"]
            _write_json(rule_path, rule_payload)
            plan = preview_backend.build_certified_rule_fast_lane_preview_plan(setup["rule_id"], root=root)
            cert_path = root / "rule_activation_certification_receipts" / f"cert_{setup['rule_id']}.json"
            cert_payload = json.loads(cert_path.read_text(encoding="utf-8"))
            cert_payload["rule_hash"] = rule_payload["rule_fingerprint"]
            _write_json(cert_path, cert_payload)
            fixed_plan = preview_backend.build_certified_rule_fast_lane_preview_plan(setup["rule_id"], root=root)
            run = preview_backend.run_certified_rule_fast_lane_preview(fixed_plan["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
            loaded = preview_backend.load_certified_rule_fast_lane_preview_result(run["fast_lane_preview_result_id"], root=root)
        self.assertIn(plan["status"], {"blocked", "planned"})
        self.assertEqual(run["status"], "incompatible")
        self.assertEqual(loaded["fast_lane_preview_result"]["semantic_loss"], "confirmed")
        self.assertEqual(loaded["fast_lane_preview_result"]["overall_compatibility"], "incompatible")

    def test_plan_result_receipt_relationships_are_deterministic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            plan_one = preview_backend.build_certified_rule_fast_lane_preview_plan(setup["rule_id"], root=root)
            plan_two = preview_backend.build_certified_rule_fast_lane_preview_plan(setup["rule_id"], root=root)
            run = preview_backend.run_certified_rule_fast_lane_preview(plan_one["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
        self.assertEqual(plan_one["fast_lane_preview_plan_id"], plan_two["fast_lane_preview_plan_id"])
        self.assertEqual(plan_one["writes_performed"], 1)
        self.assertEqual(plan_two["writes_performed"], 0)
        self.assertEqual(run["writes_performed"], 2)

    def test_preview_does_not_execute_or_mutate_fast_lane(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            plan = preview_backend.build_certified_rule_fast_lane_preview_plan(setup["rule_id"], root=root)
            rule_before = (root / "canonical_rules" / f"{setup['rule_id']}.json").read_text(encoding="utf-8")
            cert_before = (root / "rule_activation_certification_receipts" / f"cert_{setup['rule_id']}.json").read_text(encoding="utf-8")
            with patch("backend.electional.certified_rule_fast_lane_preview.format_fast_lane_compatibility_report", side_effect=AssertionError("report formatter must not run during preview")), patch("backend.electional.analysis.fast_lane.build_fast_lane_report", side_effect=AssertionError("Fast Lane execution must not run")):
                run = preview_backend.run_certified_rule_fast_lane_preview(plan["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
            rule_after = (root / "canonical_rules" / f"{setup['rule_id']}.json").read_text(encoding="utf-8")
            cert_after = (root / "rule_activation_certification_receipts" / f"cert_{setup['rule_id']}.json").read_text(encoding="utf-8")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(rule_before, rule_after)
        self.assertEqual(cert_before, cert_after)

    def test_identical_rerun_performs_zero_writes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            plan = preview_backend.build_certified_rule_fast_lane_preview_plan(setup["rule_id"], root=root)
            preview_backend.run_certified_rule_fast_lane_preview(plan["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
            rerun = preview_backend.run_certified_rule_fast_lane_preview(plan["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
        self.assertEqual(rerun["status"], "already_completed")
        self.assertEqual(rerun["writes_performed"], 0)

    def test_api_flow_health_summary_and_public_report_are_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            setup = _rule_store(root)
            workspace = api_workspace(setup["rule_id"], root=root)
            eligibility = api_validate(setup["rule_id"], root=root)
            plan = api_build_plan(setup["rule_id"], root=root)
            run = api_run(plan["fast_lane_preview_plan_id"], confirmation="RUN_FAST_LANE_COMPATIBILITY_PREVIEW", root=root)
            health = preview_backend.get_certified_rule_fast_lane_preview_health(plan["fast_lane_preview_plan_id"], root=root)
            summary = preview_backend.get_certified_rule_fast_lane_preview_summary(run["fast_lane_preview_result_id"], root=root)
            report = api_report(run["fast_lane_preview_result_id"], run["fast_lane_preview_receipt_id"], True, root=root)
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(eligibility["status"], "eligible")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(summary["preview_status"], "completed")
        self.assertIn("Fast Lane was not executed.", report)
        self.assertNotIn(str(root), report)
