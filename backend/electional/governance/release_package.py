from __future__ import annotations

from pathlib import Path


def prepare_release_template(root: Path | str = "dist/release_template") -> dict[str, object]:
    base = Path(root)
    for folder in ("app", "data", "docs", "config", "backups"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    readme = base / "README_RELEASE.md"
    if not readme.exists():
        readme.write_text(
            "# Release Template\n\n"
            "- Private data is not included by default.\n"
            "- Run project health before release.\n"
            "- Broad project-wide tests are disabled unless explicitly requested.\n",
            encoding="utf-8",
        )
    return {"path": str(base), "folders": ["app", "data", "docs", "config", "backups"], "private_data_included": False}
