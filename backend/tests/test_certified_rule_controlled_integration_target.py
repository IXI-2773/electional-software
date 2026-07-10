from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import certified_rule_controlled_integration_target as target


def _package(target_id: str = target.DEFAULT_TARGET_ID, package_id: str = "pkg_021", rule_id: str = "rule_021") -> dict[str, object]:
    payload = {
        "schema_version": target.PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "target_id": target_id,
        "canonical_rule_id": rule_id,
        "canonical_rule_schema_version": "canonical_mutable_rule_v1",
        "canonical_rule_fingerprint": "sha256:" + "1" * 64,
        "document_id": "doc_021",
        "source_revision": "source_rev_021",
        "certification_id": "cert_021",
        "certification_fingerprint": "sha256:" + "2" * 64,
        "release_candidate_result_id": "release_021",
        "release_candidate_fingerprint": "sha256:" + "3" * 64,
        "authorization_result_id": "auth_021",
        "authorization_fingerprint": "sha256:" + "4" * 64,
        "scoring_preview_result_id": "score_021",
        "scoring_config_id": "score_cfg_021",
        "scoring_config_fingerprint": "sha256:" + "5" * 64,
        "fast_lane_preview_result_id": "fast_021",
        "fast_lane_contract_id": "fast_contract_021",
        "fast_lane_contract_version": "v1",
        "fast_lane_capability_fingerprint": "sha256:" + "6" * 64,
    }
    payload["package_fingerprint"] = target._integration_package_fingerprint(payload)
    return payload


class ControlledIntegrationTargetTest(TestCase):
    def test_adapter_manifest_and_target_workspace_are_stable_and_non_production(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            first = target.get_controlled_integration_adapter_manifest(root=root)
            second = target.get_controlled_integration_adapter_manifest(root=root)
            workspace = target.get_isolated_controlled_integration_target_workspace(target.DEFAULT_TARGET_ID, root=root)
        self.assertEqual(first["adapter_manifest"]["environment_class"], "isolated_non_production")
        self.assertEqual(first["adapter_manifest"]["adapter_fingerprint"], second["adapter_manifest"]["adapter_fingerprint"])
        self.assertEqual(workspace["environment_class"], "isolated_non_production")
        self.assertEqual(workspace["pending_transaction_count"], 0)

    def test_package_validation_and_transaction_preflight_are_deterministic_and_read_only(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            target.get_controlled_integration_target_manifest(target.DEFAULT_TARGET_ID, root=root)
            target_dir = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID
            target_dir_exists = target_dir.exists()
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            validation = target.validate_controlled_integration_package(target.DEFAULT_TARGET_ID, package, root=root)
            preflight_one = target.preflight_controlled_integration_transaction(target.DEFAULT_TARGET_ID, package, root=root)
            preflight_two = target.preflight_controlled_integration_transaction(target.DEFAULT_TARGET_ID, package, root=root)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
        self.assertTrue(validation["valid"])
        self.assertEqual(preflight_one["status"], "ready")
        self.assertEqual(preflight_one["transaction_id"], preflight_two["transaction_id"])
        self.assertEqual(preflight_one["namespace_id"], preflight_two["namespace_id"])
        self.assertEqual(before, after)
        self.assertTrue(target_dir_exists)

    def test_transaction_apply_writes_pending_state_only(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            applied = target.apply_controlled_integration_transaction(target.DEFAULT_TARGET_ID, package, confirmation="APPLY_ISOLATED_INTEGRATION_TRANSACTION", root=root)
            pending_path = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "pending" / f"{applied['transaction_id']}.json"
            committed_path = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "namespaces" / f"{applied['namespace_id']}.json"
            tx_path = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "transactions" / f"{applied['transaction_id']}.json"
            pending_exists = pending_path.exists()
            committed_exists = committed_path.exists()
            tx_payload = json.loads(tx_path.read_text(encoding="utf-8"))
        self.assertEqual(applied["status"], "pending_verification")
        self.assertTrue(pending_exists)
        self.assertFalse(committed_exists)
        self.assertEqual(tx_payload["transaction_state"], "pending_verification")

    def test_independent_pending_readback_is_required_before_commit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            applied = target.apply_controlled_integration_transaction(target.DEFAULT_TARGET_ID, package, confirmation="APPLY_ISOLATED_INTEGRATION_TRANSACTION", root=root)
            pending = target.read_controlled_integration_target_state(target.DEFAULT_TARGET_ID, transaction_id=applied["transaction_id"], root=root)
            pending_path = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "pending" / f"{applied['transaction_id']}.json"
            payload = json.loads(pending_path.read_text(encoding="utf-8"))
            payload["package_fingerprint"] = "sha256:" + "9" * 64
            _write_json(pending_path, payload)
            blocked = target.commit_controlled_integration_transaction(target.DEFAULT_TARGET_ID, applied["transaction_id"], str(pending["state_fingerprint"]), confirmation="COMMIT_ISOLATED_INTEGRATION_TRANSACTION", root=root)
        self.assertEqual(pending["verification_status"], "verified_pending")
        self.assertEqual(blocked["status"], "verification_failed")

    def test_explicit_commit_creates_verified_staged_namespace(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            applied = target.apply_controlled_integration_transaction(target.DEFAULT_TARGET_ID, package, confirmation="APPLY_ISOLATED_INTEGRATION_TRANSACTION", root=root)
            pending = target.read_controlled_integration_target_state(target.DEFAULT_TARGET_ID, transaction_id=applied["transaction_id"], root=root)
            committed = target.commit_controlled_integration_transaction(target.DEFAULT_TARGET_ID, applied["transaction_id"], str(pending["state_fingerprint"]), confirmation="COMMIT_ISOLATED_INTEGRATION_TRANSACTION", root=root)
            committed_state = target.read_controlled_integration_target_state(target.DEFAULT_TARGET_ID, namespace_id=applied["namespace_id"], root=root)
        self.assertEqual(committed["status"], "committed")
        self.assertEqual(committed_state["verification_status"], "verified_committed")
        self.assertEqual(committed_state["transaction_state"], "committed")

    def test_conflicts_invalid_transitions_and_fingerprint_mismatches_are_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            applied = target.apply_controlled_integration_transaction(target.DEFAULT_TARGET_ID, package, confirmation="APPLY_ISOLATED_INTEGRATION_TRANSACTION", root=root)
            conflict = target.preflight_controlled_integration_transaction(target.DEFAULT_TARGET_ID, _package(package_id="pkg_022"), root=root)
            blocked_commit = target.commit_controlled_integration_transaction(target.DEFAULT_TARGET_ID, applied["transaction_id"], "sha256:" + "8" * 64, confirmation="COMMIT_ISOLATED_INTEGRATION_TRANSACTION", root=root)
        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(blocked_commit["status"], "conflict")

    def test_transactional_rollback_removes_only_owned_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package_one = _package(package_id="pkg_031", rule_id="rule_031")
            package_two = _package(package_id="pkg_032", rule_id="rule_032")
            applied_one = target.apply_controlled_integration_transaction(target.DEFAULT_TARGET_ID, package_one, confirmation="APPLY_ISOLATED_INTEGRATION_TRANSACTION", root=root)
            pending_one = target.read_controlled_integration_target_state(target.DEFAULT_TARGET_ID, transaction_id=applied_one["transaction_id"], root=root)
            target.commit_controlled_integration_transaction(target.DEFAULT_TARGET_ID, applied_one["transaction_id"], str(pending_one["state_fingerprint"]), confirmation="COMMIT_ISOLATED_INTEGRATION_TRANSACTION", root=root)
            applied_two = target.apply_controlled_integration_transaction(target.DEFAULT_TARGET_ID, package_two, confirmation="APPLY_ISOLATED_INTEGRATION_TRANSACTION", root=root)
            rolled = target.rollback_controlled_integration_transaction(target.DEFAULT_TARGET_ID, applied_two["transaction_id"], confirmation="ROLLBACK_ISOLATED_INTEGRATION_TRANSACTION", root=root)
            committed_one = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "namespaces" / f"{applied_one['namespace_id']}.json"
            committed_two = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "namespaces" / f"{applied_two['namespace_id']}.json"
            committed_one_exists = committed_one.exists()
            committed_two_exists = committed_two.exists()
        self.assertEqual(rolled["status"], "completed")
        self.assertTrue(committed_one_exists)
        self.assertFalse(committed_two_exists)

    def test_existing_adapter_functions_remain_compatible_and_no_production_state_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = {
                "target_id": target.DEFAULT_TARGET_ID,
                "isolated_namespace_id": "ns_legacy_021",
                "canonical_rule_id": "rule_legacy_021",
                "canonical_rule_fingerprint": "sha256:" + "1" * 64,
                "rule_schema_version": "canonical_mutable_rule_v1",
                "document_id": "doc_legacy_021",
                "source_revision": "source_rev_legacy_021",
            }
            package["execution_package_fingerprint"] = target._execution_package_fingerprint(package)
            applied = target.apply_controlled_integration_rule(target.DEFAULT_TARGET_ID, package, root=root)
            verified = target.verify_controlled_integration_rule(target.DEFAULT_TARGET_ID, package["isolated_namespace_id"], package["execution_package_fingerprint"], root=root)
            health = target.get_controlled_integration_target_health(target.DEFAULT_TARGET_ID, root=root)
            rolled = target.rollback_controlled_integration_rule(target.DEFAULT_TARGET_ID, package["isolated_namespace_id"], root=root)
            manifest = target.get_controlled_integration_target_manifest(target.DEFAULT_TARGET_ID, root=root)
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(health["environment_class"], "isolated_non_production")
        self.assertEqual(rolled["status"], "completed")
        self.assertEqual(manifest["manifest"]["environment_class"], "isolated_non_production")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
