"""Native desktop application shell for Electional Software."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
from pathlib import Path
import re
import threading
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
from .engine.chart import build_election_report, build_snapshot_for_moment, clear_snapshot_cache, format_angle, format_position, snapshot_cache_info
from .constellations import ECLIPTIC_CONSTELLATION_SPANS
from .desktop_live_sky import LIVE_SKY_BODY_COLORS, LIVE_SKY_ORBIT_ORDER, live_sky_body_rows, live_sky_timestamp_line
from .desktop_motion_pages import midpoint_contact_rows, midpoint_page_lines, midpoint_pair_rows, retrograde_motion_rows, retrograde_page_lines
from .ui.panels.actions import DesktopActionsMixin, bind_desktop_globals as bind_actions_globals
from .ui.panels.navigation import DesktopNavigationMixin, bind_desktop_globals as bind_navigation_globals
from .desktop_pages import DesktopPagesMixin, bind_desktop_globals as bind_pages_globals
from .desktop_workspace import DesktopWorkspaceMixin, bind_desktop_globals as bind_workspace_globals
from .ui.panels.left_rail import DesktopLeftRailMixin, bind_desktop_globals as bind_left_rail_globals
from .desktop_right_panel import DesktopRightPanelMixin, bind_desktop_globals as bind_right_panel_globals
from .ui.panels.wheel import DesktopWheelMixin, bind_desktop_globals as bind_wheel_globals
from .desktop_validation import (
    build_manual_validation_comparison,
    format_manual_validation_comparison,
    manual_validation_result_summary,
    manual_validation_sign_starts,
    parse_manual_validation_values,
    validation_quick_read_lines,
    validation_workbench_lines,
)
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
    load_recent_locations,
    load_user_locations,
    remember_recent_location,
    reset_location_defaults,
    save_hidden_builtin_location_ids,
    save_home_location_name,
    save_recent_locations,
    save_user_locations,
    resolve_location_by_name,
    upsert_user_location,
)
from .location_search import (
    LocationSearchResult,
    location_search_result_label,
    search_city_locations,
    timezone_warning_for_location,
)
from .point_sets import POINT_SET_NAMES, PointSet, get_point_set, visible_lots_for_point_set, visible_planets_for_point_set
from .presets import ELECTIONAL_PRESETS, RULERS
from .references import dignity_table_lines, lot_reference_lines, system_reference_lines
from .reports.text_report import (
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
    planet_strength_lines,
    planet_strength_workbench_lines,
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
from .engine.search import (
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
    aspect_peak_lines,
    build_search_config_from_text,
    ELECTION_STRATEGY_NAMES,
    election_alert_lines,
    election_strategy_values,
    exact_search_query_summary,
    format_search_summary,
    parse_exact_search_query,
    search_preset_values,
    why_not_time_lines,
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
from .time_utils import normalize_time_text, zoned_time_to_utc
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
    "guide": "Guide",
    "wheel": "Wheel",
    "wheel-aspectarian": "Wheel + Aspectarian",
    "analysis": "Analysis",
    "classical-point-data": "Classical Point Data",
    "medieval-data": "Medieval Data",
    "transit-search": "Transit Search",
    "retrogrades": "Retrogrades",
    "midpoints": "Midpoints",
    "live-sky": "Live Sky",
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
WHEEL_PRESET_HELP = {
    "clean": "Clean reading: core planets and aspects, extra chart room, minimal diagnostics.",
    "full-classic": "Full Classic: reference-style wheel with lots, nodes, fixed stars, and aspect lines.",
    "diagnostic": "Diagnostic: all overlays plus house-span/geometry clues for troubleshooting.",
}
HOME_LOCATION_DEFAULT_LABEL = "Local timezone default"
LEFT_GUIDED_COLLAPSED_SECTIONS = ("Location", "Election Model", "Search Strategy", "Safety Filters", "Aspect Focus")
TOP_NAV_BUTTON_METRICS = {"padx": 11, "pady": 3, "font_size": 9}
SEARCH_TARGET_PLANETS = ("", "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")
SEARCH_TARGET_SIGNS = (
    "",
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
    "Ophiuchus",
)
SEARCH_TARGET_ASPECTS = ("", "Conjunction", "Opposition", "Square", "Trine", "Sextile", "Semisquare", "Quincunx")
SEARCH_TARGET_HOUSES = ("", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12")
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
    "Retrogrades",
    "Midpoints",
    "Live Sky",
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
    "PDF Intake",
    "Log",
)
TOP_NAV_PAGE_TARGETS = {
    "Guide": "Summary",
    "Wheel": "Window",
    "Search": "Search",
    "Analysis": "Analysis",
    "Timeline": "Timeline",
    "Validation": "Validation",
    "Reports": "Reports",
}
TOP_NAV_SPECIAL_ACTIONS: set[str] = set()
TOP_NAV_ITEMS = ("Guide", "Wheel", "Search", "Analysis", "Timeline", "Validation", "Reports")
GUIDED_WORKFLOW_STEPS = (
    ("objective", "1", "Electing"),
    ("location", "2", "Where"),
    ("range", "3", "Date Range"),
    ("times", "4", "Times"),
    ("search", "5", "Find"),
    ("compare", "6", "Compare"),
    ("export", "7", "Save"),
)
TOP_NAV_WORKSPACE_SUMMARIES = {
    "Guide": "Guided election path from objective through final export.",
    "Wheel": "Main chart wheel with selected window and right-side judgment summary.",
    "Search": "Election search workbench with filters, candidates, rejection reasons, and relax suggestions.",
    "Analysis": "Deep electional review with aspect highlights, Moon condition, rules, and validation.",
    "Timeline": "Current, local-day, and rolling next-24-hour aspect peaks.",
    "Validation": "Accuracy audit, chart settings, and manual CapricornPROMETHEUS comparison.",
    "Reports": "Readable summaries, decision sheets, shortlist tools, and export actions.",
    "Retrogrades": "Motion status, stations, and retrograde electional cautions.",
    "Midpoints": "Primary midpoint axes and close midpoint contacts for the displayed chart.",
    "Live Sky": "Live/manual orbital sky map with date controls and zodiac position context.",
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
    "Retrogrades": "Retrogrades",
    "Midpoints": "Midpoints",
    "Live Sky": "Live Sky",
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
    "Retrogrades",
    "Midpoints",
    "Live Sky",
    "Shortlist",
    "Log",
    "Chart Data",
    "Save Wheel",
)
RIBBON_GROUPS = (
    ("Transits", ("Transits/Timeline", "Search Page", "Aspects", "Aspect Strength", "Day Report", "Report")),
    ("Electional", ("Electional Search", "Void Course", "Heliacal Search", "Out of Bounds", "Find Best", "Show Current")),
    ("Utility", ("Chart Data", "Diagnostics", "Map", "Fixed Stars", "Lots", "Shortlist")),
    ("Configuration", ("Aspect Config", "Assets", "Systems", "Bounds", "Preferences", "Focus Wheel")),
)
RIBBON_COLUMNS = 3
VIEW_PAGE_QUICK_ACTIONS = ("Interpretation", "Search", "Analysis", "Timeline", "Live Sky")

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
WHEEL_CANVAS_DEFAULT_WIDTH = 1180
WHEEL_CANVAS_DEFAULT_HEIGHT = 860
CENTER_WORKSPACE_MIN_HEIGHT = 720
CENTER_PANE_DEFAULT_WIDTH = 1180
WHEEL_EXPORT_SCALE_DEFAULT = 3.0
WHEEL_EXPORT_SCALE_MIN = 1.0
WHEEL_EXPORT_SCALE_MAX = 4.0
WHEEL_EXPORT_QUALITY_LABELS = ("2x export", "3x export", "4x export")


def _clamp_float(value: object, minimum: float, maximum: float, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def wheel_export_scale_value(value: object) -> float:
    text = str(value or "").strip().lower().replace("export", "").replace("x", "").strip()
    return _clamp_float(text if text else value, WHEEL_EXPORT_SCALE_MIN, WHEEL_EXPORT_SCALE_MAX, WHEEL_EXPORT_SCALE_DEFAULT)


def wheel_export_scale_label(value: object) -> str:
    scale = wheel_export_scale_value(value)
    return f"{scale:.0f}x export" if abs(scale - round(scale)) < 0.01 else f"{scale:.1f}x export"


def wheel_export_postscript_options(width: object, height: object, scale: object) -> dict[str, object]:
    canvas_width = max(1, int(_clamp_float(width, 1, 10000, 1200)))
    canvas_height = max(1, int(_clamp_float(height, 1, 10000, 900)))
    export_scale = wheel_export_scale_value(scale)
    return {
        "x": 0,
        "y": 0,
        "width": canvas_width,
        "height": canvas_height,
        "pagewidth": f"{int(canvas_width * export_scale)}p",
        "pageheight": f"{int(canvas_height * export_scale)}p",
    }


def tk_scaling_for_dpi(dpi: object) -> float:
    try:
        dpi_value = float(dpi)
    except (TypeError, ValueError):
        dpi_value = 96.0
    return _clamp_float(dpi_value / 72.0, 1.0, 2.8, 96.0 / 72.0)


def enable_process_dpi_awareness() -> str:
    """Ask Windows to render Tk at native monitor DPI instead of bitmap-stretching it."""

    try:
        import ctypes
        import sys

        if sys.platform != "win32":
            return "platform-default"
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return "per-monitor-dpi-aware"
        except (AttributeError, OSError, ValueError):
            ctypes.windll.user32.SetProcessDPIAware()
            return "system-dpi-aware"
    except Exception:
        return "dpi-awareness-unavailable"


def configure_tk_render_quality(root: tk.Tk) -> dict[str, object]:
    dpi = float(root.winfo_fpixels("1i") or 96.0)
    scaling = tk_scaling_for_dpi(dpi)
    root.tk.call("tk", "scaling", scaling)
    return {
        "dpi": dpi,
        "scaling": scaling,
        "summary": f"{dpi:.0f} DPI / Tk scaling {scaling:.2f}",
    }


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


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
        f"Ribbon columns: {RIBBON_COLUMNS}",
        "Advanced tools default: hidden",
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


def compact_place_name(name: str) -> str:
    text = str(name or "").strip()
    replacements = {
        ", California": ", CA",
        ", United States": ", USA",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text or "Location waiting"


def location_summary(location: LocationPreset | None) -> str:
    if not location:
        return "Location waiting"
    return f"{compact_place_name(location.name)} | {location.timezone}"


def canonical_location_summary(location: LocationPreset | None) -> str:
    if not location:
        return "Site: waiting"
    return (
        f"Site: {compact_place_name(location.name)} | "
        f"{location.timezone} | {location.latitude:.3f}, {location.longitude:.3f}"
    )


def location_coordinate_summary(location: LocationPreset | None) -> str:
    if not location:
        return "Coordinates waiting"
    return f"{location.latitude:.3f}, {location.longitude:.3f}\n{location.timezone}"


def tools_ribbon_label(visible: bool) -> str:
    return "Hide Tools" if visible else "Show Tools"


def tools_ribbon_status(visible: bool) -> str:
    return "Specialist tools visible." if visible else "Specialist tools hidden; use top navigation and the hub first."


def left_section_initially_collapsed(title: str) -> bool:
    return title in LEFT_GUIDED_COLLAPSED_SECTIONS


def top_nav_button_metrics() -> dict[str, int]:
    return dict(TOP_NAV_BUTTON_METRICS)


def wheel_preset_help_text(preset_id_or_name: str) -> str:
    preset_id = WHEEL_VIEW_PRESET_IDS_BY_NAME.get(preset_id_or_name, str(preset_id_or_name or "").strip().lower())
    return WHEEL_PRESET_HELP.get(preset_id, WHEEL_PRESET_HELP["full-classic"])


def wheel_overlay_summary(
    *,
    aspects: bool,
    lots: bool,
    nodes: bool,
    fixed_stars: bool,
    score: bool,
    compact: bool,
) -> str:
    enabled = []
    if aspects:
        enabled.append("aspects")
    if lots:
        enabled.append("lots")
    if nodes:
        enabled.append("nodes")
    if fixed_stars:
        enabled.append("stars")
    if score:
        enabled.append("score")
    if compact:
        enabled.append("compact labels")
    return "Overlays: " + (", ".join(enabled) if enabled else "none")


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
    multi = window.get("multiObjective", {})
    if isinstance(multi, Mapping):
        badges.insert(0, (f"Power {multi.get('power', '--')}", "support"))
        badges.insert(1, (f"Safety {multi.get('safety', '--')}", "cleanliness"))
        badges.insert(2, (f"Stable {multi.get('stability', '--')}", "stage"))
        badges.insert(3, (f"Risk {multi.get('risk', '--')}", "stress" if multi.get("risk") == "High" else "volatility" if multi.get("risk") == "Medium" else "support"))
    fragility = window.get("fragility")
    if not isinstance(fragility, Mapping):
        stability_payload = window.get("windowStability", {})
        fragility = stability_payload.get("fragility", {}) if isinstance(stability_payload, Mapping) else {}
    if isinstance(fragility, Mapping) and fragility.get("band"):
        band = str(fragility.get("band"))
        tone = "support" if band == "Low" else "volatility" if band == "Medium" else "stress"
        badges.append((f"Frag {band}", tone))
    cluster = window.get("windowCluster", {})
    if isinstance(cluster, Mapping) and cluster.get("index"):
        badges.append((f"Cluster {cluster.get('index')}", "stage"))
    role = str(window.get("tradeoffRole") or "").strip()
    if role:
        badges.append((role, "stage"))
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


def compact_aspect_headline(highlights: Mapping[str, object] | None) -> tuple[str, str, str]:
    if not isinstance(highlights, Mapping):
        return "No aspect highlight", "Run Calculate or Timeline to scan current contacts.", "neutral"
    current = highlights.get("current")
    if not isinstance(current, Mapping):
        return "No aspect in orb", "Open Timeline for local-day and next-24h peaks.", "neutral"
    label = str(current.get("label") or "Aspect highlight")
    tone = str(current.get("tone") or "mixed")
    orb = str(current.get("orbText") or "orb n/a")
    phase = str(current.get("phaseLabel") or ("Applying" if current.get("isApplying") else "Separating"))
    strength = current.get("strength")
    strength_text = f"strength {_safe_float(strength):.1f}" if strength is not None else "strength n/a"
    return label, f"{phase}; {orb}; {strength_text}.", tone


def workspace_hub_cards(
    snapshot: Mapping[str, object] | None,
    input_snapshot: Mapping[str, object] | None,
    location: LocationPreset | None,
    highlights: Mapping[str, object] | None,
    windows: list[dict[str, object]],
    *,
    selected_index: int = -1,
    displayed_source: str = "",
    rejection_summary: Mapping[str, object] | None = None,
) -> tuple[tuple[str, str, str, str], ...]:
    if not isinstance(snapshot, Mapping):
        return (
            ("Strongest Now", "No aspect highlight", "Run Calculate to populate the hub.", "neutral"),
            ("Next Move", "Next: show current chart", "Use Current before searching for windows.", "warning"),
            ("Quality", "Score --", "No calculation yet.", "neutral"),
        )

    signal_title, signal_detail, signal_tone = compact_aspect_headline(highlights)
    has_rejections = bool(isinstance(rejection_summary, Mapping) and rejection_summary.get("topReasons"))
    next_title, next_body, _next_hint = workflow_next_step_lines(
        has_chart=True,
        candidate_count=len(windows),
        selected_index=selected_index,
        displayed_source=displayed_source,
        has_rejections=has_rejections,
    )
    score = snapshot.get("score", "--")
    try:
        score_value = int(score)
    except (TypeError, ValueError):
        score_value = 0
    quality_headline = f"Score {score} / {score_band_label(score_value)}"
    confidence = diagnostic_metric_value(snapshot, "confidence")
    clean = diagnostic_metric_value(snapshot, "cleanliness")
    volatility = diagnostic_metric_value(snapshot, "volatility")
    support = sum(1 for aspect in snapshot.get("detectedAspects", []) if isinstance(aspect, Mapping) and aspect.get("tone") == "support")
    stress = sum(1 for aspect in snapshot.get("detectedAspects", []) if isinstance(aspect, Mapping) and aspect.get("tone") == "stress")
    quality_detail = f"Conf {confidence}; Clean {clean}; Vol {volatility}; +{support} / !{stress}"
    return (
        ("Strongest Now", signal_title, signal_detail, signal_tone),
        ("Next Move", next_title, next_body, "warning" if has_rejections or not windows else "support"),
        ("Quality", quality_headline, quality_detail, "support" if score_value >= 80 else "warning" if score_value >= 60 else "stress"),
    )


def left_status_chip_lines(
    date_text: str,
    time_text: str,
    location_name: str,
    timezone_name: str,
    zodiac_system: str,
    house_system: str,
    search_mode: str,
    validation_text: str,
) -> tuple[str, str, str, str]:
    date_value = date_text.strip() or "Date waiting"
    time_value = time_text.strip() or "Time waiting"
    location = location_name.strip() or "Location waiting"
    timezone = timezone_name.strip() or "Timezone waiting"
    zodiac = zodiac_system.strip() or "Zodiac waiting"
    houses = house_system.strip() or "Houses waiting"
    mode = search_mode.strip() or "Balanced"
    validation = validation_text.strip() or "Validation: waiting"
    return (
        f"Chart: {date_value} {time_value}",
        f"Site: {compact_place_name(location)} | {timezone}",
        f"Model: {zodiac} / {houses}",
        f"Search: {mode} | {validation.replace('Validation: ', '')}",
    )


def displayed_chart_state_line(
    input_snapshot: Mapping[str, object],
    selected_window: Mapping[str, object],
    *,
    displayed_source: str,
    selected_index: int,
) -> str:
    offset = selection_offset_label(dict(input_snapshot), dict(selected_window))
    source_key = str(displayed_source or "").lower()
    if source_key == "preview":
        source = "Preview Chart"
    elif source_key == "input chart":
        source = "Current Chart"
    else:
        source = f"Candidate #{selected_index + 1}"
    return f"{source} | {offset}"


def search_workbench_compact_lines(
    *,
    profile_name: str,
    action_note: str,
    windows: list[dict[str, object]],
    selected_time: str,
    search_mode: str,
    scan_hours: str,
    step_minutes: str,
    active_aspects: int,
    rejection_summary: Mapping[str, object] | None = None,
) -> tuple[str, str, str]:
    title = f"Search Console | {profile_name}"
    if windows:
        top = windows[0]
        summary = (
            f"{len(windows)} candidate{'s' if len(windows) != 1 else ''} ready | "
            f"top score {top.get('score', '?')} | {top.get('formattedTime', top.get('time', 'time n/a'))}"
        )
        aspects = top.get("detectedAspects", []) if isinstance(top, dict) else []
        strongest = ""
        if isinstance(aspects, list) and aspects:
            strongest = f" | strongest {aspects[0].get('label', 'aspect')}"
        cluster_text = ""
        cluster = top.get("windowCluster", {}) if isinstance(top, dict) else {}
        if isinstance(cluster, Mapping) and cluster.get("index"):
            cluster_text = f" | cluster {cluster.get('index')}: {cluster.get('type', 'window')}"
        detail = f"{action_note} | {search_mode} | {scan_hours}h/{step_minutes}m | {active_aspects} aspects{strongest}{cluster_text}"
        return title, summary, detail
    blockers: list[str] = []
    if isinstance(rejection_summary, Mapping):
        top_reasons = rejection_summary.get("topReasons", [])
        if isinstance(top_reasons, list) and top_reasons:
            blockers = [f"{reason} ({count})" for reason, count in top_reasons[:2]]
    blocker_text = ", ".join(blockers) if blockers else "no blockers reported"
    summary = f"No matching candidates yet | displayed {selected_time}"
    detail = f"{action_note} | {search_mode} | {scan_hours}h/{step_minutes}m | {active_aspects} aspects | {blocker_text}"
    return title, summary, detail


def guided_workflow_rows(
    *,
    objective: str,
    location_name: str,
    date_text: str,
    time_text: str,
    scan_hours: str,
    step_minutes: str,
    has_chart: bool,
    candidate_count: int,
    shortlisted_count: int,
    selected_index: int,
    displayed_source: str,
) -> tuple[dict[str, str], ...]:
    objective_ready = bool(str(objective).strip())
    location_ready = bool(str(location_name).strip())
    range_ready = bool(str(date_text).strip()) and _safe_float(scan_hours, 0) > 0
    times_ready = bool(str(time_text).strip()) and _safe_float(step_minutes, 0) > 0
    search_done = candidate_count > 0
    compare_ready = candidate_count >= 2 or shortlisted_count >= 2
    compare_done = shortlisted_count >= 2
    export_ready = shortlisted_count > 0 or displayed_source == "selected candidate" or (candidate_count > 0 and selected_index >= 0)

    def status(done: bool, active: bool) -> str:
        if done:
            return "done"
        if active:
            return "active"
        return "pending"

    rows = (
        ("objective", "1", "Electing", str(objective or "Choose objective"), status(objective_ready, True), "Set objective"),
        ("location", "2", "Where", compact_place_name(location_name or "Choose location"), status(location_ready, objective_ready), "Set place"),
        ("range", "3", "Date Range", f"{date_text or 'date'} + {scan_hours or '?'}h", status(range_ready, location_ready), "Set range"),
        ("times", "4", "Times", f"{time_text or 'time'} / {step_minutes or '?'}m step", status(times_ready, range_ready), "Tune times"),
        ("search", "5", "Find", f"{candidate_count} candidate{'s' if candidate_count != 1 else ''}", status(search_done, has_chart and times_ready), "Find best"),
        ("compare", "6", "Compare", f"{min(candidate_count, 3)} top / {shortlisted_count} saved", status(compare_done, compare_ready), "Compare top"),
        ("export", "7", "Save", "final pick" if export_ready else "waiting", status(False, export_ready), "Export"),
    )
    return tuple(
        {
            "id": step_id,
            "number": number,
            "label": label,
            "value": value,
            "status": step_status,
            "action": action,
        }
        for step_id, number, label, value, step_status, action in rows
    )


def guided_workflow_status_counts(rows: tuple[Mapping[str, str], ...]) -> dict[str, int]:
    counts = {"done": 0, "active": 0, "pending": 0}
    for row in rows:
        status = str(row.get("status") or "pending")
        counts[status if status in counts else "pending"] += 1
    return counts


def guided_workbench_summary(rows: tuple[Mapping[str, str], ...]) -> tuple[str, str]:
    counts = guided_workflow_status_counts(rows)
    active = next((row for row in rows if str(row.get("status")) == "active"), None)
    pending = next((row for row in rows if str(row.get("status")) == "pending"), None)
    next_row = active or pending or (rows[-1] if rows else {})
    next_label = str(next_row.get("label") or "Election")
    next_action = str(next_row.get("action") or "Continue")
    headline = f"{counts['done']} of {len(rows)} steps ready"
    detail = f"Next: {next_label} - {next_action}."
    return headline, detail


def location_intelligence_lines(
    *,
    location_name: str,
    timezone_name: str,
    latitude: str,
    longitude: str,
    home_location_name: str | None,
    recent_locations: list[LocationPreset] | tuple[LocationPreset, ...],
    saved_count: int,
    timezone_warning: str,
) -> tuple[str, str, str]:
    place = compact_place_name(location_name or "Location waiting")
    timezone = timezone_name.strip() or "Timezone waiting"
    try:
        coordinate_text = f"{float(latitude):.3f}, {float(longitude):.3f}"
    except (TypeError, ValueError):
        coordinate_text = "coordinates waiting"
    home = home_location_name.strip() if isinstance(home_location_name, str) and home_location_name.strip() else HOME_LOCATION_DEFAULT_LABEL
    recent_names = [compact_place_name(location.name) for location in recent_locations[:2]]
    recent = ", ".join(recent_names) if recent_names else "none yet"
    warning = timezone_warning.strip() or "Timezone check waiting."
    if len(warning) > 84:
        warning = warning[:81].rstrip() + "..."
    return (
        f"{place} | {timezone} | {coordinate_text}",
        f"Home: {compact_place_name(home)} | Recent: {recent}",
        f"Saved: {saved_count} | {warning}",
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
            "Show current chart",
            "Confirm setup, then press Current.",
            "This gives you a stable baseline before searching.",
        )
    if candidate_count <= 0:
        if has_rejections:
            return (
                "Loosen blocked filters",
                "Open Search or relax the tightest blocker.",
                "The current chart stays visible while you tune the search.",
            )
        return (
            "Find candidate windows",
            "Press Find Best to scan the selected range.",
            "Candidates will appear on the right board for explicit selection.",
        )
    if selected_index < 0 or displayed_source == "input chart":
        return (
            "Pick a candidate",
            f"{candidate_count} candidate{'s' if candidate_count != 1 else ''} ready. Click one to draw it.",
            "Double-click a card when you want to use that exact time.",
        )
    return (
        f"Decide on window #{selected_index + 1}",
        "Review Analysis/Timeline, then shortlist or use it.",
        "Shortlisted windows become easier to compare and export.",
    )


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


bind_actions_globals(globals())
bind_navigation_globals(globals())
bind_pages_globals(globals())
bind_workspace_globals(globals())
bind_left_rail_globals(globals())
bind_right_panel_globals(globals())
bind_wheel_globals(globals())


class ElectionalDesktopApp(DesktopNavigationMixin, DesktopActionsMixin, DesktopWorkspaceMixin, DesktopPagesMixin, DesktopLeftRailMixin, DesktopRightPanelMixin, DesktopWheelMixin):
    """Tkinter desktop UI that talks directly to the Python electional engine."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"Electional Software - {APP_BUILD_LABEL}")
        self.root.geometry("1920x1080")
        self.root.minsize(1280, 800)
        self.render_quality = configure_tk_render_quality(self.root)

        self.user_locations = load_user_locations()
        self.recent_locations = load_recent_locations()
        self.hidden_builtin_location_ids = load_hidden_builtin_location_ids()
        self.home_location_name = load_home_location_name()
        self.location_names = combined_visible_location_names([*self.recent_locations, *self.user_locations], self.hidden_builtin_location_ids)
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
        self.left_section_toggle_vars: dict[str, tk.StringVar] = {}
        self.left_section_bodies: dict[str, tk.Frame] = {}
        self.shortlist_board_cards: list[tk.Frame] = []
        self.focused_body_name: str | None = None
        self.focused_body_kind: str | None = None
        self.focused_aspect_bodies: set[str] = set()
        self.analysis_report_text_cache = ""
        self.timeline_report_text_cache = ""
        self.search_workbench_run_count = 0
        self.search_workbench_last_action = "waiting"
        self.background_job_active = False
        self.background_job_name = ""
        self.background_job_token: object | None = None
        self.location_search_results: list[LocationSearchResult] = []
        self.location_search_result_labels: dict[str, LocationSearchResult] = {}
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
        self.show_tools_var = tk.BooleanVar(value=False)
        self.compact_wheel_var = tk.BooleanVar(value=bool(display_options.get("compact_wheel", False)))
        self.point_set_var = tk.StringVar(value=get_point_set(display_options.get("point_set")).name)
        self.page_mode_var = tk.StringVar(value=PAGE_MODE_LABELS.get(str(display_options.get("page_mode") or "guide"), "Guide"))
        self.view_page_action_var = tk.StringVar(value="Interpretation")
        self.active_detail_var = tk.StringVar(value="Active detail: Window")
        self.right_panel_theme_var = tk.StringVar(value=RIGHT_PANEL_THEME_LABELS.get(str(display_options.get("right_panel_theme") or "classic-natal"), "Classic Natal"))
        self.wheel_view_preset_var = tk.StringVar(value=WHEEL_VIEW_PRESET_LABELS.get(str(display_options.get("wheel_view_preset") or "full-classic"), "Full Classic"))
        self.wheel_zoom = float(display_options.get("wheel_zoom", WHEEL_DEFAULT_ZOOM))
        self.wheel_export_scale = wheel_export_scale_value(display_options.get("wheel_export_scale", WHEEL_EXPORT_SCALE_DEFAULT))
        self.wheel_export_quality_var = tk.StringVar(value=wheel_export_scale_label(self.wheel_export_scale))
        self.live_sky_date_var = tk.StringVar(value=str(self.session_state.get("date") or date.today().isoformat()))
        self.live_sky_time_var = tk.StringVar(value=str(self.session_state.get("time") or "09:00"))
        self.live_sky_mode_var = tk.StringVar(value="Manual")
        self.live_sky_status_var = tk.StringVar(value="Live Sky waiting for chart data.")
        self.live_sky_info_var = tk.StringVar(value="")
        self.live_sky_snapshot: dict[str, object] | None = None

        self._configure_style()
        self._build_layout()
        self._apply_current_theme()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind("<Alt-Left>", lambda _event: self._select_relative_window(-1))
        self.root.bind("<Alt-Right>", lambda _event: self._select_relative_window(1))
        self.root.bind("<F11>", lambda _event: self._toggle_focus_mode())
        self.calculate(show_input_chart=True)
        initial_page_mode = self._current_page_mode_id()
        self._apply_page_mode(initial_page_mode, save=False)
        if initial_page_mode == "wheel":
            self._open_guided_workflow_page()

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

        self.center_pane = tk.Frame(self.workspace_panes, bg=PALETTE["panel"], padx=0, pady=0, width=CENTER_PANE_DEFAULT_WIDTH)
        self._build_center_scroll_area()
        self.center_panel.columnconfigure(0, weight=1)
        self.center_panel.rowconfigure(3, weight=0, minsize=0)
        self.center_panel.rowconfigure(4, weight=1, minsize=CENTER_WORKSPACE_MIN_HEIGHT)
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































































































































































































    def _run_background_job(
        self,
        name: str,
        worker: Callable[[], object],
        on_success: Callable[[object], None],
        *,
        error_title: str = "Background job failed",
        error_context: str = "Desktop background job failed",
    ) -> bool:
        if self.background_job_active:
            active = self.background_job_name or "another task"
            self.status_var.set(f"{active} is still running. Please wait for it to finish before starting {name}.")
            return False
        token = object()
        self.background_job_active = True
        self.background_job_name = name
        self.background_job_token = token
        self.status_var.set(f"{name} running in background...")
        self._log_event(f"Background job started: {name}")

        def run() -> None:
            try:
                result = worker()
            except Exception as exc:  # pragma: no cover - desktop resilience path.
                debug_path = record_desktop_exception(error_context)
                error_text = str(exc)

                def fail() -> None:
                    if self.background_job_token is not token:
                        return
                    self.background_job_active = False
                    self.background_job_name = ""
                    self.background_job_token = None
                    detail = f"\n\nDebug trace: {debug_path}" if debug_path else ""
                    self.status_var.set(f"{name} failed: {error_text}")
                    self._log_event(f"Background job failed: {name}: {error_text}")
                    messagebox.showerror(error_title, f"{error_text}{detail}")

                self.root.after(0, fail)
                return

            def finish() -> None:
                if self.background_job_token is not token:
                    return
                self.background_job_active = False
                self.background_job_name = ""
                self.background_job_token = None
                on_success(result)
                self._log_event(f"Background job finished: {name}")

            self.root.after(0, finish)

        threading.Thread(target=run, name=name.lower().replace(" ", "-"), daemon=True).start()
        return True

    def _prepare_calculation_inputs(self) -> dict[str, object] | None:
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
            return None
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
            return None

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
            target_aspect_text=self.target_aspect_var.get(),
            target_aspect_body_text=self.target_aspect_body_var.get(),
            target_planet_text=self.target_planet_var.get(),
            target_sign_text=self.target_sign_var.get(),
            target_house_text=self.target_house_var.get(),
        )
        self._update_search_summary()
        return {
            "date_text": self.date_var.get(),
            "time_text": normalized_time,
            "location": location,
            "preset": preset,
            "selected_aspects": selected_aspects,
            "zodiac_system": zodiac_system,
            "house_system": house_system,
            "search_config": search_config,
            "objective": self.objective_var.get(),
            "election_strategy": self.election_strategy_var.get(),
            "aspect_definitions": aspect_definitions,
            "aspect_profile_name": self.active_aspect_profile.name,
        }

    def _build_report_from_prepared(self, prepared: Mapping[str, object]) -> dict[str, object]:
        return build_election_report(
            str(prepared["date_text"]),
            str(prepared["time_text"]),
            prepared["location"],
            prepared["preset"].id,
            list(prepared["selected_aspects"]),
            prepared["zodiac_system"].id,
            prepared["house_system"].id,
            prepared["search_config"],
            str(prepared["objective"]),
            prepared["aspect_definitions"],
        )

    def _apply_calculation_report(self, report: Mapping[str, object], prepared: Mapping[str, object], *, show_input_chart: bool) -> None:
        snapshot = report["snapshot"]
        windows = report["windows"]
        selected_window = snapshot if show_input_chart else (windows[0] if windows else snapshot)
        selected_index = -1 if selected_window is snapshot else 0
        location = prepared["location"]
        search_config = prepared["search_config"]
        zodiac_system = prepared["zodiac_system"]
        house_system = prepared["house_system"]
        selected_aspects = list(prepared["selected_aspects"])
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
            f"Aspect profile: {prepared.get('aspect_profile_name', self.active_aspect_profile.name)}; active aspects {len(selected_aspects)}.{cache_text}"
        )
        self.current_rejection_summary = dict(report.get("rejectionSummary") or {})
        self.current_searched_window_count = evaluated_count
        self.selected_window = selected_window
        self.selected_window_index = selected_index
        self.displayed_chart_source = "input chart" if show_input_chart or not windows else "selected candidate"
        self.current_aspect_highlights = self._build_displayed_aspect_highlights(selected_window, location)

        self.title_var.set(f"{prepared['objective']} election timing")
        self.natal_summary.configure(text=f"Score {selected_window['score']} | {score_band_label(int(selected_window['score']))}")
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

    def calculate(self, *, show_input_chart: bool = False) -> None:
        prepared = self._prepare_calculation_inputs()
        if prepared is None:
            return
        try:
            report = self._build_report_from_prepared(prepared)
        except Exception as exc:  # pragma: no cover - exercised manually through the desktop UI.
            debug_path = record_desktop_exception("Electional calculation failed")
            self._log_event(f"Calculation failed: {exc}")
            detail = f"\n\nDebug trace: {debug_path}" if debug_path else ""
            messagebox.showerror("Electional calculation failed", f"{exc}{detail}")
            return
        self._apply_calculation_report(report, prepared, show_input_chart=show_input_chart)

    def calculate_in_background(
        self,
        *,
        show_input_chart: bool = False,
        job_name: str = "Electional calculation",
        on_complete: Callable[[], None] | None = None,
    ) -> bool:
        prepared = self._prepare_calculation_inputs()
        if prepared is None:
            return False

        def worker() -> object:
            return self._build_report_from_prepared(prepared)

        def finish(result: object) -> None:
            self._apply_calculation_report(result, prepared, show_input_chart=show_input_chart)
            if on_complete is not None:
                on_complete()

        return self._run_background_job(
            job_name,
            worker,
            finish,
            error_title="Electional calculation failed",
            error_context="Electional background calculation failed",
        )
















    def _use_selected_window_time(self) -> None:
        if not self.selected_window or not self.current_location:
            return
        local = self.selected_window["date"].astimezone(ZoneInfo(self.current_location.timezone))
        self.date_var.set(local.strftime("%Y-%m-%d"))
        self.time_var.set(local.strftime("%H:%M"))
        self._log_event(f"Applied selected window to input time: {self.date_var.get()} {self.time_var.get()}")
        self.calculate(show_input_chart=True)
































































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
            "target_aspect": self.target_aspect_var.get(),
            "target_aspect_body": self.target_aspect_body_var.get(),
            "target_planet": self.target_planet_var.get(),
            "target_sign": self.target_sign_var.get(),
            "target_house": self.target_house_var.get(),
            "exact_search_query": self.exact_search_query_var.get(),
            "avoid_major_stress": self.avoid_major_stress_var.get(),
            "require_applying_support": self.require_applying_support_var.get(),
            "require_angular_benefic": self.require_angular_benefic_var.get(),
            "avoid_angular_malefics": self.avoid_angular_malefics_var.get(),
            "require_moon_non_void": self.require_moon_non_void_var.get(),
            "avoid_objective_antipatterns": self.avoid_objective_antipatterns_var.get(),
            "manual_validation_comparison": self.manual_validation_result,
            "scrub_preview": {
                "offsetMinutes": int(self.time_scrub_minutes_var.get()) if hasattr(self, "time_scrub_minutes_var") else 0,
                "active": bool(hasattr(self, "time_scrub_minutes_var") and int(self.time_scrub_minutes_var.get()) != 0),
                "baseDate": str(getattr(self, "time_scrub_base_date", "") or ""),
                "baseTime": str(getattr(self, "time_scrub_base_time", "") or ""),
            },
            "display_options": {
                "show_aspects": self.show_aspects_var.get(),
                "show_lots": self.show_lots_var.get(),
                "show_nodes": self.show_nodes_var.get(),
                "show_fixed_stars": self.show_fixed_stars_var.get(),
                "show_score_overlay": self.show_score_overlay_var.get(),
                "show_tools": self.show_tools_var.get(),
                "compact_wheel": self.compact_wheel_var.get(),
                "wheel_zoom": self.wheel_zoom,
                "wheel_export_scale": self.wheel_export_scale,
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
    dpi_mode = enable_process_dpi_awareness()
    root = tk.Tk()
    app = ElectionalDesktopApp(root)
    app._log_event(f"Render quality: {dpi_mode}; {app.render_quality['summary']}.")
    root.mainloop()


if __name__ == "__main__":
    main()


