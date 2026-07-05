from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.reliability.audit_snapshot import build_audit_snapshot
from backend.electional.reliability.health import check_storage_health, format_storage_health
from backend.electional.reliability.indexes import rebuild_indexes
from backend.electional.reliability.storage import ensure_reliability_storage, save_audit_snapshot, save_outcome_log, save_replay_result
from backend.tests.test_audit_snapshot import full_snapshot


class ReliabilityStorageHealthTest(unittest.TestCase):
    def test_storage_health_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            health = check_storage_health(tmp)
            self.assertEqual(health["counts"]["audit_snapshots"], 0)
            self.assertIn(health["status"], {"healthy", "warning"})

    def test_storage_health_healthy(self) -> None:
        with TemporaryDirectory() as tmp:
            save_audit_snapshot(build_audit_snapshot(full_snapshot()), root=tmp, election_id="healthy")
            save_outcome_log({"outcome_score": 90}, root=tmp, election_id="healthy")
            save_replay_result({"run_id": "run1"}, root=tmp, run_id="run1")
            rebuild_indexes(tmp)
            health = check_storage_health(tmp)
            self.assertEqual(health["status"], "healthy")
            self.assertIn("Reliability Storage Health:", format_storage_health(health))

    def test_storage_health_missing_index_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            save_audit_snapshot(build_audit_snapshot(full_snapshot()), root=tmp, election_id="idx")
            (Path(tmp) / "indexes" / "snapshot_index.json").unlink()
            health = check_storage_health(tmp)
            self.assertEqual(health["status"], "warning")

    def test_storage_health_invalid_json_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            root = ensure_reliability_storage(tmp)
            (root / "audit_snapshots" / "bad.json").write_text("{bad", encoding="utf-8")
            health = check_storage_health(tmp)
            self.assertEqual(health["status"], "warning")
            self.assertTrue(health["invalid_json_files"])

    def test_storage_health_hash_mismatch_critical(self) -> None:
        with TemporaryDirectory() as tmp:
            result = save_audit_snapshot(build_audit_snapshot(full_snapshot()), root=tmp, election_id="hash")
            payload = json.loads(result.path.read_text(encoding="utf-8"))
            payload["id"] = "tampered"
            result.path.write_text(json.dumps(payload), encoding="utf-8")
            health = check_storage_health(tmp)
            self.assertEqual(health["status"], "critical")
            self.assertTrue(health["hash_mismatches"])

    def test_storage_health_unindexed_files_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            root = ensure_reliability_storage(tmp)
            loose = {
                "id": "loose",
                "object_type": "audit_snapshot",
                "schema_version": "phase3_reliability_v1",
                "engine_version": "test",
                "created_at_utc": "2026-07-14T00:00:00Z",
                "privacy_level": "public_safe",
            }
            (root / "audit_snapshots" / "loose.json").write_text(json.dumps(loose), encoding="utf-8")
            health = check_storage_health(tmp)
            self.assertEqual(health["status"], "warning")
            self.assertTrue(health["index_status"]["unindexed_files"])


if __name__ == "__main__":
    unittest.main()
