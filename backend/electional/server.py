"""Small standard-library JSON API for the Python electional core."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .aspects import detect_aspects
from .presets import apply_dignities, filter_positions_for_preset, get_preset, summarize_orb
from .scoring import score_window


def build_score_response(payload: dict[str, Any]) -> dict[str, Any]:
    preset = get_preset(payload.get("presetId"))
    positions = apply_dignities(payload.get("positions", []), preset)
    preset_positions = filter_positions_for_preset(positions, preset)
    selected_aspects = payload.get("aspects") or preset.aspect_ids
    detected = detect_aspects(preset_positions, selected_aspects, preset.aspect_orbs)

    return {
        "preset": preset.to_json(),
        "orbMode": summarize_orb(preset),
        "positions": positions,
        "detectedAspects": detected,
        "score": score_window(detected, positions, preset),
    }


class ElectionalRequestHandler(BaseHTTPRequestHandler):
    server_version = "ElectionalPython/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
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
        if path != "/api/score":
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            response = build_score_response(payload)
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

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
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
