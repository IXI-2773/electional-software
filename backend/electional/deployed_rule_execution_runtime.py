"""Read-only deployed-rule execution entrypoint over completed Phase 9V deployments."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from . import certified_rule_production_deployment as deployment_backend
from . import deployed_rule_operational_telemetry as telemetry_backend
from . import production_deployment_adapter as adapter_backend
from .canonical_rule_runtime import (
    _hash_payload,
    evaluate_canonical_rule,
    get_canonical_rule_runtime_capability,
    load_canonical_rule,
)
from .source_documents import SOURCE_DOCUMENT_ROOT

MANIFEST_SCHEMA = "deployed_rule_execution_runtime_manifest_v1"
EXECUTION_RUNTIME_SCHEMA = "deployed_rule_execution_runtime_v1"
PUBLIC_FUNCTIONS = [
    "build_deployed_rule_execution_workspace",
    "validate_deployed_rule_execution_eligibility",
    "execute_deployed_rule",
    "format_deployed_rule_execution_report",
    "get_deployed_rule_execution_runtime_manifest",
]


def get_deployed_rule_execution_runtime_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    capability = get_canonical_rule_runtime_capability(root=root)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "execution_runtime_schema_version": EXECUTION_RUNTIME_SCHEMA,
        "runtime_id": "deployed_rule_execution_runtime_v1",
        "runtime_version": "1",
        "entrypoint_available": bool(capability.get("single_rule_evaluator_available")),
        "canonical_evaluator_module": "canonical_rule_runtime",
        "canonical_evaluator_function": "evaluate_canonical_rule",
        "required_identifiers": [
            "canonical_rule_id",
            "production_deployment_result_id",
            "production_target_id",
            "deployed_rule_id",
        ],
        "execution_statuses": ["completed", "failed", "skipped", "blocked", "unsupported"],
        "telemetry_recording_status": "execution_telemetry_producer_available",
    }
    manifest["manifest_fingerprint"] = _hash_payload({key: manifest.get(key) for key in sorted(manifest) if key != "manifest_fingerprint"})
    return manifest


def build_deployed_rule_execution_workspace(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    *,
    execution_input: Mapping[str, Any] | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _execution_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        execution_input=execution_input,
        root=root,
    )
    eligibility = validate_deployed_rule_execution_eligibility(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        execution_input=execution_input,
        root=root,
    )
    deployment_result = context.get("deployment_result") if isinstance(context.get("deployment_result"), Mapping) else {}
    return {
        "status": "ready" if str(eligibility.get("status") or "") in {"eligible", "eligible_with_warnings"} else str(eligibility.get("status") or "blocked"),
        "canonical_rule_id": deployment_result.get("canonical_rule_id") or canonical_rule_id,
        "canonical_rule_fingerprint": deployment_result.get("canonical_rule_fingerprint"),
        "deployed_rule_id": deployment_result.get("deployed_rule_id") or deployed_rule_id,
        "deployed_rule_fingerprint": (context.get("deployed_rule") or {}).get("rule_fingerprint") if isinstance(context.get("deployed_rule"), Mapping) else None,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": deployment_result.get("production_target_id") or production_target_id,
        "production_transaction_id": deployment_result.get("production_transaction_id"),
        "document_id": deployment_result.get("document_id"),
        "source_revision": deployment_result.get("source_revision"),
        "phase_9v_result_status": deployment_result.get("final_status", (context.get("deployment_loaded") or {}).get("status")) if isinstance(context.get("deployment_loaded"), Mapping) else None,
        "current_transaction_status": (context.get("current_state") or {}).get("transaction_state") if isinstance(context.get("current_state"), Mapping) else None,
        "current_verification_status": (context.get("current_state") or {}).get("verification_status") if isinstance(context.get("current_state"), Mapping) else None,
        "runtime_capability_available": bool((context.get("runtime_capability") or {}).get("single_rule_evaluator_available")) if isinstance(context.get("runtime_capability"), Mapping) else False,
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": eligibility.get("recommended_action"),
    }


def validate_deployed_rule_execution_eligibility(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    *,
    execution_input: Mapping[str, Any] | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _execution_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        execution_input=execution_input,
        root=root,
    )
    blockers = list(context["blockers"])
    warnings = list(context["warnings"])
    deployment_result = context["deployment_result"]
    runtime_capability = context["runtime_capability"]
    status = _eligibility_status(blockers, warnings)
    return {
        "status": status,
        "canonical_rule_id": deployment_result.get("canonical_rule_id"),
        "canonical_rule_fingerprint": deployment_result.get("canonical_rule_fingerprint"),
        "deployed_rule_id": deployment_result.get("deployed_rule_id"),
        "deployed_rule_fingerprint": (context["deployed_rule"] or {}).get("rule_fingerprint") if isinstance(context["deployed_rule"], Mapping) else None,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": deployment_result.get("production_target_id"),
        "production_transaction_id": deployment_result.get("production_transaction_id"),
        "document_id": deployment_result.get("document_id"),
        "source_revision": deployment_result.get("source_revision"),
        "certification_id": _resolved_certification_id(deployment_result),
        "certification_fingerprint": deployment_result.get("certification_fingerprint"),
        "production_authorization_result_id": deployment_result.get("production_authorization_result_id"),
        "deployment_package_fingerprint": deployment_result.get("deployment_package_fingerprint"),
        "committed_production_state_fingerprint": deployment_result.get("committed_production_state_fingerprint"),
        "runtime_capability_available": bool(runtime_capability.get("single_rule_evaluator_available")) if isinstance(runtime_capability, Mapping) else False,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def execute_deployed_rule(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    *,
    execution_input: Mapping[str, Any],
    record_operational_telemetry: bool = False,
    _testing_observed_at: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    eligibility = validate_deployed_rule_execution_eligibility(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        execution_input=execution_input,
        root=root,
    )
    if str(eligibility.get("status") or "") not in {"eligible", "eligible_with_warnings"}:
        return {
            "execution_status": "unsupported" if str(eligibility.get("status") or "") == "unsupported" else "blocked",
            "runtime_outcome_status": None,
            **{key: eligibility.get(key) for key in (
                "canonical_rule_id",
                "canonical_rule_fingerprint",
                "deployed_rule_id",
                "deployed_rule_fingerprint",
                "production_deployment_result_id",
                "production_target_id",
                "production_transaction_id",
                "document_id",
                "source_revision",
                "certification_id",
                "certification_fingerprint",
                "production_authorization_result_id",
                "deployment_package_fingerprint",
                "committed_production_state_fingerprint",
            )},
            "input_fingerprint": _hash_payload(deepcopy(dict(execution_input or {}))),
            "output_fingerprint": None,
            "duration_ms": None,
            "blockers": list(eligibility.get("blockers", [])),
            "warnings": list(eligibility.get("warnings", [])),
            "telemetry_recording_status": "not_recorded",
        }
    context = _execution_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        execution_input=execution_input,
        root=root,
    )
    deployed_rule = deepcopy(dict(context["deployed_rule"]))
    input_payload = deepcopy(dict(execution_input))
    started = perf_counter()
    deployment_result = context["deployment_result"]
    try:
        result = evaluate_canonical_rule(deployed_rule, input_payload, root=root)
    except Exception as exc:
        duration_ms = max(0, int((perf_counter() - started) * 1000))
        if record_operational_telemetry:
            telemetry_backend.record_deployed_rule_execution_event(
                {
                    "execution_status": "failed",
                    "runtime_outcome_status": "exception",
                    "canonical_rule_id": deployment_result.get("canonical_rule_id"),
                    "canonical_rule_fingerprint": deployment_result.get("canonical_rule_fingerprint"),
                    "deployed_rule_id": deployment_result.get("deployed_rule_id"),
                    "deployed_rule_fingerprint": deployed_rule.get("rule_fingerprint"),
                    "production_deployment_result_id": production_deployment_result_id,
                    "production_deployment_result_fingerprint": deployment_result.get("result_fingerprint"),
                    "production_target_id": deployment_result.get("production_target_id"),
                    "production_transaction_id": deployment_result.get("production_transaction_id"),
                    "document_id": deployment_result.get("document_id"),
                    "source_revision": deployment_result.get("source_revision"),
                    "certification_id": _resolved_certification_id(deployment_result),
                    "certification_fingerprint": deployment_result.get("certification_fingerprint"),
                    "production_authorization_result_id": deployment_result.get("production_authorization_result_id"),
                    "deployment_package_fingerprint": deployment_result.get("deployment_package_fingerprint"),
                    "committed_production_state_fingerprint": deployment_result.get("committed_production_state_fingerprint"),
                    "current_production_state_fingerprint": deployment_result.get("committed_production_state_fingerprint"),
                    "current_transaction_status": context["current_state"].get("transaction_state"),
                    "current_verification_status": context["current_state"].get("verification_status"),
                    "input_fingerprint": _hash_payload(input_payload),
                    "output_fingerprint": None,
                    "duration_ms": duration_ms,
                    "error_class": exc.__class__.__name__,
                },
                root=root,
                _testing_observed_at=_testing_observed_at,
            )
        raise
    duration_ms = max(0, int((perf_counter() - started) * 1000))
    runtime_outcome_status = str((result or {}).get("result") or "")
    execution_status = _execution_status_from_result(runtime_outcome_status)
    output_fingerprint = _hash_payload(result) if isinstance(result, Mapping) else None
    envelope = {
        "execution_status": execution_status,
        "runtime_outcome_status": runtime_outcome_status,
        "canonical_rule_id": deployment_result.get("canonical_rule_id"),
        "canonical_rule_fingerprint": deployment_result.get("canonical_rule_fingerprint"),
        "deployed_rule_id": deployment_result.get("deployed_rule_id"),
        "deployed_rule_fingerprint": deployed_rule.get("rule_fingerprint"),
        "production_deployment_result_id": production_deployment_result_id,
        "production_deployment_result_fingerprint": deployment_result.get("result_fingerprint"),
        "production_target_id": deployment_result.get("production_target_id"),
        "production_transaction_id": deployment_result.get("production_transaction_id"),
        "document_id": deployment_result.get("document_id"),
        "source_revision": deployment_result.get("source_revision"),
        "certification_id": _resolved_certification_id(deployment_result),
        "certification_fingerprint": deployment_result.get("certification_fingerprint"),
        "production_authorization_result_id": deployment_result.get("production_authorization_result_id"),
        "deployment_package_fingerprint": deployment_result.get("deployment_package_fingerprint"),
        "committed_production_state_fingerprint": deployment_result.get("committed_production_state_fingerprint"),
        "current_production_state_fingerprint": deployment_result.get("committed_production_state_fingerprint"),
        "current_transaction_status": context["current_state"].get("transaction_state"),
        "current_verification_status": context["current_state"].get("verification_status"),
        "input_fingerprint": _hash_payload(input_payload),
        "output_fingerprint": output_fingerprint,
        "duration_ms": duration_ms,
        "evaluation": result,
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(result.get("blockers", [])) if isinstance(result, Mapping) else [],
        "telemetry_recording_status": "not_recorded",
    }
    if record_operational_telemetry:
        telemetry_result = telemetry_backend.record_deployed_rule_execution_event(
            envelope,
            root=root,
            _testing_observed_at=_testing_observed_at,
        )
        envelope["telemetry_recording_status"] = str(telemetry_result.get("status") or "unknown")
        if str(telemetry_result.get("status") or "") in {"blocked", "corrupt", "conflict"}:
            envelope["warnings"] = list(envelope.get("warnings", [])) + [f"telemetry:{str((telemetry_result.get('blockers') or ['record_failed'])[0])}"]
        else:
            envelope["telemetry_event_id"] = telemetry_result.get("event_id")
    return envelope


def format_deployed_rule_execution_report(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    *,
    execution_input: Mapping[str, Any] | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    workspace = build_deployed_rule_execution_workspace(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        execution_input=execution_input,
        root=root,
    )
    lines = [
        "Deployed Rule Execution Runtime",
        f"Canonical Rule ID: {workspace.get('canonical_rule_id', 'unknown')}",
        f"Deployed Rule ID: {workspace.get('deployed_rule_id', 'unknown')}",
        f"Production Deployment Result ID: {production_deployment_result_id}",
        f"Production Transaction ID: {workspace.get('production_transaction_id', 'unknown')}",
        f"Production Target ID: {workspace.get('production_target_id', 'unknown')}",
        f"Workspace Status: {workspace.get('status', 'unknown')}",
        f"Current Verification Status: {workspace.get('current_verification_status', 'unknown')}",
        "Telemetry Recording: execution_telemetry_producer_available",
        "Effectiveness evaluation: not performed",
    ]
    if workspace.get("warnings"):
        lines.append("Warnings: " + ", ".join(str(item) for item in workspace.get("warnings", [])))
    if workspace.get("blockers"):
        lines.append("Blockers: " + ", ".join(str(item) for item in workspace.get("blockers", [])))
    return "\n".join(lines)


def _execution_context(
    *,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    execution_input: Mapping[str, Any] | None,
    root: Path | str,
) -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []
    runtime_capability = get_canonical_rule_runtime_capability(root=root)
    if not bool(runtime_capability.get("single_rule_evaluator_available")):
        blockers.append("canonical_rule_evaluator_unavailable")
    if _text(canonical_rule_id) is None:
        blockers.append("canonical_rule_id_required")
    if _text(production_deployment_result_id) is None:
        blockers.append("production_deployment_result_id_required")
    if _text(production_target_id) is None:
        blockers.append("production_target_id_required")
    if _text(deployed_rule_id) is None:
        blockers.append("deployed_rule_id_required")
    if execution_input is None:
        blockers.append("execution_input_required")
    elif not isinstance(execution_input, Mapping):
        blockers.append("execution_input_invalid")

    deployment_loaded = deployment_backend.load_certified_rule_production_deployment_result(production_deployment_result_id, root=root)
    deployment_result = deployment_loaded.get("production_deployment_result") if isinstance(deployment_loaded.get("production_deployment_result"), Mapping) else {}
    deployment_receipt = deployment_backend._find_receipt_for_result(Path(root), production_deployment_result_id) if deployment_result else None
    current_state = adapter_backend.read_production_deployment_state(production_target_id, transaction_id=str(deployment_result.get("production_transaction_id") or ""), root=root) if deployment_result else {"status": "missing"}
    source_loaded = load_canonical_rule(canonical_rule_id, require_active=True, root=root) if _text(canonical_rule_id) else {"status": "not_found"}
    source_rule = source_loaded.get("rule") if isinstance(source_loaded.get("rule"), Mapping) else {}
    deployed_loaded = load_canonical_rule(deployed_rule_id, require_active=True, root=root) if _text(deployed_rule_id) else {"status": "not_found"}
    deployed_rule = deployed_loaded.get("rule") if isinstance(deployed_loaded.get("rule"), Mapping) else {}

    if not deployment_result:
        blockers.append("phase_9v_result_missing")
    else:
        if str(deployment_result.get("final_status") or "") != "completed":
            blockers.append("phase_9v_result_not_completed")
        if deployment_backend._result_is_stale(Path(root), deployment_result):
            blockers.append("phase_9v_result_stale")
        if str(deployment_result.get("canonical_rule_id") or "") != canonical_rule_id:
            blockers.append("canonical_rule_id_mismatch")
        if str(deployment_result.get("production_target_id") or "") != production_target_id:
            blockers.append("production_target_id_mismatch")
        if str(deployment_result.get("deployed_rule_id") or "") != deployed_rule_id:
            blockers.append("deployed_rule_id_mismatch")
    if not isinstance(deployment_receipt, Mapping):
        blockers.append("phase_9v_receipt_missing")
    elif str(deployment_receipt.get("result_fingerprint") or "") != str(deployment_result.get("result_fingerprint") or ""):
        blockers.append("phase_9v_receipt_fingerprint_mismatch")
    if str(current_state.get("status") or "") != "loaded":
        blockers.append("current_production_transaction_missing")
    else:
        if str(current_state.get("transaction_state") or "") != "committed":
            blockers.append("current_production_transaction_not_committed")
        if str(current_state.get("verification_status") or "") != "verified_committed":
            blockers.append("current_production_transaction_not_verified_committed")
        if str(current_state.get("deployed_rule_id") or "") != deployed_rule_id:
            blockers.append("current_state_deployed_rule_id_mismatch")
        if str(current_state.get("canonical_rule_id") or "") != canonical_rule_id:
            blockers.append("current_state_canonical_rule_id_mismatch")
    if deployed_loaded.get("status") != "loaded":
        blockers.extend(list(deployed_loaded.get("blockers", []) or ["deployed_rule_missing_or_inactive"]))
    else:
        if str(deployed_rule.get("production_activation_transaction_id") or "") != str(deployment_result.get("production_transaction_id") or ""):
            blockers.append("production_transaction_id_mismatch")
        if str(deployed_rule.get("source_canonical_rule_id") or "") != canonical_rule_id:
            blockers.append("deployed_rule_source_canonical_rule_mismatch")
        if str(deployed_rule.get("production_target_id") or "") != production_target_id:
            blockers.append("deployed_rule_target_mismatch")
        if str(deployed_rule.get("production_authorization_result_id") or "") != str(deployment_result.get("production_authorization_result_id") or ""):
            blockers.append("production_authorization_result_id_mismatch")
    if source_loaded.get("status") != "loaded":
        blockers.extend(list(source_loaded.get("blockers", []) or ["canonical_source_rule_missing_or_inactive"]))
    else:
        if str(source_rule.get("rule_fingerprint") or "") != str(deployment_result.get("canonical_rule_fingerprint") or ""):
            blockers.append("canonical_rule_fingerprint_mismatch")

    return {
        "runtime_capability": runtime_capability,
        "deployment_loaded": deployment_loaded,
        "deployment_result": deployment_result,
        "deployment_receipt": deployment_receipt,
        "current_state": current_state,
        "source_loaded": source_loaded,
        "source_rule": source_rule,
        "deployed_loaded": deployed_loaded,
        "deployed_rule": deployed_rule,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def _eligibility_status(blockers: list[str], warnings: list[str]) -> str:
    if blockers:
        if any(item.endswith("_missing") or item.endswith("_required") for item in blockers):
            return "not_found"
        if any("stale" in item for item in blockers):
            return "stale"
        if any("fingerprint_mismatch" in item or "mismatch" in item for item in blockers):
            return "corrupt"
        if any("unavailable" in item or "unsupported" in item for item in blockers):
            return "unsupported"
        return "blocked"
    return "eligible_with_warnings" if warnings else "eligible"


def _execution_status_from_result(runtime_outcome_status: str) -> str:
    if runtime_outcome_status in {"matched", "not_matched"}:
        return "completed"
    if runtime_outcome_status == "unsupported":
        return "unsupported"
    if runtime_outcome_status == "blocked":
        return "blocked"
    if runtime_outcome_status == "skipped":
        return "skipped"
    return "failed"


def _recommended_action(status: str) -> str:
    if status in {"eligible", "eligible_with_warnings"}:
        return "Execute the deployed rule through the read-only runtime entrypoint."
    if status == "stale":
        return "Refresh or rebuild deployment evidence before executing the deployed rule."
    if status == "unsupported":
        return "Restore canonical evaluator availability before deployed-rule execution."
    if status == "corrupt":
        return "Resolve deployment/deployed-rule binding mismatches before executing."
    if status == "not_found":
        return "Provide exact Phase 9V deployment and deployed-rule identifiers."
    return "Resolve execution blockers before attempting deployed-rule runtime evaluation."


def _resolved_certification_id(deployment_result: Mapping[str, Any]) -> str:
    explicit = _text(deployment_result.get("certification_id"))
    if explicit:
        return explicit
    fingerprint = _text(deployment_result.get("certification_fingerprint"))
    if fingerprint:
        return "certification_from_" + _hash_payload({"certification_fingerprint": fingerprint})[7:23]
    return ""


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if _text(item)))
