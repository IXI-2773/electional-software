from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import canonical_rule_runtime as runtime
from backend.electional import production_activation_transaction as tx_backend
from backend.electional import production_deployment_adapter as adapter
from backend.electional import production_target_descriptor as descriptor_backend


def _descriptor() -> dict[str, object]:
    manifest = {
        "schema_version": descriptor_backend.MANIFEST_SCHEMA_VERSION,
        "adapter_name": "ProductionTargetAdapter",
        "adapter_version": "1",
        "deployment_mode": "authorized_later_only",
    }
    capabilities = {
        "schema_version": descriptor_backend.CAPABILITIES_SCHEMA_VERSION,
        "capabilities": ["read_only_descriptor", "production_metadata"],
    }
    payload = {
        "schema_version": descriptor_backend.DESCRIPTOR_SCHEMA_VERSION,
        "target_id": "production_target_primary",
        "environment_class": "production",
        "target_kind": descriptor_backend.TARGET_KIND,
        "adapter_name": "ProductionTargetAdapter",
        "adapter_version": "1",
        "adapter_manifest": manifest,
        "adapter_capabilities": capabilities,
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


def _deployment_package() -> dict[str, object]:
    rule_payload = {
        "schema_version": runtime.CANONICAL_RULE_SCHEMA_VERSION,
        "rule_id": "rule_prod_deploy_001",
        "rule_type": "threshold",
        "target": "score",
        "scope": "document",
        "condition": {"field": "score", "operator": "greater_than", "value": 5},
        "operator": "greater_than",
        "value": 9,
        "priority": 50,
        "enabled": True,
        "status": "active",
        "document_id": "document_001",
        "source_proposal_id": "production_deployment_seed",
        "source_revision": "1",
    }
    descriptor = _descriptor()
    manifest = adapter.get_production_deployment_adapter_manifest()
    package = {
        "schema_version": adapter.DEPLOYMENT_PACKAGE_SCHEMA_VERSION,
        "package_id": "production_deployment_package_001",
        "canonical_rule_id": "rule_prod_deploy_001",
        "canonical_rule_schema_version": runtime.CANONICAL_RULE_SCHEMA_VERSION,
        "canonical_rule_fingerprint": runtime._rule_fingerprint_from_payload(rule_payload),
        "canonical_rule_payload": rule_payload,
        "document_id": "document_001",
        "source_revision": 1,
        "certification_id": "certification_001",
        "certification_fingerprint": "sha256:certification_001",
        "controlled_integration_result_id": "integration_result_001",
        "controlled_integration_fingerprint": "sha256:integration_result_001",
        "isolated_committed_state_fingerprint": "sha256:isolated_state_001",
        "production_authorization_result_id": "authorization_result_001",
        "production_authorization_fingerprint": "sha256:authorization_result_001",
        "production_target_id": "production_target_primary",
        "production_target_descriptor_fingerprint": descriptor["descriptor_fingerprint"],
        "production_adapter_manifest_fingerprint": descriptor["adapter_manifest_fingerprint"],
        "production_adapter_capability_fingerprint": descriptor["adapter_capability_fingerprint"],
        "deployment_adapter_fingerprint": manifest["adapter_fingerprint"],
    }
    package["package_fingerprint"] = adapter._deployment_package_fingerprint(package)
    return package


def _create_source_rule(root: Path, package: dict[str, object]) -> None:
    created = runtime.create_canonical_rule(dict(package["canonical_rule_payload"]), confirmation="CREATE_RULE", root=root)
    assert created["status"] in {"created", "already_created"}


class ProductionDeploymentAdapterTest(TestCase):
    def test_adapter_manifest_and_target_workspace_bind_real_foundations(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            manifest = adapter.get_production_deployment_adapter_manifest(root=root)
            workspace = adapter.get_production_deployment_target_workspace("production_target_primary", root=root)
        self.assertEqual(manifest["environment_class"], "production")
        self.assertEqual(manifest["authoritative_state_owner"], "canonical_rule_runtime")
        self.assertEqual(manifest["transaction_foundation_module"], "production_activation_transaction")
        self.assertEqual(workspace["status"], "healthy")
        self.assertEqual(workspace["environment_class"], "production")
        self.assertEqual(workspace["target_kind"], descriptor_backend.TARGET_KIND)

    def test_deployment_package_validation_and_transaction_binding_are_deterministic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            package = _deployment_package()
            _create_source_rule(root, package)
            first = adapter.validate_production_deployment_package("production_target_primary", package, root=root)
            second = adapter.validate_production_deployment_package("production_target_primary", package, root=root)
        self.assertEqual(first["status"], "valid")
        self.assertEqual(first["package_fingerprint"], second["package_fingerprint"])
        self.assertEqual(first["transaction_package_fingerprint"], second["transaction_package_fingerprint"])

    def test_preflight_is_read_only_and_preserves_transaction_identity(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            package = _deployment_package()
            _create_source_rule(root, package)
            before_rules = sorted(str(path.relative_to(root)) for path in (root / runtime.CANONICAL_RULE_DIR).glob("*.json"))
            first = adapter.preflight_production_deployment("production_target_primary", package, root=root)
            second = adapter.preflight_production_deployment("production_target_primary", package, root=root)
            rules = sorted(str(path.relative_to(root)) for path in (root / runtime.CANONICAL_RULE_DIR).glob("*.json"))
            pending = list((root / tx_backend.TRANSACTION_DIR / tx_backend.PENDING_DIR).glob("*.json"))
        self.assertEqual(first["status"], "ready")
        self.assertEqual(first["transaction_id"], second["transaction_id"])
        self.assertEqual(rules, before_rules)
        self.assertEqual(pending, [])

    def test_apply_creates_pending_state_without_creating_canonical_rule(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            package = _deployment_package()
            _create_source_rule(root, package)
            blocked = adapter.apply_production_deployment("production_target_primary", package, confirmation=None, root=root)
            applied = adapter.apply_production_deployment("production_target_primary", package, confirmation=adapter.APPLY_CONFIRMATION, root=root)
            loaded_rule = runtime.load_canonical_rule(str(package["canonical_rule_id"]), root=root)
            deployed_rule = runtime.load_canonical_rule(tx_backend._deployed_rule_id(adapter._to_transaction_package(package, adapter.get_production_deployment_target_workspace("production_target_primary", root=root)), applied["transaction_id"]), root=root)
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(applied["status"], "pending_verification")
        self.assertEqual(loaded_rule["status"], "loaded")
        self.assertEqual(deployed_rule["status"], "not_found")

    def test_verification_independently_reads_pending_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            package = _deployment_package()
            _create_source_rule(root, package)
            applied = adapter.apply_production_deployment("production_target_primary", package, confirmation=adapter.APPLY_CONFIRMATION, root=root)
            verified = adapter.verify_production_deployment("production_target_primary", applied["transaction_id"], root=root)
            record_path = root / tx_backend.TRANSACTION_DIR / tx_backend.RECORD_DIR / f"{applied['transaction_id']}.json"
            payload = json.loads(record_path.read_text(encoding="utf-8"))
            payload["pending_state_fingerprint"] = "sha256:drift"
            record_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            drifted = adapter.verify_production_deployment("production_target_primary", applied["transaction_id"], root=root)
        self.assertEqual(verified["status"], "verified_pending")
        self.assertEqual(drifted["status"], "verification_failed")

    def test_commit_creates_and_independently_verifies_exact_canonical_rule(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            package = _deployment_package()
            _create_source_rule(root, package)
            applied = adapter.apply_production_deployment("production_target_primary", package, confirmation=adapter.APPLY_CONFIRMATION, root=root)
            with patch.object(tx_backend, "create_canonical_rule", wraps=tx_backend.create_canonical_rule) as wrapped_create:
                committed = adapter.commit_production_deployment(
                    "production_target_primary",
                    applied["transaction_id"],
                    applied["pending_state_fingerprint"],
                    confirmation=adapter.COMMIT_CONFIRMATION,
                    root=root,
                )
            state = adapter.read_production_deployment_state("production_target_primary", transaction_id=applied["transaction_id"], root=root)
            source_rule = runtime.load_canonical_rule(str(package["canonical_rule_id"]), require_active=True, root=root)
        self.assertEqual(committed["status"], "committed")
        self.assertEqual(wrapped_create.call_count, 1)
        self.assertEqual(state["verification_status"], "verified_committed")
        self.assertEqual(state["canonical_rule_id"], package["canonical_rule_id"])
        self.assertTrue(str(state["deployed_rule_id"] or "").startswith("production_deployed_rule_"))
        self.assertEqual(source_rule["status"], "loaded")

    def test_rollback_removes_only_transaction_owned_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            package = _deployment_package()
            _create_source_rule(root, package)
            applied = adapter.apply_production_deployment("production_target_primary", package, confirmation=adapter.APPLY_CONFIRMATION, root=root)
            pending_rollback = adapter.rollback_production_deployment("production_target_primary", applied["transaction_id"], confirmation=adapter.ROLLBACK_CONFIRMATION, root=root)
            self.assertFalse((root / tx_backend.TRANSACTION_DIR / tx_backend.PENDING_DIR / f"{applied['transaction_id']}.json").exists())
            applied2 = adapter.apply_production_deployment("production_target_primary", package, confirmation=adapter.APPLY_CONFIRMATION, root=root)
            committed = adapter.commit_production_deployment("production_target_primary", applied2["transaction_id"], applied2["pending_state_fingerprint"], confirmation=adapter.COMMIT_CONFIRMATION, root=root)
            committed_rollback = adapter.rollback_production_deployment("production_target_primary", applied2["transaction_id"], confirmation=adapter.ROLLBACK_CONFIRMATION, root=root)
            source_rule = runtime.load_canonical_rule(str(package["canonical_rule_id"]), require_active=True, root=root)
            deployed_rule = runtime.load_canonical_rule(str(committed["deployed_rule_id"]), root=root)
        self.assertEqual(pending_rollback["status"], "completed")
        self.assertEqual(committed_rollback["status"], "completed")
        self.assertEqual(source_rule["status"], "loaded")
        self.assertEqual(deployed_rule["rule"]["status"], "rolled_back")

    def test_idempotency_conflicts_drift_and_unrelated_state_protection(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            descriptor_backend.register_production_target_descriptor(_descriptor(), root=root)
            existing_rule = dict(_deployment_package()["canonical_rule_payload"])
            existing_rule["rule_id"] = "rule_existing_001"
            existing_rule["source_proposal_id"] = "existing_seed"
            existing_rule["target"] = "existing_score"
            existing_rule["value"] = 3
            runtime.create_canonical_rule(existing_rule, confirmation="CREATE_RULE", root=root)
            package = _deployment_package()
            _create_source_rule(root, package)
            package["canonical_rule_payload"]["target"] = "existing_score"
            package["canonical_rule_fingerprint"] = runtime._rule_fingerprint_from_payload(package["canonical_rule_payload"])
            package["package_fingerprint"] = adapter._deployment_package_fingerprint(package)
            conflict = adapter.preflight_production_deployment("production_target_primary", package, root=root)
            package2 = _deployment_package()
            applied = adapter.apply_production_deployment("production_target_primary", package2, confirmation=adapter.APPLY_CONFIRMATION, root=root)
            same_apply = adapter.apply_production_deployment("production_target_primary", package2, confirmation=adapter.APPLY_CONFIRMATION, root=root)
            descriptor_path = root / descriptor_backend.DESCRIPTOR_DIR / "production_target_primary.json"
            drifted = json.loads(descriptor_path.read_text(encoding="utf-8"))
            drifted["adapter_version"] = "2"
            normalized = descriptor_backend._normalize_descriptor(drifted)
            assert normalized is not None
            descriptor_path.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
            blocked = adapter.commit_production_deployment("production_target_primary", applied["transaction_id"], applied["pending_state_fingerprint"], confirmation=adapter.COMMIT_CONFIRMATION, root=root)
            unrelated = runtime.load_canonical_rule("rule_existing_001", require_active=True, root=root)
        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(same_apply["status"], "conflict")
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(unrelated["status"], "loaded")
