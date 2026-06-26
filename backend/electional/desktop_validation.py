"""Manual validation helpers for the desktop UI."""

from __future__ import annotations

import re
from typing import Mapping

from .constellations import ECLIPTIC_CONSTELLATION_SPANS


CONSTELLATION_SIGN_LABELS = {
    "aries": "Ar",
    "taurus": "Ta",
    "gemini": "Ge",
    "cancer": "Ca",
    "leo": "Le",
    "virgo": "Vi",
    "libra": "Li",
    "scorpius": "Sc",
    "sagittarius": "Sg",
    "capricornus": "Cp",
    "aquarius": "Aq",
    "pisces": "Pi",
}

STANDARD_SIGN_STARTS = {
    "aries": 0.0,
    "ari": 0.0,
    "ar": 0.0,
    "taurus": 30.0,
    "tau": 30.0,
    "ta": 30.0,
    "gemini": 60.0,
    "gem": 60.0,
    "ge": 60.0,
    "cancer": 90.0,
    "can": 90.0,
    "cnc": 90.0,
    "ca": 90.0,
    "leo": 120.0,
    "le": 120.0,
    "virgo": 150.0,
    "vir": 150.0,
    "vi": 150.0,
    "libra": 180.0,
    "lib": 180.0,
    "li": 180.0,
    "scorpio": 210.0,
    "scorpius": 210.0,
    "sco": 210.0,
    "sc": 210.0,
    "sagittarius": 240.0,
    "sag": 240.0,
    "sgr": 240.0,
    "sg": 240.0,
    "capricorn": 270.0,
    "capricornus": 270.0,
    "cap": 270.0,
    "cp": 270.0,
    "aquarius": 300.0,
    "aqu": 300.0,
    "aqr": 300.0,
    "aq": 300.0,
    "pisces": 330.0,
    "pis": 330.0,
    "psc": 330.0,
    "pi": 330.0,
}

MANUAL_VALIDATION_TARGETS = (
    ("part of fortune", "Part of Fortune", "part of fortune"),
    ("part of spirit", "Part of Spirit", "part of spirit"),
    ("true north node", "True North Node", "true north node"),
    ("mean north node", "Mean North Node", "mean north node"),
    ("north node", "North Node", "north node"),
    ("sun", "Sun", "sun"),
    ("moon", "Moon", "moon"),
    ("mercury", "Mercury", "mercury"),
    ("venus", "Venus", "venus"),
    ("mars", "Mars", "mars"),
    ("jupiter", "Jupiter", "jupiter"),
    ("saturn", "Saturn", "saturn"),
    ("uranus", "Uranus", "uranus"),
    ("neptune", "Neptune", "neptune"),
    ("pluto", "Pluto", "pluto"),
    ("ascendant", "ASC", "asc"),
    ("asc", "ASC", "asc"),
    ("as", "ASC", "asc"),
    ("descendant", "DSC", "dsc"),
    ("dsc", "DSC", "dsc"),
    ("ds", "DSC", "dsc"),
    ("midheaven", "MC", "mc"),
    ("mc", "MC", "mc"),
    ("imum coeli", "IC", "ic"),
    ("ic", "IC", "ic"),
)


def _compact_place_name(name: object) -> str:
    text = str(name or "").strip()
    replacements = {
        ", California": ", CA",
        ", United States": ", USA",
        "United States": "USA",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text or "Location unavailable"


def manual_validation_sign_starts(zodiac_system_id: str = "") -> dict[str, float]:
    if str(zodiac_system_id).lower() != "true-13-sign":
        return dict(STANDARD_SIGN_STARTS)
    starts: dict[str, float] = {}
    for span in ECLIPTIC_CONSTELLATION_SPANS:
        start = float(span["start"])
        for key in (span["id"], span["name"], span["abbreviation"]):
            starts[str(key).lower()] = start
        short = CONSTELLATION_SIGN_LABELS.get(str(span["id"]))
        if short:
            starts[str(short).lower()] = start
        if str(span["id"]) == "scorpius":
            starts["scorpio"] = start
            starts["sc"] = start
        if str(span["id"]) == "capricornus":
            starts["capricorn"] = start
            starts["cp"] = start
        if str(span["id"]) == "sagittarius":
            starts["sag"] = start
            starts["sg"] = start
    return starts


def _manual_validation_target_from_line(line: str) -> tuple[str, str] | None:
    house_match = re.search(r"\b(?:house|h)\s*0?([1-9]|1[0-2])\b", line, re.IGNORECASE)
    if house_match:
        house_no = int(house_match.group(1))
        return (f"House {house_no}", f"h{house_no}")
    lowered = line.lower()
    for alias, label, key in MANUAL_VALIDATION_TARGETS:
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return (label, key)
    return None


def parse_manual_validation_values(text: str, *, zodiac_system_id: str = "") -> list[dict[str, object]]:
    starts = manual_validation_sign_starts(zodiac_system_id)
    sign_pattern = "|".join(sorted((re.escape(key) for key in starts), key=len, reverse=True))
    value_pattern = re.compile(
        rf"\b(?P<sign>{sign_pattern})\b\s*"
        rf"(?P<degree>\d{{1,2}})(?:\s*(?:deg|d|\u00b0|:|'|\s)\s*(?P<minute>\d{{1,2}}))?",
        re.IGNORECASE,
    )
    rows: list[dict[str, object]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        target = _manual_validation_target_from_line(line)
        value_match = value_pattern.search(line)
        if not target or not value_match:
            rows.append({"line": line, "status": "unparsed"})
            continue
        sign_key = value_match.group("sign").lower()
        degree = int(value_match.group("degree"))
        minute = int(value_match.group("minute") or 0)
        longitude = (starts[sign_key] + degree + minute / 60.0) % 360
        label, target_key = target
        rows.append(
            {
                "line": line,
                "label": label,
                "targetKey": target_key,
                "referenceLongitude": longitude,
                "referenceText": f"{value_match.group('sign')} {degree:02d}deg{minute:02d}",
                "status": "parsed",
            }
        )
    return rows


def _manual_target_key(label: object) -> str:
    text = str(label or "").lower()
    house_match = re.search(r"\b(?:house|h)\s*0?([1-9]|1[0-2])\b", text)
    if house_match:
        return f"h{int(house_match.group(1))}"
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _snapshot_validation_targets(snapshot: Mapping[str, object]) -> dict[str, dict[str, object]]:
    targets: dict[str, dict[str, object]] = {}
    for collection_name in ("positions", "lots", "lunarNodes"):
        collection = snapshot.get(collection_name, [])
        if not isinstance(collection, list):
            continue
        for item in collection:
            if isinstance(item, Mapping) and item.get("longitude") is not None:
                label = str(item.get("name") or item.get("shortName") or "")
                targets[_manual_target_key(label)] = {"label": label, "longitude": float(item["longitude"])}
    angles = snapshot.get("angles", [])
    if isinstance(angles, list):
        for angle in angles:
            if isinstance(angle, Mapping) and angle.get("longitude") is not None:
                angle_id = str(angle.get("id") or angle.get("shortName") or "").lower()
                label = str(angle.get("shortName") or angle_id.upper())
                targets[angle_id] = {"label": label, "longitude": float(angle["longitude"])}
    cusps = snapshot.get("houseCusps", [])
    if isinstance(cusps, list):
        for cusp in cusps:
            if isinstance(cusp, Mapping) and cusp.get("longitude") is not None and cusp.get("house") is not None:
                house_no = int(cusp["house"])
                targets[f"h{house_no}"] = {"label": f"House {house_no}", "longitude": float(cusp["longitude"])}
    return targets


def _manual_validation_cause(target_key: str, delta: float | None) -> str:
    if delta is None:
        return "No app target found."
    if delta <= 0.05:
        return "Match."
    if target_key.startswith("h") or target_key in {"asc", "dsc", "mc", "ic"}:
        return "Check location, timezone, and house system."
    return "Check zodiac, ayanamsha, time, and source settings."


def build_manual_validation_comparison(snapshot: Mapping[str, object], text: str, *, source: str = "CapricornPROMETHEUS") -> dict[str, object]:
    zodiac_system = snapshot.get("zodiacSystem")
    zodiac_id = str(getattr(zodiac_system, "id", "") or "").lower()
    parsed = parse_manual_validation_values(text, zodiac_system_id=zodiac_id)
    targets = _snapshot_validation_targets(snapshot)
    rows: list[dict[str, object]] = []
    deltas: list[float] = []
    for row in parsed:
        if row.get("status") != "parsed":
            rows.append({**row, "result": "unparsed", "cause": "Line did not contain a recognized target plus sign-degree value."})
            continue
        target_key = str(row["targetKey"])
        target = targets.get(target_key)
        delta = None
        app_longitude = None
        result = "missing target"
        if target:
            app_longitude = float(target["longitude"])
            delta = abs((app_longitude - float(row["referenceLongitude"]) + 180) % 360 - 180)
            deltas.append(delta)
            result = "match" if delta <= 0.05 else "review"
        rows.append(
            {
                **row,
                "appLongitude": app_longitude,
                "deltaDegrees": delta,
                "result": result,
                "cause": _manual_validation_cause(target_key, delta),
            }
        )
    max_delta = max(deltas) if deltas else None
    status = "No parsed values" if not deltas else "Pass" if max_delta <= 0.05 else "Review"
    return {
        "source": source.strip() or "CapricornPROMETHEUS",
        "inputText": text,
        "rows": rows,
        "parsedCount": len(deltas),
        "parsedInputCount": sum(1 for row in rows if row.get("status") == "parsed"),
        "missingCount": sum(1 for row in rows if row.get("result") == "missing target"),
        "reviewCount": sum(1 for row in rows if row.get("result") == "review"),
        "unparsedCount": sum(1 for row in rows if row.get("result") == "unparsed"),
        "maxDeltaDegrees": max_delta,
        "status": status,
    }


def manual_validation_result_summary(result: Mapping[str, object] | None) -> dict[str, object]:
    if not isinstance(result, Mapping) or not result:
        return {
            "status": "Not run",
            "headline": "Manual comparison not run.",
            "parsedInputCount": 0,
            "matchedCount": 0,
            "reviewCount": 0,
            "missingCount": 0,
            "unparsedCount": 0,
            "maxDeltaText": "n/a",
            "topCauses": [],
        }
    rows = result.get("rows", [])
    parsed_rows = [row for row in rows if isinstance(row, Mapping) and row.get("status") == "parsed"] if isinstance(rows, list) else []
    matched_count = sum(1 for row in parsed_rows if row.get("result") == "match")
    review_count = sum(1 for row in parsed_rows if row.get("result") == "review")
    missing_count = sum(1 for row in parsed_rows if row.get("result") == "missing target")
    unparsed_count = sum(1 for row in rows if isinstance(row, Mapping) and row.get("result") == "unparsed") if isinstance(rows, list) else 0
    max_delta = result.get("maxDeltaDegrees")
    max_delta_text = "n/a" if max_delta is None else f"{float(max_delta):.4f} deg"
    cause_counts: dict[str, int] = {}
    for row in parsed_rows:
        cause = str(row.get("cause") or "").strip()
        if not cause or cause == "Match.":
            continue
        cause_counts[cause] = cause_counts.get(cause, 0) + 1
    top_causes = [cause for cause, _count in sorted(cause_counts.items(), key=lambda item: (-item[1], item[0]))[:3]]
    status = str(result.get("status") or "n/a")
    if status == "Pass":
        headline = f"Manual comparison passed across {matched_count} matched rows."
    elif status == "Review":
        headline = f"Review {review_count + missing_count} row(s); max delta {max_delta_text}."
    elif status == "No parsed values":
        headline = "No parsed sign-degree values yet."
    else:
        headline = f"Manual comparison status: {status}."
    return {
        "status": status,
        "headline": headline,
        "parsedInputCount": len(parsed_rows),
        "matchedCount": matched_count,
        "reviewCount": review_count,
        "missingCount": missing_count,
        "unparsedCount": unparsed_count,
        "maxDeltaText": max_delta_text,
        "topCauses": top_causes,
    }


def format_manual_validation_comparison(result: Mapping[str, object] | None) -> list[str]:
    if not isinstance(result, Mapping) or not result:
        return ["Manual comparison not run yet.", "Paste CapricornPROMETHEUS values on the Validation page and press Compare."]
    summary = manual_validation_result_summary(result)
    lines = [
        f"Source: {result.get('source', 'CapricornPROMETHEUS')}",
        f"Status: {result.get('status', 'n/a')}",
        (
            "Rows: "
            f"{int(summary['matchedCount'])} match, "
            f"{int(summary['reviewCount'])} review, "
            f"{int(summary['missingCount'])} missing, "
            f"{int(summary['unparsedCount'])} unparsed"
        ),
    ]
    max_delta = result.get("maxDeltaDegrees")
    if max_delta is not None:
        lines.append(f"Max delta: {float(max_delta):.4f} deg")
    top_causes = summary.get("topCauses", [])
    if isinstance(top_causes, list) and top_causes:
        lines.append("Likely causes: " + "; ".join(str(cause) for cause in top_causes))
    rows = result.get("rows", [])
    if isinstance(rows, list):
        for row in rows[:10]:
            if not isinstance(row, Mapping):
                continue
            if row.get("status") != "parsed":
                lines.append(f"- Unparsed: {row.get('line', '')}")
                continue
            delta = row.get("deltaDegrees")
            delta_text = "delta n/a" if delta is None else f"delta {float(delta):.4f} deg"
            app = row.get("appLongitude")
            app_text = "app n/a" if app is None else f"app {float(app):.3f}"
            lines.append(f"- {row.get('label')}: ref {row.get('referenceText')} | {app_text} | {delta_text} | {row.get('cause')}")
    return lines


def validation_quick_read_lines(snapshot: Mapping[str, object], location: object | None, manual_result: Mapping[str, object] | None = None) -> list[str]:
    accuracy = snapshot.get("accuracyAudit", {})
    if isinstance(accuracy, Mapping):
        accuracy_label = str(accuracy.get("label") or "Accuracy unavailable")
        planet_delta = float(accuracy.get("maxPositionDeltaDegrees", 0) or 0)
        angle_delta = float(accuracy.get("maxAngleDeltaDegrees", 0) or 0)
        house_delta = float(accuracy.get("maxHouseDeltaDegrees", 0) or 0)
        delta_line = f"Deltas: planets {planet_delta:.6f} deg, angles {angle_delta:.6f} deg, houses {house_delta:.6f} deg."
    else:
        accuracy_label = "Accuracy audit unavailable"
        delta_line = "Deltas unavailable."
    manual_summary = manual_validation_result_summary(manual_result)
    top_causes = manual_summary.get("topCauses", [])
    cause_line = "Likely cause: no manual mismatch flagged yet."
    if isinstance(top_causes, list) and top_causes:
        cause_line = "Likely cause: " + "; ".join(str(cause) for cause in top_causes)
    location_name = _compact_place_name(getattr(location, "name", "Location unavailable"))
    timezone = getattr(location, "timezone", "timezone n/a")
    zodiac_name = getattr(snapshot.get("zodiacSystem"), "name", "zodiac n/a")
    house_name = getattr(snapshot.get("houseSystem"), "name", "house n/a")
    return [
        "Quick Read",
        f"Engine audit: {accuracy_label}.",
        delta_line,
        f"Manual comparison: {manual_summary['headline']}",
        cause_line,
        f"Settings: {location_name} / {timezone} | {zodiac_name} / {house_name}.",
    ]


def validation_workbench_lines(snapshot: Mapping[str, object], location: object | None, manual_result: Mapping[str, object] | None = None) -> list[str]:
    accuracy = snapshot.get("accuracyAudit", {})
    lines = [
        "Accuracy Validation",
        "",
        *validation_quick_read_lines(snapshot, location, manual_result),
        "",
    ]
    if isinstance(accuracy, Mapping):
        lines.extend(
            [
                f"Status: {accuracy.get('label', 'Accuracy unavailable')}",
                str(accuracy.get("summary", "No accuracy summary available.")),
                f"Planet max delta: {float(accuracy.get('maxPositionDeltaDegrees', 0) or 0):.6f} deg",
                f"Angle max delta: {float(accuracy.get('maxAngleDeltaDegrees', 0) or 0):.6f} deg",
                f"House max delta: {float(accuracy.get('maxHouseDeltaDegrees', 0) or 0):.6f} deg",
            ]
        )
        speed = accuracy.get("maxSpeedDeltaDegreesPerDay")
        if speed is not None:
            lines.append(f"Speed max delta: {float(speed):.6f} deg/day")
    else:
        lines.append("Accuracy audit unavailable.")
    lines.extend(
        [
            "",
            "Chart Settings",
            f"Location: {getattr(location, 'name', 'Location unavailable')} / {getattr(location, 'timezone', 'timezone n/a')}",
            f"Zodiac: {getattr(snapshot.get('zodiacSystem'), 'name', 'zodiac n/a')}",
            f"House system: {getattr(snapshot.get('houseSystem'), 'name', 'house n/a')}",
            f"Ayanamsha: {float(snapshot.get('ayanamsha', 0) or 0):.3f} deg",
            f"Engine: {snapshot.get('engine', 'engine n/a')}",
            "",
            "Manual Comparison",
            *format_manual_validation_comparison(manual_result),
        ]
    )
    return lines
