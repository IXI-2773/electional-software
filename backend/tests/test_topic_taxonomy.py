from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.topic_taxonomy import (
    build_taxonomy_search_expansion,
    format_topic_taxonomy_report,
    load_controlled_topic,
    normalize_taxonomy_label,
    resolve_controlled_topic_label,
    save_controlled_topic,
    validate_topic_taxonomy,
)


class TopicTaxonomyTest(TestCase):
    def test_save_controlled_topic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            saved = save_controlled_topic(
                " Authentication ",
                aliases=["auth", "user authentication"],
                status="active",
                root=root,
            )
            loaded = load_controlled_topic(saved["topic_id"], root=root)
            self.assertEqual(saved["status"], "saved")
            self.assertEqual(saved["topic_id"], "topic_authentication")
            self.assertEqual(loaded["topic"]["preferred_label"], "authentication")
            self.assertEqual(loaded["topic"]["aliases"], ["auth", "user authentication"])

    def test_duplicate_preferred_label_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", root=root)
            rogue = root / "topic_taxonomy" / "topic_other.json"
            rogue.parent.mkdir(parents=True, exist_ok=True)
            rogue.write_text(json.dumps({
                "schema_version": "controlled_topic_v1",
                "topic_id": "topic_other",
                "preferred_label": "authentication",
                "normalized_preferred_label": "authentication",
                "aliases": [],
                "parent_topic_ids": [],
                "child_topic_ids": [],
                "related_topic_ids": [],
                "status": "active",
                "replacement_topic_id": None,
                "note": None,
                "created_at_utc": "2026-07-04T00:00:00Z",
                "updated_at_utc": "2026-07-04T00:00:00Z",
                "warnings": [],
            }, indent=2), encoding="utf-8")
            result = save_controlled_topic("authentication", root=root)
            self.assertEqual(result["status"], "invalid")
            self.assertIn("duplicate_preferred_label", result["warnings"])

    def test_alias_conflict_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", aliases=["auth"], root=root)
            result = save_controlled_topic("authorization", aliases=["auth"], root=root)
            self.assertEqual(result["status"], "invalid")
            self.assertIn("alias_conflict_rejected", result["warnings"])

    def test_self_parent_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            result = save_controlled_topic("authentication", parent_topic_ids=["topic_authentication"], root=root)
            self.assertEqual(result["status"], "invalid")
            self.assertIn("self_parent_rejected", result["warnings"])

    def test_parent_cycle_detected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("identity access management", root=root)
            save_controlled_topic("authentication", parent_topic_ids=["topic_identity_access_management"], root=root)
            result = save_controlled_topic("identity access management", parent_topic_ids=["topic_authentication"], root=root)
            self.assertEqual(result["status"], "invalid")
            self.assertIn("parent_cycle", result["warnings"])

    def test_resolve_preferred_label(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("Multi–Factor Authentication", aliases=["mfa"], root=root)
            resolved = resolve_controlled_topic_label("multi-factor authentication", root=root)
            self.assertTrue(resolved["resolved"])
            self.assertEqual(resolved["resolution_type"], "preferred_label")
            self.assertEqual(resolved["topic_id"], "topic_multi_factor_authentication")

    def test_resolve_explicit_alias(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", aliases=["auth"], root=root)
            resolved = resolve_controlled_topic_label("auth", root=root)
            self.assertTrue(resolved["resolved"])
            self.assertEqual(resolved["resolution_type"], "alias")
            self.assertEqual(resolved["preferred_label"], "authentication")

    def test_unresolved_label_does_not_guess(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", root=root)
            unresolved = resolve_controlled_topic_label("identity verification", root=root)
            self.assertFalse(unresolved["resolved"])
            self.assertEqual(unresolved["resolution_type"], "unresolved")
            self.assertIn("controlled_topic_not_found", unresolved["warnings"])

    def test_expansion_uses_only_explicit_relationships(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("identity access management", root=root)
            save_controlled_topic("identity verification", root=root)
            save_controlled_topic("authentication", aliases=["auth"], parent_topic_ids=["topic_identity_access_management"], related_topic_ids=["topic_identity_verification"], root=root)
            save_controlled_topic("legacy authentication", status="deprecated", replacement_topic_id="topic_authentication", root=root)
            expansion = build_taxonomy_search_expansion(
                "auth",
                include_aliases=True,
                include_parents=True,
                include_related=True,
                root=root,
            )
            self.assertEqual(
                expansion["search_labels"],
                ["authentication", "auth", "identity access management", "identity verification"],
            )
            self.assertEqual(expansion["included_topic_ids"], ["topic_authentication", "topic_identity_access_management", "topic_identity_verification"])

    def test_api_topic_taxonomy_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            saved = api.save_controlled_topic("TLS 1.3", aliases=["transport layer security 1.3"], root=root)
            listed = api.list_controlled_topics(root=root)
            resolved = api.resolve_controlled_topic_label("transport layer security 1.3", root=root)
            expansion = api.build_taxonomy_search_expansion("tls 1.3", root=root)
            report = api.format_topic_taxonomy_report(public_safe=True, root=root)
            validation = validate_topic_taxonomy(root=root)
            self.assertEqual(normalize_taxonomy_label(" TLS 1.3 "), "tls 1 3")
            self.assertEqual(saved["status"], "saved")
            self.assertEqual(listed["count"], 1)
            self.assertEqual(resolved["topic_id"], "topic_tls_1_3")
            self.assertEqual(expansion["search_labels"], ["tls 1 3", "transport layer security 1 3"])
            self.assertEqual(validation["status"], "healthy")
            self.assertIn("Topic Taxonomy Report", report)
