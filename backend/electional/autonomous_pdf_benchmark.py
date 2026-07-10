"""Single-PDF benchmark evaluation for the autonomous PDF pipeline."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import rule_effectiveness_analysis as analysis_backend
from .autonomous_pdf_certification import RUN_DIR as AUTONOMOUS_RUN_DIR
from .autonomous_pdf_certification import RECEIPT_DIR as AUTONOMOUS_RECEIPT_DIR
from .document_content_map import load_document_content_map
from .document_manifest import load_document_manifest
from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, load_source_document

BENCHMARK_MANIFEST_DIR = "autonomous_pdf_benchmark_manifests"
BENCHMARK_RESULT_DIR = "autonomous_pdf_benchmark_results"
BENCHMARK_RECEIPT_DIR = "autonomous_pdf_benchmark_receipts"
BENCHMARK_MANIFEST_INDEX = "autonomous_pdf_benchmark_manifest_index.json"
BENCHMARK_RESULT_INDEX = "autonomous_pdf_benchmark_result_index.json"
BENCHMARK_RECEIPT_INDEX = "autonomous_pdf_benchmark_receipt_index.json"
MANIFEST_SCHEMA = "autonomous_pdf_benchmark_manifest_v1"
RESULT_SCHEMA = "autonomous_pdf_benchmark_result_v1"
RECEIPT_SCHEMA = "autonomous_pdf_benchmark_receipt_v1"
RELEASE_POLICY_ID = "native_pdf_benchmark_policy_v1"
COMPARISON_SCHEMA = "autonomous_pdf_benchmark_compare_v1"
ALLOWED_CLASSES = {"clean_digital_pdf", "complex_digital_pdf", "unsupported_image_only_pdf", "unsupported_corrupt_text_layer"}
FINAL_RUN_STATUSES = {"completed", "completed_with_blocked_items", "no_rule_candidates", "cancelled", "failed_rolled_back", "rollback_failed", "blocked"}
PUBLIC_FUNCTIONS = [
    "build_autonomous_pdf_benchmark_workspace",
    "validate_autonomous_pdf_benchmark_manifest",
    "run_autonomous_pdf_benchmark",
    "compare_autonomous_stage_outputs",
    "load_autonomous_pdf_benchmark_result",
    "get_autonomous_pdf_benchmark_health",
    "format_autonomous_pdf_benchmark_report",
    "get_autonomous_pdf_benchmark_summary",
]


def build_autonomous_pdf_benchmark_workspace(
    benchmark_id: str,
    autonomous_run_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    validation = validate_autonomous_pdf_benchmark_manifest(benchmark_id, root=base)
    manifest = validation.get("manifest")
    if not isinstance(manifest, Mapping):
        return {
            "benchmark_id": benchmark_id,
            "benchmark_manifest_status": validation.get("status", "invalid"),
            "benchmark_status": "blocked",
            "warnings": list(validation.get("warnings", [])),
            "blockers": list(validation.get("blockers", [])),
            "recommended_action": "Fix the benchmark manifest before benchmarking.",
        }
    run = _load_selected_run(base, manifest, autonomous_run_id)
    receipt = _load_autonomous_receipt_for_run(base, str((run or {}).get("autonomous_run_id") or ""))
    actual = _load_actual_outputs(base, manifest, run)
    existing_result = _find_result_for(benchmark_id, str((run or {}).get("autonomous_run_id") or ""), root=base)
    benchmark_status = "not_run"
    if isinstance(existing_result, Mapping):
        benchmark_status = "stale" if _result_is_stale(base, existing_result) else str(existing_result.get("release_classification") or "completed")
    return {
        "benchmark_id": benchmark_id,
        "document_id": manifest.get("document_id"),
        "source_revision": manifest.get("source_revision"),
        "document_class": manifest.get("document_class"),
        "benchmark_manifest_status": validation.get("status"),
        "autonomous_run_id": (run or {}).get("autonomous_run_id"),
        "autonomous_run_status": (run or {}).get("status", "not_found"),
        "benchmark_status": benchmark_status,
        "expected_citation_count": len(((manifest.get("expected") or {}).get("citations") or [])),
        "actual_citation_count": len(actual.get("citations", [])),
        "expected_rule_count": len(((manifest.get("expected") or {}).get("certified_rules") or [])),
        "actual_certified_rule_count": len(actual.get("certified_rules", [])),
        "existing_benchmark_result_id": (existing_result or {}).get("benchmark_result_id"),
        "existing_benchmark_receipt_id": _find_receipt_for_result(base, str((existing_result or {}).get("benchmark_result_id") or "")).get("benchmark_receipt_id") if isinstance(existing_result, Mapping) else None,
        "warnings": list(validation.get("warnings", [])),
        "blockers": list(validation.get("blockers", [])) + ([] if run else ["final_autonomous_run_required"]),
        "recommended_action": "Run the single-PDF autonomous benchmark." if run else "Provide a final autonomous Phase 9J run for this exact PDF revision.",
    }


def validate_autonomous_pdf_benchmark_manifest(
    benchmark_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    payload = _read_json(_manifest_path(base, benchmark_id))
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, Mapping):
        return {"status": "invalid", "benchmark_id": benchmark_id, "manifest": None, "warnings": [], "blockers": ["benchmark_manifest_missing"]}
    if str(payload.get("schema_version") or "") != MANIFEST_SCHEMA:
        blockers.append("unsupported_benchmark_manifest_schema")
    if _non_empty_text(payload.get("benchmark_id")) != benchmark_id:
        blockers.append("benchmark_id_mismatch")
    document_id = _non_empty_text(payload.get("document_id"))
    source_revision = _normalize_revision(payload.get("source_revision"))
    source_sha256 = _non_empty_text(payload.get("source_sha256"))
    document_class = _non_empty_text(payload.get("document_class"))
    if not document_id:
        blockers.append("document_id_required")
    if source_revision is None:
        blockers.append("source_revision_required")
    if not source_sha256:
        blockers.append("source_sha256_required")
    if document_class not in ALLOWED_CLASSES:
        blockers.append("unsupported_document_class")
    benchmark_basis = str(payload.get("benchmark_basis") or "").strip()
    if not benchmark_basis:
        blockers.append("benchmark_basis_required")
    if "autonomous" in benchmark_basis.lower():
        blockers.append("benchmark_basis_not_independent")
    if str(payload.get("release_policy_id") or RELEASE_POLICY_ID) != RELEASE_POLICY_ID:
        blockers.append("unsupported_release_policy")
    expected = payload.get("expected")
    if not isinstance(expected, Mapping):
        blockers.append("expected_section_required")
        expected = {}
    duplicate_sets = [
        ("citations", [_citation_key(item) for item in expected.get("citations", []) if isinstance(item, Mapping)]),
        ("proposals", [_proposal_key(item) for item in expected.get("proposals", []) if isinstance(item, Mapping)]),
        ("rule_candidates", [_rule_candidate_key(item) for item in expected.get("rule_candidates", []) if isinstance(item, Mapping)]),
        ("certified_rules", [_rule_key(item) for item in expected.get("certified_rules", []) if isinstance(item, Mapping)]),
        ("blocked_candidates", [_blocker_key(item) for item in expected.get("blocked_candidates", []) if isinstance(item, Mapping)]),
    ]
    for label, keys in duplicate_sets:
        if len(keys) != len(set(keys)):
            blockers.append(f"duplicate_expected_{label}")
    for anchor in expected.get("section_anchors", []) or []:
        if not isinstance(anchor, Mapping) or _normalize_page(anchor.get("page_number")) is None or not _non_empty_text(anchor.get("normalized_heading")):
            blockers.append("invalid_expected_section_anchor")
            break
    for citation in expected.get("citations", []) or []:
        if not isinstance(citation, Mapping):
            blockers.append("invalid_expected_citation_locator")
            break
        if _non_empty_text(citation.get("expected_key")):
            continue
        locator = citation.get("locator") if isinstance(citation.get("locator"), Mapping) else {}
        citation_document_id = _non_empty_text(citation.get("document_id") or locator.get("document_id"))
        citation_revision = _normalize_revision(citation.get("source_revision") or locator.get("source_revision"))
        citation_page = _normalize_page(citation.get("page") or citation.get("page_start") or locator.get("page") or locator.get("page_start"))
        citation_chunk_id = _non_empty_text(citation.get("chunk_id") or locator.get("chunk_id"))
        if not citation_document_id or citation_revision is None or citation_page is None or not citation_chunk_id or not _non_empty_text(citation.get("selected_text_hash")):
            blockers.append("invalid_expected_citation_locator")
            break
    manifest_core = deepcopy(dict(payload))
    provided_fingerprint = str(manifest_core.pop("manifest_fingerprint", "") or "")
    expected_fingerprint = analysis_backend._hash_payload(manifest_core)
    if provided_fingerprint != expected_fingerprint:
        blockers.append("benchmark_manifest_fingerprint_mismatch")
    record = load_source_document(document_id, root=base, missing_ok=True) if document_id else None
    if record is None:
        blockers.append("source_document_missing")
    else:
        if record.sha256 != source_sha256:
            blockers.append("source_sha256_mismatch")
        manifest = load_document_manifest(document_id, root=base).get("manifest")
        if not isinstance(manifest, Mapping):
            blockers.append("document_manifest_missing")
        elif _normalize_revision(manifest.get("source_revision")) != source_revision:
            blockers.append("stale_source_revision")
    status = "valid" if not blockers else "invalid"
    return {"status": status, "benchmark_id": benchmark_id, "manifest": dict(payload), "warnings": _dedupe(warnings), "blockers": _dedupe(blockers)}


def compare_autonomous_stage_outputs(
    benchmark_id: str,
    autonomous_run_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    validation = validate_autonomous_pdf_benchmark_manifest(benchmark_id, root=base)
    manifest = validation.get("manifest")
    if not isinstance(manifest, Mapping):
        return {"status": "blocked", "warnings": list(validation.get("warnings", [])), "blockers": list(validation.get("blockers", []))}
    run = _load_selected_run(base, manifest, autonomous_run_id)
    receipt = _load_autonomous_receipt_for_run(base, str((run or {}).get("autonomous_run_id") or ""))
    if not isinstance(run, Mapping) or not isinstance(receipt, Mapping) or str(run.get("status") or "") not in FINAL_RUN_STATUSES:
        return {"status": "blocked", "warnings": [], "blockers": ["final_autonomous_run_required"]}
    actual = _load_actual_outputs(base, manifest, run)
    return _compare_manifest_and_run(base, manifest, run, receipt, actual)


def run_autonomous_pdf_benchmark(
    benchmark_id: str,
    autonomous_run_id: str,
    confirmation: str | None = None,
    regenerate: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if confirmation != "BENCHMARK":
        return {"status": "blocked", "benchmark_id": benchmark_id, "blockers": ["benchmark_confirmation_required"], "warnings": []}
    validation = validate_autonomous_pdf_benchmark_manifest(benchmark_id, root=base)
    manifest = validation.get("manifest")
    if not isinstance(manifest, Mapping):
        return {"status": "blocked", "benchmark_id": benchmark_id, "blockers": list(validation.get("blockers", [])), "warnings": list(validation.get("warnings", []))}
    run = _load_selected_run(base, manifest, autonomous_run_id)
    receipt = _load_autonomous_receipt_for_run(base, autonomous_run_id)
    if not isinstance(run, Mapping) or not isinstance(receipt, Mapping) or str(run.get("status") or "") not in FINAL_RUN_STATUSES:
        return {"status": "blocked", "benchmark_id": benchmark_id, "autonomous_run_id": autonomous_run_id, "blockers": ["final_autonomous_run_required"], "warnings": []}
    current_manifest_fp = str(manifest.get("manifest_fingerprint") or "")
    current_run_fp = _autonomous_run_fingerprint(run, receipt)
    existing = _find_result_for(benchmark_id, autonomous_run_id, root=base)
    if isinstance(existing, Mapping) and not regenerate and not _result_is_stale(base, existing):
        existing_receipt = _find_receipt_for_result(base, str(existing.get("benchmark_result_id") or ""))
        return {
            "status": "already_benchmarked",
            "benchmark_result_id": existing.get("benchmark_result_id"),
            "benchmark_receipt_id": existing_receipt.get("benchmark_receipt_id"),
            "writes_performed": 0,
        }
    actual = _load_actual_outputs(base, manifest, run)
    compared = _compare_manifest_and_run(base, manifest, run, receipt, actual)
    if compared.get("status") in {"blocked", "stale", "corrupt"}:
        return compared
    result_id = _result_id(benchmark_id, autonomous_run_id, current_manifest_fp, current_run_fp)
    receipt_id = _receipt_id(result_id)
    result = {
        "schema_version": RESULT_SCHEMA,
        "comparison_schema_version": COMPARISON_SCHEMA,
        "benchmark_result_id": result_id,
        "benchmark_id": benchmark_id,
        "autonomous_run_id": autonomous_run_id,
        "document_id": manifest.get("document_id"),
        "source_revision": manifest.get("source_revision"),
        "document_class": manifest.get("document_class"),
        "benchmark_manifest_fingerprint": current_manifest_fp,
        "autonomous_run_fingerprint": current_run_fp,
        "release_policy_id": RELEASE_POLICY_ID,
        "release_classification": compared.get("release_classification"),
        "stage_metrics": deepcopy(dict(compared.get("stage_metrics") or {})),
        "critical_safety_violations": list(compared.get("critical_safety_violations", [])),
        "mismatches": list(compared.get("mismatches", [])),
        "created_at_utc": analysis_backend._now(),
        "warnings": list(compared.get("warnings", [])),
        "blockers": list(compared.get("blockers", [])),
    }
    receipt_payload = {
        "schema_version": RECEIPT_SCHEMA,
        "benchmark_receipt_id": receipt_id,
        "benchmark_result_id": result_id,
        "benchmark_id": benchmark_id,
        "autonomous_run_id": autonomous_run_id,
        "document_id": manifest.get("document_id"),
        "source_revision": manifest.get("source_revision"),
        "document_class": manifest.get("document_class"),
        "benchmark_manifest_fingerprint": current_manifest_fp,
        "autonomous_run_fingerprint": current_run_fp,
        "release_policy_id": RELEASE_POLICY_ID,
        "release_classification": compared.get("release_classification"),
        "critical_safety_violation_count": len(compared.get("critical_safety_violations", [])),
        "created_at_utc": analysis_backend._now(),
        "warnings": list(compared.get("warnings", [])),
    }
    result_path = _result_path(base, result_id)
    receipt_path = _receipt_path(base, receipt_id)
    before_result = _read_json(result_path)
    before_receipt = _read_json(receipt_path)
    before_result_index = _read_json(base / "indexes" / BENCHMARK_RESULT_INDEX)
    before_receipt_index = _read_json(base / "indexes" / BENCHMARK_RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(result_path, result)
        _update_result_index(base)
        analysis_backend._atomic_write_json(receipt_path, receipt_payload)
        _update_receipt_index(base)
    except Exception:
        _restore_json(result_path, before_result)
        _restore_json(receipt_path, before_receipt)
        _restore_json(base / "indexes" / BENCHMARK_RESULT_INDEX, before_result_index)
        _restore_json(base / "indexes" / BENCHMARK_RECEIPT_INDEX, before_receipt_index)
        return {"status": "failed_rolled_back", "benchmark_id": benchmark_id, "autonomous_run_id": autonomous_run_id, "warnings": [], "blockers": ["benchmark_result_write_failure"]}
    return {
        "status": "benchmarked",
        "benchmark_result_id": result_id,
        "benchmark_receipt_id": receipt_id,
        "release_classification": result["release_classification"],
        "critical_safety_violation_count": len(result["critical_safety_violations"]),
        "writes_performed": 2,
    }


def load_autonomous_pdf_benchmark_result(
    benchmark_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    payload = _read_json(_result_path(base, benchmark_result_id))
    if not isinstance(payload, Mapping):
        return {"status": "not_found", "benchmark_result_id": benchmark_result_id, "benchmark_result": None, "warnings": []}
    result = dict(payload)
    result["stale"] = _result_is_stale(base, result)
    return {"status": "loaded", "benchmark_result_id": benchmark_result_id, "benchmark_result": result, "warnings": []}


def get_autonomous_pdf_benchmark_health(
    benchmark_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    manifests = _load_all_manifests(base)
    results = _load_all_results(base)
    receipts = _load_all_receipts(base)
    if benchmark_id:
        manifests = [item for item in manifests if str(item.get("benchmark_id") or "") == benchmark_id]
        results = [item for item in results if str(item.get("benchmark_id") or "") == benchmark_id]
        receipts = [item for item in receipts if str(item.get("benchmark_id") or "") == benchmark_id]
    if not manifests and not results and not receipts:
        return {"status": "empty", "benchmark_manifest_count": 0, "benchmark_result_count": 0, "benchmark_receipt_count": 0, "stale_result_count": 0, "critical_safety_violation_count": 0, "recommended_action": "Create one independent benchmark manifest."}
    issues: list[str] = []
    stale_count = 0
    critical_count = 0
    if len({str(item.get("benchmark_id") or "") for item in manifests}) != len(manifests):
        issues.append("duplicate_benchmark_ids")
    if len({str(item.get("benchmark_result_id") or "") for item in results}) != len(results):
        issues.append("duplicate_benchmark_result_ids")
    if len({str(item.get("benchmark_receipt_id") or "") for item in receipts}) != len(receipts):
        issues.append("duplicate_benchmark_receipt_ids")
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        critical_count += len(result.get("critical_safety_violations", []) or [])
        for metric in (result.get("stage_metrics") or {}).values():
            if isinstance(metric, Mapping):
                value = metric.get("value")
                if isinstance(value, (int, float)) and (value < 0 or value > 1.0) and metric.get("kind") == "ratio":
                    issues.append("impossible_metric_value")
                    break
    status = "corrupt" if issues else "stale" if stale_count else "warning" if critical_count else "healthy"
    return {
        "status": status,
        "benchmark_manifest_count": len(manifests),
        "benchmark_result_count": len(results),
        "benchmark_receipt_count": len(receipts),
        "stale_result_count": stale_count,
        "critical_safety_violation_count": critical_count,
        "warnings": _dedupe(issues),
        "recommended_action": "Rerun the benchmark against the current autonomous run." if stale_count else "Benchmark health is good.",
    }


def format_autonomous_pdf_benchmark_report(
    benchmark_result_id: str | None = None,
    benchmark_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    receipt = _find_receipt_by_id(base, benchmark_receipt_id) if benchmark_receipt_id else None
    result = _find_result_by_id(base, benchmark_result_id or str((receipt or {}).get("benchmark_result_id") or ""))
    if not isinstance(result, Mapping):
        return "Autonomous PDF Quality Benchmark\n\nStatus: not_found"
    metrics = result.get("stage_metrics") or {}
    lines = [
        "Autonomous PDF Quality Benchmark",
        "",
        f"Document: {result.get('document_id')}",
        f"Source Revision: {result.get('source_revision')}",
        f"Document Class: {result.get('document_class')}",
        f"Release Classification: {result.get('release_classification')}",
        "",
        "Native Text and Structure:",
        f"- Native-Text Page Coverage: {_pct(_metric_value(metrics, 'native_text_page_coverage'))}",
        f"- Section-Anchor Recall: {_pct(_metric_value(metrics, 'section_anchor_recall'))}",
        f"- Locator Validity: {_pct(_metric_value(metrics, 'section_locator_validity'))}",
        "",
        "Citations:",
        f"- Precision: {_pct(_metric_value(metrics, 'citation_precision'))}",
        f"- Recall: {_pct(_metric_value(metrics, 'citation_recall'))}",
        f"- False Positives: {int((_metric_detail(metrics, 'citation_precision') or {}).get('false_positive_count', 0) or 0)}",
        f"- False Negatives: {int((_metric_detail(metrics, 'citation_recall') or {}).get('false_negative_count', 0) or 0)}",
        "",
        "Proposals:",
        f"- Draft Precision: {_pct(_metric_value(metrics, 'proposal_precision'))}",
        f"- Draft Recall: {_pct(_metric_value(metrics, 'proposal_recall'))}",
        f"- Promotion Safety Violations: {int((_metric_detail(metrics, 'proposal_precision') or {}).get('promotion_safety_violation_count', 0) or 0)}",
        "",
        "Rules:",
        f"- Activation Precision: {_pct(_metric_value(metrics, 'rule_activation_precision'))}",
        f"- Certification Correctness: {_pct(_metric_value(metrics, 'certification_correctness'))}",
        f"- Uncertified Active Rules: {int((_metric_detail(metrics, 'certification_correctness') or {}).get('uncertified_active_rule_count', 0) or 0)}",
        "",
        "Safety:",
        f"- Cross-Document Contamination: {int((_metric_detail(metrics, 'cross_document_contamination') or {}).get('count', 0) or 0)}",
        f"- Cross-Revision Contamination: {int((_metric_detail(metrics, 'cross_revision_contamination') or {}).get('count', 0) or 0)}",
        f"- Critical Safety Violations: {len(result.get('critical_safety_violations', []) or [])}",
        "",
        "Release Gate:",
        f"- Result: {result.get('release_classification')}",
        f"- Primary Cause: {str((result.get('critical_safety_violations') or [None])[0] or (_first_mismatch_reason(result.get('mismatches') or []) or 'none'))}",
        "",
        "Important:",
        "This result measures one PDF revision against an independent controlled benchmark manifest.",
        "No pipeline record was modified to improve the score.",
    ]
    text = "\n".join(lines)
    if public_safe:
        for needle in ("C:\\", "/Users/", "selected_text", "quote_excerpt", "claim", "condition", "value", "Traceback", "secret", "token", "api_key"):
            text = text.replace(needle, "[redacted]")
    return text


def get_autonomous_pdf_benchmark_summary(
    benchmark_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    workspace = build_autonomous_pdf_benchmark_workspace(benchmark_id, root=root)
    health = get_autonomous_pdf_benchmark_health(benchmark_id, root=root)
    return {
        "benchmark_id": benchmark_id,
        "document_id": workspace.get("document_id"),
        "source_revision": workspace.get("source_revision"),
        "document_class": workspace.get("document_class"),
        "benchmark_status": workspace.get("benchmark_status"),
        "autonomous_run_status": workspace.get("autonomous_run_status"),
        "benchmark_manifest_status": workspace.get("benchmark_manifest_status"),
        "health_status": health.get("status"),
        "critical_safety_violation_count": health.get("critical_safety_violation_count", 0),
        "recommended_action": workspace.get("recommended_action"),
    }


def _ensure_dirs(root: Path | str) -> Path:
    base = analysis_backend._ensure_analysis_dirs(root)
    for folder in (BENCHMARK_MANIFEST_DIR, BENCHMARK_RESULT_DIR, BENCHMARK_RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    defaults = (
        (BENCHMARK_MANIFEST_INDEX, "autonomous_pdf_benchmark_manifest_index_v1"),
        (BENCHMARK_RESULT_INDEX, "autonomous_pdf_benchmark_result_index_v1"),
        (BENCHMARK_RECEIPT_INDEX, "autonomous_pdf_benchmark_receipt_index_v1"),
    )
    for name, schema in defaults:
        path = base / "indexes" / name
        if not path.exists():
            analysis_backend._atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _compare_manifest_and_run(base: Path, manifest: Mapping[str, Any], run: Mapping[str, Any], receipt: Mapping[str, Any], actual: Mapping[str, Any]) -> dict:
    expected = manifest.get("expected") or {}
    mismatches: list[dict[str, Any]] = []
    safety: list[str] = []
    stage_metrics: dict[str, dict[str, Any]] = {}
    page_count_expected = _normalize_page(expected.get("page_count")) or 0
    page_count_actual = _normalize_page(actual.get("page_count")) or 0
    stage_metrics["native_text_page_coverage"] = _ratio_metric("native_text_page_coverage", min(page_count_actual, page_count_expected) if page_count_expected else None, page_count_expected if page_count_expected else None)
    expected_anchors = {_anchor_key(item): item for item in expected.get("section_anchors", []) if isinstance(item, Mapping)}
    actual_anchors = {_anchor_key(item): item for item in actual.get("section_anchors", []) if isinstance(item, Mapping)}
    anchor_tp, anchor_fp, anchor_fn = _compare_keys(expected_anchors, actual_anchors, "structure_anchor", mismatches)
    stage_metrics["section_anchor_recall"] = _ratio_metric("section_anchor_recall", anchor_tp, anchor_tp + anchor_fn, false_negative_count=anchor_fn)
    stage_metrics["section_locator_validity"] = _ratio_metric("section_locator_validity", anchor_tp, anchor_tp + anchor_fp, false_positive_count=anchor_fp)
    expected_citations = {_citation_key(item): item for item in expected.get("citations", []) if isinstance(item, Mapping)}
    actual_citations = {_citation_key(item): item for item in actual.get("citations", []) if isinstance(item, Mapping)}
    cit_tp, cit_fp, cit_fn = _compare_keys(expected_citations, actual_citations, "citation_creation", mismatches)
    stage_metrics["citation_precision"] = _ratio_metric("citation_precision", cit_tp, cit_tp + cit_fp, false_positive_count=cit_fp)
    stage_metrics["citation_recall"] = _ratio_metric("citation_recall", cit_tp, cit_tp + cit_fn, false_negative_count=cit_fn)
    expected_proposals = {_proposal_key(item): item for item in expected.get("proposals", []) if isinstance(item, Mapping)}
    actual_proposals = {_proposal_key(item): item for item in actual.get("proposals", []) if isinstance(item, Mapping)}
    prop_tp, prop_fp, prop_fn = _compare_keys(expected_proposals, actual_proposals, "proposal_creation", mismatches)
    stage_metrics["proposal_precision"] = _ratio_metric("proposal_precision", prop_tp, prop_tp + prop_fp, false_positive_count=prop_fp, promotion_safety_violation_count=0)
    stage_metrics["proposal_recall"] = _ratio_metric("proposal_recall", prop_tp, prop_tp + prop_fn, false_negative_count=prop_fn)
    expected_rule_candidates = {_rule_candidate_key(item): item for item in expected.get("rule_candidates", []) if isinstance(item, Mapping)}
    actual_rule_candidates = {_rule_candidate_key(item): item for item in actual.get("rule_candidates", []) if isinstance(item, Mapping)}
    cand_tp, cand_fp, cand_fn = _compare_keys(expected_rule_candidates, actual_rule_candidates, "rule_candidate_generation", mismatches)
    stage_metrics["rule_candidate_precision"] = _ratio_metric("rule_candidate_precision", cand_tp, cand_tp + cand_fp, false_positive_count=cand_fp)
    stage_metrics["rule_candidate_recall"] = _ratio_metric("rule_candidate_recall", cand_tp, cand_tp + cand_fn, false_negative_count=cand_fn)
    expected_rules = {_rule_key(item): item for item in expected.get("certified_rules", []) if isinstance(item, Mapping)}
    actual_rules = {_rule_key(item): item for item in actual.get("certified_rules", []) if isinstance(item, Mapping)}
    rule_tp, rule_fp, rule_fn = _compare_keys(expected_rules, actual_rules, "rule_certification", mismatches)
    stage_metrics["rule_activation_precision"] = _ratio_metric("rule_activation_precision", rule_tp, rule_tp + rule_fp, false_positive_count=rule_fp)
    stage_metrics["certification_correctness"] = _ratio_metric("certification_correctness", rule_tp, rule_tp + rule_fp + rule_fn, uncertified_active_rule_count=actual.get("uncertified_active_rule_count", 0))
    expected_blockers = {_blocker_key(item): item for item in expected.get("blocked_candidates", []) if isinstance(item, Mapping)}
    actual_blockers = {_blocker_key(item): item for item in actual.get("blocked_candidates", []) if isinstance(item, Mapping)}
    blk_tp = len(set(expected_blockers) & set(actual_blockers))
    blk_fn = len(set(expected_blockers) - set(actual_blockers))
    blk_unblocked = 0
    for key in expected_blockers:
        if key not in actual_blockers:
            mismatches.append(_mismatch("blocking", "unexpectedly_unblocked", "expected_blocker_allowed_through", key, None, manifest))
            blk_unblocked += 1
    for key in set(actual_blockers) - set(expected_blockers):
        mismatches.append(_mismatch("blocking", "incorrectly_blocked", "unexpected_blocker", None, key, manifest))
    stage_metrics["blocker_accuracy"] = _ratio_metric("blocker_accuracy", blk_tp, len(expected_blockers) or None, unexpectedly_unblocked_count=blk_unblocked)
    cross_document = sum(1 for item in actual.get("all_records", []) if str(item.get("document_id") or "") != str(manifest.get("document_id") or ""))
    cross_revision = sum(1 for item in actual.get("all_records", []) if _normalize_revision(item.get("source_revision")) not in {None, _normalize_revision(manifest.get("source_revision"))})
    stage_metrics["cross_document_contamination"] = {"kind": "count", "value": cross_document, "count": cross_document}
    stage_metrics["cross_revision_contamination"] = {"kind": "count", "value": cross_revision, "count": cross_revision}
    if cross_document:
        safety.append("foreign_document_rule_used")
    if cross_revision:
        safety.append("foreign_revision_rule_used")
    if actual.get("uncertified_active_rule_count", 0):
        safety.append("failed_runtime_rule_left_active")
    if any(item.get("classification") == "false_positive" for item in mismatches if item.get("stage") == "rule_certification"):
        safety.append("incorrect_rule_certified")
    if any(item.get("classification") == "incorrectly_blocked" for item in mismatches if item.get("stage") == "blocking"):
        pass
    release_classification = _classify_release(manifest, run, stage_metrics, safety, mismatches, actual)
    return {
        "status": "compared",
        "release_classification": release_classification,
        "stage_metrics": stage_metrics,
        "critical_safety_violations": _dedupe(safety),
        "mismatches": mismatches,
        "warnings": [],
        "blockers": [],
    }


def _classify_release(manifest: Mapping[str, Any], run: Mapping[str, Any], metrics: Mapping[str, Any], safety: list[str], mismatches: list[Mapping[str, Any]], actual: Mapping[str, Any]) -> str:
    document_class = str(manifest.get("document_class") or "")
    if document_class.startswith("unsupported_"):
        if str(run.get("status") or "") == "blocked" and not actual.get("citations") and not actual.get("proposals") and not actual.get("certified_rules"):
            return "passes_unsupported_pdf_rejection_gate"
        return "fails_safety_gate"
    if safety:
        return "fails_safety_gate"
    thresholds = {
        "clean_digital_pdf": {
            "native_text_page_coverage": 0.98,
            "section_anchor_recall": 0.90,
            "section_locator_validity": 0.98,
            "citation_precision": 0.95,
            "citation_recall": 0.85,
            "proposal_precision": 0.90,
            "proposal_recall": 0.80,
            "rule_activation_precision": 1.00,
            "certification_correctness": 1.00,
            "blocker_accuracy": 0.95,
        },
        "complex_digital_pdf": {
            "native_text_page_coverage": 0.95,
            "section_anchor_recall": 0.80,
            "section_locator_validity": 0.95,
            "citation_precision": 0.93,
            "citation_recall": 0.75,
            "proposal_precision": 0.85,
            "proposal_recall": 0.70,
            "rule_activation_precision": 1.00,
            "certification_correctness": 1.00,
            "blocker_accuracy": 0.90,
        },
    }.get(document_class, {})
    for key, threshold in thresholds.items():
        value = _metric_value(metrics, key)
        if value is None:
            if key == "blocker_accuracy":
                continue
            return "fails_quality_gate"
        if value < threshold:
            return "fails_quality_gate"
    if len([item for item in mismatches if item.get("classification") == "unexpectedly_unblocked"]):
        return "fails_safety_gate"
    return "passes_clean_pdf_gate" if document_class == "clean_digital_pdf" else "passes_complex_pdf_gate"


def _load_selected_run(base: Path, manifest: Mapping[str, Any], autonomous_run_id: str | None) -> dict[str, Any] | None:
    if autonomous_run_id:
        run = _load_autonomous_run(base, autonomous_run_id)
        if not isinstance(run, Mapping):
            return None
        if str(run.get("document_id") or "") != str(manifest.get("document_id") or ""):
            return None
        if _normalize_revision(run.get("source_revision")) != _normalize_revision(manifest.get("source_revision")):
            return None
        return dict(run)
    for item in _load_all_autonomous_runs(base):
        if str(item.get("document_id") or "") == str(manifest.get("document_id") or "") and _normalize_revision(item.get("source_revision")) == _normalize_revision(manifest.get("source_revision")) and str(item.get("status") or "") in FINAL_RUN_STATUSES:
            return item
    return None


def _load_actual_outputs(base: Path, manifest: Mapping[str, Any], run: Mapping[str, Any] | None) -> dict[str, Any]:
    document_id = str(manifest.get("document_id") or "")
    source_revision = _normalize_revision(manifest.get("source_revision"))
    content_map_loaded = load_document_content_map(document_id, root=base).get("content_map")
    sections = []
    if isinstance(content_map_loaded, Mapping):
        for section in content_map_loaded.get("sections", []) or []:
            if isinstance(section, Mapping):
                sections.append({"page_number": _normalize_page(section.get("page_start")), "normalized_heading": _normalize_text(section.get("title")), "locator": f"page:{_normalize_page(section.get('page_start')) or 0}"})
    record = load_source_document(document_id, root=base, missing_ok=True)
    citations = []
    proposals = []
    rule_candidates = []
    certified_rules = []
    blocked_candidates = []
    all_records = []
    uncertified_active_rule_count = 0
    for item in (run or {}).get("item_results", []) or []:
        if not isinstance(item, Mapping):
            continue
        if item.get("blocker"):
            blocked_candidates.append({"candidate_id": item.get("candidate_id"), "expected_blocker_code": item.get("blocker"), "expected_blocked_stage": "blocking"})
        citation_id = _non_empty_text(item.get("citation_id"))
        if citation_id:
            citation = _read_json(base / "citations" / f"{citation_id}.json")
            if isinstance(citation, Mapping):
                citations.append(dict(citation))
                all_records.append(dict(citation))
        proposal_id = _non_empty_text(item.get("proposal_id"))
        if proposal_id:
            proposal = _read_json(base / "proposals" / f"{proposal_id}.json")
            if isinstance(proposal, Mapping):
                proposal_payload = dict(proposal)
                citation_keys: list[str] = []
                for citation_id in proposal_payload.get("accepted_citation_ids", []) or []:
                    citation_record = _read_json(base / "citations" / f"{citation_id}.json")
                    if isinstance(citation_record, Mapping):
                        citation_keys.append(_citation_key(citation_record))
                if citation_keys:
                    proposal_payload["citation_keys"] = sorted(citation_keys)
                proposals.append(proposal_payload)
                all_records.append(dict(proposal_payload))
                if bool(proposal_payload.get("structured_rule_ready")):
                    rule_candidates.append(
                        {
                            "proposal_id": proposal_payload.get("proposal_id"),
                            "citation_keys": list(proposal_payload.get("citation_keys", [])),
                            "target": proposal_payload.get("target"),
                            "scope": proposal_payload.get("scope"),
                            "condition": proposal_payload.get("condition"),
                            "operator": proposal_payload.get("operator"),
                            "value": proposal_payload.get("value"),
                            "structured_rule_ready": True,
                            "document_id": proposal_payload.get("document_id"),
                            "source_revision": proposal_payload.get("source_revision"),
                        }
                    )
        explicit_rule_candidate = item.get("rule_candidate")
        if isinstance(explicit_rule_candidate, Mapping):
            candidate_payload = dict(explicit_rule_candidate)
            candidate_payload.setdefault("document_id", item.get("document_id"))
            candidate_payload.setdefault("source_revision", item.get("source_revision"))
            rule_candidates.append(candidate_payload)
        cert_id = _non_empty_text(item.get("certification_receipt_id"))
        activation_receipt_id = _non_empty_text(item.get("activation_receipt_id"))
        if cert_id:
            cert = _read_json(base / "rule_activation_certification_receipts" / f"{cert_id}.json")
            if isinstance(cert, Mapping):
                rule_id = _non_empty_text(cert.get("rule_id"))
                if rule_id:
                    rule = _read_json(base / "canonical_rules" / f"{rule_id}.json")
                    if isinstance(rule, Mapping):
                        certified_rules.append(dict(rule))
                        all_records.append(dict(rule))
        elif activation_receipt_id:
            activation = _read_json(base / "proposal_rule_activation_receipts" / f"{activation_receipt_id}.json")
            if isinstance(activation, Mapping):
                rule_id = _non_empty_text(activation.get("rule_id"))
                if rule_id:
                    rule = _read_json(base / "canonical_rules" / f"{rule_id}.json")
                    if isinstance(rule, Mapping) and str(rule.get("status") or "") == "active":
                        uncertified_active_rule_count += 1
                        all_records.append(dict(rule))
    return {
        "page_count": record.page_count if record and record.extraction_status == STATUS_EXTRACTED else 0,
        "section_anchors": sections,
        "citations": [item for item in citations if str(item.get("document_id") or "") == document_id and _normalize_revision(item.get("source_revision")) == source_revision],
        "proposals": [item for item in proposals if str(item.get("document_id") or "") == document_id and _normalize_revision(item.get("source_revision")) == source_revision],
        "rule_candidates": [item for item in rule_candidates if str(item.get("document_id") or "") == document_id and _normalize_revision(item.get("source_revision")) == source_revision],
        "certified_rules": [item for item in certified_rules if str(item.get("document_id") or "") == document_id and _normalize_revision(item.get("source_revision")) == source_revision],
        "blocked_candidates": blocked_candidates,
        "all_records": all_records,
        "uncertified_active_rule_count": uncertified_active_rule_count,
    }


def _compare_keys(expected: Mapping[str, Any], actual: Mapping[str, Any], stage: str, mismatches: list[dict[str, Any]]) -> tuple[int, int, int]:
    tp = len(set(expected) & set(actual))
    fp = len(set(actual) - set(expected))
    fn = len(set(expected) - set(actual))
    for key in sorted(set(actual) - set(expected)):
        mismatches.append(_mismatch(stage, "false_positive", f"unexpected_{stage}_record", None, key, expected.get(key) or actual.get(key)))
    for key in sorted(set(expected) - set(actual)):
        mismatches.append(_mismatch(stage, "false_negative", f"expected_{stage}_missing", key, None, expected.get(key) or actual.get(key)))
    return tp, fp, fn


def _mismatch(stage: str, classification: str, reason: str, expected_key: str | None, actual_key: str | None, context: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload = context if isinstance(context, Mapping) else {}
    locator = payload.get("locator") if isinstance(payload.get("locator"), str) else payload.get("locator")
    return {
        "stage": stage,
        "classification": classification,
        "reason": reason,
        "expected_key": expected_key,
        "actual_key": actual_key,
        "document_id": payload.get("document_id"),
        "source_revision": payload.get("source_revision"),
        "page": payload.get("page") or payload.get("page_number") or payload.get("page_start"),
        "chunk_id": payload.get("chunk_id"),
        "locator": locator,
        "related_identity": payload.get("proposal_id") or payload.get("rule_id") or payload.get("citation_id"),
    }


def _ratio_metric(name: str, numerator: int | None, denominator: int | None, **extra: Any) -> dict[str, Any]:
    value = None if numerator is None or denominator in {None, 0} else round(float(numerator) / float(denominator), 6)
    payload = {"kind": "ratio", "name": name, "value": value, "numerator": numerator, "denominator": denominator}
    payload.update(extra)
    return payload


def _citation_key(item: Mapping[str, Any]) -> str:
    if _non_empty_text(item.get("expected_key")):
        return str(item.get("expected_key"))
    locator = item.get("locator") if isinstance(item.get("locator"), Mapping) else {}
    return "|".join(
        [
            str(item.get("document_id") or locator.get("document_id") or ""),
            str(_normalize_revision(item.get("source_revision") or locator.get("source_revision")) or ""),
            str(item.get("chunk_id") or locator.get("chunk_id") or ""),
            str(_normalize_page(item.get("page") or item.get("page_start") or locator.get("page") or locator.get("page_start")) or ""),
            str(item.get("selected_text_hash") or ""),
        ]
    )


def _proposal_key(item: Mapping[str, Any]) -> str:
    if _non_empty_text(item.get("expected_key")):
        return str(item.get("expected_key"))
    citation_part = ",".join(sorted(str(x) for x in item.get("citation_keys", []) or item.get("accepted_citation_ids", []) or []))
    payload = {
        "citation_part": citation_part,
        "target": item.get("target") or (item.get("rule_candidate") or {}).get("target"),
        "scope": item.get("scope") or (item.get("rule_candidate") or {}).get("scope"),
        "operator": item.get("operator") or (item.get("rule_candidate") or {}).get("operator"),
        "value": item.get("value") or (item.get("rule_candidate") or {}).get("value"),
        "condition": item.get("condition") or (item.get("rule_candidate") or {}).get("condition"),
        "structured_rule_ready": bool(item.get("structured_rule_ready", True)),
    }
    return analysis_backend._hash_payload(payload)


def _rule_key(item: Mapping[str, Any]) -> str:
    if _non_empty_text(item.get("expected_key")):
        return str(item.get("expected_key"))
    payload = {
        "rule_type": item.get("rule_type"),
        "target": item.get("target"),
        "scope": item.get("scope"),
        "condition": item.get("condition"),
        "operator": item.get("operator"),
        "value": item.get("value"),
    }
    return analysis_backend._hash_payload(payload)


def _rule_candidate_key(item: Mapping[str, Any]) -> str:
    if _non_empty_text(item.get("expected_key")):
        return str(item.get("expected_key"))
    payload = {
        "citation_part": ",".join(sorted(str(x) for x in item.get("citation_keys", []) or [])),
        "target": item.get("target") or (item.get("rule_candidate") or {}).get("target"),
        "scope": item.get("scope") or (item.get("rule_candidate") or {}).get("scope"),
        "condition": item.get("condition") or (item.get("rule_candidate") or {}).get("condition"),
        "operator": item.get("operator") or (item.get("rule_candidate") or {}).get("operator"),
        "value": item.get("value") or (item.get("rule_candidate") or {}).get("value"),
        "structured_rule_ready": bool(item.get("structured_rule_ready", True)),
    }
    return analysis_backend._hash_payload(payload)


def _blocker_key(item: Mapping[str, Any]) -> str:
    if _non_empty_text(item.get("expected_key")):
        return str(item.get("expected_key"))
    return "|".join([str(item.get("candidate_id") or ""), str(item.get("expected_blocker_code") or item.get("blocker") or ""), str(item.get("expected_blocked_stage") or item.get("stage") or "")])


def _anchor_key(item: Mapping[str, Any]) -> str:
    if _non_empty_text(item.get("expected_key")):
        return str(item.get("expected_key"))
    return "|".join([str(_normalize_page(item.get("page_number")) or ""), _normalize_text(item.get("normalized_heading") or item.get("title")), str(item.get("locator") or "")])


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_page(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
        return number if number > 0 else None
    return None


def _normalize_revision(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    validation = validate_autonomous_pdf_benchmark_manifest(str(result.get("benchmark_id") or ""), root=base)
    manifest = validation.get("manifest")
    if not isinstance(manifest, Mapping):
        return True
    run = _load_autonomous_run(base, str(result.get("autonomous_run_id") or ""))
    receipt = _load_autonomous_receipt_for_run(base, str(result.get("autonomous_run_id") or ""))
    if not isinstance(run, Mapping) or not isinstance(receipt, Mapping):
        return True
    return (
        str(result.get("benchmark_manifest_fingerprint") or "") != str(manifest.get("manifest_fingerprint") or "")
        or str(result.get("autonomous_run_fingerprint") or "") != _autonomous_run_fingerprint(run, receipt)
        or str(result.get("release_policy_id") or "") != RELEASE_POLICY_ID
        or str(result.get("comparison_schema_version") or "") != COMPARISON_SCHEMA
    )


def _autonomous_run_fingerprint(run: Mapping[str, Any], receipt: Mapping[str, Any]) -> str:
    return analysis_backend._hash_payload(
        {
            "run_id": run.get("autonomous_run_id"),
            "document_id": run.get("document_id"),
            "source_revision": run.get("source_revision"),
            "status": run.get("status"),
            "plan_fingerprint": run.get("plan_fingerprint"),
            "manifest_fingerprint": run.get("manifest_fingerprint"),
            "item_results": run.get("item_results", []),
            "receipt": receipt,
        }
    )


def _find_result_for(benchmark_id: str, autonomous_run_id: str, *, root: Path) -> dict[str, Any] | None:
    for item in _load_all_results(root):
        if str(item.get("benchmark_id") or "") == benchmark_id and str(item.get("autonomous_run_id") or "") == autonomous_run_id:
            return item
    return None


def _find_receipt_for_result(base: Path, benchmark_result_id: str) -> dict[str, Any]:
    for item in _load_all_receipts(base):
        if str(item.get("benchmark_result_id") or "") == benchmark_result_id:
            return item
    return {}


def _find_result_by_id(base: Path, benchmark_result_id: str | None) -> dict[str, Any] | None:
    if not benchmark_result_id:
        return None
    payload = _read_json(_result_path(base, benchmark_result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_by_id(base: Path, benchmark_receipt_id: str | None) -> dict[str, Any] | None:
    if not benchmark_receipt_id:
        return None
    payload = _read_json(_receipt_path(base, benchmark_receipt_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _load_autonomous_run(base: Path, autonomous_run_id: str) -> dict[str, Any] | None:
    payload = _read_json(base / AUTONOMOUS_RUN_DIR / f"{analysis_backend._safe_id(autonomous_run_id)}.json")
    return dict(payload) if isinstance(payload, Mapping) and payload.get("autonomous_run_id") == autonomous_run_id else None


def _load_autonomous_receipt_for_run(base: Path, autonomous_run_id: str) -> dict[str, Any] | None:
    for item in _load_all_autonomous_receipts(base):
        if str(item.get("autonomous_run_id") or "") == autonomous_run_id:
            return item
    return None


def _load_all_autonomous_runs(base: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted((base / AUTONOMOUS_RUN_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping) and payload.get("autonomous_run_id"):
            items.append(dict(payload))
    return items


def _load_all_autonomous_receipts(base: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted((base / AUTONOMOUS_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping) and payload.get("autonomous_receipt_id"):
            items.append(dict(payload))
    return items


def _load_all_manifests(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / BENCHMARK_MANIFEST_DIR, "benchmark_id")


def _load_all_results(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / BENCHMARK_RESULT_DIR, "benchmark_result_id")


def _load_all_receipts(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / BENCHMARK_RECEIPT_DIR, "benchmark_receipt_id")


def _load_dir_json(directory: Path, identity_key: str) -> list[dict[str, Any]]:
    items = []
    for path in sorted(directory.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping) and payload.get(identity_key):
            items.append(dict(payload))
    return items


def _update_result_index(base: Path) -> None:
    items = []
    for item in _load_all_results(base):
        items.append(
            {
                "benchmark_result_id": item.get("benchmark_result_id"),
                "benchmark_id": item.get("benchmark_id"),
                "autonomous_run_id": item.get("autonomous_run_id"),
                "document_id": item.get("document_id"),
                "source_revision": item.get("source_revision"),
                "document_class": item.get("document_class"),
                "release_classification": item.get("release_classification"),
                "created_at_utc": item.get("created_at_utc"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / BENCHMARK_RESULT_INDEX, {"schema_version": "autonomous_pdf_benchmark_result_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for item in _load_all_receipts(base):
        items.append(
            {
                "benchmark_receipt_id": item.get("benchmark_receipt_id"),
                "benchmark_result_id": item.get("benchmark_result_id"),
                "benchmark_id": item.get("benchmark_id"),
                "autonomous_run_id": item.get("autonomous_run_id"),
                "release_classification": item.get("release_classification"),
                "created_at_utc": item.get("created_at_utc"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / BENCHMARK_RECEIPT_INDEX, {"schema_version": "autonomous_pdf_benchmark_receipt_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _result_id(benchmark_id: str, autonomous_run_id: str, manifest_fingerprint: str, run_fingerprint: str) -> str:
    return f"autonomous_benchmark_result_{analysis_backend._hash_payload({'benchmark_id': benchmark_id, 'autonomous_run_id': autonomous_run_id, 'manifest': manifest_fingerprint, 'run': run_fingerprint, 'policy': RELEASE_POLICY_ID})[7:23]}"


def _receipt_id(result_id: str) -> str:
    return f"autonomous_benchmark_receipt_{analysis_backend._hash_payload({'result_id': result_id})[7:23]}"


def _manifest_path(base: Path, benchmark_id: str) -> Path:
    return base / BENCHMARK_MANIFEST_DIR / f"{analysis_backend._safe_id(benchmark_id)}.json"


def _result_path(base: Path, benchmark_result_id: str) -> Path:
    return base / BENCHMARK_RESULT_DIR / f"{analysis_backend._safe_id(benchmark_result_id)}.json"


def _receipt_path(base: Path, benchmark_receipt_id: str) -> Path:
    return base / BENCHMARK_RECEIPT_DIR / f"{analysis_backend._safe_id(benchmark_receipt_id)}.json"


def _metric_value(metrics: Mapping[str, Any], key: str) -> float | None:
    item = metrics.get(key)
    return item.get("value") if isinstance(item, Mapping) else None


def _metric_detail(metrics: Mapping[str, Any], key: str) -> dict[str, Any] | None:
    item = metrics.get(key)
    return dict(item) if isinstance(item, Mapping) else None


def _pct(value: float | None) -> str:
    return "null" if value is None else f"{value * 100:.2f}%"


def _first_mismatch_reason(mismatches: list[Mapping[str, Any]]) -> str | None:
    for item in mismatches:
        reason = _non_empty_text(item.get("reason"))
        if reason:
            return reason
    return None


def _read_json(path: Path) -> dict[str, Any] | None:
    return analysis_backend._read_json(path)


def _restore_json(path: Path, payload: Any) -> None:
    analysis_backend._restore_json(path, payload)


def _non_empty_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item)))


__all__ = PUBLIC_FUNCTIONS
