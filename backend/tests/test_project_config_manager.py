from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.config_manager import load_project_config, validate_project_config
from backend.electional.governance.docs_coverage import get_docs_coverage
from backend.electional.governance.extensions import get_extension, get_extension_registry
from backend.electional.governance.performance_budget import get_performance_budget_status
from backend.electional.governance.release_package import prepare_release_template


class ProjectConfigManagerTest(unittest.TestCase):
    def test_config_load_default(self) -> None:
        with TemporaryDirectory() as tmp:
            config = load_project_config(Path(tmp) / "missing.json", create_paths=False)
            self.assertFalse(config["testing_policy"]["allow_broad_suite_by_default"])

    def test_config_bad_value_warning(self) -> None:
        warnings = validate_project_config({"testing_policy": {"allow_broad_suite_by_default": True}, "paths": {}})
        self.assertIn("broad_suite_must_be_disabled_by_default", warnings)

    def test_config_creates_missing_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            config = load_project_config(Path(tmp) / "config.json", create_paths=True)
            self.assertIn("paths", config)

    def test_extension_registry_pdf_extractor_and_unknown(self) -> None:
        registry = get_extension_registry()
        self.assertTrue(any(item["extension_id"] == "pdf_text_extractor_pypdf" for item in registry["extensions"]))
        self.assertEqual(get_extension("missing")["status"], "unknown")

    def test_docs_coverage_and_performance_budget(self) -> None:
        self.assertIn("features", get_docs_coverage())
        self.assertIn("checks", get_performance_budget_status())

    def test_release_template_created(self) -> None:
        with TemporaryDirectory() as tmp:
            result = prepare_release_template(Path(tmp) / "release")
            self.assertFalse(result["private_data_included"])
            self.assertTrue((Path(result["path"]) / "README_RELEASE.md").exists())


if __name__ == "__main__":
    unittest.main()
