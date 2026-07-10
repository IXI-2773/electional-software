"""Deterministic recommendation layer for certified rule effectiveness analyses."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import rule_effectiveness_analysis as analysis_backend
from .canonical_rule_runtime import load_canonical_rule
from .rule_supersession import SUPERSESSION_CHAIN_DIR
from .source_documents import SOURCE_DOCUMENT_ROOT

RECOMMENDATION_DIR = "rule_effectiveness_recommendations"
REVIEW_DIR = "rule_effectiveness_recommendation_reviews"
ACTION_CANDIDATE_DIR = "rule_action_candidates"
RECEIPT_DIR = "rule_effectiveness_recommendation_receipts"
RECOMMENDATION_INDEX = "rule_effectiveness_recommendation_index.json"
REVIEW_INDEX = "rule_effectiveness_recommendation_review_index.json"
ACTION_INDEX = "rule_action_candidate_index.json"
RECEIPT_INDEX = "rule_effectiveness_recommendation_receipt_index.json"
RECOMMENDATION_SCHEMA = "rule_effectiveness_recommendation_v1"
REVIEW_SCHEMA = "rule_effectiveness_recommendation_review_v1"
ACTION_SCHEMA = "rule_action_candidate_v1"
DECISION_RECEIPT_SCHEMA = "rule_effectiveness_recommendation_receipt_v1"
POLICY_SCHEMA = "rule_effectiveness_recommendation_policy_v1"

_DEFAULT_POLICY: dict[str, Any] = {
    "schema_version": POLICY_SCHEMA,
    "policy_id": "default_v1",
    "minimum_records_evaluated": 30,
    "maximum_evaluation_error_rate": 0.05,
    "minimum_evaluation_completion_rate": 0.95,
    "minimum_match_coverage": 0.01,
    "maximum_match_coverage": 0.95,
    "rollback": {
        "minimum_labeled_records": 30,
        "maximum_balanced_accuracy": 0.40,
        "maximum_precision": 0.35,
        "minimum_version_regression": 0.15,
    },
    "supersession_review": {
        "maximum_balanced_accuracy": 0.55,
        "minimum_version_disagreement_rate": 0.10,
        "minimum_version_regression": 0.05,
    },
    "monitor": {
        "minimum_balanced_accuracy": 0.55,
        "maximum_balanced_accuracy": 0.70,
    },
}


def build_rule_effectiveness_recommendation_workspace(
    analysis_id: str,
    policy_id: str = "default_v1",
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    analysis = _load_analysis(base, analysis_id)
    receipt = _load_analysis_receipt(base, analysis_id)
    policy = _load_policy(policy_id)
    validation = validate_rule_effectiveness_recommendation_inputs(analysis_id, policy_id, root=base)
    recommendation = _load_recommendation_for_analysis(base, analysis_id, _policy_fingerprint(policy))
    review = _load_review_for_recommendation(base, str((recommendation or {}).get("recommendation_id") or ""))
    candidate = _load_action_candidate_for_review(base, str((review or {}).get("recommendation_review_id") or ""))
    decision_receipt = _load_decision_receipt_for_candidate(base, str((candidate or {}).get("action_candidate_id") or ""))
    comparison = dict(((analysis or {}).get("comparison") or {})) if isinstance(analysis, Mapping) else {}
    outcome = dict(((analysis or {}).get("outcome_metrics") or {})) if isinstance(analysis, Mapping) else {}
    rule_id = str((analysis or {}).get("rule_id") or "")
    return {
        "analysis_id": analysis_id,
        "rule_id": rule_id,
        "analysis_status": str((analysis or {}).get("status") or "missing"),
        "analysis_current": not _is_stale(base, analysis, policy),
        "rule_certification_status": "completed" if isinstance(receipt, dict) and not validation.get("blockers") else "missing",
        "policy_id": policy_id,
        "policy_status": "valid" if not _validate_policy(policy)["blockers"] else "invalid",
        "recommendation_status": str((recommendation or {}).get("recommendation_status") or "not_generated"),
        "recommendation_id": (recommendation or {}).get("recommendation_id"),
        "recommendation_type": (recommendation or {}).get("recommendation_type"),
        "review_status": str((review or {}).get("review_status") or "pending"),
        "recommendation_review_id": (review or {}).get("recommendation_review_id"),
        "action_candidate_id": (candidate or {}).get("action_candidate_id"),
        "action_candidate_type": (candidate or {}).get("action_type"),
        "action_candidate_status": (candidate or {}).get("status"),
        "decision_receipt_id": (decision_receipt or {}).get("recommendation_receipt_id"),
        "triggered_condition_count": len(list((recommendation or {}).get("triggered_conditions", []) or [])),
        "outcome_metrics_available": outcome.get("outcome_metrics_status") == "available",
        "version_comparison_available": bool(comparison.get("comparison_rule_id")),
        "warnings": list(validation.get("warnings", [])),
        "blockers": list(validation.get("blockers", [])),
        "recommended_action": "Generate the deterministic effectiveness recommendation." if not recommendation else _workspace_recommended_action(recommendation, review, candidate, decision_receipt),
    }


def validate_rule_effectiveness_recommendation_inputs(
    analysis_id: str,
    policy_id: str = "default_v1",
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    analysis = _load_analysis(base, analysis_id)
    if not isinstance(analysis, dict):
        return {"valid": False, "analysis_id": analysis_id, "warnings": [], "blockers": ["effectiveness_analysis_not_found"]}
    if str(analysis.get("schema_version") or "") != analysis_backend.ANALYSIS_SCHEMA:
        blockers.append("effectiveness_analysis_schema_unsupported")
    if str(analysis.get("status") or "") not in {"completed", "completed_with_warnings"}:
        blockers.append("effectiveness_analysis_not_completed")
    receipt = _load_analysis_receipt(base, analysis_id)
    if not isinstance(receipt, dict):
        blockers.append("effectiveness_analysis_receipt_missing")
    elif str(receipt.get("analysis_id") or "") != analysis_id:
        blockers.append("effectiveness_analysis_receipt_mismatch")
    elif str(receipt.get("rule_fingerprint") or "") != str(analysis.get("rule_fingerprint") or ""):
        blockers.append("effectiveness_analysis_receipt_rule_fingerprint_mismatch")
    elif str(receipt.get("dataset_fingerprint") or "") != str(analysis.get("dataset_fingerprint") or ""):
        blockers.append("effectiveness_analysis_receipt_dataset_fingerprint_mismatch")
    rule_id = str(analysis.get("rule_id") or "")
    loaded_rule = load_canonical_rule(rule_id, root=base)
    rule = dict(loaded_rule.get("rule") or {}) if loaded_rule.get("status") == "loaded" else None
    if not isinstance(rule, dict):
        blockers.append("canonical_rule_not_found")
    elif analysis_backend._hash_payload(rule) != str(analysis.get("rule_fingerprint") or ""):
        blockers.append("effectiveness_analysis_rule_fingerprint_changed")
    certification = analysis_backend._load_certification_receipt_for_rule(base, rule_id)
    if not isinstance(certification, dict):
        blockers.append("rule_certification_missing")
    else:
        if str(certification.get("certification_status") or "") != "completed":
            blockers.append("rule_certification_incomplete")
        if str(certification.get("certification_receipt_id") or "") != str(analysis.get("certification_receipt_id") or ""):
            blockers.append("rule_certification_receipt_mismatch")
        if isinstance(rule, dict) and str(certification.get("rule_hash") or "") != analysis_backend._hash_payload(rule):
            blockers.append("rule_certification_hash_mismatch")
    dataset = analysis_backend._load_dataset(base, str(analysis.get("dataset_id") or ""))
    if not isinstance(dataset, dict):
        blockers.append("historical_rule_dataset_unavailable")
    elif str(analysis.get("dataset_fingerprint") or "") != analysis_backend._dataset_fingerprint(dataset):
        blockers.append("effectiveness_analysis_dataset_fingerprint_changed")
    comparison_rule_id = str(analysis.get("comparison_rule_id") or "")
    if comparison_rule_id:
        comparison = load_canonical_rule(comparison_rule_id, root=base)
        comparison_rule = dict(comparison.get("rule") or {}) if comparison.get("status") == "loaded" else None
        if not isinstance(comparison_rule, dict):
            blockers.append("comparison_rule_not_found")
        elif analysis_backend._hash_payload(comparison_rule) != str(analysis.get("comparison_rule_fingerprint") or ""):
            blockers.append("comparison_rule_fingerprint_changed")
    if analysis.get("persistent_state_mutated") is True:
        blockers.append("persistent_state_mutated")
    policy = _load_policy(policy_id)
    policy_validation = _validate_policy(policy)
    blockers.extend(policy_validation["blockers"])
    warnings.extend(policy_validation["warnings"])
    records_evaluated = int(analysis.get("records_evaluated", 0) or 0)
    if records_evaluated < int(policy.get("minimum_records_evaluated", 0) or 0):
        blockers.append("minimum_records_evaluated_not_met")
    return {
        "valid": not blockers,
        "analysis_id": analysis_id,
        "policy_id": policy_id,
        "analysis": analysis,
        "receipt": receipt,
        "rule": rule,
        "dataset": dataset,
        "policy": policy,
        "comparison_available": bool(comparison_rule_id),
        "outcome_metrics_available": ((analysis.get("outcome_metrics") or {}).get("outcome_metrics_status") == "available"),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def generate_rule_effectiveness_recommendation(
    analysis_id: str,
    policy_id: str = "default_v1",
    regenerate: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    validation = validate_rule_effectiveness_recommendation_inputs(analysis_id, policy_id, root=base)
    if validation["blockers"]:
        return {"status": "blocked", "analysis_id": analysis_id, "policy_id": policy_id, "warnings": list(validation["warnings"]), "blockers": list(validation["blockers"])}
    analysis = dict(validation["analysis"] or {})
    policy = dict(validation["policy"] or {})
    policy_fingerprint = _policy_fingerprint(policy)
    existing = None if regenerate else _load_recommendation_for_analysis(base, analysis_id, policy_fingerprint)
    if isinstance(existing, dict):
        if _is_recommendation_stale(base, existing, policy):
            return {"status": "blocked", "recommendation_id": existing.get("recommendation_id"), "warnings": [], "blockers": ["effectiveness_recommendation_stale"]}
        if _recommendation_state_diverged(base, existing):
            return {"status": "blocked", "recommendation_id": existing.get("recommendation_id"), "warnings": [], "blockers": ["effectiveness_recommendation_state_diverged"]}
        return {"status": "already_generated", "recommendation_id": existing.get("recommendation_id"), "writes_performed": 0}
    generated = _build_recommendation_record(base, analysis, policy)
    path = _recommendation_path(base, str(generated["recommendation_id"]))
    before_record = analysis_backend._read_json(path)
    before_index = analysis_backend._read_json(base / "indexes" / RECOMMENDATION_INDEX)
    try:
        analysis_backend._atomic_write_json(path, generated)
        _update_recommendation_index(base)
    except Exception:
        analysis_backend._restore_json(path, before_record)
        analysis_backend._restore_json(base / "indexes" / RECOMMENDATION_INDEX, before_index)
        return {"status": "failed", "analysis_id": analysis_id, "warnings": [], "blockers": ["effectiveness_recommendation_write_failure"]}
    return {**generated, "status": "generated"}


def save_rule_effectiveness_recommendation_decision(
    recommendation_id: str,
    decision: str,
    reviewer_note: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    recommendation = _load_recommendation_by_id(base, recommendation_id)
    if not isinstance(recommendation, dict):
        return {"status": "blocked", "warnings": [], "blockers": ["effectiveness_recommendation_not_found"]}
    if _is_recommendation_stale(base, recommendation, _load_policy(str(recommendation.get("policy_id") or "default_v1"))):
        return {"status": "blocked", "recommendation_id": recommendation_id, "warnings": [], "blockers": ["effectiveness_recommendation_stale"]}
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"accept", "reject", "defer", "request_more_evidence"}:
        return {"status": "blocked", "recommendation_id": recommendation_id, "warnings": [], "blockers": ["recommendation_decision_unsupported"]}
    note = _normalize_note(reviewer_note)
    if normalized_decision in {"reject", "defer", "request_more_evidence"} and not note:
        return {"status": "blocked", "recommendation_id": recommendation_id, "warnings": [], "blockers": ["reviewer_note_required"]}
    review_id = _review_id(str(recommendation["recommendation_id"]))
    existing = _load_review_by_id(base, review_id)
    review_status = {
        "accept": "accepted",
        "reject": "rejected",
        "defer": "deferred",
        "request_more_evidence": "more_evidence_requested",
    }[normalized_decision]
    recommendation_fingerprint = _recommendation_fingerprint(recommendation)
    if isinstance(existing, dict):
        if existing.get("decision") == normalized_decision and _normalize_note(existing.get("reviewer_note")) == note and str(existing.get("recommendation_fingerprint") or "") == recommendation_fingerprint:
            return {**existing, "status": "already_reviewed", "writes_performed": 0}
        revision = int(existing.get("review_revision", 0) or 0) + 1
        created_at = str(existing.get("created_at_utc") or analysis_backend._now())
    else:
        revision = 1
        created_at = analysis_backend._now()
    review = {
        "schema_version": REVIEW_SCHEMA,
        "recommendation_review_id": review_id,
        "recommendation_id": recommendation["recommendation_id"],
        "analysis_id": recommendation["analysis_id"],
        "rule_id": recommendation["rule_id"],
        "decision": normalized_decision,
        "review_status": review_status,
        "reviewer_note": note,
        "recommendation_fingerprint": recommendation_fingerprint,
        "review_revision": revision,
        "created_at_utc": created_at,
        "updated_at_utc": analysis_backend._now(),
        "warnings": [],
    }
    path = _review_path(base, review_id)
    before_record = analysis_backend._read_json(path)
    before_index = analysis_backend._read_json(base / "indexes" / REVIEW_INDEX)
    try:
        analysis_backend._atomic_write_json(path, review)
        _update_review_index(base)
    except Exception:
        analysis_backend._restore_json(path, before_record)
        analysis_backend._restore_json(base / "indexes" / REVIEW_INDEX, before_index)
        return {"status": "failed", "recommendation_id": recommendation_id, "warnings": [], "blockers": ["effectiveness_recommendation_review_write_failure"]}
    return {**review, "status": "saved"}


def create_rule_action_candidate_from_recommendation(
    recommendation_review_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    review = _load_review_by_id(base, recommendation_review_id)
    if not isinstance(review, dict):
        return {"status": "blocked", "warnings": [], "blockers": ["effectiveness_recommendation_review_not_found"]}
    if str(confirmation or "") != "QUEUE":
        return {"status": "blocked", "recommendation_review_id": recommendation_review_id, "warnings": [], "blockers": ["queue_confirmation_required"]}
    if str(review.get("decision") or "") != "accept":
        return {"status": "blocked", "recommendation_review_id": recommendation_review_id, "warnings": [], "blockers": ["accepted_recommendation_review_required"]}
    recommendation = _load_recommendation_by_id(base, str(review.get("recommendation_id") or ""))
    if not isinstance(recommendation, dict):
        return {"status": "blocked", "recommendation_review_id": recommendation_review_id, "warnings": [], "blockers": ["effectiveness_recommendation_not_found"]}
    policy = _load_policy(str(recommendation.get("policy_id") or "default_v1"))
    if _is_recommendation_stale(base, recommendation, policy):
        return {"status": "blocked", "recommendation_review_id": recommendation_review_id, "warnings": [], "blockers": ["effectiveness_recommendation_stale"]}
    existing_candidate = _load_action_candidate_for_review(base, recommendation_review_id)
    existing_receipt = _load_decision_receipt_for_recommendation_review(base, recommendation_review_id)
    if isinstance(existing_candidate, dict) and isinstance(existing_receipt, dict):
        return {
            "status": "already_queued",
            "action_candidate_id": existing_candidate.get("action_candidate_id"),
            "recommendation_receipt_id": existing_receipt.get("recommendation_receipt_id"),
            "writes_performed": 0,
        }
    if isinstance(existing_candidate, dict) != isinstance(existing_receipt, dict):
        return {"status": "blocked", "recommendation_review_id": recommendation_review_id, "warnings": [], "blockers": ["effectiveness_recommendation_state_diverged"]}
    candidate = _build_action_candidate(base, recommendation, review)
    decision_receipt = _build_decision_receipt(recommendation, review, candidate, policy)
    review_copy = deepcopy(review)
    review_copy["action_candidate_id"] = candidate["action_candidate_id"]
    review_copy["updated_at_utc"] = analysis_backend._now()
    review_path = _review_path(base, recommendation_review_id)
    candidate_path = _action_candidate_path(base, str(candidate["action_candidate_id"]))
    receipt_path = _decision_receipt_path(base, str(decision_receipt["recommendation_receipt_id"]))
    before_review = analysis_backend._read_json(review_path)
    before_candidate = analysis_backend._read_json(candidate_path)
    before_receipt = analysis_backend._read_json(receipt_path)
    before_action_index = analysis_backend._read_json(base / "indexes" / ACTION_INDEX)
    before_receipt_index = analysis_backend._read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(review_path, review_copy)
        analysis_backend._atomic_write_json(candidate_path, candidate)
        _update_action_index(base)
        analysis_backend._atomic_write_json(receipt_path, decision_receipt)
        _update_decision_receipt_index(base)
    except Exception:
        analysis_backend._restore_json(review_path, before_review)
        analysis_backend._restore_json(candidate_path, before_candidate)
        analysis_backend._restore_json(receipt_path, before_receipt)
        analysis_backend._restore_json(base / "indexes" / ACTION_INDEX, before_action_index)
        analysis_backend._restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "failed_rolled_back", "recommendation_review_id": recommendation_review_id, "warnings": [], "blockers": ["effectiveness_action_candidate_write_failure"]}
    return {**candidate, "recommendation_receipt_id": decision_receipt["recommendation_receipt_id"], "status": "queued"}


def load_rule_effectiveness_recommendation(
    recommendation_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    recommendation = _load_recommendation_by_id(base, recommendation_id)
    if not isinstance(recommendation, dict):
        return {"status": "not_found", "recommendation_id": recommendation_id, "warnings": [], "blockers": ["effectiveness_recommendation_not_found"]}
    policy = _load_policy(str(recommendation.get("policy_id") or "default_v1"))
    stale = _is_recommendation_stale(base, recommendation, policy)
    return {"status": "loaded", "recommendation": recommendation, "stale": stale, "warnings": [], "blockers": ["effectiveness_recommendation_stale"] if stale else []}


def get_rule_effectiveness_recommendation_health(
    rule_id: str | None = None,
    recommendation_type: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    recommendations = _load_recommendations(base)
    reviews = _load_reviews(base)
    candidates = _load_action_candidates(base)
    receipts = _load_decision_receipts(base)
    if rule_id:
        recommendations = [item for item in recommendations if str(item.get("rule_id") or "") == rule_id]
        reviews = [item for item in reviews if str(item.get("rule_id") or "") == rule_id]
        candidates = [item for item in candidates if str(item.get("rule_id") or "") == rule_id]
        receipts = [item for item in receipts if str(item.get("rule_id") or "") == rule_id]
    if recommendation_type:
        recommendations = [item for item in recommendations if str(item.get("recommendation_type") or "") == recommendation_type]
    if not recommendations and not reviews and not candidates and not receipts:
        return {"status": "empty", "recommendation_count": 0, "current_recommendation_count": 0, "stale_recommendation_count": 0, "accepted_count": 0, "pending_review_count": 0, "action_candidate_count": 0, "divergent_state_count": 0, "warnings": [], "recommended_action": "Generate one deterministic effectiveness recommendation."}
    stale = 0
    divergent = 0
    warnings: list[str] = []
    for item in recommendations:
        if _is_recommendation_stale(base, item, _load_policy(str(item.get("policy_id") or "default_v1"))):
            stale += 1
        if not list(item.get("triggered_conditions", []) or []):
            divergent += 1
    accepted_without_candidate = 0
    for review in reviews:
        if str(review.get("decision") or "") == "accept" and not _load_action_candidate_for_review(base, str(review.get("recommendation_review_id") or "")):
            accepted_without_candidate += 1
    candidate_without_receipt = sum(1 for item in candidates if not _load_decision_receipt_for_candidate(base, str(item.get("action_candidate_id") or "")))
    divergent += accepted_without_candidate + candidate_without_receipt
    if stale:
        warnings.append("one_recommendation_is_stale_after_analysis_change")
    status = "corrupt" if divergent else "stale" if stale else "healthy"
    if warnings and status == "healthy":
        status = "warning"
    return {
        "status": status,
        "recommendation_count": len(recommendations),
        "current_recommendation_count": len(recommendations) - stale,
        "stale_recommendation_count": stale,
        "accepted_count": sum(1 for item in reviews if str(item.get("decision") or "") == "accept"),
        "pending_review_count": max(len(recommendations) - len(reviews), 0),
        "action_candidate_count": len(candidates),
        "divergent_state_count": divergent,
        "warnings": warnings,
        "recommended_action": "Regenerate one recommendation from the current analysis." if stale else "Recommendation health is good.",
    }


def format_rule_effectiveness_recommendation_report(
    recommendation_id: str | None = None,
    action_candidate_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    candidate = _load_action_candidate_by_id(base, action_candidate_id) if action_candidate_id else None
    recommendation = _load_recommendation_by_id(base, recommendation_id or str((candidate or {}).get("recommendation_id") or ""))
    if not isinstance(recommendation, dict):
        return "Rule Effectiveness Recommendation Report\n\nStatus: not_found"
    review = _load_review_for_recommendation(base, str(recommendation.get("recommendation_id") or ""))
    if not isinstance(candidate, dict):
        candidate = _load_action_candidate_for_review(base, str((review or {}).get("recommendation_review_id") or ""))
    policy = _load_policy(str(recommendation.get("policy_id") or "default_v1"))
    stale = _is_recommendation_stale(base, recommendation, policy)
    lines = [
        "Rule Effectiveness Recommendation Report",
        "",
        f"Rule: {recommendation.get('rule_id')}",
        f"Analysis: {'stale' if stale else 'current'}",
        f"Policy: {recommendation.get('policy_id')}",
        f"Recommendation: {recommendation.get('recommendation_type')}",
        "",
        "Triggered Conditions:",
    ]
    for item in list(recommendation.get("triggered_conditions", []) or []):
        lines.append(f"- {item.get('condition_id')}: actual={item.get('actual_value')} threshold={item.get('threshold')}")
    if len(lines) == 7:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Review:",
            f"- Decision: {str((review or {}).get('decision') or 'pending')}",
            f"- Status: {str((review or {}).get('review_status') or 'pending')}",
            "",
            "Action Candidate:",
            f"- Type: {str((candidate or {}).get('action_type') or 'none')}",
            f"- Status: {str((candidate or {}).get('status') or 'not_queued')}",
            "- Automatic Rollback Performed: No",
            "- Rule Modified: No",
            "",
            "Important:",
            "This recommendation was produced from explicit metrics and fixed policy thresholds.",
            "No rollback, supersession, scoring change, objective-pack change, Fast Lane action, or replay execution occurred.",
        ]
    )
    text = "\n".join(lines)
    if public_safe:
        for needle in ("C:\\", "/Users/", "evaluation_context", "reviewer_note", "Traceback", "token", "secret", "api_key"):
            text = text.replace(needle, "[redacted]")
    return text


def _ensure_dirs(root: Path | str) -> Path:
    base = analysis_backend._ensure_analysis_dirs(root)
    for folder in (RECOMMENDATION_DIR, REVIEW_DIR, ACTION_CANDIDATE_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for path, payload in (
        (base / "indexes" / RECOMMENDATION_INDEX, {"schema_version": "rule_effectiveness_recommendation_index_v1", "items": [], "updated_at_utc": analysis_backend._now()}),
        (base / "indexes" / REVIEW_INDEX, {"schema_version": "rule_effectiveness_recommendation_review_index_v1", "items": [], "updated_at_utc": analysis_backend._now()}),
        (base / "indexes" / ACTION_INDEX, {"schema_version": "rule_action_candidate_index_v1", "items": [], "updated_at_utc": analysis_backend._now()}),
        (base / "indexes" / RECEIPT_INDEX, {"schema_version": "rule_effectiveness_recommendation_receipt_index_v1", "items": [], "updated_at_utc": analysis_backend._now()}),
    ):
        if not path.exists():
            analysis_backend._atomic_write_json(path, payload)
    return base


def _load_policy(policy_id: str) -> dict[str, Any]:
    if policy_id == "default_v1":
        return deepcopy(_DEFAULT_POLICY)
    return {"schema_version": POLICY_SCHEMA, "policy_id": policy_id}


def _validate_policy(policy: Mapping[str, Any]) -> dict[str, list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if str(policy.get("schema_version") or "") != POLICY_SCHEMA:
        blockers.append("recommendation_policy_schema_unsupported")
    required = {"minimum_records_evaluated", "maximum_evaluation_error_rate", "minimum_evaluation_completion_rate", "minimum_match_coverage", "maximum_match_coverage", "rollback", "supersession_review", "monitor"}
    for key in required:
        if key not in policy:
            blockers.append(f"recommendation_policy_missing_{key}")
    if blockers:
        return {"warnings": [], "blockers": _dedupe(blockers)}
    numeric_paths = [
        ("minimum_records_evaluated", policy.get("minimum_records_evaluated")),
        ("maximum_evaluation_error_rate", policy.get("maximum_evaluation_error_rate")),
        ("minimum_evaluation_completion_rate", policy.get("minimum_evaluation_completion_rate")),
        ("minimum_match_coverage", policy.get("minimum_match_coverage")),
        ("maximum_match_coverage", policy.get("maximum_match_coverage")),
        ("rollback.minimum_labeled_records", (policy.get("rollback") or {}).get("minimum_labeled_records")),
        ("rollback.maximum_balanced_accuracy", (policy.get("rollback") or {}).get("maximum_balanced_accuracy")),
        ("rollback.maximum_precision", (policy.get("rollback") or {}).get("maximum_precision")),
        ("rollback.minimum_version_regression", (policy.get("rollback") or {}).get("minimum_version_regression")),
        ("supersession_review.maximum_balanced_accuracy", (policy.get("supersession_review") or {}).get("maximum_balanced_accuracy")),
        ("supersession_review.minimum_version_disagreement_rate", (policy.get("supersession_review") or {}).get("minimum_version_disagreement_rate")),
        ("supersession_review.minimum_version_regression", (policy.get("supersession_review") or {}).get("minimum_version_regression")),
        ("monitor.minimum_balanced_accuracy", (policy.get("monitor") or {}).get("minimum_balanced_accuracy")),
        ("monitor.maximum_balanced_accuracy", (policy.get("monitor") or {}).get("maximum_balanced_accuracy")),
    ]
    for name, value in numeric_paths:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            blockers.append(f"recommendation_policy_invalid_{name.replace('.', '_')}")
            continue
        if "minimum_records" in name or "minimum_labeled_records" in name:
            if value < 0:
                blockers.append(f"recommendation_policy_invalid_{name.replace('.', '_')}")
        elif value < 0 or value > 1:
            blockers.append(f"recommendation_policy_invalid_{name.replace('.', '_')}")
    if float(policy.get("minimum_match_coverage", 0) or 0) > float(policy.get("maximum_match_coverage", 0) or 0):
        blockers.append("recommendation_policy_match_coverage_invalid")
    if float((policy.get("rollback") or {}).get("maximum_balanced_accuracy", 0) or 0) > float((policy.get("monitor") or {}).get("minimum_balanced_accuracy", 0) or 0):
        blockers.append("recommendation_policy_rollback_monitor_order_invalid")
    unsupported = sorted(set(policy.keys()) - {"schema_version", "policy_id", "minimum_records_evaluated", "maximum_evaluation_error_rate", "minimum_evaluation_completion_rate", "minimum_match_coverage", "maximum_match_coverage", "rollback", "supersession_review", "monitor"})
    if unsupported:
        warnings.append("recommendation_policy_contains_unsupported_keys")
    return {"warnings": _dedupe(warnings), "blockers": _dedupe(blockers)}


def _policy_fingerprint(policy: Mapping[str, Any]) -> str:
    return analysis_backend._hash_payload(
        {
            "schema_version": policy.get("schema_version"),
            "policy_id": policy.get("policy_id"),
            "minimum_records_evaluated": policy.get("minimum_records_evaluated"),
            "maximum_evaluation_error_rate": policy.get("maximum_evaluation_error_rate"),
            "minimum_evaluation_completion_rate": policy.get("minimum_evaluation_completion_rate"),
            "minimum_match_coverage": policy.get("minimum_match_coverage"),
            "maximum_match_coverage": policy.get("maximum_match_coverage"),
            "rollback": policy.get("rollback"),
            "supersession_review": policy.get("supersession_review"),
            "monitor": policy.get("monitor"),
        }
    )


def _build_recommendation_record(base: Path, analysis: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    comparison = dict(analysis.get("comparison") or {})
    outcome = dict(analysis.get("outcome_metrics") or {})
    policy_fingerprint = _policy_fingerprint(policy)
    rule = load_canonical_rule(str(analysis.get("rule_id") or ""), root=base)
    current_rule = dict(rule.get("rule") or {}) if rule.get("status") == "loaded" else {}
    current_active = str(current_rule.get("status") or "") == "active"
    labeled_count = _labeled_record_count(outcome)
    conditions = _evaluate_conditions(analysis, policy, current_active, labeled_count)
    recommendation_type = _pick_recommendation_type(conditions)
    triggered = [item for item in conditions if item.get("triggered")]
    secondary: list[str] = []
    if recommendation_type != "monitor" and _condition_lookup(conditions, "monitor_band")["triggered"]:
        secondary.append("monitor_band_detected")
    dataset = analysis_backend._load_dataset(base, str(analysis.get("dataset_id") or ""))
    recommendation = {
        "schema_version": RECOMMENDATION_SCHEMA,
        "recommendation_id": _recommendation_id(str(analysis.get("analysis_id") or ""), policy_fingerprint),
        "analysis_id": analysis.get("analysis_id"),
        "effectiveness_receipt_id": (_load_analysis_receipt(base, str(analysis.get("analysis_id") or "")) or {}).get("effectiveness_receipt_id"),
        "rule_id": analysis.get("rule_id"),
        "rule_fingerprint": analysis.get("rule_fingerprint"),
        "certification_receipt_id": analysis.get("certification_receipt_id"),
        "dataset_id": analysis.get("dataset_id"),
        "dataset_fingerprint": analysis.get("dataset_fingerprint"),
        "comparison_rule_id": analysis.get("comparison_rule_id"),
        "comparison_rule_fingerprint": analysis.get("comparison_rule_fingerprint"),
        "policy_id": policy.get("policy_id"),
        "policy_fingerprint": policy_fingerprint,
        "recommendation_type": recommendation_type,
        "recommendation_status": "generated",
        "triggered_conditions": triggered,
        "non_triggered_conditions": [item for item in conditions if not item.get("triggered")],
        "supporting_metrics": {
            "records_evaluated": analysis.get("records_evaluated"),
            "match_coverage": analysis.get("match_coverage"),
            "evaluation_completion_rate": analysis.get("evaluation_completion_rate"),
            "evaluation_error_rate": analysis.get("evaluation_error_rate"),
            "outcome_metrics_status": outcome.get("outcome_metrics_status"),
            "labeled_record_count": labeled_count,
            "precision": outcome.get("precision"),
            "balanced_accuracy": outcome.get("balanced_accuracy"),
            "version_regression": _version_regression(comparison),
            "version_disagreement_rate": comparison.get("match_disagreement_rate"),
            "comparison_rule_id": analysis.get("comparison_rule_id"),
            "dataset_record_count": len(list((dataset or {}).get("records", []) or [])) if isinstance(dataset, Mapping) else 0,
        },
        "secondary_observations": secondary,
        "created_at_utc": analysis_backend._now(),
        "warnings": list(analysis.get("warnings", [])),
        "blockers": [],
    }
    return recommendation


def _evaluate_conditions(analysis: Mapping[str, Any], policy: Mapping[str, Any], current_active: bool, labeled_count: int) -> list[dict[str, Any]]:
    outcome = dict(analysis.get("outcome_metrics") or {})
    comparison = dict(analysis.get("comparison") or {})
    rollback = dict(policy.get("rollback") or {})
    supersession = dict(policy.get("supersession_review") or {})
    monitor = dict(policy.get("monitor") or {})
    conditions = [
        _condition("evaluation_completion_below_minimum", "evaluation_completion_rate", analysis.get("evaluation_completion_rate"), "less_than", policy.get("minimum_evaluation_completion_rate")),
        _condition("evaluation_error_above_maximum", "evaluation_error_rate", analysis.get("evaluation_error_rate"), "greater_than", policy.get("maximum_evaluation_error_rate")),
        _condition("match_coverage_below_minimum", "match_coverage", analysis.get("match_coverage"), "less_than", policy.get("minimum_match_coverage")),
        _condition("match_coverage_above_maximum", "match_coverage", analysis.get("match_coverage"), "greater_than", policy.get("maximum_match_coverage")),
        _condition("records_evaluated_below_minimum", "records_evaluated", analysis.get("records_evaluated"), "less_than", policy.get("minimum_records_evaluated")),
        _condition("outcome_metrics_unavailable", "outcome_metrics_status", outcome.get("outcome_metrics_status"), "equals", "unavailable"),
        _condition("rollback_labeled_records_below_minimum", "labeled_record_count", labeled_count, "less_than", rollback.get("minimum_labeled_records")),
        _condition("rollback_balanced_accuracy_below_threshold", "balanced_accuracy", outcome.get("balanced_accuracy"), "less_than_or_equal", rollback.get("maximum_balanced_accuracy")),
        _condition("rollback_precision_below_threshold", "precision", outcome.get("precision"), "less_than_or_equal", rollback.get("maximum_precision")),
        _condition("rollback_version_regression_met", "version_regression", _version_regression(comparison), "greater_than_or_equal", rollback.get("minimum_version_regression")),
        _condition("supersession_balanced_accuracy_below_threshold", "balanced_accuracy", outcome.get("balanced_accuracy"), "less_than_or_equal", supersession.get("maximum_balanced_accuracy")),
        _condition("supersession_disagreement_rate_met", "match_disagreement_rate", comparison.get("match_disagreement_rate"), "greater_than_or_equal", supersession.get("minimum_version_disagreement_rate")),
        _condition("supersession_version_regression_met", "version_regression", _version_regression(comparison), "greater_than_or_equal", supersession.get("minimum_version_regression")),
        _condition("monitor_band", "balanced_accuracy", outcome.get("balanced_accuracy"), "between", [monitor.get("minimum_balanced_accuracy"), monitor.get("maximum_balanced_accuracy")]),
        _condition("rule_currently_active", "rule_status", "active" if current_active else "inactive", "equals", "active"),
    ]
    return conditions


def _pick_recommendation_type(conditions: list[dict[str, Any]]) -> str:
    lookup = {str(item["condition_id"]): item for item in conditions}
    if lookup["evaluation_completion_below_minimum"]["triggered"] or lookup["evaluation_error_above_maximum"]["triggered"] or lookup["match_coverage_below_minimum"]["triggered"] or lookup["match_coverage_above_maximum"]["triggered"]:
        return "review_data_quality"
    if lookup["records_evaluated_below_minimum"]["triggered"] or lookup["outcome_metrics_unavailable"]["triggered"] or lookup["rollback_labeled_records_below_minimum"]["triggered"]:
        return "insufficient_evidence"
    if lookup["rule_currently_active"]["triggered"] and lookup["rollback_balanced_accuracy_below_threshold"]["triggered"] and (lookup["rollback_precision_below_threshold"]["triggered"] or lookup["rollback_version_regression_met"]["triggered"]):
        return "rollback_candidate"
    if lookup["rule_currently_active"]["triggered"] and lookup["supersession_balanced_accuracy_below_threshold"]["triggered"] and (lookup["supersession_disagreement_rate_met"]["triggered"] or lookup["supersession_version_regression_met"]["triggered"]):
        return "supersession_review_candidate"
    if lookup["monitor_band"]["triggered"]:
        return "monitor"
    return "continue"


def _condition(condition_id: str, metric: str, actual_value: Any, operator: str, threshold: Any) -> dict[str, Any]:
    available = actual_value is not None
    triggered = False
    if operator == "equals":
        triggered = available and actual_value == threshold
    elif operator == "less_than":
        triggered = available and float(actual_value) < float(threshold)
    elif operator == "greater_than":
        triggered = available and float(actual_value) > float(threshold)
    elif operator == "less_than_or_equal":
        triggered = available and float(actual_value) <= float(threshold)
    elif operator == "greater_than_or_equal":
        triggered = available and float(actual_value) >= float(threshold)
    elif operator == "between":
        minimum, maximum = threshold
        triggered = available and minimum is not None and maximum is not None and float(minimum) <= float(actual_value) <= float(maximum)
    return {
        "condition_id": condition_id,
        "metric": metric,
        "actual_value": actual_value,
        "operator": operator,
        "threshold": threshold,
        "triggered": bool(triggered),
        "available": available,
    }


def _workspace_recommended_action(recommendation: Mapping[str, Any], review: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None, decision_receipt: Mapping[str, Any] | None) -> str:
    if isinstance(candidate, Mapping) and isinstance(decision_receipt, Mapping):
        return "Await one explicit human action on the queued candidate."
    if isinstance(review, Mapping) and str(review.get("decision") or "") == "accept":
        return "Queue one controlled action candidate with QUEUE confirmation."
    if isinstance(review, Mapping):
        return "Review is recorded. Generate a new recommendation only after analysis changes."
    return f"Review the {recommendation.get('recommendation_type')} recommendation and save a human decision."


def _load_analysis(root: Path, analysis_id: str) -> dict[str, Any] | None:
    loaded = analysis_backend.load_rule_effectiveness_analysis(analysis_id, root=root)
    if loaded.get("status") == "loaded":
        return deepcopy(dict(loaded.get("analysis") or {}))
    return None


def _load_analysis_receipt(root: Path, analysis_id: str) -> dict[str, Any] | None:
    return analysis_backend._load_receipt_for_analysis(root, analysis_id)


def _labeled_record_count(outcome: Mapping[str, Any]) -> int:
    if str(outcome.get("outcome_metrics_status") or "") != "available":
        return 0
    return sum(int(outcome.get(name, 0) or 0) for name in ("true_positives", "false_positives", "true_negatives", "false_negatives"))


def _version_regression(comparison: Mapping[str, Any]) -> float | None:
    deltas = dict(comparison.get("metric_deltas") or {})
    delta = deltas.get("balanced_accuracy_delta")
    if isinstance(delta, (int, float)):
        return -float(delta)
    return None


def _recommendation_id(analysis_id: str, policy_fingerprint: str) -> str:
    suffix = policy_fingerprint[7:19]
    return f"rule_recommendation_{analysis_backend._safe_id(analysis_id)}_{suffix}"


def _review_id(recommendation_id: str) -> str:
    return f"rule_recommendation_review_{analysis_backend._safe_id(recommendation_id)[-24:]}"


def _action_candidate_id(review_id: str) -> str:
    return f"rule_action_candidate_{analysis_backend._safe_id(review_id)[-24:]}"


def _decision_receipt_id(action_candidate_id: str) -> str:
    return f"rule_recommendation_receipt_{analysis_backend._safe_id(action_candidate_id)[-24:]}"


def _recommendation_fingerprint(recommendation: Mapping[str, Any]) -> str:
    return analysis_backend._hash_payload(
        {
            "analysis_id": recommendation.get("analysis_id"),
            "rule_id": recommendation.get("rule_id"),
            "rule_fingerprint": recommendation.get("rule_fingerprint"),
            "dataset_fingerprint": recommendation.get("dataset_fingerprint"),
            "policy_fingerprint": recommendation.get("policy_fingerprint"),
            "comparison_rule_fingerprint": recommendation.get("comparison_rule_fingerprint"),
            "recommendation_type": recommendation.get("recommendation_type"),
            "triggered_conditions": recommendation.get("triggered_conditions"),
            "supporting_metrics": recommendation.get("supporting_metrics"),
        }
    )


def _build_action_candidate(base: Path, recommendation: Mapping[str, Any], review: Mapping[str, Any]) -> dict[str, Any]:
    action_type = {
        "rollback_candidate": "rollback_review",
        "supersession_review_candidate": "supersession_review",
        "monitor": "monitoring",
        "continue": "no_action",
        "review_data_quality": "data_quality_review",
        "request_more_evidence": "evidence_collection",
        "insufficient_evidence": "evidence_collection",
    }[str(recommendation.get("recommendation_type") or "continue")]
    rule = load_canonical_rule(str(recommendation.get("rule_id") or ""), root=base)
    current_rule = dict(rule.get("rule") or {}) if rule.get("status") == "loaded" else {}
    version_chain_id = _find_version_chain_id(base, str(recommendation.get("rule_id") or ""), str(recommendation.get("comparison_rule_id") or ""))
    future_handler = None
    future_confirmation = None
    warnings: list[str] = []
    if action_type == "rollback_review":
        if current_rule.get("source_rule_activation_review_id"):
            future_handler = "rollback_proposal_rule_activation"
            future_confirmation = "ROLLBACK"
        else:
            warnings.append("action_handler_unresolved")
    elif action_type == "supersession_review":
        warnings.append("action_handler_unresolved")
    return {
        "schema_version": ACTION_SCHEMA,
        "action_candidate_id": _action_candidate_id(str(review.get("recommendation_review_id") or "")),
        "recommendation_id": recommendation.get("recommendation_id"),
        "recommendation_review_id": review.get("recommendation_review_id"),
        "analysis_id": recommendation.get("analysis_id"),
        "rule_id": recommendation.get("rule_id"),
        "rule_fingerprint": recommendation.get("rule_fingerprint"),
        "action_type": action_type,
        "status": "pending_human_action",
        "target_rule_id": recommendation.get("rule_id"),
        "target_version_chain_id": version_chain_id,
        "future_handler": future_handler,
        "future_confirmation_required": future_confirmation,
        "created_at_utc": analysis_backend._now(),
        "warnings": warnings,
    }


def _build_decision_receipt(recommendation: Mapping[str, Any], review: Mapping[str, Any], candidate: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": DECISION_RECEIPT_SCHEMA,
        "recommendation_receipt_id": _decision_receipt_id(str(candidate.get("action_candidate_id") or "")),
        "recommendation_id": recommendation.get("recommendation_id"),
        "recommendation_review_id": review.get("recommendation_review_id"),
        "action_candidate_id": candidate.get("action_candidate_id"),
        "analysis_id": recommendation.get("analysis_id"),
        "rule_id": recommendation.get("rule_id"),
        "rule_fingerprint": recommendation.get("rule_fingerprint"),
        "policy_id": policy.get("policy_id"),
        "policy_fingerprint": _policy_fingerprint(policy),
        "decision": review.get("decision"),
        "action_type": candidate.get("action_type"),
        "receipt_status": "completed",
        "created_at_utc": analysis_backend._now(),
        "warnings": list(candidate.get("warnings", [])),
    }


def _is_stale(base: Path, analysis: Mapping[str, Any] | None, policy: Mapping[str, Any]) -> bool:
    if not isinstance(analysis, Mapping):
        return True
    rule = load_canonical_rule(str(analysis.get("rule_id") or ""), root=base)
    current_rule = dict(rule.get("rule") or {}) if rule.get("status") == "loaded" else None
    if not isinstance(current_rule, dict) or analysis_backend._hash_payload(current_rule) != str(analysis.get("rule_fingerprint") or ""):
        return True
    dataset = analysis_backend._load_dataset(base, str(analysis.get("dataset_id") or ""))
    if not isinstance(dataset, dict) or str(analysis.get("dataset_fingerprint") or "") != analysis_backend._dataset_fingerprint(dataset):
        return True
    certification = analysis_backend._load_certification_receipt_for_rule(base, str(analysis.get("rule_id") or ""))
    if not isinstance(certification, dict) or str(certification.get("certification_receipt_id") or "") != str(analysis.get("certification_receipt_id") or ""):
        return True
    if str(certification.get("rule_hash") or "") != analysis_backend._hash_payload(current_rule):
        return True
    comparison_rule_id = str(analysis.get("comparison_rule_id") or "")
    if comparison_rule_id:
        comparison = load_canonical_rule(comparison_rule_id, root=base)
        comparison_rule = dict(comparison.get("rule") or {}) if comparison.get("status") == "loaded" else None
        if not isinstance(comparison_rule, dict) or analysis_backend._hash_payload(comparison_rule) != str(analysis.get("comparison_rule_fingerprint") or ""):
            return True
    _ = policy
    return False


def _is_recommendation_stale(base: Path, recommendation: Mapping[str, Any], policy: Mapping[str, Any]) -> bool:
    analysis = _load_analysis(base, str(recommendation.get("analysis_id") or ""))
    if _is_stale(base, analysis, policy):
        return True
    if str(recommendation.get("policy_fingerprint") or "") != _policy_fingerprint(policy):
        return True
    return False


def _recommendation_state_diverged(base: Path, recommendation: Mapping[str, Any]) -> bool:
    review = _load_review_for_recommendation(base, str(recommendation.get("recommendation_id") or ""))
    candidate = _load_action_candidate_for_review(base, str((review or {}).get("recommendation_review_id") or ""))
    receipt = _load_decision_receipt_for_candidate(base, str((candidate or {}).get("action_candidate_id") or ""))
    return isinstance(candidate, dict) != isinstance(receipt, dict)


def _normalize_note(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _find_version_chain_id(base: Path, rule_id: str, comparison_rule_id: str) -> str | None:
    if not rule_id:
        return None
    for path in sorted((base / SUPERSESSION_CHAIN_DIR).glob("*.json")):
        payload = analysis_backend._read_json(path)
        if not isinstance(payload, dict):
            continue
        versions = payload.get("versions", [])
        ids = {str(item.get("rule_id") or "") for item in versions if isinstance(item, Mapping)}
        if rule_id in ids and (not comparison_rule_id or comparison_rule_id in ids):
            return str(payload.get("version_chain_id") or "") or None
    return None


def _condition_lookup(conditions: list[dict[str, Any]], condition_id: str) -> dict[str, Any]:
    for item in conditions:
        if str(item.get("condition_id") or "") == condition_id:
            return item
    return {"condition_id": condition_id, "triggered": False}


def _recommendation_path(root: Path, recommendation_id: str) -> Path:
    return root / RECOMMENDATION_DIR / f"{analysis_backend._safe_id(recommendation_id)}.json"


def _review_path(root: Path, review_id: str) -> Path:
    return root / REVIEW_DIR / f"{analysis_backend._safe_id(review_id)}.json"


def _action_candidate_path(root: Path, action_candidate_id: str) -> Path:
    return root / ACTION_CANDIDATE_DIR / f"{analysis_backend._safe_id(action_candidate_id)}.json"


def _decision_receipt_path(root: Path, receipt_id: str) -> Path:
    return root / RECEIPT_DIR / f"{analysis_backend._safe_id(receipt_id)}.json"


def _load_recommendation_by_id(root: Path, recommendation_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_recommendation_path(root, recommendation_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_review_by_id(root: Path, review_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_review_path(root, review_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_action_candidate_by_id(root: Path, action_candidate_id: str | None) -> dict[str, Any] | None:
    if not action_candidate_id:
        return None
    payload = analysis_backend._read_json(_action_candidate_path(root, action_candidate_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_recommendation_for_analysis(root: Path, analysis_id: str, policy_fingerprint: str) -> dict[str, Any] | None:
    recommendation_id = _recommendation_id(analysis_id, policy_fingerprint)
    return _load_recommendation_by_id(root, recommendation_id)


def _load_review_for_recommendation(root: Path, recommendation_id: str) -> dict[str, Any] | None:
    review = _load_review_by_id(root, _review_id(recommendation_id))
    return review if isinstance(review, dict) and str(review.get("recommendation_id") or "") == recommendation_id else None


def _load_action_candidate_for_review(root: Path, review_id: str) -> dict[str, Any] | None:
    candidate = _load_action_candidate_by_id(root, _action_candidate_id(review_id))
    return candidate if isinstance(candidate, dict) and str(candidate.get("recommendation_review_id") or "") == review_id else None


def _load_decision_receipt_for_candidate(root: Path, action_candidate_id: str) -> dict[str, Any] | None:
    if not action_candidate_id:
        return None
    receipt = _load_decision_receipt_by_id(root, _decision_receipt_id(action_candidate_id))
    return receipt if isinstance(receipt, dict) and str(receipt.get("action_candidate_id") or "") == action_candidate_id else None


def _load_decision_receipt_for_recommendation_review(root: Path, review_id: str) -> dict[str, Any] | None:
    candidate = _load_action_candidate_for_review(root, review_id)
    return _load_decision_receipt_for_candidate(root, str((candidate or {}).get("action_candidate_id") or ""))


def _load_decision_receipt_by_id(root: Path, receipt_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_decision_receipt_path(root, receipt_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_recommendations(root: Path) -> list[dict[str, Any]]:
    return [dict(item) for item in _load_directory_records(root / RECOMMENDATION_DIR)]


def _load_reviews(root: Path) -> list[dict[str, Any]]:
    return [dict(item) for item in _load_directory_records(root / REVIEW_DIR)]


def _load_action_candidates(root: Path) -> list[dict[str, Any]]:
    return [dict(item) for item in _load_directory_records(root / ACTION_CANDIDATE_DIR)]


def _load_decision_receipts(root: Path) -> list[dict[str, Any]]:
    return [dict(item) for item in _load_directory_records(root / RECEIPT_DIR)]


def _load_directory_records(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record_path in sorted(path.glob("*.json")):
        payload = analysis_backend._read_json(record_path)
        if isinstance(payload, dict):
            items.append(deepcopy(dict(payload)))
    return items


def _update_recommendation_index(root: Path) -> None:
    items = [
        {
            "recommendation_id": item.get("recommendation_id"),
            "analysis_id": item.get("analysis_id"),
            "rule_id": item.get("rule_id"),
            "recommendation_type": item.get("recommendation_type"),
            "recommendation_status": item.get("recommendation_status"),
            "created_at_utc": item.get("created_at_utc"),
        }
        for item in _load_recommendations(root)
    ]
    analysis_backend._atomic_write_json(root / "indexes" / RECOMMENDATION_INDEX, {"schema_version": "rule_effectiveness_recommendation_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_review_index(root: Path) -> None:
    items = [
        {
            "recommendation_review_id": item.get("recommendation_review_id"),
            "recommendation_id": item.get("recommendation_id"),
            "rule_id": item.get("rule_id"),
            "decision": item.get("decision"),
            "review_status": item.get("review_status"),
            "updated_at_utc": item.get("updated_at_utc"),
        }
        for item in _load_reviews(root)
    ]
    analysis_backend._atomic_write_json(root / "indexes" / REVIEW_INDEX, {"schema_version": "rule_effectiveness_recommendation_review_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_action_index(root: Path) -> None:
    items = [
        {
            "action_candidate_id": item.get("action_candidate_id"),
            "recommendation_review_id": item.get("recommendation_review_id"),
            "rule_id": item.get("rule_id"),
            "action_type": item.get("action_type"),
            "status": item.get("status"),
            "created_at_utc": item.get("created_at_utc"),
        }
        for item in _load_action_candidates(root)
    ]
    analysis_backend._atomic_write_json(root / "indexes" / ACTION_INDEX, {"schema_version": "rule_action_candidate_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_decision_receipt_index(root: Path) -> None:
    items = [
        {
            "recommendation_receipt_id": item.get("recommendation_receipt_id"),
            "recommendation_id": item.get("recommendation_id"),
            "recommendation_review_id": item.get("recommendation_review_id"),
            "action_candidate_id": item.get("action_candidate_id"),
            "rule_id": item.get("rule_id"),
            "action_type": item.get("action_type"),
            "receipt_status": item.get("receipt_status"),
            "created_at_utc": item.get("created_at_utc"),
        }
        for item in _load_decision_receipts(root)
    ]
    analysis_backend._atomic_write_json(root / "indexes" / RECEIPT_INDEX, {"schema_version": "rule_effectiveness_recommendation_receipt_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item)))


__all__ = [
    "build_rule_effectiveness_recommendation_workspace",
    "validate_rule_effectiveness_recommendation_inputs",
    "generate_rule_effectiveness_recommendation",
    "save_rule_effectiveness_recommendation_decision",
    "create_rule_action_candidate_from_recommendation",
    "load_rule_effectiveness_recommendation",
    "get_rule_effectiveness_recommendation_health",
    "format_rule_effectiveness_recommendation_report",
]
