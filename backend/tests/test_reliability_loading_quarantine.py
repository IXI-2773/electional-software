from __future__ import annotations

import json
from tempfile import TemporaryDirectory
import unittest

from backend.electional.reliability.audit_snapshot import build_audit_snapshot
from backend.electional.reliability.loading import load_audit_snapshot_tolerant
from backend.electional.reliability.storage import ensure_reliability_storage, load_reliability_object, save_audit_snapshot
from backend.tests.test_audit_snapshot import full_snapshot


class ReliabilityLoadingQuarantineTest(unittest.TestCase):
    def test_load_legacy_unversioned_snapshot_and_missing_sections_unavailable(self) -> None:
        with TemporaryDirectory() as tmp:
            path = ensure_reliability_storage(tmp) / "audit_snapshots" / "legacy.json"
            path.write_text(json.dumps({"input": {"objective": "exam"}, "extra": 1}), encoding="utf-8")
            loaded = load_audit_snapshot_tolerant(path)
            audit = loaded["audit_snapshot"]
            self.assertEqual(audit["phase1_advanced_analysis"]["status"], "unavailable")
            self.assertEqual(audit["phase2_tactical_analysis"]["fast_lane"]["status"], "unavailable")
            self.assertEqual(audit["phase3_reliability"]["status"], "unavailable")
            self.assertEqual(audit["extra"], 1)

    def test_bad_json_skipped_and_quarantined_when_enabled(self) -> None:
        with TemporaryDirectory() as tmp:
            root = ensure_reliability_storage(tmp)
            path = root / "audit_snapshots" / "bad.json"
            path.write_text("{bad", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_audit_snapshot_tolerant(path, quarantine=True, root=tmp)
            self.assertTrue(list((root / "quarantine").glob("*.quarantine.json")))

    def test_hash_mismatch_detected_and_partial_write_residue_ignored(self) -> None:
        with TemporaryDirectory() as tmp:
            result = save_audit_snapshot(build_audit_snapshot(full_snapshot()), root=tmp, election_id="hash")
            payload = json.loads(result.path.read_text(encoding="utf-8"))
            payload["id"] = "tampered"
            result.path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_reliability_object(result.path)
            temp = result.path.with_name(f".{result.path.name}.tmp")
            temp.write_text("{bad", encoding="utf-8")
            loaded = load_audit_snapshot_tolerant(result.path)
            self.assertIn("audit_snapshot", loaded)


if __name__ == "__main__":
    unittest.main()
