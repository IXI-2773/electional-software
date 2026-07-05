from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.taxonomy_topic_search import (
    build_taxonomy_topic_search_plan,
    deduplicate_taxonomy_topic_results,
    get_taxonomy_topic_search_health,
    group_taxonomy_topic_results,
    resolve_taxonomy_search_query,
    search_taxonomy_aware_topic_content,
)
from backend.electional.topic_taxonomy import save_controlled_topic


def _write_topic_index(root: Path, topics: dict[str, list[dict]]) -> None:
    index_dir = root / "cross_document_topic_indexes"
    index_dir.mkdir(parents=True, exist_ok=True)
    (root / "indexes").mkdir(parents=True, exist_ok=True)
    payload = {"status": "healthy", "topics": topics}
    (root / "cross_document_topic_indexes" / "current.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (root / "indexes" / "cross_document_topic_index.json").write_text(json.dumps({"status": "healthy", "stale": False, "index_file": "current.json"}, indent=2), encoding="utf-8")


def _match(document_id: str, document_title: str, chapter_id: str, chapter_title: str, chapter_number: int, section_id: str, section_title: str, page_start: int, page_end: int, *, match_reason: str = "exact_topic_tag", map_source: str = "curated", readiness: str = "ready", chunk_ids: list[str] | None = None) -> dict:
    return {
        "document_id": document_id,
        "document_title": document_title,
        "chapter_id": chapter_id,
        "chapter_title": chapter_title,
        "chapter_number": chapter_number,
        "chapter_start_page": page_start,
        "section_id": section_id,
        "section_title": section_title,
        "section_order": chapter_number,
        "page_start": page_start,
        "page_end": page_end,
        "chunk_ids": chunk_ids or [],
        "matched_tags": [],
        "match_reason": match_reason,
        "reader_backend_readiness": readiness,
        "map_source": map_source,
        "warnings": [],
    }


class TaxonomyTopicSearchTest(TestCase):
    def test_unresolved_query_does_not_search(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            result = search_taxonomy_aware_topic_content("unknown phrase", root=root)
            self.assertEqual(result["status"], "unresolved")
            self.assertEqual(result["results"], [])
            self.assertIn("controlled_topic_not_found", result["warnings"])

    def test_alias_query_resolves_to_preferred_topic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", aliases=["auth"], root=root)
            resolved = resolve_taxonomy_search_query("auth", root=root)
            self.assertTrue(resolved["resolved"])
            self.assertEqual(resolved["preferred_label"], "authentication")
            self.assertEqual(resolved["resolution_type"], "alias")

    def test_search_uses_only_approved_expansion_labels(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", aliases=["auth"], root=root)
            _write_topic_index(
                root,
                {
                    "authentication": [_match("doc_a", "Security Manual", "chapter_001", "Access Control", 1, "section_001", "Authentication", 14, 18)],
                    "auth": [_match("doc_b", "Identity Guide", "chapter_002", "Short Forms", 2, "section_002", "Auth", 7, 9)],
                    "identity verification": [_match("doc_c", "Verifier", "chapter_003", "Verification", 3, "section_003", "Identity Verification", 3, 4)],
                },
            )
            result = search_taxonomy_aware_topic_content("authentication", include_aliases=True, include_related=False, root=root)
            labels = sorted({label for item in result["results"] for label in item.get("matched_search_labels", [])})
            self.assertEqual(labels, ["auth", "authentication"])
            self.assertEqual(result["structural_match_count"], 2)

    def test_parent_related_expansion_disabled_by_default(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("identity access management", root=root)
            save_controlled_topic("identity verification", root=root)
            save_controlled_topic("authentication", parent_topic_ids=["topic_identity_access_management"], related_topic_ids=["topic_identity_verification"], root=root)
            plan = build_taxonomy_topic_search_plan("authentication", root=root)
            self.assertEqual([item["normalized_label"] for item in plan["search_labels"]], ["authentication"])

    def test_missing_phase_8r_index_blocks_search(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", root=root)
            result = search_taxonomy_aware_topic_content("authentication", root=root)
            self.assertEqual(result["status"], "blocked")
            self.assertIn("cross_document_topic_index_missing", result["blockers"])

    def test_duplicate_structural_results_merge_provenance(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", aliases=["auth"], root=root)
            shared = _match("doc_a", "Security Manual", "chapter_001", "Access Control", 1, "section_001", "Authentication", 14, 18, chunk_ids=["chunk_1"])
            _write_topic_index(root, {"authentication": [shared], "auth": [shared]})
            result = search_taxonomy_aware_topic_content("authentication", include_aliases=True, root=root)
            self.assertEqual(result["structural_match_count"], 1)
            self.assertEqual(result["results"][0]["matched_search_labels"], ["auth", "authentication"])
            self.assertEqual(len(result["results"][0]["match_provenance"]), 2)

    def test_direct_match_ranks_before_alias_match(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", aliases=["auth"], root=root)
            _write_topic_index(
                root,
                {
                    "authentication": [_match("doc_b", "Zeta Manual", "chapter_002", "Authentication", 2, "section_002", "Preferred", 2, 3)],
                    "auth": [_match("doc_a", "Alpha Manual", "chapter_001", "Aliases", 1, "section_001", "Alias Only", 1, 1)],
                },
            )
            result = search_taxonomy_aware_topic_content("authentication", include_aliases=True, root=root)
            self.assertTrue(result["results"][0]["direct_match"])
            self.assertEqual(result["results"][0]["document_id"], "doc_b")

    def test_results_group_by_document_chapter_section(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", root=root)
            _write_topic_index(root, {"authentication": [_match("doc_a", "Security Manual", "chapter_001", "Access Control", 1, "section_001", "Authentication", 14, 18)]})
            grouped = group_taxonomy_topic_results(search_taxonomy_aware_topic_content("authentication", root=root)["results"])
            self.assertEqual(grouped[0]["document_id"], "doc_a")
            self.assertEqual(grouped[0]["chapters"][0]["chapter_id"], "chapter_001")
            self.assertEqual(grouped[0]["chapters"][0]["sections"][0]["section_id"], "section_001")

    def test_critical_taxonomy_validation_blocks_search(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", root=root)
            rogue = root / "topic_taxonomy" / "topic_broken.json"
            rogue.parent.mkdir(parents=True, exist_ok=True)
            rogue.write_text(json.dumps({"schema_version": "broken_v1", "topic_id": "topic_broken", "preferred_label": "broken", "normalized_preferred_label": "broken", "aliases": [], "parent_topic_ids": [], "child_topic_ids": [], "related_topic_ids": [], "status": "active", "replacement_topic_id": None, "note": None, "created_at_utc": "2026-07-04T00:00:00Z", "updated_at_utc": "2026-07-04T00:00:00Z", "warnings": []}, indent=2), encoding="utf-8")
            _write_topic_index(root, {"authentication": [_match("doc_a", "Security Manual", "chapter_001", "Access Control", 1, "section_001", "Authentication", 14, 18)]})
            result = search_taxonomy_aware_topic_content("authentication", root=root)
            self.assertIn(result["status"], {"blocked", "critical"})
            self.assertIn("taxonomy_validation_critical", result["blockers"])

    def test_api_taxonomy_topic_search_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_controlled_topic("authentication", aliases=["auth"], root=root)
            _write_topic_index(root, {"authentication": [_match("doc_a", "Security Manual", "chapter_001", "Access Control", 1, "section_001", "Authentication", 14, 18)], "auth": [_match("doc_a", "Security Manual", "chapter_001", "Access Control", 1, "section_001", "Authentication", 14, 18)]})
            resolved = api.resolve_taxonomy_search_query("auth", root=root)
            plan = api.build_taxonomy_topic_search_plan("auth", root=root)
            search = api.search_taxonomy_aware_topic_content("auth", root=root)
            health = api.get_taxonomy_topic_search_health(root=root)
            report = api.format_taxonomy_topic_search_report("auth", root=root)
            self.assertEqual(resolved["topic_id"], "topic_authentication")
            self.assertGreaterEqual(len(plan["search_labels"]), 1)
            self.assertEqual(search["structural_match_count"], 1)
            self.assertEqual(health["status"], "healthy")
            self.assertIn("Taxonomy-Aware Topic Search Report", report)
