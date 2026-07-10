from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import certified_rule_fast_lane_preview as fast_lane_preview
from backend.electional import certified_rule_integration_authorization as authorization
from backend.electional import certified_rule_objective_preview as objective_preview
from backend.electional import certified_rule_scoring_preview as scoring_preview
from backend.electional.api import (
    build_certified_rule_integration_authorization_plan as api_build_plan,
    build_certified_rule_integration_authorization_workspace as api_workspace,
    format_certified_rule_integration_authorization_report as api_report,
    save_certified_rule_integration_authorization_decision as api_save,
    validate_certified_rule_integration_authorization_eligibility as api_validate,
)
from backend.electional.objective_outcome_scoring import save_objective_outcome_scoring_config
from backend.tests.test_certified_rule_objective_preview import _mapping, _scoring_config, _setup_dataset, _setup_pack, _setup_rule


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _fast_lane_certification_fingerprint(certification: dict[str, object]) -> str:
    return authorization._certification_fingerprint(certification)


def _build_phase_9r_inputs(root: Path) -> dict[str, object]:
    rule = _setup_rule(root)
    pack = _setup_pack(root)
    _setup_dataset(root)
    objective_plan = objective_preview.build_certified_rule_objective_preview_plan(rule["rule_id"], "preview_pack", "preview_dataset", _mapping(), root=root)
    objective_run = objective_preview.run_certified_rule_objective_preview(objective_plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
    config = _scoring_config(pack)
    config["scoring_config_id"] = "phase_9r_score_config"
    save_objective_outcome_scoring_config(config, confirmation="SAVE_SCORING_CONFIG", root=root)
    scoring_plan = scoring_preview.build_certified_rule_scoring_preview_plan(objective_run["objective_preview_result_id"], "phase_9r_score_config", root=root)
    scoring_run = scoring_preview.run_certified_rule_scoring_preview(scoring_plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
    fast_result_id = "fast_lane_preview_result_phase_9r"
    fast_receipt_id = "fast_lane_preview_receipt_phase_9r"
    manifest = fast_lane_preview.get_fast_lane_capability_manifest()
    capability_fp = fast_lane_preview.get_fast_lane_capability_fingerprint(manifest)
    evaluator_fp = fast_lane_preview.get_fast_lane_compatibility_evaluator_fingerprint()
    certification = json.loads((root / "rule_activation_certification_receipts" / f"cert_{rule['rule_id']}.json").read_text(encoding="utf-8"))
    fast_result = {
        "schema_version": fast_lane_preview.RESULT_SCHEMA,
        "preview_schema_version": fast_lane_preview.PREVIEW_SCHEMA_VERSION,
        "fast_lane_preview_result_id": fast_result_id,
        "fast_lane_preview_plan_id": "fast_lane_preview_plan_phase_9r",
        "canonical_rule_id": rule["rule_id"],
        "document_id": rule["document_id"],
        "source_revision": rule["source_revision"],
        "rule_schema_version": fast_lane_preview.CANONICAL_RULE_SCHEMA(None),
        "rule_fingerprint": rule["rule_fingerprint"],
        "certification_receipt_id": certification["certification_receipt_id"],
        "certification_fingerprint": _fast_lane_certification_fingerprint(certification),
        "fast_lane_contract_id": manifest["fast_lane_contract_id"],
        "fast_lane_contract_version": manifest["fast_lane_contract_version"],
        "fast_lane_capability_fingerprint": capability_fp,
        "compatibility_evaluator_fingerprint": evaluator_fp,
        "dimension_results": [{"dimension": "operators", "status": "compatible"}],
        "supported_operators": ["equals"],
        "unsupported_operators": [],
        "supported_input_fields": ["final_command.command"],
        "unsupported_input_fields": [],
        "supported_actions": ["fast_lane.command"],
        "unsupported_actions": [],
        "semantic_loss": "none",
        "overall_compatibility": "compatible",
        "blockers": [],
        "warnings": [],
        "compatibility_result_fingerprint": "sha256:compatibility_phase_9r",
        "preview_status": "completed",
    }
    fast_result["result_fingerprint"] = fast_lane_preview._result_fingerprint(
        {
            "canonical_rule_id": rule["rule_id"],
            "document_id": rule["document_id"],
            "source_revision": rule["source_revision"],
            "rule_schema_version": fast_result["rule_schema_version"],
            "rule_fingerprint": rule["rule_fingerprint"],
            "certification_receipt_id": certification["certification_receipt_id"],
            "certification_fingerprint": fast_result["certification_fingerprint"],
            "fast_lane_contract_id": manifest["fast_lane_contract_id"],
            "fast_lane_contract_version": manifest["fast_lane_contract_version"],
            "fast_lane_capability_fingerprint": capability_fp,
            "compatibility_evaluator_fingerprint": evaluator_fp,
        },
        {"result_fingerprint": fast_result["compatibility_result_fingerprint"]},
        "completed",
    )
    fast_receipt = {
        "schema_version": fast_lane_preview.RECEIPT_SCHEMA,
        "fast_lane_preview_receipt_id": fast_receipt_id,
        "fast_lane_preview_result_id": fast_result_id,
        "fast_lane_preview_plan_id": fast_result["fast_lane_preview_plan_id"],
        "canonical_rule_id": rule["rule_id"],
        "document_id": rule["document_id"],
        "source_revision": rule["source_revision"],
        "certification_receipt_id": certification["certification_receipt_id"],
        "certification_fingerprint": fast_result["certification_fingerprint"],
        "fast_lane_contract_id": manifest["fast_lane_contract_id"],
        "fast_lane_contract_version": manifest["fast_lane_contract_version"],
        "fast_lane_capability_fingerprint": capability_fp,
        "compatibility_evaluator_fingerprint": evaluator_fp,
        "overall_compatibility": "compatible",
        "semantic_loss": "none",
        "preview_status": "completed",
        "summary_counts": {"compatible_dimension_count": 1, "warning_dimension_count": 0, "incompatible_dimension_count": 0},
        "result_fingerprint": fast_result["result_fingerprint"],
        "created_at_utc": "2026-01-01T00:00:00Z",
    }
    _write_json(root / fast_lane_preview.RESULT_DIR / f"{fast_result_id}.json", fast_result)
    _write_json(root / fast_lane_preview.RECEIPT_DIR / f"{fast_receipt_id}.json", fast_receipt)
    return {
        "rule_id": rule["rule_id"],
        "document_id": rule["document_id"],
        "objective_run": objective_run,
        "scoring_run": scoring_run,
        "fast_run": {"fast_lane_preview_result_id": fast_result_id, "fast_lane_preview_receipt_id": fast_receipt_id},
    }


class CertifiedRuleIntegrationAuthorizationTest(TestCase):
    def test_matching_current_phase_9p_and_9q_evidence_records_one_immutable_reviewed_decision(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9r_inputs(root)
            workspace = authorization.build_certified_rule_integration_authorization_workspace(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            eligibility = authorization.validate_certified_rule_integration_authorization_eligibility(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            plan = authorization.build_certified_rule_integration_authorization_plan(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            saved = authorization.save_certified_rule_integration_authorization_decision(
                plan["integration_authorization_plan_id"],
                "reviewer.alpha",
                "authorize_for_later_integration",
                "Evidence reviewed; keep later execution separate.",
                list(authorization.AUTHORIZE_ACKS),
                confirmation=authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
            rerun = authorization.save_certified_rule_integration_authorization_decision(
                plan["integration_authorization_plan_id"],
                "reviewer.alpha",
                "authorize_for_later_integration",
                "Evidence reviewed; keep later execution separate.",
                list(authorization.AUTHORIZE_ACKS),
                confirmation=authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
            loaded = authorization.load_certified_rule_integration_authorization_result(saved["integration_authorization_result_id"], root=root)
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(eligibility["status"], "eligible")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(saved["status"], "authorized")
        self.assertEqual(rerun["status"], "already_completed")
        self.assertEqual(rerun["writes_performed"], 0)
        self.assertFalse(loaded["integration_authorization_result"]["stale"])

    def test_stale_or_missing_evidence_blocks_authorization_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9r_inputs(root)
            manifest_path = root / "document_manifests" / f"{built['document_id']}.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_revision"] = 99
            _write_json(manifest_path, manifest)
            stale = authorization.validate_certified_rule_integration_authorization_eligibility(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            missing = authorization.validate_certified_rule_integration_authorization_eligibility(built["rule_id"], "missing_scoring", built["fast_run"]["fast_lane_preview_result_id"], root=root)
        self.assertEqual(stale["status"], "stale")
        self.assertIn("source_revision_not_current", stale["blockers"])
        self.assertIn("scoring_preview_result_missing", missing["blockers"])

    def test_authorize_requires_current_compatible_fast_lane_and_explicit_acknowledgements(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9r_inputs(root)
            fast_result_path = root / fast_lane_preview.RESULT_DIR / f"{fast_lane_preview.analysis_backend._safe_id(built['fast_run']['fast_lane_preview_result_id'])}.json"
            fast_receipt_path = root / fast_lane_preview.RECEIPT_DIR / f"{fast_lane_preview.analysis_backend._safe_id(built['fast_run']['fast_lane_preview_receipt_id'])}.json"
            fast_result = json.loads(fast_result_path.read_text(encoding="utf-8"))
            fast_receipt = json.loads(fast_receipt_path.read_text(encoding="utf-8"))
            fast_result["overall_compatibility"] = "incompatible"
            fast_result["semantic_loss"] = "confirmed"
            fast_receipt["result_fingerprint"] = fast_result["result_fingerprint"]
            _write_json(fast_result_path, fast_result)
            _write_json(fast_receipt_path, fast_receipt)
            plan = authorization.build_certified_rule_integration_authorization_plan(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            blocked = authorization.save_certified_rule_integration_authorization_decision(
                plan["integration_authorization_plan_id"],
                "reviewer.alpha",
                "authorize_for_later_integration",
                "Trying to approve incompatible evidence.",
                ["reviewed_scoring_preview"],
                confirmation=authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
            rejected = authorization.save_certified_rule_integration_authorization_decision(
                plan["integration_authorization_plan_id"],
                "reviewer.alpha",
                "reject_integration",
                "Compatibility is not sufficient.",
                ["reviewed_scoring_preview"],
                confirmation=authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
        self.assertIn("missing_acknowledgement:no_fast_lane_execution", blocked["blockers"])
        self.assertEqual(rejected["status"], "rejected")

    def test_authorization_is_read_only_with_respect_to_rule_scoring_and_fast_lane_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9r_inputs(root)
            rule_path = root / "canonical_rules" / f"{built['rule_id']}.json"
            scoring_path = root / scoring_preview.RESULT_DIR / f"{scoring_preview.analysis_backend._safe_id(built['scoring_run']['scoring_preview_result_id'])}.json"
            fast_path = root / fast_lane_preview.RESULT_DIR / f"{fast_lane_preview.analysis_backend._safe_id(built['fast_run']['fast_lane_preview_result_id'])}.json"
            rule_before = rule_path.read_text(encoding="utf-8")
            scoring_before = scoring_path.read_text(encoding="utf-8")
            fast_before = fast_path.read_text(encoding="utf-8")
            plan = authorization.build_certified_rule_integration_authorization_plan(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            authorization.save_certified_rule_integration_authorization_decision(
                plan["integration_authorization_plan_id"],
                "reviewer.alpha",
                "defer_integration",
                "Hold for later execution review.",
                ["reviewed_scoring_preview", "reviewed_fast_lane_preview"],
                confirmation=authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
            rule_after = rule_path.read_text(encoding="utf-8")
            scoring_after = scoring_path.read_text(encoding="utf-8")
            fast_after = fast_path.read_text(encoding="utf-8")
        self.assertEqual(rule_before, rule_after)
        self.assertEqual(scoring_before, scoring_after)
        self.assertEqual(fast_before, fast_after)

    def test_dependency_change_marks_authorization_result_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9r_inputs(root)
            plan = authorization.build_certified_rule_integration_authorization_plan(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            saved = authorization.save_certified_rule_integration_authorization_decision(
                plan["integration_authorization_plan_id"],
                "reviewer.alpha",
                "defer_integration",
                "Waiting for a later activation phase.",
                ["reviewed_scoring_preview", "reviewed_fast_lane_preview"],
                confirmation=authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
            manifest_path = root / "document_manifests" / f"{built['document_id']}.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_revision"] = 77
            _write_json(manifest_path, manifest)
            loaded = authorization.load_certified_rule_integration_authorization_result(saved["integration_authorization_result_id"], root=root)
            health = authorization.get_certified_rule_integration_authorization_health(plan["integration_authorization_plan_id"], root=root)
        self.assertTrue(loaded["integration_authorization_result"]["stale"])
        self.assertEqual(health["status"], "stale")

    def test_api_flow_and_public_report_are_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9r_inputs(root)
            workspace = api_workspace(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            eligibility = api_validate(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            plan = api_build_plan(built["rule_id"], built["scoring_run"]["scoring_preview_result_id"], built["fast_run"]["fast_lane_preview_result_id"], root=root)
            saved = api_save(
                plan["integration_authorization_plan_id"],
                "reviewer.alpha",
                "authorize_for_later_integration",
                "Read-only evidence approved for later gated execution.",
                list(authorization.AUTHORIZE_ACKS),
                confirmation=authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
            report = api_report(saved["integration_authorization_result_id"], saved["integration_authorization_receipt_id"], True, root=root)
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(eligibility["status"], "eligible")
        self.assertEqual(saved["status"], "authorized")
        self.assertIn("Certified Rule Integration Authorization", report)
        self.assertIn("no Fast Lane, production scoring, or activation was performed", report)
        self.assertNotIn(str(root), report)
