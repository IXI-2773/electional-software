"""Retrograde and midpoint page helpers for the desktop UI."""

from __future__ import annotations

from typing import Mapping

from .engine.chart import format_position
from .reports.text_report import format_motion_summary


PLANET_LABELS = {
    "Sun": "Su",
    "Moon": "Mo",
    "Mercury": "Me",
    "Venus": "Ve",
    "Mars": "Ma",
    "Jupiter": "Ju",
    "Saturn": "Sa",
    "Uranus": "Ur",
    "Neptune": "Ne",
    "Pluto": "Pl",
}

PLANET_GLYPHS = {
    "Sun": "\u2609",
    "Moon": "\u263d",
    "Mercury": "\u263f",
    "Venus": "\u2640",
    "Mars": "\u2642",
    "Jupiter": "\u2643",
    "Saturn": "\u2644",
    "Uranus": "\u26e2",
    "Neptune": "\u2646",
    "Pluto": "\u2647",
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def planet_glyph(name: str) -> str:
    return PLANET_GLYPHS.get(name, PLANET_LABELS.get(name, name[:2] or "?"))


def circular_distance_degrees(first: float, second: float) -> float:
    return abs((first - second + 180) % 360 - 180)


def midpoint_degrees(first: float, second: float) -> float:
    delta = ((second - first + 180) % 360) - 180
    return (first + delta / 2) % 360


def _point_longitude(point: Mapping[str, object]) -> float | None:
    if "longitude" not in point:
        return None
    try:
        return float(point["longitude"]) % 360.0
    except (TypeError, ValueError):
        return None


def _motion_speed(point: Mapping[str, object]) -> tuple[float | None, str, Mapping[str, object]]:
    motion = point.get("motion", {})
    if not isinstance(motion, Mapping):
        return None, "Motion unknown", {}
    speed = None
    if "dailyLongitudeChange" in motion:
        speed = _safe_float(motion.get("dailyLongitudeChange"), 0.0)
    label = str(motion.get("label") or "Motion unknown")
    station = motion.get("station", {})
    return speed, label, station if isinstance(station, Mapping) else {}


def retrograde_motion_rows(snapshot: Mapping[str, object]) -> list[dict[str, object]]:
    """Return current motion rows for the chart's planet positions."""

    positions = snapshot.get("positions", [])
    if not isinstance(positions, list):
        return []

    rows: list[dict[str, object]] = []
    for point in positions:
        if not isinstance(point, Mapping):
            continue
        name = str(point.get("name") or "Point")
        speed, motion_label, station = _motion_speed(point)
        speed_available = speed is not None
        retrograde = bool(point.get("isRetrograde")) or (speed_available and speed < -0.0001) or "retro" in motion_label.lower()
        stationary = bool(point.get("isStationary")) or bool(station.get("isInStationWindow"))
        if not stationary and speed_available and name not in {"Sun", "Moon"}:
            stationary = abs(float(speed)) <= 0.03
        if stationary and retrograde:
            status = "Station Rx"
            tone = "warning"
        elif stationary:
            status = "Station Direct"
            tone = "warning"
        elif retrograde:
            status = "Retrograde"
            tone = "stress"
        else:
            status = "Direct"
            tone = "support"
        house = point.get("house", "-")
        try:
            position_text = format_position(dict(point))
        except (KeyError, TypeError, ValueError):
            longitude = _point_longitude(point)
            position_text = f"{longitude:.2f} deg" if longitude is not None else "position n/a"
        rows.append(
            {
                "name": name,
                "glyph": planet_glyph(name),
                "position": position_text,
                "house": house,
                "status": status,
                "tone": tone,
                "speed": speed,
                "speedText": f"{float(speed):+.3f} deg/day" if speed_available else "speed n/a",
                "motion": format_motion_summary(dict(point)) if isinstance(point, Mapping) else motion_label,
                "stationPhase": str(station.get("phase") or "").strip(),
            }
        )
    return rows


def retrograde_page_lines(snapshot: Mapping[str, object]) -> list[str]:
    rows = retrograde_motion_rows(snapshot)
    retrograde_count = sum(1 for row in rows if str(row.get("status", "")).startswith("Retrograde") or "Rx" in str(row.get("status", "")))
    station_count = sum(1 for row in rows if "Station" in str(row.get("status", "")))
    lines = [
        "Retrogrades",
        "",
        f"Chart time: {snapshot.get('formattedTime', 'time unavailable')}",
        f"Retrograde/station count: {retrograde_count} retrograde, {station_count} station-sensitive.",
        "",
        "Electional read",
        "- Retrogrades favor review, repair, return, revision, and recovery more than clean first launches.",
        "- Stationary planets are loud: useful when you want that planet emphasized, risky when it rules the wrong matter.",
        "- Direct planets with healthy speed usually behave more cleanly for fresh starts.",
        "",
        "Point       Pos              H   Motion          Speed",
    ]
    if not rows:
        lines.append("No planet motion rows are available yet.")
        return lines
    for row in rows:
        lines.append(
            f"{row['glyph']} {row['name']:<9} {row['position']:<16} H{row['house']:<2} "
            f"{row['status']:<14} {row['speedText']}"
        )
    cautions = [row for row in rows if row.get("tone") in {"stress", "warning"}]
    lines.extend(["", "Current cautions"])
    if cautions:
        for row in cautions[:8]:
            note = row.get("stationPhase") or row.get("motion") or row.get("status")
            lines.append(f"- {row['name']}: {row['status']} ({note}).")
    else:
        lines.append("- No retrograde or station-sensitive planets in the current planet set.")
    return lines


def format_absolute_longitude(longitude: object) -> str:
    value = _safe_float(longitude, 0.0) % 360.0
    return f"{value:06.2f} deg"


def _midpoint_source_points(snapshot: Mapping[str, object]) -> list[dict[str, object]]:
    positions = snapshot.get("positions", [])
    if not isinstance(positions, list):
        return []
    rows: list[dict[str, object]] = []
    for point in positions:
        if not isinstance(point, Mapping):
            continue
        name = str(point.get("name") or "")
        if name not in PLANET_LABELS:
            continue
        longitude = _point_longitude(point)
        if longitude is None:
            continue
        rows.append({"name": name, "glyph": planet_glyph(name), "longitude": longitude})
    return rows


def midpoint_pair_rows(snapshot: Mapping[str, object], *, limit: int = 45) -> list[dict[str, object]]:
    points = _midpoint_source_points(snapshot)
    rows: list[dict[str, object]] = []
    for first_index, first in enumerate(points):
        for second in points[first_index + 1 :]:
            midpoint = midpoint_degrees(float(first["longitude"]), float(second["longitude"]))
            rows.append(
                {
                    "pair": f"{first['name']}/{second['name']}",
                    "glyphPair": f"{first['glyph']}/{second['glyph']}",
                    "midpoint": midpoint,
                    "opposition": (midpoint + 180.0) % 360.0,
                }
            )
    return rows[:limit]


def midpoint_contact_rows(snapshot: Mapping[str, object], *, orb: float = 1.5, limit: int = 24) -> list[dict[str, object]]:
    points = _midpoint_source_points(snapshot)
    rows: list[dict[str, object]] = []
    for first_index, first in enumerate(points):
        for second in points[first_index + 1 :]:
            midpoint = midpoint_degrees(float(first["longitude"]), float(second["longitude"]))
            opposite = (midpoint + 180.0) % 360.0
            pair_names = {str(first["name"]), str(second["name"])}
            for body in points:
                if str(body["name"]) in pair_names:
                    continue
                body_longitude = float(body["longitude"])
                direct_orb = circular_distance_degrees(body_longitude, midpoint)
                opposite_orb = circular_distance_degrees(body_longitude, opposite)
                active_orb = min(direct_orb, opposite_orb)
                if active_orb <= orb:
                    rows.append(
                        {
                            "body": body["name"],
                            "bodyGlyph": body["glyph"],
                            "pair": f"{first['name']}/{second['name']}",
                            "glyphPair": f"{first['glyph']}/{second['glyph']}",
                            "midpoint": midpoint,
                            "axisPoint": midpoint if direct_orb <= opposite_orb else opposite,
                            "axisSide": "midpoint" if direct_orb <= opposite_orb else "opposite midpoint",
                            "orb": active_orb,
                            "bodyLongitude": body_longitude,
                        }
                    )
    rows.sort(key=lambda row: (float(row["orb"]), str(row["body"]), str(row["pair"])))
    return rows[:limit]


def midpoint_page_lines(snapshot: Mapping[str, object]) -> list[str]:
    contacts = midpoint_contact_rows(snapshot)
    pairs = midpoint_pair_rows(snapshot)
    lines = [
        "Midpoints",
        "",
        f"Chart time: {snapshot.get('formattedTime', 'time unavailable')}",
        "Scope: primary planet midpoint axes. Positions are absolute ecliptic longitude so true 13-sign charts do not get fake equal-sign labels.",
        "",
        "How to read",
        "- Body = A/B means the body is conjunct or opposite the midpoint axis of A and B.",
        "- Tight midpoint contacts can describe the hidden blend behind an election.",
        "- Use these as testimony, not as a replacement for aspects, Moon condition, and house/angle fit.",
        "",
        "Closest midpoint contacts",
    ]
    if contacts:
        for row in contacts:
            lines.append(
                f"- {row['bodyGlyph']} {row['body']} = {row['glyphPair']} {row['pair']} "
                f"({row['axisSide']}; orb {float(row['orb']):.2f} deg, axis {format_absolute_longitude(row['axisPoint'])})."
            )
    else:
        lines.append("- No primary planet midpoint contacts within 1.50 degrees.")
    lines.extend(["", "Planet pair midpoint list"])
    if not pairs:
        lines.append("No midpoint pairs are available yet.")
        return lines
    for row in pairs[:30]:
        lines.append(
            f"- {row['glyphPair']} {row['pair']:<15} midpoint {format_absolute_longitude(row['midpoint'])}; "
            f"opposite {format_absolute_longitude(row['opposition'])}"
        )
    if len(pairs) > 30:
        lines.append(f"- {len(pairs) - 30} additional pairs hidden for readability.")
    return lines
