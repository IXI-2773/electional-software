from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.backup_restore import backup_reliability_data, restore_reliability_data


class BackupRestoreTest(unittest.TestCase):
    def test_backup_created_manifest_and_hash_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "data" / "reliability"
            source.mkdir(parents=True)
            (source / "snapshot.json").write_text('{"id":"x"}', encoding="utf-8")
            result = backup_reliability_data(output_dir=root / "backups", root=root)
            self.assertTrue(Path(result["path"]).exists())
            self.assertIn("data/reliability/snapshot.json", result["manifest"]["file_hashes"])

    def test_restore_dry_run_commit_and_no_overwrite_without_flag(self) -> None:
        with TemporaryDirectory() as src, TemporaryDirectory() as dest:
            source = Path(src)
            (source / "data" / "reliability").mkdir(parents=True)
            (source / "data" / "reliability" / "snapshot.json").write_text("{}", encoding="utf-8")
            backup = backup_reliability_data(output_dir=source / "backups", root=source)
            dry = restore_reliability_data(input_zip=backup["path"], root=dest, dry_run=True)
            self.assertTrue(dry["dry_run"])
            restore_reliability_data(input_zip=backup["path"], root=dest, dry_run=False)
            self.assertTrue((Path(dest) / "data" / "reliability" / "snapshot.json").exists())
            with self.assertRaises(FileExistsError):
                restore_reliability_data(input_zip=backup["path"], root=dest, dry_run=False)


if __name__ == "__main__":
    unittest.main()
