"""Validation helpers shared by desktop and API-facing code."""

from __future__ import annotations

from datetime import datetime

from .time_utils import is_valid_timezone, normalize_time_text


def validate_election_inputs(date_text: str, time_text: str, latitude_text: str, longitude_text: str, timezone_text: str) -> list[str]:
    errors = []
    try:
        datetime.strptime(date_text.strip(), "%Y-%m-%d")
    except ValueError:
        errors.append("Date must use YYYY-MM-DD.")

    try:
        normalize_time_text(time_text)
    except ValueError as exc:
        errors.append(str(exc))

    try:
        latitude = float(latitude_text)
        if not -90 <= latitude <= 90:
            errors.append("Latitude must be between -90 and 90.")
    except ValueError:
        errors.append("Latitude must be a number.")

    try:
        longitude = float(longitude_text)
        if not -180 <= longitude <= 180:
            errors.append("Longitude must be between -180 and 180.")
    except ValueError:
        errors.append("Longitude must be a number.")

    if not is_valid_timezone(timezone_text.strip() or "UTC"):
        errors.append("Time zone must be a valid IANA name like America/Los_Angeles.")

    return errors


def parse_optional_int(text: str, field_name: str, errors: list[str], *, minimum: int | None = None) -> int | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    try:
        value = int(cleaned)
    except ValueError:
        errors.append(f"{field_name} must be a whole number.")
        return None
    if minimum is not None and value < minimum:
        errors.append(f"{field_name} must be at least {minimum}.")
    return value


def validate_search_inputs(
    scan_hours_text: str,
    step_minutes_text: str,
    minimum_score_text: str,
    max_results_text: str,
    minimum_fit_text: str = "",
) -> list[str]:
    errors: list[str] = []
    scan_hours = parse_optional_int(scan_hours_text, "Scan hours", errors, minimum=0)
    step_minutes = parse_optional_int(step_minutes_text, "Step minutes", errors, minimum=1)
    minimum_score = parse_optional_int(minimum_score_text, "Minimum score", errors, minimum=10)
    parse_optional_int(max_results_text, "Max results", errors, minimum=1)
    minimum_fit = parse_optional_int(minimum_fit_text, "Minimum fit", errors, minimum=0)
    if minimum_score is not None and minimum_score > 99:
        errors.append("Minimum score must be 99 or lower.")
    if minimum_fit is not None and minimum_fit > 5:
        errors.append("Minimum fit must be 5 or lower.")
    if scan_hours is not None and step_minutes is not None and scan_hours * 60 < step_minutes:
        errors.append("Step minutes must fit inside the scan range.")
    return errors
