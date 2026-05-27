from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.storage import load_json_dict, load_json_list, save_json


class JsonStorageTest(unittest.TestCase):
    def test_missing_files_return_empty_containers(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.json"

            self.assertEqual(load_json_dict(missing), {})
            self.assertEqual(load_json_list(missing), [])

    def test_malformed_json_returns_empty_containers(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "broken.json"
            path.write_text("{ nope", encoding="utf-8")

            self.assertEqual(load_json_dict(path), {})
            self.assertEqual(load_json_list(path), [])

    def test_container_type_mismatch_returns_empty_container(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data.json"

            save_json(path, {"ok": True})
            self.assertEqual(load_json_list(path), [])

            save_json(path, [1, 2, 3])
            self.assertEqual(load_json_dict(path), {})

    def test_save_json_round_trip_uses_sorted_indented_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "data.json"

            save_json(path, {"z": 1, "a": 2})

            self.assertEqual(load_json_dict(path), {"a": 2, "z": 1})
            self.assertIn('\n  "a": 2,\n', path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
