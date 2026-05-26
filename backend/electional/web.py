"""Server-rendered Python interface for Electional Software."""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Mapping

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


def render_wheel_placeholder(preset_name: str) -> str:
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

    return f"""
      <svg class="wheel-svg python-wheel-svg" viewBox="0 0 600 600" role="img" aria-label="Python-rendered electional wheel placeholder">
        <circle class="outer-disc" cx="300" cy="300" r="282" />
        {''.join(sectors)}
        <circle class="aspect-disc" cx="300" cy="300" r="210" />
        <circle class="aspect-disc" cx="300" cy="300" r="118" />
        <line class="angle-line asc" x1="28" y1="300" x2="572" y2="300" />
        <line class="angle-line mc" x1="300" y1="28" x2="300" y2="572" />
        <text class="angle-label asc" x="62" y="292">ASC</text>
        <text class="angle-label dsc" x="538" y="292">DSC</text>
        <text class="angle-label mc" x="322" y="60">MC</text>
        <text class="angle-label ic" x="322" y="540">IC</text>
        <circle class="center-disc" cx="300" cy="300" r="78" />
        <text class="center-title" x="300" y="292">Python</text>
        <text class="center-subtitle" x="300" y="318">{escape(preset_name)}</text>
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

    location_options = "\n".join(option(location_option.id, location_option.name, selected_location_id) for location_option in LOCATION_PRESETS)
    preset_options = "\n".join(option(preset_option.id, preset_option.name, selected_preset_id) for preset_option in ELECTIONAL_PRESETS)
    objective_options = "\n".join(option(value, label, selected_objective) for value, label in OBJECTIVES.items())
    aspect_rows = "\n".join(
        f"<span class=\"tag\">{escape(aspect_id)}: {preset.aspect_orbs[aspect_id]:g} deg</span>"
        for aspect_id in preset.aspect_ids
    )
    point_rows = "\n".join(f"<span class=\"tag muted-tag\">{escape(point)}</span>" for point in preset.point_names)

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
            <span>{escape(selected_date)} {escape(selected_time)}</span>
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
                <span>Py</span>
                <small>interface owner</small>
              </div>
            </div>
            <div class="wheel-frame">{render_wheel_placeholder(preset.short_name)}</div>
          </section>

          <aside class="inspector" aria-label="Python chart data panels">
            <section class="summary-grid" aria-label="Election summary">
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
                <strong>Python now owns this interface route.</strong>
                <span>Ephemeris and house-angle calculation are the next backend migration layer. The legacy browser UI remains available during transition.</span>
              </article>
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
      <span>Chart time: <strong>{escape(selected_date)} {escape(selected_time)}</strong></span>
      <span>Preset: <strong>{escape(preset.name)}</strong></span>
      <span>Backend: <strong>Python interface</strong></span>
      <span>Engine: <strong>Migration mode</strong></span>
    </footer>
  </body>
</html>
"""
