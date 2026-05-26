"""Server-rendered Python interface for Electional Software."""

from __future__ import annotations

from datetime import date
from html import escape
from math import cos, radians, sin
from typing import Mapping

from .chart import build_snapshot, build_transit_windows, format_angle, format_position
from .locations import LOCATION_PRESETS, get_location
from .presets import ELECTIONAL_PRESETS, get_preset, summarize_orb


OBJECTIVES = {
    "launch": "Launch or publish",
    "meeting": "Meeting or negotiation",
    "creative": "Creative work",
    "relationship": "Relationship timing",
}


def get_first(params: Mapping[str, list[str]], key: str, default: str) -> str:
    values = params.get(key)
    return values[0] if values else default


def option(value: str, label: str, selected_value: str) -> str:
    selected = " selected" if value == selected_value else ""
    return f'<option value="{escape(value)}"{selected}>{escape(label)}</option>'


def polar_point(center: float, radius: float, degrees: float) -> tuple[float, float]:
    angle = radians(degrees)
    return center + radius * cos(angle), center + radius * sin(angle)


def longitude_to_wheel_degrees(longitude: float, ascendant_longitude: float) -> float:
    return 180 - ((longitude - ascendant_longitude) % 360)


def line_for_longitude(longitude: float, ascendant_longitude: float, inner_radius: float, outer_radius: float, class_name: str) -> str:
    center = 300
    degrees = longitude_to_wheel_degrees(longitude, ascendant_longitude)
    inner = polar_point(center, inner_radius, degrees)
    outer = polar_point(center, outer_radius, degrees)
    return (
        f'<line class="{class_name}" x1="{inner[0]:.2f}" y1="{inner[1]:.2f}" '
        f'x2="{outer[0]:.2f}" y2="{outer[1]:.2f}" />'
    )


def render_wheel(snapshot: dict[str, object]) -> str:
    angles = snapshot["angles"]
    positions = snapshot["positions"]
    aspects = snapshot["detectedAspects"]
    ascendant = next(angle for angle in angles if angle["id"] == "asc")
    ascendant_longitude = float(ascendant["longitude"])
    sectors = []
    colors = ["#d66d86", "#caa778", "#22b8a9", "#b55c9e"]
    for index in range(12):
        rotation = index * 30
        sectors.append(
            f'<line class="python-wheel-tick" x1="300" y1="28" x2="300" y2="92" transform="rotate({rotation} 300 300)" />'
        )
        sectors.append(
            f'<path class="python-wheel-sector" style="--sector:{colors[index % len(colors)]}" '
            f'd="M300 300 L300 28 A272 272 0 0 1 436 64 Z" transform="rotate({rotation} 300 300)" />'
        )

    planet_markers = []
    for planet in positions:
        degrees = longitude_to_wheel_degrees(float(planet["longitude"]), ascendant_longitude)
        point = polar_point(300, 207, degrees)
        tick_start = polar_point(300, 226, degrees)
        tick_end = polar_point(300, 238, degrees)
        angular_class = " angular" if planet.get("isAngular") else ""
        label = escape(str(planet["name"])[:2])
        planet_markers.append(
            f'<line class="planet-tick" x1="{tick_start[0]:.2f}" y1="{tick_start[1]:.2f}" '
            f'x2="{tick_end[0]:.2f}" y2="{tick_end[1]:.2f}" />'
            f'<g class="planet-marker{angular_class}" transform="translate({point[0]:.2f} {point[1]:.2f})">'
            f'<circle r="12" /><text y="5">{label}</text></g>'
        )

    aspect_lines = []
    color_by_aspect = {
        "conjunction": "#283047",
        "trine": "#1c8f7a",
        "sextile": "#2279a8",
        "square": "#b54e64",
        "opposition": "#8b3e8a",
    }
    for aspect in aspects:
        first = next((planet for planet in positions if planet["name"] == aspect["bodies"][0]), None)
        second = next((planet for planet in positions if planet["name"] == aspect["bodies"][1]), None)
        if not first or not second:
            continue
        first_point = polar_point(300, 118, longitude_to_wheel_degrees(float(first["longitude"]), ascendant_longitude))
        second_point = polar_point(300, 118, longitude_to_wheel_degrees(float(second["longitude"]), ascendant_longitude))
        color = color_by_aspect.get(str(aspect["aspectId"]), "#8b7c6f")
        aspect_lines.append(
            f'<line class="aspect-line" style="--aspect-color:{color}" '
            f'x1="{first_point[0]:.2f}" y1="{first_point[1]:.2f}" '
            f'x2="{second_point[0]:.2f}" y2="{second_point[1]:.2f}" />'
        )

    angle_lines = "".join(
        line_for_longitude(float(angle["longitude"]), ascendant_longitude, 88, 282, f"angle-line {angle['id']}")
        for angle in angles
    )
    angle_labels = []
    for angle in angles:
        point = polar_point(300, 248, longitude_to_wheel_degrees(float(angle["longitude"]), ascendant_longitude))
        angle_labels.append(
            f'<text class="angle-label {angle["id"]}" x="{point[0]:.2f}" y="{point[1]:.2f}">{escape(str(angle["shortName"]))}</text>'
        )

    return f"""
      <svg class="wheel-svg python-wheel-svg" viewBox="0 0 600 600" role="img" aria-label="Python-rendered electional astrology chart">
        <circle class="outer-disc" cx="300" cy="300" r="282" />
        {''.join(sectors)}
        <circle class="aspect-disc" cx="300" cy="300" r="210" />
        <circle class="aspect-disc" cx="300" cy="300" r="118" />
        {''.join(aspect_lines)}
        {angle_lines}
        {''.join(planet_markers)}
        {''.join(angle_labels)}
        <circle class="center-disc" cx="300" cy="300" r="78" />
        <text class="center-title" x="300" y="292">Python</text>
        <text class="center-subtitle" x="300" y="318">{escape(str(snapshot["engine"]))}</text>
      </svg>
    """


def render_app(params: Mapping[str, list[str]] | None = None) -> str:
    params = params or {}
    selected_location_id = get_first(params, "location", "los-angeles")
    selected_preset_id = get_first(params, "preset", "transit-1-degree")
    selected_objective = get_first(params, "objective", "launch")
    selected_date = get_first(params, "date", date.today().isoformat())
    selected_time = get_first(params, "time", "09:00")

    location = get_location(selected_location_id)
    preset = get_preset(selected_preset_id)
    objective_label = OBJECTIVES.get(selected_objective, OBJECTIVES["launch"])
    snapshot = build_snapshot(selected_date, selected_time, location, selected_preset_id)
    windows = build_transit_windows(selected_date, selected_time, location, selected_preset_id)
    top_window = windows[0]
    all_detected = [aspect for window in windows for aspect in window["detectedAspects"]]
    support_count = sum(1 for aspect in all_detected if aspect["tone"] == "support")
    stress_count = sum(1 for aspect in all_detected if aspect["tone"] == "stress")
    tracked_count = len({aspect["aspectId"] for aspect in all_detected})
    angular_count = sum(1 for planet in top_window["positions"] if planet.get("isAngular") and planet.get("isPresetPoint"))

    location_options = "\n".join(option(location_option.id, location_option.name, selected_location_id) for location_option in LOCATION_PRESETS)
    preset_options = "\n".join(option(preset_option.id, preset_option.name, selected_preset_id) for preset_option in ELECTIONAL_PRESETS)
    objective_options = "\n".join(option(value, label, selected_objective) for value, label in OBJECTIVES.items())
    aspect_rows = "\n".join(
        f"<span class=\"tag\">{escape(aspect_id)}: {preset.aspect_orbs[aspect_id]:g} deg</span>"
        for aspect_id in preset.aspect_ids
    )
    point_rows = "\n".join(f"<span class=\"tag muted-tag\">{escape(point)}</span>" for point in preset.point_names)
    timeline_rows = "\n".join(
        f"""
        <article class="timeline-card{' selected' if index == 0 else ''}">
          <div class="timeline-time">{escape(str(window['time']))}</div>
          <div>
            <div class="timeline-title">{escape(str(window['title']))}</div>
            <div class="timeline-meta">{escape(str(window['note']))}</div>
          </div>
          <div class="tag-row"><span class="tag">Score {window['score']}</span></div>
        </article>
        """
        for index, window in enumerate(windows)
    )
    position_rows = "\n".join(
        f"""
        <article class="position-row{' muted-position' if not planet.get('isPresetPoint') else ''}">
          <div>
            <strong>{escape(str(planet['name']))}</strong>
            <small>House {planet['house']} / {escape(str(planet['dignity']['label']))}</small>
          </div>
          <span>{escape(format_position(planet))}</span>
        </article>
        """
        for planet in snapshot["positions"]
    )
    angle_rows = "\n".join(
        f'<article class="angle-card"><span>{escape(str(angle["name"]))}</span><strong>{escape(format_angle(angle))}</strong></article>'
        for angle in snapshot["angles"]
    )
    detected_rows = "\n".join(
        f"""
        <article class="detected-card{' stress' if aspect['tone'] == 'stress' else ''}">
          <strong>{escape(str(aspect['label']))}</strong>
          <span>{escape(str(aspect['orbText']))} orb / limit {float(aspect['orbLimit']):g} deg</span>
        </article>
        """
        for aspect in snapshot["detectedAspects"]
    ) or """
        <article class="empty-state">
          <strong>No selected aspects in orb</strong>
          <span>Try a wider preset or a different time.</span>
        </article>
    """

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Electional Software Python</title>
    <link rel="stylesheet" href="/styles.css" />
  </head>
  <body>
    <header class="top-ribbon" aria-label="Application tools">
      <div class="app-title">Electional Software - Python Interface</div>
      <nav class="menu-strip" aria-label="Main sections">
        <span>Chart</span>
        <span>Selected Chart</span>
        <span>View Page</span>
        <span>Search</span>
        <span>Utility</span>
        <span>Configuration Editors</span>
        <span>Astro Mapping</span>
      </nav>
      <div class="tool-strip" aria-label="Electional tools">
        <button type="button">Python Chart</button>
        <button type="button">Presets</button>
        <button type="button">Electional Search</button>
        <button type="button">Ephemeris Next</button>
      </div>
    </header>

    <main class="app-shell">
      <aside class="sidebar" aria-label="Electional controls">
        <div class="brand">
          <p class="eyebrow">Python App</p>
          <h1>Election chart</h1>
          <div class="chart-meta">
            <span>{escape(str(snapshot["formattedTime"]))}</span>
            <span>{escape(location.name)}</span>
            <span>{location.latitude:.4f}, {location.longitude:.4f}</span>
            <span>{escape(location.timezone)}</span>
          </div>
        </div>

        <form class="control-panel" method="get" action="/">
          <label>
            Election date
            <input type="date" name="date" value="{escape(selected_date)}" />
          </label>
          <label>
            Start time
            <input type="time" name="time" value="{escape(selected_time)}" />
          </label>
          <label>
            Location preset
            <select name="location">{location_options}</select>
          </label>
          <label>
            Objective
            <select name="objective">{objective_options}</select>
          </label>
          <label>
            Electional preset
            <select name="preset">{preset_options}</select>
          </label>
          <button class="python-submit" type="submit">Recalculate in Python</button>
        </form>
      </aside>

      <section class="workspace" aria-live="polite">
        <section class="chart-board">
          <div class="chart-left-rail" aria-label="House groups">
            <div class="house-badge">Py<br />UI<br />1</div>
            <div class="house-badge">No<br />JS</div>
            <div class="house-badge">API</div>
          </div>

          <section class="wheel-panel" aria-label="Python astrology chart wheel">
            <div class="wheel-header">
              <div>
                <p class="eyebrow">Server-rendered Python interface</p>
                <h2>{escape(objective_label)} windows near {escape(location.name)}</h2>
              </div>
              <div class="score-card">
                <span>{top_window["score"]}</span>
                <small>top window score</small>
              </div>
            </div>
            <div class="wheel-frame">{render_wheel(snapshot)}</div>
          </section>

          <aside class="inspector" aria-label="Python chart data panels">
            <section class="summary-grid" aria-label="Election summary">
              <article><span>Benefic</span><strong>{support_count}</strong></article>
              <article><span>Stress</span><strong>{stress_count}</strong></article>
              <article><span>Aspects</span><strong>{tracked_count}</strong></article>
              <article><span>Angular</span><strong>{angular_count}</strong></article>
              <article><span>Preset</span><strong>{escape(preset.short_name)}</strong></article>
              <article><span>Orb mode</span><strong>{escape(summarize_orb(preset))}</strong></article>
              <article><span>Timezone</span><strong>{escape(location.timezone)}</strong></article>
              <article><span>Backend</span><strong>Python</strong></article>
            </section>

            <section class="panel-block">
              <div class="section-heading">
                <h3>Migration status</h3>
                <p>No JavaScript required for this screen.</p>
              </div>
              <article class="empty-state">
                <strong>Python now owns the interface and chart calculations.</strong>
                <span>Timezone conversion, ephemeris, angles, houses, aspects, dignity, scoring, and candidate windows are calculated server-side.</span>
              </article>
            </section>

            <section class="panel-block">
              <div class="section-heading">
                <h3>Candidate windows</h3>
                <p>Ranked by Python scoring.</p>
              </div>
              <div class="timeline">{timeline_rows}</div>
            </section>

            <section class="panel-block">
              <div class="section-heading">
                <h3>Planets</h3>
                <p>{escape(str(snapshot["engine"]))}</p>
              </div>
              <div class="position-grid">{position_rows}</div>
            </section>

            <section class="panel-block">
              <div class="section-heading">
                <h3>Angles</h3>
                <p>Whole Sign houses.</p>
              </div>
              <div class="angle-grid">{angle_rows}</div>
            </section>

            <section class="panel-block">
              <div class="section-heading">
                <h3>Detected aspects</h3>
                <p>Inside Python preset orbs.</p>
              </div>
              <div class="detected-grid">{detected_rows}</div>
            </section>

            <section class="panel-block">
              <div class="section-heading">
                <h3>Aspect preset</h3>
                <p>{escape(preset.source)}</p>
              </div>
              <div class="tag-row">{aspect_rows}</div>
            </section>

            <section class="panel-block">
              <div class="section-heading">
                <h3>Point set</h3>
                <p>{len(preset.point_names)} active points.</p>
              </div>
              <div class="tag-row">{point_rows}</div>
            </section>
          </aside>
        </section>
      </section>
    </main>

    <footer class="status-bar" aria-label="Application status">
      <span>Location: <strong>{escape(location.name)}</strong></span>
      <span>Chart time: <strong>{escape(str(snapshot["formattedTime"]))}</strong></span>
      <span>Preset: <strong>{escape(preset.name)}</strong></span>
      <span>Backend: <strong>Python chart engine</strong></span>
      <span>Engine: <strong>{escape(str(snapshot["engine"]))}</strong></span>
    </footer>
  </body>
</html>
"""
