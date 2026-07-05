from __future__ import annotations

from typing import Mapping


def render_report_template(snapshot: Mapping[str, object], mode: str = "normal") -> str:
    tactical = snapshot.get("tacticalAnalysis") if isinstance(snapshot.get("tacticalAnalysis"), Mapping) else {}
    advanced = snapshot.get("advancedAnalysis") if isinstance(snapshot.get("advancedAnalysis"), Mapping) else {}
    audit = snapshot.get("auditSnapshot") if isinstance(snapshot.get("auditSnapshot"), Mapping) else snapshot.get("audit_snapshot", {})
    fast = tactical.get("fast_lane", {}) if isinstance(tactical, Mapping) and isinstance(tactical.get("fast_lane"), Mapping) else {}
    mode = mode.lower()
    if mode == "fast_lane":
        return "\n".join([
            "Fast Lane",
            f"Command: {fast.get('command', 'unknown')}",
            f"Window: {fast.get('window', 'unknown')}",
            f"Best minute: {fast.get('best', fast.get('best_minute', 'unknown'))}",
            f"Cutoff: {fast.get('cutoff', 'unknown')}",
            f"Main reason: {fast.get('main_reason', '')}",
            f"Main risk: {fast.get('main_risk', '')}",
            f"Action moment: {fast.get('action', fast.get('action_moment', ''))}",
            f"Confidence: {fast.get('confidence', 'unknown')}",
        ])
    if mode == "expert":
        return f"Expert Report\nPhase 1: {bool(advanced)}\nPhase 2: {bool(tactical)}\nControl: {advanced.get('control_index', {}) if isinstance(advanced, Mapping) else {}}"
    if mode == "audit":
        return f"Audit Report\nReliability: {bool(audit)}\nSchema: {snapshot.get('engine_schema_version', 'unknown')}"
    if mode == "calendar":
        calendar = tactical.get("strategic_calendar_context", {}) if isinstance(tactical, Mapping) else {}
        return f"Calendar Report\nWindows: {len(calendar.get('entries', [])) if isinstance(calendar, Mapping) else 0}"
    if mode == "developer_debug":
        return f"Developer Debug\nKeys: {', '.join(sorted(str(key) for key in snapshot.keys()))}"
    return f"Normal Report\nCommand: {fast.get('command', 'unknown')}\nTactical summary available: {bool(tactical)}"
