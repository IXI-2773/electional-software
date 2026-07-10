from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import canonical_rule_runtime as runtime
from backend.electional import production_activation_transaction as tx


def _package(rule_id: str = "rule_prod_001", *, value: object = 7) -> dict[str, object]:
    rule_payload = {
        "schema_version": runtime.CANONICAL_RULE_SCHEMA_VERSION,
        "rule_id": rule_id,
        "rule_type": "threshold",
        "target": "score",
        "scope": "document",
        "condition": {"field": "score", "operator": "greater_than", "value": 5},
        "operator": "greater_than",
        "value": value,
        "priority": 50,
        "enabled": True,
        "status": "active",
        "document_id": "document_001",
        "source_proposal_id": "production_activation_transaction_seed",
        "source_revision": "1",
    }
    package = {
        "schema_version": tx.PACKAGE_SCHEMA_VERSION,
        "transaction_package_id": "production_deployment_package_001",
        "canonical_rule_id": rule_id,
        "canonical_rule_schema_version": runtime.CANONICAL_RULE_SCHEMA_VERSION,
        "canonical_rule_fingerprint": runtime._rule_fingerprint_from_payload(rule_payload),
        "canonical_rule_payload": rule_payload,
        "document_id": "document_001",
        "source_revision": 1,
        "certification_id": "certification_001",
        "certification_fingerprint": "sha256:certification_001",
        "production_authorization_result_id": "authorization_001",
        "production_authorization_fingerprint": "sha256:authorization_001",
        "production_target_id": "production_target_primary",
        "production_target_descriptor_fingerprint": "sha256:target_descriptor_001",
        "deployment_package_fingerprint": "sha256:deployment_package_001",
    }
    package["package_fingerprint"] = tx._package_fingerprint(package)
    return package


def _create_source_rule(root: Path, package: dict[str, object]) -> None:
    created = runtime.create_canonical_rule(dict(package["canonical_rule_payload"]), confirmation="CREATE_RULE", root=root)
    assert created["status"] in {"created", "already_created"}


class ProductionActivationTransactionTest(TestCase):
    def test_manifest_describes_real_pending_verify_commit_and_rollback_boundaries(self) -> None:
        with TemporaryDirectory() as tmp:
            manifest = tx.get_production_activation_transaction_manifest(root=Path(tmp) / "store")
        self.assertEqual(manifest["environment_class"], "production")
        self.assertEqual(manifest["transaction_mode"], "pending_then_explicit_commit")
        self.assertEqual(manifest["verification_mode"], "independent_pending_filesystem_readback")
        self.assertTrue(manifest["supports_pending_apply"])
        self.assertTrue(manifest["supports_independent_verification"])
        self.assertTrue(manifest["supports_explicit_commit"])
        self.assertTrue(manifest["supports_rollback"])
        self.assertTrue(str(manifest["manifest_fingerprint"]).startswith("sha256:"))

    def test_preflight_is_deterministic_and_performs_zero_writes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            _create_source_rule(root, package)
            first = tx.preflight_production_activation_transaction(package, root=root)
            second = tx.preflight_production_activation_transaction(package, root=root)
            records = list((root / tx.TRANSACTION_DIR / tx.RECORD_DIR).glob("*.json"))
            pending = list((root / tx.TRANSACTION_DIR / tx.PENDING_DIR).glob("*.json"))
        self.assertEqual(first["status"], "ready")
        self.assertEqual(first["transaction_id"], second["transaction_id"])
        self.assertEqual(first["production_state_fingerprint"], second["production_state_fingerprint"])
        self.assertEqual(records, [])
        self.assertEqual(pending, [])

    def test_apply_persists_pending_state_without_creating_canonical_rule(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            _create_source_rule(root, package)
            applied = tx.apply_production_activation_transaction(package, confirmation=tx.APPLY_CONFIRMATION, root=root)
            loaded_rule = runtime.load_canonical_rule(str(package["canonical_rule_id"]), root=root)
            pending_payload = json.loads((root / tx.TRANSACTION_DIR / tx.PENDING_DIR / f"{applied['transaction_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(applied["status"], "pending_verification")
        self.assertEqual(loaded_rule["status"], "loaded")
        self.assertEqual(pending_payload["package_fingerprint"], package["package_fingerprint"])

    def test_independent_pending_readback_is_required_before_commit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            _create_source_rule(root, package)
            applied = tx.apply_production_activation_transaction(package, confirmation=tx.APPLY_CONFIRMATION, root=root)
            record_path = root / tx.TRANSACTION_DIR / tx.RECORD_DIR / f"{applied['transaction_id']}.json"
            payload = json.loads(record_path.read_text(encoding="utf-8"))
            payload["pending_state_fingerprint"] = "sha256:drift"
            record_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            readback = tx.read_production_activation_transaction_state(applied["transaction_id"], root=root)
            blocked = tx.commit_production_activation_transaction(
                applied["transaction_id"],
                expected_pending_state_fingerprint=applied["pending_state_fingerprint"],
                confirmation=tx.COMMIT_CONFIRMATION,
                root=root,
            )
        self.assertEqual(readback["verification_status"], "unverified")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("pending_state_not_verified", blocked["blockers"])

    def test_commit_creates_and_independently_verifies_exact_canonical_rule(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            _create_source_rule(root, package)
            applied = tx.apply_production_activation_transaction(package, confirmation=tx.APPLY_CONFIRMATION, root=root)
            with patch.object(tx, "create_canonical_rule", wraps=tx.create_canonical_rule) as wrapped_create:
                committed = tx.commit_production_activation_transaction(
                    applied["transaction_id"],
                    expected_pending_state_fingerprint=applied["pending_state_fingerprint"],
                    confirmation=tx.COMMIT_CONFIRMATION,
                    root=root,
                )
            source_rule = runtime.load_canonical_rule(str(package["canonical_rule_id"]), require_active=True, root=root)
            loaded_rule = runtime.load_canonical_rule(str(committed["committed_rule_id"]), require_active=True, root=root)
        self.assertEqual(committed["status"], "committed")
        self.assertEqual(wrapped_create.call_count, 1)
        self.assertEqual(loaded_rule["status"], "loaded")
        self.assertEqual(loaded_rule["rule"]["production_activation_transaction_id"], applied["transaction_id"])
        self.assertEqual(loaded_rule["rule"]["source_canonical_rule_id"], package["canonical_rule_id"])
        self.assertEqual(source_rule["status"], "loaded")

    def test_conflicts_fingerprint_drift_and_invalid_transitions_are_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            _create_source_rule(root, package)
            conflict_rule = dict(package["canonical_rule_payload"])
            conflict_rule["source_proposal_id"] = "existing_active"
            conflict_rule["rule_id"] = "rule_existing_conflict_001"
            conflict_rule["target"] = "score"
            conflict_rule["value"] = 99
            created = runtime.create_canonical_rule(conflict_rule, confirmation="CREATE_RULE", root=root)
            preflight = tx.preflight_production_activation_transaction(package, root=root)
            self.assertEqual(created["status"], "created")
            self.assertEqual(preflight["status"], "conflict")
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            package = _package()
            _create_source_rule(root, package)
            applied = tx.apply_production_activation_transaction(package, confirmation=tx.APPLY_CONFIRMATION, root=root)
            blocked = tx.commit_production_activation_transaction(
                applied["transaction_id"],
                expected_pending_state_fingerprint="sha256:not_the_same",
                confirmation=tx.COMMIT_CONFIRMATION,
                root=root,
            )
            rolled = tx.rollback_production_activation_transaction(applied["transaction_id"], confirmation=tx.ROLLBACK_CONFIRMATION, root=root)
            invalid = tx.commit_production_activation_transaction(
                applied["transaction_id"],
                expected_pending_state_fingerprint=applied["pending_state_fingerprint"],
                confirmation=tx.COMMIT_CONFIRMATION,
                root=root,
            )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("pending_state_fingerprint_mismatch", blocked["blockers"])
        self.assertEqual(rolled["status"], "completed")
        self.assertEqual(invalid["status"], "blocked")
        self.assertIn("transaction_state_invalid_for_commit", invalid["blockers"])

    def test_rollback_cleans_pending_or_deactivates_only_transaction_owned_rule(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            pending_package = _package("rule_pending_001")
            _create_source_rule(root, pending_package)
            pending = tx.apply_production_activation_transaction(pending_package, confirmation=tx.APPLY_CONFIRMATION, root=root)
            pending_rollback = tx.rollback_production_activation_transaction(pending["transaction_id"], confirmation=tx.ROLLBACK_CONFIRMATION, root=root)
            self.assertFalse((root / tx.TRANSACTION_DIR / tx.PENDING_DIR / f"{pending['transaction_id']}.json").exists())
            committed_package = _package("rule_commit_001")
            _create_source_rule(root, committed_package)
            applied = tx.apply_production_activation_transaction(committed_package, confirmation=tx.APPLY_CONFIRMATION, root=root)
            committed = tx.commit_production_activation_transaction(
                applied["transaction_id"],
                expected_pending_state_fingerprint=applied["pending_state_fingerprint"],
                confirmation=tx.COMMIT_CONFIRMATION,
                root=root,
            )
            committed_rollback = tx.rollback_production_activation_transaction(applied["transaction_id"], confirmation=tx.ROLLBACK_CONFIRMATION, root=root)
            source_rule = runtime.load_canonical_rule(str(committed_package["canonical_rule_id"]), require_active=True, root=root)
            rolled_rule = runtime.load_canonical_rule(str(committed["committed_rule_id"]), root=root)
            rollback_record = json.loads((root / tx.TRANSACTION_DIR / tx.ROLLBACK_DIR / f"{applied['transaction_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(pending_rollback["status"], "completed")
        self.assertEqual(committed["status"], "committed")
        self.assertEqual(committed_rollback["status"], "completed")
        self.assertEqual(rolled_rule["rule"]["status"], "rolled_back")
        self.assertEqual(source_rule["status"], "loaded")
        self.assertEqual(rollback_record["transaction_id"], applied["transaction_id"])

    def test_no_other_canonical_rule_or_production_state_is_modified(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            existing_rule = dict(_package("rule_existing_001")["canonical_rule_payload"])
            existing_rule["source_proposal_id"] = "existing_rule_seed"
            runtime.create_canonical_rule(existing_rule, confirmation="CREATE_RULE", root=root)
            before_existing = runtime.load_canonical_rule("rule_existing_001", require_active=True, root=root)["rule"]
            package = _package("rule_new_001")
            _create_source_rule(root, package)
            applied = tx.apply_production_activation_transaction(package, confirmation=tx.APPLY_CONFIRMATION, root=root)
            tx.commit_production_activation_transaction(
                applied["transaction_id"],
                expected_pending_state_fingerprint=applied["pending_state_fingerprint"],
                confirmation=tx.COMMIT_CONFIRMATION,
                root=root,
            )
            after_existing = runtime.load_canonical_rule("rule_existing_001", require_active=True, root=root)["rule"]
            health = tx.get_production_activation_transaction_health(root=root)
        self.assertEqual(before_existing, after_existing)
        self.assertEqual(health["committed_count"], 1)
