"""Native desktop application shell for Electional Software."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, ttk
import traceback
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

from .calendar_export import calendar_from_entries
from .aspect_highlights import build_aspect_highlights
from .aspects import (
    Aspect,
    AspectProfile,
    DEFAULT_ASPECT_PROFILE_ID,
    aspect_profile_by_id,
    load_aspect_profiles,
    sanitize_aspect_id,
    save_aspect_profiles,
    validate_aspect_profile,
)
from .capricorn_assets import (
    format_capricorn_asset_audit,
    format_capricorn_aspect_import_result,
    import_capricorn_aspect_profiles,
    inventory_capricorn_assets,
)
from .chart import build_election_report, build_snapshot_for_moment, clear_snapshot_cache, format_angle, format_position, snapshot_cache_info
from .constellations import ECLIPTIC_CONSTELLATION_SPANS
from .locations import (
    DEFAULT_TIMEZONE,
    LOCATION_PRESETS,
    LocationPreset,
    build_custom_location,
    combined_visible_location_names,
    default_location_for_timezone,
    home_location_for_app,
    get_location,
    load_hidden_builtin_location_ids,
    load_home_location_name,
    load_user_locations,
    reset_location_defaults,
    save_hidden_builtin_location_ids,
    save_home_location_name,
    save_user_locations,
    resolve_location_by_name,
    upsert_user_location,
)
from .point_sets import POINT_SET_NAMES, PointSet, get_point_set, visible_lots_for_point_set, visible_planets_for_point_set
from .presets import ELECTIONAL_PRESETS, RULERS
from .references import dignity_table_lines, lot_reference_lines, system_reference_lines
from .reporting import (
    build_analysis_page,
    build_classical_point_data_page,
    build_comparison_export_text,
    build_decision_brief_page,
    build_diagnostics_page,
    build_medieval_data_page,
    build_transit_search_page,
    build_window_comparison_page,
    build_report_text,
    advisor_lines,
    angle_testimony_lines,
    condition_lines,
    constellation_lines,
    format_aspectarian,
    format_aspect_highlight,
    format_aspect_highlight_dashboard,
    format_aspect_timeline,
    format_dignity_summary,
    format_aspect_summary,
    format_fixed_star_contact,
    format_lunar_phase,
    format_motion_summary,
    format_planet_focus,
    format_score_breakdown,
    format_window_label,
    factor_explorer_lines,
    judgment_context_lines,
    improvement_guide_lines,
    rule_lines,
    score_accounting_lines,
    score_diagnostic_lines,
    score_evaluation_lines,
    score_reason_lines,
    strongest_aspect_analysis_lines,
    validation_summary_lines,
)
from .screening import moon_void_course_summary, solar_elongation_summary
from .search import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_MAXIMUM_VOLATILITY,
    DEFAULT_MINIMUM_CLEANLINESS,
    DEFAULT_MINIMUM_CONFIDENCE,
    DEFAULT_MINIMUM_FIT,
    DEFAULT_MINIMUM_SCORE,
    DEFAULT_SCAN_HOURS,
    DEFAULT_STEP_MINUTES,
    SEARCH_PRESET_NAMES,
    SEARCH_QUALITY_MODE_NAMES,
    SearchConfig,
    build_search_config_from_text,
    format_search_summary,
    search_preset_values,
)
from .session import OBJECTIVES, clean_session_state, load_session_state, save_session_state
from .shortlist import add_shortlist_entry, build_shortlist_entry, format_shortlist_entries, load_shortlist, save_shortlist
from .shortlist import (
    SHORTLIST_TAG_CHOICES,
    add_shortlist_tag,
    build_shortlist_compare_text,
    normalize_shortlist_tags,
    remove_shortlist_tag,
    shortlist_batch_diagnostics,
    shortlist_entry_by_id,
)
from .systems import DEFAULT_HOUSE_SYSTEM_ID, DEFAULT_ZODIAC_SYSTEM_ID, HOUSE_SYSTEMS, ZODIAC_SYSTEMS, get_house_system, get_zodiac_system
from .time_utils import normalize_time_text
from .validation import validate_election_inputs, validate_search_inputs

DEBUG_LOG_PATH = Path(__file__).resolve().parents[2] / "reports" / "electional-debug.log"
APP_BUILD_LABEL = "Search Workbench Repair 2026-06-07"


def record_desktop_exception(context: str) -> Path | None:
    try:
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as log:
            log.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] {context}\n")
            log.write(traceback.format_exc())
        return DEBUG_LOG_PATH
    except OSError:
        return None


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
    "Moon": "\u263D",
    "Mercury": "\u263F",
    "Venus": "\u2640",
    "Mars": "\u2642",
    "Jupiter": "\u2643",
    "Saturn": "\u2644",
    "Uranus": "\u26E2",
    "Neptune": "\u2646",
    "Pluto": "\u2647",
}
SIGN_GLYPHS = {
    "Ar": "\u2648",
    "Ta": "\u2649",
    "Ge": "\u264A",
    "Ca": "\u264B",
    "Le": "\u264C",
    "Vi": "\u264D",
    "Li": "\u264E",
    "Sc": "\u264F",
    "Sg": "\u2650",
    "Cp": "\u2651",
    "Aq": "\u2652",
    "Pi": "\u2653",
}
ANGLE_GLYPHS = {"asc": "ASC", "dsc": "DSC", "mc": "MC", "ic": "IC"}

SIGN_LABELS = ("Ar", "Ta", "Ge", "Ca", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi")
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
ZODIAC_SYSTEM_NAMES = tuple(system.name for system in ZODIAC_SYSTEMS)
HOUSE_SYSTEM_NAMES = tuple(system.name for system in HOUSE_SYSTEMS)
PAGE_MODE_LABELS = {
    "wheel": "Wheel",
    "wheel-aspectarian": "Wheel + Aspectarian",
    "analysis": "Analysis",
    "classical-point-data": "Classical Point Data",
    "medieval-data": "Medieval Data",
    "transit-search": "Transit Search",
    "validation": "Validation",
    "reports": "Reports",
}
PAGE_MODE_NAMES = tuple(PAGE_MODE_LABELS.values())
PAGE_MODE_IDS_BY_NAME = {name: mode_id for mode_id, name in PAGE_MODE_LABELS.items()}
RIGHT_PANEL_THEME_LABELS = {"astrolabe": "Astrolabe", "classic-natal": "Classic Natal"}
RIGHT_PANEL_THEME_IDS_BY_NAME = {name: theme_id for theme_id, name in RIGHT_PANEL_THEME_LABELS.items()}
RIGHT_PANEL_THEME_NAMES = tuple(RIGHT_PANEL_THEME_LABELS.values())
WHEEL_VIEW_PRESET_LABELS = {"clean": "Clean", "full-classic": "Full Classic", "diagnostic": "Diagnostic"}
WHEEL_VIEW_PRESET_IDS_BY_NAME = {name: preset_id for preset_id, name in WHEEL_VIEW_PRESET_LABELS.items()}
WHEEL_VIEW_PRESET_NAMES = tuple(WHEEL_VIEW_PRESET_LABELS.values())
HOME_LOCATION_DEFAULT_LABEL = "Local timezone default"
DETAIL_PAGE_TABS = (
    "Summary",
    "Window",
    "Analysis",
    "Validation",
    "Reports",
    "Advisor",
    "Improve",
    "Decision",
    "Compare",
    "Diagnostics",
    "Search",
    "Focus",
    "Score",
    "Accounting",
    "Conditions",
    "Angles",
    "Point Data",
    "Medieval",
    "Rules",
    "Significators",
    "Moon",
    "House Rulers",
    "Reception",
    "Planet Condition",
    "Declination",
    "Advanced",
    "Factor Explorer",
    "Constellations",
    "Cusps",
    "Lots",
    "Nodes",
    "Timing",
    "Timeline",
    "Planets",
    "Aspects",
    "Aspectarian",
    "Aspect Strength",
    "Fixed Stars",
    "Shortlist Board",
    "Shortlist",
    "Pick Compare",
    "Pick Tools",
    "Button Health",
    "Log",
)
TOP_NAV_PAGE_TARGETS = {
    "Wheel": "Window",
    "Search": "Search",
    "Analysis": "Analysis",
    "Timeline": "Timeline",
    "Validation": "Validation",
    "Reports": "Reports",
}
TOP_NAV_SPECIAL_ACTIONS: set[str] = set()
TOP_NAV_ITEMS = ("Wheel", "Search", "Analysis", "Timeline", "Validation", "Reports")
TOP_NAV_WORKSPACE_SUMMARIES = {
    "Wheel": "Main chart wheel with selected window and right-side judgment summary.",
    "Search": "Election search workbench with filters, candidates, rejection reasons, and relax suggestions.",
    "Analysis": "Deep electional review with aspect highlights, Moon condition, rules, and validation.",
    "Timeline": "Current, local-day, and rolling next-24-hour aspect peaks.",
    "Validation": "Accuracy audit, chart settings, and manual CapricornPROMETHEUS comparison.",
    "Reports": "Readable summaries, decision sheets, shortlist tools, and export actions.",
}
RIBBON_PAGE_TARGETS = {
    "Analysis": "Analysis",
    "Search Page": "Search",
    "Advisor": "Advisor",
    "Improve": "Improve",
    "Decision": "Decision",
    "Compare": "Compare",
    "Factors": "Factor Explorer",
    "Diagnostics": "Diagnostics",
    "Aspects": "Aspects",
    "Aspect Strength": "Aspect Strength",
    "Declination": "Declination",
    "Button Health": "Button Health",
}
RIBBON_SPECIAL_ACTIONS = {
    "New Chart",
    "Show Current",
    "Find Best",
    "Save",
    "Save Report",
    "Copy",
    "Report",
    "Day Report",
    "Wheel",
    "Export Wheel",
    "Calendar",
    "Ask",
    "Calculate",
    "Transits",
    "Transits/Timeline",
    "Electional Search",
    "Out of Bounds",
    "Aspect Config",
    "Assets",
    "Shortlist",
    "Chart Data",
    "Score Audit",
    "Factor Map",
    "Cache Stats",
    "Clear Cache",
    "Health",
    "Focus Wheel",
    "Void Course",
    "Preferences",
    "Systems",
    "Bounds",
    "Lots",
    "Fixed Stars",
    "Heliacal Search",
    "Map",
}
VIEW_PAGE_TARGETS = {
    "Interpretation": "Window",
    "Analysis": "Analysis",
    "Validation": "Validation",
    "Reports": "Reports",
    "Advisor": "Advisor",
    "Improve": "Improve",
    "Decision": "Decision",
    "Compare": "Compare",
    "Search": "Search",
    "Timing": "Timing",
    "Timeline": "Timeline",
    "Angles": "Angles",
    "Aspects": "Aspects",
    "Aspectarian": "Aspectarian",
    "Aspect Strength": "Aspect Strength",
    "Point Data": "Point Data",
    "Medieval": "Medieval",
    "Conditions": "Conditions",
    "Shortlist": "Shortlist",
    "Log": "Log",
}
VIEW_PAGE_SPECIAL_ACTIONS = {"Chart Data", "Save Wheel"}
VIEW_PAGE_STRIP_ACTIONS = (
    "Interpretation",
    "Search",
    "Analysis",
    "Timeline",
    "Validation",
    "Reports",
    "Advisor",
    "Improve",
    "Decision",
    "Compare",
    "Timing",
    "Angles",
    "Aspects",
    "Aspectarian",
    "Aspect Strength",
    "Point Data",
    "Medieval",
    "Conditions",
    "Shortlist",
    "Log",
    "Chart Data",
    "Save Wheel",
)
RIBBON_GROUPS = (
    ("Transits", ("Transits/Timeline", "Search Page", "Aspects", "Aspect Strength", "Day Report", "Report")),
    ("Electional", ("Electional Search", "Void Course", "Heliacal Search", "Out of Bounds", "Find Best", "Show Current")),
    ("Utility", ("Chart Data", "Diagnostics", "Map", "Fixed Stars", "Lots", "Shortlist")),
    ("Configuration", ("Aspect Config", "Assets", "Systems", "Bounds", "Preferences", "Focus Wheel", "Clear Cache")),
)
RIBBON_COLUMNS = 2
VIEW_PAGE_QUICK_ACTIONS = ("Interpretation", "Search", "Analysis", "Timeline", "Validation")

PALETTE = {
    "app_bg": "#f3f4ee",
    "title_bar": "#26332f",
    "top_bar": "#596d66",
    "top_bar_dark": "#374842",
    "top_nav": "#596d66",
    "top_nav_hover": "#71847d",
    "top_nav_active": "#8ba09a",
    "ribbon": "#eceee6",
    "ribbon_panel": "#fbfaf1",
    "ribbon_panel_soft": "#fffdf6",
    "panel": "#f6f5ec",
    "panel_alt": "#fffdf4",
    "panel_line": "#d2d1bf",
    "panel_line_strong": "#a9ac98",
    "canvas": "#fbfaf3",
    "canvas_grid": "#eceee6",
    "chart_disc": "#f0f2ed",
    "chart_inner": "#fffefa",
    "chart_line": "#3a3a36",
    "chart_line_soft": "#7d7667",
    "chart_bezel": "#56615d",
    "chart_bezel_inner": "#d7ddd8",
    "chart_house_fill": "#fbfcf8",
    "chart_house_fill_alt": "#eef2ed",
    "chart_ring_fill": "#f8faf6",
    "chart_tick_major": "#2d2a28",
    "chart_tick_medium": "#6a665d",
    "chart_tick_minor": "#b6ae99",
    "text": "#202823",
    "muted": "#68736c",
    "accent": "#4f7c72",
    "accent_dark": "#355d53",
    "score": "#2f7568",
    "support": "#5f925e",
    "stress": "#a85261",
    "warning": "#b07832",
    "button": "#fffdf4",
    "button_hover": "#f1f4ea",
    "button_line": "#c5c8b7",
    "button_active": "#e5ebdf",
    "selected": "#e7ede2",
    "metric_bg": "#f7f6ed",
    "center_hub": "#ffffff",
    "chip": "#e9efe4",
    "chip_line": "#c8d0bd",
    "surface_shadow": "#dfe3d8",
    "sign_badge_fill": "#fffefa",
    "sign_badge_line": "#aebdb6",
    "planet_fill": "#fffefa",
    "planet_fill_angular": "#eef4ef",
    "lot_fill": "#edf2e9",
    "node_fill": "#edf1ee",
    "star_fill": "#fafbf8",
    "aspect_ring": "#aab6b0",
    "astrolabe_bg": "#f6f5ec",
    "astrolabe_panel": "#fffdf4",
    "astrolabe_line": "#b4bda8",
    "astrolabe_gold": "#4f7c72",
    "astrolabe_ink": "#202823",
    "astrolabe_muted": "#68736c",
    "surface": "#fffdf4",
    "surface_soft": "#faf8ec",
    "surface_sage": "#eef4e8",
    "surface_gold": "#fbf0d5",
    "surface_stress": "#f8e7ea",
    "surface_support": "#e8f4eb",
    "teal": "#2e7f78",
    "gold": "#b88635",
}

SIGN_COLORS = (
    "#d86f82",
    "#c9ae66",
    "#34b5b0",
    "#9bbc88",
    "#d89169",
    "#c1c2a5",
    "#3fa8b9",
    "#b66e9c",
    "#d37d74",
    "#b8af96",
    "#5ca1c7",
    "#b774aa",
)
CLASSIC_SIGN_COLORS = (
    "#d44747",
    "#c9a23a",
    "#a6c945",
    "#63bf53",
    "#3cbf3a",
    "#49cfa3",
    "#54c6df",
    "#4ab8e7",
    "#5e50d6",
    "#6d43d0",
    "#c33ab2",
    "#d24d7f",
)
CLASSIC_CONSTELLATION_FILL = "#c7c86e"
CLASSIC_PLANET_FIELD = "#a4a0f2"
CLASSIC_ASPECT_CENTER = "#ffffff"
CLASSIC_HOUSE_RING_COLORS = (
    "#c76b75",
    "#bd8063",
    "#b4aa68",
    "#93b66f",
    "#72ad72",
    "#5da188",
    "#5d97aa",
    "#6786b4",
    "#7779bd",
    "#8d72b8",
    "#a66cab",
    "#b56d8e",
)
CLASSIC_HOUSE_FIELD_COLORS = (
    "#aaa6f4",
    "#9f9af0",
)
CLASSIC_HOUSE_FIELD_LINE = "#3b3f75"
CLASSIC_WHEEL_BG = "#f8f9f5"
CLASSIC_TICK_RING = "#d9d6ef"
CLASSIC_AXIS = "#1f1f1f"
CLASSIC_HOUSE_LINE = "#262626"
CLASSIC_CENTER_LINE = "#8ea0c9"
CLASSIC_PANEL_BG = "#fffefa"
CLASSIC_PANEL_LINE = "#aebbb5"
CLASSIC_PANEL_TEXT = "#202826"
CLASSIC_PANEL_MUTED = "#66716d"
CLASSIC_PANEL_ACCENT = "#496a62"
CLASSIC_SIGN_TEXT = "#152033"
CLASSIC_SIGN_HALO = "#f5f0da"
CLASSIC_HOUSE_TEXT = "#071b56"
CLASSIC_HOUSE_HALO = "#f4f1e4"
CLASSIC_HOUSE_SPAN_TEXT = "#273268"
CLASSIC_HOUSE_SPAN_HALO = "#f8f5e8"
CLASSIC_PLANET_DEGREE = "#071b56"
CLASSIC_PLANET_RETROGRADE = "#c02020"
CLASSIC_ASPECT_SUPPORT = "#2d7fa0"
CLASSIC_ASPECT_STRESS = "#c74358"
CLASSIC_ASPECT_NEUTRAL = "#6f756b"
CLASSIC_LEFT_PANEL_WIDTH = 132
CLASSIC_RIGHT_PANEL_WIDTH = 360
CLASSIC_LEFT_WRAP = 112
CLASSIC_RIGHT_WRAP = 326
CLASSIC_PLANET_COLORS = {
    "Sun": "#e0a400",
    "Moon": "#d5d7db",
    "Mercury": "#9b7c52",
    "Venus": "#8eca45",
    "Mars": "#ff3125",
    "Jupiter": "#c6b02f",
    "Saturn": "#2134a0",
    "Uranus": "#34c4cc",
    "Neptune": "#58adef",
    "Pluto": "#795b53",
}

CONSTELLATION_COLORS = (
    "#d8e6f2",
    "#e9d7d5",
    "#e5d9b6",
    "#cde6e0",
    "#d8dfc1",
    "#ead2bb",
    "#e0d9c1",
    "#c8dfdf",
    "#ead1d8",
    "#ddd4e8",
    "#e7d0c7",
    "#d7d9d1",
    "#c8dcea",
)
ANGLE_COLORS = {
    "asc": "#097a77",
    "dsc": "#5a7688",
    "mc": "#9d641d",
    "ic": "#4d66a6",
}
WHEEL_DEFAULT_ZOOM = 0.98
WHEEL_MIN_ZOOM = 0.82
WHEEL_MAX_ZOOM = 1.18


def planet_abbreviation(name: str) -> str:
    """Return a compact planet label suitable for the chart wheel."""

    return PLANET_LABELS.get(name, name[:2].title())


def planet_glyph(name: str) -> str:
    return PLANET_GLYPHS.get(name, planet_abbreviation(name))


def sign_glyph(sign: str) -> str:
    return SIGN_GLYPHS.get(sign, sign)


def uses_classic_wheel_theme(theme_name: str) -> bool:
    return RIGHT_PANEL_THEME_IDS_BY_NAME.get(theme_name, "astrolabe") == "classic-natal"


def classic_planet_degree_text(planet: Mapping[str, object]) -> str:
    zodiac = planet.get("zodiac", {})
    if not isinstance(zodiac, Mapping) or "degree" not in zodiac or "minute" not in zodiac:
        return ""
    degree = int(zodiac.get("degree", 0) or 0)
    minute = int(zodiac.get("minute", 0) or 0)
    return f"{degree}\N{DEGREE SIGN}{minute:02d}"


def classic_position_table_text(point: Mapping[str, object]) -> str:
    zodiac = point.get("zodiac", {})
    if not isinstance(zodiac, Mapping):
        return format_position(dict(point))
    sign = sign_glyph(str(zodiac.get("sign") or ""))
    try:
        degree = int(zodiac.get("degree", 0) or 0)
        minute = int(zodiac.get("minute", 0) or 0)
    except (TypeError, ValueError):
        return format_position(dict(point))
    return f"{sign} {degree:02d}\N{DEGREE SIGN}{minute:02d}"


def classic_dignity_table_text(point: Mapping[str, object]) -> str:
    dignity = point.get("dignity")
    if not isinstance(dignity, Mapping):
        return "n/a"
    label = str(dignity.get("label") or "").strip()
    if not label:
        return "n/a"
    normalized = label.lower()
    if normalized.startswith("unavail"):
        return "n/a"
    if normalized.startswith("detriment"):
        return "Detr."
    return label[:7]


def aspect_glyph(aspect_name: object) -> str:
    if isinstance(aspect_name, Mapping):
        explicit = str(aspect_name.get("aspectGlyph") or aspect_name.get("aspectAbbreviation") or "").strip()
        if explicit:
            return explicit
        aspect_name = aspect_name.get("aspectName")
    return {
        "Conjunction": "\u260c",
        "Opposition": "\u260d",
        "Trine": "\u25b3",
        "Square": "\u25a1",
        "Sextile": "\u2736",
    }.get(str(aspect_name), str(aspect_name or "")[:2])


def lot_abbreviation(name: str) -> str:
    return {
        "Part of Fortune": "Fo",
        "Part of Spirit": "Sp",
        "Part of Eros": "Er",
        "Part of Necessity": "Ne",
        "Part of Courage": "Co",
        "Part of Victory": "Vi",
        "Part of Nemesis": "Nm",
    }.get(name, name[:2].title())


def node_abbreviation(name: str) -> str:
    return {
        "True North Node": "TN",
        "True South Node": "TS",
        "Mean North Node": "MN",
        "Mean South Node": "MS",
    }.get(name, name[:2].title())


def star_abbreviation(name: str) -> str:
    compact = {
        "Aldebaran": "Ald",
        "Algol": "Alg",
        "Regulus": "Reg",
        "Sirius": "Sir",
        "Spica": "Spi",
        "Antares": "Ant",
        "Galactic Center": "GC",
    }
    return compact.get(name, name[:3].title())


def wheel_degrees(longitude: float, ascendant_longitude: float) -> float:
    """Convert ecliptic longitude into desktop chart-wheel screen degrees."""

    return (180 + ((longitude - ascendant_longitude) % 360)) % 360


def wheel_degrees_from_xy(center_x: float, center_y: float, x: float, y: float) -> float:
    """Convert a canvas point into the same screen-degree system used by the wheel."""

    return math.degrees(math.atan2(center_y - y, x - center_x)) % 360


def midpoint_longitude(start: float, end: float) -> float:
    return (start + ((end - start) % 360) / 2) % 360


def house_label_screen_angle(cusp_longitude: float, next_cusp_longitude: float, ascendant_longitude: float) -> float:
    return midpoint_degrees(
        wheel_degrees(cusp_longitude, ascendant_longitude),
        wheel_degrees(next_cusp_longitude, ascendant_longitude),
    )


def house_span_rows(snapshot: Mapping[str, object]) -> list[dict[str, object]]:
    cusps = snapshot.get("houseCusps", [])
    if not isinstance(cusps, list):
        return []
    ordered = sorted(
        [cusp for cusp in cusps if isinstance(cusp, Mapping) and "house" in cusp and "longitude" in cusp],
        key=lambda cusp: int(cusp["house"]),
    )
    rows: list[dict[str, object]] = []
    for index, cusp in enumerate(ordered):
        next_cusp = ordered[(index + 1) % len(ordered)] if ordered else None
        if next_cusp is None:
            continue
        longitude = float(cusp["longitude"])
        next_longitude = float(next_cusp["longitude"])
        span = (next_longitude - longitude) % 360
        rows.append(
            {
                "house": int(cusp["house"]),
                "longitude": longitude,
                "nextLongitude": next_longitude,
                "span": span,
                "source": str(cusp.get("source") or "native"),
            }
        )
    return rows


def house_geometry_summary(snapshot: Mapping[str, object]) -> str:
    rows = house_span_rows(snapshot)
    if not rows:
        return "House geometry: cusps unavailable."
    house_system = snapshot.get("houseSystem")
    house_name = getattr(house_system, "name", "House system")
    sources = sorted({str(row["source"]) for row in rows})
    spans = [float(row["span"]) for row in rows]
    min_span = min(spans)
    max_span = max(spans)
    spread = max_span - min_span
    mode = "unequal quadrant/accounted houses" if spread >= 1.0 else "near-equal house spans"
    return f"{house_name}: {mode}; spans {min_span:.1f}-{max_span:.1f} deg; source {', '.join(sources)}."


def house_span_label(span: object) -> str:
    try:
        return f"{float(span):.1f}deg"
    except (TypeError, ValueError):
        return ""


def house_geometry_lines(snapshot: Mapping[str, object]) -> list[str]:
    rows = house_span_rows(snapshot)
    if not rows:
        return ["House Geometry", "- House cusps are unavailable."]
    return [
        "House Geometry",
        f"- {house_geometry_summary(snapshot)}",
        "- Wide and narrow houses come from the selected house system, latitude, time, and ASC/MC geometry.",
        "",
        "House  Cusp longitude  Span to next  Source",
        *[
            f"H{int(row['house']):02d}    {float(row['longitude']):7.2f} deg      {float(row['span']):5.2f} deg    {row['source']}"
            for row in rows
        ],
    ]


def house_geometry_insight_lines(snapshot: Mapping[str, object]) -> list[str]:
    rows = house_span_rows(snapshot)
    if not rows:
        return [
            "House geometry unavailable.",
            "Calculate a chart with house cusps before reviewing house width.",
        ]
    house_system = snapshot.get("houseSystem")
    house_name = getattr(house_system, "name", "House system")
    spans = [float(row["span"]) for row in rows]
    min_span = min(spans)
    max_span = max(spans)
    spread = max_span - min_span

    def _house_pair(row: Mapping[str, object]) -> str:
        return f"H{int(row['house']):02d} {house_span_label(row['span'])}"

    widest = ", ".join(_house_pair(row) for row in sorted(rows, key=lambda row: float(row["span"]), reverse=True)[:2])
    narrowest = ", ".join(_house_pair(row) for row in sorted(rows, key=lambda row: float(row["span"]))[:2])
    lines = [
        f"{house_name}: {min_span:.1f}-{max_span:.1f}deg house spans.",
        f"Widest: {widest}.",
        f"Narrowest: {narrowest}.",
    ]
    if spread >= 1.0:
        lines.append("Uneven houses are expected here: ASC/MC, latitude, and time project the local sky onto the ecliptic.")
        lines.append("Signs are the zodiac ring; houses are sky sectors. They do not have to match sign sizes.")
    else:
        lines.append("This chart is near equal-house visually; house widths are not strongly distorted.")
    return lines


def button_health_lines(available_pages: tuple[str, ...] | list[str] | None = None) -> list[str]:
    pages = set(available_pages or DETAIL_PAGE_TABS)
    ribbon_labels = [label for _group, labels in RIBBON_GROUPS for label in labels]
    missing_top_actions = [label for label in TOP_NAV_ITEMS if label not in TOP_NAV_PAGE_TARGETS and label not in TOP_NAV_SPECIAL_ACTIONS]
    missing_ribbon_actions = [label for label in ribbon_labels if label not in RIBBON_PAGE_TARGETS and label not in RIBBON_SPECIAL_ACTIONS]
    missing_view_actions = [label for label in VIEW_PAGE_STRIP_ACTIONS if label not in VIEW_PAGE_TARGETS and label not in VIEW_PAGE_SPECIAL_ACTIONS]
    missing_top_pages = [target for target in TOP_NAV_PAGE_TARGETS.values() if target not in pages]
    missing_ribbon_pages = [target for target in RIBBON_PAGE_TARGETS.values() if target not in pages]
    missing_view_pages = [target for target in VIEW_PAGE_TARGETS.values() if target not in pages]
    problems = missing_top_actions + missing_ribbon_actions + missing_view_actions + missing_top_pages + missing_ribbon_pages + missing_view_pages

    lines = [
        "Button Health",
        f"Top nav buttons: {len(TOP_NAV_ITEMS)}",
        f"Ribbon buttons: {len(ribbon_labels)}",
        f"View page shortcuts: {len(VIEW_PAGE_STRIP_ACTIONS)}",
        f"Detail pages: {len(pages)}",
        "",
    ]
    if not problems:
        lines.append("- All visible top, ribbon, and page-strip buttons have wired actions and available page targets.")
    else:
        lines.append("- Button wiring needs attention.")
        if missing_top_actions:
            lines.append(f"- Top nav labels without actions: {', '.join(missing_top_actions)}.")
        if missing_ribbon_actions:
            lines.append(f"- Ribbon labels without actions: {', '.join(missing_ribbon_actions)}.")
        if missing_view_actions:
            lines.append(f"- Page-strip labels without actions: {', '.join(missing_view_actions)}.")
        if missing_top_pages:
            lines.append(f"- Top nav targets missing tabs: {', '.join(missing_top_pages)}.")
        if missing_ribbon_pages:
            lines.append(f"- Ribbon targets missing tabs: {', '.join(missing_ribbon_pages)}.")
        if missing_view_pages:
            lines.append(f"- Page-strip targets missing tabs: {', '.join(missing_view_pages)}.")
    return lines


def constellation_arc_segments() -> list[dict[str, object]]:
    segments = []
    for index, span in enumerate(ECLIPTIC_CONSTELLATION_SPANS):
        start = float(span["start"])
        end = float(span["end"])
        extent = (end - start) % 360 or 360.0
        segments.append(
            {
                "id": span["id"],
                "name": span["name"],
                "abbreviation": span["abbreviation"],
                "start": start,
                "end": end,
                "extent": extent,
                "midpoint": (start + extent / 2) % 360,
                "color": CONSTELLATION_COLORS[index % len(CONSTELLATION_COLORS)],
            }
        )
    return segments


def zodiac_arc_segments(system_id_or_name: str | None) -> list[dict[str, object]]:
    system = get_zodiac_system(system_id_or_name)
    if system.mode == "constellational":
        segments: list[dict[str, object]] = []
        for index, segment in enumerate(constellation_arc_segments()):
            segment_id = str(segment.get("id", "")).lower()
            sign_label = CONSTELLATION_SIGN_LABELS.get(segment_id)
            is_ophiuchus = segment_id == "ophiuchus"
            segments.append(
                {
                    **segment,
                    "label": sign_glyph(sign_label) if sign_label else "",
                    "fallbackLabel": str(segment.get("abbreviation") or ""),
                    "kind": "true-13-sign",
                    "isOphiuchus": is_ophiuchus,
                    "color": CLASSIC_SIGN_COLORS[index % len(CLASSIC_SIGN_COLORS)],
                }
            )
        return segments
    return [
        {
            "id": sign.lower(),
            "name": sign,
            "abbreviation": sign,
            "start": index * 30.0,
            "end": ((index + 1) * 30.0) % 360,
            "extent": 30.0,
            "midpoint": index * 30.0 + 15.0,
            "color": CLASSIC_SIGN_COLORS[index],
            "label": sign_glyph(sign),
            "kind": "sign",
        }
        for index, sign in enumerate(SIGN_LABELS)
    ]


def _polar(center_x: float, center_y: float, radius: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    return center_x + math.cos(radians) * radius, center_y - math.sin(radians) * radius


def _arc_points(cx: float, cy: float, radius: float, start: float, end: float, step: float = 6.0) -> list[float]:
    span = (end - start) % 360
    steps = max(2, int(span / step) + 1)
    points: list[float] = []
    for index in range(steps + 1):
        angle = (start + span * index / steps) % 360
        x, y = _polar(cx, cy, radius, angle)
        points.extend((x, y))
    return points


def body_marker_offsets(
    longitudes: list[float],
    *,
    compact: bool,
    crowd_threshold: float | None = None,
    angle_step: float | None = None,
    radial_step: float | None = None,
) -> list[tuple[float, float]]:
    """Return per-body angular and radial offsets for crowded wheel clusters."""

    if not longitudes:
        return []

    crowd_threshold = crowd_threshold if crowd_threshold is not None else (8.0 if compact else 10.0)
    angle_step = angle_step if angle_step is not None else (4.0 if compact else 5.0)
    radial_step = radial_step if radial_step is not None else (9.0 if compact else 11.0)

    ordered = sorted(
        [{"index": index, "longitude": longitude % 360} for index, longitude in enumerate(longitudes)],
        key=lambda item: float(item["longitude"]),
    )
    clusters: list[list[dict[str, float | int]]] = [[ordered[0]]]
    for item in ordered[1:]:
        previous = clusters[-1][-1]
        gap = (float(item["longitude"]) - float(previous["longitude"])) % 360
        if gap <= crowd_threshold:
            clusters[-1].append(item)
        else:
            clusters.append([item])
    if len(clusters) > 1:
        wrap_gap = (float(clusters[0][0]["longitude"]) + 360 - float(clusters[-1][-1]["longitude"])) % 360
        if wrap_gap <= crowd_threshold:
            clusters[0] = clusters[-1] + clusters[0]
            clusters.pop()

    offsets: list[tuple[float, float]] = [(0.0, 0.0) for _ in longitudes]
    for cluster in clusters:
        center = (len(cluster) - 1) / 2
        for position, item in enumerate(cluster):
            centered = position - center
            angular_offset = centered * angle_step
            radial_offset = (abs(centered) + (0.35 if len(cluster) > 1 else 0.0)) * radial_step
            offsets[int(item["index"])] = (angular_offset, radial_offset)
    return offsets


def planet_marker_offsets(longitudes: list[float], *, compact: bool) -> list[tuple[float, float]]:
    return body_marker_offsets(longitudes, compact=compact)


def circular_distance_degrees(first: float, second: float) -> float:
    delta = abs((first - second + 180) % 360 - 180)
    return float(delta)


def midpoint_degrees(first: float, second: float) -> float:
    delta = ((second - first + 180) % 360) - 180
    return (first + delta / 2) % 360


def aspect_curve_points(
    cx: float,
    cy: float,
    radius: float,
    angle_a: float,
    angle_b: float,
    *,
    compact: bool,
    lane_index: int = 0,
) -> list[float]:
    span = circular_distance_degrees(angle_a, angle_b)
    midpoint = midpoint_degrees(angle_a, angle_b)
    lane_offset = (-1.5 + (lane_index % 4)) * (4.0 if compact else 5.5)
    control_radius = max(radius * 0.12, radius * (0.31 - min(span, 180.0) / 540.0) - (lane_index % 3) * radius * 0.03)
    x1, y1 = _polar(cx, cy, radius, angle_a)
    cx1, cy1 = _polar(cx, cy, control_radius, midpoint + lane_offset)
    x2, y2 = _polar(cx, cy, radius, angle_b)
    return [x1, y1, cx1, cy1, x2, y2]


def shift_local_datetime_minutes(date_text: str, time_text: str, timezone_name: str, minutes: int) -> tuple[str, str]:
    local_time = datetime.strptime(f"{date_text} {normalize_time_text(time_text)}", "%Y-%m-%d %H:%M")
    zoned = local_time.replace(tzinfo=ZoneInfo(timezone_name or "UTC"))
    shifted = zoned + timedelta(minutes=minutes)
    return shifted.strftime("%Y-%m-%d"), shifted.strftime("%H:%M")


def shift_local_datetime(date_text: str, time_text: str, timezone_name: str, hours: int) -> tuple[str, str]:
    return shift_local_datetime_minutes(date_text, time_text, timezone_name, hours * 60)


def window_score_color(score: int) -> str:
    if score >= 86:
        return "#e6f6ef"
    if score >= 76:
        return "#eef7f5"
    if score >= 60:
        return "#fff5df"
    return "#f9e7eb"


def score_band_label(score: int) -> str:
    if score >= 86:
        return "Prime"
    if score >= 76:
        return "Strong"
    if score >= 60:
        return "Workable"
    return "Caution"


def shortlist_metric_band(metric: str, value: int) -> tuple[str, str]:
    if metric == "volatility":
        if value <= 18:
            return "#e8f7ef", PALETTE["support"]
        if value <= 30:
            return "#eef7f5", PALETTE["accent"]
        if value <= 45:
            return "#fff5df", PALETTE["warning"]
        return "#fae7eb", PALETTE["stress"]
    if value >= 86:
        return "#e8f7ef", PALETTE["support"]
    if value >= 72:
        return "#eef7f5", PALETTE["accent"]
    if value >= 58:
        return "#fff5df", PALETTE["warning"]
    return "#fae7eb", PALETTE["stress"]


def shortlist_score_band(score: int) -> tuple[str, str]:
    if score >= 86:
        return "#e8f7ef", PALETTE["support"]
    if score >= 76:
        return "#eef7f5", PALETTE["accent"]
    if score >= 60:
        return "#fff5df", PALETTE["warning"]
    return "#fae7eb", PALETTE["stress"]


def fixed_star_contact_count(snapshot: dict[str, object]) -> int:
    contacts = snapshot.get("fixedStarContacts", [])
    return len(contacts) if isinstance(contacts, list) else 0


def summary_chip_lines(snapshot: dict[str, object], point_set_name: str = "") -> list[str]:
    phase = snapshot.get("lunarPhase", {})
    phase_name = phase.get("name", "Moon phase unknown") if isinstance(phase, dict) else "Moon phase unknown"
    planetary_hour = snapshot.get("planetaryHour", {})
    hour_ruler = planetary_hour.get("hourRuler", "n/a") if isinstance(planetary_hour, dict) and planetary_hour.get("available") else "n/a"
    zodiac_system = snapshot.get("zodiacSystem")
    zodiac_name = getattr(zodiac_system, "name", "Zodiac n/a")
    house_system = snapshot.get("houseSystem")
    house_name = getattr(house_system, "name", "Houses n/a")
    return [
        f"Moon: {phase_name}",
        f"Hour: {hour_ruler}",
        f"Points: {point_set_name or '10 Planets'}",
        f"Zodiac: {zodiac_name}",
        f"Houses: {house_name}",
    ]


def selection_offset_label(input_snapshot: dict[str, object], selected_window: dict[str, object]) -> str:
    try:
        delta_minutes = round((selected_window["date"] - input_snapshot["date"]).total_seconds() / 60)
    except (KeyError, TypeError, AttributeError):
        return "Offset unavailable"
    if delta_minutes == 0:
        return "Selected equals search start"
    sign = "+" if delta_minutes > 0 else "-"
    minutes = abs(int(delta_minutes))
    hours, remaining_minutes = divmod(minutes, 60)
    if hours and remaining_minutes:
        return f"Selected {sign}{hours}h {remaining_minutes}m from start"
    if hours:
        return f"Selected {sign}{hours}h from start"
    return f"Selected {sign}{remaining_minutes}m from start"


def compact_time_label(snapshot: dict[str, object]) -> str:
    text = str(snapshot.get("formattedTime", "time unavailable"))
    return text.replace(", 2026, ", " ").replace(", 2027, ", " ").replace(", ", " ")


def location_summary(location: LocationPreset | None) -> str:
    if not location:
        return "Location waiting"
    return f"{location.name} | {location.timezone} | {location.latitude:.3f}, {location.longitude:.3f}"


def _compact_position_lookup(snapshot: dict[str, object]) -> dict[str, dict[str, object]]:
    positions = snapshot.get("positions", [])
    if not isinstance(positions, list):
        return {}
    return {
        str(planet.get("name")): dict(planet)
        for planet in positions
        if isinstance(planet, dict) and planet.get("name")
    }


def _compact_angle_sign(snapshot: dict[str, object], angle_id: str, fallback_house: int) -> str:
    angles = snapshot.get("angles", [])
    if isinstance(angles, list):
        for angle in angles:
            if not isinstance(angle, dict) or angle.get("id") != angle_id:
                continue
            zodiac = angle.get("zodiac")
            if isinstance(zodiac, dict) and zodiac.get("sign"):
                return str(zodiac.get("sign"))
    cusps = snapshot.get("houseCusps", [])
    if isinstance(cusps, list):
        for cusp in cusps:
            if not isinstance(cusp, dict) or cusp.get("house") != fallback_house:
                continue
            zodiac = cusp.get("zodiac")
            if isinstance(zodiac, dict) and zodiac.get("sign"):
                return str(zodiac.get("sign"))
    return ""


def _compact_lord_line(label: str, sign: str, ruler: str, positions_by_name: dict[str, dict[str, object]]) -> str:
    planet = positions_by_name.get(ruler)
    if not planet:
        return f"{label}: {sign or 'n/a'} / {ruler or 'n/a'} not visible"
    dignity = planet.get("dignity")
    dignity_label = str(dignity.get("label", "Peregrine")) if isinstance(dignity, dict) else "dignity n/a"
    return f"{label}: {sign or 'n/a'} / {ruler} H{planet.get('house', 'n/a')} {dignity_label}"


def compact_judgment_lines(snapshot: dict[str, object]) -> list[str]:
    """Compact astrolabe-panel judgment summary for the desktop right rail."""

    aspect_lines = strongest_aspect_analysis_lines(snapshot)
    strongest = "Strongest: no selected major aspect"
    if len(aspect_lines) > 1:
        strongest = "Strongest: " + aspect_lines[1].lstrip("- ")
    if len(aspect_lines) > 2:
        strongest += " " + aspect_lines[2].lstrip("- ")
    positions = _compact_position_lookup(snapshot)
    asc_sign = _compact_angle_sign(snapshot, "asc", 1)
    tenth_sign = _compact_angle_sign(snapshot, "mc", 10)
    asc_lord = RULERS.get(asc_sign, "")
    tenth_lord = RULERS.get(tenth_sign, "")
    reasons = [line.lstrip("- ") for line in score_reason_lines(snapshot)[:3]]
    return [
        strongest,
        _compact_lord_line("ASC lord", asc_sign, asc_lord, positions),
        _compact_lord_line("10th lord", tenth_sign, tenth_lord, positions),
        "Top reasons: " + ("; ".join(reasons) if reasons else "No score reasons available."),
    ]


def diagnostic_metric_value(window: Mapping[str, object], metric: str, fallback: object = "--") -> object:
    breakdown = window.get("scoreBreakdown", {})
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, Mapping) else {}
    value = diagnostics.get(metric, {}) if isinstance(diagnostics, Mapping) else {}
    if isinstance(value, Mapping):
        return value.get("score", fallback)
    return fallback


def candidate_metric_badges(window: Mapping[str, object]) -> list[tuple[str, str]]:
    aspects_value = window.get("detectedAspects", [])
    aspects = aspects_value if isinstance(aspects_value, list) else []
    support = sum(1 for aspect in aspects if isinstance(aspect, Mapping) and aspect.get("tone") == "support")
    stress = sum(1 for aspect in aspects if isinstance(aspect, Mapping) and aspect.get("tone") == "stress")
    breakdown = window.get("scoreBreakdown", {})
    fit_matches = int(breakdown.get("objectiveMatches", 0)) if isinstance(breakdown, Mapping) else 0
    moon_condition = window.get("moonCondition", {})
    void_state = {}
    if isinstance(moon_condition, Mapping):
        void_state = moon_condition.get("voidOfCourse", {}) if isinstance(moon_condition.get("voidOfCourse"), Mapping) else {}
    moon_label = "Moon OK"
    moon_tone = "support"
    if void_state.get("isVoid") is True:
        moon_label = "Moon Void"
        moon_tone = "stress"
    elif not void_state:
        moon_label = "Moon ?"
        moon_tone = "neutral"
    positions_value = window.get("positions", [])
    positions = positions_value if isinstance(positions_value, list) else []
    angular_names = {
        str(position.get("name"))
        for position in positions
        if isinstance(position, Mapping) and position.get("isAngular")
    }
    benefic_label = "Ang+ Yes" if angular_names.intersection({"Venus", "Jupiter"}) else "Ang+ No"
    malefic_label = "Malefic Ang" if angular_names.intersection({"Mars", "Saturn"}) else "Malefic Clear"
    badges = [
        (f"Conf {diagnostic_metric_value(window, 'confidence')}", "confidence"),
        (f"Clean {diagnostic_metric_value(window, 'cleanliness')}", "cleanliness"),
        (f"Vol {diagnostic_metric_value(window, 'volatility')}", "volatility"),
        (f"Fit {fit_matches}", "fit"),
        (f"+{support} / !{stress}", "balance"),
        (moon_label, moon_tone),
        (benefic_label, "support" if "Yes" in benefic_label else "neutral"),
        (malefic_label, "stress" if "Ang" in malefic_label and "Clear" not in malefic_label else "support"),
    ]
    stage = str(window.get("searchStage") or "").strip()
    resolution = window.get("searchResolutionMinutes")
    if stage:
        stage_label = f"{resolution}m refined" if stage.lower() == "refined" and resolution else stage.title()
        badges.append((stage_label, "stage"))
    return badges


def candidate_board_summary(
    windows: list[dict[str, object]],
    *,
    evaluated_count: int = 0,
    search_mode: str = "",
    selected_index: int = -1,
    displayed_source: str = "",
) -> str:
    count = len(windows)
    result_label = f"{count} candidate{'s' if count != 1 else ''}"
    evaluated_label = f"{evaluated_count or count} evaluated"
    mode_label = (search_mode or "balanced").replace("-", " ").title()
    if selected_index >= 0 and count:
        selected_label = f"Selected #{selected_index + 1}"
    else:
        selected_label = "Input chart" if displayed_source == "input chart" else "No selection"
    return f"{result_label} | {evaluated_label} | {mode_label} | {selected_label}"


def left_status_chip_lines(
    date_text: str,
    time_text: str,
    location_name: str,
    timezone_name: str,
    zodiac_system: str,
    house_system: str,
    search_mode: str,
    validation_text: str,
) -> tuple[str, str, str, str, str]:
    date_value = date_text.strip() or "Date waiting"
    time_value = time_text.strip() or "Time waiting"
    location = location_name.strip() or "Location waiting"
    timezone = timezone_name.strip() or "Timezone waiting"
    zodiac = zodiac_system.strip() or "Zodiac waiting"
    houses = house_system.strip() or "Houses waiting"
    mode = search_mode.strip() or "Balanced"
    validation = validation_text.strip() or "Validation: waiting"
    return (
        f"Time: {date_value} {time_value}",
        f"{location} | {timezone}",
        f"{zodiac} / {houses}",
        f"Search: {mode}",
        validation,
    )


def workflow_next_step_lines(
    *,
    has_chart: bool,
    candidate_count: int,
    selected_index: int,
    displayed_source: str,
    has_rejections: bool = False,
) -> tuple[str, str, str]:
    if not has_chart:
        return (
            "Next: show the current chart",
            "Confirm date, time, location, zodiac, and houses, then press Show Current.",
            "This gives you a stable baseline before searching.",
        )
    if candidate_count <= 0:
        if has_rejections:
            return (
                "Next: loosen blocked filters",
                "Open Search Page to review rejection reasons, then relax the tightest blocker.",
                "The current chart stays visible while you tune the search.",
            )
        return (
            "Next: find candidate windows",
            "Press Find Best or Electional Search to scan the selected time range.",
            "Candidates will appear on the right board for explicit selection.",
        )
    if selected_index < 0 or displayed_source == "input chart":
        return (
            "Next: pick a candidate",
            f"{candidate_count} candidate window{'s' if candidate_count != 1 else ''} ready. Click a card to draw it on the wheel.",
            "Double-click a card when you want to use that exact time.",
        )
    return (
        f"Next: decide on window #{selected_index + 1}",
        "Review Analysis, Timeline, and House Geometry, then Shortlist or Use Selected Time.",
        "Shortlisted windows become easier to compare and export.",
    )


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
    value_pattern = re.compile(rf"\b(?P<sign>{sign_pattern})\b\s*(?P<degree>\d{{1,2}})(?:\s*(?:deg|d|°|:|'|\s)\s*(?P<minute>\d{{1,2}}))?", re.IGNORECASE)
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
        "maxDeltaDegrees": max_delta,
        "status": status,
    }


def format_manual_validation_comparison(result: Mapping[str, object] | None) -> list[str]:
    if not isinstance(result, Mapping) or not result:
        return ["Manual comparison not run yet.", "Paste CapricornPROMETHEUS values on the Validation page and press Compare."]
    max_delta = result.get("maxDeltaDegrees")
    lines = [
        f"Source: {result.get('source', 'CapricornPROMETHEUS')}",
        f"Status: {result.get('status', 'n/a')}",
        f"Parsed rows: {int(result.get('parsedCount', 0) or 0)}",
    ]
    if max_delta is not None:
        lines.append(f"Max delta: {float(max_delta):.4f} deg")
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


def validation_workbench_lines(snapshot: Mapping[str, object], location: object | None, manual_result: Mapping[str, object] | None = None) -> list[str]:
    accuracy = snapshot.get("accuracyAudit", {})
    lines = ["Accuracy Validation"]
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


def timeline_item_display(item: Mapping[str, object]) -> dict[str, object]:
    label = str(item.get("label") or "Aspect")
    bodies = item.get("bodies", [])
    body_names = [str(body) for body in bodies] if isinstance(bodies, list) else []
    tone = str(item.get("tone") or "mixed")
    tone_label = "Support" if tone == "support" else "Stress" if tone == "stress" else "Mixed"
    phase = str(item.get("phaseLabel") or ("Applying" if item.get("isApplying") else "Separating"))
    orb = str(item.get("orbText") or "orb n/a")
    peak = str(item.get("perfectsAtText") or item.get("timeToExactText") or "exact time n/a")
    time_text = str(item.get("formattedTime") or "")
    strength = item.get("strength")
    try:
        strength_text = f"{float(strength):.1f}"
    except (TypeError, ValueError):
        strength_text = "--"
    return {
        "time": time_text or "time n/a",
        "label": label,
        "tone": tone,
        "toneLabel": tone_label,
        "orb": orb,
        "phase": phase,
        "peak": peak,
        "strength": strength_text,
        "bodies": body_names,
    }


def timeline_visual_rows(
    highlights: Mapping[str, object] | None,
    *,
    key: str = "timelineByTime",
    limit: int = 12,
) -> list[dict[str, object]]:
    if not highlights:
        return []
    items = highlights.get(key)
    if not isinstance(items, list):
        return []
    rows: list[dict[str, object]] = []
    for item in items[:limit]:
        if isinstance(item, Mapping):
            rows.append(timeline_item_display(item))
    return rows


def analysis_metric_cards(snapshot: Mapping[str, object], windows: list[dict[str, object]] | None = None) -> list[tuple[str, str, str, str]]:
    breakdown = snapshot.get("scoreBreakdown", {})
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, Mapping) else {}
    aspects = snapshot.get("detectedAspects", [])
    positions = snapshot.get("positions", [])
    rule_evaluations = snapshot.get("ruleEvaluations", {})
    rules = rule_evaluations.get("rules", []) if isinstance(rule_evaluations, Mapping) else []
    support = sum(1 for aspect in aspects if isinstance(aspect, Mapping) and aspect.get("tone") == "support")
    stress = sum(1 for aspect in aspects if isinstance(aspect, Mapping) and aspect.get("tone") == "stress")
    angular = sum(1 for planet in positions if isinstance(planet, Mapping) and planet.get("isAngular"))

    def diagnostic_card(key: str, label: str, tone: str) -> tuple[str, str, str, str]:
        value = diagnostics.get(key, {}) if isinstance(diagnostics, Mapping) else {}
        if isinstance(value, Mapping):
            score = str(value.get("score", "--"))
            note = str(value.get("summary") or value.get("band") or "No diagnostic summary.")
        else:
            score = "--"
            note = "Diagnostic unavailable."
        return (label, score, note, tone)

    return [
        ("Score", str(snapshot.get("score", "--")), str(snapshot.get("note") or snapshot.get("title") or "Current electional score."), "score"),
        diagnostic_card("confidence", "Confidence", "support"),
        diagnostic_card("cleanliness", "Cleanliness", "support"),
        diagnostic_card("volatility", "Volatility", "warning"),
        ("Support", str(support), "Selected supportive aspects in orb.", "support"),
        ("Stress", str(stress), "Selected stressful aspects in orb.", "stress"),
        ("Angular", str(angular), "Visible bodies near chart angles.", "neutral"),
        ("Rules", str(len(rules) if isinstance(rules, list) else 0), f"{len(windows or [])} candidate windows in the current search.", "neutral"),
    ]


def analysis_notice_lines(
    snapshot: Mapping[str, object],
    rejection_summary: Mapping[str, object] | None,
    location: object | None = None,
) -> list[str]:
    lines = [line.lstrip("- ") for line in validation_summary_lines(snapshot, location)]
    if not snapshot.get("traditionalRulesEnabled", True):
        lines.append("True 13-Sign mode: traditional dignity/rulership scoring is unavailable.")
    summary = rejection_summary or {}
    top_reasons = summary.get("topReasons", [])
    if isinstance(top_reasons, list) and top_reasons:
        lines.append("Top rejected-window reasons: " + "; ".join(f"{reason} ({count})" for reason, count in top_reasons[:3]) + ".")
    suggestions = summary.get("suggestedRelaxations", [])
    if isinstance(suggestions, list) and suggestions:
        lines.append("Suggested relaxation: " + str(suggestions[0]))
    return lines


class ElectionalDesktopApp:
    """Tkinter desktop UI that talks directly to the Python electional engine."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"Electional Software - {APP_BUILD_LABEL}")
        self.root.geometry("1920x1080")
        self.root.minsize(1280, 800)

        self.user_locations = load_user_locations()
        self.hidden_builtin_location_ids = load_hidden_builtin_location_ids()
        self.home_location_name = load_home_location_name()
        self.location_names = combined_visible_location_names(self.user_locations, self.hidden_builtin_location_ids)
        self.locations_by_name = self._location_map()
        self.presets_by_name = {preset.name: preset for preset in ELECTIONAL_PRESETS}
        self.aspect_vars: dict[str, tk.BooleanVar] = {}
        self.current_location: LocationPreset | None = None
        self.input_snapshot: dict[str, object] | None = None
        self.current_windows: list[dict[str, object]] = []
        self.current_aspect_highlights: dict[str, object] = {}
        self.current_search_summary = ""
        self.current_rejection_summary: dict[str, object] = {}
        self.current_searched_window_count = 0
        self.selected_window: dict[str, object] | None = None
        self.selected_window_index = 0
        self.displayed_chart_source = "input chart"
        self.window_cards: list[tk.Frame] = []
        self.shortlist = load_shortlist()
        self.shortlist_compare_a_id: str | None = self.shortlist[0]["id"] if self.shortlist else None
        self.shortlist_compare_b_id: str | None = self.shortlist[1]["id"] if len(self.shortlist) > 1 else None
        self._resize_job: str | None = None
        self.focus_mode = False
        self.event_log: list[str] = []
        self.session_state = clean_session_state(load_session_state())
        self.metric_vars: dict[str, tk.StringVar] = {}
        self.left_status_chip_vars: list[tk.StringVar] = []
        self.shortlist_board_cards: list[tk.Frame] = []
        self.focused_body_name: str | None = None
        self.focused_body_kind: str | None = None
        self.focused_aspect_bodies: set[str] = set()
        self.analysis_report_text_cache = ""
        self.timeline_report_text_cache = ""
        self.search_workbench_run_count = 0
        self.search_workbench_last_action = "waiting"
        self._moon_drag_state: dict[str, object] = {}
        self._wheel_drag_geometry: dict[str, float] = {}
        manual_validation = self.session_state.get("manual_validation_comparison")
        self.manual_validation_result = manual_validation if isinstance(manual_validation, dict) else {}
        self.manual_validation_input_cache = str(self.manual_validation_result.get("inputText") or "")
        self.manual_validation_source_var = tk.StringVar(value=str(self.manual_validation_result.get("source") or "CapricornPROMETHEUS"))
        self.top_nav_buttons: dict[str, tk.Button] = {}
        self.active_top_nav_label: str | None = None
        display_options = self.session_state.get("display_options", {})
        self.aspect_profiles = load_aspect_profiles()
        self.active_aspect_profile = aspect_profile_by_id(
            str(self.session_state.get("active_aspect_profile") or DEFAULT_ASPECT_PROFILE_ID),
            self.aspect_profiles,
        )
        self.aspect_profile_var = tk.StringVar(value=self.active_aspect_profile.name)
        self.show_aspects_var = tk.BooleanVar(value=bool(display_options.get("show_aspects", True)))
        self.show_lots_var = tk.BooleanVar(value=bool(display_options.get("show_lots", True)))
        self.show_nodes_var = tk.BooleanVar(value=bool(display_options.get("show_nodes", True)))
        self.show_fixed_stars_var = tk.BooleanVar(value=bool(display_options.get("show_fixed_stars", True)))
        self.show_score_overlay_var = tk.BooleanVar(value=bool(display_options.get("show_score_overlay", True)))
        self.compact_wheel_var = tk.BooleanVar(value=bool(display_options.get("compact_wheel", False)))
        self.point_set_var = tk.StringVar(value=get_point_set(display_options.get("point_set")).name)
        self.page_mode_var = tk.StringVar(value=PAGE_MODE_LABELS.get(str(display_options.get("page_mode") or "wheel"), "Wheel"))
        self.view_page_action_var = tk.StringVar(value="Interpretation")
        self.right_panel_theme_var = tk.StringVar(value=RIGHT_PANEL_THEME_LABELS.get(str(display_options.get("right_panel_theme") or "classic-natal"), "Classic Natal"))
        self.wheel_view_preset_var = tk.StringVar(value=WHEEL_VIEW_PRESET_LABELS.get(str(display_options.get("wheel_view_preset") or "full-classic"), "Full Classic"))
        self.wheel_zoom = float(display_options.get("wheel_zoom", WHEEL_DEFAULT_ZOOM))

        self._configure_style()
        self._build_layout()
        self._apply_current_theme()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind("<Alt-Left>", lambda _event: self._select_relative_window(-1))
        self.root.bind("<Alt-Right>", lambda _event: self._select_relative_window(1))
        self.root.bind("<F11>", lambda _event: self._toggle_focus_mode())
        self.calculate(show_input_chart=True)
        self._apply_page_mode(self._current_page_mode_id(), save=False)

    def _configure_style(self) -> None:
        self.root.configure(bg=PALETTE["app_bg"])
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=PALETTE["panel"])
        style.configure("Top.TFrame", background=PALETTE["top_bar"])
        style.configure("Ribbon.TFrame", background=PALETTE["ribbon"])
        style.configure("Workbench.TFrame", background=PALETTE["app_bg"])
        style.configure("Panel.TFrame", background=PALETTE["panel"], relief="flat", borderwidth=0)
        style.configure("Card.TFrame", background=PALETTE["panel_alt"], relief="flat", borderwidth=0)
        style.configure("RibbonPanel.TFrame", background=PALETTE["ribbon_panel"], relief="flat", borderwidth=0)
        style.configure("Panel.TLabelframe", background=PALETTE["panel_alt"], bordercolor=PALETTE["panel_line"], relief="solid", borderwidth=1)
        style.configure("Panel.TLabelframe.Label", background=PALETTE["panel_alt"], foreground=PALETTE["accent_dark"], font=("Georgia", 10, "bold"))
        style.configure("Ribbon.TLabelframe", background=PALETTE["ribbon_panel"], bordercolor=PALETTE["panel_line"], relief="flat")
        style.configure("Ribbon.TLabelframe.Label", background=PALETTE["ribbon_panel"], foreground=PALETTE["muted"], font=("Georgia", 8, "bold"))
        style.configure("TNotebook", background=PALETTE["panel"], borderwidth=0)
        style.configure("TNotebook.Tab", background="#ececdf", foreground=PALETTE["muted"], padding=(12, 7), font=("Georgia", 8, "bold"))
        style.map("TNotebook.Tab", background=[("selected", PALETTE["panel_alt"]), ("active", "#f7f5e9")], foreground=[("selected", PALETTE["accent_dark"]), ("active", PALETTE["text"])])
        style.configure("Title.TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Georgia", 18, "bold"))
        style.configure("Small.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
        style.configure("Accent.TLabel", background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Georgia", 9, "bold"))
        style.configure("Score.TLabel", background=PALETTE["panel_alt"], foreground=PALETTE["score"], font=("Georgia", 32, "bold"))
        style.configure("TButton", background=PALETTE["button"], foreground=PALETTE["text"], padding=(12, 7), bordercolor=PALETTE["button_line"], lightcolor=PALETTE["button"], darkcolor=PALETTE["button_line"], focusthickness=1, focuscolor=PALETTE["accent"])
        style.configure("Compact.TButton", background=PALETTE["button"], foreground=PALETTE["text"], padding=(8, 5), bordercolor=PALETTE["button_line"], lightcolor=PALETTE["button"], darkcolor=PALETTE["button_line"], focusthickness=1, focuscolor=PALETTE["accent"])
        style.map("TButton", background=[("pressed", PALETTE["button_active"]), ("active", PALETTE["button_hover"])], bordercolor=[("active", PALETTE["accent"])])
        style.map("Compact.TButton", background=[("pressed", PALETTE["button_active"]), ("active", PALETTE["button_hover"])], bordercolor=[("active", PALETTE["accent"])])
        style.configure("TCheckbutton", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
        style.configure("TCombobox", fieldbackground=PALETTE["panel_alt"], background=PALETTE["ribbon_panel"], foreground=PALETTE["text"], arrowsize=14, bordercolor=PALETTE["panel_line"], padding=4)

    def _location_map(self) -> dict[str, LocationPreset]:
        locations = {location.name: location for location in LOCATION_PRESETS}
        locations.update({location.name: location for location in self.user_locations})
        return locations

    def _refresh_location_choices(self) -> None:
        self.location_names = combined_visible_location_names(self.user_locations, self.hidden_builtin_location_ids)
        self.locations_by_name = self._location_map()
        if hasattr(self, "location_combo"):
            self.location_combo.configure(values=self.location_names)
        self._refresh_location_status()

    def _refresh_location_status(self) -> None:
        if not hasattr(self, "location_status_var"):
            return
        count_text = f"{len(self.user_locations)} custom saved location{'s' if len(self.user_locations) != 1 else ''}."
        home_text = f" Home: {self.home_location_name}." if self.home_location_name else " Home: local timezone default."
        hidden_count = len(self.hidden_builtin_location_ids)
        hidden_text = f" Hidden built-ins: {hidden_count}." if hidden_count else " Built-ins visible."
        self.location_status_var.set(count_text + home_text + hidden_text)

    def _build_layout(self) -> None:
        self._build_top_bars()

        self.shell = tk.Frame(self.root, bg=PALETTE["app_bg"], padx=8, pady=8)
        self.shell.pack(fill=tk.BOTH, expand=True)

        self.workspace_panes = tk.PanedWindow(
            self.shell,
            orient=tk.HORIZONTAL,
            bg=PALETTE["app_bg"],
            bd=0,
            sashwidth=6,
            sashrelief=tk.FLAT,
            showhandle=True,
            handlesize=18,
            handlepad=48,
        )
        self.workspace_panes.pack(fill=tk.BOTH, expand=True)

        self.left_panel = tk.Frame(self.workspace_panes, bg=PALETTE["panel"], padx=8, pady=8, width=320)
        self.left_panel.pack_propagate(False)
        self._build_left_scroll_area()
        self._build_left_controls()

        self.center_pane = tk.Frame(self.workspace_panes, bg=PALETTE["panel"], padx=0, pady=0, width=720)
        self._build_center_scroll_area()
        self.center_panel.columnconfigure(0, weight=1)
        self.center_panel.rowconfigure(3, weight=1, minsize=260)
        self._build_chart_panel()

        self.right_panel = tk.Frame(self.workspace_panes, bg=PALETTE["astrolabe_bg"], padx=7, pady=7, width=350)
        self.right_panel.pack_propagate(False)
        self._build_right_panel()
        self._pack_workspace_panels()

        self.status_var = tk.StringVar(value="Backend: Python desktop engine")
        status = tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            bg=PALETTE["top_bar_dark"],
            fg="white",
            font=("Segoe UI", 9),
            padx=10,
            pady=3,
        )
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_left_scroll_area(self) -> None:
        viewport = tk.Frame(self.left_panel, bg=PALETTE["panel"])
        viewport.pack(fill=tk.BOTH, expand=True)
        self.left_scroll_canvas = tk.Canvas(
            viewport,
            bg=PALETTE["panel"],
            bd=0,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(viewport, orient=tk.VERTICAL, command=self.left_scroll_canvas.yview)
        self.left_controls_parent = ttk.Frame(self.left_scroll_canvas, style="Panel.TFrame")
        self.left_controls_window = self.left_scroll_canvas.create_window((0, 0), window=self.left_controls_parent, anchor="nw")
        self.left_scroll_canvas.configure(yscrollcommand=scrollbar.set)
        self.left_scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.left_controls_parent.bind(
            "<Configure>",
            lambda _event: self.left_scroll_canvas.configure(scrollregion=self.left_scroll_canvas.bbox("all")),
        )
        self.left_scroll_canvas.bind(
            "<Configure>",
            lambda event: self.left_scroll_canvas.itemconfigure(self.left_controls_window, width=event.width),
        )
        self.left_scroll_canvas.bind("<Enter>", lambda _event: self.left_scroll_canvas.bind_all("<MouseWheel>", self._scroll_left_controls))
        self.left_scroll_canvas.bind("<Leave>", lambda _event: self.left_scroll_canvas.unbind_all("<MouseWheel>"))

    def _scroll_left_controls(self, event: tk.Event) -> None:
        if not hasattr(self, "left_scroll_canvas"):
            return
        delta = int(-1 * (event.delta / 120)) if getattr(event, "delta", 0) else 0
        if delta:
            self.left_scroll_canvas.yview_scroll(delta, "units")

    def _build_center_scroll_area(self) -> None:
        viewport = tk.Frame(self.center_pane, bg=PALETTE["panel"])
        viewport.pack(fill=tk.BOTH, expand=True)
        self.center_scroll_canvas = tk.Canvas(
            viewport,
            bg=PALETTE["panel"],
            bd=0,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(viewport, orient=tk.VERTICAL, command=self.center_scroll_canvas.yview)
        self.center_panel = ttk.Frame(self.center_scroll_canvas, style="Panel.TFrame", padding=10)
        self.center_controls_window = self.center_scroll_canvas.create_window((0, 0), window=self.center_panel, anchor="nw")
        self.center_scroll_canvas.configure(yscrollcommand=scrollbar.set)
        self.center_scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.center_panel.bind(
            "<Configure>",
            lambda _event: self.center_scroll_canvas.configure(scrollregion=self.center_scroll_canvas.bbox("all")),
        )
        self.center_scroll_canvas.bind(
            "<Configure>",
            lambda event: self.center_scroll_canvas.itemconfigure(self.center_controls_window, width=event.width),
        )
        self.center_scroll_canvas.bind("<Enter>", lambda _event: self.center_scroll_canvas.bind_all("<MouseWheel>", self._scroll_center_workspace))
        self.center_scroll_canvas.bind("<Leave>", lambda _event: self.center_scroll_canvas.unbind_all("<MouseWheel>"))
        self.center_panel.bind("<Enter>", lambda _event: self.center_scroll_canvas.bind_all("<MouseWheel>", self._scroll_center_workspace))
        self.center_panel.bind("<Leave>", lambda _event: self.center_scroll_canvas.unbind_all("<MouseWheel>"))

    def _scroll_center_workspace(self, event: tk.Event) -> None:
        if not hasattr(self, "center_scroll_canvas"):
            return
        delta = int(-1 * (event.delta / 120)) if getattr(event, "delta", 0) else 0
        if delta:
            self.center_scroll_canvas.yview_scroll(delta, "units")

    def _build_top_bars(self) -> None:
        title_bar = tk.Frame(self.root, bg=PALETTE["title_bar"], height=54)
        title_bar.pack(fill=tk.X)
        brand = tk.Frame(title_bar, bg=PALETTE["title_bar"])
        brand.pack(side=tk.LEFT, padx=18, pady=8)
        tk.Label(brand, text="Electional Software", bg=PALETTE["title_bar"], fg="#ffffff", font=("Segoe UI Semibold", 14)).pack(anchor="w")
        tk.Label(brand, text=f"Judgment engine and timing workbench | {APP_BUILD_LABEL}", bg=PALETTE["title_bar"], fg="#90a6b8", font=("Segoe UI", 8)).pack(anchor="w")
        tk.Label(
            title_bar,
            text="Python desktop engine",
            bg=PALETTE["title_bar"],
            fg="#b9c5d2",
            font=("Segoe UI Semibold", 9),
        ).pack(side=tk.RIGHT, padx=18, pady=15)

        menu = ttk.Frame(self.root, style="Top.TFrame", padding=(14, 6))
        menu.pack(fill=tk.X)
        for index, item in enumerate(TOP_NAV_ITEMS):
            menu.columnconfigure(index, weight=1, uniform="top-nav")
            button = self._top_nav_button(menu, item)
            self.top_nav_buttons[item] = button
            button.grid(
                row=0,
                column=index,
                sticky="ew",
                padx=(0 if index == 0 else 3, 0 if index == len(TOP_NAV_ITEMS) - 1 else 3),
            )

        ribbon = tk.Frame(self.root, bg=PALETTE["ribbon"], padx=12, pady=5)
        ribbon.pack(fill=tk.X)
        for index, (group_title, items) in enumerate(RIBBON_GROUPS):
            ribbon.columnconfigure(index, weight=1, uniform="ribbon-groups")
            self._ribbon_group(ribbon, group_title, items).grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0 if index == 0 else 5, 0 if index == len(RIBBON_GROUPS) - 1 else 5),
                pady=(1, 2),
            )

    def _top_nav_button(self, parent: tk.Widget, label: str) -> tk.Button:
        button = tk.Button(
            parent,
            text=label,
            command=lambda: self._run_top_nav_action(label),
            bg=PALETTE["top_nav"],
            fg="#f8f2de",
            activebackground=PALETTE["top_nav_active"],
            activeforeground="#fffdf6",
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=5,
            cursor="hand2",
            font=("Georgia", 9, "bold"),
            highlightthickness=1,
            highlightbackground=PALETTE["top_bar_dark"],
        )
        button.bind("<Enter>", lambda _event: self._set_top_nav_hover(label, True))
        button.bind("<Leave>", lambda _event: self._set_top_nav_hover(label, False))
        return button

    def _set_top_nav_hover(self, label: str, active: bool) -> None:
        button = self.top_nav_buttons.get(label)
        if not button:
            return
        if label == self.active_top_nav_label:
            button.configure(bg=PALETTE["top_nav_active"], fg="#fffdf6")
        else:
            button.configure(bg=PALETTE["top_nav_hover"] if active else PALETTE["top_nav"], fg="#f8f2de")

    def _set_active_top_nav(self, label: str) -> None:
        self.active_top_nav_label = label
        for item, button in self.top_nav_buttons.items():
            if item == label:
                button.configure(bg=PALETTE["top_nav_active"], fg="#fffdf6")
            else:
                button.configure(bg=PALETTE["top_nav"], fg="#f8f2de")

    def _sync_top_nav_selection(self, page_title: str) -> None:
        selected = next((label for label, target in TOP_NAV_PAGE_TARGETS.items() if target == page_title), None)
        if selected is None:
            return
        self._set_active_top_nav(selected)

    def _ribbon_group(self, parent: tk.Widget, title: str, items: tuple[str, ...]) -> tk.Frame:
        group = tk.Frame(
            parent,
            bg=PALETTE["ribbon_panel"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=9,
            pady=7,
        )
        tk.Frame(group, bg=PALETTE["accent"], height=2).pack(fill=tk.X, pady=(0, 5))
        tk.Label(
            group,
            text=title.upper(),
            bg=PALETTE["ribbon_panel"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 8, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 6))
        grid = tk.Frame(group, bg=PALETTE["ribbon_panel"])
        grid.pack(fill=tk.X)
        for column in range(RIBBON_COLUMNS):
            grid.columnconfigure(column, weight=1, uniform=f"ribbon-{title}")
        for index, item in enumerate(items):
            row = index // RIBBON_COLUMNS
            column = index % RIBBON_COLUMNS
            self._ribbon_button(grid, item).grid(row=row, column=column, sticky="nsew", padx=(0, 3), pady=(0, 3))
        return group

    def _ribbon_button(self, parent: tk.Widget, label: str) -> tk.Button:
        title = {
            "New Chart": "New",
            "Save Report": "Save",
            "Copy": "Copy",
            "Report": "Report",
            "Day Report": "Day Report",
            "Wheel": "Wheel",
            "Export Wheel": "Export",
            "Calculate": "Calc",
            "Show Current": "Current",
            "Find Best": "Find Best",
            "Search Page": "Search",
            "Transits/Timeline": "Timeline",
            "Advisor": "Advisor",
            "Improve": "Improve",
            "Decision": "Decision",
            "Compare": "Compare",
            "Factors": "Factors",
            "Chart Data": "Data",
            "Diagnostics": "Diag",
            "Aspects": "Aspects",
            "Aspect Strength": "Strength",
            "Declination": "Parallels",
            "Button Health": "Buttons",
            "Score Audit": "Audit",
            "Factor Map": "Factors",
            "Cache Stats": "Cache",
            "Clear Cache": "Clear",
            "Focus Wheel": "Focus",
            "Void Course": "VOC",
            "Out of Bounds": "OOB",
            "Aspect Config": "Aspects",
            "Fixed Stars": "Stars",
            "Heliacal Search": "Heliacal",
            "Map": "Map",
        }.get(label, label)
        button = tk.Button(
            parent,
            text=title,
            command=lambda action=label: self._run_ribbon_action(action),
            bg=PALETTE["button"],
            fg=PALETTE["text"],
            activebackground=PALETTE["button_hover"],
            activeforeground=PALETTE["accent_dark"],
            disabledforeground=PALETTE["muted"],
            relief=tk.FLAT,
            bd=0,
            highlightbackground=PALETTE["button_line"],
            highlightthickness=1,
            width=14,
            height=2,
            cursor="hand2",
            font=("Georgia", 8, "bold"),
            justify=tk.CENTER,
            wraplength=100,
            padx=3,
            pady=2,
        )
        return button

    def _run_top_nav_action(self, label: str) -> None:
        actions = {
            "Wheel": lambda: self._open_main_page("Wheel", "Window"),
            "Search": self._open_search_workbench_page,
            "Analysis": lambda: self._apply_page_mode("analysis"),
            "Timeline": self._open_timeline_workbench,
            "Validation": lambda: self._apply_page_mode("validation"),
            "Reports": lambda: self._apply_page_mode("reports"),
        }
        actions.get(label, lambda: self._show_unknown_action(label))()

    def _set_workspace_page(self, label: str) -> None:
        if label in TOP_NAV_ITEMS:
            self._set_active_top_nav(label)
        if hasattr(self, "workspace_page_var"):
            self.workspace_page_var.set(f"Main page: {label}")
        if hasattr(self, "workspace_page_summary_var"):
            self.workspace_page_summary_var.set(TOP_NAV_WORKSPACE_SUMMARIES.get(label, "Workspace page opened."))

    def _open_main_page(self, label: str, detail_page: str) -> None:
        self._set_workspace_page(label)
        self._scroll_center_to_top()
        self._focus_detail_page(detail_page)
        self.status_var.set(f"Opened {label} workspace page.")

    def _mark_search_workbench_action(self, action: str, *, running: bool = False) -> None:
        self.search_workbench_run_count += 1
        stamp = datetime.now().strftime("%H:%M:%S")
        self.search_workbench_last_action = f"{action} #{self.search_workbench_run_count} at {stamp}"
        if hasattr(self, "search_workbench_title_var"):
            self.search_workbench_title_var.set(f"Search Workbench | {action}")
        if hasattr(self, "search_workbench_summary_var"):
            state = "Running" if running else "Opened"
            self.search_workbench_summary_var.set(f"{state}: {self.search_workbench_last_action}")
        if hasattr(self, "search_workbench_detail_var"):
            self.search_workbench_detail_var.set("Updating visible search diagnostics...")
        if hasattr(self, "status_var"):
            self.status_var.set(f"{action}: updating Search Workbench.")
        try:
            self.root.update_idletasks()
        except tk.TclError:
            return

    def _open_search_workbench_page(self) -> None:
        self._mark_search_workbench_action("Search Page")
        if not self.selected_window:
            self.calculate(show_input_chart=True)
        self._set_workspace_page("Search")
        self._scroll_center_to_top()
        self._apply_page_mode("transit-search")
        self._refresh_search_workbench_strip()
        self._focus_detail_page("Search")
        self.status_var.set("Opened Search Workbench with active filters, aspect profile, candidates, and rejection diagnostics.")

    def _bind_clickable(self, widget: tk.Widget, command: Callable[[], None]) -> None:
        widget.bind("<Button-1>", lambda _event: command())
        widget.bind("<Enter>", lambda _event: self._set_clickable_hover(widget, True))
        widget.bind("<Leave>", lambda _event: self._set_clickable_hover(widget, False))
        for child in widget.winfo_children():
            self._bind_clickable(child, command)

    def _set_clickable_hover(self, widget: tk.Widget, active: bool) -> None:
        color = PALETTE["button_hover"] if active else PALETTE["button"]
        widget.configure(cursor="hand2" if active else "")
        if isinstance(widget, (tk.Frame, tk.Label)):
            widget.configure(bg=color)
            for child in widget.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=color)
                elif isinstance(child, tk.Frame):
                    child.configure(bg=PALETTE["accent"])

    def _render_summary_chips(self, snapshot: dict[str, object]) -> None:
        for child in self.context_chip_frame.winfo_children():
            child.destroy()
        for text in summary_chip_lines(snapshot, self._current_point_set().name):
            chip = tk.Frame(
                self.context_chip_frame,
                bg=PALETTE["chip"],
                highlightbackground=PALETTE["chip_line"],
                highlightthickness=1,
                padx=9,
                pady=4,
            )
            chip.pack(side=tk.LEFT, padx=(0, 6), pady=(0, 2))
            tk.Label(chip, text=text, bg=PALETTE["chip"], fg=PALETTE["top_bar_dark"], font=("Georgia", 8, "bold")).pack()

    def _run_ribbon_action(self, label: str) -> None:
        actions = {
            "New Chart": self._new_chart,
            "Save": self._save_current_report,
            "Save Report": self._save_current_report,
            "Copy": self._copy_current_report,
            "Report": self._show_current_report_dialog,
            "Day Report": self._show_daily_aspect_report_dialog,
            "Wheel": self._save_chart_wheel,
            "Export Wheel": self._save_chart_wheel,
            "Calendar": self._save_selected_calendar_event,
            "Ask": self._show_quick_help,
            "Calculate": self.calculate,
            "Show Current": lambda: self.calculate(show_input_chart=True),
            "Find Best": self.calculate,
            "Transits": self._open_timeline_workbench,
            "Transits/Timeline": self._open_timeline_workbench,
            "Electional Search": self._run_electional_search_workbench,
            "Search Page": self._open_search_workbench_page,
            "Shortlist": self._add_selected_to_shortlist,
            "Advisor": lambda: self._focus_detail_page("Advisor"),
            "Improve": lambda: self._focus_detail_page("Improve"),
            "Decision": lambda: self._focus_detail_page("Decision"),
            "Compare": lambda: self._focus_detail_page("Compare"),
            "Factors": lambda: self._focus_detail_page("Factor Explorer"),
            "Chart Data": self._show_chart_inspector,
            "Diagnostics": lambda: self._focus_detail_page("Diagnostics"),
            "Aspects": self._show_wheel_aspects,
            "Aspect Strength": lambda: self._focus_detail_page("Aspect Strength"),
            "Declination": lambda: self._focus_detail_page("Declination"),
            "Button Health": self._show_button_health,
            "Score Audit": self._show_score_audit_dialog,
            "Factor Map": self._show_factor_map_dialog,
            "Cache Stats": self._show_cache_stats_dialog,
            "Clear Cache": self._clear_search_cache,
            "Health": self._show_calculation_health_dialog,
            "Focus Wheel": self._toggle_focus_mode,
            "Void Course": self._show_void_course_dialog,
            "Out of Bounds": self._show_out_of_bounds_dialog,
            "Aspect Config": self._show_aspect_config_dialog,
            "Assets": self._show_capricorn_asset_audit,
            "Preferences": self._show_preferences_dialog,
            "Systems": self._show_systems_dialog,
            "Bounds": self._show_bounds_dialog,
            "Lots": self._show_lots_reference_dialog,
            "Fixed Stars": self._show_fixed_stars_dialog,
            "Heliacal Search": self._show_heliacal_dialog,
            "Map": self._show_astro_mapping_dialog,
        }
        actions.get(label, lambda: self._show_unknown_action(label))()

    def _show_wheel_aspects(self) -> None:
        self.show_aspects_var.set(True)
        self.compact_wheel_var.set(False)
        self._display_option_changed()
        self._focus_detail_page("Aspects")
        self.status_var.set("Wheel aspects enabled and aspect list opened.")

    def _show_capricorn_asset_audit(self) -> None:
        inventory = inventory_capricorn_assets()
        self._show_text_dialog("CapricornPROMETHEUS Assets", format_capricorn_asset_audit(inventory))
        if inventory.exists and inventory.root:
            self.status_var.set(f"Opened Capricorn asset audit for {inventory.root}.")
        else:
            self.status_var.set("Capricorn asset folder not found in the usual locations.")

    def _import_capricorn_aspect_profiles(self) -> None:
        result = import_capricorn_aspect_profiles()
        self.aspect_profiles = load_aspect_profiles()
        self.active_aspect_profile = self.aspect_profiles[-1] if self.aspect_profiles else self.active_aspect_profile
        self.aspect_profile_var.set(self.active_aspect_profile.name)
        if hasattr(self, "aspect_profile_combo"):
            self.aspect_profile_combo.configure(values=self._aspect_profile_names())
        self._refresh_aspect_focus_controls()
        self._refresh_left_status_chips()
        self._save_session()
        self._show_text_dialog("Capricorn Aspect Import", format_capricorn_aspect_import_result(result))
        self.status_var.set(f"Imported {result.imported_profiles} Capricorn aspect profiles.")

    def _open_timeline_workbench(self) -> None:
        self._mark_search_workbench_action("Timeline")
        if not self.selected_window:
            self.calculate(show_input_chart=True)
        if not self.selected_window:
            return
        self._set_workspace_page("Timeline")
        self._scroll_center_to_top()
        self.page_mode_var.set(PAGE_MODE_LABELS["transit-search"])
        self.show_aspects_var.set(True)
        self._refresh_search_workbench_strip()
        self._focus_detail_page("Timeline")
        self._save_session()
        self.status_var.set("Opened transit/timeline workbench with current, local-day, and next-24h aspect scans.")

    def _run_electional_search_workbench(self) -> None:
        self._mark_search_workbench_action("Electional Search", running=True)
        self.calculate(show_input_chart=False)
        if not self.selected_window:
            return
        self._set_workspace_page("Search")
        self._scroll_center_to_top()
        self._apply_page_mode("transit-search")
        self._refresh_search_workbench_strip()
        self._focus_detail_page("Search")
        self.status_var.set("Electional Search completed with ranked candidates and rejection diagnostics.")

    def _show_out_of_bounds_dialog(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("Out of Bounds", "Calculate a chart before checking declination and out-of-bounds diagnostics.")
            return
        lines = judgment_context_lines(self.selected_window, "declinationContext")
        if not lines:
            lines = [
                "Declination / Out-of-Bounds Diagnostics",
                "- Declination data is not available for the current point set or backend response.",
                "- Recalculate with the full electional point set, then open this tool again.",
            ]
        self._focus_detail_page("Declination")
        self._show_text_dialog("Out of Bounds / Declination", "\n".join(lines))
        self.status_var.set("Opened out-of-bounds and declination diagnostics.")

    def _unique_aspect_profile_id(self, name: str, replacing: str | None = None) -> str:
        base = sanitize_aspect_id(name)
        if base == DEFAULT_ASPECT_PROFILE_ID:
            base = "custom-aspect-profile"
        used = {profile.id for profile in self.aspect_profiles if profile.id != replacing}
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _show_aspect_config_dialog(self) -> None:
        working_aspects = list(self.active_aspect_profile.aspects)
        dialog = tk.Toplevel(self.root)
        dialog.title("Aspect Configuration")
        dialog.geometry("900x620")
        dialog.configure(bg=PALETTE["app_bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        header = tk.Frame(dialog, bg=PALETTE["top_bar"], padx=12, pady=8)
        header.pack(fill=tk.X)
        tk.Label(header, text="Aspect Configuration Dialog", bg=PALETTE["top_bar"], fg="white", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(
            header,
            text="Create and tune the aspects used by chart detection, election search, scoring, reports, and the wheel.",
            bg=PALETTE["top_bar"],
            fg="#dce8e2",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(2, 0))

        body = tk.Frame(dialog, bg=PALETTE["panel"], padx=12, pady=12)
        body.pack(fill=tk.BOTH, expand=True)
        profile_grid = tk.Frame(body, bg=PALETTE["panel"])
        profile_grid.pack(fill=tk.X, pady=(0, 10))
        profile_grid.columnconfigure(1, weight=1)
        profile_grid.columnconfigure(3, weight=2)
        name_var = tk.StringVar(value=self.active_aspect_profile.name)
        description_var = tk.StringVar(value=self.active_aspect_profile.description)
        tk.Label(profile_grid, text="Name", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 6))
        tk.Entry(profile_grid, textvariable=name_var, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]).grid(row=0, column=1, sticky="ew", padx=(0, 12), ipady=5)
        tk.Label(profile_grid, text="Description", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold")).grid(row=0, column=2, sticky="w", padx=(0, 6))
        tk.Entry(profile_grid, textvariable=description_var, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]).grid(row=0, column=3, sticky="ew", ipady=5)

        table_wrap = tk.Frame(body, bg=PALETTE["panel"], highlightbackground=PALETTE["panel_line"], highlightthickness=1)
        table_wrap.pack(fill=tk.BOTH, expand=True)
        columns = ("enabled", "glyph", "name", "line", "abbr", "angle", "orb", "tone", "kind")
        tree = ttk.Treeview(table_wrap, columns=columns, show="headings", height=14)
        headings = {
            "enabled": "On",
            "glyph": "Glyph",
            "name": "Aspect",
            "line": "Line",
            "abbr": "Abv",
            "angle": "Angle Exact",
            "orb": "Orb",
            "tone": "Tone",
            "kind": "Kind",
        }
        widths = {"enabled": 48, "glyph": 60, "name": 190, "line": 82, "abbr": 70, "angle": 95, "orb": 80, "tone": 85, "kind": 78}
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], minwidth=widths[column], stretch=column == "name")
        scrollbar = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def refresh_tree(select_index: int | None = None) -> None:
            tree.delete(*tree.get_children())
            for index, aspect in enumerate(working_aspects):
                tree.insert(
                    "",
                    tk.END,
                    iid=str(index),
                    values=(
                        "yes" if aspect.enabled else "no",
                        aspect.glyph or aspect.abbreviation,
                        aspect.name,
                        aspect.color,
                        aspect.abbreviation,
                        f"{float(aspect.angle):06.2f}",
                        f"{float(aspect.default_orb):.2f}",
                        aspect.tone,
                        "built-in" if aspect.built_in else "custom",
                    ),
                )
            if select_index is not None and 0 <= select_index < len(working_aspects):
                tree.selection_set(str(select_index))
                tree.see(str(select_index))

        def selected_index() -> int | None:
            selection = tree.selection()
            if not selection:
                return None
            try:
                return int(selection[0])
            except ValueError:
                return None

        def open_editor(index: int | None = None) -> None:
            existing = working_aspects[index] if index is not None else None
            editor = tk.Toplevel(dialog)
            editor.title("Edit Aspect" if existing else "Add Aspect")
            editor.geometry("430x440")
            editor.configure(bg=PALETTE["panel"])
            editor.transient(dialog)
            editor.grab_set()
            form = tk.Frame(editor, bg=PALETTE["panel"], padx=12, pady=12)
            form.pack(fill=tk.BOTH, expand=True)
            name_field = tk.StringVar(value=existing.name if existing else "")
            id_field = tk.StringVar(value=existing.id if existing else "")
            abbr_field = tk.StringVar(value=existing.abbreviation if existing else "")
            glyph_field = tk.StringVar(value=existing.glyph if existing else "")
            angle_field = tk.StringVar(value=f"{float(existing.angle):g}" if existing else "45")
            orb_field = tk.StringVar(value=f"{float(existing.default_orb):g}" if existing else "2")
            tone_field = tk.StringVar(value=existing.tone if existing else "mixed")
            color_field = tk.StringVar(value=existing.color if existing else "#536d8d")
            enabled_field = tk.BooleanVar(value=existing.enabled if existing else True)

            def row(label: str, widget: tk.Widget) -> None:
                tk.Label(form, text=label, bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 8, "bold")).pack(anchor="w", pady=(7, 2))
                widget.pack(fill=tk.X, ipady=4)

            row("Name", tk.Entry(form, textvariable=name_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            row("Identifier", tk.Entry(form, textvariable=id_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            row("Abbreviation", tk.Entry(form, textvariable=abbr_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            row("Glyph / fallback text", tk.Entry(form, textvariable=glyph_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            number_row = tk.Frame(form, bg=PALETTE["panel"])
            number_row.pack(fill=tk.X)
            number_row.columnconfigure(0, weight=1)
            number_row.columnconfigure(1, weight=1)
            for column, (label, variable) in enumerate((("Exact angle", angle_field), ("Orb degrees", orb_field))):
                cell = tk.Frame(number_row, bg=PALETTE["panel"])
                cell.grid(row=0, column=column, sticky="ew", padx=(0, 5) if column == 0 else (5, 0))
                tk.Label(cell, text=label, bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 8, "bold")).pack(anchor="w", pady=(7, 2))
                tk.Entry(cell, textvariable=variable, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]).pack(fill=tk.X, ipady=4)
            row("Tone", ttk.Combobox(form, textvariable=tone_field, values=("support", "stress", "mixed"), state="readonly"))
            row("Line / color", tk.Entry(form, textvariable=color_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            tk.Checkbutton(form, text="Enabled in this profile", variable=enabled_field, bg=PALETTE["panel"], fg=PALETTE["text"], activebackground=PALETTE["panel"], selectcolor=PALETTE["panel_alt"]).pack(anchor="w", pady=(8, 0))

            def save_aspect() -> None:
                name = name_field.get().strip()
                aspect_id = sanitize_aspect_id(id_field.get() or name)
                try:
                    angle = float(angle_field.get())
                    orb = float(orb_field.get())
                except ValueError:
                    messagebox.showerror("Aspect validation", "Angle and orb must be numbers.", parent=editor)
                    return
                duplicate = any(aspect.id == aspect_id and idx != index for idx, aspect in enumerate(working_aspects))
                candidate = Aspect(
                    id=aspect_id,
                    name=name,
                    angle=angle,
                    default_orb=orb,
                    tone=tone_field.get(),
                    meaning=(existing.meaning if existing else "Custom aspect definition."),
                    abbreviation=abbr_field.get().strip() or name[:4].title(),
                    glyph=glyph_field.get().strip() or abbr_field.get().strip() or name[:2].title(),
                    color=color_field.get().strip() or "#536d8d",
                    enabled=enabled_field.get(),
                    built_in=bool(existing.built_in) if existing else False,
                )
                errors = []
                if duplicate:
                    errors.append(f"Duplicate aspect id: {aspect_id}.")
                errors.extend(validate_aspect_profile(AspectProfile("edit", "Edit", "", tuple([candidate]))))
                if errors:
                    messagebox.showerror("Aspect validation", "\n".join(errors), parent=editor)
                    return
                if index is None:
                    working_aspects.append(candidate)
                    refresh_tree(len(working_aspects) - 1)
                else:
                    working_aspects[index] = candidate
                    refresh_tree(index)
                editor.destroy()

            actions = tk.Frame(editor, bg=PALETTE["panel"], padx=12, pady=10)
            actions.pack(fill=tk.X)
            ttk.Button(actions, text="Save Aspect", command=save_aspect).pack(side=tk.RIGHT)
            ttk.Button(actions, text="Cancel", command=editor.destroy).pack(side=tk.RIGHT, padx=(0, 8))

        def delete_or_disable() -> None:
            index = selected_index()
            if index is None:
                return
            aspect = working_aspects[index]
            if aspect.built_in:
                working_aspects[index] = Aspect(
                    id=aspect.id,
                    name=aspect.name,
                    angle=aspect.angle,
                    default_orb=aspect.default_orb,
                    tone=aspect.tone,
                    meaning=aspect.meaning,
                    abbreviation=aspect.abbreviation,
                    glyph=aspect.glyph,
                    color=aspect.color,
                    enabled=False,
                    built_in=True,
                )
                refresh_tree(index)
                return
            del working_aspects[index]
            refresh_tree(min(index, len(working_aspects) - 1))

        def move(delta: int) -> None:
            index = selected_index()
            if index is None:
                return
            target = index + delta
            if target < 0 or target >= len(working_aspects):
                return
            working_aspects[index], working_aspects[target] = working_aspects[target], working_aspects[index]
            refresh_tree(target)

        def save_profile() -> None:
            profile_name = name_var.get().strip() or "Custom Aspect Profile"
            profile_id = self.active_aspect_profile.id
            if profile_id == DEFAULT_ASPECT_PROFILE_ID:
                if profile_name == self.active_aspect_profile.name:
                    profile_name = f"{profile_name} Custom"
                profile_id = self._unique_aspect_profile_id(profile_name)
            profile = AspectProfile(profile_id, profile_name, description_var.get().strip(), tuple(working_aspects))
            errors = validate_aspect_profile(profile)
            if errors:
                messagebox.showerror("Aspect profile validation", "\n".join(errors), parent=dialog)
                return
            replaced = False
            next_profiles: list[AspectProfile] = []
            for existing_profile in self.aspect_profiles:
                if existing_profile.id == profile.id:
                    next_profiles.append(profile)
                    replaced = True
                else:
                    next_profiles.append(existing_profile)
            if not replaced:
                next_profiles.append(profile)
            self.aspect_profiles = next_profiles
            save_aspect_profiles(self.aspect_profiles)
            self.active_aspect_profile = profile
            self.aspect_profile_var.set(profile.name)
            if hasattr(self, "aspect_profile_combo"):
                self.aspect_profile_combo.configure(values=self._aspect_profile_names())
            self._refresh_aspect_focus_controls()
            self._refresh_left_status_chips()
            self._save_session()
            self._log_event(f"Saved aspect profile: {profile.name} ({len(profile.aspects)} aspects)")
            self.status_var.set(f"Saved aspect profile: {profile.name}. Recalculate when ready.")
            dialog.destroy()

        button_bar = tk.Frame(body, bg=PALETTE["panel"])
        button_bar.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_bar, text="Add", command=lambda: open_editor()).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Edit", command=lambda: open_editor(selected_index()) if selected_index() is not None else None).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Delete / Disable", command=delete_or_disable).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Move Up", command=lambda: move(-1)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Move Down", command=lambda: move(1)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_bar, text="OK and Save", command=save_profile).pack(side=tk.RIGHT, padx=(0, 8))
        refresh_tree(0)

    def _new_chart(self) -> None:
        try:
            location = self.locations_by_name.get(self.location_var.get()) or build_custom_location(
                self.location_name_var.get(),
                self.latitude_var.get(),
                self.longitude_var.get(),
                self.timezone_var.get(),
            )
        except ValueError:
            location = default_location_for_timezone()
        self.date_var.set(date.today().isoformat())
        self.time_var.set("09:00")
        self.location_var.set(location.name)
        self.location_name_var.set(location.name)
        self.latitude_var.set(f"{location.latitude:.4f}")
        self.longitude_var.set(f"{location.longitude:.4f}")
        self.timezone_var.set(location.timezone)
        self.objective_var.set(OBJECTIVES[0])
        self.zodiac_system_var.set(get_zodiac_system(DEFAULT_ZODIAC_SYSTEM_ID).name)
        self.house_system_var.set(get_house_system(DEFAULT_HOUSE_SYSTEM_ID).name)
        self.preset_var.set(ELECTIONAL_PRESETS[1].name)
        enabled_by_id = {aspect.id: aspect.enabled for aspect in self.active_aspect_profile.aspects}
        for aspect_id, var in self.aspect_vars.items():
            var.set(bool(enabled_by_id.get(aspect_id, True)))
        self.calculate(show_input_chart=True)

    def _save_current_report(self) -> None:
        if not self.selected_window or not self.current_location:
            self.status_var.set("Nothing to save yet. Calculate a chart first.")
            return
        reports_dir = Path.cwd() / "reports"
        reports_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = reports_dir / f"electional-report-{stamp}.txt"
        path.write_text(self._current_report_text(), encoding="utf-8")
        self.status_var.set(f"Saved report: {path}")
        self._log_event(f"Saved report: {path.name}")

    def _copy_current_report(self) -> None:
        if not self.selected_window:
            self.status_var.set("Nothing to copy yet. Calculate a chart first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._current_report_text())
        self.status_var.set("Copied current electional report to clipboard.")

    def _show_current_report_dialog(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("Electional report", "Calculate a chart before viewing a report.")
            return
        report = self._current_report_text()
        self._show_text_dialog("Electional Report", report)
        self.status_var.set("Opened full electional report.")

    def _show_daily_aspect_report_dialog(self) -> None:
        if not self.selected_window or not self.current_location:
            messagebox.showinfo("Day Report", "Calculate a chart/search before opening the daily aspect report.")
            return
        dashboard = format_aspect_highlight_dashboard(self.current_aspect_highlights)
        timeline = self.current_aspect_highlights.get("timeline", []) if isinstance(self.current_aspect_highlights, dict) else []
        timeline_lines = [
            f"- {format_aspect_highlight(item)}"
            for item in timeline[:12]
            if isinstance(item, Mapping)
        ]
        try:
            preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
            zodiac_system = get_zodiac_system(self.zodiac_system_var.get())
            house_system = get_house_system(self.house_system_var.get())
            step_minutes = int(self.step_minutes_var.get().strip() or DEFAULT_STEP_MINUTES)
            max_results = max(12, int(self.max_results_var.get().strip())) if self.max_results_var.get().strip() else 12
            daily_config = SearchConfig(
                end_offset_minutes=24 * 60,
                step_minutes=step_minutes,
                max_results=max_results,
                minimum_score=None,
                minimum_fit=None,
                minimum_confidence=None,
                minimum_cleanliness=None,
                maximum_volatility=None,
                avoid_major_stress=False,
                require_applying_support=False,
                require_angular_benefic=False,
                avoid_angular_malefics=False,
                require_moon_non_void=False,
                avoid_objective_antipatterns=False,
            )
            daily_report = build_election_report(
                self.date_var.get(),
                self.time_var.get(),
                self.current_location,
                preset.id,
                self._selected_aspect_ids(),
                zodiac_system.id,
                house_system.id,
                daily_config,
                self.objective_var.get(),
                self._active_aspect_definitions(),
            )
        except Exception as exc:  # pragma: no cover - exercised through desktop UI.
            messagebox.showerror("Day Report", f"Could not build the 24-hour day report:\n{exc}")
            return
        windows = list(daily_report.get("windows", []))
        selected = windows[0] if windows else daily_report.get("snapshot", self.selected_window)
        daily_searched = int(daily_report.get("searchedWindowCount", len(windows)) or len(windows))
        daily_evaluated = int(daily_report.get("evaluatedWindowCount", daily_searched) or daily_searched)
        daily_refined = int(daily_report.get("refinedWindowCount", 0) or 0)
        body = build_transit_search_page(
            daily_report.get("snapshot", self.input_snapshot or self.selected_window),
            selected,
            windows,
            self.current_location,
            format_search_summary(daily_config)
            + " Mode: 24-hour best-overall aspect report; hard filters are omitted for ranking visibility; "
            + f"evaluated {daily_evaluated} ({daily_searched} coarse + {daily_refined} refined); "
            + f"deep-built {daily_report.get('deepWindowCount', len(windows))}.",
            dict(daily_report.get("rejectionSummary") or {}),
        )
        report_text = (
            "Daily Aspect Report\n\n"
            "Current / Local Day / Next 24 Hours\n"
            f"{dashboard}\n\n"
            "Local-Day Timeline\n"
            + ("\n".join(timeline_lines) if timeline_lines else "- No local-day aspect highlights available.")
            + "\n\nRanked Election Windows\n"
            + body
        )
        self._show_text_dialog("Daily Aspect Report", report_text)
        self._focus_detail_page("Analysis")
        self.status_var.set("Opened 24-hour best-aspects-through-the-day report.")

    def _save_chart_wheel(self) -> None:
        if not self.selected_window:
            self.status_var.set("Nothing to export yet. Calculate a chart first.")
            return
        reports_dir = Path.cwd() / "reports"
        reports_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = reports_dir / f"electional-wheel-{stamp}.ps"
        self.canvas.update_idletasks()
        self.canvas.postscript(file=str(path), colormode="color")
        self.status_var.set(f"Saved chart wheel: {path}")
        self._log_event(f"Saved wheel export: {path.name}")

    def _add_selected_to_shortlist(self) -> None:
        if not self.selected_window or not self.current_location:
            self.status_var.set("Nothing to shortlist yet. Calculate and select a candidate window first.")
            return
        entry = build_shortlist_entry(self.selected_window, self.current_location, self.objective_var.get())
        self.shortlist = add_shortlist_entry(self.shortlist, entry)
        save_shortlist(self.shortlist)
        self._refresh_shortlist_text()
        self._focus_detail_page("Shortlist Board")
        self.status_var.set(f"Shortlisted {entry['formattedTime']} with score {entry['score']}.")
        self._log_event(f"Shortlisted window: {entry['formattedTime']} score {entry['score']}")

    def _clear_shortlist(self) -> None:
        self.shortlist = []
        save_shortlist(self.shortlist)
        self._refresh_shortlist_text()
        self.status_var.set("Cleared shortlisted candidate windows.")
        self._log_event("Cleared shortlist")

    def _save_shortlist_report(self) -> None:
        if not self.shortlist:
            self.status_var.set("Shortlist is empty.")
            return
        reports_dir = Path.cwd() / "reports"
        reports_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = reports_dir / f"electional-shortlist-{stamp}.txt"
        path.write_text(format_shortlist_entries(self.shortlist), encoding="utf-8")
        self.status_var.set(f"Saved shortlist: {path}")
        self._log_event(f"Saved shortlist: {path.name}")

    def _save_comparison_sheet(self) -> None:
        if not self.selected_window or not self.current_location:
            self.status_var.set("Nothing to export yet. Calculate and select a candidate window first.")
            return
        reports_dir = Path.cwd() / "reports"
        reports_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = reports_dir / f"electional-decision-sheet-{stamp}.txt"
        path.write_text(
            build_comparison_export_text(
                self.input_snapshot or self.selected_window,
                self.selected_window,
                self.current_windows,
                self.objective_var.get(),
                self.current_location,
            ),
            encoding="utf-8",
        )
        self.status_var.set(f"Saved decision sheet: {path}")
        self._log_event(f"Saved decision sheet: {path.name}")

    def _save_selected_calendar_event(self) -> None:
        if not self.selected_window or not self.current_location:
            self.status_var.set("Nothing to calendar-export yet. Select a candidate window first.")
            return
        entry = build_shortlist_entry(self.selected_window, self.current_location, self.objective_var.get())
        reports_dir = Path.cwd() / "reports"
        reports_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = reports_dir / f"electional-window-{stamp}.ics"
        path.write_text(calendar_from_entries([entry]), encoding="utf-8")
        self.status_var.set(f"Saved calendar event: {path}")
        self._log_event(f"Saved calendar event: {path.name}")

    def _save_shortlist_calendar(self) -> None:
        if not self.shortlist:
            self.status_var.set("Shortlist is empty.")
            return
        reports_dir = Path.cwd() / "reports"
        reports_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = reports_dir / f"electional-shortlist-{stamp}.ics"
        path.write_text(calendar_from_entries(self.shortlist), encoding="utf-8")
        self.status_var.set(f"Saved shortlist calendar: {path}")
        self._log_event(f"Saved shortlist calendar: {path.name}")

    def _copy_selected_calendar_event(self) -> None:
        if not self.selected_window or not self.current_location:
            self.status_var.set("Nothing to calendar-copy yet. Select a candidate window first.")
            return
        entry = build_shortlist_entry(self.selected_window, self.current_location, self.objective_var.get())
        self.root.clipboard_clear()
        self.root.clipboard_append(calendar_from_entries([entry]))
        self.status_var.set("Copied selected window calendar event to clipboard.")

    def _copy_shortlist(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(format_shortlist_entries(self.shortlist))
        self.status_var.set("Copied shortlist to clipboard.")

    def _focus_detail_page(self, page_title: str) -> None:
        if not hasattr(self, "detail_notebook"):
            return
        if page_title == "Button Health":
            self._refresh_button_health_text()
        for tab_id in self.detail_notebook.tabs():
            if self.detail_notebook.tab(tab_id, "text") == page_title:
                self.detail_notebook.select(tab_id)
                self._sync_top_nav_selection(page_title)
                self.status_var.set(f"Opened {page_title} detail page.")
                return
        self.status_var.set(f"{page_title} detail page is not available yet.")

    def _available_detail_pages(self) -> tuple[str, ...]:
        if not hasattr(self, "detail_notebook"):
            return DETAIL_PAGE_TABS
        return tuple(str(self.detail_notebook.tab(tab_id, "text")) for tab_id in self.detail_notebook.tabs())

    def _refresh_button_health_text(self) -> None:
        if hasattr(self, "button_health_text"):
            self._set_text(self.button_health_text, "\n".join(button_health_lines(self._available_detail_pages())))

    def _show_button_health(self) -> None:
        self._refresh_button_health_text()
        self._focus_detail_page("Button Health")

    def _refresh_shortlist_text(self) -> None:
        if not hasattr(self, "shortlist_text"):
            return
        actions = (
            "Shortlist Actions\n"
            "- Select a candidate window and press Shortlist or Save Pick.\n"
            "- Shortlisted windows rank by score, confidence, cleanliness, readiness, then lower volatility.\n"
            "- The shortlist now opens with batch diagnostics so the cleanest and steadiest saved windows stand out first.\n"
            "- Use Load Chart on a shortlist card to reopen that saved election in the main workspace.\n"
            "- Use Pick Tools to copy/save shortlist text or export .ics calendar files.\n\n"
        )
        self._set_text(self.shortlist_text, actions + format_shortlist_entries(self.shortlist))
        self._sync_shortlist_compare_defaults()
        self._refresh_shortlist_compare_text()
        self._refresh_shortlist_board()

    def _sync_shortlist_compare_defaults(self) -> None:
        valid_ids = [str(entry.get("id")) for entry in self.shortlist]
        if self.shortlist_compare_a_id not in valid_ids:
            self.shortlist_compare_a_id = valid_ids[0] if valid_ids else None
        if self.shortlist_compare_b_id not in valid_ids or self.shortlist_compare_b_id == self.shortlist_compare_a_id:
            alternatives = [entry_id for entry_id in valid_ids if entry_id != self.shortlist_compare_a_id]
            self.shortlist_compare_b_id = alternatives[0] if alternatives else None

    def _refresh_shortlist_compare_text(self) -> None:
        if not hasattr(self, "shortlist_compare_text"):
            return
        self._set_text(
            self.shortlist_compare_text,
            build_shortlist_compare_text(
                self.shortlist,
                self.shortlist_compare_a_id,
                self.shortlist_compare_b_id,
            ),
        )

    def _set_shortlist_compare_slot(self, entry_id: str, slot: str) -> None:
        if slot == "A":
            self.shortlist_compare_a_id = entry_id
            if self.shortlist_compare_b_id == entry_id:
                alternatives = [str(entry.get("id")) for entry in self.shortlist if str(entry.get("id")) != entry_id]
                self.shortlist_compare_b_id = alternatives[0] if alternatives else None
        else:
            self.shortlist_compare_b_id = entry_id
            if self.shortlist_compare_a_id == entry_id:
                alternatives = [str(entry.get("id")) for entry in self.shortlist if str(entry.get("id")) != entry_id]
                self.shortlist_compare_a_id = alternatives[0] if alternatives else None
        self._refresh_shortlist_compare_text()
        self._refresh_shortlist_board()
        self._focus_detail_page("Pick Compare")
        self._log_event(f"Shortlist compare slot {slot} set to {entry_id}")

    def _load_shortlist_entry(self, entry_id: str) -> None:
        entry = shortlist_entry_by_id(self.shortlist, entry_id)
        if not entry:
            self.status_var.set("That shortlisted window is no longer available.")
            return

        entry_datetime = str(entry.get("datetime", "")).strip()
        date_text = ""
        time_text = ""
        if "T" in entry_datetime:
            try:
                parsed = datetime.fromisoformat(entry_datetime)
                date_text = parsed.date().isoformat()
                time_text = parsed.strftime("%H:%M")
            except ValueError:
                date_text = ""
                time_text = ""
        if not date_text:
            date_text = self.date_var.get()
            time_text = normalize_time_text(self.time_var.get())

        location_name = str(entry.get("location", "")).strip()
        timezone_name = str(entry.get("timezone", "")).strip() or self.timezone_var.get()
        resolved_location = self.locations_by_name.get(location_name)
        latitude = entry.get("latitude", getattr(resolved_location, "latitude", self.latitude_var.get()))
        longitude = entry.get("longitude", getattr(resolved_location, "longitude", self.longitude_var.get()))

        self.date_var.set(date_text)
        self.time_var.set(time_text)
        self.objective_var.set(str(entry.get("objective", self.objective_var.get())))
        self.location_name_var.set(location_name or self.location_name_var.get())
        self.latitude_var.set(f"{float(latitude):.4f}" if isinstance(latitude, (int, float)) else str(latitude))
        self.longitude_var.set(f"{float(longitude):.4f}" if isinstance(longitude, (int, float)) else str(longitude))
        self.timezone_var.set(timezone_name)
        if location_name in self.location_names:
            self.location_var.set(location_name)
        else:
            self.location_var.set("Custom")

        self.calculate(show_input_chart=True)
        target_time = str(entry.get("formattedTime", "")).strip()
        matched_window = next((window for window in self.current_windows if str(window.get("formattedTime", "")).strip() == target_time), None)
        if matched_window:
            self._select_window(matched_window)
        self._focus_detail_page("Summary")
        self.status_var.set(f"Loaded shortlisted window {target_time or 'into the workspace'}.")
        self._log_event(f"Loaded shortlist entry: {target_time or entry_id}")

    def _add_tag_to_shortlist_entry(self, entry_id: str, tag_value: str) -> None:
        tag = str(tag_value).strip()
        if not tag:
            self.status_var.set("Enter or choose a shortlist tag first.")
            return
        self.shortlist = add_shortlist_tag(self.shortlist, entry_id, tag)
        save_shortlist(self.shortlist)
        self._refresh_shortlist_text()
        self.status_var.set(f"Added shortlist tag '{tag}'.")
        self._log_event(f"Shortlist tag added: {tag}")

    def _remove_tag_from_shortlist_entry(self, entry_id: str, tag: str) -> None:
        self.shortlist = remove_shortlist_tag(self.shortlist, entry_id, tag)
        save_shortlist(self.shortlist)
        self._refresh_shortlist_text()
        self.status_var.set(f"Removed shortlist tag '{tag}'.")
        self._log_event(f"Shortlist tag removed: {tag}")

    def _refresh_shortlist_board(self) -> None:
        if not hasattr(self, "shortlist_board_frame"):
            return
        for child in self.shortlist_board_frame.winfo_children():
            child.destroy()
        self.shortlist_board_cards = []

        intro = tk.Frame(
            self.shortlist_board_frame,
            bg=PALETTE["panel_alt"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        intro.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            intro,
            text="Shortlist Board",
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            font=("Segoe UI Semibold", 13),
        ).pack(anchor="w")
        tk.Label(
            intro,
            text="Use the cards below to spot the cleanest saved elections, tag them, and send any two picks straight into compare.",
            bg=PALETTE["panel_alt"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 9),
            wraplength=860,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        diagnostics = shortlist_batch_diagnostics(self.shortlist)
        summary_wrap = tk.Frame(self.shortlist_board_frame, bg=PALETTE["app_bg"])
        summary_wrap.pack(fill=tk.X, pady=(0, 8))
        self._render_shortlist_summary_cards(summary_wrap, diagnostics)

        if not self.shortlist:
            empty = tk.Frame(
                self.shortlist_board_frame,
                bg=PALETTE["panel_alt"],
                highlightbackground=PALETTE["panel_line"],
                highlightthickness=1,
                padx=12,
                pady=14,
            )
            empty.pack(fill=tk.X)
            tk.Label(empty, text="No shortlisted windows yet.", bg=PALETTE["panel_alt"], fg=PALETTE["accent_dark"], font=("Georgia", 10, "bold")).pack(anchor="w")
            tk.Label(
                empty,
                text=(
                    "Run Find Best, click a candidate card, then press Shortlist or Save Pick. "
                    "Once saved, this board will rank candidates by score, confidence, cleanliness, steadiness, and tags."
                ),
                bg=PALETTE["panel_alt"],
                fg=PALETTE["text"],
                font=("Segoe UI", 8),
                wraplength=320,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(5, 0))
            tk.Label(
                empty,
                text="Good tags to start with: best for launch, backup, client-safe, needs review.",
                bg=PALETTE["panel_alt"],
                fg=PALETTE["muted"],
                font=("Segoe UI", 8),
                wraplength=320,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(5, 0))
            return

        for rank, entry in enumerate(self.shortlist, start=1):
            self._render_shortlist_entry_card(self.shortlist_board_frame, entry, rank)

        self.shortlist_board_canvas.update_idletasks()
        self.shortlist_board_canvas.configure(scrollregion=self.shortlist_board_canvas.bbox("all"))

    def _render_shortlist_summary_cards(self, parent: tk.Frame, diagnostics: dict[str, object]) -> None:
        parent.columnconfigure((0, 1, 2, 3), weight=1)

        def compact_name(entry: dict[str, object] | None) -> str:
            if not entry:
                return "n/a"
            return f"{entry.get('formattedTime', 'time unavailable')} | {entry.get('objective', 'Objective')}"

        summary_cards = [
            ("Best Overall", compact_name((diagnostics.get("topOverall") or [None])[0]), shortlist_score_band(int((diagnostics.get("averages") or {}).get("score", 0)))),
            ("Cleanest", compact_name((diagnostics.get("topCleanest") or [None])[0]), shortlist_metric_band("cleanliness", int((diagnostics.get("averages") or {}).get("cleanliness", 0)))),
            ("Highest Confidence", compact_name((diagnostics.get("topConfident") or [None])[0]), shortlist_metric_band("confidence", int((diagnostics.get("averages") or {}).get("confidence", 0)))),
            ("Steadiest", compact_name((diagnostics.get("topSteady") or [None])[0]), shortlist_metric_band("volatility", int((diagnostics.get("averages") or {}).get("volatility", 0)))),
        ]
        for index, (label, body, colors) in enumerate(summary_cards):
            bg_color, accent_color = colors
            card = tk.Frame(parent, bg=bg_color, highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=10, pady=9)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 4, 0), pady=0)
            tk.Frame(card, bg=accent_color, height=4).pack(fill=tk.X, pady=(0, 7))
            tk.Label(card, text=label, bg=bg_color, fg=accent_color, font=("Segoe UI Semibold", 9)).pack(anchor="w")
            tk.Label(card, text=body, bg=bg_color, fg=PALETTE["text"], font=("Segoe UI", 9), justify="left", wraplength=180).pack(anchor="w", pady=(4, 0))

    def _render_shortlist_entry_card(self, parent: tk.Frame, entry: dict[str, object], rank: int) -> None:
        score_bg, score_accent = shortlist_score_band(int(entry.get("score", 0)))
        card = tk.Frame(parent, bg=PALETTE["panel_alt"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=12, pady=10)
        card.pack(fill=tk.X, pady=(0, 8))
        self.shortlist_board_cards.append(card)
        tk.Frame(card, bg=score_accent, height=4).pack(fill=tk.X, pady=(0, 8))

        header = tk.Frame(card, bg=PALETTE["panel_alt"])
        header.pack(fill=tk.X)
        header.columnconfigure(1, weight=1)
        tk.Label(header, text=f"#{rank}", bg=score_bg, fg=score_accent, font=("Segoe UI Semibold", 11), padx=8, pady=4).grid(row=0, column=0, sticky="w", padx=(0, 8))
        title_block = tk.Frame(header, bg=PALETTE["panel_alt"])
        title_block.grid(row=0, column=1, sticky="ew")
        tk.Label(title_block, text=str(entry.get("formattedTime", "time unavailable")), bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI Semibold", 11)).pack(anchor="w")
        tk.Label(title_block, text=f"{entry.get('title', 'Electional window')} | {entry.get('objective', 'Objective')}", bg=PALETTE["panel_alt"], fg=PALETTE["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))
        compare_text = f"A {'selected' if self.shortlist_compare_a_id == entry.get('id') else 'set'} | B {'selected' if self.shortlist_compare_b_id == entry.get('id') else 'set'}"
        tk.Label(header, text=compare_text, bg=PALETTE["panel_alt"], fg=PALETTE["accent_dark"], font=("Segoe UI Semibold", 8)).grid(row=0, column=2, sticky="e")

        metrics = tk.Frame(card, bg=PALETTE["panel_alt"])
        metrics.pack(fill=tk.X, pady=(8, 6))
        metric_defs = (
            ("Score", int(entry.get("score", 0)), shortlist_score_band(int(entry.get("score", 0)))),
            ("Conf", int(entry.get("confidence", 0)), shortlist_metric_band("confidence", int(entry.get("confidence", 0)))),
            ("Clean", int(entry.get("cleanliness", 0)), shortlist_metric_band("cleanliness", int(entry.get("cleanliness", 0)))),
            ("Read", int(entry.get("readiness", 0)), shortlist_metric_band("readiness", int(entry.get("readiness", 0)))),
            ("Vol", int(entry.get("volatility", 0)), shortlist_metric_band("volatility", int(entry.get("volatility", 0)))),
        )
        for index, (label, value, colors) in enumerate(metric_defs):
            bg_color, accent_color = colors
            metric = tk.Frame(metrics, bg=bg_color, highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=7, pady=5)
            metric.grid(row=0, column=index, sticky="ew", padx=(0, 5 if index < len(metric_defs) - 1 else 0))
            metrics.columnconfigure(index, weight=1)
            tk.Label(metric, text=label, bg=bg_color, fg=PALETTE["muted"], font=("Segoe UI Semibold", 8)).pack(anchor="w")
            tk.Label(metric, text=str(value), bg=bg_color, fg=accent_color, font=("Segoe UI Semibold", 12)).pack(anchor="w")

        meta = tk.Frame(card, bg=PALETTE["panel_alt"])
        meta.pack(fill=tk.X)
        tk.Label(meta, text=f"{entry.get('location', 'n/a')} | {entry.get('timezone', 'n/a')}", bg=PALETTE["panel_alt"], fg=PALETTE["muted"], font=("Segoe UI", 9)).pack(anchor="w")
        tk.Label(meta, text=f"Moon: {entry.get('lunarPhase', 'n/a')}", bg=PALETTE["panel_alt"], fg=PALETTE["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        tags = normalize_shortlist_tags(entry.get("tags", []))
        tag_wrap = tk.Frame(card, bg=PALETTE["panel_alt"])
        tag_wrap.pack(fill=tk.X, pady=(7, 0))
        tk.Label(tag_wrap, text="Tags", bg=PALETTE["panel_alt"], fg=PALETTE["accent"], font=("Segoe UI Semibold", 9)).pack(anchor="w")
        tag_chip_row = tk.Frame(tag_wrap, bg=PALETTE["panel_alt"])
        tag_chip_row.pack(fill=tk.X, pady=(4, 4))
        if tags:
            for tag in tags:
                chip = tk.Frame(tag_chip_row, bg=PALETTE["chip"], highlightbackground=PALETTE["chip_line"], highlightthickness=1, padx=6, pady=3)
                chip.pack(side=tk.LEFT, padx=(0, 6))
                tk.Label(chip, text=tag, bg=PALETTE["chip"], fg=PALETTE["accent_dark"], font=("Segoe UI Semibold", 8)).pack(side=tk.LEFT)
                tk.Button(
                    chip,
                    text="x",
                    command=lambda entry_id=str(entry.get("id")), tag_name=tag: self._remove_tag_from_shortlist_entry(entry_id, tag_name),
                    bg=PALETTE["chip"],
                    fg=PALETTE["muted"],
                    relief="flat",
                    bd=0,
                    padx=3,
                    pady=0,
                    font=("Segoe UI Semibold", 7),
                ).pack(side=tk.LEFT)
        else:
            tk.Label(tag_chip_row, text="No tags yet.", bg=PALETTE["panel_alt"], fg=PALETTE["muted"], font=("Segoe UI", 8)).pack(anchor="w")

        controls = tk.Frame(tag_wrap, bg=PALETTE["panel_alt"])
        controls.pack(fill=tk.X)
        tag_value = tk.StringVar(value=SHORTLIST_TAG_CHOICES[0])
        tag_combo = ttk.Combobox(controls, values=SHORTLIST_TAG_CHOICES, textvariable=tag_value, state="normal", width=18)
        tag_combo.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Load Chart", command=lambda entry_id=str(entry.get("id")): self._load_shortlist_entry(entry_id)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Add Tag", command=lambda entry_id=str(entry.get("id")), var=tag_value: self._add_tag_to_shortlist_entry(entry_id, var.get())).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Set A", command=lambda entry_id=str(entry.get("id")): self._set_shortlist_compare_slot(entry_id, "A")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Set B", command=lambda entry_id=str(entry.get("id")): self._set_shortlist_compare_slot(entry_id, "B")).pack(side=tk.LEFT)

        note = str(entry.get("note", "")).strip()
        if note:
            tk.Label(card, text=note, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 9), wraplength=860, justify="left").pack(anchor="w", pady=(8, 0))

    def _current_report_text(self) -> str:
        report = build_report_text(self.selected_window, self.current_windows, self.current_location)
        analysis = ""
        if self.selected_window and self.current_location:
            analysis = "\n\n" + build_analysis_page(
                self.selected_window,
                self.current_windows,
                self.current_location,
                self.current_aspect_highlights,
                self.current_search_summary,
                self.current_rejection_summary,
            )
        if self.input_snapshot and self.selected_window:
            state = (
                "Chart State\n"
                f"Search start: {self.input_snapshot['formattedTime']}\n"
                f"Displayed chart: {self.displayed_chart_source} at {self.selected_window['formattedTime']}\n"
                f"{selection_offset_label(self.input_snapshot, self.selected_window)}\n\n"
            )
            return state + report + analysis
        return report + analysis

    def _show_quick_help(self) -> None:
        body = "\n".join(
            [
                "Electional Software Help",
                "",
                "Workflow",
                "1. Set the search start date, time, and location on the left.",
                "2. Choose sidereal zodiac, house system, objective, and electional model.",
                "3. Calculate to rank candidate windows.",
                "4. Select a candidate card to inspect it, or use it as the new input time.",
                "",
                "State Clarity",
                "- Search Start is the original input chart.",
                "- Selected Window is the ranked candidate currently drawn on the wheel.",
                "- Difference shows how far the selected window is from the search start.",
                "- Previous/Next Window or Alt+Left/Alt+Right steps through ranked candidates.",
                "- Focus Wheel or F11 hides the side panels for chart inspection.",
                "",
                "Useful Buttons",
                "- Day Report opens the ranked best-aspects-through-the-day search report.",
                "- Search Page shows scan filters, rejected windows, and candidate-window diagnostics.",
                "- Preferences applies calculation/search defaults in one place.",
                "- Chart Data opens the calculated positions, houses, Lots, and fixed-star contacts.",
                "- Void Course, Fixed Stars, and Heliacal Search open focused screening tools.",
                "- Save Location stores a reusable custom place in the preset dropdown.",
            ]
        )
        self._show_text_dialog("Electional Software Help", body)

    def _show_unknown_action(self, feature_name: str) -> None:
        self.status_var.set(f"No action is wired for {feature_name}.")
        messagebox.showinfo(feature_name, f"No desktop action is wired for {feature_name}. Use Ask to open the help panel or report this missing button.")

    def _show_preferences_dialog(self) -> None:
        self._set_workspace_page("Settings")
        dialog = tk.Toplevel(self.root)
        dialog.title("Preferences")
        dialog.geometry("620x690")
        dialog.configure(bg=PALETTE["app_bg"])
        dialog.transient(self.root)

        header = tk.Frame(dialog, bg=PALETTE["top_bar"], padx=14, pady=10)
        header.pack(fill=tk.X)
        tk.Label(header, text="Preferences", bg=PALETTE["top_bar"], fg="white", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(
            header,
            text="Apply calculation, search, and workflow defaults without hunting through panels.",
            bg=PALETTE["top_bar"],
            fg="#dce9f3",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(3, 0))

        body = tk.Frame(dialog, bg=PALETTE["panel"], padx=14, pady=12)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        zodiac_var = tk.StringVar(value=self.zodiac_system_var.get())
        house_var = tk.StringVar(value=self.house_system_var.get())
        objective_var = tk.StringVar(value=self.objective_var.get())
        preset_var = tk.StringVar(value=self.preset_var.get())
        point_set_var = tk.StringVar(value=self.point_set_var.get())
        page_mode_var = tk.StringVar(value=self.page_mode_var.get())
        right_panel_theme_var = tk.StringVar(value=self.right_panel_theme_var.get())
        wheel_view_preset_var = tk.StringVar(value=self.wheel_view_preset_var.get())
        home_choices = [HOME_LOCATION_DEFAULT_LABEL, *self.location_names]
        if self.home_location_name and self.home_location_name not in home_choices:
            home_choices.append(self.home_location_name)
        home_var = tk.StringVar(value=self.home_location_name or HOME_LOCATION_DEFAULT_LABEL)
        scan_var = tk.StringVar(value=self.scan_hours_var.get())
        step_var = tk.StringVar(value=self.step_minutes_var.get())
        minimum_var = tk.StringVar(value=self.minimum_score_var.get())
        minimum_fit_var = tk.StringVar(value=self.minimum_fit_var.get())
        minimum_confidence_var = tk.StringVar(value=self.minimum_confidence_var.get())
        minimum_cleanliness_var = tk.StringVar(value=self.minimum_cleanliness_var.get())
        maximum_volatility_var = tk.StringVar(value=self.maximum_volatility_var.get())
        max_results_var = tk.StringVar(value=self.max_results_var.get())
        search_quality_mode_var = tk.StringVar(value=self.search_quality_mode_var.get())
        avoid_major_stress_var = tk.BooleanVar(value=self.avoid_major_stress_var.get())
        require_applying_support_var = tk.BooleanVar(value=self.require_applying_support_var.get())
        require_angular_benefic_var = tk.BooleanVar(value=self.require_angular_benefic_var.get())
        avoid_angular_malefics_var = tk.BooleanVar(value=self.avoid_angular_malefics_var.get())
        require_moon_non_void_var = tk.BooleanVar(value=self.require_moon_non_void_var.get())
        avoid_objective_antipatterns_var = tk.BooleanVar(value=self.avoid_objective_antipatterns_var.get())

        calculation = ttk.LabelFrame(body, text="Calculation Defaults", style="Panel.TLabelframe", padding=10)
        calculation.pack(fill=tk.X)
        self._dialog_combo_row(calculation, "Zodiac system", zodiac_var, list(ZODIAC_SYSTEM_NAMES))
        self._dialog_combo_row(calculation, "House system", house_var, list(HOUSE_SYSTEM_NAMES))
        self._dialog_combo_row(calculation, "Objective", objective_var, list(OBJECTIVES))
        self._dialog_combo_row(calculation, "Electional model", preset_var, [preset.name for preset in ELECTIONAL_PRESETS])

        workflow = ttk.LabelFrame(body, text="Workflow Defaults", style="Panel.TLabelframe", padding=10)
        workflow.pack(fill=tk.X, pady=(10, 0))
        self._dialog_combo_row(workflow, "Page mode", page_mode_var, list(PAGE_MODE_NAMES))
        self._dialog_combo_row(workflow, "Point configuration", point_set_var, list(POINT_SET_NAMES))
        self._dialog_combo_row(workflow, "Wheel presentation", right_panel_theme_var, list(RIGHT_PANEL_THEME_NAMES))
        self._dialog_combo_row(workflow, "Wheel preset", wheel_view_preset_var, list(WHEEL_VIEW_PRESET_NAMES))
        self._dialog_combo_row(workflow, "Home location", home_var, home_choices)

        search = ttk.LabelFrame(body, text="Search Defaults", style="Panel.TLabelframe", padding=10)
        search.pack(fill=tk.X, pady=(10, 0))
        search.columnconfigure(0, weight=1)
        search.columnconfigure(1, weight=1)
        mode_frame = ttk.Frame(search, style="Panel.TFrame")
        mode_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(mode_frame, text="Search mode", style="Small.TLabel").pack(anchor="w", pady=(0, 3))
        ttk.Combobox(mode_frame, textvariable=search_quality_mode_var, values=list(SEARCH_QUALITY_MODE_NAMES), state="readonly").pack(fill=tk.X, ipady=5)
        self._dialog_entry_row(search, "Scan hours", scan_var, 1, 0)
        self._dialog_entry_row(search, "Step minutes", step_var, 1, 1)
        self._dialog_entry_row(search, "Minimum score", minimum_var, 2, 0)
        self._dialog_entry_row(search, "Minimum fit", minimum_fit_var, 2, 1)
        self._dialog_entry_row(search, "Minimum confidence", minimum_confidence_var, 3, 0)
        self._dialog_entry_row(search, "Minimum cleanliness", minimum_cleanliness_var, 3, 1)
        self._dialog_entry_row(search, "Maximum volatility", maximum_volatility_var, 4, 0)
        self._dialog_entry_row(search, "Max results", max_results_var, 4, 1)
        ttk.Checkbutton(search, text="Avoid major stress", variable=avoid_major_stress_var).grid(row=5, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        ttk.Checkbutton(search, text="Require applying support", variable=require_applying_support_var).grid(row=5, column=1, sticky="w", padx=(6, 0), pady=(0, 8))
        ttk.Checkbutton(search, text="Require angular benefic", variable=require_angular_benefic_var).grid(row=6, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        ttk.Checkbutton(search, text="Avoid angular malefics", variable=avoid_angular_malefics_var).grid(row=6, column=1, sticky="w", padx=(6, 0), pady=(0, 8))
        ttk.Checkbutton(search, text="Keep Moon non-void", variable=require_moon_non_void_var).grid(row=7, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        ttk.Checkbutton(search, text="Avoid objective anti-patterns", variable=avoid_objective_antipatterns_var).grid(row=7, column=1, sticky="w", padx=(6, 0), pady=(0, 8))

        actions = tk.Frame(dialog, bg=PALETTE["app_bg"], padx=12, pady=10)
        actions.pack(fill=tk.X)
        ttk.Button(
            actions,
            text="Sidereal Default",
            command=lambda: self._apply_preferences(
                dialog,
                get_zodiac_system(DEFAULT_ZODIAC_SYSTEM_ID).name,
                get_house_system(DEFAULT_HOUSE_SYSTEM_ID).name,
                objective_var.get(),
                preset_var.get(),
                PAGE_MODE_LABELS["wheel"],
                get_point_set("full-electional").name,
                RIGHT_PANEL_THEME_LABELS["classic-natal"],
                WHEEL_VIEW_PRESET_LABELS["full-classic"],
                home_var.get(),
                scan_var.get(),
                step_var.get(),
                minimum_var.get(),
                minimum_fit_var.get(),
                minimum_confidence_var.get(),
                minimum_cleanliness_var.get(),
                maximum_volatility_var.get(),
                max_results_var.get(),
                search_quality_mode_var.get(),
                avoid_major_stress_var.get(),
                require_applying_support_var.get(),
                require_angular_benefic_var.get(),
                avoid_angular_malefics_var.get(),
                require_moon_non_void_var.get(),
                avoid_objective_antipatterns_var.get(),
            ),
        ).pack(side=tk.LEFT)
        ttk.Button(actions, text="Reset Locations", command=lambda: (dialog.destroy(), self._reset_locations())).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(
            actions,
            text="Apply",
            command=lambda: self._apply_preferences(
                dialog,
                zodiac_var.get(),
                house_var.get(),
                objective_var.get(),
                preset_var.get(),
                page_mode_var.get(),
                point_set_var.get(),
                right_panel_theme_var.get(),
                wheel_view_preset_var.get(),
                home_var.get(),
                scan_var.get(),
                step_var.get(),
                minimum_var.get(),
                minimum_fit_var.get(),
                minimum_confidence_var.get(),
                minimum_cleanliness_var.get(),
                maximum_volatility_var.get(),
                max_results_var.get(),
                search_quality_mode_var.get(),
                avoid_major_stress_var.get(),
                require_applying_support_var.get(),
                require_angular_benefic_var.get(),
                avoid_angular_malefics_var.get(),
                require_moon_non_void_var.get(),
                avoid_objective_antipatterns_var.get(),
            ),
        ).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)

    def _dialog_combo_row(self, parent: tk.Widget, label: str, variable: tk.StringVar, values: list[str]) -> None:
        ttk.Label(parent, text=label, style="Small.TLabel").pack(anchor="w", pady=(8, 3))
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
        combo.pack(fill=tk.X, ipady=5)

    def _dialog_entry_row(self, parent: tk.Widget, label: str, variable: tk.StringVar, row: int, column: int) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame")
        frame.grid(row=row, column=column, sticky="ew", padx=(0, 6) if column == 0 else (6, 0), pady=(0, 8))
        ttk.Label(frame, text=label, style="Small.TLabel").pack(anchor="w", pady=(0, 3))
        tk.Entry(frame, textvariable=variable, bg=PALETTE["panel_alt"], relief=tk.SOLID, bd=1, font=("Segoe UI", 10, "bold")).pack(fill=tk.X, ipady=6)

    def _apply_preferences(
        self,
        dialog: tk.Toplevel,
        zodiac: str,
        house: str,
        objective: str,
        preset: str,
        page_mode: str,
        point_set_name: str,
        right_panel_theme: str,
        wheel_view_preset: str,
        home_location_name: str,
        scan_hours: str,
        step_minutes: str,
        minimum_score: str,
        minimum_fit: str,
        minimum_confidence: str,
        minimum_cleanliness: str,
        maximum_volatility: str,
        max_results: str,
        search_quality_mode: str,
        avoid_major_stress: bool,
        require_applying_support: bool,
        require_angular_benefic: bool,
        avoid_angular_malefics: bool,
        require_moon_non_void: bool,
        avoid_objective_antipatterns: bool,
    ) -> None:
        errors = validate_search_inputs(
            scan_hours,
            step_minutes,
            minimum_score,
            max_results,
            minimum_fit,
            minimum_confidence,
            minimum_cleanliness,
            maximum_volatility,
        )
        if errors:
            messagebox.showerror("Preference validation failed", "Fix these search defaults:\n" + "\n".join(f"- {error}" for error in errors))
            return
        self.zodiac_system_var.set(get_zodiac_system(zodiac).name)
        self.house_system_var.set(get_house_system(house).name)
        self.objective_var.set(objective if objective in OBJECTIVES else OBJECTIVES[0])
        self.preset_var.set(preset if preset in self.presets_by_name else ELECTIONAL_PRESETS[1].name)
        self.page_mode_var.set(page_mode if page_mode in PAGE_MODE_NAMES else PAGE_MODE_LABELS["wheel"])
        self.point_set_var.set(get_point_set(point_set_name).name)
        self.right_panel_theme_var.set(right_panel_theme if right_panel_theme in RIGHT_PANEL_THEME_NAMES else RIGHT_PANEL_THEME_LABELS["classic-natal"])
        self.wheel_view_preset_var.set(wheel_view_preset if wheel_view_preset in WHEEL_VIEW_PRESET_NAMES else WHEEL_VIEW_PRESET_LABELS["full-classic"])
        self._apply_wheel_view_preset(self._current_wheel_preset_id(), save=False)
        chosen_home = home_location_name.strip()
        if chosen_home == HOME_LOCATION_DEFAULT_LABEL:
            self.home_location_name = None
            save_home_location_name(None)
        else:
            self.home_location_name = chosen_home
            save_home_location_name(chosen_home)
        self.scan_hours_var.set(scan_hours)
        self.step_minutes_var.set(step_minutes)
        self.minimum_score_var.set(minimum_score)
        self.minimum_fit_var.set(minimum_fit)
        self.minimum_confidence_var.set(minimum_confidence)
        self.minimum_cleanliness_var.set(minimum_cleanliness)
        self.maximum_volatility_var.set(maximum_volatility)
        self.max_results_var.set(max_results)
        self.search_quality_mode_var.set(search_quality_mode if search_quality_mode in SEARCH_QUALITY_MODE_NAMES else SEARCH_QUALITY_MODE_NAMES[0])
        self.avoid_major_stress_var.set(avoid_major_stress)
        self.require_applying_support_var.set(require_applying_support)
        self.require_angular_benefic_var.set(require_angular_benefic)
        self.avoid_angular_malefics_var.set(avoid_angular_malefics)
        self.require_moon_non_void_var.set(require_moon_non_void)
        self.avoid_objective_antipatterns_var.set(avoid_objective_antipatterns)
        self._sync_aspects_to_preset()
        self._update_search_summary()
        self._refresh_location_status()
        self._apply_current_theme()
        self._apply_page_mode(self._current_page_mode_id(), save=False)
        dialog.destroy()
        self.status_var.set("Preferences applied.")
        self.calculate(show_input_chart=True)

    def _selected_aspect_ids(self) -> list[str]:
        return [aspect for aspect, var in self.aspect_vars.items() if var.get()]

    def _aspect_profile_names(self) -> list[str]:
        return [profile.name for profile in self.aspect_profiles]

    def _profile_by_name(self, name: str) -> AspectProfile:
        for profile in self.aspect_profiles:
            if profile.name == name:
                return profile
        return self.aspect_profiles[0] if self.aspect_profiles else self.active_aspect_profile

    def _active_aspect_definitions(self) -> tuple[Aspect, ...]:
        return self.active_aspect_profile.aspects

    def _aspect_profile_changed(self, _event: object | None = None) -> None:
        previous = {aspect_id: var.get() for aspect_id, var in self.aspect_vars.items()}
        self.active_aspect_profile = self._profile_by_name(self.aspect_profile_var.get())
        self.aspect_profile_var.set(self.active_aspect_profile.name)
        self._refresh_aspect_focus_controls(previous)
        self._refresh_left_status_chips()
        self._save_session()
        self.status_var.set(f"Aspect profile active: {self.active_aspect_profile.name}.")

    def _refresh_aspect_focus_controls(
        self,
        selections: Mapping[str, object] | None = None,
        preset: object | None = None,
    ) -> None:
        if not hasattr(self, "aspect_focus_options_frame"):
            return
        for child in self.aspect_focus_options_frame.winfo_children():
            child.destroy()
        preset = preset or self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        selection_map = selections if isinstance(selections, Mapping) else {}
        self.aspect_vars = {}
        for aspect in self.active_aspect_profile.aspects:
            if aspect.id in selection_map:
                checked = bool(selection_map[aspect.id]) and aspect.enabled
            else:
                checked = bool(aspect.enabled and (aspect.id in preset.aspect_ids or not aspect.built_in))
            var = tk.BooleanVar(value=checked)
            self.aspect_vars[aspect.id] = var
            label = (
                f"{aspect.glyph or aspect.abbreviation}  {aspect.name}  "
                f"{float(aspect.angle):g}deg / orb {float(aspect.default_orb):g}deg"
            )
            check = ttk.Checkbutton(self.aspect_focus_options_frame, text=label, variable=var)
            check.pack(anchor="w", pady=2)
            if not aspect.enabled:
                check.state(["disabled"])
        if not self.aspect_vars:
            tk.Label(
                self.aspect_focus_options_frame,
                text="No aspect definitions are available. Open Aspect Config to restore the built-ins.",
                bg=PALETTE["panel_alt"],
                fg=PALETTE["stress"],
                font=("Segoe UI", 8, "bold"),
                wraplength=265,
                justify=tk.LEFT,
            ).pack(fill=tk.X)

    def _show_text_dialog(self, title: str, body: str) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("720x560")
        dialog.configure(bg=PALETTE["app_bg"])
        dialog.transient(self.root)
        header = tk.Frame(dialog, bg=PALETTE["top_bar"], padx=12, pady=8)
        header.pack(fill=tk.X)
        tk.Label(header, text=title, bg=PALETTE["top_bar"], fg="white", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        text = tk.Text(
            dialog,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Consolas", 10),
            padx=12,
            pady=12,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        text.insert("1.0", body)
        text.configure(state=tk.DISABLED)
        actions = tk.Frame(dialog, bg=PALETTE["app_bg"], padx=12)
        actions.pack(fill=tk.X, pady=(0, 12))
        ttk.Button(actions, text="Copy", command=lambda: self._copy_dialog_text(body, title)).pack(side=tk.LEFT)
        ttk.Button(actions, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    def _copy_dialog_text(self, body: str, title: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(body)
        self.status_var.set(f"Copied {title} to clipboard.")

    def _show_bounds_dialog(self) -> None:
        body = "\n".join(dignity_table_lines())
        self._show_text_dialog("Essential Dignities / Bounds Reference", body)
        self.status_var.set("Opened essential dignity reference.")

    def _show_systems_dialog(self) -> None:
        self._show_text_dialog("Astrology Systems", "\n".join(system_reference_lines()))
        self.status_var.set("Opened astrology system reference.")

    def _show_lots_reference_dialog(self) -> None:
        self._show_text_dialog("Arabic Lots / Parts", "\n".join(lot_reference_lines()))
        self.status_var.set("Opened Lots reference.")

    def _show_fixed_stars_dialog(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("Fixed Stars", "Calculate a chart before checking fixed-star contacts.")
            return
        stars = self.selected_window.get("fixedStars", [])
        contacts = self.selected_window.get("fixedStarContacts", [])
        star_lines = [
            f"{star['name']:<16} {format_position(star):<15} {star['nature']:<12} mag {float(star['magnitude']):>5.2f}"
            for star in stars
        ]
        contact_lines = [
            f"{format_fixed_star_contact(contact)}\n  {contact.get('note', '')}"
            for contact in contacts
        ]
        lines = [
            "Fixed Stars",
            f"Chart time: {self.selected_window['formattedTime']}",
            f"Zodiac: {self.selected_window['zodiacSystem'].name}",
            "",
            "Contacts within diagnostic star orb",
            *(contact_lines or ["No fixed-star conjunctions within the diagnostic star orb."]),
            "",
            "Reference Positions",
            *star_lines,
            "",
            "Source note: curated from Astrolog 7.80's Swiss Ephemeris fixed-star file (sefstars.txt).",
        ]
        self._show_text_dialog("Fixed Stars", "\n".join(lines))
        self.status_var.set("Opened fixed-star contacts.")

    def _show_heliacal_dialog(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("Heliacal Search", "Calculate a chart before checking solar elongation.")
            return
        lines = [
            "Solar Elongation / Heliacal Screening",
            f"Chart time: {self.selected_window['formattedTime']}",
            "",
            *solar_elongation_summary(self.selected_window),
            "",
            "Note: this is a diagnostic visibility screen based on solar separation and morning/evening side.",
            "A full heliacal visibility model still needs horizon altitude, latitude, magnitude, and twilight rules.",
        ]
        self._show_text_dialog("Heliacal Search", "\n".join(lines))
        self.status_var.set("Opened solar elongation screening.")

    def _show_astro_mapping_dialog(self) -> None:
        self._set_workspace_page("Map")
        if not self.selected_window or not self.current_location:
            messagebox.showinfo("Astro Mapping", "Calculate a chart before opening astro mapping.")
            return
        angular_bodies = [
            (
                f"- {planet['name']}: {format_position(planet)} "
                f"near {planet['closestAngle']['shortName']} ({float(planet['closestAngle']['distance']):.1f} deg), "
                f"House {planet.get('house', 'n/a')}"
            )
            for planet in self.selected_window.get("positions", [])
            if isinstance(planet, dict) and planet.get("isAngular")
        ]
        angle_lines = [
            f"- {angle['shortName']}: {format_angle(angle)}"
            for angle in self.selected_window.get("angles", [])
            if isinstance(angle, dict)
        ]
        location = self.current_location
        lines = [
            "Astro Mapping",
            f"Location: {location.name}",
            f"Coordinates: {location.latitude:.4f}, {location.longitude:.4f}",
            f"Timezone: {location.timezone}",
            f"Chart time: {self.selected_window['formattedTime']}",
            "",
            "Angles",
            *(angle_lines or ["- Angles unavailable."]),
            "",
            "Angular Bodies",
            *(angular_bodies or ["- No calculated planets are within the angular orb in this chart."]),
            "",
            "Use this as the local mapping readout: it shows what is rising, culminating, setting, or anti-culminating at the selected place and time.",
        ]
        self._show_text_dialog("Astro Mapping", "\n".join(lines))
        self.status_var.set("Opened local astro mapping readout.")

    def _show_score_audit_dialog(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("Score Audit", "Calculate a chart before opening score audit.")
            return
        lines = [
            "Score Audit",
            f"Time: {self.selected_window.get('formattedTime', 'n/a')}",
            f"Score: {self.selected_window.get('score', 'n/a')}",
            "",
            "Breakdown",
            format_score_breakdown(self.selected_window),
            "",
            "Point Accounting",
            *score_accounting_lines(self.selected_window),
            "",
            "Evaluation",
            *score_evaluation_lines(self.selected_window),
            "",
            "Diagnostics",
            *score_diagnostic_lines(self.selected_window),
            "",
            "Reason Lines",
            *score_reason_lines(self.selected_window),
        ]
        self._show_text_dialog("Score Audit", "\n".join(lines))
        self.status_var.set("Opened score audit.")

    def _show_factor_map_dialog(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("Factor Map", "Calculate a chart before opening factor map.")
            return
        lines = factor_explorer_lines(self.selected_window, self.input_snapshot)
        self._show_text_dialog("Factor Map", "\n".join(lines))
        self.status_var.set("Opened factor map.")

    def _show_cache_stats_dialog(self) -> None:
        cache = snapshot_cache_info()
        lines = [
            "Search Cache Stats",
            f"- Hits: {cache.get('hits', 0)}",
            f"- Misses: {cache.get('misses', 0)}",
            f"- Stored snapshots: {cache.get('currsize', 0)} / {cache.get('maxsize', 0)}",
            "",
            "Current Search",
            f"- Summary: {self.current_search_summary or 'No search calculated yet.'}",
            f"- Evaluated windows: {self.current_searched_window_count}",
            "",
            "Actions",
            "- Use Tools > Clear Cache to reset stored chart snapshots before comparing fresh calculation speed.",
            "",
            "Note: repeated searches with the same time, location, objective, systems, model, and aspects reuse cached chart snapshots.",
        ]
        self._show_text_dialog("Cache Stats", "\n".join(lines))
        self.status_var.set("Opened search cache stats.")

    def _clear_search_cache(self) -> None:
        before = snapshot_cache_info()
        clear_snapshot_cache()
        after = snapshot_cache_info()
        self.status_var.set(f"Cleared {before.get('currsize', 0)} cached chart snapshot(s).")
        self._log_event(f"Cleared search cache: {before.get('currsize', 0)} stored snapshots removed")
        lines = [
            "Search Cache Cleared",
            f"- Removed snapshots: {before.get('currsize', 0)}",
            f"- Hits before clear: {before.get('hits', 0)}",
            f"- Misses before clear: {before.get('misses', 0)}",
            f"- Stored snapshots now: {after.get('currsize', 0)} / {after.get('maxsize', 0)}",
            "",
            "Next calculation or search will rebuild the needed snapshots.",
        ]
        self._show_text_dialog("Clear Cache", "\n".join(lines))

    def _show_void_course_dialog(self) -> None:
        if not self.selected_window or not self.current_location:
            messagebox.showinfo("Void Course", "Calculate a chart before checking the Moon.")
            return
        lines = [
            "Void of Course Moon Scan",
            f"Start: {self.selected_window['formattedTime']}",
            f"Location: {self.current_location.name}",
            f"Selected aspects: {', '.join(self._selected_aspect_ids()) or 'none'}",
            f"System: {self.selected_window['zodiacSystem'].name} / {self.selected_window['houseSystem'].name}",
            "",
            *moon_void_course_summary(
                self.selected_window,
                self.current_location,
                self._selected_aspect_ids(),
                self._active_aspect_definitions(),
            ),
        ]
        self._show_text_dialog("Void of Course Moon", "\n".join(lines))
        self.status_var.set("Opened void-of-course Moon scan.")

    def _show_chart_inspector(self) -> None:
        if not self.selected_window or not self.current_location:
            messagebox.showinfo("Chart Data", "Calculate a chart before opening chart data.")
            return
        positions = "\n".join(
            (
                f"{planet['name']:<8} {format_position(planet):<16} "
                f"H{planet['house']:<2} {planet['dignity']['label']:<10} "
                f"Bound {str(planet['dignity'].get('boundLord', '-')):<8} "
                f"{format_motion_summary(planet):<24} "
                f"Angle {planet['closestAngle']['shortName']} {planet['closestAngle']['distance']:.1f} deg"
            )
            for planet in self.selected_window["positions"]
        )
        angles = "\n".join(format_angle(angle) for angle in self.selected_window["angles"])
        house_cusps = "\n".join(
            f"House {cusp['house']:<2} {format_position(cusp)}" for cusp in self.selected_window.get("houseCusps", [])
        )
        lots = "\n".join(
            f"{lot['name']:<18} {format_position(lot):<16} H{lot['house']:<2} {lot['formula']} ({lot['sect']})"
            for lot in self.selected_window.get("lots", [])
        )
        nodes = "\n".join(
            f"{node['name']:<18} {format_position(node):<16} H{node['house']:<2} {node.get('calculation', '')}"
            for node in self.selected_window.get("lunarNodes", [])
        )
        aspects = "\n".join(f"{format_aspect_summary(aspect)} {aspect['tone']}" for aspect in self.selected_window["detectedAspects"])
        fixed_star_contacts = "\n".join(
            f"{format_fixed_star_contact(contact)}: {contact.get('note', '')}"
            for contact in self.selected_window.get("fixedStarContacts", [])
        )
        backend = self.selected_window.get("calculationBackend", {})
        notes = "\n".join(f"- {note}" for note in self.selected_window.get("calculationNotes", []))
        body = (
            "Calculated Chart Data\n"
            f"Location: {self.current_location.name}\n"
            f"Time: {self.selected_window['formattedTime']}\n"
            f"Engine: {self.selected_window['engine']}\n"
            f"Backend: {backend.get('activeEngine', self.selected_window['engine']) if isinstance(backend, dict) else self.selected_window['engine']}\n"
            f"Ephemeris path: {backend.get('ephemerisPath', 'n/a') if isinstance(backend, dict) else 'n/a'}\n"
            f"Ephemeris files: {backend.get('ephemerisFileCount', 'n/a') if isinstance(backend, dict) else 'n/a'}\n"
            f"Zodiac system: {self.selected_window['zodiacSystem'].name}\n"
            f"House system: {self.selected_window['houseSystem'].name}\n"
            f"Ayanamsha: {float(self.selected_window['ayanamsha']):.3f} deg\n"
            f"Preset: {self.selected_window['preset'].name}\n"
            f"Score: {self.selected_window['score']}\n"
            f"Lunar phase: {format_lunar_phase(self.selected_window)}\n"
            f"Score explanation: {format_score_breakdown(self.selected_window)}\n\n"
            "Angles\n"
            f"{angles}\n\n"
            "House Cusps\n"
            f"{house_cusps}\n\n"
            "Arabic Lots\n"
            f"{lots or 'No lots calculated.'}\n\n"
            "Lunar Nodes\n"
            f"{nodes or 'No lunar nodes calculated.'}\n\n"
            "Planets\n"
            f"{positions}\n\n"
            "Detected Aspects\n"
            f"{aspects or 'No selected major aspects in orb.'}\n\n"
            "Aspectarian\n"
            f"{format_aspectarian(self.selected_window)}\n\n"
            "Fixed Star Contacts\n"
            f"{fixed_star_contacts or 'No fixed-star conjunctions within the diagnostic star orb.'}\n\n"
            "Calculation Notes\n"
            f"{notes or 'No calculation warnings.'}"
        )
        self._show_text_dialog("Chart Data", body)
        self.status_var.set("Opened calculated chart data.")

    def _show_calculation_health_dialog(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("Calculation Health", "Calculate a chart before opening calculation health.")
            return
        backend = self.selected_window.get("calculationBackend", {})
        notes = self.selected_window.get("calculationNotes", [])
        cusp_sources = sorted({str(cusp.get("source", "native")) for cusp in self.selected_window.get("houseCusps", [])})
        planetary_hour = self.selected_window.get("planetaryHour", {})
        lines = [
            "Calculation Health",
            f"Time: {self.selected_window['formattedTime']}",
            f"Zodiac: {self.selected_window['zodiacSystem'].name}",
            f"House system: {self.selected_window['houseSystem'].name}",
            f"Ayanamsha: {float(self.selected_window['ayanamsha']):.3f} deg",
            "",
            "Engine",
            f"- Active: {backend.get('activeEngine', self.selected_window['engine']) if isinstance(backend, dict) else self.selected_window['engine']}",
            f"- Swiss Python available: {backend.get('swissPythonAvailable', False) if isinstance(backend, dict) else False}",
            f"- Astrolog reference available: {backend.get('astrologReferenceAvailable', False) if isinstance(backend, dict) else False}",
            f"- Astrolog executable available: {backend.get('astrologExecutableAvailable', False) if isinstance(backend, dict) else False}",
            f"- Ephemeris files: {backend.get('ephemerisFileCount', 'n/a') if isinstance(backend, dict) else 'n/a'}",
            f"- Ephemeris path: {backend.get('ephemerisPath', 'n/a') if isinstance(backend, dict) else 'n/a'}",
            "",
            "House Cusps",
            f"- Sources: {', '.join(cusp_sources) or 'native'}",
            "",
            "Planetary Hour",
            (
                f"- {planetary_hour.get('period', 'n/a')} hour {planetary_hour.get('hourNumber')} "
                f"ruled by {planetary_hour.get('hourRuler')}"
                if isinstance(planetary_hour, dict) and planetary_hour.get("available")
                else f"- Unavailable: {planetary_hour.get('reason', 'unknown') if isinstance(planetary_hour, dict) else 'unknown'}"
            ),
            "",
            "Notes",
        ]
        lines.extend(f"- {note}" for note in notes)
        if not notes:
            lines.append("- No calculation warnings.")
        self._show_text_dialog("Calculation Health", "\n".join(lines))
        self.status_var.set("Opened calculation health diagnostics.")

    def _build_left_controls(self) -> None:
        parent = getattr(self, "left_controls_parent", self.left_panel)
        card = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        card.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(card, text="WORKSPACE", style="Accent.TLabel").pack(anchor="w")
        ttk.Label(card, text="Election Setup", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Georgia", 14, "bold")).pack(anchor="w", pady=(6, 4))
        self.natal_summary = ttk.Label(card, text="", style="Small.TLabel", justify=tk.LEFT)
        self.natal_summary.pack(anchor="w")

        today = date.today()
        state = self.session_state
        self.date_var = tk.StringVar(value=str(state.get("date") or today.strftime("%Y-%m-%d")))
        self.time_var = tk.StringVar(value=str(state.get("time") or "09:00"))
        self.location_var = tk.StringVar(value=str(state.get("location_preset") or state.get("location_name")))
        self.location_name_var = tk.StringVar(value=str(state.get("location_name")))
        self.latitude_var = tk.StringVar(value=str(state.get("latitude")))
        self.longitude_var = tk.StringVar(value=str(state.get("longitude")))
        self.timezone_var = tk.StringVar(value=str(state.get("timezone")))
        self.objective_var = tk.StringVar(value=str(state.get("objective") or OBJECTIVES[0]))
        self.preset_var = tk.StringVar(value=str(state.get("preset") or ELECTIONAL_PRESETS[1].name))
        self.zodiac_system_var = tk.StringVar(value=str(state.get("zodiac_system") or get_zodiac_system(DEFAULT_ZODIAC_SYSTEM_ID).name))
        self.house_system_var = tk.StringVar(value=str(state.get("house_system") or get_house_system(DEFAULT_HOUSE_SYSTEM_ID).name))
        self.scan_hours_var = tk.StringVar(value=str(state.get("scan_hours") or DEFAULT_SCAN_HOURS))
        self.step_minutes_var = tk.StringVar(value=str(state.get("step_minutes") or DEFAULT_STEP_MINUTES))
        self.minimum_score_var = tk.StringVar(value=str(state.get("minimum_score") or DEFAULT_MINIMUM_SCORE))
        self.minimum_fit_var = tk.StringVar(value=str(state.get("minimum_fit") or DEFAULT_MINIMUM_FIT))
        self.minimum_confidence_var = tk.StringVar(value=str(state.get("minimum_confidence") or DEFAULT_MINIMUM_CONFIDENCE))
        self.minimum_cleanliness_var = tk.StringVar(value=str(state.get("minimum_cleanliness") or DEFAULT_MINIMUM_CLEANLINESS))
        self.maximum_volatility_var = tk.StringVar(value=str(state.get("maximum_volatility") or DEFAULT_MAXIMUM_VOLATILITY))
        self.max_results_var = tk.StringVar(value=str(state.get("max_results") or DEFAULT_MAX_RESULTS))
        self.search_quality_mode_var = tk.StringVar(value=str(state.get("search_quality_mode") or SEARCH_QUALITY_MODE_NAMES[0]))
        self.avoid_major_stress_var = tk.BooleanVar(value=bool(state.get("avoid_major_stress", False)))
        self.require_applying_support_var = tk.BooleanVar(value=bool(state.get("require_applying_support", False)))
        self.require_angular_benefic_var = tk.BooleanVar(value=bool(state.get("require_angular_benefic", False)))
        self.avoid_angular_malefics_var = tk.BooleanVar(value=bool(state.get("avoid_angular_malefics", False)))
        self.require_moon_non_void_var = tk.BooleanVar(value=bool(state.get("require_moon_non_void", False)))
        self.avoid_objective_antipatterns_var = tk.BooleanVar(value=bool(state.get("avoid_objective_antipatterns", False)))
        self.search_summary_var = tk.StringVar(value="")
        self.search_preset_var = tk.StringVar(value=str(state.get("search_preset") or "Custom"))
        self.validation_var = tk.StringVar(value="Validation: waiting for first calculation")

        current_box = self._left_section(parent, "Current Setup", "The displayed chart state at a glance.")
        self._build_left_status_chips(current_box)
        self._build_workflow_next_step(current_box)

        timing_box = self._left_section(parent, "Timing", "Set the exact chart time without jumping to a candidate.")
        self._labeled_entry(timing_box, "Election date", self.date_var)
        self._labeled_entry(timing_box, "Start time", self.time_var)
        self._button_row(
            timing_box,
            (
                ("Now", self._set_current_time),
                ("Exact", lambda: self.calculate(show_input_chart=True)),
            ),
            pady=(7, 0),
        )
        self._timing_adjustment_grid(timing_box)

        location_box = self._left_section(parent, "Location", "Save, reuse, or correct your working place.")
        self.location_combo = self._labeled_combo(location_box, "Location preset", self.location_var, self.location_names)
        self.location_combo.bind("<<ComboboxSelected>>", self._load_selected_location)
        self._labeled_entry(location_box, "Location name", self.location_name_var)
        coordinate_row = ttk.Frame(location_box, style="Panel.TFrame")
        coordinate_row.pack(fill=tk.X)
        coordinate_row.columnconfigure(0, weight=1)
        coordinate_row.columnconfigure(1, weight=1)
        self._labeled_entry(coordinate_row, "Latitude", self.latitude_var, compact=True, column=0)
        self._labeled_entry(coordinate_row, "Longitude", self.longitude_var, compact=True, column=1)
        self._labeled_entry(location_box, "Time zone", self.timezone_var)
        self.location_status_var = tk.StringVar(
            value=""
        )
        tk.Label(
            location_box,
            textvariable=self.location_status_var,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            justify=tk.LEFT,
            wraplength=260,
            font=("Segoe UI", 8),
        ).pack(anchor="w", fill=tk.X, pady=(7, 0))
        self._button_row(
            location_box,
            (
                ("Save Custom", self._save_location_preset),
                ("Set Home", self._set_home_location),
                ("Use Home", self._use_home_location),
            ),
            pady=(8, 0),
        )
        self._button_row(
            location_box,
            (
                ("Use Local", self._use_default_location),
                ("Hide Built-in", self._hide_selected_builtin_location),
            ),
            pady=(6, 0),
        )
        self._button_row(
            location_box,
            (
                ("Forget Custom", self._forget_location_preset),
                ("Reset Locations", self._reset_locations),
            ),
            pady=(6, 0),
        )
        self._refresh_location_status()

        model_box = self._left_section(parent, "Election Model", "Objective, zodiac, houses, and preset.")
        self._labeled_combo(model_box, "Objective", self.objective_var, list(OBJECTIVES))
        self._labeled_combo(model_box, "Zodiac system", self.zodiac_system_var, list(ZODIAC_SYSTEM_NAMES))
        self._labeled_combo(model_box, "House system", self.house_system_var, list(HOUSE_SYSTEM_NAMES))
        self.preset_combo = self._labeled_combo(model_box, "Electional model", self.preset_var, [preset.name for preset in ELECTIONAL_PRESETS])
        self.preset_combo.bind("<<ComboboxSelected>>", self._sync_aspects_to_preset)

        search_box = self._left_section(parent, "Search Strategy", "Rank windows by score, cleanliness, confidence, or risk.")
        self._labeled_combo(search_box, "Search preset", self.search_preset_var, list(SEARCH_PRESET_NAMES)).bind("<<ComboboxSelected>>", self._apply_selected_search_preset)
        self._labeled_combo(search_box, "Search mode", self.search_quality_mode_var, list(SEARCH_QUALITY_MODE_NAMES)).bind("<<ComboboxSelected>>", lambda _event: self._update_search_summary())
        search_row = ttk.Frame(search_box, style="Panel.TFrame")
        search_row.pack(fill=tk.X)
        search_row.columnconfigure(0, weight=1)
        search_row.columnconfigure(1, weight=1)
        self._labeled_entry(search_row, "Scan hours", self.scan_hours_var, compact=True, column=0)
        self._labeled_entry(search_row, "Step minutes", self.step_minutes_var, compact=True, column=1)
        result_row = ttk.Frame(search_box, style="Panel.TFrame")
        result_row.pack(fill=tk.X)
        result_row.columnconfigure(0, weight=1)
        result_row.columnconfigure(1, weight=1)
        self._labeled_entry(result_row, "Minimum score", self.minimum_score_var, compact=True, column=0)
        self._labeled_entry(result_row, "Minimum fit", self.minimum_fit_var, compact=True, column=1)
        limit_row = ttk.Frame(search_box, style="Panel.TFrame")
        limit_row.pack(fill=tk.X)
        limit_row.columnconfigure(0, weight=1)
        limit_row.columnconfigure(1, weight=1)
        self._labeled_entry(limit_row, "Min confidence", self.minimum_confidence_var, compact=True, column=0)
        tk.Checkbutton(
            limit_row,
            text="Avoid major stress",
            variable=self.avoid_major_stress_var,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["panel"],
            selectcolor=PALETTE["panel_alt"],
            font=("Segoe UI", 8, "bold"),
            command=self._update_search_summary,
        ).grid(row=0, column=1, sticky="w", padx=(6, 0), pady=(28, 0))
        diagnostics_row = ttk.Frame(search_box, style="Panel.TFrame")
        diagnostics_row.pack(fill=tk.X)
        diagnostics_row.columnconfigure(0, weight=1)
        diagnostics_row.columnconfigure(1, weight=1)
        self._labeled_entry(diagnostics_row, "Min cleanliness", self.minimum_cleanliness_var, compact=True, column=0)
        self._labeled_entry(diagnostics_row, "Max volatility", self.maximum_volatility_var, compact=True, column=1)
        max_row = ttk.Frame(search_box, style="Panel.TFrame")
        max_row.pack(fill=tk.X)
        max_row.columnconfigure(0, weight=1)
        max_row.columnconfigure(1, weight=1)
        self._labeled_entry(max_row, "Max results", self.max_results_var, compact=True, column=0)
        self._button_row(
            search_box,
            (
                ("6h", lambda: self._set_search_preset("6", "60")),
                ("12h", lambda: self._set_search_preset("12", "60")),
                ("24h", lambda: self._set_search_preset("24", "120")),
            ),
            pady=(8, 0),
        )
        preset_filters = ttk.Frame(search_box, style="Panel.TFrame")
        preset_filters.pack(fill=tk.X, pady=(7, 0))
        for index, label in enumerate(("Strict Launch", "Clean Negotiation", "Safe Travel", "Conservative Money")):
            preset_filters.columnconfigure(index % 2, weight=1, uniform="preset-filter")
            ttk.Button(
                preset_filters,
                text=label,
                command=lambda name=label: self._apply_search_filter_preset(name),
                style="Compact.TButton",
            ).grid(row=index // 2, column=index % 2, sticky="ew", padx=(0 if index % 2 == 0 else 3, 0 if index % 2 == 1 else 3), pady=(0 if index < 2 else 5, 0))
        tk.Label(
            search_box,
            textvariable=self.search_summary_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["muted"],
            justify=tk.LEFT,
            wraplength=270,
            font=("Segoe UI", 8),
        ).pack(anchor="w", fill=tk.X, pady=(8, 0))

        safety_box = self._left_section(parent, "Safety Filters", "Hard gates for cleaner election windows.")
        filter_row = ttk.Frame(safety_box, style="Panel.TFrame")
        filter_row.pack(fill=tk.X, pady=(2, 0))
        tk.Checkbutton(
            filter_row,
            text="Require applying support",
            variable=self.require_applying_support_var,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["panel"],
            selectcolor=PALETTE["panel_alt"],
            font=("Segoe UI", 8, "bold"),
            command=self._update_search_summary,
        ).pack(anchor="w")
        tk.Checkbutton(
            filter_row,
            text="Require angular benefic",
            variable=self.require_angular_benefic_var,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["panel"],
            selectcolor=PALETTE["panel_alt"],
            font=("Segoe UI", 8, "bold"),
            command=self._update_search_summary,
        ).pack(anchor="w")
        tk.Checkbutton(
            filter_row,
            text="Avoid angular malefics",
            variable=self.avoid_angular_malefics_var,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["panel"],
            selectcolor=PALETTE["panel_alt"],
            font=("Segoe UI", 8, "bold"),
            command=self._update_search_summary,
        ).pack(anchor="w")
        tk.Checkbutton(
            filter_row,
            text="Keep Moon non-void",
            variable=self.require_moon_non_void_var,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["panel"],
            selectcolor=PALETTE["panel_alt"],
            font=("Segoe UI", 8, "bold"),
            command=self._update_search_summary,
        ).pack(anchor="w")
        tk.Checkbutton(
            filter_row,
            text="Avoid objective anti-patterns",
            variable=self.avoid_objective_antipatterns_var,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            activebackground=PALETTE["panel"],
            selectcolor=PALETTE["panel_alt"],
            font=("Segoe UI", 8, "bold"),
            command=self._update_search_summary,
        ).pack(anchor="w")
        self._update_search_summary()

        aspect_box = self._left_section(parent, "Aspect Focus", "Choose which contacts the search should care about.")
        preset = ELECTIONAL_PRESETS[1]
        session_aspects = state.get("aspects") if isinstance(state.get("aspects"), dict) else {}
        self.aspect_profile_combo = self._labeled_combo(aspect_box, "Aspect profile", self.aspect_profile_var, self._aspect_profile_names())
        self.aspect_profile_combo.bind("<<ComboboxSelected>>", self._aspect_profile_changed)
        self.aspect_focus_options_frame = ttk.Frame(aspect_box, style="Panel.TFrame")
        self.aspect_focus_options_frame.pack(fill=tk.X, pady=(8, 0))
        self._refresh_aspect_focus_controls(session_aspects, preset)
        self._button_row(
            aspect_box,
            (
                ("Aspect Config", self._show_aspect_config_dialog),
                ("Apply Preset", self._sync_aspects_to_preset),
                ("Import Cap", self._import_capricorn_aspect_profiles),
            ),
            pady=(8, 0),
        )

        tk.Label(
            aspect_box,
            text="Aspect profiles control which contacts are searched, scored, drawn, and reported. Custom angles use their profile orb unless the electional model overrides that id.",
            bg=PALETTE["panel_alt"],
            fg=PALETTE["muted"],
            justify=tk.LEFT,
            wraplength=270,
            font=("Segoe UI", 8),
        ).pack(anchor="w", fill=tk.X)

        action_box = self._left_section(parent, "Actions", "Calculate, review, and open deeper pages.")
        self._button_row(
            action_box,
            (
                ("Show Current", lambda: self.calculate(show_input_chart=True)),
                ("Find Best", self.calculate),
            ),
        )
        self._button_row(
            action_box,
            (
                ("Preferences", self._show_preferences_dialog),
                ("Day Report", self._show_daily_aspect_report_dialog),
                ("Search Page", self._open_search_workbench_page),
            ),
            pady=(7, 0),
        )
        tk.Label(
            parent,
            textvariable=self.validation_var,
            bg=PALETTE["panel"],
            fg=PALETTE["accent_dark"],
            justify=tk.LEFT,
            wraplength=285,
            font=("Georgia", 9, "bold"),
        ).pack(anchor="w", pady=(10, 0))

    def _left_section(self, parent: tk.Widget, title: str, subtitle: str = "") -> tk.Frame:
        section = tk.Frame(
            parent,
            bg=PALETTE["panel_alt"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=10,
            pady=9,
        )
        section.pack(fill=tk.X, pady=(0, 10))
        tk.Frame(section, bg=PALETTE["accent"], height=2).pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            section,
            text=title,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 9, "bold"),
            anchor="w",
        ).pack(fill=tk.X)
        if subtitle:
            tk.Label(
                section,
                text=subtitle,
                bg=PALETTE["panel_alt"],
                fg=PALETTE["muted"],
                font=("Segoe UI", 8),
                wraplength=275,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(2, 3))
        return section

    def _build_left_status_chips(self, parent: tk.Widget) -> None:
        self.left_status_chip_vars = [tk.StringVar(value="") for _ in range(5)]
        for variable in self.left_status_chip_vars:
            chip = tk.Frame(
                parent,
                bg=PALETTE["chip"],
                highlightbackground=PALETTE["chip_line"],
                highlightthickness=1,
                padx=7,
                pady=4,
            )
            chip.pack(fill=tk.X, pady=(5, 0))
            tk.Label(
                chip,
                textvariable=variable,
                bg=PALETTE["chip"],
                fg=PALETTE["top_bar_dark"],
                font=("Segoe UI Semibold", 8),
                wraplength=265,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X)
        self._refresh_left_status_chips()

    def _build_workflow_next_step(self, parent: tk.Widget) -> None:
        guide = tk.Frame(
            parent,
            bg=PALETTE["surface_sage"],
            highlightbackground=PALETTE["chip_line"],
            highlightthickness=1,
            padx=8,
            pady=7,
        )
        guide.pack(fill=tk.X, pady=(8, 0))
        tk.Label(
            guide,
            text="Next Step",
            bg=PALETTE["surface_sage"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 9, "bold"),
            anchor="w",
        ).pack(fill=tk.X)
        self.workflow_step_title_var = tk.StringVar(value="")
        self.workflow_step_body_var = tk.StringVar(value="")
        self.workflow_step_hint_var = tk.StringVar(value="")
        tk.Label(
            guide,
            textvariable=self.workflow_step_title_var,
            bg=PALETTE["surface_sage"],
            fg=PALETTE["top_bar_dark"],
            font=("Segoe UI Semibold", 8),
            wraplength=260,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))
        tk.Label(
            guide,
            textvariable=self.workflow_step_body_var,
            bg=PALETTE["surface_sage"],
            fg=PALETTE["text"],
            font=("Segoe UI", 8),
            wraplength=260,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            guide,
            textvariable=self.workflow_step_hint_var,
            bg=PALETTE["surface_sage"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 7),
            wraplength=260,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 6))
        self._button_row(
            guide,
            (
                ("Current", lambda: self.calculate(show_input_chart=True)),
                ("Find Best", self.calculate),
                ("Analysis", lambda: self._focus_detail_page("Analysis")),
            ),
        )
        self._refresh_workflow_next_step()

    def _refresh_left_status_chips(self) -> None:
        if not getattr(self, "left_status_chip_vars", None):
            return
        lines = left_status_chip_lines(
            self.date_var.get() if hasattr(self, "date_var") else "",
            self.time_var.get() if hasattr(self, "time_var") else "",
            self.location_name_var.get() if hasattr(self, "location_name_var") else "",
            self.timezone_var.get() if hasattr(self, "timezone_var") else "",
            self.zodiac_system_var.get() if hasattr(self, "zodiac_system_var") else "",
            self.house_system_var.get() if hasattr(self, "house_system_var") else "",
            (
                f"{self.search_quality_mode_var.get()} | {self.active_aspect_profile.name}"
                if hasattr(self, "search_quality_mode_var") and hasattr(self, "active_aspect_profile")
                else self.search_quality_mode_var.get()
                if hasattr(self, "search_quality_mode_var")
                else ""
            ),
            self.validation_var.get() if hasattr(self, "validation_var") else "",
        )
        for variable, text in zip(self.left_status_chip_vars, lines):
            variable.set(text)
        self._refresh_workflow_next_step()

    def _refresh_workflow_next_step(self) -> None:
        if not hasattr(self, "workflow_step_title_var"):
            return
        has_rejections = False
        if isinstance(getattr(self, "current_rejection_summary", None), dict):
            top_reasons = self.current_rejection_summary.get("topReasons")
            has_rejections = bool(top_reasons)
        title, body, hint = workflow_next_step_lines(
            has_chart=bool(self.selected_window or self.input_snapshot),
            candidate_count=len(getattr(self, "current_windows", [])),
            selected_index=int(getattr(self, "selected_window_index", -1)),
            displayed_source=str(getattr(self, "displayed_chart_source", "")),
            has_rejections=has_rejections,
        )
        self.workflow_step_title_var.set(title)
        self.workflow_step_body_var.set(body)
        self.workflow_step_hint_var.set(hint)

    def _button_row(
        self,
        parent: tk.Widget,
        actions: tuple[tuple[str, Callable[[], None]], ...],
        *,
        pady: tuple[int, int] = (0, 0),
    ) -> None:
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill=tk.X, pady=pady)
        for index, (label, command) in enumerate(actions):
            row.columnconfigure(index, weight=1, uniform="button-row")
            ttk.Button(row, text=label, command=command, style="Compact.TButton").grid(
                row=0,
                column=index,
                sticky="ew",
                padx=(0 if index == 0 else 3, 0 if index == len(actions) - 1 else 3),
            )

    def _timing_adjustment_grid(self, parent: tk.Widget) -> None:
        grid = ttk.Frame(parent, style="Panel.TFrame")
        grid.pack(fill=tk.X, pady=(7, 0))
        actions: tuple[tuple[str, Callable[[], None]], ...] = (
            ("-2h", lambda: self._shift_time(-2)),
            ("-1h", lambda: self._shift_time(-1)),
            ("+1h", lambda: self._shift_time(1)),
            ("+2h", lambda: self._shift_time(2)),
            ("-15m", lambda: self._shift_time_minutes(-15)),
            ("+15m", lambda: self._shift_time_minutes(15)),
            ("-5m", lambda: self._shift_time_minutes(-5)),
            ("+5m", lambda: self._shift_time_minutes(5)),
            ("Exact", lambda: self.calculate(show_input_chart=True)),
        )
        for column in range(3):
            grid.columnconfigure(column, weight=1, uniform="timing-grid")
        for index, (label, command) in enumerate(actions):
            row, column = divmod(index, 3)
            ttk.Button(grid, text=label, command=command, style="Compact.TButton").grid(
                row=row,
                column=column,
                sticky="ew",
                padx=(0 if column == 0 else 3, 0 if column == 2 else 3),
                pady=(0 if row == 0 else 5, 0),
            )

    def _labeled_entry(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.StringVar,
        *,
        compact: bool = False,
        column: int | None = None,
    ) -> None:
        container = ttk.Frame(parent, style="Panel.TFrame")
        if column is None:
            container.pack(fill=tk.X)
        else:
            container.grid(row=0, column=column, sticky="ew", padx=(0, 6) if column == 0 else (6, 0))
        ttk.Label(container, text=label, style="Small.TLabel").pack(anchor="w", pady=(8 if compact else 10, 3))
        entry = tk.Entry(
            container,
            textvariable=variable,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            insertbackground=PALETTE["accent"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
            highlightcolor=PALETTE["accent"],
            font=("Segoe UI Semibold", 10),
        )
        entry.pack(fill=tk.X, ipady=6 if compact else 7)

    def _labeled_combo(self, parent: tk.Widget, label: str, variable: tk.StringVar, values: list[str]) -> ttk.Combobox:
        ttk.Label(parent, text=label, style="Small.TLabel").pack(anchor="w", pady=(10, 3))
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
        combo.pack(fill=tk.X, ipady=5)
        return combo

    def _load_selected_location(self, _event: object | None = None) -> None:
        location = self.locations_by_name.get(self.location_var.get(), get_location(None))
        self.location_name_var.set(location.name)
        self.latitude_var.set(f"{location.latitude:.4f}")
        self.longitude_var.set(f"{location.longitude:.4f}")
        self.timezone_var.set(location.timezone)

    def _save_location_preset(self) -> None:
        errors = validate_election_inputs(
            date.today().isoformat(),
            "09:00",
            self.latitude_var.get(),
            self.longitude_var.get(),
            self.timezone_var.get(),
        )
        if errors:
            self.validation_var.set("Location not saved:\n" + "\n".join(f"- {error}" for error in errors))
            return
        location = build_custom_location(
            self.location_name_var.get(),
            self.latitude_var.get(),
            self.longitude_var.get(),
            self.timezone_var.get(),
        )
        self.user_locations = upsert_user_location(self.user_locations, location)
        save_user_locations(self.user_locations)
        self._refresh_location_choices()
        self.location_var.set(location.name)
        self.status_var.set(f"Saved custom location: {location.name}.")
        self._log_event(f"Saved location preset: {location.name}")
        self.calculate(show_input_chart=True)

    def _set_home_location(self) -> None:
        errors = validate_election_inputs(
            date.today().isoformat(),
            "09:00",
            self.latitude_var.get(),
            self.longitude_var.get(),
            self.timezone_var.get(),
        )
        if errors:
            self.validation_var.set("Home location not saved:\n" + "\n".join(f"- {error}" for error in errors))
            return
        location = build_custom_location(
            self.location_name_var.get(),
            self.latitude_var.get(),
            self.longitude_var.get(),
            self.timezone_var.get(),
        )
        builtin_names = {preset.name for preset in LOCATION_PRESETS}
        if location.name not in builtin_names:
            self.user_locations = upsert_user_location(self.user_locations, location)
            save_user_locations(self.user_locations)
        self.home_location_name = location.name
        save_home_location_name(location.name)
        self._refresh_location_choices()
        self.location_var.set(location.name)
        self.status_var.set(f"Home location set: {location.name}.")
        self._log_event(f"Home location set: {location.name}")
        self.calculate(show_input_chart=True)

    def _use_home_location(self) -> None:
        location = resolve_location_by_name(self.home_location_name, self.user_locations) if self.home_location_name else None
        if not location:
            location = home_location_for_app(user_locations=self.user_locations)
        self.location_var.set(location.name)
        self.location_name_var.set(location.name)
        self.latitude_var.set(f"{location.latitude:.4f}")
        self.longitude_var.set(f"{location.longitude:.4f}")
        self.timezone_var.set(location.timezone)
        label = "saved home" if self.home_location_name else "local default"
        self.status_var.set(f"Loaded {label} location: {location.name}.")
        self._log_event(f"Loaded {label} location: {location.name}")
        self.calculate(show_input_chart=True)

    def _use_default_location(self) -> None:
        location = default_location_for_timezone()
        self.location_var.set(location.name)
        self.location_name_var.set(location.name)
        self.latitude_var.set(f"{location.latitude:.4f}")
        self.longitude_var.set(f"{location.longitude:.4f}")
        self.timezone_var.set(location.timezone)
        self.status_var.set(f"Loaded local default location: {location.name}.")
        self._log_event(f"Loaded local default location: {location.name}")
        self.calculate(show_input_chart=True)

    def _selected_builtin_location(self) -> LocationPreset | None:
        selected_name = self.location_var.get().strip() or self.location_name_var.get().strip()
        for location in LOCATION_PRESETS:
            if location.name.lower() == selected_name.lower():
                return location
        return None

    def _hide_selected_builtin_location(self) -> None:
        location = self._selected_builtin_location()
        if not location:
            self.status_var.set("Select a built-in location before using Hide Built-in.")
            return
        self.hidden_builtin_location_ids.add(location.id)
        save_hidden_builtin_location_ids(self.hidden_builtin_location_ids)
        self._refresh_location_choices()
        fallback = home_location_for_app(user_locations=self.user_locations)
        if fallback.id == location.id:
            fallback = next((preset for preset in LOCATION_PRESETS if preset.id not in self.hidden_builtin_location_ids), fallback)
        self.location_var.set(fallback.name)
        self.location_name_var.set(fallback.name)
        self.latitude_var.set(f"{fallback.latitude:.4f}")
        self.longitude_var.set(f"{fallback.longitude:.4f}")
        self.timezone_var.set(fallback.timezone)
        self.status_var.set(f"Hid built-in location: {location.name}. Use Reset Locations to restore it.")
        self._log_event(f"Hid built-in location: {location.name}")
        self.calculate(show_input_chart=True)

    def _reset_locations(self) -> None:
        self.hidden_builtin_location_ids = set()
        self.home_location_name = None
        reset_location_defaults()
        self._refresh_location_choices()
        location = home_location_for_app(user_locations=self.user_locations)
        self.location_var.set(location.name)
        self.location_name_var.set(location.name)
        self.latitude_var.set(f"{location.latitude:.4f}")
        self.longitude_var.set(f"{location.longitude:.4f}")
        self.timezone_var.set(location.timezone)
        self.status_var.set("Location defaults reset: built-ins restored and home location cleared.")
        self._log_event("Location defaults reset")
        self.calculate(show_input_chart=True)

    def _forget_location_preset(self) -> None:
        selected_name = self.location_name_var.get().strip() or self.location_var.get().strip()
        builtin_names = {location.name for location in LOCATION_PRESETS}
        if selected_name in builtin_names:
            self.status_var.set("Built-in locations can be hidden, not forgotten. Use Hide Built-in or Reset Locations.")
            return
        before_count = len(self.user_locations)
        self.user_locations = [location for location in self.user_locations if location.name.lower() != selected_name.lower()]
        if len(self.user_locations) == before_count:
            self.status_var.set(f"No saved custom location named {selected_name or 'blank'} was found.")
            return
        if self.home_location_name and self.home_location_name.lower() == selected_name.lower():
            self.home_location_name = None
            save_home_location_name(None)
        save_user_locations(self.user_locations)
        self._refresh_location_choices()
        fallback = home_location_for_app(user_locations=self.user_locations)
        self.location_var.set(fallback.name)
        self.location_name_var.set(fallback.name)
        self.latitude_var.set(f"{fallback.latitude:.4f}")
        self.longitude_var.set(f"{fallback.longitude:.4f}")
        self.timezone_var.set(fallback.timezone)
        self.status_var.set(f"Forgot saved location: {selected_name}.")
        self._log_event(f"Forgot location preset: {selected_name}")
        self.calculate(show_input_chart=True)

    def _sync_aspects_to_preset(self, _event: object | None = None) -> None:
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        enabled_by_id = {aspect.id: aspect.enabled for aspect in self.active_aspect_profile.aspects}
        for aspect_id, var in self.aspect_vars.items():
            var.set(bool(enabled_by_id.get(aspect_id, True) and (aspect_id in preset.aspect_ids or aspect_id not in preset.aspect_orbs)))
        self._save_session()
        self.status_var.set(f"Aspect focus updated for {preset.name}.")

    def _set_search_preset(self, scan_hours: str, step_minutes: str) -> None:
        self.scan_hours_var.set(scan_hours)
        self.step_minutes_var.set(step_minutes)
        self.search_preset_var.set("Custom")
        self._update_search_summary()

    def _apply_selected_search_preset(self, _event: object | None = None) -> None:
        self._apply_search_filter_preset(self.search_preset_var.get())

    def _apply_search_filter_preset(self, preset_name: str) -> None:
        overrides = search_preset_values(preset_name)
        if not overrides:
            self.search_preset_var.set("Custom")
            self._update_search_summary()
            return
        self.search_preset_var.set(preset_name)
        for key, value in overrides.items():
            match key:
                case "minimum_fit":
                    self.minimum_fit_var.set(str(value))
                case "minimum_confidence":
                    self.minimum_confidence_var.set(str(value))
                case "minimum_cleanliness":
                    self.minimum_cleanliness_var.set(str(value))
                case "maximum_volatility":
                    self.maximum_volatility_var.set(str(value))
                case "require_applying_support":
                    self.require_applying_support_var.set(bool(value))
                case "require_angular_benefic":
                    self.require_angular_benefic_var.set(bool(value))
                case "avoid_major_stress":
                    self.avoid_major_stress_var.set(bool(value))
                case "avoid_angular_malefics":
                    self.avoid_angular_malefics_var.set(bool(value))
                case "require_moon_non_void":
                    self.require_moon_non_void_var.set(bool(value))
                case "avoid_objective_antipatterns":
                    self.avoid_objective_antipatterns_var.set(bool(value))
        self._update_search_summary()
        self.status_var.set(f"Applied {preset_name} search preset.")

    def _update_search_summary(self) -> None:
        try:
            config = build_search_config_from_text(
                self.scan_hours_var.get(),
                self.step_minutes_var.get(),
                self.minimum_score_var.get(),
                self.max_results_var.get(),
                self.minimum_fit_var.get(),
                avoid_major_stress=self.avoid_major_stress_var.get(),
                require_applying_support=self.require_applying_support_var.get(),
                require_angular_benefic=self.require_angular_benefic_var.get(),
                avoid_angular_malefics=self.avoid_angular_malefics_var.get(),
                require_moon_non_void=self.require_moon_non_void_var.get(),
                avoid_objective_antipatterns=self.avoid_objective_antipatterns_var.get(),
                minimum_confidence_text=self.minimum_confidence_var.get(),
                minimum_cleanliness_text=self.minimum_cleanliness_var.get(),
                maximum_volatility_text=self.maximum_volatility_var.get(),
                search_quality_mode_text=self.search_quality_mode_var.get(),
            )
        except ValueError:
            self.search_summary_var.set("Search settings need attention.")
            self._refresh_left_status_chips()
            return
        self.search_summary_var.set(format_search_summary(config))
        self._refresh_left_status_chips()

    def _shift_time(self, hours: int) -> None:
        self._shift_time_minutes(hours * 60)

    def _shift_time_minutes(self, minutes: int) -> None:
        errors = validate_election_inputs(
            self.date_var.get(),
            self.time_var.get(),
            self.latitude_var.get(),
            self.longitude_var.get(),
            self.timezone_var.get(),
        )
        if errors:
            self.validation_var.set("Validation failed:\n" + "\n".join(f"- {error}" for error in errors))
            return
        next_date, next_time = shift_local_datetime_minutes(self.date_var.get(), self.time_var.get(), self.timezone_var.get(), minutes)
        self.date_var.set(next_date)
        self.time_var.set(next_time)
        self.calculate(show_input_chart=True)

    def _set_current_time(self) -> None:
        timezone_name = self.timezone_var.get() or DEFAULT_TIMEZONE
        now = datetime.now(ZoneInfo(timezone_name))
        self.date_var.set(now.strftime("%Y-%m-%d"))
        self.time_var.set(now.strftime("%H:%M"))
        self.calculate(show_input_chart=True)

    def _build_chart_panel(self) -> None:
        header = ttk.Frame(self.center_panel, style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, minsize=88)
        ttk.Label(header, text="RADIX + ELECTIONAL TRANSITS", style="Accent.TLabel").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value="")
        self.title_label = ttk.Label(header, textvariable=self.title_var, style="Title.TLabel", wraplength=520, justify=tk.LEFT)
        self.title_label.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.timing_context_var = tk.StringVar(value="")
        self.timing_context_label = ttk.Label(header, textvariable=self.timing_context_var, style="Small.TLabel", wraplength=520, justify=tk.LEFT)
        self.timing_context_label.grid(row=2, column=0, sticky="ew", pady=(1, 0), padx=(0, 8))
        self.context_chip_frame = tk.Frame(header, bg=PALETTE["panel"])
        self.context_chip_frame.grid(row=3, column=0, sticky="w", pady=(5, 0))
        self.workspace_page_var = tk.StringVar(value="Main page: Wheel")
        self.workspace_page_summary_var = tk.StringVar(value=TOP_NAV_WORKSPACE_SUMMARIES["Wheel"])
        workspace_frame = tk.Frame(header, bg=PALETTE["panel"], padx=0, pady=0)
        workspace_frame.grid(row=4, column=0, sticky="ew", pady=(4, 0), padx=(0, 8))
        tk.Label(workspace_frame, textvariable=self.workspace_page_var, bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Segoe UI Semibold", 8)).pack(side=tk.LEFT)
        tk.Label(workspace_frame, text=" / ", bg=PALETTE["panel"], fg=PALETTE["muted"], font=("Segoe UI", 8)).pack(side=tk.LEFT)
        tk.Label(workspace_frame, textvariable=self.workspace_page_summary_var, bg=PALETTE["panel"], fg=PALETTE["muted"], font=("Segoe UI", 8), wraplength=620, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X)
        header.bind("<Configure>", self._resize_header_labels)

        score_card = tk.Frame(
            header,
            bg=PALETTE["panel_alt"],
            highlightbackground=PALETTE["panel_line_strong"],
            highlightthickness=1,
            padx=12,
            pady=7,
        )
        score_card.grid(row=0, column=1, rowspan=5, sticky="e")
        tk.Frame(score_card, bg=PALETTE["score"], height=2).pack(fill=tk.X, pady=(0, 5))
        self.score_var = tk.StringVar(value="--")
        tk.Label(
            score_card,
            textvariable=self.score_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["score"],
            font=("Georgia", 25, "bold"),
        ).pack()
        self.score_band_var = tk.StringVar(value="waiting")
        tk.Label(
            score_card,
            textvariable=self.score_band_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 9),
        ).pack()

        state_bar = tk.Frame(self.center_panel, bg=PALETTE["panel"])
        state_bar.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        state_bar.columnconfigure(0, weight=1)
        state_bar.columnconfigure(1, weight=1)
        state_bar.columnconfigure(2, weight=1)
        state_bar.columnconfigure(3, weight=1)
        self.location_state_var = tk.StringVar(value="Location: waiting")
        self.input_state_var = tk.StringVar(value="Search start: waiting")
        self.selected_state_var = tk.StringVar(value="Selected window: waiting")
        self.offset_state_var = tk.StringVar(value="Offset: waiting")
        self._state_card(state_bar, "Location", self.location_state_var, 0, PALETTE["top_bar"])
        self._state_card(state_bar, "Search Start", self.input_state_var, 1, PALETTE["top_bar"])
        self._state_card(state_bar, "Selected Window", self.selected_state_var, 2, PALETTE["accent"])
        self._state_card(state_bar, "Difference", self.offset_state_var, 3, PALETTE["warning"])

        self.search_workbench_frame = tk.Frame(
            self.center_panel,
            bg=PALETTE["panel_alt"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=10,
            pady=7,
        )
        self.search_workbench_frame.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self.search_workbench_frame.columnconfigure(0, weight=1)
        self.search_workbench_frame.columnconfigure(1, weight=1)
        self.search_workbench_title_var = tk.StringVar(value="Search Workbench")
        self.search_workbench_summary_var = tk.StringVar(value="Waiting for calculation. Use Electional Search to rank candidate windows.")
        self.search_workbench_detail_var = tk.StringVar(value="Aspect profile and filters will appear here.")
        tk.Label(
            self.search_workbench_frame,
            textvariable=self.search_workbench_title_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            self.search_workbench_frame,
            textvariable=self.search_workbench_summary_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            font=("Segoe UI Semibold", 8),
            anchor="w",
            justify=tk.LEFT,
            wraplength=520,
        ).grid(row=1, column=0, sticky="ew", pady=(3, 0))
        tk.Label(
            self.search_workbench_frame,
            textvariable=self.search_workbench_detail_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 8),
            anchor="w",
            justify=tk.LEFT,
            wraplength=520,
        ).grid(row=2, column=0, sticky="ew", pady=(2, 0))
        quick_actions = tk.Frame(self.search_workbench_frame, bg=PALETTE["panel_alt"])
        quick_actions.grid(row=0, column=1, rowspan=3, sticky="e", padx=(10, 0))
        ttk.Button(quick_actions, text="Run Search", command=self._run_electional_search_workbench, style="Compact.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_actions, text="Timeline", command=self._open_timeline_workbench, style="Compact.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_actions, text="Aspects", command=self._show_aspect_config_dialog, style="Compact.TButton").pack(side=tk.LEFT)

        self.wheel_workspace = tk.Frame(
            self.center_panel,
            bg=PALETTE["surface"],
            highlightbackground=PALETTE["panel_line_strong"],
            highlightthickness=1,
            padx=6,
            pady=6,
        )
        self.wheel_workspace.grid(row=3, column=0, sticky="nsew")
        self.wheel_workspace.columnconfigure(0, weight=1)
        self.wheel_workspace.columnconfigure(1, weight=0)
        self.wheel_workspace.rowconfigure(1, weight=1)
        self._build_wheel_display_controls()

        self.classic_left_panel = tk.Frame(
            self.wheel_workspace,
            bg=CLASSIC_PANEL_BG,
            highlightbackground=CLASSIC_PANEL_LINE,
            highlightthickness=1,
            padx=5,
            pady=7,
            width=CLASSIC_LEFT_PANEL_WIDTH,
        )
        self.classic_left_panel.grid_propagate(False)

        self.canvas = tk.Canvas(
            self.wheel_workspace,
            width=900,
            height=660,
            bg=PALETTE["canvas"],
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
        )
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._schedule_redraw)
        self.canvas.bind("<Enter>", lambda _event: self.center_scroll_canvas.bind_all("<MouseWheel>", self._scroll_center_workspace))
        self.canvas.bind("<Leave>", lambda _event: self.center_scroll_canvas.unbind_all("<MouseWheel>"))

        self.classic_right_panel = tk.Frame(
            self.wheel_workspace,
            bg=CLASSIC_PANEL_BG,
            highlightbackground=CLASSIC_PANEL_LINE,
            highlightthickness=1,
            padx=6,
            pady=8,
            width=CLASSIC_RIGHT_PANEL_WIDTH,
        )
        self.classic_right_panel.grid(row=1, column=1, sticky="nse", padx=(8, 0))
        self.classic_right_panel.grid_propagate(False)
        self._build_classic_side_panels()

        self.focus_body_var = tk.StringVar(value="")
        self._build_chart_page_strip()

        actions = ttk.Frame(self.center_panel, style="Panel.TFrame")
        actions.grid(row=5, column=0, sticky="ew", pady=(5, 0))
        self.focus_mode_button_var = tk.StringVar(value="Focus Wheel")
        for label, command in (
            ("Recalculate", self.calculate),
            ("Prev Window", lambda: self._select_relative_window(-1)),
            ("Next Window", lambda: self._select_relative_window(1)),
            ("Use Selected Time", self._use_selected_window_time),
            ("View Report", self._show_current_report_dialog),
            ("Copy Report", self._copy_current_report),
            ("Save Report", self._save_current_report),
            ("Calendar", self._save_selected_calendar_event),
            ("Shortlist", self._add_selected_to_shortlist),
        ):
            ttk.Button(actions, text=label, command=command).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, textvariable=self.focus_mode_button_var, command=self._toggle_focus_mode).pack(side=tk.RIGHT)

    def _build_chart_page_strip(self) -> None:
        strip = tk.Frame(
            self.center_panel,
            bg=PALETTE["surface_soft"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=8,
            pady=6,
        )
        strip.grid(row=4, column=0, sticky="ew", pady=(5, 0))
        nav_row = tk.Frame(strip, bg=PALETTE["surface_soft"])
        nav_row.pack(fill=tk.X)
        quick_row = tk.Frame(strip, bg=PALETTE["surface_soft"])
        quick_row.pack(fill=tk.X, pady=(5, 0))

        tk.Label(nav_row, text="More detail", bg=PALETTE["surface_soft"], fg=PALETTE["accent"], font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        page_action_combo = ttk.Combobox(nav_row, textvariable=self.view_page_action_var, values=VIEW_PAGE_STRIP_ACTIONS, state="readonly", width=18)
        page_action_combo.pack(side=tk.LEFT, padx=(0, 4))
        page_action_combo.bind("<<ComboboxSelected>>", lambda _event: self._run_view_page_action(self.view_page_action_var.get()))
        ttk.Button(nav_row, text="Open", command=lambda: self._run_view_page_action(self.view_page_action_var.get()), style="Compact.TButton").pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(nav_row, text="Workspace mode", bg=PALETTE["surface_soft"], fg=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        page_mode_combo = ttk.Combobox(nav_row, textvariable=self.page_mode_var, values=PAGE_MODE_NAMES, state="readonly", width=22)
        page_mode_combo.pack(side=tk.LEFT, padx=(0, 9))
        page_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._page_mode_changed())
        tk.Label(quick_row, text="Primary tools", bg=PALETTE["surface_soft"], fg=PALETTE["accent"], font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        for label in VIEW_PAGE_QUICK_ACTIONS:
            tk.Button(
                quick_row,
                text=label,
                command=lambda action=label: self._run_view_page_action(action),
                bg=PALETTE["button"],
                fg=PALETTE["accent_dark"],
                activebackground=PALETTE["button_hover"],
                relief=tk.FLAT,
                padx=7,
                pady=2,
                font=("Georgia", 8, "bold"),
            ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_row, text="Focus", command=self._focus_selected_body, style="Compact.TButton").pack(side=tk.RIGHT, padx=(6, 0))
        self.focus_body_combo = ttk.Combobox(quick_row, textvariable=self.focus_body_var, values=[], state="readonly", width=18)
        self.focus_body_combo.pack(side=tk.RIGHT)
        self.focus_body_combo.bind("<<ComboboxSelected>>", lambda _event: self._focus_selected_body())
        tk.Label(quick_row, text="Focus point", bg=PALETTE["surface_soft"], fg=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(side=tk.RIGHT, padx=(8, 6))

    def _run_view_page_action(self, label: str) -> None:
        self.view_page_action_var.set(label if label in VIEW_PAGE_STRIP_ACTIONS else "Interpretation")
        if label == "Interpretation":
            self._focus_detail_page("Window")
        elif label == "Search":
            self._open_search_workbench_page()
        elif label == "Analysis":
            self._apply_page_mode("analysis")
        elif label == "Timeline":
            self._open_timeline_workbench()
        elif label == "Validation":
            self._apply_page_mode("validation")
        elif label == "Reports":
            self._apply_page_mode("reports")
        elif label == "Chart Data":
            self._show_chart_inspector()
        elif label == "Save Wheel":
            self._save_chart_wheel()
        else:
            self._focus_detail_page(VIEW_PAGE_TARGETS.get(label, label))

    def _resize_header_labels(self, event: object) -> None:
        width = max(240, int(getattr(event, "width", 640)) - 120)
        self.title_label.configure(wraplength=width)
        self.timing_context_label.configure(wraplength=width)

    def _build_wheel_display_controls(self) -> None:
        display = tk.Frame(
            self.wheel_workspace,
            bg=PALETTE["surface_soft"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=8,
            pady=5,
        )
        display.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        view_row = tk.Frame(display, bg=PALETTE["surface_soft"])
        view_row.pack(fill=tk.X)
        option_row = tk.Frame(display, bg=PALETTE["surface_soft"])
        option_row.pack(fill=tk.X, pady=(5, 0))

        tk.Label(view_row, text="Wheel preset", bg=PALETTE["surface_soft"], fg=PALETTE["accent"], font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        preset_combo = ttk.Combobox(view_row, textvariable=self.wheel_view_preset_var, values=WHEEL_VIEW_PRESET_NAMES, state="readonly", width=14)
        preset_combo.pack(side=tk.LEFT, padx=(0, 8))
        preset_combo.bind("<<ComboboxSelected>>", lambda _event: self._wheel_preset_changed())
        for label, command in (
            ("Clean", self._apply_clean_wheel_view),
            ("Full Classic", self._apply_full_wheel_view),
            ("Diagnostic", self._apply_diagnostic_wheel_view),
            ("Fit", self._fit_wheel_view),
            ("Zoom -", lambda: self._adjust_wheel_zoom(-0.06)),
            ("Zoom +", lambda: self._adjust_wheel_zoom(0.06)),
        ):
            ttk.Button(view_row, text=label, command=command, style="Compact.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(view_row, text="Reset Panels", command=self._reset_workspace_panels, style="Compact.TButton").pack(side=tk.RIGHT)

        tk.Label(option_row, text="Theme", bg=PALETTE["surface_soft"], fg=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        theme_combo = ttk.Combobox(option_row, textvariable=self.right_panel_theme_var, values=RIGHT_PANEL_THEME_NAMES, state="readonly", width=14)
        theme_combo.pack(side=tk.LEFT, padx=(0, 10))
        theme_combo.bind("<<ComboboxSelected>>", lambda _event: self._wheel_theme_changed())
        tk.Label(option_row, text="Points", bg=PALETTE["surface_soft"], fg=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        point_combo = ttk.Combobox(option_row, textvariable=self.point_set_var, values=POINT_SET_NAMES, state="readonly", width=16)
        point_combo.pack(side=tk.LEFT, padx=(0, 12))
        point_combo.bind("<<ComboboxSelected>>", lambda _event: self._point_set_changed())
        tk.Label(option_row, text="Overlays", bg=PALETTE["surface_soft"], fg=PALETTE["accent_dark"], font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 7))
        for label, variable in (
            ("Aspects", self.show_aspects_var),
            ("Score", self.show_score_overlay_var),
            ("Lots", self.show_lots_var),
            ("Nodes", self.show_nodes_var),
            ("Fixed Stars", self.show_fixed_stars_var),
            ("Compact", self.compact_wheel_var),
        ):
            tk.Checkbutton(
                option_row,
                text=label,
                variable=variable,
                command=self._display_option_changed,
                bg=PALETTE["surface_soft"],
                activebackground=PALETTE["surface_soft"],
                fg=PALETTE["muted"],
                selectcolor=PALETTE["surface_soft"],
                font=("Segoe UI", 8, "bold"),
            ).pack(side=tk.LEFT, padx=(0, 8))

    def _display_option_changed(self) -> None:
        self._redraw_selected_window()
        self._save_session()
        self.status_var.set("Updated wheel display options.")

    def _current_page_mode_id(self) -> str:
        return PAGE_MODE_IDS_BY_NAME.get(self.page_mode_var.get(), "wheel")

    def _current_point_set(self) -> PointSet:
        return get_point_set(self.point_set_var.get())

    def _current_wheel_theme_id(self) -> str:
        return RIGHT_PANEL_THEME_IDS_BY_NAME.get(self.right_panel_theme_var.get(), "astrolabe")

    def _current_wheel_preset_id(self) -> str:
        return WHEEL_VIEW_PRESET_IDS_BY_NAME.get(self.wheel_view_preset_var.get(), "full-classic")

    def _is_classic_wheel_theme(self) -> bool:
        return self._current_wheel_theme_id() == "classic-natal"

    def _is_diagnostic_wheel_preset(self) -> bool:
        return self._current_wheel_preset_id() == "diagnostic"

    def _planet_marker_font(self, size: int) -> tuple[str, int]:
        return ("Segoe UI Symbol" if self._is_classic_wheel_theme() else "Segoe UI Semibold", size)

    def _visible_planets(self, snapshot: dict[str, object]) -> list[dict[str, object]]:
        return [dict(planet) for planet in visible_planets_for_point_set(snapshot.get("positions", []), self._current_point_set())]

    def _visible_lots(self, snapshot: dict[str, object]) -> list[dict[str, object]]:
        return [dict(lot) for lot in visible_lots_for_point_set(snapshot.get("lots", []), self._current_point_set())]

    def _point_set_changed(self) -> None:
        point_set = get_point_set(self.point_set_var.get())
        self.show_nodes_var.set(point_set.show_nodes)
        self.show_lots_var.set(point_set.show_lots)
        self.show_fixed_stars_var.set(point_set.show_fixed_stars)
        if point_set.show_nodes or point_set.show_lots or point_set.show_fixed_stars:
            self.compact_wheel_var.set(False)
        self._display_option_changed()
        self.status_var.set(f"Point configuration: {point_set.name}.")

    def _wheel_theme_changed(self) -> None:
        if self._is_classic_wheel_theme():
            self.compact_wheel_var.set(False)
            self.show_score_overlay_var.set(False)
        self._display_option_changed()
        self._apply_current_theme()
        self.status_var.set(f"Wheel theme: {self.right_panel_theme_var.get()}.")

    def _page_mode_changed(self) -> None:
        self._apply_page_mode(self._current_page_mode_id())

    def _apply_page_mode(self, mode_id: str, *, save: bool = True) -> None:
        if mode_id == "wheel-aspectarian":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self.show_aspects_var.set(True)
            self.compact_wheel_var.set(False)
            self._focus_detail_page("Aspectarian")
            status = "Page mode: Wheel + Aspectarian."
        elif mode_id == "analysis":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self.show_aspects_var.set(True)
            self.compact_wheel_var.set(False)
            self._set_workspace_page("Analysis")
            self._focus_detail_page("Analysis")
            status = "Page mode: Analysis."
        elif mode_id == "validation":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self._set_workspace_page("Validation")
            self._focus_detail_page("Validation")
            status = "Page mode: Validation."
        elif mode_id == "reports":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self._set_workspace_page("Reports")
            self._focus_detail_page("Reports")
            status = "Page mode: Reports."
        elif mode_id == "medieval-data":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self.show_aspects_var.set(True)
            self.show_lots_var.set(True)
            self.show_nodes_var.set(False)
            self.show_fixed_stars_var.set(False)
            self.compact_wheel_var.set(False)
            self._focus_detail_page("Medieval")
            status = "Page mode: Medieval Data."
        elif mode_id == "classical-point-data":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self.show_aspects_var.set(True)
            self.show_lots_var.set(True)
            self.show_nodes_var.set(True)
            self.show_fixed_stars_var.set(False)
            self.compact_wheel_var.set(True)
            self._focus_detail_page("Point Data")
            status = "Page mode: Classical Point Data."
        elif mode_id == "transit-search":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self.show_aspects_var.set(True)
            self.show_lots_var.set(False)
            self.show_nodes_var.set(False)
            self.show_fixed_stars_var.set(False)
            self.compact_wheel_var.set(True)
            self._set_workspace_page("Search")
            self._focus_detail_page("Search")
            status = "Page mode: Transit Search."
        else:
            self.page_mode_var.set(PAGE_MODE_LABELS["wheel"])
            self.show_aspects_var.set(True)
            self._set_workspace_page("Wheel")
            self._focus_detail_page("Window")
            status = "Page mode: Wheel."
        self._redraw_selected_window()
        if save:
            self._save_session()
        self.status_var.set(status)

    def _fit_wheel_view(self) -> None:
        self.wheel_zoom = WHEEL_DEFAULT_ZOOM
        self.compact_wheel_var.set(True)
        self._display_option_changed()
        self.status_var.set("Wheel view fitted with extra label room.")

    def _adjust_wheel_zoom(self, delta: float) -> None:
        self.wheel_zoom = max(WHEEL_MIN_ZOOM, min(WHEEL_MAX_ZOOM, self.wheel_zoom + delta))
        self._display_option_changed()
        self.status_var.set(f"Wheel zoom: {self.wheel_zoom:.0%}.")

    def _scroll_center_to_top(self) -> None:
        if hasattr(self, "center_scroll_canvas"):
            self.center_scroll_canvas.yview_moveto(0)
            self.status_var.set("Middle workspace moved to top.")

    def _toggle_focus_mode(self) -> None:
        self._set_focus_mode(not self.focus_mode)

    def _pack_workspace_panels(self) -> None:
        for panel in (self.left_panel, self.center_pane, self.right_panel):
            if str(panel) in self.workspace_panes.panes():
                self.workspace_panes.forget(panel)
        self.workspace_panes.add(self.left_panel, minsize=280, width=320, stretch="never", padx=0)
        self.workspace_panes.add(self.center_pane, minsize=720, width=1060, stretch="always", padx=6)
        self.workspace_panes.add(self.right_panel, minsize=320, width=350, stretch="never", padx=0)

    def _apply_current_theme(self) -> None:
        is_classic = self._is_classic_wheel_theme()
        if hasattr(self, "canvas"):
            self.canvas.configure(
                bg=CLASSIC_WHEEL_BG if is_classic else PALETTE["canvas"],
                highlightbackground=CLASSIC_PANEL_LINE if is_classic else PALETTE["panel_line"],
            )
        if hasattr(self, "classic_left_panel"):
            self.classic_left_panel.grid_remove()
            if self.selected_window:
                self._refresh_classic_side_panels(self.selected_window, self.current_location)
            elif is_classic:
                self.classic_right_panel.grid()
            else:
                self.classic_right_panel.grid_remove()

    def _set_focus_mode(self, enabled: bool) -> None:
        self.focus_mode = enabled
        if enabled:
            if str(self.left_panel) in self.workspace_panes.panes():
                self.workspace_panes.forget(self.left_panel)
            if str(self.right_panel) in self.workspace_panes.panes():
                self.workspace_panes.forget(self.right_panel)
            if str(self.center_pane) not in self.workspace_panes.panes():
                self.workspace_panes.add(self.center_pane, minsize=420, stretch="always")
            self.focus_mode_button_var.set("Exit Focus")
            self.status_var.set("Focus wheel mode: side panels hidden. Press F11 to restore.")
        else:
            self._pack_workspace_panels()
            self.focus_mode_button_var.set("Focus Wheel")
            self.status_var.set("Focus wheel mode off: side panels restored.")
        self._schedule_redraw()

    def _reset_workspace_panels(self) -> None:
        self.focus_mode = False
        self._pack_workspace_panels()
        self.focus_mode_button_var.set("Focus Wheel")
        self._schedule_redraw()
        self.status_var.set("Workspace panels reset. Drag the vertical handles to resize side panels.")

    def _apply_clean_wheel_view(self) -> None:
        self._apply_wheel_view_preset("clean")

    def _apply_full_wheel_view(self) -> None:
        self._apply_wheel_view_preset("full-classic")

    def _apply_diagnostic_wheel_view(self) -> None:
        self._apply_wheel_view_preset("diagnostic")

    def _apply_wheel_view_preset(self, preset_id: str, *, save: bool = True) -> None:
        preset_id = preset_id if preset_id in WHEEL_VIEW_PRESET_LABELS else "full-classic"
        self.wheel_view_preset_var.set(WHEEL_VIEW_PRESET_LABELS[preset_id])
        self.right_panel_theme_var.set(RIGHT_PANEL_THEME_LABELS["classic-natal"])
        self.show_score_overlay_var.set(False)
        self.wheel_zoom = WHEEL_DEFAULT_ZOOM
        if preset_id == "clean":
            self.point_set_var.set(get_point_set("classical-7").name)
            self.show_aspects_var.set(True)
            self.show_lots_var.set(False)
            self.show_nodes_var.set(False)
            self.show_fixed_stars_var.set(False)
            self.compact_wheel_var.set(True)
        elif preset_id == "diagnostic":
            self.point_set_var.set(get_point_set("full-electional").name)
            self.show_aspects_var.set(True)
            self.show_lots_var.set(True)
            self.show_nodes_var.set(True)
            self.show_fixed_stars_var.set(True)
            self.compact_wheel_var.set(False)
        else:
            self.point_set_var.set(get_point_set("full-electional").name)
            self.show_aspects_var.set(True)
            self.show_lots_var.set(True)
            self.show_nodes_var.set(True)
            self.show_fixed_stars_var.set(True)
            self.compact_wheel_var.set(False)
        self._redraw_selected_window()
        self._apply_current_theme()
        if save:
            self._save_session()
        self.status_var.set(f"Wheel preset: {WHEEL_VIEW_PRESET_LABELS[preset_id]}.")

    def _wheel_preset_changed(self) -> None:
        self._apply_wheel_view_preset(self._current_wheel_preset_id())

    def _legacy_apply_clean_wheel_view(self) -> None:
        self.point_set_var.set(get_point_set("classical-7").name)
        self.show_aspects_var.set(True)
        self.show_lots_var.set(False)
        self.show_nodes_var.set(False)
        self.show_fixed_stars_var.set(False)
        self.compact_wheel_var.set(True)
        self._display_option_changed()

    def _legacy_apply_full_wheel_view(self) -> None:
        self.point_set_var.set(get_point_set("full-electional").name)
        self.show_aspects_var.set(True)
        self.show_lots_var.set(True)
        self.show_nodes_var.set(True)
        self.show_fixed_stars_var.set(True)
        self.compact_wheel_var.set(False)
        self._display_option_changed()

    def _state_card(self, parent: tk.Widget, title: str, variable: tk.StringVar, column: int, accent_color: str) -> None:
        card = tk.Frame(parent, bg=PALETTE["panel_alt"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=8, pady=5)
        card.grid(row=0, column=column, sticky="ew", padx=(0, 6) if column < 3 else (0, 0))
        tk.Frame(card, bg=accent_color, height=2).pack(fill=tk.X, pady=(0, 4))
        tk.Label(card, text=title, bg=PALETTE["panel_alt"], fg=accent_color, font=("Georgia", 8, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=170, justify=tk.LEFT).pack(anchor="w")

    def _build_classic_side_panels(self) -> None:
        self.classic_meta_title_var = tk.StringVar(value="Birth")
        self.classic_meta_lines_var = tk.StringVar(value="Natal Chart")
        tk.Label(
            self.classic_left_panel,
            textvariable=self.classic_meta_title_var,
            bg=CLASSIC_PANEL_BG,
            fg=CLASSIC_PANEL_ACCENT,
            font=("Georgia", 9, "bold"),
            anchor="w",
            justify=tk.LEFT,
        ).pack(fill=tk.X, anchor="w")
        tk.Label(
            self.classic_left_panel,
            textvariable=self.classic_meta_lines_var,
            bg=CLASSIC_PANEL_BG,
            fg=CLASSIC_PANEL_TEXT,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
            justify=tk.LEFT,
            wraplength=CLASSIC_LEFT_WRAP,
        ).pack(fill=tk.X, anchor="w", pady=(5, 8))
        tk.Frame(self.classic_left_panel, bg=CLASSIC_PANEL_LINE, height=1).pack(fill=tk.X, pady=(1, 8))

        self.classic_point_table_canvas = tk.Canvas(
            self.classic_right_panel,
            width=CLASSIC_RIGHT_PANEL_WIDTH - 16,
            height=222,
            bg=CLASSIC_PANEL_BG,
            highlightthickness=1,
            highlightbackground=CLASSIC_PANEL_LINE,
        )
        self.classic_point_table_canvas.pack(fill=tk.X, pady=(0, 7))

        aspect_boxes = tk.Frame(self.classic_right_panel, bg=CLASSIC_PANEL_BG)
        aspect_boxes.pack(fill=tk.X, pady=(0, 7))
        aspect_boxes.columnconfigure(0, weight=1)
        aspect_boxes.columnconfigure(1, weight=1)
        self.classic_support_title_vars: list[tk.StringVar] = []
        self.classic_support_body_vars: list[tk.StringVar] = []
        for column, heading in enumerate(("Strongest Support", "Strongest Stress")):
            block = tk.Frame(
                aspect_boxes,
                bg=CLASSIC_PANEL_BG,
                highlightbackground=CLASSIC_PANEL_LINE,
                highlightthickness=1,
                padx=5,
                pady=4,
            )
            block.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 4, 0))
            tk.Label(block, text=heading, bg=CLASSIC_PANEL_BG, fg=CLASSIC_PANEL_ACCENT, font=("Georgia", 8, "bold"), anchor="w").pack(fill=tk.X)
            title_var = tk.StringVar(value="")
            body_var = tk.StringVar(value="")
            tk.Label(block, textvariable=title_var, bg=CLASSIC_PANEL_BG, fg=CLASSIC_PANEL_TEXT, font=("Segoe UI Semibold", 8), anchor="w", justify=tk.LEFT, wraplength=158).pack(fill=tk.X, pady=(4, 2))
            tk.Label(block, textvariable=body_var, bg=CLASSIC_PANEL_BG, fg=CLASSIC_PANEL_MUTED, font=("Segoe UI Symbol", 8), anchor="w", justify=tk.LEFT, wraplength=158).pack(fill=tk.X)
            self.classic_support_title_vars.append(title_var)
            self.classic_support_body_vars.append(body_var)

        self.classic_aspect_grid_canvas = tk.Canvas(
            self.classic_right_panel,
            width=CLASSIC_RIGHT_PANEL_WIDTH - 16,
            height=330,
            bg=CLASSIC_PANEL_BG,
            highlightthickness=1,
            highlightbackground=CLASSIC_PANEL_LINE,
        )
        self.classic_aspect_grid_canvas.pack(fill=tk.BOTH, expand=True)

    def _draw_classic_point_table(self, snapshot: dict[str, object]) -> None:
        canvas = self.classic_point_table_canvas
        canvas.delete("all")
        width = max(330, int(canvas.winfo_width() or CLASSIC_RIGHT_PANEL_WIDTH - 16))
        height = max(222, int(canvas.winfo_height() or 222))
        row_h = 15
        headers = ("#", "H", "Point", "Position", "Dign.")
        cols = (
            7,
            24,
            46,
            int(width * 0.50),
            int(width * 0.78),
        )
        canvas.create_rectangle(0, 0, width, 20, fill="#f3f6f2", outline=CLASSIC_PANEL_LINE)
        for col, header in zip(cols, headers):
            canvas.create_text(col, 10, text=header, anchor="w", fill=CLASSIC_PANEL_TEXT, font=("Georgia", 8, "bold"))
        visible = self._visible_planets(snapshot)
        visible_ids = {point.get("id") for point in visible}
        rows: list[dict[str, object]] = [dict(point) for point in visible[:12]]
        if self.show_lots_var.get():
            rows.extend(dict(lot) for lot in self._visible_lots(snapshot)[:3])
        max_rows = min(12, max(8, int((height - 36) / row_h)))
        for index, point in enumerate(rows[:max_rows], start=1):
            y = 20 + index * row_h
            bg = "#fffefa" if index % 2 else "#f1f4f0"
            canvas.create_rectangle(0, y - row_h + 1, width, y + 1, fill=bg, outline=PALETTE["panel_line"])
            name = str(point.get("name", "Point"))
            glyph = planet_glyph(name) if point.get("id") in visible_ids else lot_abbreviation(name)
            dignity_text = classic_dignity_table_text(point)
            color = CLASSIC_PLANET_COLORS.get(name, CLASSIC_PANEL_TEXT)
            baseline = y - 7
            canvas.create_text(cols[0], baseline, text=str(index), anchor="w", fill=CLASSIC_PANEL_MUTED, font=("Segoe UI", 8))
            canvas.create_text(cols[1], baseline, text=str(point.get("house", "")), anchor="w", fill=CLASSIC_PANEL_TEXT, font=("Segoe UI Semibold", 8))
            canvas.create_text(cols[2], baseline, text=glyph, anchor="w", fill=color, font=("Segoe UI Symbol", 10, "bold"))
            canvas.create_text(cols[2] + 20, baseline, text=name[:14], anchor="w", fill=CLASSIC_PANEL_TEXT, font=("Segoe UI Semibold", 8))
            canvas.create_text(cols[3], baseline, text=classic_position_table_text(point), anchor="w", fill=CLASSIC_PANEL_TEXT, font=("Segoe UI", 8))
            canvas.create_text(cols[4], baseline, text=dignity_text, anchor="w", fill=CLASSIC_PANEL_MUTED, font=("Segoe UI", 8))
        footer_y = min(height - 9, 23 + max_rows * row_h)
        canvas.create_line(0, footer_y - 9, width, footer_y - 9, fill=CLASSIC_PANEL_LINE)
        canvas.create_text(width - 8, footer_y, text="Point Detail", anchor="e", fill=CLASSIC_PANEL_ACCENT, font=("Georgia", 8, "bold"))

    def _draw_classic_aspect_grid(self, snapshot: dict[str, object]) -> None:
        canvas = self.classic_aspect_grid_canvas
        canvas.delete("all")
        planets = self._visible_planets(snapshot)[:10]
        names = [str(planet.get("name")) for planet in planets]
        if not names:
            return
        aspect_lookup: dict[frozenset[str], dict[str, object]] = {}
        for aspect in snapshot.get("detectedAspects", []):
            if not isinstance(aspect, dict):
                continue
            bodies = aspect.get("bodies", [])
            if isinstance(bodies, list) and len(bodies) == 2:
                aspect_lookup[frozenset((str(bodies[0]), str(bodies[1])))] = aspect
        available_width = max(330, int(canvas.winfo_width() or CLASSIC_RIGHT_PANEL_WIDTH - 16))
        cell = max(24, min(29, (available_width - 54) // len(names)))
        left = 34
        top = 34
        size = cell * len(names)
        canvas.create_rectangle(left, top, left + size, top + size, fill="#fffefa", outline="#4f5d58", width=1)
        for index, name in enumerate(names):
            x = left + index * cell
            y = top + index * cell
            glyph = planet_glyph(name)
            color = CLASSIC_PLANET_COLORS.get(name, CLASSIC_PANEL_TEXT)
            canvas.create_text(x + cell / 2, top - 15, text=glyph, fill=color, font=("Segoe UI Symbol", 15, "bold"))
            canvas.create_text(left - 15, y + cell / 2, text=glyph, fill=color, font=("Segoe UI Symbol", 15, "bold"))
            canvas.create_line(left, y, left + size, y, fill="#9ca8a2", width=1)
            canvas.create_line(x, top, x, top + size, fill="#9ca8a2", width=1)
        canvas.create_line(left, top + size, left + size, top, fill="#596762", width=1)
        for row, row_name in enumerate(names):
            for column, column_name in enumerate(names):
                if row <= column:
                    continue
                aspect = aspect_lookup.get(frozenset((row_name, column_name)))
                if not aspect:
                    continue
                x = left + column * cell + cell / 2
                y = top + row * cell + cell / 2
                color = PALETTE["stress"] if aspect.get("tone") == "stress" else PALETTE["support"] if aspect.get("tone") == "support" else CLASSIC_PANEL_ACCENT
                canvas.create_text(x, y - 4, text=aspect_glyph(aspect), fill=color, font=("Segoe UI Symbol", 10, "bold"))
                orb = str(aspect.get("orbText") or "")
                canvas.create_text(x, y + 8, text=orb.replace("\N{DEGREE SIGN}", "")[:4], fill=color, font=("Segoe UI", 6))
        canvas.create_line(left + size, top, left + size, top + size, fill="#596762", width=1)
        canvas.create_line(left, top + size, left + size, top + size, fill="#596762", width=1)

    def _classic_aspect_rows(self, snapshot: dict[str, object], *, tone: str | None = None, limit: int = 5) -> list[str]:
        aspects = [
            aspect
            for aspect in snapshot.get("detectedAspects", [])
            if isinstance(aspect, dict) and (tone is None or aspect.get("tone") == tone)
        ]
        aspects.sort(
            key=lambda aspect: (
                0 if aspect.get("isApplying") else 1,
                float(aspect.get("orb", 99) or 99),
            )
        )
        rows: list[str] = []
        for aspect in aspects[:limit]:
            bodies = aspect.get("bodies", [])
            if not isinstance(bodies, list) or len(bodies) != 2:
                continue
            left = planet_glyph(str(bodies[0]))
            right = planet_glyph(str(bodies[1]))
            glyph = aspect_glyph(aspect)
            orb = str(aspect.get("orbText") or "")
            marker = "A" if aspect.get("isApplying") else "S"
            rows.append(f"{left} {glyph} {right}  {orb} {marker}")
        return rows or ["No active aspects"]

    def _classic_chart_info_lines(self, snapshot: dict[str, object], location: LocationPreset | None = None) -> list[str]:
        location = location or self.current_location
        location_text = location.name if location else "Location unavailable"
        formatted_time = str(snapshot.get("formattedTime", "time unavailable"))
        time_parts = formatted_time.split(", ")
        if len(time_parts) >= 3:
            time_lines = [", ".join(time_parts[:2]), ", ".join(time_parts[2:])]
        else:
            time_lines = [formatted_time]
        if ", " in location_text and len(location_text) > 18:
            location_head, location_tail = location_text.split(", ", 1)
            location_lines = [f"{location_head},", location_tail]
        else:
            location_lines = [location_text]
        zodiac_name = getattr(snapshot.get("zodiacSystem"), "name", "Zodiac n/a")
        house_name = getattr(snapshot.get("houseSystem"), "name", "House n/a")
        rules_line = "Traditional" if snapshot.get("traditionalRulesEnabled", True) else "13-sign rules off"
        nodes_label = "Mean Nodes"
        calculation_notes = snapshot.get("calculationNotes", [])
        if any("true node" in str(note).lower() for note in calculation_notes):
            nodes_label = "True Nodes"
        return [
            line
            for line in [
                "Natal Chart",
                *time_lines,
                *location_lines,
                f"{zodiac_name}",
                f"{house_name}",
                nodes_label,
                rules_line,
            ]
            if line
        ]

    def _draw_classic_chart_info(self, snapshot: dict[str, object], x: float, y: float, max_width: float) -> None:
        lines = self._classic_chart_info_lines(snapshot, self.current_location)
        line_height = 13
        block_width = max(112, max_width)
        block_height = 31 + line_height * len(lines)
        self.canvas.create_rectangle(
            x,
            y,
            x + block_width,
            y + block_height,
            fill=CLASSIC_PANEL_BG,
            outline=CLASSIC_PANEL_LINE,
            width=1,
            tags=("classic-chart-info",),
        )
        self.canvas.create_text(
            x + 8,
            y + 9,
            text="Birth",
            anchor="nw",
            fill=CLASSIC_PANEL_ACCENT,
            font=("Georgia", 9, "bold"),
            tags=("classic-chart-info",),
        )
        self.canvas.create_text(
            x + 8,
            y + 29,
            text="\n".join(lines),
            anchor="nw",
            fill=CLASSIC_PANEL_TEXT,
            font=("Segoe UI", 8, "bold"),
            width=max(80, int(block_width - 14)),
            tags=("classic-chart-info",),
        )

    def _refresh_classic_side_panels(self, snapshot: dict[str, object], location: LocationPreset | None = None) -> None:
        if not hasattr(self, "classic_meta_lines_var"):
            return
        if not self._is_classic_wheel_theme():
            self.classic_left_panel.grid_remove()
            self.classic_right_panel.grid_remove()
            return

        self.classic_left_panel.grid_remove()
        self.classic_right_panel.grid()
        location = location or self.current_location
        self.classic_meta_title_var.set("Birth")
        self.classic_meta_lines_var.set("\n".join(self._classic_chart_info_lines(snapshot, location)))
        self._draw_classic_point_table(snapshot)
        self._draw_classic_aspect_grid(snapshot)

        support_blocks = (
            ("Support/applying", "\n".join(self._classic_aspect_rows(snapshot, tone="support", limit=5))),
            ("Stress/watch", "\n".join(self._classic_aspect_rows(snapshot, tone="stress", limit=5))),
        )
        for (title_var, body_var), (title_text, body_text) in zip(zip(self.classic_support_title_vars, self.classic_support_body_vars), support_blocks):
            title_var.set(title_text)
            body_var.set(body_text)

    def _build_right_panel(self) -> None:
        self._build_metric_panel()
        self._build_window_list_panel()
        self.detail_notebook = ttk.Notebook(self.right_panel)
        self.detail_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 9))
        self.summary_text = self._text_tab("Summary")
        self.window_detail_text = self._text_tab("Window")
        self.analysis_canvas, self.analysis_frame = self._visual_tab("Analysis")
        self.validation_canvas, self.validation_frame = self._visual_tab("Validation")
        self.reports_canvas, self.reports_frame = self._visual_tab("Reports")
        self.advisor_text = self._text_tab("Advisor")
        self.improve_text = self._text_tab("Improve")
        self.decision_text = self._text_tab("Decision")
        self.compare_text = self._text_tab("Compare")
        self.diagnostics_text = self._text_tab("Diagnostics")
        self.search_text = self._text_tab("Search")
        self.interpretation_text = self._text_tab("Focus")
        self.score_detail_text = self._text_tab("Score")
        self.accounting_text = self._text_tab("Accounting")
        self.conditions_text = self._text_tab("Conditions")
        self.angles_text = self._text_tab("Angles")
        self.classical_point_data_text = self._text_tab("Point Data")
        self.medieval_text = self._text_tab("Medieval")
        self.rules_text = self._text_tab("Rules")
        self.significators_text = self._text_tab("Significators")
        self.moon_judgment_text = self._text_tab("Moon")
        self.house_rulers_text = self._text_tab("House Rulers")
        self.reception_text = self._text_tab("Reception")
        self.planet_condition_text = self._text_tab("Planet Condition")
        self.declination_text = self._text_tab("Declination")
        self.advanced_aspects_text = self._text_tab("Advanced")
        self.factor_explorer_text = self._text_tab("Factor Explorer")
        self.constellations_text = self._text_tab("Constellations")
        self.cusps_text = self._text_tab("Cusps")
        self.lots_text = self._text_tab("Lots")
        self.nodes_text = self._text_tab("Nodes")
        self.timing_text = self._text_tab("Timing")
        self.timeline_canvas, self.timeline_frame = self._visual_tab("Timeline")
        self.planets_text = self._text_tab("Planets")
        self.aspects_text = self._text_tab("Aspects")
        self.aspectarian_text = self._text_tab("Aspectarian")
        self.aspect_strength_text = self._text_tab("Aspect Strength")
        self.fixed_stars_text = self._text_tab("Fixed Stars")
        self.button_health_text = self._text_tab("Button Health")
        shortlist_board = ttk.Frame(self.detail_notebook, style="Panel.TFrame", padding=7)
        self.detail_notebook.add(shortlist_board, text="Shortlist Board")
        shortlist_board.columnconfigure(0, weight=1)
        shortlist_board.rowconfigure(0, weight=1)
        shortlist_viewport = ttk.Frame(shortlist_board, style="Panel.TFrame")
        shortlist_viewport.grid(row=0, column=0, sticky="nsew")
        shortlist_viewport.columnconfigure(0, weight=1)
        shortlist_viewport.rowconfigure(0, weight=1)
        self.shortlist_board_canvas = tk.Canvas(
            shortlist_viewport,
            bg=PALETTE["panel_alt"],
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
            bd=0,
        )
        shortlist_scrollbar = ttk.Scrollbar(shortlist_viewport, orient=tk.VERTICAL, command=self.shortlist_board_canvas.yview)
        self.shortlist_board_frame = ttk.Frame(self.shortlist_board_canvas, style="Panel.TFrame")
        self.shortlist_board_window = self.shortlist_board_canvas.create_window((0, 0), window=self.shortlist_board_frame, anchor="nw")
        self.shortlist_board_canvas.configure(yscrollcommand=shortlist_scrollbar.set)
        self.shortlist_board_canvas.grid(row=0, column=0, sticky="nsew")
        shortlist_scrollbar.grid(row=0, column=1, sticky="ns")
        self.shortlist_board_frame.bind("<Configure>", lambda _event: self.shortlist_board_canvas.configure(scrollregion=self.shortlist_board_canvas.bbox("all")))
        self.shortlist_board_canvas.bind("<Configure>", lambda event: self.shortlist_board_canvas.itemconfigure(self.shortlist_board_window, width=event.width))
        self.shortlist_text = self._text_tab("Shortlist")
        self.shortlist_compare_text = self._text_tab("Pick Compare")
        shortlist_actions = ttk.Frame(self.detail_notebook, style="Panel.TFrame", padding=7)
        self.detail_notebook.add(shortlist_actions, text="Pick Tools")
        tk.Label(
            shortlist_actions,
            text="Pick Tools",
            bg=PALETTE["panel"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 11, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            shortlist_actions,
            text=(
                "Export or copy the selected election, the whole shortlist, or a decision sheet. "
                "Use this after saving two or more serious candidates."
            ),
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 8),
            wraplength=320,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
        ttk.Button(shortlist_actions, text="Save Selected .ics", command=self._save_selected_calendar_event).pack(fill=tk.X, pady=(0, 7))
        ttk.Button(shortlist_actions, text="Copy Selected .ics", command=self._copy_selected_calendar_event).pack(fill=tk.X, pady=(0, 7))
        ttk.Button(shortlist_actions, text="Save Decision Sheet", command=self._save_comparison_sheet).pack(fill=tk.X, pady=(0, 7))
        ttk.Button(shortlist_actions, text="Save Shortlist .ics", command=self._save_shortlist_calendar).pack(fill=tk.X, pady=(0, 7))
        ttk.Button(shortlist_actions, text="Copy Shortlist", command=self._copy_shortlist).pack(fill=tk.X, pady=(0, 7))
        ttk.Button(shortlist_actions, text="Save Shortlist", command=self._save_shortlist_report).pack(fill=tk.X, pady=(0, 7))
        ttk.Button(shortlist_actions, text="Clear Shortlist", command=self._clear_shortlist).pack(fill=tk.X)
        self.log_text = self._text_tab("Log")
        self._refresh_shortlist_text()
        self._refresh_button_health_text()
        self._refresh_event_log()

    def _build_metric_panel(self) -> None:
        frame = tk.Frame(
            self.right_panel,
            bg=PALETTE["astrolabe_panel"],
            highlightbackground=PALETTE["astrolabe_line"],
            highlightthickness=1,
            padx=8,
            pady=7,
        )
        frame.pack(fill=tk.X, pady=(0, 7))
        tk.Frame(frame, bg=PALETTE["astrolabe_gold"], height=2).pack(fill=tk.X, pady=(0, 5))
        tk.Label(
            frame,
            text="JUDGMENT PANEL",
            bg=PALETTE["astrolabe_panel"],
            fg=PALETTE["astrolabe_gold"],
            font=("Georgia", 9, "bold"),
            anchor="w",
        ).pack(fill=tk.X)
        score_row = tk.Frame(frame, bg=PALETTE["astrolabe_panel"])
        score_row.pack(fill=tk.X, pady=(3, 5))
        self.judgment_score_var = tk.StringVar(value="--")
        self.judgment_grade_var = tk.StringVar(value="Awaiting calculation")
        tk.Label(score_row, textvariable=self.judgment_score_var, bg=PALETTE["astrolabe_panel"], fg=PALETTE["astrolabe_gold"], font=("Georgia", 24, "bold")).pack(side=tk.LEFT)
        tk.Label(score_row, textvariable=self.judgment_grade_var, bg=PALETTE["astrolabe_panel"], fg=PALETTE["astrolabe_muted"], font=("Segoe UI", 8, "bold"), justify=tk.LEFT, wraplength=210).pack(side=tk.LEFT, padx=(9, 0), fill=tk.X)
        self.judgment_line_vars = [tk.StringVar(value="") for _index in range(4)]
        for index, variable in enumerate(self.judgment_line_vars):
            fg = PALETTE["astrolabe_gold"] if index == 0 else PALETTE["astrolabe_ink"]
            tk.Label(
                frame,
                textvariable=variable,
                bg=PALETTE["astrolabe_panel"],
                fg=fg,
                font=("Segoe UI", 8 if index else 8, "bold" if index == 0 else "normal"),
                wraplength=330,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(2, 0))
        self.validation_panel_vars = [tk.StringVar(value="") for _index in range(4)]
        validation_block = tk.Frame(frame, bg=PALETTE["panel"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=7, pady=5)
        validation_block.pack(fill=tk.X, pady=(7, 0))
        tk.Label(validation_block, text="Calculation Health", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 8, "bold"), anchor="w").pack(fill=tk.X)
        for variable in self.validation_panel_vars:
            tk.Label(
                validation_block,
                textvariable=variable,
                bg=PALETTE["panel"],
                fg=PALETTE["text"],
                font=("Segoe UI", 7),
                wraplength=330,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(2, 0))
        self.house_geometry_var = tk.StringVar(value="")
        house_block = tk.Frame(frame, bg=PALETTE["panel"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=7, pady=5)
        house_block.pack(fill=tk.X, pady=(7, 0))
        tk.Label(house_block, text="House Geometry", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 8, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(
            house_block,
            textvariable=self.house_geometry_var,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("Segoe UI", 7),
            wraplength=330,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(3, 0))
        self.aspect_dashboard_var = tk.StringVar(value="")
        aspect_block = tk.Frame(frame, bg=PALETTE["panel"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=7, pady=5)
        aspect_block.pack(fill=tk.X, pady=(7, 0))
        tk.Label(aspect_block, text="Aspect Dashboard", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 8, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(
            aspect_block,
            textvariable=self.aspect_dashboard_var,
            bg=PALETTE["panel"],
            fg=PALETTE["text"],
            font=("Segoe UI", 7),
            wraplength=330,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(3, 0))
        action_row = tk.Frame(frame, bg=PALETTE["astrolabe_panel"])
        action_row.pack(fill=tk.X, pady=(7, 0))
        self._astrolabe_button(action_row, "Day Report", self._show_daily_aspect_report_dialog).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        self._astrolabe_button(action_row, "Full Report", self._show_current_report_dialog).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Frame(frame, bg=PALETTE["astrolabe_line"], height=1).pack(fill=tk.X, pady=(6, 5))
        metric_grid = tk.Frame(frame, bg=PALETTE["astrolabe_panel"])
        metric_grid.pack(fill=tk.X)
        metrics = (
            ("score", "Score", PALETTE["astrolabe_ink"]),
            ("confidence", "Confidence", PALETTE["astrolabe_gold"]),
            ("fit", "Fit", "#58b9ad"),
            ("support", "Support", "#70c698"),
            ("stress", "Stress", "#db8795"),
            ("angular", "Angular", "#b7c5dc"),
            ("stars", "Stars", "#9eb3e1"),
            ("rules", "Rules", "#d2aa62"),
        )
        for index, (key, label, value_color) in enumerate(metrics):
            var = tk.StringVar(value="--")
            self.metric_vars[key] = var
            card = tk.Frame(
                metric_grid,
                bg=PALETTE["panel"],
                highlightbackground=PALETTE["panel_line"],
                highlightthickness=1,
                padx=6,
                pady=4,
            )
            card.grid(row=index // 2, column=index % 2, sticky="ew", padx=3, pady=3)
            tk.Frame(card, bg=value_color, height=1).pack(fill=tk.X, pady=(0, 3))
            tk.Label(card, text=label, bg=PALETTE["panel"], fg=PALETTE["astrolabe_muted"], font=("Georgia", 7, "bold")).pack(anchor="w")
            tk.Label(card, textvariable=var, bg=PALETTE["panel"], fg=value_color, font=("Segoe UI Semibold", 12)).pack(anchor="w")
        metric_grid.columnconfigure(0, weight=1)
        metric_grid.columnconfigure(1, weight=1)

    def _astrolabe_button(self, parent: tk.Widget, label: str, command: Callable[[], None]) -> tk.Button:
        return tk.Button(
            parent,
            text=label,
            command=command,
            bg=PALETTE["button"],
            fg=PALETTE["astrolabe_gold"],
            activebackground=PALETTE["button_hover"],
            activeforeground=PALETTE["text"],
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=3,
            cursor="hand2",
            font=("Georgia", 8, "bold"),
            highlightthickness=1,
            highlightbackground=PALETTE["astrolabe_line"],
        )

    def _refresh_judgment_panel(self, snapshot: dict[str, object]) -> None:
        if not hasattr(self, "judgment_score_var"):
            return
        raw_score = snapshot.get("score", "--")
        self.judgment_score_var.set(str(raw_score))
        try:
            score_value = int(raw_score)
        except (TypeError, ValueError):
            score_value = 0
        breakdown = snapshot.get("scoreBreakdown", {})
        evaluation = breakdown.get("evaluation", {}) if isinstance(breakdown, dict) else {}
        grade = evaluation.get("grade", "n/a") if isinstance(evaluation, dict) else "n/a"
        band = evaluation.get("band", score_band_label(score_value)) if isinstance(evaluation, dict) else score_band_label(score_value)
        self.judgment_grade_var.set(f"{band} / Grade {grade}")
        for variable, line in zip(self.judgment_line_vars, compact_judgment_lines(snapshot)):
            variable.set(line)
        if hasattr(self, "validation_panel_vars"):
            validation_lines = [str(line).lstrip("- ") for line in validation_summary_lines(snapshot, self.current_location)[:4]]
            for index, variable in enumerate(self.validation_panel_vars):
                variable.set(validation_lines[index] if index < len(validation_lines) else "")
        if hasattr(self, "house_geometry_var"):
            self.house_geometry_var.set("\n".join(house_geometry_insight_lines(snapshot)[:4]))
        if hasattr(self, "aspect_dashboard_var"):
            dashboard_lines = []
            highlights = self.current_aspect_highlights if isinstance(self.current_aspect_highlights, dict) else {}
            for label, key in (("Now", "current"), ("Day", "localDay"), ("24h", "rolling24Hours")):
                result = highlights.get(key)
                if isinstance(result, Mapping):
                    dashboard_lines.append(f"{label}: {format_aspect_highlight(result).splitlines()[0]}")
            self.aspect_dashboard_var.set("\n".join(dashboard_lines) if dashboard_lines else "No selected major aspect in orb.")

    def _build_window_list_panel(self) -> None:
        frame = tk.Frame(self.right_panel, bg=PALETTE["astrolabe_panel"], highlightbackground=PALETTE["astrolabe_line"], highlightthickness=1, padx=8, pady=7)
        frame.pack(fill=tk.X, pady=(0, 7))
        header = tk.Frame(frame, bg=PALETTE["astrolabe_panel"])
        header.pack(fill=tk.X)
        tk.Label(header, text="CANDIDATE BOARD", bg=PALETTE["astrolabe_panel"], fg=PALETTE["astrolabe_gold"], font=("Georgia", 8, "bold"), anchor="w").pack(side=tk.LEFT)
        self.candidate_board_summary_var = tk.StringVar(value="No search yet")
        tk.Label(
            frame,
            textvariable=self.candidate_board_summary_var,
            bg=PALETTE["astrolabe_panel"],
            fg=PALETTE["astrolabe_muted"],
            font=("Segoe UI", 7),
            wraplength=310,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(3, 6))
        viewport = ttk.Frame(frame, style="Panel.TFrame")
        viewport.pack(fill=tk.X)
        self.window_cards_canvas = tk.Canvas(
            viewport,
            height=310,
            bg=PALETTE["panel"],
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
            bd=0,
        )
        scrollbar = ttk.Scrollbar(viewport, orient=tk.VERTICAL, command=self.window_cards_canvas.yview)
        self.window_cards_frame = ttk.Frame(self.window_cards_canvas, style="Panel.TFrame")
        self.window_cards_window = self.window_cards_canvas.create_window((0, 0), window=self.window_cards_frame, anchor="nw")
        self.window_cards_canvas.configure(yscrollcommand=scrollbar.set)
        self.window_cards_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.window_cards_frame.bind(
            "<Configure>",
            lambda _event: self.window_cards_canvas.configure(scrollregion=self.window_cards_canvas.bbox("all")),
        )
        self.window_cards_canvas.bind(
            "<Configure>",
            lambda event: self.window_cards_canvas.itemconfigure(self.window_cards_window, width=event.width),
        )
        buttons = ttk.Frame(frame, style="Panel.TFrame")
        buttons.pack(fill=tk.X, pady=(7, 0))
        actions = (
            ("Prev", lambda: self._select_relative_window(-1)),
            ("Next", lambda: self._select_relative_window(1)),
            ("Use Time", self._use_selected_window_time),
            ("Save Pick", self._add_selected_to_shortlist),
            ("Copy", self._copy_current_report),
        )
        for index, (label, command) in enumerate(actions):
            buttons.columnconfigure(index % 3, weight=1, uniform="candidate-actions")
            ttk.Button(buttons, text=label, command=command, style="Compact.TButton").grid(
                row=index // 3,
                column=index % 3,
                sticky="ew",
                padx=(0 if index % 3 == 0 else 3, 0 if index % 3 == 2 else 3),
                pady=(0 if index < 3 else 5, 0),
            )

    def _text_panel(self, title: str, height: int) -> tk.Text:
        frame = ttk.LabelFrame(self.right_panel, text=title, style="Panel.TLabelframe", padding=7)
        frame.pack(fill=tk.X, pady=(0, 9))
        text = tk.Text(
            frame,
            width=40,
            height=height,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
        )
        text.pack(fill=tk.X)
        text.configure(state=tk.DISABLED)
        return text

    def _tab_placeholder_text(self, title: str) -> str:
        purpose = {
            "Summary": "Dashboard overview for the displayed chart.",
            "Window": "Selected candidate timing, reasons, and next actions.",
            "Advisor": "Practical electional advice and cautions.",
            "Improve": "Specific changes that may improve the current election.",
            "Decision": "Go/no-go brief for the selected window.",
            "Compare": "Comparison between the input chart and candidate windows.",
            "Diagnostics": "Calculation health, validation, and data-quality notes.",
            "Search": "Search settings, candidate counts, rejected windows, and filter explanations.",
            "Focus": "Point interpretation after selecting a planet, lot, node, star, or timeline aspect.",
            "Score": "Score breakdown, grade, reasons, and angular testimony.",
            "Accounting": "Line-by-line point accounting behind the score.",
            "Conditions": "Planet, Moon, and calculation condition notes.",
            "Angles": "Angular contacts and angle-based electional testimony.",
            "Point Data": "Classical point table for planets, lots, nodes, and houses.",
            "Medieval": "Traditional condition, dignity, reception, and house-rule context when available.",
            "Rules": "Pure Python electional rules, planetary hour, nakshatra, tithi, and cautions.",
            "Significators": "Objective significators and their condition.",
            "Moon": "Moon condition, phase, void status, and applying contacts.",
            "House Rulers": "Relevant house lords and their electional condition.",
            "Reception": "Reception, dispositors, and whether planets can help each other.",
            "Planet Condition": "Motion, dignity availability, angularity, and planet-specific notes.",
            "Declination": "Parallels, contra-parallels, and declination diagnostics.",
            "Advanced": "Advanced aspect diagnostics and secondary testimony.",
            "Factor Explorer": "Grouped scoring factors and why they moved the grade.",
            "Constellations": "True 13-sign constellation placement diagnostics.",
            "Cusps": "House cusp positions and house-system context.",
            "Lots": "Arabic lots/parts, formulas, and house placement.",
            "Nodes": "Lunar node positions and angle proximity.",
            "Timing": "Applying/separating contacts and exact-time guidance.",
            "Planets": "Planet positions, houses, motion, dignity, and angular flags.",
            "Aspects": "Selected aspect contacts currently in orb.",
            "Aspectarian": "Grid-style aspect table for the current point set.",
            "Aspect Strength": "Strongest support and stress contacts by strength.",
            "Fixed Stars": "Fixed-star reference positions and contacts.",
            "Shortlist": "Saved candidates and their rankable decision data.",
            "Pick Compare": "Two saved candidates compared side by side.",
            "Button Health": "Checks visible navigation buttons and page targets.",
            "Log": "Recent app events, calculations, exports, and selection actions.",
        }.get(title, "Electional detail page.")
        return "\n".join(
            [
                title,
                "",
                purpose,
                "",
                "Waiting for chart data.",
                "Run Calculate or Find Best to populate this page with live electional testimony.",
            ]
        )

    def _text_tab(self, title: str) -> tk.Text:
        frame = ttk.Frame(self.detail_notebook, style="Panel.TFrame", padding=4)
        self.detail_notebook.add(frame, text=title)
        text = tk.Text(
            frame,
            width=40,
            height=16,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Segoe UI", 8),
            padx=6,
            pady=5,
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
        )
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, self._tab_placeholder_text(title))
        text.configure(state=tk.DISABLED)
        return text

    def _visual_tab(self, title: str) -> tuple[tk.Canvas, ttk.Frame]:
        tab = ttk.Frame(self.detail_notebook, style="Panel.TFrame", padding=4)
        self.detail_notebook.add(tab, text=title)
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        canvas = tk.Canvas(
            tab,
            bg=PALETTE["panel"],
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
            bd=0,
        )
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        body = ttk.Frame(canvas, style="Panel.TFrame", padding=8)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        body.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", lambda event, target=canvas: target.yview_scroll(int(-1 * (event.delta / 120)), "units")))
        canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))
        return canvas, body

    def _clear_frame(self, frame: tk.Widget) -> None:
        for child in frame.winfo_children():
            child.destroy()

    def calculate(self, *, show_input_chart: bool = False) -> None:
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        zodiac_system = get_zodiac_system(self.zodiac_system_var.get())
        house_system = get_house_system(self.house_system_var.get())
        selected_aspects = [aspect for aspect, var in self.aspect_vars.items() if var.get()]
        aspect_definitions = self._active_aspect_definitions()
        if not selected_aspects:
            self.validation_var.set("Validation failed:\n- Select at least one aspect focus before calculating.")
            self._refresh_left_status_chips()
            self.status_var.set("Validation: failed. Select at least one aspect focus.")
            messagebox.showerror("Electional validation failed", "Select at least one aspect focus before calculating.")
            return
        errors = validate_election_inputs(
            self.date_var.get(),
            self.time_var.get(),
            self.latitude_var.get(),
            self.longitude_var.get(),
            self.timezone_var.get(),
        )
        errors.extend(
            validate_search_inputs(
                self.scan_hours_var.get(),
                self.step_minutes_var.get(),
                self.minimum_score_var.get(),
                self.max_results_var.get(),
                self.minimum_fit_var.get(),
                self.minimum_confidence_var.get(),
                self.minimum_cleanliness_var.get(),
                self.maximum_volatility_var.get(),
            )
        )
        if errors:
            message = "Validation failed:\n" + "\n".join(f"- {error}" for error in errors)
            self.validation_var.set(message)
            self._refresh_left_status_chips()
            self.status_var.set("Validation: failed. Fix the highlighted input values and calculate again.")
            messagebox.showerror("Electional validation failed", message)
            return

        location = build_custom_location(
            self.location_name_var.get(),
            self.latitude_var.get(),
            self.longitude_var.get(),
            self.timezone_var.get(),
        )
        normalized_time = normalize_time_text(self.time_var.get())
        self.time_var.set(normalized_time)
        search_config = build_search_config_from_text(
            self.scan_hours_var.get(),
            self.step_minutes_var.get(),
            self.minimum_score_var.get(),
            self.max_results_var.get(),
            self.minimum_fit_var.get(),
            avoid_major_stress=self.avoid_major_stress_var.get(),
            require_applying_support=self.require_applying_support_var.get(),
            require_angular_benefic=self.require_angular_benefic_var.get(),
            avoid_angular_malefics=self.avoid_angular_malefics_var.get(),
            require_moon_non_void=self.require_moon_non_void_var.get(),
            avoid_objective_antipatterns=self.avoid_objective_antipatterns_var.get(),
            minimum_confidence_text=self.minimum_confidence_var.get(),
            minimum_cleanliness_text=self.minimum_cleanliness_var.get(),
            maximum_volatility_text=self.maximum_volatility_var.get(),
            search_quality_mode_text=self.search_quality_mode_var.get(),
        )
        self._update_search_summary()

        try:
            report = build_election_report(
                self.date_var.get(),
                normalized_time,
                location,
                preset.id,
                selected_aspects,
                zodiac_system.id,
                house_system.id,
                search_config,
                self.objective_var.get(),
                aspect_definitions,
            )
        except Exception as exc:  # pragma: no cover - exercised manually through the desktop UI.
            debug_path = record_desktop_exception("Electional calculation failed")
            self._log_event(f"Calculation failed: {exc}")
            detail = f"\n\nDebug trace: {debug_path}" if debug_path else ""
            messagebox.showerror("Electional calculation failed", f"{exc}{detail}")
            return

        snapshot = report["snapshot"]
        windows = report["windows"]
        selected_window = snapshot if show_input_chart else (windows[0] if windows else snapshot)
        selected_index = -1 if selected_window is snapshot else 0
        self.current_location = location
        self.input_snapshot = snapshot
        self.current_windows = list(windows)
        search_mode = str(report.get("searchMode") or "full")
        deep_count = int(report.get("deepWindowCount") or len(windows))
        searched_count = int(report.get("searchedWindowCount") or len(windows))
        evaluated_count = int(report.get("evaluatedWindowCount") or searched_count)
        refined_count = int(report.get("refinedWindowCount") or 0)
        cache = report.get("snapshotCache", {})
        cache_text = ""
        if isinstance(cache, dict):
            cache_text = f" Cache hits {cache.get('hits', 0)}, stored {cache.get('currsize', 0)}."
        self.current_search_summary = (
            f"{format_search_summary(search_config)} Mode: {search_mode}; evaluated {evaluated_count} "
            f"({searched_count} coarse + {refined_count} refined); deep-built {deep_count}. "
            f"Aspect profile: {self.active_aspect_profile.name}; active aspects {len(selected_aspects)}.{cache_text}"
        )
        self.current_rejection_summary = dict(report.get("rejectionSummary") or {})
        self.current_searched_window_count = evaluated_count
        self.selected_window = selected_window
        self.selected_window_index = selected_index
        self.displayed_chart_source = "input chart" if show_input_chart or not windows else "selected candidate"
        self.current_aspect_highlights = self._build_displayed_aspect_highlights(selected_window, location)

        self.title_var.set(f"{self.objective_var.get()} near {location.name}")
        self.natal_summary.configure(
            text=(
                f"{self.date_var.get()} {self.time_var.get()}\n"
                f"{location.name}\n"
                f"{location.latitude:.4f}, {location.longitude:.4f}\n"
                f"{location.timezone}\n"
                f"{selected_window['zodiacSystem'].name} / {selected_window['houseSystem'].name}"
            )
        )
        self.score_var.set(str(selected_window["score"]))
        self.score_band_var.set(f"{score_band_label(int(selected_window['score']))} window")
        validation = selected_window.get("locationValidation", {})
        validation_suffix = ""
        if isinstance(validation, dict) and validation.get("correctedKnownLocation"):
            validation_suffix = " | Indio corrected"
        if not selected_window.get("traditionalRulesEnabled", True):
            validation_suffix += " | 13-sign rules off"
        accuracy_label = self._accuracy_status_label(selected_window)
        self.validation_var.set(f"Validation: {accuracy_label}{validation_suffix}")
        self._refresh_left_status_chips()
        result_note = f"{len(windows)} matching window{'s' if len(windows) != 1 else ''}"
        if not windows:
            result_note = "No matching windows; showing the input chart"
        self.status_var.set(
            (
                f"Location: {location.name}    Chart time: {selected_window['formattedTime']}    "
                f"Search: {search_config.end_offset_minutes // 60}h/{search_config.step_minutes}m    "
                f"Results: {result_note} of {evaluated_count} evaluated    "
                f"System: {zodiac_system.name} / {house_system.name}    Validation: {accuracy_label}"
            )
        )
        self._log_event(
            (
                f"Calculated {location.name}: selected {selected_window['formattedTime']} "
                f"score {selected_window['score']} ({zodiac_system.name} / {house_system.name})"
            )
        )
        self._set_timing_context(snapshot, selected_window, location)
        self._render_summary_chips(selected_window)
        self._refresh_classic_side_panels(selected_window, location)
        self._populate_window_list(windows)
        self._refresh_search_workbench_strip()
        self.selected_window_index = selected_index
        self._refresh_window_card_styles()
        self._draw_wheel(selected_window)
        self._render_text_panels(selected_window, windows, location)
        self._apply_current_theme()
        self._save_session()

    def _populate_window_list(self, windows: list[dict[str, object]]) -> None:
        for card in self.window_cards:
            card.destroy()
        self.window_cards = []
        self._refresh_candidate_board_summary(windows)
        if not windows:
            empty_card = tk.Frame(
                self.window_cards_frame,
                bg=PALETTE["panel_alt"],
                highlightbackground=PALETTE["astrolabe_line"],
                highlightthickness=1,
                padx=10,
                pady=10,
            )
            empty_card.pack(fill=tk.X, padx=5, pady=(5, 7))
            tk.Label(
                empty_card,
                text="No candidate windows matched the current filters.",
                bg=PALETTE["panel_alt"],
                fg=PALETTE["astrolabe_ink"],
                font=("Georgia", 9, "bold"),
                wraplength=300,
                justify=tk.LEFT,
            ).pack(fill=tk.X)
            summary = self.current_rejection_summary if isinstance(self.current_rejection_summary, dict) else {}
            top_reasons = summary.get("topReasons", [])
            suggestions = summary.get("suggestedRelaxations", [])
            if isinstance(top_reasons, list) and top_reasons:
                reason_text = "Top blockers:\n" + "\n".join(f"{reason} ({count})" for reason, count in top_reasons[:4])
                tk.Label(
                    empty_card,
                    text=reason_text,
                    bg=PALETTE["panel_alt"],
                    fg=PALETTE["astrolabe_ink"],
                    font=("Segoe UI", 8),
                    wraplength=300,
                    justify=tk.LEFT,
                    anchor="w",
                ).pack(fill=tk.X, pady=(6, 0))
            if isinstance(suggestions, list) and suggestions:
                tk.Label(
                    empty_card,
                    text="Suggested relaxations",
                    bg=PALETTE["panel_alt"],
                    fg=PALETTE["accent_dark"],
                    font=("Georgia", 8, "bold"),
                    anchor="w",
                ).pack(fill=tk.X, pady=(8, 2))
                suggestion_wrap = tk.Frame(empty_card, bg=PALETTE["panel_alt"])
                suggestion_wrap.pack(fill=tk.X)
                for suggestion in suggestions[:3]:
                    suggestion_card = tk.Frame(
                        suggestion_wrap,
                        bg=PALETTE["chip"],
                        highlightbackground=PALETTE["chip_line"],
                        highlightthickness=1,
                        padx=7,
                        pady=4,
                    )
                    suggestion_card.pack(fill=tk.X, pady=(0, 4))
                    tk.Label(
                        suggestion_card,
                        text=str(suggestion),
                        bg=PALETTE["chip"],
                        fg=PALETTE["accent_dark"],
                        font=("Segoe UI Semibold", 7),
                        wraplength=285,
                        justify=tk.LEFT,
                        anchor="w",
                    ).pack(fill=tk.X)
                ttk.Button(empty_card, text="Open Search Page", command=self._open_search_workbench_page, style="Compact.TButton").pack(fill=tk.X, pady=(4, 0))
            else:
                tk.Label(
                    empty_card,
                    text="Open the Search page to inspect filters and rejected-window diagnostics.",
                    bg=PALETTE["panel_alt"],
                    fg=PALETTE["muted"],
                    font=("Segoe UI", 8),
                    wraplength=300,
                    justify=tk.LEFT,
                    anchor="w",
                ).pack(fill=tk.X, pady=(6, 0))
            self.selected_window_index = -1
            self._refresh_candidate_board_summary(windows)
            self._refresh_workflow_next_step()
            return
        for index, window in enumerate(windows, start=1):
            self._create_window_card(index - 1, window)
        if self.selected_window_index >= len(windows):
            self.selected_window_index = 0
        self._refresh_window_card_styles()

    def _create_window_card(self, index: int, window: dict[str, object]) -> None:
        score = int(window.get("score", 0))
        card_bg = window_score_color(score)
        card = tk.Frame(
            self.window_cards_frame,
            bg=card_bg,
            highlightbackground=PALETTE["astrolabe_gold"] if index == self.selected_window_index else PALETTE["panel_line"],
            highlightthickness=1,
            padx=9,
            pady=8,
        )
        card.pack(fill=tk.X, padx=5, pady=(5, 6))
        self.window_cards.append(card)
        header = tk.Frame(card, bg=card["bg"])
        header.pack(fill=tk.X)
        header.columnconfigure(1, weight=1)
        tk.Label(
            header,
            text=f"#{index + 1}",
            bg=PALETTE["button"],
            fg=PALETTE["astrolabe_gold"],
            font=("Georgia", 7, "bold"),
            padx=6,
            pady=1,
        ).grid(row=0, column=0, sticky="w", padx=(0, 7))
        tk.Label(
            header,
            text=str(window["time"]),
            bg=card["bg"],
            fg=PALETTE["astrolabe_ink"],
            font=("Georgia", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")
        tk.Label(
            header,
            text=f"{score} {score_band_label(score)}",
            bg=PALETTE["panel_alt"],
            fg=PALETTE["astrolabe_gold"],
            font=("Georgia", 8, "bold"),
            padx=6,
            pady=1,
        ).grid(row=0, column=2, sticky="e")
        offset_text = selection_offset_label(self.input_snapshot or window, window)
        stage_text = self._search_stage_label(window)
        meta = tk.Frame(card, bg=card["bg"])
        meta.pack(fill=tk.X, pady=(4, 0))
        tk.Label(
            meta,
            text=offset_text,
            bg=card["bg"],
            fg=PALETTE["muted"],
            font=("Segoe UI Semibold", 7),
            anchor="w",
        ).pack(side=tk.LEFT)
        if stage_text:
            tk.Label(
                meta,
                text=stage_text,
                bg=PALETTE["chip"],
                fg=PALETTE["accent_dark"],
                font=("Segoe UI Semibold", 7),
                padx=5,
                pady=1,
            ).pack(side=tk.RIGHT)
        tk.Label(
            card,
            text=str(window.get("title", "Electional window")),
            bg=card["bg"],
            fg=PALETTE["astrolabe_ink"],
            font=("Georgia", 8, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))
        rank_reasons = window.get("rankReasons", [])
        if isinstance(rank_reasons, list) and rank_reasons:
            tk.Label(
                card,
                text=str(rank_reasons[0]),
                bg=card["bg"],
                fg=PALETTE["accent_dark"],
                font=("Segoe UI", 8, "bold"),
                anchor="w",
                wraplength=300,
                justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(3, 0))
        note = str(window.get("note", "")).strip()
        if note:
            tk.Label(
                card,
                text=note,
                bg=card["bg"],
                fg=PALETTE["astrolabe_muted"],
                font=("Segoe UI", 8),
                anchor="w",
                wraplength=300,
                justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(2, 0))
        if isinstance(rank_reasons, list) and len(rank_reasons) > 1:
            why_text = "\n".join(str(reason) for reason in rank_reasons[1:3])
            tk.Label(
                card,
                text=why_text,
                bg=card["bg"],
                fg=PALETTE["text"],
                font=("Segoe UI", 7),
                anchor="w",
                wraplength=300,
                justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(4, 0))
        why_window = str(window.get("whyThisWindow") or "").strip()
        if why_window and not rank_reasons:
            tk.Label(
                card,
                text=why_window,
                bg=card["bg"],
                fg=PALETTE["text"],
                font=("Segoe UI", 7),
                anchor="w",
                wraplength=300,
                justify=tk.LEFT,
            ).pack(fill=tk.X, pady=(4, 0))
        tag_row = tk.Frame(card, bg=card["bg"])
        tag_row.pack(fill=tk.X, pady=(6, 0))
        for badge_index, (text, tone) in enumerate(candidate_metric_badges(window)):
            bg, fg = self._candidate_badge_colors(tone)
            tag_row.columnconfigure(badge_index % 3, weight=1, uniform="candidate-badge")
            tk.Label(
                tag_row,
                text=text,
                bg=bg,
                fg=fg,
                font=("Segoe UI Semibold", 7),
                padx=4,
                pady=2,
            ).grid(row=badge_index // 3, column=badge_index % 3, sticky="ew", padx=(0 if badge_index % 3 == 0 else 2, 0 if badge_index % 3 == 2 else 2), pady=(0 if badge_index < 3 else 4, 0))
        self._bind_card_click(card, lambda selected=index: self._select_window_by_index(selected))
        self._bind_card_click(card, lambda selected=index: self._activate_window_card(selected), double_click=True)

    def _candidate_badge_colors(self, tone: str) -> tuple[str, str]:
        if tone in {"support", "confidence", "cleanliness", "fit"}:
            return "#e8f4eb", PALETTE["support"]
        if tone == "stress":
            return "#f8e5e8", PALETTE["stress"]
        if tone == "volatility":
            return "#fff2d8", PALETTE["warning"]
        if tone in {"stage", "balance"}:
            return PALETTE["chip"], PALETTE["accent_dark"]
        return PALETTE["button"], PALETTE["muted"]

    def _refresh_candidate_board_summary(self, windows: list[dict[str, object]] | None = None) -> None:
        if not hasattr(self, "candidate_board_summary_var"):
            return
        candidate_windows = list(windows if windows is not None else self.current_windows)
        self.candidate_board_summary_var.set(
            candidate_board_summary(
                candidate_windows,
                evaluated_count=getattr(self, "current_searched_window_count", len(candidate_windows)),
                search_mode=self.search_quality_mode_var.get() if hasattr(self, "search_quality_mode_var") else "",
                selected_index=self.selected_window_index,
                displayed_source=self.displayed_chart_source,
            )
        )

    def _refresh_search_workbench_strip(self) -> None:
        if not hasattr(self, "search_workbench_summary_var"):
            return
        windows = list(self.current_windows)
        selected = self.selected_window or self.input_snapshot
        active_aspects = len(self._selected_aspect_ids()) if getattr(self, "aspect_vars", None) else 0
        profile_name = self.active_aspect_profile.name if hasattr(self, "active_aspect_profile") else "Major Five"
        selected_time = str(selected.get("formattedTime", "waiting")) if isinstance(selected, dict) else "waiting"
        self.search_workbench_title_var.set(f"Search Workbench | {profile_name}")
        action_note = f"Last action: {self.search_workbench_last_action}. "
        if windows:
            top = windows[0]
            summary = (
                f"{action_note}{len(windows)} candidate window{'s' if len(windows) != 1 else ''} ready; "
                f"top score {top.get('score', '?')} at {top.get('formattedTime', top.get('time', 'time n/a'))}."
            )
            strongest = ""
            aspects = top.get("detectedAspects", []) if isinstance(top, dict) else []
            if isinstance(aspects, list) and aspects:
                strongest = f" Strongest: {aspects[0].get('label', 'aspect')} ({aspects[0].get('orbText', 'orb n/a')})."
            detail = (
                f"Mode: {self.search_quality_mode_var.get()} | "
                f"Scan {self.scan_hours_var.get()}h every {self.step_minutes_var.get()}m | "
                f"active aspects {active_aspects} | {house_geometry_summary(selected)}.{strongest}"
            )
        else:
            summary = f"{action_note}No candidate windows matched yet; displayed chart is {selected_time}."
            blockers: list[str] = []
            rejection_summary = self.current_rejection_summary if isinstance(self.current_rejection_summary, dict) else {}
            top_reasons = rejection_summary.get("topReasons", [])
            if isinstance(top_reasons, list) and top_reasons:
                blockers = [f"{reason} ({count})" for reason, count in top_reasons[:2]]
            suggestions = rejection_summary.get("suggestedRelaxations", [])
            suggestion_text = ""
            if isinstance(suggestions, list) and suggestions:
                suggestion_text = f" Try: {suggestions[0]}"
            detail = (
                f"Mode: {self.search_quality_mode_var.get()} | "
                f"active aspects {active_aspects} | "
                f"{house_geometry_summary(selected)} | "
                f"blockers: {', '.join(blockers) if blockers else 'none reported yet'}.{suggestion_text}"
            )
        self.search_workbench_summary_var.set(summary)
        self.search_workbench_detail_var.set(detail)

    def _bind_card_click(self, widget: tk.Widget, command: Callable[[], None], *, double_click: bool = False) -> None:
        widget.bind("<Double-Button-1>" if double_click else "<Button-1>", lambda _event: command())
        widget.bind("<Enter>", lambda _event: widget.configure(cursor="hand2"))
        widget.bind("<Leave>", lambda _event: widget.configure(cursor=""))
        for child in widget.winfo_children():
            self._bind_card_click(child, command, double_click=double_click)

    def _select_window_by_index(self, index: int) -> None:
        if not self.current_windows or not self.current_location:
            return
        if index < 0 or index >= len(self.current_windows):
            return
        self.selected_window_index = index
        selected = self.current_windows[index]
        self.selected_window = selected
        self.displayed_chart_source = "selected candidate"
        self.current_aspect_highlights = self._build_displayed_aspect_highlights(selected, self.current_location)
        self.score_var.set(str(selected["score"]))
        self.score_band_var.set(f"{score_band_label(int(selected['score']))} window")
        accuracy_label = self._accuracy_status_label(selected)
        self.status_var.set(
            f"Location: {self.current_location.name}    Chart time: {selected['formattedTime']}    System: {selected['zodiacSystem'].name} / {selected['houseSystem'].name}    Validation: {accuracy_label}"
        )
        self._log_event(f"Selected window #{index + 1}: {selected['formattedTime']} score {selected['score']}")
        self._set_timing_context(self.input_snapshot or selected, selected, self.current_location)
        self._render_summary_chips(selected)
        self._refresh_classic_side_panels(selected, self.current_location)
        self._refresh_search_workbench_strip()
        self._refresh_window_card_styles()
        self._refresh_workflow_next_step()
        self._draw_wheel(selected)
        self._render_text_panels(selected, self.current_windows, self.current_location)
        self._apply_current_theme()

    def _activate_window_card(self, index: int) -> None:
        self._select_window_by_index(index)
        self._use_selected_window_time()

    def _select_relative_window(self, delta: int) -> None:
        if not self.current_windows:
            return
        next_index = (self.selected_window_index + delta) % len(self.current_windows)
        self._select_window_by_index(next_index)

    def _select_window_from_list(self, _event: object | None = None) -> None:
        self._select_window_by_index(self.selected_window_index)

    def _refresh_window_card_styles(self) -> None:
        for index, card in enumerate(self.window_cards):
            selected = index == self.selected_window_index
            card.configure(highlightbackground=PALETTE["astrolabe_gold"] if selected else PALETTE["panel_line"], highlightthickness=2 if selected else 1)
        self._refresh_candidate_board_summary()
        self._refresh_workflow_next_step()

    def _accuracy_status_label(self, snapshot: dict[str, object]) -> str:
        accuracy = snapshot.get("accuracyAudit", {})
        if isinstance(accuracy, dict):
            label = str(accuracy.get("label") or "").strip()
            if label:
                return label
            status = str(accuracy.get("status") or "").strip()
            if status:
                return status.title()
        return "Pass"

    def _search_stage_label(self, window: dict[str, object]) -> str:
        stage = str(window.get("searchStage") or "").strip().lower()
        resolution = window.get("searchResolutionMinutes")
        if stage == "refined":
            return f"{resolution}m refined" if resolution else "refined"
        if stage == "input":
            return "input"
        return ""

    def _set_timing_context(
        self,
        input_snapshot: dict[str, object],
        selected_window: dict[str, object],
        location: LocationPreset | None = None,
    ) -> None:
        offset = selection_offset_label(input_snapshot, selected_window)
        source = "Current Chart" if self.displayed_chart_source == "input chart" else f"Selected Window #{self.selected_window_index + 1}"
        self.timing_context_var.set(
            f"{location_summary(location)}    Displayed: {source} at {selected_window['formattedTime']}    Search start: {input_snapshot['formattedTime']}    {offset}"
        )
        self.location_state_var.set(location_summary(location))
        self.input_state_var.set(compact_time_label(input_snapshot))
        self.selected_state_var.set(compact_time_label(selected_window))
        self.offset_state_var.set(offset)

    def _build_displayed_aspect_highlights(
        self,
        displayed_snapshot: dict[str, object],
        location: LocationPreset | None,
    ) -> dict[str, object]:
        if not location:
            return {}
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        zodiac_system = get_zodiac_system(self.zodiac_system_var.get())
        house_system = get_house_system(self.house_system_var.get())
        selected_aspects = self._selected_aspect_ids()

        def snapshot_builder(moment: datetime) -> dict[str, object]:
            return build_snapshot_for_moment(
                moment,
                location,
                preset,
                selected_aspects,
                zodiac_system.id,
                house_system.id,
                self.objective_var.get(),
                "fast",
                self._active_aspect_definitions(),
            )

        try:
            return build_aspect_highlights(displayed_snapshot, location.timezone, snapshot_builder)
        except Exception as exc:  # pragma: no cover - UI resilience path.
            self._log_event(f"Aspect highlight scan failed: {exc}")
            return {}

    def _use_selected_window_time(self) -> None:
        if not self.selected_window or not self.current_location:
            return
        local = self.selected_window["date"].astimezone(ZoneInfo(self.current_location.timezone))
        self.date_var.set(local.strftime("%Y-%m-%d"))
        self.time_var.set(local.strftime("%H:%M"))
        self._log_event(f"Applied selected window to input time: {self.date_var.get()} {self.time_var.get()}")
        self.calculate(show_input_chart=True)

    def _event_wheel_degrees(self, event: tk.Event) -> float | None:
        geometry = getattr(self, "_wheel_drag_geometry", {})
        if not geometry:
            return None
        try:
            return wheel_degrees_from_xy(float(geometry["cx"]), float(geometry["cy"]), float(event.x), float(event.y))
        except (KeyError, TypeError, ValueError):
            return None

    def _start_moon_drag(self, event: tk.Event, planet_id: str) -> None:
        if not self.selected_window:
            return
        self._moon_drag_state = {
            "planet_id": planet_id,
            "start_x": float(event.x),
            "start_y": float(event.y),
            "moved": False,
            "target_degrees": self._event_wheel_degrees(event),
        }
        self.canvas.configure(cursor="fleur")
        self.status_var.set("Moon drag ready: move around the wheel, then release to calculate that timing.")

    def _drag_moon_marker(self, event: tk.Event) -> None:
        state = getattr(self, "_moon_drag_state", {})
        if not state:
            return
        start_x = float(state.get("start_x", event.x))
        start_y = float(state.get("start_y", event.y))
        moved = math.hypot(float(event.x) - start_x, float(event.y) - start_y) >= 4.0
        target_degrees = self._event_wheel_degrees(event)
        state["moved"] = bool(state.get("moved")) or moved
        state["target_degrees"] = target_degrees
        self._moon_drag_state = state
        self._draw_moon_drag_preview(target_degrees)
        if target_degrees is not None:
            self.status_var.set(f"Moon drag target: {target_degrees:.1f} deg on wheel. Release to solve chart time.")

    def _release_moon_drag(self, event: tk.Event, planet_id: str) -> None:
        state = getattr(self, "_moon_drag_state", {})
        self._moon_drag_state = {}
        self.canvas.delete("moon-drag-preview")
        self.canvas.configure(cursor="")
        if not state or not state.get("moved"):
            self._select_planet_by_id(planet_id)
            return
        target_degrees = self._event_wheel_degrees(event)
        if target_degrees is None:
            target_degrees = state.get("target_degrees")
        if target_degrees is None:
            self.status_var.set("Moon drag cancelled: wheel target was unavailable.")
            return
        self._apply_moon_drag_time(float(target_degrees))

    def _draw_moon_drag_preview(self, target_degrees: float | None) -> None:
        self.canvas.delete("moon-drag-preview")
        if target_degrees is None:
            return
        geometry = getattr(self, "_wheel_drag_geometry", {})
        try:
            cx = float(geometry["cx"])
            cy = float(geometry["cy"])
            outer = float(geometry["outer"])
        except (KeyError, TypeError, ValueError):
            return
        radius = outer * (0.720 if self._is_classic_wheel_theme() else 0.645)
        x, y = _polar(cx, cy, radius, target_degrees)
        inner_x, inner_y = _polar(cx, cy, max(30.0, radius - 55.0), target_degrees)
        self.canvas.create_line(inner_x, inner_y, x, y, fill=PALETTE["warning"], width=2, dash=(4, 4), tags=("moon-drag-preview",))
        self.canvas.create_oval(x - 15, y - 15, x + 15, y + 15, outline=PALETTE["warning"], width=2, tags=("moon-drag-preview",))
        self.canvas.create_text(
            x,
            y,
            text=planet_glyph("Moon"),
            fill=CLASSIC_PLANET_COLORS.get("Moon", PALETTE["warning"]),
            font=("Segoe UI Symbol", 18, "bold"),
            tags=("moon-drag-preview",),
        )

    def _apply_moon_drag_time(self, target_degrees: float) -> None:
        if not self.selected_window or not self.current_location:
            self.status_var.set("Moon drag needs an active calculated chart first.")
            return
        try:
            matched_time, matched_distance = self._find_time_for_moon_wheel_degrees(target_degrees)
        except Exception as exc:  # pragma: no cover - UI resilience path.
            debug_path = record_desktop_exception("Moon drag timing solve failed")
            detail = f" Debug trace: {debug_path}" if debug_path else ""
            self._log_event(f"Moon drag failed: {exc}")
            self.status_var.set(f"Moon drag failed: {exc}.{detail}")
            return
        local = matched_time.astimezone(ZoneInfo(self.current_location.timezone))
        self.date_var.set(local.strftime("%Y-%m-%d"))
        self.time_var.set(local.strftime("%H:%M"))
        self._log_event(
            f"Moon drag set input time to {self.date_var.get()} {self.time_var.get()} "
            f"for wheel angle {target_degrees:.1f} deg (miss {matched_distance:.2f} deg)"
        )
        self.status_var.set(
            f"Moon drag solved: {local:%Y-%m-%d %H:%M} local; recalculating aspects and election judgment."
        )
        self.calculate(show_input_chart=True)

    def _find_time_for_moon_wheel_degrees(self, target_degrees: float) -> tuple[datetime, float]:
        if not self.selected_window or not self.current_location:
            raise ValueError("No active chart/location is available.")
        start_moment = self.selected_window["date"]
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        zodiac_system = get_zodiac_system(self.zodiac_system_var.get())
        house_system = get_house_system(self.house_system_var.get())
        selected_aspects = self._selected_aspect_ids()
        aspect_definitions = self._active_aspect_definitions()

        def _moon_angle(moment: datetime) -> float:
            snapshot = build_snapshot_for_moment(
                moment,
                self.current_location,
                preset,
                selected_aspects,
                zodiac_system.id,
                house_system.id,
                self.objective_var.get(),
                "fast",
                aspect_definitions,
            )
            ascendant = next(angle for angle in snapshot["angles"] if angle["id"] == "asc")
            moon = next(planet for planet in snapshot["positions"] if planet["name"] == "Moon")
            return wheel_degrees(float(moon["longitude"]), float(ascendant["longitude"]))

        best_moment = start_moment
        best_distance = 999.0
        for offset_minutes in range(-18 * 60, 18 * 60 + 1, 10):
            moment = start_moment + timedelta(minutes=offset_minutes)
            distance = circular_distance_degrees(_moon_angle(moment), target_degrees)
            if distance < best_distance:
                best_moment = moment
                best_distance = distance
        refined_center = best_moment
        for offset_minutes in range(-12, 13):
            moment = refined_center + timedelta(minutes=offset_minutes)
            distance = circular_distance_degrees(_moon_angle(moment), target_degrees)
            if distance < best_distance:
                best_moment = moment
                best_distance = distance
        return best_moment, best_distance

    def _schedule_redraw(self, _event: object | None = None) -> None:
        if not self.selected_window:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(90, self._redraw_selected_window)

    def _redraw_selected_window(self) -> None:
        self._resize_job = None
        if self.selected_window:
            self._draw_wheel(self.selected_window)

    def _draw_wheel(self, snapshot: dict[str, object]) -> None:
        self.canvas.delete("all")
        measured_width = self.canvas.winfo_width()
        measured_height = self.canvas.winfo_height()
        width = measured_width if measured_width > 1 else int(self.canvas.cget("width"))
        height = measured_height if measured_height > 1 else int(self.canvas.cget("height"))
        if self._is_classic_wheel_theme():
            self._draw_classic_wheel(snapshot, width, height)
            return
        cx = width / 2
        cy = height / 2
        side_padding = 96 if not self.compact_wheel_var.get() and self.show_fixed_stars_var.get() else 70
        vertical_padding = 62 if self.compact_wheel_var.get() else 76
        fit_width = max(320, width - side_padding * 2)
        fit_height = max(320, height - vertical_padding * 2)
        outer = max(150, min(fit_width, fit_height) / 2 * self.wheel_zoom)
        constellation_inner = outer * 0.895
        sign_outer = outer * 0.885
        zodiac_inner = outer * 0.755
        house_inner = outer * (0.52 if self.compact_wheel_var.get() else 0.47)
        aspect_radius = outer * 0.425

        self._draw_grid(width, height)
        self.canvas.create_oval(cx - outer - 22, cy - outer - 16, cx + outer + 22, cy + outer + 28, fill="#e4ebf0", outline="")
        self.canvas.create_oval(cx - outer - 10, cy - outer - 8, cx + outer + 10, cy + outer + 14, fill="#edf2f5", outline="")
        self.canvas.create_oval(cx - outer + 7, cy - outer + 10, cx + outer + 7, cy + outer + 10, fill=PALETTE["surface_shadow"], outline="")
        self.canvas.create_oval(
            cx - outer,
            cy - outer,
            cx + outer,
            cy + outer,
            fill="#f7fafb",
            outline=PALETTE["chart_bezel"],
            width=3,
        )
        self.canvas.create_oval(
            cx - outer + 8,
            cy - outer + 8,
            cx + outer - 8,
            cy + outer - 8,
            outline=PALETTE["chart_bezel_inner"],
            width=1,
        )

        ascendant = next(angle for angle in snapshot["angles"] if angle["id"] == "asc")
        asc_lon = float(ascendant["longitude"])
        self._wheel_drag_geometry = {"cx": cx, "cy": cy, "outer": outer, "asc_lon": asc_lon}

        self._draw_constellation_band(cx, cy, outer, constellation_inner, asc_lon)
        self.canvas.create_oval(
            cx - constellation_inner,
            cy - constellation_inner,
            cx + constellation_inner,
            cy + constellation_inner,
            fill=PALETTE["chart_ring_fill"],
            outline="#ffffff",
            width=1,
        )

        for index, sign in enumerate(SIGN_LABELS):
            start = wheel_degrees(index * 30, asc_lon)
            self.canvas.create_arc(
                cx - sign_outer,
                cy - sign_outer,
                cx + sign_outer,
                cy + sign_outer,
                start=start,
                extent=30,
                fill=SIGN_COLORS[index],
                outline="#fffdf8",
                width=1,
            )
            label_angle = wheel_degrees(index * 30 + 15, asc_lon)
            lx, ly = _polar(cx, cy, sign_outer * 0.93, label_angle)
            self._draw_sign_badge(lx, ly, sign, SIGN_COLORS[index])

        self.canvas.create_oval(cx - sign_outer + 1, cy - sign_outer + 1, cx + sign_outer - 1, cy + sign_outer - 1, outline="#ffffff", width=1)
        self.canvas.create_oval(cx - sign_outer + 11, cy - sign_outer + 11, cx + sign_outer - 11, cy + sign_outer - 11, outline="#ffffff", width=1)
        self._draw_degree_ticks(cx, cy, sign_outer, zodiac_inner, asc_lon)

        self.canvas.create_oval(cx - zodiac_inner, cy - zodiac_inner, cx + zodiac_inner, cy + zodiac_inner, outline=PALETTE["chart_bezel"], width=2)
        self._draw_house_sectors(snapshot, cx, cy, zodiac_inner - 2, house_inner + 1, asc_lon)
        self.canvas.create_oval(
            cx - house_inner,
            cy - house_inner,
            cx + house_inner,
            cy + house_inner,
            fill=PALETTE["chart_inner"],
            outline=PALETTE["chart_bezel"],
            width=2,
        )
        self.canvas.create_oval(cx - house_inner + 8, cy - house_inner + 8, cx + house_inner - 8, cy + house_inner - 8, outline="#edf2ed", width=1)
        self.canvas.create_oval(
            cx - aspect_radius,
            cy - aspect_radius,
            cx + aspect_radius,
            cy + aspect_radius,
            outline=PALETTE["aspect_ring"],
            width=1,
            dash=(4, 5),
        )
        self.canvas.create_oval(cx - aspect_radius + 24, cy - aspect_radius + 24, cx + aspect_radius - 24, cy + aspect_radius - 24, outline=PALETTE["chart_bezel_inner"], width=1)
        self.canvas.create_oval(cx - 72, cy - 72, cx + 72, cy + 72, outline="#b7c2ca", width=2)

        house_cusps = sorted(snapshot.get("houseCusps", []), key=lambda cusp: int(cusp["house"]))
        span_by_house = {int(row["house"]): row["span"] for row in house_span_rows(snapshot)}
        for house_index, cusp in enumerate(house_cusps):
            next_cusp = house_cusps[(house_index + 1) % len(house_cusps)]
            house_no = int(cusp["house"])
            cusp_longitude = float(cusp["longitude"])
            label_longitude = midpoint_longitude(cusp_longitude, float(next_cusp["longitude"]))
            angle = wheel_degrees(cusp_longitude, asc_lon)
            x1, y1 = _polar(cx, cy, house_inner, angle)
            x2, y2 = _polar(cx, cy, zodiac_inner, angle)
            self.canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                fill=PALETTE["chart_line"],
                width=2 if house_no in {1, 4, 7, 10} else 1,
            )
            label_angle = wheel_degrees(label_longitude, asc_lon)
            lx, ly = _polar(cx, cy, outer * 0.64, label_angle)
            self.canvas.create_text(lx, ly, text=str(house_no), fill=PALETTE["accent_dark"], font=("Segoe UI Semibold", 10 if self.compact_wheel_var.get() else 12))
            span_text = house_span_label(span_by_house.get(house_no))
            if span_text and self._is_diagnostic_wheel_preset():
                sx, sy = _polar(cx, cy, outer * 0.585, label_angle)
                self._draw_halo_text(
                    sx,
                    sy,
                    text=span_text,
                    fill=PALETTE["muted"],
                    halo=PALETTE["surface"],
                    font=("Segoe UI", 7 if self.compact_wheel_var.get() else 8),
                    tags=("house-span",),
                )

        if self.show_aspects_var.get():
            self._draw_aspects(snapshot, cx, cy, aspect_radius, asc_lon)
        self._draw_angles(snapshot, cx, cy, outer, asc_lon)
        point_set = get_point_set(self.point_set_var.get())
        if self.show_fixed_stars_var.get() and point_set.show_fixed_stars and not self.compact_wheel_var.get():
            self._draw_fixed_stars(snapshot, cx, cy, asc_lon, outer)
        self._draw_planets(snapshot, cx, cy, asc_lon, outer)
        if self.show_lots_var.get() and point_set.show_lots and not self.compact_wheel_var.get():
            self._draw_lots(snapshot, cx, cy, asc_lon, outer)
        if self.show_nodes_var.get() and point_set.show_nodes and not self.compact_wheel_var.get():
            self._draw_nodes(snapshot, cx, cy, asc_lon, outer)
        self._draw_focused_body_callout(snapshot, cx, cy, outer, asc_lon)
        self._draw_center_hub(cx, cy, snapshot)
        self._draw_wheel_legend(width, height)

    def _draw_classic_wheel(self, snapshot: dict[str, object], width: int, height: int) -> None:
        metadata_width = 142 if width >= 600 else 0
        chart_width = max(320, width - metadata_width)
        cx = metadata_width + chart_width / 2
        cy = height / 2
        side_padding = 14 if self.show_fixed_stars_var.get() else 10
        fit_width = max(320, chart_width - side_padding * 2)
        fit_height = max(320, height - 14)
        outer = max(150, min(fit_width, fit_height) / 2 * self.wheel_zoom)
        sign_outer = outer * 0.958
        tick_outer = outer * 0.878
        zodiac_inner = outer * 0.760
        house_outer = outer * 0.525
        house_inner = outer * 0.385
        aspect_radius = outer * 0.382
        house_label_radius = (house_outer + house_inner) / 2
        self._classic_center_radius = aspect_radius

        self._draw_grid(width, height)
        if metadata_width:
            self._draw_classic_chart_info(snapshot, 10, 10, metadata_width - 20)
        self.canvas.create_oval(cx - outer - 8, cy - outer - 8, cx + outer + 8, cy + outer + 8, fill="#d6dbce", outline="")
        self.canvas.create_oval(cx - outer, cy - outer, cx + outer, cy + outer, fill=CLASSIC_CONSTELLATION_FILL, outline=CLASSIC_HOUSE_LINE, width=1)
        self.canvas.create_oval(cx - sign_outer, cy - sign_outer, cx + sign_outer, cy + sign_outer, fill="#eee6c7", outline="#000000", width=1)

        ascendant = next(angle for angle in snapshot["angles"] if angle["id"] == "asc")
        asc_lon = float(ascendant["longitude"])
        self._wheel_drag_geometry = {"cx": cx, "cy": cy, "outer": outer, "asc_lon": asc_lon}
        zodiac_system = snapshot.get("zodiacSystem")
        system_id = getattr(zodiac_system, "id", None) or getattr(zodiac_system, "name", None)
        segments = zodiac_arc_segments(system_id)

        for segment in segments:
            start = wheel_degrees(float(segment["start"]), asc_lon)
            self.canvas.create_arc(
                cx - sign_outer,
                cy - sign_outer,
                cx + sign_outer,
                cy + sign_outer,
                start=start,
                extent=float(segment["extent"]),
                fill=str(segment["color"]),
                outline="#f9f6df",
                width=1,
            )
            if float(segment["extent"]) < 4:
                continue
            label_angle = wheel_degrees(float(segment["midpoint"]), asc_lon)
            lx, ly = _polar(cx, cy, outer * 0.908, label_angle)
            label_font = ("Segoe UI Symbol", 12 if self.compact_wheel_var.get() else 14, "bold")
            if bool(segment.get("isOphiuchus")):
                self._draw_ophiuchus_symbol(lx, ly, 10 if self.compact_wheel_var.get() else 12)
            else:
                self._draw_halo_text(
                    lx,
                    ly,
                    text=str(segment.get("label") or segment.get("fallbackLabel") or ""),
                    fill=CLASSIC_SIGN_TEXT,
                    halo=CLASSIC_SIGN_HALO,
                    font=label_font,
                    tags=("sign-label",),
                )

        self.canvas.create_oval(cx - tick_outer, cy - tick_outer, cx + tick_outer, cy + tick_outer, fill=CLASSIC_TICK_RING, outline="#000000", width=1)
        self._draw_degree_ticks(cx, cy, tick_outer, zodiac_inner, asc_lon)
        self.canvas.create_oval(cx - zodiac_inner, cy - zodiac_inner, cx + zodiac_inner, cy + zodiac_inner, fill=CLASSIC_PLANET_FIELD, outline="#000000", width=1)
        self._draw_house_sectors(
            snapshot,
            cx,
            cy,
            zodiac_inner,
            house_outer,
            asc_lon,
            fills=CLASSIC_HOUSE_FIELD_COLORS,
            outline=CLASSIC_HOUSE_FIELD_LINE,
            width=1,
        )
        self._draw_house_sectors(snapshot, cx, cy, house_outer, house_inner, asc_lon, fills=CLASSIC_HOUSE_RING_COLORS, outline="#4b2345", width=1)
        self.canvas.create_oval(cx - house_outer, cy - house_outer, cx + house_outer, cy + house_outer, outline="#101010", width=1)
        self.canvas.create_oval(cx - house_inner, cy - house_inner, cx + house_inner, cy + house_inner, fill=CLASSIC_ASPECT_CENTER, outline=CLASSIC_HOUSE_LINE, width=1)

        house_cusps = sorted(snapshot.get("houseCusps", []), key=lambda cusp: int(cusp["house"]))
        span_by_house = {int(row["house"]): row["span"] for row in house_span_rows(snapshot)}
        house_labels: list[tuple[float, float, str]] = []
        house_span_labels: list[tuple[float, float, str]] = []
        for house_index, cusp in enumerate(house_cusps):
            next_cusp = house_cusps[(house_index + 1) % len(house_cusps)]
            house_no = int(cusp["house"])
            cusp_longitude = float(cusp["longitude"])
            next_longitude = float(next_cusp["longitude"])
            angle = wheel_degrees(cusp_longitude, asc_lon)
            x1, y1 = _polar(cx, cy, aspect_radius, angle)
            x2, y2 = _polar(cx, cy, zodiac_inner, angle)
            self.canvas.create_line(x1, y1, x2, y2, fill=CLASSIC_HOUSE_LINE, width=3 if house_no in {1, 4, 7, 10} else 2)
            marker_inner_x, marker_inner_y = _polar(cx, cy, house_outer - 5, angle)
            marker_outer_x, marker_outer_y = _polar(cx, cy, zodiac_inner + 3, angle)
            self.canvas.create_line(
                marker_inner_x,
                marker_inner_y,
                marker_outer_x,
                marker_outer_y,
                fill="#0f1534",
                width=2 if house_no in {1, 4, 7, 10} else 1,
                tags=("house-projection",),
            )
            label_angle = wheel_degrees(midpoint_longitude(cusp_longitude, next_longitude), asc_lon)
            lx, ly = _polar(cx, cy, house_label_radius, label_angle)
            house_labels.append((lx, ly, str(house_no)))
            span_text = house_span_label(span_by_house.get(house_no))
            if span_text and self._is_diagnostic_wheel_preset():
                sx, sy = _polar(cx, cy, house_outer + (zodiac_inner - house_outer) * 0.22, label_angle)
                house_span_labels.append((sx, sy, span_text))

        if self.show_aspects_var.get():
            self._draw_classic_aspects(snapshot, cx, cy, aspect_radius * 0.94, asc_lon)
        self._draw_angles(snapshot, cx, cy, outer, asc_lon)
        point_set = get_point_set(self.point_set_var.get())
        if self.show_fixed_stars_var.get() and point_set.show_fixed_stars:
            self._draw_fixed_stars(snapshot, cx, cy, asc_lon, outer)
        self._draw_planets(snapshot, cx, cy, asc_lon, outer)
        if self.show_lots_var.get() and point_set.show_lots:
            self._draw_lots(snapshot, cx, cy, asc_lon, outer)
        if self.show_nodes_var.get() and point_set.show_nodes:
            self._draw_nodes(snapshot, cx, cy, asc_lon, outer)
        for sx, sy, span_text in house_span_labels:
            self._draw_house_span_label(sx, sy, span_text)
        for lx, ly, house_text in house_labels:
            self._draw_house_number_badge(lx, ly, house_text)
        self._draw_focused_body_callout(snapshot, cx, cy, outer, asc_lon)
        self._draw_center_hub(cx, cy, snapshot)
        footer_y = min(height - 14, cy + outer + 18)
        zodiac_label = "Zodiac 13" if str(getattr(snapshot.get("zodiacSystem"), "id", "")).lower() == "true-13-sign" else str(getattr(snapshot.get("zodiacSystem"), "name", "Zodiac"))
        self.canvas.create_text(
            cx,
            footer_y,
            text=f"{zodiac_label} - Astrology Data Sheet",
            fill=CLASSIC_PANEL_TEXT,
            font=("Georgia", 9),
            tags=("classic-footer",),
        )
        self.canvas.create_text(
            cx,
            min(height - 4, footer_y + 12),
            text=house_geometry_summary(snapshot),
            fill=CLASSIC_PANEL_MUTED,
            font=("Segoe UI", 7),
            tags=("classic-footer",),
        )

    def _draw_house_number_badge(self, x: float, y: float, text: str) -> None:
        self._draw_halo_text(
            x,
            y,
            text=text,
            fill="#10121f",
            halo="#d6c1c9",
            font=("Georgia", 11 if self.compact_wheel_var.get() else 13, "bold"),
            tags=("house-label",),
        )

    def _draw_house_span_label(self, x: float, y: float, text: str) -> None:
        self._draw_halo_text(
            x,
            y,
            text=text,
            fill=CLASSIC_HOUSE_SPAN_TEXT,
            halo=CLASSIC_HOUSE_SPAN_HALO,
            font=("Segoe UI", 7 if self.compact_wheel_var.get() else 8, "bold"),
            tags=("house-span",),
        )

    def _draw_classic_aspects(self, snapshot: dict[str, object], cx: float, cy: float, radius: float, asc_lon: float) -> None:
        positions = {planet["name"]: planet for planet in self._visible_planets(snapshot)}
        ranked_aspects = sorted(
            [
                aspect
                for aspect in snapshot.get("detectedAspects", [])
                if isinstance(aspect, dict)
                and isinstance(aspect.get("bodies"), list)
                and len(aspect.get("bodies", [])) == 2
            ],
            key=lambda aspect: (
                bool(aspect.get("isApplying")),
                float(aspect.get("strength", 0) or 0),
                -float(aspect.get("orb", 99) or 99),
            ),
            reverse=True,
        )
        for aspect in ranked_aspects[:14]:
            body_a, body_b = aspect["bodies"]
            if body_a not in positions or body_b not in positions:
                continue
            angle_a = wheel_degrees(float(positions[body_a]["longitude"]), asc_lon)
            angle_b = wheel_degrees(float(positions[body_b]["longitude"]), asc_lon)
            x1, y1 = _polar(cx, cy, radius, angle_a)
            x2, y2 = _polar(cx, cy, radius, angle_b)
            tone = str(aspect.get("tone") or "")
            color = CLASSIC_ASPECT_SUPPORT if tone == "support" else CLASSIC_ASPECT_STRESS if tone == "stress" else CLASSIC_ASPECT_NEUTRAL
            width = 3 if aspect.get("isApplying") else 2
            dash = () if aspect.get("isApplying") else (5, 5)
            self.canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                fill=color,
                width=width,
                dash=dash,
                tags=("classic-aspect",),
            )

    def _draw_ophiuchus_symbol(self, x: float, y: float, size: float) -> None:
        color = CLASSIC_SIGN_TEXT
        halo = CLASSIC_SIGN_HALO
        self.canvas.create_line(x, y - size, x, y + size, fill=halo, width=4, tags=("sign-label-halo",))
        self.canvas.create_line(x - size * 0.55, y - size * 0.55, x + size * 0.55, y - size * 0.55, fill=halo, width=4, tags=("sign-label-halo",))
        self.canvas.create_line(x, y - size, x, y + size, fill=color, width=2, tags=("sign-label",))
        self.canvas.create_line(x - size * 0.55, y - size * 0.55, x + size * 0.55, y - size * 0.55, fill=color, width=2, tags=("sign-label-vector",))
        points = [
            x - size * 0.55,
            y + size * 0.25,
            x - size * 0.18,
            y + size * 0.55,
            x + size * 0.20,
            y + size * 0.10,
            x + size * 0.55,
            y + size * 0.45,
        ]
        self.canvas.create_line(*points, fill=halo, width=5, smooth=True, tags=("sign-label-halo",))
        self.canvas.create_line(*points, fill=color, width=2, smooth=True, tags=("sign-label-vector",))

    def _draw_center_hub(self, cx: float, cy: float, snapshot: dict[str, object]) -> None:
        if self._is_classic_wheel_theme():
            center_radius = float(getattr(self, "_classic_center_radius", 112.0))
            self.canvas.create_oval(cx - center_radius, cy - center_radius, cx + center_radius, cy + center_radius, fill="", outline=CLASSIC_CENTER_LINE, width=1)
            self.canvas.create_oval(cx - center_radius * 0.68, cy - center_radius * 0.68, cx + center_radius * 0.68, cy + center_radius * 0.68, fill="", outline=CLASSIC_CENTER_LINE, width=1)
            if self.show_score_overlay_var.get():
                self.canvas.create_text(cx, cy - 10, text=f"Score {snapshot['score']}", fill="#18214e", font=("Segoe UI Semibold", 13))
                self.canvas.create_text(cx, cy + 14, text=score_band_label(int(snapshot["score"])), fill="#00607b", font=("Segoe UI", 9, "bold"))
            return
        self.canvas.create_oval(cx - 63, cy - 58, cx + 63, cy + 68, fill="#dde7ec", outline="")
        self.canvas.create_oval(cx - 60, cy - 60, cx + 60, cy + 60, fill=PALETTE["center_hub"], outline=PALETTE["chart_bezel"], width=2)
        self.canvas.create_oval(cx - 49, cy - 49, cx + 49, cy + 49, outline=PALETTE["chart_bezel_inner"], width=1)
        self.canvas.create_oval(cx - 37, cy - 37, cx + 37, cy + 37, outline="#edf4f2", width=1)
        self.canvas.create_line(cx - 30, cy + 2, cx + 30, cy + 2, fill=PALETTE["chart_bezel_inner"], width=1)
        self.canvas.create_text(cx, cy - 12, text=f"Score {snapshot['score']}", fill=PALETTE["top_bar_dark"], font=("Segoe UI Semibold", 13 if self.compact_wheel_var.get() else 15))
        self.canvas.create_text(cx, cy + 15, text=score_band_label(int(snapshot["score"])), fill=PALETTE["accent_dark"], font=("Segoe UI Semibold", 8 if self.compact_wheel_var.get() else 9))

    def _draw_halo_text(
        self,
        x: float,
        y: float,
        *,
        text: str,
        fill: str,
        halo: str,
        font: tuple[str, int] | tuple[str, int, str],
        anchor: str = "center",
        tags: tuple[str, ...] = (),
    ) -> None:
        halo_tags = tuple(f"{tag}-halo" for tag in tags) if tags else ()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.canvas.create_text(x + dx, y + dy, text=text, fill=halo, font=font, anchor=anchor, tags=halo_tags)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor, tags=tags)

    def _is_focused_body(self, kind: str, name: str) -> bool:
        if kind == "planet" and name in getattr(self, "focused_aspect_bodies", set()):
            return True
        return self.focused_body_kind == kind and self.focused_body_name == name

    def _focused_wheel_target(self, snapshot: dict[str, object]) -> tuple[str, dict[str, object]] | None:
        if not self.focused_body_name or not self.focused_body_kind:
            return None
        if self.focused_body_kind == "planet":
            for planet in snapshot.get("positions", []):
                if isinstance(planet, dict) and str(planet.get("name")) == self.focused_body_name:
                    return ("planet", planet)
        if self.focused_body_kind == "lot":
            for lot in snapshot.get("lots", []):
                if isinstance(lot, dict) and str(lot.get("name")) == self.focused_body_name:
                    return ("lot", lot)
        if self.focused_body_kind == "node":
            for node in snapshot.get("lunarNodes", []):
                if isinstance(node, dict) and str(node.get("name")) == self.focused_body_name:
                    return ("node", node)
        if self.focused_body_kind == "star":
            for star in snapshot.get("fixedStars", []):
                if isinstance(star, dict) and str(star.get("name")) == self.focused_body_name:
                    return ("star", star)
        return None

    def _draw_focused_body_callout(self, snapshot: dict[str, object], cx: float, cy: float, outer: float, asc_lon: float) -> None:
        target = self._focused_wheel_target(snapshot)
        if not target:
            return
        kind, body = target
        degrees = wheel_degrees(float(body["longitude"]), asc_lon)
        anchor_radius = outer * (0.67 if kind == "planet" else 0.76 if kind == "lot" else 0.60 if kind == "node" else 0.90)
        anchor_x, anchor_y = _polar(cx, cy, anchor_radius, degrees)
        tip_x, tip_y = _polar(cx, cy, outer * 1.03, degrees)
        box_x, box_y = _polar(cx, cy, outer * 1.16, degrees)
        if self._is_classic_wheel_theme():
            label_x, label_y = _polar(cx, cy, outer * 1.10, degrees)
            label_anchor = "w" if math.cos(math.radians(degrees)) >= 0 else "e"
            position_text = classic_planet_degree_text(body)
            if not position_text and isinstance(body, Mapping) and "zodiac" in body:
                position_text = format_position(body)
            label_text = f"{body.get('name', kind.title())}  {position_text}".strip()
            self.canvas.create_line(anchor_x, anchor_y, tip_x, tip_y, label_x, label_y, fill="#385f94", width=1, smooth=True)
            self.canvas.create_text(
                label_x,
                label_y,
                text=label_text,
                anchor=label_anchor,
                fill="#203f73",
                font=("Segoe UI", 9, "bold"),
            )
            return
        is_right = math.cos(math.radians(degrees)) >= 0
        box_width = 104 if self.compact_wheel_var.get() else 118
        box_height = 38
        left = box_x - 10 if is_right else box_x - box_width + 10
        right = left + box_width
        top = box_y - box_height / 2
        bottom = box_y + box_height / 2
        pointer_x = left if is_right else right
        line_color = PALETTE["accent_dark"]
        self.canvas.create_line(anchor_x, anchor_y, tip_x, tip_y, pointer_x, box_y, fill=line_color, width=2, smooth=True)
        self.canvas.create_rectangle(left, top, right, bottom, fill=PALETTE["panel_alt"], outline=line_color, width=1)
        self.canvas.create_text(
            left + 8 if is_right else right - 8,
            top + 11,
            text=str(body.get("name", kind.title())),
            anchor="w" if is_right else "e",
            fill=PALETTE["top_bar_dark"],
            font=("Segoe UI Semibold", 8),
        )
        self.canvas.create_text(
            left + 8 if is_right else right - 8,
            top + 26,
            text=format_position(body),
            anchor="w" if is_right else "e",
            fill=PALETTE["muted"],
            font=("Segoe UI", 8),
        )

    def _draw_house_sectors(
        self,
        snapshot: dict[str, object],
        cx: float,
        cy: float,
        outer_radius: float,
        inner_radius: float,
        asc_lon: float,
        fills: tuple[str, ...] | None = None,
        outline: str = "",
        width: int = 1,
    ) -> None:
        house_cusps = sorted(snapshot.get("houseCusps", []), key=lambda cusp: int(cusp["house"]))
        if not house_cusps:
            return
        fills = fills or (PALETTE["chart_house_fill"], PALETTE["chart_house_fill_alt"])
        for index, cusp in enumerate(house_cusps):
            next_cusp = house_cusps[(index + 1) % len(house_cusps)]
            start = wheel_degrees(float(cusp["longitude"]), asc_lon)
            end = wheel_degrees(float(next_cusp["longitude"]), asc_lon)
            outer_points = _arc_points(cx, cy, outer_radius, start, end)
            inner_points = _arc_points(cx, cy, inner_radius, end, start)
            self.canvas.create_polygon(
                outer_points + inner_points,
                fill=fills[index % len(fills)],
                outline=outline,
                width=width,
            )

    def _draw_constellation_band(self, cx: float, cy: float, outer: float, inner: float, asc_lon: float) -> None:
        for segment in constellation_arc_segments():
            start = wheel_degrees(float(segment["start"]), asc_lon)
            extent = float(segment["extent"])
            self.canvas.create_arc(
                cx - outer,
                cy - outer,
                cx + outer,
                cy + outer,
                start=start,
                extent=extent,
                fill=str(segment["color"]),
                outline="#ffffff",
                width=1,
            )
        self.canvas.create_oval(cx - inner, cy - inner, cx + inner, cy + inner, fill="#f7fafb", outline=PALETTE["chart_bezel_inner"], width=1)
        if self.compact_wheel_var.get():
            return
        for segment in constellation_arc_segments():
            if float(segment["extent"]) < 10:
                continue
            label_angle = wheel_degrees(float(segment["midpoint"]), asc_lon)
            lx, ly = _polar(cx, cy, outer * 0.947, label_angle)
            self.canvas.create_text(
                lx,
                ly,
                text=str(segment["abbreviation"]),
                fill=PALETTE["top_bar_dark"],
                font=("Segoe UI Semibold", 7),
            )

    def _draw_sign_badge(self, x: float, y: float, text: str, fill: str) -> None:
        width = 26 if self.compact_wheel_var.get() else 30
        height = 23 if self.compact_wheel_var.get() else 25
        self.canvas.create_rectangle(
            x - width / 2 + 1,
            y - height / 2 + 2,
            x + width / 2 + 1,
            y + height / 2 + 2,
            fill="#d8d0bd",
            outline="",
        )
        self.canvas.create_rectangle(
            x - width / 2,
            y - height / 2,
            x + width / 2,
            y + height / 2,
            fill=PALETTE["sign_badge_fill"],
            outline=PALETTE["sign_badge_line"],
            width=1,
        )
        self.canvas.create_rectangle(
            x - width / 2 + 1,
            y - height / 2 + 1,
            x + width / 2 - 1,
            y + height / 2 - 1,
            outline=fill,
            width=1,
        )
        self.canvas.create_text(
            x,
            y,
            text=text,
            fill=PALETTE["top_bar_dark"],
            font=("Segoe UI Semibold", 10 if self.compact_wheel_var.get() else 12),
        )

    def _draw_degree_ticks(self, cx: float, cy: float, outer: float, zodiac_inner: float, asc_lon: float) -> None:
        for degree in range(360):
            angle = wheel_degrees(degree, asc_lon)
            if self._is_classic_wheel_theme():
                if degree % 30 == 0:
                    tick_length = 18
                    line_width = 2
                    color = "#000000"
                elif degree % 10 == 0:
                    tick_length = 10
                    line_width = 1
                    color = "#1c1c1c"
                elif degree % 5 == 0:
                    tick_length = 7
                    line_width = 1
                    color = "#2c2c2c"
                else:
                    tick_length = 4
                    line_width = 1
                    color = "#3d3d3d"
            else:
                if degree % 30 == 0:
                    tick_length = 16
                    line_width = 2
                    color = PALETTE["chart_tick_major"]
                elif degree % 10 == 0:
                    tick_length = 10
                    line_width = 1
                    color = PALETTE["chart_tick_medium"]
                elif degree % 5 == 0:
                    tick_length = 6
                    line_width = 1
                    color = PALETTE["chart_tick_medium"]
                else:
                    tick_length = 3
                    line_width = 1
                    color = PALETTE["chart_tick_minor"]
            x1, y1 = _polar(cx, cy, zodiac_inner, angle)
            x2, y2 = _polar(cx, cy, min(outer, zodiac_inner + tick_length), angle)
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=line_width)

    def _draw_grid(self, width: int, height: int) -> None:
        if self._is_classic_wheel_theme():
            return
        for x in range(0, width, 72):
            self.canvas.create_line(x, 0, x, height, fill=PALETTE["canvas_grid"], width=1)
        for y in range(0, height, 72):
            self.canvas.create_line(0, y, width, y, fill=PALETTE["canvas_grid"], width=1)

    def _draw_wheel_legend(self, width: int, height: int) -> None:
        if self.compact_wheel_var.get() or self._is_classic_wheel_theme():
            return
        x = 16
        y = max(16, height - 88)
        self.canvas.create_rectangle(
            x,
            y,
            x + 290,
            y + 70,
            fill=PALETTE["panel_alt"],
            outline=PALETTE["panel_line"],
        )
        self.canvas.create_line(x + 12, y + 16, x + 42, y + 16, fill=PALETTE["support"], width=2)
        self.canvas.create_text(x + 50, y + 16, text="support", anchor="w", fill=PALETTE["muted"], font=("Segoe UI", 8))
        self.canvas.create_line(x + 12, y + 36, x + 42, y + 36, fill=PALETTE["stress"], width=2)
        self.canvas.create_text(x + 50, y + 36, text="stress", anchor="w", fill=PALETTE["muted"], font=("Segoe UI", 8))
        self.canvas.create_line(x + 12, y + 56, x + 42, y + 56, fill=PALETTE["chart_line"], width=2, dash=(5, 4))
        self.canvas.create_text(x + 50, y + 56, text="dashed separating", anchor="w", fill=PALETTE["muted"], font=("Segoe UI", 8))
        self.canvas.create_arc(x + 128, y + 10, x + 156, y + 38, start=20, extent=80, fill=CONSTELLATION_COLORS[2], outline="#ffffff")
        self.canvas.create_text(x + 164, y + 24, text="unequal constellations", anchor="w", fill=PALETTE["muted"], font=("Segoe UI", 8))

    def _draw_angles(self, snapshot: dict[str, object], cx: float, cy: float, outer: float, asc_lon: float) -> None:
        for angle in snapshot["angles"]:
            degrees = wheel_degrees(float(angle["longitude"]), asc_lon)
            angle_id = str(angle.get("id", ""))
            if self._is_classic_wheel_theme():
                x0, y0 = _polar(cx, cy, outer * 0.02, degrees)
                x2, y2 = _polar(cx, cy, outer * 0.992, degrees)
                self.canvas.create_line(x0, y0, x2, y2, fill=CLASSIC_AXIS, width=2 if angle_id in {"asc", "dsc", "mc", "ic"} else 1)
                lx, ly = _polar(cx, cy, outer - 7, degrees)
                label_size = 15
                label_outline = "#c78a2b" if angle_id in {"mc", "ic"} else "#3f76b4"
                label_fill = "#5e4a1f" if angle_id in {"mc", "ic"} else "#29598e"
                self.canvas.create_oval(
                    lx - label_size,
                    ly - label_size,
                    lx + label_size,
                    ly + label_size,
                    fill="#fdfbf0",
                    outline=label_outline,
                    width=1,
                )
                self.canvas.create_text(lx, ly, text=ANGLE_GLYPHS.get(angle_id, angle["shortName"]), fill=label_fill, font=("Georgia", 10, "bold"))
            else:
                color = ANGLE_COLORS.get(angle_id, PALETTE["accent_dark"])
                x0, y0 = _polar(cx, cy, outer * 0.245, degrees)
                x1, y1 = _polar(cx, cy, outer * 0.39, degrees)
                x2, y2 = _polar(cx, cy, outer * 0.985, degrees)
                self.canvas.create_line(x0, y0, x2, y2, fill="#ffffff", width=7)
                self.canvas.create_line(x1, y1, x2, y2, fill=color, width=3)
                lx, ly = _polar(cx, cy, outer - 28, degrees)
                label_size = 19 if self.compact_wheel_var.get() else 22
                self.canvas.create_oval(
                    lx - label_size + 2,
                    ly - label_size + 3,
                    lx + label_size + 2,
                    ly + label_size + 3,
                    fill="#d7e1e6",
                    outline="",
                )
                self.canvas.create_oval(
                    lx - label_size,
                    ly - label_size,
                    lx + label_size,
                    ly + label_size,
                    fill=PALETTE["sign_badge_fill"],
                    outline=color,
                    width=2,
                )
                self.canvas.create_text(lx, ly - 1, text=angle["shortName"], fill=color, font=("Segoe UI Semibold", 11 if self.compact_wheel_var.get() else 13))
                constellation = angle.get("constellation", {})
                if isinstance(constellation, dict) and not self.compact_wheel_var.get():
                    self.canvas.create_text(
                        lx,
                        ly + label_size + 8,
                        text=str(constellation.get("abbreviation", "")),
                        fill=PALETTE["muted"],
                        font=("Segoe UI", 7, "bold"),
                    )

    def _draw_fixed_stars(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        contacted = {
            str(contact.get("star"))
            for contact in snapshot.get("fixedStarContacts", [])
            if isinstance(contact, dict)
        }
        for star in snapshot.get("fixedStars", []):
            if not isinstance(star, dict):
                continue
            degrees = wheel_degrees(float(star["longitude"]), asc_lon)
            x, y = _polar(cx, cy, outer * 0.91, degrees)
            label_x, label_y = _polar(cx, cy, outer * 0.965, degrees)
            active_contact = str(star.get("name")) in contacted
            size = 7 if active_contact else 5
            fill = "#fff8d8" if active_contact else PALETTE["star_fill"]
            outline = PALETTE["warning"] if active_contact else "#7893a4"
            star_tag = f"star:{star['id']}"
            focused = self._is_focused_body("star", str(star["name"]))
            self.canvas.create_polygon(
                x,
                y - size,
                x + size,
                y,
                x,
                y + size,
                x - size,
                y,
                fill=fill,
                outline=PALETTE["warning"] if focused else outline,
                width=2 if active_contact or focused else 1,
                tags=("fixed-star-marker", star_tag),
            )
            if focused:
                self.canvas.create_oval(x - 11, y - 11, x + 11, y + 11, outline=PALETTE["warning"], width=1, tags=("fixed-star-marker", star_tag))
            self.canvas.create_text(
                label_x,
                label_y,
                text=star_abbreviation(str(star["name"])),
                fill=PALETTE["warning"] if focused else outline,
                font=("Segoe UI", 7, "bold"),
                tags=("fixed-star-marker", star_tag),
            )
            self.canvas.tag_bind(star_tag, "<Button-1>", lambda _event, star_id=str(star["id"]): self._select_fixed_star_by_id(star_id))
            self.canvas.tag_bind(star_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(star_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_planets(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        planets = self._visible_planets(snapshot)
        classic_theme = self._is_classic_wheel_theme()
        if classic_theme:
            offsets = body_marker_offsets(
                [float(planet["longitude"]) for planet in planets],
                compact=self.compact_wheel_var.get(),
                crowd_threshold=8.5 if self.compact_wheel_var.get() else 10.5,
                angle_step=4.8 if self.compact_wheel_var.get() else 5.8,
                radial_step=5.6 if self.compact_wheel_var.get() else 7.0,
            )
            base_radius = outer * (0.708 if self.compact_wheel_var.get() else 0.720)
            marker_size = 15 if self.compact_wheel_var.get() else 18
        else:
            offsets = planet_marker_offsets([float(planet["longitude"]) for planet in planets], compact=self.compact_wheel_var.get())
            base_radius = outer * (0.665 if self.compact_wheel_var.get() else 0.645)
            marker_size = 12 if self.compact_wheel_var.get() else 15
        for planet, (angle_offset, radial_offset) in zip(planets, offsets):
            anchor_degrees = wheel_degrees(float(planet["longitude"]), asc_lon)
            degrees = anchor_degrees + angle_offset
            if classic_theme:
                anchor_radius = outer * 0.748
                radius = min(outer * 0.755, max(outer * 0.650, base_radius - radial_offset * 0.35))
            else:
                radius = max(outer * 0.53, base_radius - radial_offset)
            x, y = _polar(cx, cy, radius, degrees)
            if not classic_theme:
                fill = PALETTE["planet_fill_angular"] if planet.get("isAngular") else PALETTE["planet_fill"]
                if planet.get("isPresetPoint"):
                    fill = "#f7f0dc"
                outline = PALETTE["accent_dark"] if planet.get("isAngular") else PALETTE["chart_line"]
            planet_tag = f"planet:{planet['id']}"
            focused = self._is_focused_body("planet", str(planet["name"]))
            if classic_theme:
                ax, ay = _polar(cx, cy, anchor_radius, anchor_degrees)
                ix, iy = _polar(cx, cy, outer * 0.735, anchor_degrees)
                self.canvas.create_line(ix, iy, ax, ay, fill=CLASSIC_HOUSE_LINE, width=1, tags=("planet-anchor", planet_tag))
                if abs(angle_offset) > 0.2 or abs(radial_offset) > 0.2:
                    self.canvas.create_line(ax, ay, x, y, fill="#245e75", width=1, tags=("planet-anchor", planet_tag))
                hit_size = marker_size + 8
                self.canvas.create_oval(
                    x - hit_size,
                    y - hit_size,
                    x + hit_size,
                    y + hit_size,
                    fill="",
                    outline="",
                    tags=("planet-marker", planet_tag),
                )
                if focused:
                    self.canvas.create_oval(
                        x - marker_size - 5,
                        y - marker_size - 5,
                        x + marker_size + 5,
                        y + marker_size + 5,
                        outline=PALETTE["warning"],
                        width=2,
                        tags=("planet-marker", planet_tag),
                    )
                marker_color = CLASSIC_PLANET_COLORS.get(str(planet["name"]), PALETTE["top_bar_dark"])
                glyph_size = 27 if self.compact_wheel_var.get() else 31
                self._draw_halo_text(
                    x,
                    y,
                    text=planet_glyph(str(planet["name"])),
                    fill=marker_color,
                    halo=CLASSIC_HOUSE_HALO,
                    font=self._planet_marker_font(glyph_size),
                    tags=("planet-marker", planet_tag),
                )
                degree_text = classic_planet_degree_text(planet)
                radius_distance = math.hypot(x - cx, y - cy) or 1.0
                radial_x = (x - cx) / radius_distance
                radial_y = (y - cy) / radius_distance
                tangent_x = -radial_y
                tangent_y = radial_x
                if degree_text:
                    degree_tangent = 18 if self.compact_wheel_var.get() else 22
                    degree_radial = 9 if self.compact_wheel_var.get() else 12
                    tangent_sign = -1 if x >= cx else 1
                    degree_x = x + tangent_x * degree_tangent * tangent_sign + radial_x * degree_radial
                    degree_y = y + tangent_y * degree_tangent * tangent_sign + radial_y * degree_radial
                    self.canvas.create_text(
                        degree_x,
                        degree_y,
                        text=degree_text,
                        fill=CLASSIC_PLANET_DEGREE,
                        font=("Segoe UI Semibold", 10 if self.compact_wheel_var.get() else 11),
                        tags=("planet-marker", planet_tag),
                    )
                if planet.get("isRetrograde"):
                    retro_tangent = 8 if self.compact_wheel_var.get() else 10
                    retro_radial = 2 if self.compact_wheel_var.get() else 3
                    tangent_sign = 1 if x >= cx else -1
                    retro_x = x + tangent_x * retro_tangent * tangent_sign - radial_x * retro_radial
                    retro_y = y + tangent_y * retro_tangent * tangent_sign - radial_y * retro_radial
                    self.canvas.create_text(
                        retro_x,
                        retro_y,
                        text="R",
                        fill=CLASSIC_PLANET_RETROGRADE,
                        font=("Segoe UI", 7, "bold"),
                        tags=("planet-marker", planet_tag),
                    )
            else:
                focus_outline = PALETTE["warning"] if focused else outline
                self.canvas.create_oval(x - marker_size + 2, y - marker_size + 4, x + marker_size + 2, y + marker_size + 4, fill="#cfd9df", outline="", tags=("planet-marker", planet_tag))
                self.canvas.create_oval(x - marker_size, y - marker_size, x + marker_size, y + marker_size, fill=fill, outline=outline, width=2, tags=("planet-marker", planet_tag))
                self.canvas.create_arc(x - marker_size + 3, y - marker_size + 3, x + marker_size - 3, y + marker_size - 3, start=35, extent=125, outline="#ffffff", width=1, tags=("planet-marker", planet_tag))
                if focused:
                    self.canvas.create_oval(x - marker_size - 4, y - marker_size - 4, x + marker_size + 4, y + marker_size + 4, outline=focus_outline, width=2, tags=("planet-marker", planet_tag))
                self.canvas.create_text(
                    x,
                    y,
                    text=planet_abbreviation(str(planet["name"])),
                    fill=PALETTE["top_bar_dark"],
                    font=self._planet_marker_font(9 if self.compact_wheel_var.get() else 10),
                    tags=("planet-marker", planet_tag),
                )
            planet_id = str(planet["id"])
            if str(planet.get("name")) == "Moon":
                self.canvas.tag_bind(planet_tag, "<ButtonPress-1>", lambda event, target_id=planet_id: self._start_moon_drag(event, target_id))
                self.canvas.tag_bind(planet_tag, "<B1-Motion>", self._drag_moon_marker)
                self.canvas.tag_bind(planet_tag, "<ButtonRelease-1>", lambda event, target_id=planet_id: self._release_moon_drag(event, target_id))
                self.canvas.tag_bind(planet_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="fleur"))
            else:
                self.canvas.tag_bind(planet_tag, "<Button-1>", lambda _event, target_id=planet_id: self._select_planet_by_id(target_id))
                self.canvas.tag_bind(planet_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(planet_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_lots(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        lots = self._visible_lots(snapshot)
        classic_theme = self._is_classic_wheel_theme()
        offsets = body_marker_offsets([float(lot["longitude"]) for lot in lots], compact=self.compact_wheel_var.get(), crowd_threshold=10.0, angle_step=4.5, radial_step=10.0)
        base_radius = outer * (0.565 if classic_theme else 0.58)
        for lot, (angle_offset, radial_offset) in zip(lots, offsets):
            degrees = wheel_degrees(float(lot["longitude"]), asc_lon) + angle_offset
            radius = min(outer * (0.635 if classic_theme else 0.76), max(outer * 0.48, base_radius + radial_offset * (0.35 if classic_theme else 0.7)))
            x, y = _polar(cx, cy, radius, degrees)
            lot_tag = f"lot:{lot['id']}"
            focused = self._is_focused_body("lot", str(lot["name"]))
            if classic_theme:
                size = 6 if not focused else 9
                self.canvas.create_polygon(
                    x,
                    y - size,
                    x + size,
                    y,
                    x,
                    y + size,
                    x - size,
                    y,
                    fill="#f5efd6",
                    outline=PALETTE["warning"] if focused else "#6f6040",
                    width=2 if focused else 1,
                    tags=("lot-marker", lot_tag),
                )
                if focused:
                    self.canvas.create_text(
                        x + 13,
                        y,
                        text=lot_abbreviation(str(lot["name"])),
                        fill=CLASSIC_HOUSE_TEXT,
                        font=("Segoe UI Semibold", 8),
                        anchor="w",
                        tags=("lot-marker", lot_tag),
                    )
                self.canvas.tag_bind(lot_tag, "<Button-1>", lambda _event, lot_id=str(lot["id"]): self._select_lot_by_id(lot_id))
                self.canvas.tag_bind(lot_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
                self.canvas.tag_bind(lot_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))
                continue
            self.canvas.create_rectangle(
                x - 11,
                y - 10,
                x + 15,
                y + 16,
                fill="#d7e0e5",
                outline="",
                tags=("lot-marker", lot_tag),
            )
            self.canvas.create_rectangle(
                x - 13,
                y - 13,
                x + 13,
                y + 13,
                fill=PALETTE["lot_fill"],
                outline=PALETTE["warning"] if focused else PALETTE["accent_dark"],
                width=2,
                tags=("lot-marker", lot_tag),
            )
            if focused:
                self.canvas.create_rectangle(x - 17, y - 17, x + 17, y + 17, outline=PALETTE["warning"], width=1, tags=("lot-marker", lot_tag))
            self.canvas.create_text(
                x,
                y,
                text=lot_abbreviation(str(lot["name"])),
                fill=PALETTE["top_bar_dark"],
                font=("Segoe UI Semibold", 8),
                tags=("lot-marker", lot_tag),
            )
            self.canvas.tag_bind(lot_tag, "<Button-1>", lambda _event, lot_id=str(lot["id"]): self._select_lot_by_id(lot_id))
            self.canvas.tag_bind(lot_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(lot_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_nodes(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        nodes = [node for node in snapshot.get("lunarNodes", []) if isinstance(node, dict)]
        classic_theme = self._is_classic_wheel_theme()
        offsets = body_marker_offsets([float(node["longitude"]) for node in nodes], compact=self.compact_wheel_var.get(), crowd_threshold=9.0, angle_step=4.0, radial_step=9.0)
        base_radius = outer * (0.62 if classic_theme else 0.42)
        for node, (angle_offset, radial_offset) in zip(nodes, offsets):
            degrees = wheel_degrees(float(node["longitude"]), asc_lon) + angle_offset
            radius = max(outer * (0.56 if classic_theme else 0.34), base_radius - radial_offset * (0.35 if classic_theme else 0.8))
            x, y = _polar(cx, cy, radius, degrees)
            node_tag = f"node:{node['id']}"
            focused = self._is_focused_body("node", str(node["name"]))
            if classic_theme:
                self.canvas.create_text(
                    x,
                    y,
                    text="☊" if "North" in str(node.get("name")) else "☋",
                    fill=PALETTE["warning"] if focused else "#26335f",
                    font=("Segoe UI Symbol", 13 if focused else 11, "bold"),
                    tags=("node-marker", node_tag),
                )
                if focused:
                    self.canvas.create_oval(x - 12, y - 12, x + 12, y + 12, outline=PALETTE["warning"], width=1, tags=("node-marker", node_tag))
                self.canvas.tag_bind(node_tag, "<Button-1>", lambda _event, node_id=str(node["id"]): self._select_node_by_id(node_id))
                self.canvas.tag_bind(node_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
                self.canvas.tag_bind(node_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))
                continue
            self.canvas.create_polygon(
                x + 2,
                y - 10,
                x + 14,
                y + 13,
                x - 10,
                y + 13,
                fill="#d7e0e5",
                outline="",
                tags=("node-marker", node_tag),
            )
            self.canvas.create_polygon(
                x,
                y - 13,
                x + 12,
                y + 10,
                x - 12,
                y + 10,
                fill=PALETTE["node_fill"],
                outline=PALETTE["warning"] if focused else PALETTE["accent_dark"],
                width=2,
                tags=("node-marker", node_tag),
            )
            if focused:
                self.canvas.create_oval(x - 17, y - 17, x + 17, y + 17, outline=PALETTE["warning"], width=1, tags=("node-marker", node_tag))
            self.canvas.create_text(
                x,
                y + 2,
                text=node_abbreviation(str(node["name"])),
                fill=PALETTE["top_bar_dark"],
                font=("Segoe UI Semibold", 8),
                tags=("node-marker", node_tag),
            )
            self.canvas.tag_bind(node_tag, "<Button-1>", lambda _event, node_id=str(node["id"]): self._select_node_by_id(node_id))
            self.canvas.tag_bind(node_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(node_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_aspects(self, snapshot: dict[str, object], cx: float, cy: float, radius: float, asc_lon: float) -> None:
        positions = {planet["name"]: planet for planet in self._visible_planets(snapshot)}
        for lane_index, aspect in enumerate(snapshot["detectedAspects"][:10]):
            body_a, body_b = aspect["bodies"]
            if body_a not in positions or body_b not in positions:
                continue
            angle_a = wheel_degrees(float(positions[body_a]["longitude"]), asc_lon)
            angle_b = wheel_degrees(float(positions[body_b]["longitude"]), asc_lon)
            color = PALETTE["support"] if aspect["tone"] == "support" else PALETTE["stress"]
            line_width = 2.4 if aspect.get("isApplying") else 1.7
            self.canvas.create_line(
                *aspect_curve_points(cx, cy, radius, angle_a, angle_b, compact=self.compact_wheel_var.get(), lane_index=lane_index),
                fill=color,
                width=line_width,
                dash=() if aspect.get("isApplying") else (5, 4),
                smooth=True,
            )

    def _tone_surface(self, tone: str) -> tuple[str, str]:
        if tone in {"support", "score"}:
            return PALETTE["surface_support"], PALETTE["support"]
        if tone == "stress":
            return PALETTE["surface_stress"], PALETTE["stress"]
        if tone == "warning":
            return PALETTE["surface_gold"], PALETTE["warning"]
        if tone == "mixed":
            return PALETTE["surface_gold"], PALETTE["gold"]
        return PALETTE["surface"], PALETTE["accent_dark"]

    def _visual_card(self, parent: tk.Widget, title: str, subtitle: str = "", *, tone: str = "neutral") -> tk.Frame:
        bg, accent = self._tone_surface(tone)
        card = tk.Frame(parent, bg=bg, highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=9, pady=8)
        card.pack(fill=tk.X, pady=(0, 8))
        tk.Frame(card, bg=accent, height=2).pack(fill=tk.X, pady=(0, 5))
        tk.Label(card, text=title, bg=bg, fg=accent, font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        if subtitle:
            tk.Label(card, text=subtitle, bg=bg, fg=PALETTE["muted"], font=("Segoe UI", 8), wraplength=315, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(2, 0))
        return card

    def _render_highlight_card(self, parent: tk.Widget, title: str, result: object) -> None:
        result_map = result if isinstance(result, Mapping) else None
        tone = str(result_map.get("tone") or "neutral") if result_map else "neutral"
        card = self._visual_card(parent, title, tone=tone)
        for index, line in enumerate(format_aspect_highlight(result_map).splitlines()[:3]):
            tk.Label(
                card,
                text=line,
                bg=card["bg"],
                fg=PALETTE["text"] if index else PALETTE["accent_dark"],
                font=("Segoe UI Semibold", 8 if index == 0 else 7),
                wraplength=300,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(2 if index else 4, 0))

    def _render_timeline_panel(self, snapshot: dict[str, object]) -> None:
        if not hasattr(self, "timeline_frame"):
            return
        self._clear_frame(self.timeline_frame)
        highlights = self.current_aspect_highlights if isinstance(self.current_aspect_highlights, Mapping) else {}
        header = self._visual_card(
            self.timeline_frame,
            "Aspect Timeline",
            "Current, local-day, and next-24-hour aspect peaks for the displayed chart.",
        )
        tk.Label(
            header,
            text=f"Displayed: {snapshot.get('formattedTime', 'time unavailable')}",
            bg=header["bg"],
            fg=PALETTE["text"],
            font=("Segoe UI", 8),
            wraplength=315,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))
        for title, key in (("Current Aspect", "current"), ("Strongest Today", "localDay"), ("Strongest Next 24h", "rolling24Hours")):
            self._render_highlight_card(self.timeline_frame, title, highlights.get(key))
        self._render_timeline_section("Local Day", timeline_visual_rows(highlights, key="timelineByTime", limit=12))
        self._render_timeline_section("Rolling Next 24 Hours", timeline_visual_rows(highlights, key="rollingTimelineByTime", limit=12))

    def _render_timeline_section(self, title: str, rows: list[dict[str, object]]) -> None:
        section = self._visual_card(self.timeline_frame, title)
        if not rows:
            tk.Label(
                section,
                text="No aspect timeline entries available for this range.",
                bg=section["bg"],
                fg=PALETTE["muted"],
                font=("Segoe UI", 8),
                wraplength=315,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(5, 0))
            return
        for row in rows:
            self._render_timeline_row(section, row)

    def _render_timeline_row(self, parent: tk.Widget, row: dict[str, object]) -> None:
        bg, accent = self._tone_surface(str(row.get("tone") or "neutral"))
        item = tk.Frame(parent, bg=bg, highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=7, pady=5)
        item.pack(fill=tk.X, pady=(5, 0))
        header = tk.Frame(item, bg=bg)
        header.pack(fill=tk.X)
        tk.Label(header, text=str(row.get("time", "time n/a")), bg=bg, fg=accent, font=("Segoe UI Semibold", 7), anchor="w").pack(side=tk.LEFT)
        tk.Label(header, text=str(row.get("toneLabel", "Mixed")), bg=bg, fg=accent, font=("Georgia", 7, "bold"), anchor="e").pack(side=tk.RIGHT)
        tk.Label(item, text=str(row.get("label", "Aspect")), bg=bg, fg=PALETTE["text"], font=("Segoe UI Semibold", 8), wraplength=305, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(3, 0))
        detail = f"{row.get('orb', 'orb n/a')} | {row.get('phase', 'phase n/a')} | peak {row.get('peak', 'exact n/a')} | strength {row.get('strength', '--')}"
        tk.Label(item, text=detail, bg=bg, fg=PALETTE["muted"], font=("Segoe UI", 7), wraplength=305, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(2, 0))
        self._bind_timeline_row(item, row)

    def _bind_timeline_row(self, widget: tk.Widget, row: dict[str, object]) -> None:
        widget.bind("<Button-1>", lambda _event, selected=row: self._focus_timeline_aspect(selected))
        widget.bind("<Enter>", lambda _event: widget.configure(cursor="hand2"))
        widget.bind("<Leave>", lambda _event: widget.configure(cursor=""))
        for child in widget.winfo_children():
            self._bind_timeline_row(child, row)

    def _focus_timeline_aspect(self, row: Mapping[str, object]) -> None:
        bodies = row.get("bodies", [])
        body_names = [str(body) for body in bodies if str(body)] if isinstance(bodies, list) else []
        if not body_names:
            self.status_var.set("Timeline aspect selected, but no focusable bodies were available.")
            return
        self.focused_aspect_bodies = set(body_names[:2])
        self.focused_body_kind = "planet"
        self.focused_body_name = body_names[0]
        self.focus_body_var.set(" / ".join(body_names[:2]))
        self._set_text(
            self.interpretation_text,
            f"Timeline aspect focus: {row.get('label', 'Aspect')}\n"
            f"Bodies: {', '.join(body_names[:2])}\n"
            f"{row.get('orb', '')} | {row.get('phase', '')} | peak {row.get('peak', '')}",
        )
        self._redraw_selected_window()
        self.status_var.set(f"Focused timeline aspect: {row.get('label', 'Aspect')}.")

    def _render_analysis_panel(self, snapshot: dict[str, object], windows: list[dict[str, object]], location: object) -> None:
        if not hasattr(self, "analysis_frame"):
            return
        self._clear_frame(self.analysis_frame)
        score = int(snapshot.get("score", 0) or 0)
        header = self._visual_card(
            self.analysis_frame,
            "Electional Analysis",
            f"{snapshot.get('formattedTime', 'time unavailable')} | {getattr(location, 'name', 'Location unavailable')}",
            tone="score" if score >= 76 else "warning",
        )
        tk.Label(header, text=f"Score {score} - {score_band_label(score)}", bg=header["bg"], fg=PALETTE["score"], font=("Georgia", 18, "bold"), anchor="w").pack(fill=tk.X, pady=(4, 0))
        tk.Label(header, text=str(snapshot.get("note") or snapshot.get("title") or "Review the supporting testimony below."), bg=header["bg"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=315, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(2, 0))

        metric_section = self._visual_card(self.analysis_frame, "Quality Metrics", "Score, diagnostics, aspect balance, angularity, and rule load.")
        grid = tk.Frame(metric_section, bg=metric_section["bg"])
        grid.pack(fill=tk.X, pady=(5, 0))
        for index, (label, value, note, tone) in enumerate(analysis_metric_cards(snapshot, windows)):
            self._analysis_metric_card(grid, index, label, value, note, tone)

        highlights = self.current_aspect_highlights if isinstance(self.current_aspect_highlights, Mapping) else {}
        aspect_section = self._visual_card(self.analysis_frame, "Aspect Highlights", "Strongest contacts for now, the local day, and the next 24 hours.")
        for title, key in (("Current", "current"), ("Local Day", "localDay"), ("Next 24h", "rolling24Hours")):
            result = highlights.get(key)
            line = format_aspect_highlight(result if isinstance(result, Mapping) else None).splitlines()[0]
            tk.Label(aspect_section, text=f"{title}: {line}", bg=aspect_section["bg"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=315, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(4, 0))

        self._analysis_text_section("Moon Timing", judgment_context_lines(snapshot, "moonCondition"))
        self._analysis_text_section("Planet Conditions", judgment_context_lines(snapshot, "planetConditionContext"))
        self._analysis_text_section("House Geometry", house_geometry_insight_lines(snapshot))
        self._analysis_text_section("Houses And Angles", [*angle_testimony_lines(snapshot), *judgment_context_lines(snapshot, "houseRulerContext")])
        self._analysis_text_section("Search, Validation, And Rejections", analysis_notice_lines(snapshot, self.current_rejection_summary, location))
        self._analysis_text_section("Accuracy Validation", validation_workbench_lines(snapshot, location, self.manual_validation_result))

    def _render_validation_panel(self, snapshot: dict[str, object], location: object) -> None:
        if not hasattr(self, "validation_frame"):
            return
        self._clear_frame(self.validation_frame)
        header = self._visual_card(
            self.validation_frame,
            "Accuracy Validation",
            "Swiss integration audit plus manual CapricornPROMETHEUS comparison for the displayed chart.",
            tone="score" if self._accuracy_status_label(snapshot).lower().startswith("swiss") else "warning",
        )
        for line in validation_workbench_lines(snapshot, location, self.manual_validation_result)[:10]:
            tk.Label(
                header,
                text=line,
                bg=header["bg"],
                fg=PALETTE["text"],
                font=("Segoe UI", 8),
                wraplength=315,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(3, 0))

        manual = self._visual_card(
            self.validation_frame,
            "Manual CapricornPROMETHEUS Compare",
            "Paste planet, angle, or cusp rows. The app parses recognized sign-degree values and reports deltas.",
        )
        tk.Label(manual, text="Reference source", bg=manual["bg"], fg=PALETTE["muted"], font=("Segoe UI Semibold", 7), anchor="w").pack(fill=tk.X, pady=(5, 2))
        tk.Entry(
            manual,
            textvariable=self.manual_validation_source_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.SOLID,
            bd=1,
            font=("Segoe UI", 8),
        ).pack(fill=tk.X, ipady=3)
        tk.Label(manual, text="Paste comparison rows", bg=manual["bg"], fg=PALETTE["muted"], font=("Segoe UI Semibold", 7), anchor="w").pack(fill=tk.X, pady=(7, 2))
        self.manual_validation_input_widget = tk.Text(
            manual,
            height=7,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.SOLID,
            bd=1,
            wrap=tk.WORD,
            font=("Consolas", 8),
            padx=5,
            pady=4,
        )
        self.manual_validation_input_widget.pack(fill=tk.X)
        self.manual_validation_input_widget.insert("1.0", self.manual_validation_input_cache)
        action_row = tk.Frame(manual, bg=manual["bg"])
        action_row.pack(fill=tk.X, pady=(7, 0))
        ttk.Button(action_row, text="Compare", command=self._run_manual_validation_compare, style="Compact.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(action_row, text="Clear", command=self._clear_manual_validation_compare, style="Compact.TButton").pack(side=tk.LEFT)

        result_card = self._visual_card(self.validation_frame, "Comparison Result", tone="warning" if self.manual_validation_result.get("status") == "Review" else "score")
        for line in format_manual_validation_comparison(self.manual_validation_result)[:14]:
            tk.Label(
                result_card,
                text=line,
                bg=result_card["bg"],
                fg=PALETTE["text"],
                font=("Segoe UI", 8),
                wraplength=315,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(3, 0))

    def _run_manual_validation_compare(self) -> None:
        if not self.selected_window:
            self.status_var.set("Manual comparison needs a calculated chart first.")
            return
        text = ""
        if hasattr(self, "manual_validation_input_widget"):
            text = self.manual_validation_input_widget.get("1.0", tk.END).strip()
        self.manual_validation_input_cache = text
        self.manual_validation_result = build_manual_validation_comparison(
            self.selected_window,
            text,
            source=self.manual_validation_source_var.get(),
        )
        self._render_validation_panel(self.selected_window, self.current_location)
        self._render_analysis_panel(self.selected_window, self.current_windows, self.current_location)
        self._save_session()
        self.status_var.set(f"Manual validation comparison: {self.manual_validation_result.get('status', 'complete')}.")

    def _clear_manual_validation_compare(self) -> None:
        self.manual_validation_input_cache = ""
        self.manual_validation_result = {}
        if hasattr(self, "manual_validation_input_widget"):
            self.manual_validation_input_widget.delete("1.0", tk.END)
        if self.selected_window:
            self._render_validation_panel(self.selected_window, self.current_location)
            self._render_analysis_panel(self.selected_window, self.current_windows, self.current_location)
        self._save_session()
        self.status_var.set("Manual validation comparison cleared.")

    def _render_reports_panel(self, snapshot: dict[str, object], windows: list[dict[str, object]], location: object) -> None:
        if not hasattr(self, "reports_frame"):
            return
        self._clear_frame(self.reports_frame)
        header = self._visual_card(
            self.reports_frame,
            "Reports And Exports",
            "Create readable decision artifacts from the displayed chart, search results, and shortlist.",
        )
        tk.Label(
            header,
            text=f"Displayed: {snapshot.get('formattedTime', 'time unavailable')} | {len(windows)} candidate window{'s' if len(windows) != 1 else ''}",
            bg=header["bg"],
            fg=PALETTE["text"],
            font=("Segoe UI", 8),
            wraplength=315,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))
        report_actions = (
            ("View Full Report", self._show_current_report_dialog),
            ("Copy Report", self._copy_current_report),
            ("Save Report", self._save_current_report),
            ("Day Report", self._show_daily_aspect_report_dialog),
            ("Save Decision Sheet", self._save_comparison_sheet),
            ("Open Shortlist Board", lambda: self._focus_detail_page("Shortlist Board")),
        )
        grid = tk.Frame(header, bg=header["bg"])
        grid.pack(fill=tk.X, pady=(8, 0))
        for index, (label, command) in enumerate(report_actions):
            grid.columnconfigure(index % 2, weight=1, uniform="report-actions")
            ttk.Button(grid, text=label, command=command, style="Compact.TButton").grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0 if index % 2 == 0 else 4, 0 if index % 2 == 1 else 4),
                pady=(0 if index < 2 else 5, 0),
            )

        summary = self._visual_card(self.reports_frame, "Report Preview")
        preview_lines = [
            f"Score {snapshot.get('score', 'n/a')} - {score_band_label(int(snapshot.get('score', 0) or 0))}",
            str(snapshot.get("note") or snapshot.get("title") or "No note available."),
            f"Validation: {self._accuracy_status_label(snapshot)}",
            f"Manual compare: {self.manual_validation_result.get('status', 'not run') if isinstance(self.manual_validation_result, dict) else 'not run'}",
            f"Search: {self.current_search_summary or 'Search summary unavailable.'}",
        ]
        for line in preview_lines:
            tk.Label(summary, text=line, bg=summary["bg"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=315, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(3, 0))

    def _analysis_metric_card(self, parent: tk.Widget, index: int, label: str, value: str, note: str, tone: str) -> None:
        bg, accent = self._tone_surface(tone)
        parent.columnconfigure(index % 2, weight=1, uniform="analysis-metrics")
        card = tk.Frame(parent, bg=bg, highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=6, pady=5)
        card.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0 if index % 2 == 0 else 3, 0 if index % 2 == 1 else 3), pady=(0 if index < 2 else 5, 0))
        tk.Label(card, text=label, bg=bg, fg=PALETTE["muted"], font=("Segoe UI Semibold", 7), anchor="w").pack(fill=tk.X)
        tk.Label(card, text=value, bg=bg, fg=accent, font=("Georgia", 13, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(card, text=note, bg=bg, fg=PALETTE["text"], font=("Segoe UI", 7), wraplength=135, justify=tk.LEFT, anchor="w").pack(fill=tk.X)

    def _analysis_text_section(self, title: str, lines: list[str]) -> None:
        section = self._visual_card(self.analysis_frame, title)
        readable = [str(line).lstrip("- ") for line in lines if str(line).strip()]
        if not readable:
            readable = ["No details available."]
        for line in readable[:8]:
            tk.Label(section, text=line, bg=section["bg"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=315, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(3, 0))

    def _context_page_text(self, title: str, lines: list[str], snapshot: dict[str, object]) -> str:
        readable = [str(line).strip() for line in lines if str(line).strip()]
        if readable and not all("unavailable" in line.lower() for line in readable):
            return "\n".join(readable)
        zodiac_name = getattr(snapshot.get("zodiacSystem"), "name", "Zodiac n/a")
        house_name = getattr(snapshot.get("houseSystem"), "name", "House n/a")
        purpose = {
            "Significators": "Reviews the planets that represent the election objective, the querent/operator, and the relevant houses.",
            "Moon": "Reviews lunar phase, void status, applying contacts, and whether the Moon helps or weakens the timing.",
            "House Rulers": "Reviews the lords of the key houses and whether they are supported, stressed, angular, or unavailable.",
            "Reception": "Reviews mutual reception, dispositors, and whether planets can help each other deliver the election.",
            "Planet Conditions": "Reviews motion, angularity, dignity availability, and condition notes for the active point set.",
            "Declination": "Reviews parallels, contra-parallels, and out-of-bounds style testimony when available.",
            "Advanced Aspects": "Reviews secondary aspect diagnostics, applying/separating nuance, and special contacts when active.",
        }.get(title, "Reviews supporting testimony for the displayed election.")
        if not snapshot.get("traditionalRulesEnabled", True) and title in {"Significators", "House Rulers", "Reception"}:
            reason = (
                "Traditional rulership and reception logic is intentionally disabled in True 13-Sign mode. "
                "Switch to a 12-sign tropical or sidereal zodiac when you want classical lord, reception, and dignity judgments."
            )
        elif title == "Declination":
            reason = "No declination or parallel testimony is active for this chart and point set yet."
        elif title == "Advanced Aspects":
            reason = "No advanced aspect diagnostics are active for the selected point set and aspect focus."
        else:
            reason = "This diagnostic page has no active testimony for the displayed chart yet."
        return "\n".join(
            [
                title,
                "",
                "Purpose",
                f"- {purpose}",
                "",
                "Current status",
                reason,
                "",
                "Current calculation",
                f"- Zodiac: {zodiac_name}",
                f"- House system: {house_name}",
                f"- Time: {snapshot.get('formattedTime', 'time unavailable')}",
                "",
                "Next useful move",
                "- Change point set, zodiac/house system, or aspect focus, then recalculate.",
            ]
        )

    def _render_text_panels(self, snapshot: dict[str, object], windows: list[dict[str, object]], location: object) -> None:
        support = sum(1 for aspect in snapshot["detectedAspects"] if aspect["tone"] == "support")
        stress = sum(1 for aspect in snapshot["detectedAspects"] if aspect["tone"] == "stress")
        angular = sum(1 for planet in snapshot["positions"] if planet.get("isAngular"))
        self._set_text(
            self.summary_text,
            (
                "Summary Dashboard\n"
                f"Displayed chart: {snapshot.get('formattedTime', 'time unavailable')}\n"
                f"Location: {getattr(location, 'name', 'Location unavailable')} / {getattr(location, 'timezone', 'timezone n/a')}\n"
                f"Score: {snapshot['score']} ({score_band_label(int(snapshot['score']))})\n"
                f"Score explanation: {format_score_breakdown(snapshot)}\n"
                f"Lunar phase: {format_lunar_phase(snapshot)}\n"
                f"Zodiac: {snapshot['zodiacSystem'].name}\n"
                f"House system: {snapshot['houseSystem'].name}\n"
                f"Ayanamsha: {float(snapshot['ayanamsha']):.3f} deg\n"
                f"Fixed-star score: {float(snapshot['scoreBreakdown'].get('fixedStar', 0)):+.1f}\n"
                f"Calculation engine: {snapshot['calculationBackend']['activeEngine']}\n"
                f"Model: {snapshot['preset'].name}\n"
                f"Engine: {snapshot['engine']}\n\n"
                "Read this first\n"
                "- Use Analysis for the full judgment.\n"
                "- Use Timeline to see aspect peaks across the day.\n"
                "- Use Search to understand why windows passed or failed filters."
            ),
        )
        self.metric_vars["score"].set(str(snapshot["score"]))
        breakdown = snapshot.get("scoreBreakdown", {})
        diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, dict) else {}
        objective_fit = int(breakdown.get("objectiveMatches", 0)) if isinstance(breakdown, dict) else 0
        confidence = diagnostics.get("confidence", {}) if isinstance(diagnostics, dict) else {}
        self.metric_vars["confidence"].set(str(confidence.get("score", "--")))
        self.metric_vars["fit"].set(str(objective_fit))
        self.metric_vars["support"].set(str(support))
        self.metric_vars["stress"].set(str(stress))
        self.metric_vars["angular"].set(str(angular))
        self.metric_vars["stars"].set(str(fixed_star_contact_count(snapshot)))
        rule_evaluations = snapshot.get("ruleEvaluations", {})
        rules = rule_evaluations.get("rules", []) if isinstance(rule_evaluations, dict) else []
        self.metric_vars["rules"].set(str(len(rules) if isinstance(rules, list) else 0))
        self._refresh_judgment_panel(snapshot)
        self._refresh_shortlist_text()

        selected_rank = next((index for index, window in enumerate(windows, start=1) if window["date"] == snapshot["date"]), 1)
        aspect_labels = ", ".join(format_aspect_summary(aspect) for aspect in snapshot["detectedAspects"][:3]) or "No selected major aspects"
        self._set_text(
            self.window_detail_text,
            (
                "Selected Window\n"
                f"Rank: {selected_rank} of {len(windows)}\n"
                f"Time: {snapshot['formattedTime']}\n"
                f"Score: {snapshot['score']} - {snapshot.get('title', 'Election')}\n"
                f"Lunar phase: {format_lunar_phase(snapshot)}\n"
                f"Score explanation: {format_score_breakdown(snapshot)}\n"
                f"{chr(10).join(score_reason_lines(snapshot)[:4])}\n"
                f"{snapshot.get('note', '')}\n"
                f"{aspect_labels}\n\n"
                "Actions\n"
                "- Use Selected Time to copy this window back into the input chart.\n"
                "- Shortlist serious candidates before comparing them."
            ),
        )
        timeline_lines = [
            "Aspect Timeline",
            "",
            "Local Day",
            *format_aspect_timeline(self.current_aspect_highlights, key="timelineByTime", limit=12),
            "",
            "Rolling Next 24 Hours",
            *format_aspect_timeline(self.current_aspect_highlights, key="rollingTimelineByTime", limit=12),
        ]
        self.timeline_report_text_cache = "\n".join(timeline_lines)
        self.analysis_report_text_cache = build_analysis_page(
            snapshot,
            windows,
            location,
            self.current_aspect_highlights,
            self.current_search_summary,
            self.current_rejection_summary,
        )
        validation_report_text = "\n".join(validation_workbench_lines(snapshot, location, self.manual_validation_result))
        self.analysis_report_text_cache = self.analysis_report_text_cache + "\n\n" + validation_report_text
        self._render_timeline_panel(snapshot)
        self._render_analysis_panel(snapshot, windows, location)
        self._render_validation_panel(snapshot, location)
        self._render_reports_panel(snapshot, windows, location)
        self._set_text(
            self.advisor_text,
            "\n".join(advisor_lines(self.selected_window, self.input_snapshot, self.objective_var.get())),
        )
        self._set_text(self.improve_text, "\n".join(improvement_guide_lines(snapshot, self.input_snapshot)))
        self._set_text(
            self.decision_text,
            build_decision_brief_page(
                self.input_snapshot or snapshot,
                snapshot,
                self.objective_var.get(),
                location,
            ),
        )
        self._set_text(self.diagnostics_text, build_diagnostics_page(snapshot))
        self._set_text(
            self.compare_text,
            build_window_comparison_page(
                self.input_snapshot or snapshot,
                windows,
                self.objective_var.get(),
            ),
        )
        self._set_text(
            self.search_text,
            build_transit_search_page(
                self.input_snapshot or snapshot,
                snapshot,
                windows,
                location,
                self.current_search_summary or "Search profile unavailable.",
                self.current_rejection_summary,
            ),
        )
        self._set_text(
            self.interpretation_text,
            self._selected_window_interpretation(snapshot, selected_rank, len(windows)),
        )
        point_set = get_point_set(self.point_set_var.get())
        body_names = [str(planet["name"]) for planet in self._visible_planets(snapshot)]
        if self.show_lots_var.get() and point_set.show_lots:
            body_names.extend(str(lot["name"]) for lot in self._visible_lots(snapshot))
        if self.show_nodes_var.get() and point_set.show_nodes:
            body_names.extend(str(node["name"]) for node in snapshot.get("lunarNodes", []))
        if self.show_fixed_stars_var.get() and point_set.show_fixed_stars:
            body_names.extend(str(star["name"]) for star in snapshot.get("fixedStars", []))
        self.focus_body_combo.configure(values=body_names)
        if self.focus_body_var.get() not in body_names and body_names:
            self.focus_body_var.set(body_names[0])

        self._set_text(
            self.score_detail_text,
            (
                f"Score: {snapshot['score']}\n"
                f"{format_score_breakdown(snapshot)}\n\n"
                "Evaluation\n"
                + "\n".join(score_evaluation_lines(snapshot))
                + "\n\n"
                "Reason Lines\n"
                + "\n".join(score_reason_lines(snapshot))
                + "\n\nAngles\n"
                + "\n".join(angle_testimony_lines(snapshot))
            ),
        )
        self._set_text(
            self.accounting_text,
            (
                "Point Accounting\n"
                + "\n".join(score_accounting_lines(snapshot))
                + "\n\nEvaluation\n"
                + "\n".join(score_evaluation_lines(snapshot))
            ),
        )
        self._set_text(self.conditions_text, "\n".join(condition_lines(snapshot)))
        self._set_text(self.angles_text, "\n".join(angle_testimony_lines(snapshot)))
        self._set_text(self.classical_point_data_text, build_classical_point_data_page(snapshot))
        self._set_text(self.medieval_text, build_medieval_data_page(snapshot))
        notes = snapshot.get("calculationNotes", [])
        if notes:
            self._set_text(self.conditions_text, "\n".join([*condition_lines(snapshot), "", "Calculation Notes", *[f"- {note}" for note in notes]]))

        lunar_context = rule_evaluations.get("lunarContext", {}) if isinstance(rule_evaluations, dict) else {}
        nakshatra = lunar_context.get("nakshatra", {}) if isinstance(lunar_context, dict) else {}
        tithi = lunar_context.get("tithi", {}) if isinstance(lunar_context, dict) else {}
        planetary_hour = rule_evaluations.get("planetaryHour", {}) if isinstance(rule_evaluations, dict) else {}
        rule_summary = [
            "Pure Python Electional Rules",
            f"Score impact: {float(rule_evaluations.get('scoreImpact', 0)):+.1f}" if isinstance(rule_evaluations, dict) else "Score impact: n/a",
            "",
            "Planetary Hour",
            (
                f"{planetary_hour.get('period', 'n/a').title()} hour {planetary_hour.get('hourNumber')} "
                f"ruled by {planetary_hour.get('hourRuler')} "
                f"(day ruler {planetary_hour.get('dayRuler')}, {float(planetary_hour.get('scoreImpact', 0)):+.1f})"
                if isinstance(planetary_hour, dict) and planetary_hour.get("available")
                else "Planetary hour: unavailable"
            ),
            (
                f"{planetary_hour.get('periodStartText')} to {planetary_hour.get('periodEndText')}"
                if isinstance(planetary_hour, dict) and planetary_hour.get("available")
                else ""
            ),
            "",
            "Sidereal Lunar Context",
            (
                f"Nakshatra: {nakshatra.get('name')} pada {nakshatra.get('pada')} "
                f"(#{nakshatra.get('index')})"
                if isinstance(nakshatra, dict) and nakshatra
                else "Nakshatra: unavailable"
            ),
            (
                f"Tithi: {tithi.get('paksha')} {tithi.get('name')} (#{tithi.get('number')})"
                if isinstance(tithi, dict) and tithi
                else "Tithi: unavailable"
            ),
            "",
            "Active Rules",
            *rule_lines(snapshot),
        ]
        self._set_text(self.rules_text, "\n".join(rule_summary) if rule_lines(snapshot) else "\n".join([*rule_summary, "- No active caution/support rules."]))
        self._set_text(self.significators_text, self._context_page_text("Significators", judgment_context_lines(snapshot, "significatorContext"), snapshot))
        self._set_text(self.moon_judgment_text, self._context_page_text("Moon", judgment_context_lines(snapshot, "moonCondition"), snapshot))
        self._set_text(self.house_rulers_text, self._context_page_text("House Rulers", judgment_context_lines(snapshot, "houseRulerContext"), snapshot))
        self._set_text(self.reception_text, self._context_page_text("Reception", judgment_context_lines(snapshot, "receptionContext"), snapshot))
        self._set_text(self.planet_condition_text, self._context_page_text("Planet Conditions", judgment_context_lines(snapshot, "planetConditionContext"), snapshot))
        self._set_text(self.declination_text, self._context_page_text("Declination", judgment_context_lines(snapshot, "declinationContext"), snapshot))
        self._set_text(self.advanced_aspects_text, self._context_page_text("Advanced Aspects", judgment_context_lines(snapshot, "advancedAspectContext"), snapshot))
        self._set_text(self.factor_explorer_text, "\n".join(factor_explorer_lines(snapshot, self.input_snapshot)))
        self._set_text(self.constellations_text, "\n".join(constellation_lines(snapshot)))

        planet_lines = []
        for planet in snapshot["positions"]:
            angular = " angular" if planet.get("isAngular") else ""
            dignity = format_dignity_summary(planet)
            constellation = planet.get("constellation", {})
            constellation_text = ""
            if isinstance(constellation, dict):
                constellation_text = f"; {constellation.get('name')} {float(constellation.get('spanDegrees', 0)):.0f}deg"
            planet_lines.append(
                f"{planet['name']:<8} {format_position(planet):<15} H{planet['house']:<2} "
                f"{dignity}; {format_motion_summary(planet)}{angular}{constellation_text}"
            )
        angle_lines = ["", "Angles:"]
        angle_lines.extend(format_angle(angle) for angle in snapshot["angles"])
        self._set_text(self.planets_text, "\n".join(planet_lines + angle_lines))

        cusp_lines = [
            f"House {cusp['house']:<2} {format_position(cusp):<16} span {next((row['span'] for row in house_span_rows(snapshot) if row['house'] == int(cusp['house'])), 0):>5.2f} deg"
            for cusp in snapshot.get("houseCusps", [])
        ]
        self._set_text(
            self.cusps_text,
            (
                f"{snapshot['houseSystem'].name} cusps\n"
                f"Zodiac: {snapshot['zodiacSystem'].name}\n"
                f"Ayanamsha: {float(snapshot['ayanamsha']):.3f} deg\n\n"
                + "\n".join(house_geometry_insight_lines(snapshot))
                + "\n\n"
                + "\n".join(cusp_lines)
                + "\n\n"
                + "\n".join(house_geometry_lines(snapshot))
            ),
        )

        lot_lines = [
            (
                f"{lot['name']:<16} {format_position(lot):<16} H{lot['house']:<2} "
                f"{lot['formula']} ({lot['sect']})\n"
                f"{'':<16} Topic: {lot.get('topic', 'n/a')}"
            )
            for lot in snapshot.get("lots", [])
        ]
        self._set_text(
            self.lots_text,
            (
                "Arabic Lots\n"
                f"Zodiac: {snapshot['zodiacSystem'].name}\n"
                f"House system: {snapshot['houseSystem'].name}\n\n"
                + ("\n".join(lot_lines) if lot_lines else "No lots calculated.")
            ),
        )

        node_lines = [
            (
                f"{node['name']:<16} {format_position(node):<16} H{node['house']:<2} "
                f"{node.get('calculation', 'node calculation')}\n"
                f"{'':<16} Closest angle: {node['closestAngle']['shortName']} {node['closestAngle']['distance']:.1f} deg"
            )
            for node in snapshot.get("lunarNodes", [])
        ]
        self._set_text(
            self.nodes_text,
            (
                "Lunar Nodes\n"
                f"Zodiac: {snapshot['zodiacSystem'].name}\n"
                f"House system: {snapshot['houseSystem'].name}\n\n"
                + ("\n".join(node_lines) if node_lines else "No lunar nodes calculated.")
            ),
        )

        timing = snapshot.get("timingProfile", {})
        if isinstance(timing, dict):
            timing_lines = [
                "Aspect Timing",
                str(timing.get("summary", "Timing profile unavailable.")),
                "",
                "How to use this page",
                "- Check whether the strongest contacts are applying or separating.",
                "- Prefer windows where support is applying and stress is separating or weak.",
                "- Compare this page with Timeline for exact local-day and next-24h peaks.",
                "",
                f"Applying contacts: {timing.get('applyingCount', 0)}",
                f"Support: {timing.get('supportCount', 0)}",
                f"Stress: {timing.get('stressCount', 0)}",
            ]
            for title, key in (("Next aspect", "nextAspect"), ("Next support", "nextSupport"), ("Next stress", "nextStress")):
                item = timing.get(key)
                if isinstance(item, dict):
                    timing_lines.extend(
                        [
                            "",
                            title,
                            f"- {item.get('label')}",
                            f"- Orb: {item.get('orbText', 'n/a')}",
                            f"- Exact in: {item.get('timeToExactText', 'n/a')}",
                            f"- Perfects near: {item.get('perfectsAtText', 'n/a') or 'n/a'}",
                        ]
                    )
            self._set_text(self.timing_text, "\n".join(timing_lines))
        else:
            self._set_text(
                self.timing_text,
                "\n".join(
                    [
                        "Aspect Timing",
                        "",
                        "Timing profile unavailable for this chart.",
                        "",
                        "How to use this page",
                        "- Recalculate after changing time, location, aspect focus, or point set.",
                        "- Use Timeline for local-day and rolling-24h aspect scans when available.",
                        "- Use Find Best to generate candidate windows with applying support.",
                    ]
                ),
            )

        aspect_lines = []
        for aspect in snapshot["detectedAspects"]:
            aspect_lines.append(f"{format_aspect_summary(aspect)} - {aspect['tone']}")
        self._set_text(
            self.aspects_text,
            "\n".join(aspect_lines)
            or "\n".join(
                [
                    "Aspects",
                    "",
                    "No selected major aspects are currently in orb.",
                    "",
                    "Try next",
                    "- Enable more aspect types in the left rail.",
                    "- Switch Points from a smaller set to Full Electional.",
                    "- Widen the search or use Timeline to inspect the day before filtering.",
                ]
            ),
        )
        self._set_text(self.aspectarian_text, format_aspectarian(snapshot))
        self._set_text(self.aspect_strength_text, "\n".join(strongest_aspect_analysis_lines(snapshot)))

        star_lines = [
            f"{star['name']:<16} {format_position(star):<15} {star['nature']:<12} mag {float(star['magnitude']):>5.2f}"
            for star in snapshot.get("fixedStars", [])
        ]
        contact_lines = [
            f"{format_fixed_star_contact(contact)}\n  {contact.get('note', '')}"
            for contact in snapshot.get("fixedStarContacts", [])
        ]
        self._set_text(
            self.fixed_stars_text,
            (
                f"Fixed-star score: {float(snapshot['scoreBreakdown'].get('fixedStar', 0)):+.1f}\n"
                "Contacts within diagnostic star orb\n"
                + ("\n".join(contact_lines) if contact_lines else "No fixed-star conjunctions within the diagnostic star orb.")
                + "\n\nReference positions\n"
                + "\n".join(star_lines)
            ),
        )

    def _selected_window_interpretation(self, snapshot: dict[str, object], rank: int, count: int) -> str:
        support = [aspect["label"] for aspect in snapshot["detectedAspects"] if aspect["tone"] == "support"]
        stress = [aspect["label"] for aspect in snapshot["detectedAspects"] if aspect["tone"] == "stress"]
        angular = [
            f"{planet['name']} near {planet['closestAngle']['shortName']}"
            for planet in snapshot["positions"]
            if planet.get("isAngular")
        ]
        lines = [
            f"Selected window ranks {rank} of {count} with score {snapshot['score']}.",
            str(snapshot.get("note", "No interpretation note available.")),
            "Moon phase: " + format_lunar_phase(snapshot) + ".",
        ]
        if support:
            lines.append("Support: " + ", ".join(support[:3]) + ".")
        if stress:
            lines.append("Watch: " + ", ".join(stress[:3]) + ".")
        if angular:
            lines.append("Angles: " + ", ".join(angular[:3]) + ".")
        return "\n".join(lines)

    def _focus_selected_body(self) -> None:
        if not self.selected_window:
            return
        name = self.focus_body_var.get()
        self._select_planet_by_name(name)
        self._select_lot_by_name(name)
        self._select_node_by_name(name)
        self._select_fixed_star_by_name(name)

    def _select_planet_by_id(self, planet_id: str) -> None:
        if not self.selected_window:
            return
        planet = next((item for item in self.selected_window["positions"] if str(item["id"]) == planet_id), None)
        if planet:
            self._show_planet_focus(planet)

    def _select_planet_by_name(self, planet_name: str) -> None:
        if not self.selected_window:
            return
        planet = next((item for item in self.selected_window["positions"] if str(item["name"]) == planet_name), None)
        if planet:
            self._show_planet_focus(planet)

    def _select_lot_by_id(self, lot_id: str) -> None:
        if not self.selected_window:
            return
        lot = next((item for item in self.selected_window.get("lots", []) if str(item["id"]) == lot_id), None)
        if lot:
            self._show_lot_focus(lot)

    def _select_lot_by_name(self, lot_name: str) -> None:
        if not self.selected_window:
            return
        lot = next((item for item in self.selected_window.get("lots", []) if str(item["name"]) == lot_name), None)
        if lot:
            self._show_lot_focus(lot)

    def _select_node_by_id(self, node_id: str) -> None:
        if not self.selected_window:
            return
        node = next((item for item in self.selected_window.get("lunarNodes", []) if str(item["id"]) == node_id), None)
        if node:
            self._show_node_focus(node)

    def _select_node_by_name(self, node_name: str) -> None:
        if not self.selected_window:
            return
        node = next((item for item in self.selected_window.get("lunarNodes", []) if str(item["name"]) == node_name), None)
        if node:
            self._show_node_focus(node)

    def _select_fixed_star_by_id(self, star_id: str) -> None:
        if not self.selected_window:
            return
        star = next((item for item in self.selected_window.get("fixedStars", []) if str(item["id"]) == star_id), None)
        if star:
            self._show_fixed_star_focus(star)

    def _select_fixed_star_by_name(self, star_name: str) -> None:
        if not self.selected_window:
            return
        star = next((item for item in self.selected_window.get("fixedStars", []) if str(item["name"]) == star_name), None)
        if star:
            self._show_fixed_star_focus(star)

    def _show_lot_focus(self, lot: dict[str, object]) -> None:
        self.focused_aspect_bodies = set()
        self.focused_body_kind = "lot"
        self.focused_body_name = str(lot["name"])
        self.focus_body_var.set(str(lot["name"]))
        text = (
            f"{lot['name']}: {format_position(lot)} in House {lot['house']}.\n"
            f"Formula: {lot['formula']} ({lot['sect']} chart).\n"
            f"Topic: {lot.get('topic', 'n/a')}.\n"
            f"Closest angle: {lot['closestAngle']['shortName']} at {lot['closestAngle']['distance']:.1f} deg."
        )
        self._set_text(self.interpretation_text, text)
        self._redraw_selected_window()
        self.status_var.set(f"Focused {lot['name']} at {format_position(lot)}.")
        self._log_event(f"Focused lot: {lot['name']} {format_position(lot)}")

    def _show_node_focus(self, node: dict[str, object]) -> None:
        self.focused_aspect_bodies = set()
        self.focused_body_kind = "node"
        self.focused_body_name = str(node["name"])
        self.focus_body_var.set(str(node["name"]))
        text = (
            f"{node['name']}: {format_position(node)} in House {node['house']}.\n"
            f"Calculation: {node.get('calculation', 'node calculation')}.\n"
            f"Closest angle: {node['closestAngle']['shortName']} at {node['closestAngle']['distance']:.1f} deg.\n"
            "Electional use: nodes can mark karmic, public, or fated-feeling emphasis; confirm by aspects and house topic."
        )
        self._set_text(self.interpretation_text, text)
        self._redraw_selected_window()
        self.status_var.set(f"Focused {node['name']} at {format_position(node)}.")
        self._log_event(f"Focused node: {node['name']} {format_position(node)}")

    def _show_fixed_star_focus(self, star: dict[str, object]) -> None:
        self.focused_aspect_bodies = set()
        self.focused_body_kind = "star"
        self.focused_body_name = str(star["name"])
        self.focus_body_var.set(str(star["name"]))
        contacts = [
            contact
            for contact in (self.selected_window or {}).get("fixedStarContacts", [])
            if isinstance(contact, dict) and contact.get("starId") == star.get("id")
        ]
        contact_lines = [format_fixed_star_contact(contact) for contact in contacts]
        text = (
            f"{star['name']}: {format_position(star)}.\n"
            f"Nature: {star.get('nature', 'n/a')}; magnitude {float(star.get('magnitude', 0)):.2f}.\n"
            f"Note: {star.get('electionalNote', 'No note available.')}\n"
            f"Contacts: {', '.join(contact_lines) if contact_lines else 'No conjunctions within the diagnostic star orb.'}"
        )
        self._set_text(self.interpretation_text, text)
        self._redraw_selected_window()
        self.status_var.set(f"Focused fixed star {star['name']} at {format_position(star)}.")
        self._log_event(f"Focused fixed star: {star['name']} {format_position(star)}")

    def _show_planet_focus(self, planet: dict[str, object]) -> None:
        self.focused_aspect_bodies = set()
        self.focused_body_kind = "planet"
        self.focused_body_name = str(planet["name"])
        self.focus_body_var.set(str(planet["name"]))
        self._set_text(self.interpretation_text, format_planet_focus(planet, self.selected_window["detectedAspects"]))
        self._redraw_selected_window()
        self.status_var.set(f"Focused {planet['name']} at {format_position(planet)}.")
        self._log_event(f"Focused planet: {planet['name']} {format_position(planet)}")

    def _session_payload(self) -> dict[str, Any]:
        return {
            "date": self.date_var.get(),
            "time": self.time_var.get(),
            "location_preset": self.location_var.get(),
            "location_name": self.location_name_var.get(),
            "latitude": self.latitude_var.get(),
            "longitude": self.longitude_var.get(),
            "timezone": self.timezone_var.get(),
            "objective": self.objective_var.get(),
            "preset": self.preset_var.get(),
            "zodiac_system": self.zodiac_system_var.get(),
            "house_system": self.house_system_var.get(),
            "active_aspect_profile": self.active_aspect_profile.id,
            "aspects": {aspect_id: var.get() for aspect_id, var in self.aspect_vars.items()},
            "scan_hours": self.scan_hours_var.get(),
            "step_minutes": self.step_minutes_var.get(),
            "search_preset": self.search_preset_var.get(),
            "search_quality_mode": self.search_quality_mode_var.get(),
            "minimum_score": self.minimum_score_var.get(),
            "minimum_fit": self.minimum_fit_var.get(),
            "minimum_confidence": self.minimum_confidence_var.get(),
            "minimum_cleanliness": self.minimum_cleanliness_var.get(),
            "maximum_volatility": self.maximum_volatility_var.get(),
            "max_results": self.max_results_var.get(),
            "avoid_major_stress": self.avoid_major_stress_var.get(),
            "require_applying_support": self.require_applying_support_var.get(),
            "require_angular_benefic": self.require_angular_benefic_var.get(),
            "avoid_angular_malefics": self.avoid_angular_malefics_var.get(),
            "require_moon_non_void": self.require_moon_non_void_var.get(),
            "avoid_objective_antipatterns": self.avoid_objective_antipatterns_var.get(),
            "manual_validation_comparison": self.manual_validation_result,
            "display_options": {
                "show_aspects": self.show_aspects_var.get(),
                "show_lots": self.show_lots_var.get(),
                "show_nodes": self.show_nodes_var.get(),
                "show_fixed_stars": self.show_fixed_stars_var.get(),
                "show_score_overlay": self.show_score_overlay_var.get(),
                "compact_wheel": self.compact_wheel_var.get(),
                "wheel_zoom": self.wheel_zoom,
                "point_set": get_point_set(self.point_set_var.get()).id,
                "page_mode": self._current_page_mode_id(),
                "right_panel_theme": RIGHT_PANEL_THEME_IDS_BY_NAME.get(self.right_panel_theme_var.get(), "classic-natal"),
                "wheel_view_preset": WHEEL_VIEW_PRESET_IDS_BY_NAME.get(self.wheel_view_preset_var.get(), "full-classic"),
            },
        }

    def _save_session(self) -> None:
        save_session_state(self._session_payload())

    def _close(self) -> None:
        try:
            self._save_session()
        finally:
            self.root.destroy()

    def _set_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state=tk.DISABLED)

    def _log_event(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.event_log.append(f"{stamp}  {message}")
        self.event_log = self.event_log[-80:]
        self._refresh_event_log()

    def _refresh_event_log(self) -> None:
        if not hasattr(self, "log_text"):
            return
        body = "\n".join(reversed(self.event_log)) or "No session events yet."
        self._set_text(self.log_text, body)


def main() -> None:
    root = tk.Tk()
    ElectionalDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
