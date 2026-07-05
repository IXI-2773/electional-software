from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

DEFAULT_BACKUP_PATHS = ("data/reliability", "data/profiles", "data/watchlists", "data/objective_packs")


def backup_reliability_data(*, output_dir: Path | str, root: Path | str = ".", include_private: bool = False) -> dict[str, object]:
    base = Path(root)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    backup_id = "backup_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    zip_path = out / f"{backup_id}.zip"
    manifest = {
        "backup_id": backup_id,
        "created_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "engine_version": "phase4_operational_v1",
        "included_paths": [],
        "file_hashes": {},
        "privacy_level": "private" if include_private else "public_safe",
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in _iter_backup_files(base):
            rel = file_path.relative_to(base).as_posix()
            manifest["included_paths"].append(rel)
            manifest["file_hashes"][rel] = _hash_file(file_path)
            archive.write(file_path, rel)
        archive.writestr("backup_manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"backup_id": backup_id, "path": str(zip_path), "manifest": manifest}


def restore_reliability_data(*, input_zip: Path | str, root: Path | str = ".", dry_run: bool = True, overwrite: bool = False) -> dict[str, object]:
    target = Path(root)
    with zipfile.ZipFile(input_zip, "r") as archive:
        names = archive.namelist()
        if "backup_manifest.json" not in names:
            raise ValueError("Missing backup manifest.")
        manifest = json.loads(archive.read("backup_manifest.json").decode("utf-8"))
        planned = [name for name in names if name != "backup_manifest.json"]
        conflicts = [name for name in planned if (target / name).exists() and not overwrite]
        if conflicts and not dry_run:
            raise FileExistsError("Restore would overwrite existing files.")
        if not dry_run:
            for name in planned:
                destination = target / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() and not overwrite:
                    raise FileExistsError(str(destination))
                destination.write_bytes(archive.read(name))
    return {"dry_run": dry_run, "files": planned, "conflicts": conflicts, "manifest": manifest}


def _iter_backup_files(root: Path) -> Iterable[Path]:
    for rel in DEFAULT_BACKUP_PATHS:
        folder = root / rel
        if folder.exists():
            yield from sorted(path for path in folder.rglob("*") if path.is_file())


def _hash_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
