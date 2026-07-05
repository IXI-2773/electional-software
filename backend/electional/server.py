"""Small standard-library JSON API for the Python electional core."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .aspects import Aspect, aspect_from_mapping, aspect_profile_by_id, detect_aspects
from .engine.chart import build_election_report, build_snapshot, build_transit_windows
from .locations import LocationPreset, get_location
from .presets import apply_dignities, filter_positions_for_preset, get_preset, summarize_orb
from .reports.text_report import build_report_text
from .engine.scoring import score_breakdown, score_window
from .engine.search import SearchConfig
from .web import render_app


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def json_default(value: object) -> object:
    if hasattr(value, "to_json"):
        return value.to_json()  # type: ignore[no-any-return]
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def location_from_payload(payload: dict[str, Any]) -> LocationPreset:
    custom = payload.get("location")
    if isinstance(custom, dict):
        return LocationPreset(
            str(custom.get("id") or "custom"),
            str(custom.get("name") or "Custom Location"),
            float(custom.get("latitude", 0)),
            float(custom.get("longitude", 0)),
            str(custom.get("timezone") or "UTC"),
        )
    return get_location(str(payload.get("locationId") or payload.get("location") or "los-angeles"))


def optional_int(payload: dict[str, Any], key: str, fallback: int | None = None) -> int | None:
    if key not in payload or payload[key] in (None, ""):
        return fallback
    try:
        return int(payload[key])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a whole number.") from exc


def search_config_from_payload(payload: dict[str, Any]) -> SearchConfig:
    def minutes_from(key: str, fallback: int) -> int:
        if key in payload:
            value = optional_int(payload, key)
            return fallback if value is None else value
        hour_key = key.replace("Minutes", "Hours")
        if hour_key in payload:
            try:
                return int(float(payload[hour_key]) * 60)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{hour_key} must be a number.") from exc
        return fallback

    step_minutes = optional_int(payload, "stepMinutes", 120)
    config = SearchConfig(
        start_offset_minutes=minutes_from("startOffsetMinutes", 0),
        end_offset_minutes=minutes_from("endOffsetMinutes", 600),
        step_minutes=120 if step_minutes is None else step_minutes,
        max_results=optional_int(payload, "maxResults"),
        minimum_score=optional_int(payload, "minimumScore"),
        minimum_fit=optional_int(payload, "minimumFit"),
        minimum_confidence=optional_int(payload, "minimumConfidence"),
        minimum_cleanliness=optional_int(payload, "minimumCleanliness"),
        maximum_volatility=optional_int(payload, "maximumVolatility"),
        avoid_major_stress=bool(payload.get("avoidMajorStress", False)),
        require_applying_support=bool(payload.get("requireApplyingSupport", False)),
        require_angular_benefic=bool(payload.get("requireAngularBenefic", False)),
        avoid_angular_malefics=bool(payload.get("avoidAngularMalefics", False)),
        require_moon_non_void=bool(payload.get("requireMoonNonVoid", False)),
        avoid_objective_antipatterns=bool(payload.get("avoidObjectiveAntipatterns", False)),
        target_aspect_text=str(payload.get("targetAspect") or payload.get("targetAspectText") or ""),
        target_aspect_body_text=str(payload.get("targetAspectBody") or payload.get("targetAspectBodyText") or ""),
        target_planet_text=str(payload.get("targetPlanet") or payload.get("targetPlanetText") or ""),
        target_sign_text=str(payload.get("targetSign") or payload.get("targetSignText") or ""),
        target_house=optional_int(payload, "targetHouse"),
        quality_mode=str(payload.get("qualityMode") or payload.get("searchQualityMode") or "balanced"),
    )
    config.offsets()
    if config.minimum_score is not None and not 10 <= config.minimum_score <= 99:
        raise ValueError("minimumScore must be between 10 and 99.")
    if config.max_results is not None and config.max_results < 1:
        raise ValueError("maxResults must be at least 1.")
    if config.target_house is not None and not 1 <= config.target_house <= 12:
        raise ValueError("targetHouse must be between 1 and 12.")
    return config


def aspect_definitions_from_payload(payload: dict[str, Any]) -> tuple[Aspect, ...] | None:
    explicit = payload.get("aspectDefinitions")
    if isinstance(explicit, list):
        definitions = [aspect_from_mapping(item) for item in explicit if isinstance(item, dict)]
        return tuple(definitions) if definitions else None
    profile_id = payload.get("aspectProfileId")
    if profile_id:
        return aspect_profile_by_id(str(profile_id)).aspects
    return None


def selected_aspects_from_payload(payload: dict[str, Any], preset: object, aspect_definitions: tuple[Aspect, ...] | None) -> list[str] | tuple[str, ...]:
    explicit = payload.get("aspects")
    if isinstance(explicit, list) and explicit:
        return [str(item) for item in explicit]
    if aspect_definitions:
        return [aspect.id for aspect in aspect_definitions if aspect.enabled]
    return preset.aspect_ids


def decode_json_object(raw_body: bytes) -> dict[str, Any]:
    payload = json.loads(raw_body or b"{}")
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object.")
    return payload


def build_score_response(payload: dict[str, Any]) -> dict[str, Any]:
    preset = get_preset(payload.get("presetId"))
    positions = apply_dignities(payload.get("positions", []), preset)
    preset_positions = filter_positions_for_preset(positions, preset)
    aspect_definitions = aspect_definitions_from_payload(payload)
    selected_aspects = selected_aspects_from_payload(payload, preset, aspect_definitions)
    detected = detect_aspects(preset_positions, selected_aspects, preset.aspect_orbs, aspect_definitions=aspect_definitions)

    return {
        "preset": preset.to_json(),
        "orbMode": summarize_orb(preset),
        "positions": positions,
        "detectedAspects": detected,
        "score": score_window(detected, positions, preset),
        "scoreBreakdown": score_breakdown(detected, positions, preset),
    }


def build_chart_response(payload: dict[str, Any]) -> dict[str, Any]:
    location = location_from_payload(payload)
    preset = get_preset(str(payload.get("presetId") or "traditional-lilly"))
    aspect_definitions = aspect_definitions_from_payload(payload)
    selected_aspects = selected_aspects_from_payload(payload, preset, aspect_definitions)
    snapshot = build_snapshot(
        str(payload.get("date") or "2026-05-26"),
        str(payload.get("time") or "09:00"),
        location,
        preset.id,
        selected_aspects,
        str(payload.get("zodiacSystemId") or payload.get("zodiacSystem") or "sidereal-lahiri"),
        str(payload.get("houseSystemId") or payload.get("houseSystem") or "whole-sign"),
        str(payload.get("objective") or "Launch or publish"),
        aspect_definitions,
    )
    return {"location": location.to_json(), "snapshot": snapshot}


def build_search_response(payload: dict[str, Any]) -> dict[str, Any]:
    location = location_from_payload(payload)
    config = search_config_from_payload(payload)
    preset = get_preset(str(payload.get("presetId") or "traditional-lilly"))
    aspect_definitions = aspect_definitions_from_payload(payload)
    selected_aspects = selected_aspects_from_payload(payload, preset, aspect_definitions)
    windows = build_transit_windows(
        str(payload.get("date") or "2026-05-26"),
        str(payload.get("time") or "09:00"),
        location,
        preset.id,
        selected_aspects,
        str(payload.get("zodiacSystemId") or payload.get("zodiacSystem") or "sidereal-lahiri"),
        str(payload.get("houseSystemId") or payload.get("houseSystem") or "whole-sign"),
        config,
        str(payload.get("objective") or "Launch or publish"),
        aspect_definitions,
    )
    return {"location": location.to_json(), "search": asdict(config), "resultCount": len(windows), "windows": windows}


def build_report_response(payload: dict[str, Any]) -> dict[str, Any]:
    location = location_from_payload(payload)
    config = search_config_from_payload(payload)
    preset = get_preset(str(payload.get("presetId") or "traditional-lilly"))
    aspect_definitions = aspect_definitions_from_payload(payload)
    selected_aspects = selected_aspects_from_payload(payload, preset, aspect_definitions)
    report = build_election_report(
        str(payload.get("date") or "2026-05-26"),
        str(payload.get("time") or "09:00"),
        location,
        preset.id,
        selected_aspects,
        str(payload.get("zodiacSystemId") or payload.get("zodiacSystem") or "sidereal-lahiri"),
        str(payload.get("houseSystemId") or payload.get("houseSystem") or "whole-sign"),
        config,
        str(payload.get("objective") or "Launch or publish"),
        aspect_definitions,
    )
    windows = report["windows"]
    selected_window = windows[0] if windows else report["snapshot"]
    return {
        **report,
        "location": location.to_json(),
        "search": asdict(config),
        "resultCount": len(windows),
        "reportText": build_report_text(selected_window, windows, location),
    }


class ElectionalRequestHandler(BaseHTTPRequestHandler):
    server_version = "ElectionalPython/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/":
            self.send_html(render_app(parse_qs(parsed_url.query)))
            return

        if path == "/styles.css":
            self.send_static_file(PROJECT_ROOT / "styles.css", "text/css; charset=utf-8")
            return

        if path == "/api/health":
            self.send_json({"ok": True, "service": "electional-python"})
            return

        if path == "/api/presets":
            from .presets import ELECTIONAL_PRESETS

            self.send_json({"presets": [preset.to_json() for preset in ELECTIONAL_PRESETS]})
            return

        self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        routes = {
            "/api/score": build_score_response,
            "/api/chart": build_chart_response,
            "/api/search": build_search_response,
            "/api/report": build_report_response,
        }
        if path not in routes:
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("content-length", "0"))
            payload = decode_json_object(self.rfile.read(length))
            response = routes[path](payload)
        except Exception as exc:  # pragma: no cover - returned to caller for local debugging.
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self.send_json(response)

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def send_html(self, html: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, default=json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), ElectionalRequestHandler)
    print(f"Electional Python API listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
