from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.document_manifest import build_document_manifest
from backend.electional.evidence_binder import build_evidence_binder
from backend.electional.locator_migration_planner import (
    audit_document_locator_contracts,
    build_locator_migration_plan,
    format_locator_migration_report,
    get_locator_migration_health,
    preview_locator_correction,
    validate_locator_correction_proposal,
)
from backend.electional.proposal_review import update_proposal_review_status
from backend.electional.source_knowledge import create_manual_proposal, create_source_citation
from backend.tests.test_document_content_curation import _build_detected_map, _write_chunk


def _first_citation_item(audit: dict) -> dict:
    return next(item for item in audit.get("items", []) if item.get("record_type") == "citation")


class LocatorMigrationPlannerTest(TestCase):
    def test_valid_locator_requires_no_proposal(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "normal note", root=root / "store")
            audit = audit_document_locator_contracts(record.document_id, root=root / "store")
            item = next(item for item in audit["items"] if item["record_id"] == citation.citation_id)
            self.assertEqual(item["locator_status"], "valid")
            plan = build_locator_migration_plan(record.document_id, root=root / "store")["plan"]
            proposal = next(item for item in plan["proposals"] if item["record_id"] == citation.citation_id)
            self.assertEqual(proposal["classification"], "already_valid")

    def test_stale_revision_locator_detected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "stale note", root=root / "store")
            path = root / "store" / "citations" / f"{citation.citation_id}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["source_revision"] = 1
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            manifest_path = root / "store" / "indexes" / f"{record.document_id}.json"
            if manifest_path.exists():
                manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_payload["sha256"] = "changed"
                manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            audit = audit_document_locator_contracts(record.document_id, root=root / "store")
            item = next(item for item in audit["items"] if item["record_id"] == citation.citation_id)
            self.assertEqual(item["locator_status"], "stale_revision")

    def test_unique_exact_candidate_creates_safe_proposal(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "move me", root=root / "store")
            path = root / "store" / "citations" / f"{citation.citation_id}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["source_revision"] = 1
            payload["chunk_id"] = "chunk_old_014_001"
            payload["page_start"] = 1
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            manifest_path = root / "store" / "indexes" / f"{record.document_id}.json"
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_payload["sha256"] = "changed"
            manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            plan = build_locator_migration_plan(record.document_id, scope="stale_only", root=root / "store")["plan"]
            proposal = next(item for item in plan["proposals"] if item["record_id"] == citation.citation_id)
            self.assertEqual(proposal["classification"], "safe_candidate")
            self.assertEqual(proposal["reason"], "unique_page_offset_match")
            self.assertFalse(proposal["apply_allowed"])

    def test_multiple_candidates_require_manual_review(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0004", 4, 1, 1, "same page duplicate")
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "ambiguous note", root=root / "store")
            path = root / "store" / "citations" / f"{citation.citation_id}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["chunk_id"] = "chunk_old_missing"
            payload["page_start"] = 1
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            audit = audit_document_locator_contracts(record.document_id, root=root / "store")
            item = next(item for item in audit["items"] if item["record_id"] == citation.citation_id)
            self.assertEqual(item["candidate_status"], "ambiguous")
            plan = build_locator_migration_plan(record.document_id, scope="stale_only", root=root / "store")["plan"]
            proposal = next(item for item in plan["proposals"] if item["record_id"] == citation.citation_id)
            self.assertEqual(proposal["classification"], "manual_review")

    def test_cross_document_candidate_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "cross note", root=root / "store")
            path = root / "store" / "citations" / f"{citation.citation_id}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["document_id"] = "other_doc"
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            audit = audit_document_locator_contracts(record.document_id, root=root / "store")
            item = next(item for item in audit["items"] if item["record_id"] == citation.citation_id)
            self.assertEqual(item["locator_status"], "cross_document_reference")
            plan = build_locator_migration_plan(record.document_id, scope="critical_only", root=root / "store")["plan"]
            proposal = next(item for item in plan["proposals"] if item["record_id"] == citation.citation_id)
            self.assertEqual(proposal["classification"], "blocked")

    def test_dependency_impact_includes_linked_records(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "proposal link", root=root / "store")
            proposal = create_manual_proposal(record.document_id, f"chunk_{record.document_id}_0001", "Manual proposal", root=root / "store")
            update_proposal_review_status(proposal.proposal_id, "in_review", "not_decided", root=root / "store")
            build_evidence_binder(proposal.proposal_id, regenerate=True, root=root / "store")
            path = root / "store" / "citations" / f"{citation.citation_id}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["chunk_id"] = "chunk_old_missing"
            payload["page_start"] = 1
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            plan = build_locator_migration_plan(record.document_id, scope="stale_only", root=root / "store")["plan"]
            proposal_item = next(item for item in plan["proposals"] if item["record_id"] == citation.citation_id)
            impact = proposal_item["dependency_impact"]
            self.assertGreaterEqual(impact["proposal_count"], 1)
            self.assertGreaterEqual(impact["proposal_review_count"], 1)
            self.assertGreaterEqual(impact["evidence_binder_count"], 1)

    def test_preview_does_not_mutate_records(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "preview note", root=root / "store")
            path = root / "store" / "citations" / f"{citation.citation_id}.json"
            before_bytes = path.read_bytes()
            payload = json.loads(before_bytes.decode("utf-8"))
            payload["chunk_id"] = "chunk_old_missing"
            payload["page_start"] = 1
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            plan = build_locator_migration_plan(record.document_id, scope="stale_only", root=root / "store")["plan"]
            proposal_item = next(item for item in plan["proposals"] if item["record_id"] == citation.citation_id)
            mid_bytes = path.read_bytes()
            preview = preview_locator_correction(plan["migration_plan_id"], proposal_item["proposal_id"], root=root / "store")
            after_bytes = path.read_bytes()
            self.assertEqual(mid_bytes, after_bytes)
            self.assertEqual(preview["actually_modified"], [])
            self.assertFalse(preview["apply_allowed"])

    def test_plan_becomes_stale_when_source_revision_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            plan = build_locator_migration_plan(record.document_id, root=root / "store")["plan"]
            manifest_path = root / "store" / "indexes" / f"{record.document_id}.json"
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_payload["sha256"] = "changed_again"
            manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            loaded = api.load_locator_migration_plan(plan["migration_plan_id"], root=root / "store")
            self.assertEqual(loaded["status"], "stale")

    def test_public_report_hides_private_paths_and_text(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "C:/private/source.pdf token=abc", quote_excerpt="secret quoted text", root=root / "store")
            path = root / "store" / "citations" / f"{citation.citation_id}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["chunk_id"] = "chunk_old_missing"
            payload["page_start"] = 1
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            plan = build_locator_migration_plan(record.document_id, scope="stale_only", root=root / "store")["plan"]
            report = format_locator_migration_report(document_id=record.document_id, migration_plan_id=plan["migration_plan_id"], public_safe=True, root=root / "store")
            self.assertNotIn("C:/private/source.pdf", report)
            self.assertNotIn("secret quoted text", report)
            self.assertNotIn("token=abc", report)

    def test_api_locator_migration_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "api note", root=root / "store")
            path = root / "store" / "citations" / f"{citation.citation_id}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["chunk_id"] = "chunk_old_missing"
            payload["page_start"] = 1
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            audit = api.audit_document_locator_contracts(record.document_id, root=root / "store")
            built = api.build_locator_migration_plan(record.document_id, scope="stale_only", root=root / "store")
            proposal_item = built["plan"]["proposals"][0]
            preview = api.preview_locator_correction(built["migration_plan_id"], proposal_item["proposal_id"], root=root / "store")
            report = api.format_locator_migration_report(document_id=record.document_id, migration_plan_id=built["migration_plan_id"], root=root / "store")
            validation = validate_locator_correction_proposal(built["migration_plan_id"], proposal_item["proposal_id"], root=root / "store")
            health = get_locator_migration_health(record.document_id, root=root / "store")
            self.assertGreaterEqual(audit["records_checked"], 1)
            self.assertEqual(built["status"], "planned")
            self.assertIn(preview["classification"], {"safe_candidate", "manual_review", "blocked", "already_valid"})
            self.assertIn("Locator Migration Plan Report", report)
            self.assertFalse(validation["apply_allowed"])
            self.assertIn(health["status"], {"healthy", "warning", "critical", "stale"})
