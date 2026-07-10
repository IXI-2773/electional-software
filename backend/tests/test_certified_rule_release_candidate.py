from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import certified_rule_integration_authorization as authorization
from backend.electional import certified_rule_fast_lane_preview as fast_lane_preview
from backend.electional import certified_rule_release_candidate as release_candidate
from backend.electional import certified_rule_scoring_preview as scoring_preview
from backend.electional.api import (
    build_certified_rule_release_candidate_plan as api_build_plan,
    build_certified_rule_release_candidate_workspace as api_workspace,
    format_certified_rule_release_candidate_report as api_report,
    qualify_certified_rule_release_candidate as api_qualify,
    validate_certified_rule_release_candidate_eligibility as api_validate,
)
from backend.tests.test_certified_rule_integration_authorization import _build_phase_9r_inputs, _write_json


def _build_phase_9s_inputs(root: Path) -> dict[str, object]:
    built = _build_phase_9r_inputs(root)
    auth_plan = authorization.build_certified_rule_integration_authorization_plan(
        built["rule_id"],
        built["scoring_run"]["scoring_preview_result_id"],
        built["fast_run"]["fast_lane_preview_result_id"],
        root=root,
    )
    auth_saved = authorization.save_certified_rule_integration_authorization_decision(
        auth_plan["integration_authorization_plan_id"],
        "reviewer.alpha",
        "authorize_for_later_integration",
        "Evidence chain reviewed for later controlled integration.",
        list(authorization.AUTHORIZE_ACKS),
        confirmation=authorization.REQUIRED_CONFIRMATION,
        root=root,
    )
    built["authorization_plan"] = auth_plan
    built["authorization_saved"] = auth_saved
    return built


class CertifiedRuleReleaseCandidateTest(TestCase):
    def test_current_authorized_package_qualifies_and_rerun_is_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9s_inputs(root)
            workspace = release_candidate.build_certified_rule_release_candidate_workspace(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
            eligibility = release_candidate.validate_certified_rule_release_candidate_eligibility(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
            plan = release_candidate.build_certified_rule_release_candidate_plan(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
            run = release_candidate.qualify_certified_rule_release_candidate(plan["release_candidate_plan_id"], confirmation=release_candidate.REQUIRED_CONFIRMATION, root=root)
            rerun = release_candidate.qualify_certified_rule_release_candidate(plan["release_candidate_plan_id"], confirmation=release_candidate.REQUIRED_CONFIRMATION, root=root)
            loaded = release_candidate.load_certified_rule_release_candidate_result(run["release_candidate_result_id"], root=root)
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertIn(eligibility["status"], {"eligible", "eligible_with_warnings"})
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(run["status"], "qualified")
        self.assertEqual(rerun["status"], "already_qualified")
        self.assertEqual(rerun["writes_performed"], 0)
        self.assertFalse(loaded["release_candidate_result"]["stale"])

    def test_pending_rule_rollback_makes_candidate_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9s_inputs(root)
            rule_path = root / "canonical_rules" / f"{built['rule_id']}.json"
            rule_payload = json.loads(rule_path.read_text(encoding="utf-8"))
            rule_payload["rollback_pending"] = True
            _write_json(rule_path, rule_payload)
            eligibility = release_candidate.validate_certified_rule_release_candidate_eligibility(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
            plan = release_candidate.build_certified_rule_release_candidate_plan(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
        self.assertEqual(eligibility["status"], "stale")
        self.assertEqual(plan["status"], "stale")
        self.assertIn("rule_has_pending_rollback", [code for gate in eligibility["gate_previews"] for code in gate.get("blocker_codes", [])])

    def test_source_revision_drift_makes_candidate_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9s_inputs(root)
            manifest_path = root / "document_manifests" / f"{built['document_id']}.json"
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_payload["source_revision"] = 99
            _write_json(manifest_path, manifest_payload)
            eligibility = release_candidate.validate_certified_rule_release_candidate_eligibility(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
            plan = release_candidate.build_certified_rule_release_candidate_plan(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
        self.assertEqual(eligibility["status"], "stale")
        self.assertEqual(plan["status"], "stale")

    def test_qualification_does_not_mutate_authorized_or_preview_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9s_inputs(root)
            plan = release_candidate.build_certified_rule_release_candidate_plan(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
            rule_path = root / "canonical_rules" / f"{built['rule_id']}.json"
            auth_path = root / authorization.RESULT_DIR / f"{authorization.analysis_backend._safe_id(built['authorization_saved']['integration_authorization_result_id'])}.json"
            scoring_path = root / "certified_rule_scoring_preview_results" / f"{scoring_preview.analysis_backend._safe_id(built['scoring_run']['scoring_preview_result_id'])}.json"
            fast_path = root / "certified_rule_fast_lane_preview_results" / f"{fast_lane_preview.analysis_backend._safe_id(built['fast_run']['fast_lane_preview_result_id'])}.json"
            before = {path: path.read_text(encoding="utf-8") for path in (rule_path, auth_path, scoring_path, fast_path)}
            release_candidate.qualify_certified_rule_release_candidate(plan["release_candidate_plan_id"], confirmation=release_candidate.REQUIRED_CONFIRMATION, root=root)
            after = {path: path.read_text(encoding="utf-8") for path in (rule_path, auth_path, scoring_path, fast_path)}
        self.assertEqual(before, after)

    def test_api_flow_health_summary_and_public_report_are_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9s_inputs(root)
            workspace = api_workspace(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
            eligibility = api_validate(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
            plan = api_build_plan(built["rule_id"], built["authorization_saved"]["integration_authorization_result_id"], root=root)
            run = api_qualify(plan["release_candidate_plan_id"], confirmation=release_candidate.REQUIRED_CONFIRMATION, root=root)
            health = release_candidate.get_certified_rule_release_candidate_health(plan["release_candidate_plan_id"], root=root)
            summary = release_candidate.get_certified_rule_release_candidate_summary(run["release_candidate_result_id"], root=root)
            report = api_report(run["release_candidate_result_id"], run["release_candidate_receipt_id"], True, root=root)
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertIn(eligibility["status"], {"eligible", "eligible_with_warnings"})
        self.assertEqual(run["status"], "qualified")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(summary["status"], "qualified")
        self.assertIn("Certified Rule Release Candidate Qualification", report)
        self.assertIn("no activation, Fast Lane execution, or production scoring was performed", report)
        self.assertNotIn(str(root), report)
