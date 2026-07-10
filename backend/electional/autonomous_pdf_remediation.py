"""Single-PDF remediation workflow for autonomous PDF benchmark failures."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import autonomous_pdf_benchmark as benchmark_backend
from . import rule_effectiveness_analysis as analysis_backend
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "autonomous_pdf_remediation_plans"
CASE_DIR = "autonomous_pdf_remediation_cases"
RECEIPT_DIR = "autonomous_pdf_remediation_receipts"
PLAN_INDEX = "autonomous_pdf_remediation_plan_index.json"
CASE_INDEX = "autonomous_pdf_remediation_case_index.json"
RECEIPT_INDEX = "autonomous_pdf_remediation_receipt_index.json"
PLAN_SCHEMA = "autonomous_pdf_remediation_plan_v1"
CASE_SCHEMA = "autonomous_pdf_remediation_case_v1"
RECEIPT_SCHEMA = "autonomous_pdf_remediation_receipt_v1"
REMEDIATION_SCHEMA_VERSION = "autonomous_pdf_remediation_v1"
PUBLIC_FUNCTIONS = [
    "build_autonomous_pdf_remediation_workspace",
    "run_autonomous_pdf_remediation_triage",
    "load_autonomous_pdf_remediation_case",
    "review_autonomous_pdf_remediation_case",
    "verify_autonomous_pdf_remediation",
    "load_autonomous_pdf_remediation_plan",
    "get_autonomous_pdf_remediation_health",
    "format_autonomous_pdf_remediation_report",
]
STAGE_ALIASES = {
    "structure_anchor": "structure_mapping",
    "blocking": "citation_blocking",
    "proposal_creation": "proposal_generation",
    "rule_certification": "certification",
    "rule_candidate_generation": "rule_candidate_generation",
    "citation_creation": "citation_creation",
}
METRIC_KEYS = [
    "native_text_page_coverage",
    "section_anchor_recall",
    "section_locator_validity",
    "citation_precision",
    "citation_recall",
    "proposal_precision",
    "proposal_recall",
    "rule_candidate_precision",
    "rule_candidate_recall",
    "rule_activation_precision",
    "certification_correctness",
    "blocker_accuracy",
]
REVIEW_DECISIONS = {
    "accept_for_targeted_fix",
    "benchmark_manifest_review",
    "source_document_review",
    "expected_conservative_behavior",
    "defer",
    "reject",
    "no_action",
}


def build_autonomous_pdf_remediation_workspace(
    benchmark_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    result, receipt, blockers = _load_benchmark_context(base, benchmark_result_id)
    if blockers:
        return {"status": "blocked", "benchmark_result_id": benchmark_result_id, "blockers": blockers, "warnings": []}
    assert result is not None and receipt is not None
    plan = _find_plan_for_result(base, benchmark_result_id)
    cases = _load_cases_for_plan(base, str((plan or {}).get("remediation_plan_id") or ""))
    receipts = _load_receipts_for_plan(base, str((plan or {}).get("remediation_plan_id") or ""))
    if str(result.get("release_classification") or "").startswith("passes_") and not list(result.get("mismatches") or []):
        status = "no_action_required"
    else:
        status = "ready_for_triage" if plan is None else str(plan.get("status") or "triaged")
    return {
        "status": status,
        "benchmark_result_id": benchmark_result_id,
        "document_id": result.get("document_id"),
        "source_revision": result.get("source_revision"),
        "document_class": result.get("document_class"),
        "release_classification": result.get("release_classification"),
        "failed_release_gates": _failed_release_gates(result),
        "stage_metrics": deepcopy(dict(result.get("stage_metrics") or {})),
        "critical_safety_violations": list(result.get("critical_safety_violations", [])),
        "mismatch_count": len(result.get("mismatches") or []),
        "remediation_plan_id": (plan or {}).get("remediation_plan_id"),
        "case_count": len(cases),
        "review_receipt_count": len([item for item in receipts if str(item.get("receipt_kind") or "") == "review"]),
        "verification_receipt_count": len([item for item in receipts if str(item.get("receipt_kind") or "") == "verification"]),
        "recommended_action": "Run TRIAGE to create bounded remediation cases." if status != "no_action_required" else "No remediation action is required.",
    }


def run_autonomous_pdf_remediation_triage(
    benchmark_result_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if confirmation != "TRIAGE":
        return {"status": "blocked", "benchmark_result_id": benchmark_result_id, "blockers": ["triage_confirmation_required"], "warnings": []}
    result, receipt, blockers = _load_benchmark_context(base, benchmark_result_id)
    if blockers:
        return {"status": "blocked", "benchmark_result_id": benchmark_result_id, "blockers": blockers, "warnings": []}
    assert result is not None and receipt is not None
    plan_id = _plan_id(result)
    existing_plan = _read_json(_plan_path(base, plan_id))
    cases = _build_cases(result)
    deferred_count = max(0, len(cases) - 50)
    cases = cases[:50]
    ordered_case_ids = [str(item["remediation_case_id"]) for item in cases]
    plan_payload = {
        "schema_version": PLAN_SCHEMA,
        "remediation_schema_version": REMEDIATION_SCHEMA_VERSION,
        "remediation_plan_id": plan_id,
        "benchmark_result_id": benchmark_result_id,
        "document_id": result.get("document_id"),
        "source_revision": result.get("source_revision"),
        "benchmark_fingerprint": _benchmark_fingerprint(result),
        "release_classification": result.get("release_classification"),
        "failed_release_gates": _failed_release_gates(result),
        "critical_safety_violation_count": len(result.get("critical_safety_violations") or []),
        "ordered_case_ids": ordered_case_ids,
        "deferred_mismatch_count": deferred_count,
        "plan_fingerprint": _plan_fingerprint(result, ordered_case_ids),
        "status": "triaged",
        "verification_records": [],
        "created_at_utc": str((existing_plan or {}).get("created_at_utc") or analysis_backend._now()),
        "updated_at_utc": analysis_backend._now(),
    }
    if isinstance(existing_plan, Mapping) and str(existing_plan.get("plan_fingerprint") or "") == plan_payload["plan_fingerprint"]:
        return {
            "status": "already_triaged",
            "remediation_plan_id": plan_id,
            "case_count": len(_load_cases_for_plan(base, plan_id)),
            "writes_performed": 0,
        }
    receipt_payload = _receipt_payload(
        receipt_kind="triage",
        remediation_plan_id=plan_id,
        benchmark_result_id=benchmark_result_id,
        document_id=str(result.get("document_id") or ""),
        source_revision=result.get("source_revision"),
        payload={
            "case_count": len(cases),
            "deferred_mismatch_count": deferred_count,
            "critical_safety_violation_count": len(result.get("critical_safety_violations") or []),
        },
    )
    before_plan = _read_json(_plan_path(base, plan_id))
    before_cases = {case_id: _read_json(_case_path(base, case_id)) for case_id in ordered_case_ids}
    before_receipt = _read_json(_receipt_path(base, str(receipt_payload["remediation_receipt_id"])))
    before_plan_index = _read_json(base / "indexes" / PLAN_INDEX)
    before_case_index = _read_json(base / "indexes" / CASE_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(_plan_path(base, plan_id), plan_payload)
        for case in cases:
            analysis_backend._atomic_write_json(_case_path(base, str(case["remediation_case_id"])), case)
        analysis_backend._atomic_write_json(_receipt_path(base, str(receipt_payload["remediation_receipt_id"])), receipt_payload)
        _update_indexes(base)
    except Exception:
        _restore_json(_plan_path(base, plan_id), before_plan)
        for case_id, snapshot in before_cases.items():
            _restore_json(_case_path(base, case_id), snapshot)
        _restore_json(_receipt_path(base, str(receipt_payload["remediation_receipt_id"])), before_receipt)
        _restore_json(base / "indexes" / PLAN_INDEX, before_plan_index)
        _restore_json(base / "indexes" / CASE_INDEX, before_case_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "failed", "benchmark_result_id": benchmark_result_id, "blockers": ["remediation_triage_write_failure"], "warnings": []}
    return {
        "status": "triaged",
        "remediation_plan_id": plan_id,
        "case_count": len(cases),
        "critical_case_count": len([item for item in cases if item.get("severity") == "critical"]),
        "writes_performed": len(cases) + 2,
    }


def load_autonomous_pdf_remediation_case(
    remediation_case_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    payload = _read_json(_case_path(base, remediation_case_id))
    if not isinstance(payload, Mapping):
        return {"status": "not_found", "remediation_case_id": remediation_case_id, "remediation_case": None, "warnings": []}
    return {"status": "loaded", "remediation_case_id": remediation_case_id, "remediation_case": dict(payload), "warnings": []}


def review_autonomous_pdf_remediation_case(
    remediation_case_id: str,
    decision: str,
    note: str | None = None,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if confirmation != "REVIEW":
        return {"status": "blocked", "remediation_case_id": remediation_case_id, "blockers": ["review_confirmation_required"], "warnings": []}
    if decision not in REVIEW_DECISIONS:
        return {"status": "blocked", "remediation_case_id": remediation_case_id, "blockers": ["unsupported_review_decision"], "warnings": []}
    case = _read_json(_case_path(base, remediation_case_id))
    if not isinstance(case, Mapping):
        return {"status": "not_found", "remediation_case_id": remediation_case_id, "blockers": ["remediation_case_missing"], "warnings": []}
    current_decision = str(case.get("review_decision") or "")
    normalized_note = str(note or "").strip()
    if current_decision:
        if current_decision == decision and str(case.get("review_note") or "") == normalized_note:
            return {"status": "already_reviewed", "remediation_case_id": remediation_case_id, "writes_performed": 0}
        return {"status": "blocked", "remediation_case_id": remediation_case_id, "blockers": ["conflicting_review_decision"], "warnings": []}
    updated_case = dict(case)
    updated_case["review_decision"] = decision
    updated_case["review_note"] = normalized_note
    updated_case["reviewed_at_utc"] = analysis_backend._now()
    updated_case["current_status"] = "reviewed"
    receipt_payload = _receipt_payload(
        receipt_kind="review",
        remediation_plan_id=str(case.get("remediation_plan_id") or ""),
        benchmark_result_id=str(case.get("benchmark_result_id") or ""),
        document_id=str(case.get("document_id") or ""),
        source_revision=case.get("source_revision"),
        payload={"remediation_case_id": remediation_case_id, "decision": decision, "note": normalized_note},
    )
    before_case = _read_json(_case_path(base, remediation_case_id))
    before_receipt = _read_json(_receipt_path(base, str(receipt_payload["remediation_receipt_id"])))
    before_case_index = _read_json(base / "indexes" / CASE_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(_case_path(base, remediation_case_id), updated_case)
        analysis_backend._atomic_write_json(_receipt_path(base, str(receipt_payload["remediation_receipt_id"])), receipt_payload)
        _update_case_index(base)
        _update_receipt_index(base)
    except Exception:
        _restore_json(_case_path(base, remediation_case_id), before_case)
        _restore_json(_receipt_path(base, str(receipt_payload["remediation_receipt_id"])), before_receipt)
        _restore_json(base / "indexes" / CASE_INDEX, before_case_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "failed", "remediation_case_id": remediation_case_id, "blockers": ["review_receipt_write_failure"], "warnings": []}
    return {"status": "reviewed", "remediation_case_id": remediation_case_id, "review_decision": decision, "writes_performed": 2}


def verify_autonomous_pdf_remediation(
    remediation_plan_id: str,
    new_benchmark_result_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if confirmation != "VERIFY":
        return {"status": "blocked", "remediation_plan_id": remediation_plan_id, "blockers": ["verification_confirmation_required"], "warnings": []}
    plan = _read_json(_plan_path(base, remediation_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "not_found", "remediation_plan_id": remediation_plan_id, "blockers": ["remediation_plan_missing"], "warnings": []}
    original_result, _original_receipt, blockers = _load_benchmark_context(base, str(plan.get("benchmark_result_id") or ""))
    new_result, _new_receipt, new_blockers = _load_benchmark_context(base, new_benchmark_result_id)
    blockers.extend(new_blockers)
    if blockers:
        return {"status": "blocked", "remediation_plan_id": remediation_plan_id, "blockers": _dedupe(blockers), "warnings": []}
    assert original_result is not None and new_result is not None
    if str(original_result.get("document_id") or "") != str(new_result.get("document_id") or ""):
        return {"status": "blocked", "remediation_plan_id": remediation_plan_id, "blockers": ["foreign_document_benchmark_result"], "warnings": []}
    if _normalize_revision(original_result.get("source_revision")) != _normalize_revision(new_result.get("source_revision")):
        return {"status": "stale", "remediation_plan_id": remediation_plan_id, "blockers": ["source_revision_changed"], "warnings": []}
    if str(original_result.get("benchmark_result_id") or "") == str(new_result.get("benchmark_result_id") or ""):
        return {"status": "blocked", "remediation_plan_id": remediation_plan_id, "blockers": ["new_benchmark_result_required"], "warnings": []}
    verification_fingerprint = analysis_backend._hash_payload({"plan": remediation_plan_id, "new_result": new_benchmark_result_id, "schema": REMEDIATION_SCHEMA_VERSION})
    existing_records = [item for item in plan.get("verification_records", []) or [] if str(item.get("verification_fingerprint") or "") == verification_fingerprint]
    if existing_records:
        return {"status": "already_verified", "remediation_plan_id": remediation_plan_id, "writes_performed": 0}
    reviewed_cases = [item for item in _load_cases_for_plan(base, remediation_plan_id) if str(item.get("review_decision") or "")]
    new_keys = {_mismatch_identity(item): item for item in new_result.get("mismatches", []) if isinstance(item, Mapping)}
    old_keys = {_mismatch_identity(item): item for item in original_result.get("mismatches", []) if isinstance(item, Mapping)}
    classifications: list[dict[str, Any]] = []
    regressed_count = 0
    resolved_count = 0
    persisting_count = 0
    for case in reviewed_cases:
        related = list(case.get("related_mismatch_ids") or [])
        old_present = [item for item in related if item in old_keys]
        new_present = [item for item in related if item in new_keys]
        if not old_present:
            status = "unavailable"
        elif not new_present and not _related_new_safety(case, new_result):
            status = "resolved"
            resolved_count += 1
        elif new_present and len(new_present) < len(old_present):
            status = "partially_resolved"
        elif _related_new_safety(case, new_result):
            status = "regressed"
            regressed_count += 1
        else:
            status = "persists"
            persisting_count += 1
        classifications.append({"remediation_case_id": case.get("remediation_case_id"), "verification_status": status})
    metric_deltas = _metric_deltas(original_result, new_result)
    receipt_payload = _receipt_payload(
        receipt_kind="verification",
        remediation_plan_id=remediation_plan_id,
        benchmark_result_id=str(plan.get("benchmark_result_id") or ""),
        document_id=str(plan.get("document_id") or ""),
        source_revision=plan.get("source_revision"),
        payload={
            "new_benchmark_result_id": new_benchmark_result_id,
            "verification_fingerprint": verification_fingerprint,
            "case_classifications": classifications,
            "metric_deltas": metric_deltas,
        },
    )
    updated_plan = dict(plan)
    updated_plan["status"] = "verified"
    updated_plan["verification_records"] = list(plan.get("verification_records", []) or []) + [{
        "new_benchmark_result_id": new_benchmark_result_id,
        "verification_fingerprint": verification_fingerprint,
        "resolved_count": resolved_count,
        "persisting_count": persisting_count,
        "regressed_count": regressed_count,
    }]
    updated_plan["updated_at_utc"] = analysis_backend._now()
    before_plan = _read_json(_plan_path(base, remediation_plan_id))
    before_receipt = _read_json(_receipt_path(base, str(receipt_payload["remediation_receipt_id"])))
    before_plan_index = _read_json(base / "indexes" / PLAN_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(_plan_path(base, remediation_plan_id), updated_plan)
        analysis_backend._atomic_write_json(_receipt_path(base, str(receipt_payload["remediation_receipt_id"])), receipt_payload)
        _update_plan_index(base)
        _update_receipt_index(base)
    except Exception:
        _restore_json(_plan_path(base, remediation_plan_id), before_plan)
        _restore_json(_receipt_path(base, str(receipt_payload["remediation_receipt_id"])), before_receipt)
        _restore_json(base / "indexes" / PLAN_INDEX, before_plan_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "failed", "remediation_plan_id": remediation_plan_id, "blockers": ["verification_receipt_write_failure"], "warnings": []}
    return {
        "status": "verified",
        "remediation_plan_id": remediation_plan_id,
        "resolved_count": resolved_count,
        "persisting_count": persisting_count,
        "regressed_count": regressed_count,
        "writes_performed": 2,
    }


def load_autonomous_pdf_remediation_plan(
    remediation_plan_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    plan = _read_json(_plan_path(base, remediation_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "not_found", "remediation_plan_id": remediation_plan_id, "remediation_plan": None, "warnings": []}
    cases = _load_cases_for_plan(base, remediation_plan_id)
    receipts = _load_receipts_for_plan(base, remediation_plan_id)
    return {"status": "loaded", "remediation_plan_id": remediation_plan_id, "remediation_plan": dict(plan), "cases": cases, "receipts": receipts, "warnings": []}


def get_autonomous_pdf_remediation_health(
    remediation_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    plans = _load_all_plans(base)
    cases = _load_all_cases(base)
    receipts = _load_all_receipts(base)
    if remediation_plan_id:
        plans = [item for item in plans if str(item.get("remediation_plan_id") or "") == remediation_plan_id]
        cases = [item for item in cases if str(item.get("remediation_plan_id") or "") == remediation_plan_id]
        receipts = [item for item in receipts if str(item.get("remediation_plan_id") or "") == remediation_plan_id]
    if not plans and not cases and not receipts:
        return {"status": "empty", "plan_count": 0, "case_count": 0, "receipt_count": 0, "recommended_action": "Run TRIAGE for one failing benchmark result."}
    warnings: list[str] = []
    stale_count = 0
    unresolved_critical = 0
    if len({str(item.get("remediation_plan_id") or "") for item in plans}) != len(plans):
        warnings.append("duplicate_remediation_plan_ids")
    if len({str(item.get("remediation_case_id") or "") for item in cases}) != len(cases):
        warnings.append("duplicate_remediation_case_ids")
    if len({str(item.get("remediation_receipt_id") or "") for item in receipts}) != len(receipts):
        warnings.append("duplicate_remediation_receipt_ids")
    for plan in plans:
        benchmark_result = benchmark_backend.load_autonomous_pdf_benchmark_result(str(plan.get("benchmark_result_id") or ""), root=base).get("benchmark_result")
        if not isinstance(benchmark_result, Mapping):
            warnings.append("missing_benchmark_result")
            continue
        if benchmark_result.get("stale"):
            stale_count += 1
        if str(plan.get("benchmark_fingerprint") or "") != _benchmark_fingerprint(benchmark_result):
            warnings.append("benchmark_fingerprint_mismatch")
    for case in cases:
        if str(case.get("severity") or "") == "critical" and not str(case.get("review_decision") or ""):
            unresolved_critical += 1
    status = "corrupt" if warnings else "stale" if stale_count else "blocked" if unresolved_critical else "healthy"
    return {
        "status": status,
        "plan_count": len(plans),
        "case_count": len(cases),
        "receipt_count": len(receipts),
        "stale_plan_count": stale_count,
        "unresolved_critical_case_count": unresolved_critical,
        "warnings": _dedupe(warnings),
        "recommended_action": "Review critical remediation cases first." if unresolved_critical else "Remediation health is good.",
    }


def format_autonomous_pdf_remediation_report(
    remediation_plan_id: str,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    loaded = load_autonomous_pdf_remediation_plan(remediation_plan_id, root=root)
    plan = loaded.get("remediation_plan")
    if not isinstance(plan, Mapping):
        return "Autonomous PDF Remediation\n\nStatus: not_found"
    cases = [item for item in loaded.get("cases", []) if isinstance(item, Mapping)]
    receipts = [item for item in loaded.get("receipts", []) if isinstance(item, Mapping)]
    latest_verification = next((item for item in reversed(receipts) if str(item.get("receipt_kind") or "") == "verification"), {})
    case_statuses = list(((latest_verification.get("payload") or {}).get("case_classifications") or []))
    deltas = dict(((latest_verification.get("payload") or {}).get("metric_deltas") or {}))
    lines = [
        "Autonomous PDF Remediation",
        "",
        f"Document: {plan.get('document_id')}",
        f"Source Revision: {plan.get('source_revision')}",
        f"Original Release Classification: {plan.get('release_classification')}",
        f"Plan Status: {plan.get('status')}",
        f"Failed Release Gates: {', '.join(plan.get('failed_release_gates', []) or ['none'])}",
        f"Total Cases: {len(cases)}",
        f"Critical Cases: {len([item for item in cases if item.get('severity') == 'critical'])}",
        f"High Cases: {len([item for item in cases if item.get('severity') == 'high'])}",
        f"Reviewed Cases: {len([item for item in cases if item.get('review_decision')])}",
        f"Unreviewed Cases: {len([item for item in cases if not item.get('review_decision')])}",
        f"Resolved Cases: {len([item for item in case_statuses if item.get('verification_status') == 'resolved'])}",
        f"Persisting Cases: {len([item for item in case_statuses if item.get('verification_status') == 'persists'])}",
        f"Regressed Cases: {len([item for item in case_statuses if item.get('verification_status') == 'regressed'])}",
        "Metric Deltas:",
    ]
    for key in METRIC_KEYS + ["critical_safety_violation_count", "mismatch_count"]:
        payload = deltas.get(key)
        lines.append(f"- {key}: {_format_delta(payload)}")
    lines.append(f"Recommended Next Action: {_recommended_action(plan, cases, case_statuses)}")
    if not public_safe:
        lines.append(f"Plan Fingerprint: {plan.get('plan_fingerprint')}")
    return "\n".join(lines)


def _ensure_dirs(root: Path | str) -> Path:
    base = benchmark_backend._ensure_dirs(root)
    for folder in (PLAN_DIR, CASE_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    defaults = (
        (PLAN_INDEX, "autonomous_pdf_remediation_plan_index_v1"),
        (CASE_INDEX, "autonomous_pdf_remediation_case_index_v1"),
        (RECEIPT_INDEX, "autonomous_pdf_remediation_receipt_index_v1"),
    )
    for name, schema in defaults:
        path = base / "indexes" / name
        if not path.exists():
            analysis_backend._atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _load_benchmark_context(base: Path, benchmark_result_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    loaded = benchmark_backend.load_autonomous_pdf_benchmark_result(benchmark_result_id, root=base)
    result = loaded.get("benchmark_result")
    if not isinstance(result, Mapping):
        return None, None, ["benchmark_result_missing"]
    if result.get("stale"):
        return None, None, ["benchmark_result_stale"]
    receipt = benchmark_backend._find_receipt_for_result(base, benchmark_result_id)
    if not isinstance(receipt, Mapping) or str(receipt.get("benchmark_result_id") or "") != benchmark_result_id:
        return None, None, ["benchmark_receipt_missing"]
    blockers: list[str] = []
    if str(result.get("document_id") or "") != str(receipt.get("document_id") or ""):
        blockers.append("benchmark_result_receipt_document_mismatch")
    if _normalize_revision(result.get("source_revision")) != _normalize_revision(receipt.get("source_revision")):
        blockers.append("benchmark_result_receipt_revision_mismatch")
    if not str(result.get("document_id") or "") or _normalize_revision(result.get("source_revision")) is None:
        blockers.append("benchmark_provenance_missing")
    return dict(result), dict(receipt), _dedupe(blockers)


def _build_cases(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    failed_gates = _failed_release_gates(result)
    benchmark_fp = _benchmark_fingerprint(result)
    groups: dict[str, dict[str, Any]] = {}
    for mismatch in result.get("mismatches", []) or []:
        if not isinstance(mismatch, Mapping):
            continue
        stage = _normalize_stage(mismatch.get("stage"))
        reason = str(mismatch.get("reason") or "unknown_reason")
        expected_key = str(mismatch.get("expected_key") or "")
        actual_key = str(mismatch.get("actual_key") or "")
        family = expected_key or actual_key or str(mismatch.get("chunk_id") or mismatch.get("page") or "unknown")
        group_key = analysis_backend._hash_payload({
            "document_id": result.get("document_id"),
            "source_revision": result.get("source_revision"),
            "stage": stage,
            "reason": reason,
            "family": family,
            "route": _route_for_stage(stage),
        })
        item = groups.setdefault(group_key, {
            "stage": stage,
            "reason_codes": [],
            "mismatch_classifications": [],
            "related_mismatch_ids": [],
            "related_safety_violations": [],
            "failed_release_gates": [],
            "evidence_references": [],
        })
        item["reason_codes"].append(reason)
        item["mismatch_classifications"].append(str(mismatch.get("classification") or "unknown"))
        item["related_mismatch_ids"].append(_mismatch_identity(mismatch))
        item["evidence_references"].append({
            "expected_identity": expected_key or None,
            "actual_identity": actual_key or None,
            "locator": mismatch.get("locator"),
            "page": mismatch.get("page"),
        })
    for safety in result.get("critical_safety_violations", []) or []:
        stage = _stage_for_safety(str(safety))
        group_key = analysis_backend._hash_payload({
            "document_id": result.get("document_id"),
            "source_revision": result.get("source_revision"),
            "stage": stage,
            "reason": str(safety),
            "family": str(safety),
            "route": _route_for_stage(stage),
        })
        item = groups.setdefault(group_key, {
            "stage": stage,
            "reason_codes": [],
            "mismatch_classifications": [],
            "related_mismatch_ids": [],
            "related_safety_violations": [],
            "failed_release_gates": [],
            "evidence_references": [],
        })
        item["related_safety_violations"].append(str(safety))
        item["reason_codes"].append(str(safety))
    cases: list[dict[str, Any]] = []
    for item in groups.values():
        stage = str(item["stage"])
        related_safety = _dedupe(item["related_safety_violations"])
        severity = _severity_for_case(stage, item, failed_gates)
        case_id = _case_id(benchmark_fp, result, item, related_safety)
        case_payload = {
            "schema_version": CASE_SCHEMA,
            "remediation_schema_version": REMEDIATION_SCHEMA_VERSION,
            "remediation_case_id": case_id,
            "remediation_plan_id": _plan_id(result),
            "benchmark_result_id": result.get("benchmark_result_id"),
            "document_id": result.get("document_id"),
            "source_revision": result.get("source_revision"),
            "stage": stage,
            "severity": severity,
            "mismatch_classifications": _dedupe(item["mismatch_classifications"]),
            "reason_codes": _dedupe(item["reason_codes"]),
            "failed_release_gates": [gate for gate in failed_gates if _gate_relevant(stage, gate, related_safety)],
            "related_safety_violations": related_safety,
            "root_cause_classification": _root_cause_classification(stage, item, related_safety),
            "root_cause_confidence": 0.0 if _root_cause_classification(stage, item, related_safety) == "unresolved" else 0.8,
            "recommended_corrective_route": _corrective_route(stage, related_safety),
            "evidence_references": item["evidence_references"][:5],
            "related_mismatch_ids": _dedupe(item["related_mismatch_ids"]),
            "current_status": "triaged",
            "case_fingerprint": analysis_backend._hash_payload({
                "benchmark_fp": benchmark_fp,
                "stage": stage,
                "reason_codes": sorted(_dedupe(item["reason_codes"])),
                "related_mismatch_ids": sorted(_dedupe(item["related_mismatch_ids"])),
                "related_safety_violations": sorted(related_safety),
            }),
            "review_decision": None,
            "review_note": "",
            "created_at_utc": analysis_backend._now(),
            "updated_at_utc": analysis_backend._now(),
        }
        cases.append(case_payload)
    cases.sort(key=lambda item: (_severity_rank(str(item.get("severity") or "")), str(item.get("stage") or ""), str(item.get("remediation_case_id") or "")))
    return cases


def _failed_release_gates(result: Mapping[str, Any]) -> list[str]:
    release = str(result.get("release_classification") or "")
    metrics = result.get("stage_metrics") or {}
    if release == "fails_safety_gate":
        return ["safety_gate"]
    if release.startswith("passes_"):
        return []
    thresholds = {
        "clean_digital_pdf": {
            "native_text_page_coverage": 0.98,
            "section_anchor_recall": 0.90,
            "section_locator_validity": 0.98,
            "citation_precision": 0.95,
            "citation_recall": 0.85,
            "proposal_precision": 0.90,
            "proposal_recall": 0.80,
            "rule_candidate_precision": 0.90,
            "rule_candidate_recall": 0.80,
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
            "rule_candidate_precision": 0.85,
            "rule_candidate_recall": 0.70,
            "rule_activation_precision": 1.00,
            "certification_correctness": 1.00,
            "blocker_accuracy": 0.90,
        },
    }.get(str(result.get("document_class") or ""), {})
    failed = []
    for key, threshold in thresholds.items():
        value = (metrics.get(key) or {}).get("value")
        if value is not None and isinstance(value, (int, float)) and value < threshold:
            failed.append(key)
    return failed


def _metric_deltas(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    before_metrics = before.get("stage_metrics") or {}
    after_metrics = after.get("stage_metrics") or {}
    for key in METRIC_KEYS:
        before_value = (before_metrics.get(key) or {}).get("value")
        after_value = (after_metrics.get(key) or {}).get("value")
        payload[key] = {
            "before": before_value if isinstance(before_value, (int, float)) else None,
            "after": after_value if isinstance(after_value, (int, float)) else None,
            "delta": round(float(after_value) - float(before_value), 6) if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)) else None,
        }
    payload["critical_safety_violation_count"] = {
        "before": len(before.get("critical_safety_violations") or []),
        "after": len(after.get("critical_safety_violations") or []),
        "delta": len(after.get("critical_safety_violations") or []) - len(before.get("critical_safety_violations") or []),
    }
    payload["mismatch_count"] = {
        "before": len(before.get("mismatches") or []),
        "after": len(after.get("mismatches") or []),
        "delta": len(after.get("mismatches") or []) - len(before.get("mismatches") or []),
    }
    return payload


def _normalize_stage(value: Any) -> str:
    return STAGE_ALIASES.get(str(value or ""), str(value or "final_run_state"))


def _mismatch_identity(item: Mapping[str, Any]) -> str:
    return analysis_backend._hash_payload({
        "stage": _normalize_stage(item.get("stage")),
        "classification": item.get("classification"),
        "reason": item.get("reason"),
        "expected_key": item.get("expected_key"),
        "actual_key": item.get("actual_key"),
        "page": item.get("page"),
        "chunk_id": item.get("chunk_id"),
        "locator": item.get("locator"),
    })


def _benchmark_fingerprint(result: Mapping[str, Any]) -> str:
    return analysis_backend._hash_payload({
        "benchmark_result_id": result.get("benchmark_result_id"),
        "document_id": result.get("document_id"),
        "source_revision": result.get("source_revision"),
        "manifest_fp": result.get("benchmark_manifest_fingerprint"),
        "run_fp": result.get("autonomous_run_fingerprint"),
        "release_policy_id": result.get("release_policy_id"),
        "comparison_schema_version": result.get("comparison_schema_version"),
    })


def _plan_id(result: Mapping[str, Any]) -> str:
    return f"autonomous_remediation_plan_{_benchmark_fingerprint(result)[7:23]}"


def _case_id(benchmark_fp: str, result: Mapping[str, Any], item: Mapping[str, Any], related_safety: list[str]) -> str:
    return f"autonomous_remediation_case_{analysis_backend._hash_payload({'benchmark_fp': benchmark_fp, 'document_id': result.get('document_id'), 'source_revision': result.get('source_revision'), 'stage': item.get('stage'), 'classifications': sorted(item.get('mismatch_classifications', [])), 'reasons': sorted(item.get('reason_codes', [])), 'mismatches': sorted(item.get('related_mismatch_ids', [])), 'safety': sorted(related_safety)})[7:23]}"


def _plan_fingerprint(result: Mapping[str, Any], ordered_case_ids: list[str]) -> str:
    return analysis_backend._hash_payload({"benchmark_fingerprint": _benchmark_fingerprint(result), "case_ids": ordered_case_ids, "schema": REMEDIATION_SCHEMA_VERSION})


def _severity_for_case(stage: str, item: Mapping[str, Any], failed_gates: list[str]) -> str:
    reasons = set(item.get("reason_codes", []))
    safety = set(item.get("related_safety_violations", []))
    if safety or reasons & {"foreign_document_rule_used", "foreign_revision_rule_used", "incorrect_rule_certified", "failed_runtime_rule_left_active", "rollback_failed"}:
        return "critical"
    if stage in {"rule_activation", "certification", "rollback", "final_run_state"} or any(gate in {"safety_gate", "rule_activation_precision", "certification_correctness"} for gate in failed_gates):
        return "high"
    if stage in {"rule_candidate_generation", "proposal_generation", "citation_creation", "citation_blocking"}:
        return "medium"
    return "low"


def _root_cause_classification(stage: str, item: Mapping[str, Any], related_safety: list[str]) -> str:
    if "benchmark_manifest_fingerprint_mismatch" in item.get("reason_codes", []):
        return "benchmark_manifest_defect"
    if stage == "document_classification":
        return "source_document_limitation"
    if related_safety:
        return "phase_9j_pipeline_defect"
    if "expected_blocker_allowed_through" in item.get("reason_codes", []):
        return "expected_conservative_block"
    return "unresolved"


def _corrective_route(stage: str, related_safety: list[str]) -> str:
    if related_safety:
        return "inspect_phase_9j_stage"
    if stage in {"rule_candidate_generation", "proposal_generation", "citation_creation", "citation_blocking", "rule_activation", "runtime_validation", "certification", "rollback"}:
        return "inspect_phase_9j_stage"
    if stage in {"structure_mapping", "native_text_coverage", "document_classification"}:
        return "inspect_source_document"
    return "unresolved_manual_review"


def _gate_relevant(stage: str, gate: str, related_safety: list[str]) -> bool:
    if gate == "safety_gate":
        return bool(related_safety)
    if stage == "rule_candidate_generation":
        return gate.startswith("rule_candidate_")
    if stage == "proposal_generation":
        return gate.startswith("proposal_")
    if stage == "citation_creation":
        return gate.startswith("citation_")
    if stage == "structure_mapping":
        return gate in {"section_anchor_recall", "section_locator_validity"}
    return True


def _route_for_stage(stage: str) -> str:
    return _corrective_route(stage, [])


def _stage_for_safety(code: str) -> str:
    if "rollback" in code:
        return "rollback"
    if "certif" in code:
        return "certification"
    if "runtime" in code:
        return "runtime_validation"
    if "foreign_" in code:
        return "final_run_state"
    return "rule_activation"


def _related_new_safety(case: Mapping[str, Any], new_result: Mapping[str, Any]) -> bool:
    case_safety = set(case.get("related_safety_violations", []) or [])
    new_safety = set(new_result.get("critical_safety_violations", []) or [])
    return bool(case_safety & new_safety) or (str(case.get("severity") or "") != "critical" and bool(new_safety))


def _receipt_payload(*, receipt_kind: str, remediation_plan_id: str, benchmark_result_id: str, document_id: str, source_revision: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    receipt_id = f"autonomous_remediation_receipt_{analysis_backend._hash_payload({'kind': receipt_kind, 'plan': remediation_plan_id, 'benchmark_result_id': benchmark_result_id, 'payload': payload})[7:23]}"
    return {
        "schema_version": RECEIPT_SCHEMA,
        "remediation_receipt_id": receipt_id,
        "receipt_kind": receipt_kind,
        "remediation_plan_id": remediation_plan_id,
        "benchmark_result_id": benchmark_result_id,
        "document_id": document_id,
        "source_revision": source_revision,
        "payload": deepcopy(dict(payload)),
        "created_at_utc": analysis_backend._now(),
    }


def _recommended_action(plan: Mapping[str, Any], cases: list[Mapping[str, Any]], statuses: list[Mapping[str, Any]]) -> str:
    if any(item.get("verification_status") == "regressed" for item in statuses):
        return "Investigate regressed remediation cases before any further benchmark closure."
    if any(str(item.get("severity") or "") == "critical" and not item.get("review_decision") for item in cases):
        return "Review critical remediation cases first."
    if statuses and all(item.get("verification_status") == "resolved" for item in statuses):
        return "Remediation cases are resolved for this PDF revision."
    return "Continue targeted remediation review for persisting cases."


def _format_delta(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return "null"
    before = payload.get("before")
    after = payload.get("after")
    delta = payload.get("delta")
    if before is None or after is None:
        return "null"
    return f"{before} -> {after} ({delta:+})"


def _severity_rank(value: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}.get(value, 9)


def _load_all_plans(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / PLAN_DIR, "remediation_plan_id")


def _load_all_cases(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / CASE_DIR, "remediation_case_id")


def _load_all_receipts(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / RECEIPT_DIR, "remediation_receipt_id")


def _find_plan_for_result(base: Path, benchmark_result_id: str) -> dict[str, Any] | None:
    for item in _load_all_plans(base):
        if str(item.get("benchmark_result_id") or "") == benchmark_result_id:
            return item
    return None


def _load_cases_for_plan(base: Path, remediation_plan_id: str) -> list[dict[str, Any]]:
    return [item for item in _load_all_cases(base) if str(item.get("remediation_plan_id") or "") == remediation_plan_id]


def _load_receipts_for_plan(base: Path, remediation_plan_id: str) -> list[dict[str, Any]]:
    return [item for item in _load_all_receipts(base) if str(item.get("remediation_plan_id") or "") == remediation_plan_id]


def _update_indexes(base: Path) -> None:
    _update_plan_index(base)
    _update_case_index(base)
    _update_receipt_index(base)


def _update_plan_index(base: Path) -> None:
    items = []
    for item in _load_all_plans(base):
        items.append({
            "remediation_plan_id": item.get("remediation_plan_id"),
            "benchmark_result_id": item.get("benchmark_result_id"),
            "document_id": item.get("document_id"),
            "source_revision": item.get("source_revision"),
            "status": item.get("status"),
        })
    analysis_backend._atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "autonomous_pdf_remediation_plan_index_v1", "items": sorted(items, key=lambda entry: str(entry.get("remediation_plan_id") or "")), "updated_at_utc": analysis_backend._now()})


def _update_case_index(base: Path) -> None:
    items = []
    for item in _load_all_cases(base):
        items.append({
            "remediation_case_id": item.get("remediation_case_id"),
            "remediation_plan_id": item.get("remediation_plan_id"),
            "severity": item.get("severity"),
            "stage": item.get("stage"),
            "current_status": item.get("current_status"),
        })
    analysis_backend._atomic_write_json(base / "indexes" / CASE_INDEX, {"schema_version": "autonomous_pdf_remediation_case_index_v1", "items": sorted(items, key=lambda entry: str(entry.get("remediation_case_id") or "")), "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for item in _load_all_receipts(base):
        items.append({
            "remediation_receipt_id": item.get("remediation_receipt_id"),
            "remediation_plan_id": item.get("remediation_plan_id"),
            "receipt_kind": item.get("receipt_kind"),
            "document_id": item.get("document_id"),
            "source_revision": item.get("source_revision"),
        })
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "autonomous_pdf_remediation_receipt_index_v1", "items": sorted(items, key=lambda entry: str(entry.get("remediation_receipt_id") or "")), "updated_at_utc": analysis_backend._now()})


def _load_dir_json(folder: Path, required_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not folder.exists():
        return items
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping) and payload.get(required_id):
            items.append(dict(payload))
    return items


def _plan_path(base: Path, remediation_plan_id: str) -> Path:
    return base / PLAN_DIR / f"{analysis_backend._safe_id(remediation_plan_id)}.json"


def _case_path(base: Path, remediation_case_id: str) -> Path:
    return base / CASE_DIR / f"{analysis_backend._safe_id(remediation_case_id)}.json"


def _receipt_path(base: Path, remediation_receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{analysis_backend._safe_id(remediation_receipt_id)}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    return benchmark_backend._read_json(path)


def _restore_json(path: Path, payload: dict[str, Any] | None) -> None:
    benchmark_backend._restore_json(path, payload)


def _normalize_revision(value: Any) -> int | None:
    return benchmark_backend._normalize_revision(value)


def _dedupe(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen

