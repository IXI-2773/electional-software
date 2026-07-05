from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from backend.electional.search_checkpoint import cancel_search_checkpoint, load_search_checkpoint, resume_search_checkpoint, save_search_checkpoint


class SearchCheckpointTest(unittest.TestCase):
    def test_search_checkpoint_save_resume_and_atomic_write(self) -> None:
        with TemporaryDirectory() as tmp:
            path = save_search_checkpoint({"search_id": "exam", "engine_version": "v1"}, root=tmp)
            self.assertTrue(path.exists())
            self.assertFalse(path.with_name(f".{path.name}.tmp").exists())
            self.assertEqual(load_search_checkpoint("exam", root=tmp)["engine_version"], "v1")
            self.assertTrue(resume_search_checkpoint("exam", {"engine_version": "v1"}, root=tmp).accepted)

    def test_search_checkpoint_reject_version_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            save_search_checkpoint({"search_id": "exam", "engine_version": "v1"}, root=tmp)
            result = resume_search_checkpoint("exam", {"engine_version": "v2"}, root=tmp)
            self.assertFalse(result.accepted)
            self.assertIn("Version mismatch", result.warning)

    def test_search_checkpoint_cancel_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            save_search_checkpoint({"search_id": "exam", "engine_version": "v1"}, root=tmp)
            self.assertEqual(cancel_search_checkpoint("exam", root=tmp)["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
