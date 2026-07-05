"""Live Sky presentation helpers for the desktop UI."""

from __future__ import annotations

from typing import Mapping

from .engine.chart import format_position


LIVE_SKY_ORBIT_ORDER = {
    "Mercury": 0.18,
    "Venus": 0.25,
    "Earth": 0.34,
    "Moon": 0.38,
    "Mars": 0.46,
    "Ceres": 0.52,
    "Jupiter": 0.62,
    "Saturn": 0.72,
    "Uranus": 0.82,
    "Neptune": 0.90,
    "Pluto": 0.96,
}

LIVE_SKY_BODY_COLORS = {
    "Sun": "#ffd51f",
    "Mercury": "#d4aa44",
    "Venus": "#d4c060",
    "Earth": "#2747ff",
    "Moon": "#d8d9df",
    "Mars": "#d84635",
    "Jupiter": "#d69b3e",
    "Saturn": "#caa45d",
    "Uranus": "#7fd8ff",
    "Neptune": "#8673e6",
    "Pluto": "#b98864",
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
    return PLANET_GLYPHS.get(name, name[:2] or "?")


def live_sky_body_rows(snapshot: Mapping[str, object]) -> list[dict[str, object]]:
    positions = snapshot.get("positions", [])
    if not isinstance(positions, list):
        return []
    by_name = {str(point.get("name")): point for point in positions if isinstance(point, Mapping)}
    rows: list[dict[str, object]] = []
    sun = by_name.get("Sun")
    if isinstance(sun, Mapping):
        sun_longitude = _safe_float(sun.get("tropicalLongitude", sun.get("longitude")), 0.0) % 360.0
        rows.append(
            {
                "name": "Sun",
                "glyph": planet_glyph("Sun"),
                "longitude": sun_longitude,
                "radiusFactor": 0.0,
                "color": LIVE_SKY_BODY_COLORS["Sun"],
                "position": format_position(dict(sun)),
                "distanceAu": 0.0,
            }
        )
        rows.append(
            {
                "name": "Earth",
                "glyph": "E",
                "longitude": (sun_longitude + 180.0) % 360.0,
                "radiusFactor": LIVE_SKY_ORBIT_ORDER["Earth"],
                "color": LIVE_SKY_BODY_COLORS["Earth"],
                "position": "opposite Sun",
                "distanceAu": 1.0,
            }
        )
    for point in positions:
        if not isinstance(point, Mapping):
            continue
        name = str(point.get("name") or "")
        if name == "Sun":
            continue
        longitude = _safe_float(point.get("tropicalLongitude", point.get("longitude")), 0.0) % 360.0
        rows.append(
            {
                "name": name,
                "glyph": planet_glyph(name),
                "longitude": longitude,
                "radiusFactor": LIVE_SKY_ORBIT_ORDER.get(name, 0.55),
                "color": LIVE_SKY_BODY_COLORS.get(name, "#cfd8dc"),
                "position": format_position(dict(point)),
                "distanceAu": point.get("distanceAu"),
            }
        )
    rows.sort(key=lambda row: (float(row.get("radiusFactor", 0.0)), str(row.get("name", ""))))
    return rows


def live_sky_timestamp_line(snapshot: Mapping[str, object], location: object | None, mode: str) -> str:
    mode_label = "Live" if mode == "live" else "Manual"
    timezone_name = getattr(location, "timezone", "timezone n/a")
    return f"{mode_label}: {snapshot.get('formattedTime', 'time unavailable')} ({timezone_name})"
