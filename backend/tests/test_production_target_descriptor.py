from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import production_target_descriptor as descriptor_backend


def _descriptor(target_id: str = "production_target_primary") -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": descriptor_backend.DESCRIPTOR_SCHEMA_VERSION,
        "target_id": target_id,
        "environment_class": "production",
        "target_kind": descriptor_backend.TARGET_KIND,
        "adapter_name": "authoritative_production_adapter",
        "adapter_version": "1",
        "adapter_manifest": {
            "schema_version": descriptor_backend.MANIFEST_SCHEMA_VERSION,
            "adapter_name": "authoritative_production_adapter",
            "adapter_version": "1",
        },
        "adapter_capabilities": {
            "schema_version": descriptor_backend.CAPABILITIES_SCHEMA_VERSION,
            "capabilities": ["describe_target", "read_release_state"],
        },
        "descriptor_access_mode": descriptor_backend.ACCESS_MODE,
        "authorization_scope": descriptor_backend.AUTHORIZATION_SCOPE,
        "operational_entrypoints_exposed": [],
        "deployment_executed": False,
        "activation_executed": False,
        "production_scoring_executed": False,
        "live_fast_lane_executed": False,
    }
    normalized = descriptor_backend._normalize_descriptor(payload)
    assert normalized is not None
    return normalized


class ProductionTargetDescriptorTest(TestCase):
    def test_validate_computes_deterministic_manifest_capability_and_descriptor_fingerprints(self) -> None:
        first = descriptor_backend.get_production_target_descriptor_fingerprint(_descriptor())
        second = descriptor_backend.get_production_target_descriptor_fingerprint(_descriptor())
        self.assertEqual(first["status"], "computed")
        self.assertEqual(first["adapter_manifest_fingerprint"], second["adapter_manifest_fingerprint"])
        self.assertEqual(first["adapter_capability_fingerprint"], second["adapter_capability_fingerprint"])
        self.assertEqual(first["descriptor_fingerprint"], second["descriptor_fingerprint"])

    def test_register_persists_one_immutable_descriptor_and_index(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            registered = descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            loaded = descriptor_backend.load_production_target_descriptor("production_target_primary", root=root)
            index = json.loads((root / "indexes" / descriptor_backend.DESCRIPTOR_INDEX).read_text(encoding="utf-8"))
        self.assertEqual(registered["status"], "registered")
        self.assertEqual(registered["writes_performed"], 1)
        self.assertEqual(loaded["status"], "loaded")
        self.assertEqual(index["items"][0]["target_id"], "production_target_primary")

    def test_identical_reregister_is_idempotent_and_different_descriptor_conflicts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            first = descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            second = descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            conflicting_descriptor = {
                "schema_version": descriptor_backend.DESCRIPTOR_SCHEMA_VERSION,
                "target_id": "production_target_primary",
                "environment_class": "production",
                "target_kind": descriptor_backend.TARGET_KIND,
                "adapter_name": "authoritative_production_adapter",
                "adapter_version": "2",
                "adapter_manifest": {
                    "schema_version": descriptor_backend.MANIFEST_SCHEMA_VERSION,
                    "adapter_name": "authoritative_production_adapter",
                    "adapter_version": "2",
                },
                "adapter_capabilities": {
                    "schema_version": descriptor_backend.CAPABILITIES_SCHEMA_VERSION,
                    "capabilities": ["describe_target", "read_release_state"],
                },
                "descriptor_access_mode": descriptor_backend.ACCESS_MODE,
                "authorization_scope": descriptor_backend.AUTHORIZATION_SCOPE,
                "operational_entrypoints_exposed": [],
                "deployment_executed": False,
                "activation_executed": False,
                "production_scoring_executed": False,
                "live_fast_lane_executed": False,
            }
            normalized = descriptor_backend._normalize_descriptor(conflicting_descriptor)
            assert normalized is not None
            conflict = descriptor_backend.register_production_target_descriptor(normalized, root=root)
        self.assertEqual(first["status"], "registered")
        self.assertEqual(second["writes_performed"], 0)
        self.assertEqual(conflict["status"], "conflict")

    def test_invalid_environment_execution_flags_and_operational_entrypoints_are_blocked(self) -> None:
        descriptor = _descriptor()
        descriptor["environment_class"] = "isolated_non_production"
        descriptor["operational_entrypoints_exposed"] = ["deploy"]
        descriptor["deployment_executed"] = True
        result = descriptor_backend.validate_production_target_descriptor(descriptor)
        self.assertFalse(result["valid"])
        self.assertIn("production_target_environment_invalid", result["blockers"])
        self.assertIn("production_target_operational_entrypoints_forbidden", result["blockers"])
        self.assertIn("deployment_executed_must_be_false", result["blockers"])

    def test_load_reports_corrupt_descriptor_without_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            registered = descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            path = root / descriptor_backend.DESCRIPTOR_DIR / "production_target_primary.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["descriptor_fingerprint"] = "sha256:" + "0" * 64
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            loaded = descriptor_backend.load_production_target_descriptor("production_target_primary", root=root)
        self.assertEqual(registered["status"], "registered")
        self.assertEqual(loaded["status"], "corrupt")
        self.assertIn("production_target_descriptor_fingerprint_mismatch", loaded["blockers"])

    def test_health_detects_missing_or_stale_index(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            healthy = descriptor_backend.get_production_target_descriptor_health(root=root)
            index_path = root / "indexes" / descriptor_backend.DESCRIPTOR_INDEX
            index_payload = json.loads(index_path.read_text(encoding="utf-8"))
            index_payload["items"] = []
            index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")
            stale = descriptor_backend.get_production_target_descriptor_health(root=root)
        self.assertEqual(healthy["status"], "healthy")
        self.assertEqual(stale["status"], "warning")
        self.assertIn("production_target_descriptor_index_stale", stale["warnings"])

    def test_report_is_public_safe_and_read_only(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            report = descriptor_backend.format_production_target_descriptor_report("production_target_primary", root=root)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
        self.assertEqual(before, after)
        self.assertIn("No production target connection was attempted.", report)
        self.assertNotIn("\\", report)
        self.assertNotIn("C:", report)
