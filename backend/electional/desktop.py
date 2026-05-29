"""Native desktop application shell for Electional Software."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .calendar_export import calendar_from_entries
from .chart import build_election_report, clear_snapshot_cache, format_angle, format_position, snapshot_cache_info
from .locations import (
    DEFAULT_TIMEZONE,
    LOCATION_PRESETS,
    LocationPreset,
    build_custom_location,
    combined_location_names,
    default_location_for_timezone,
    home_location_for_app,
    get_location,
    load_home_location_name,
    load_user_locations,
    save_home_location_name,
    save_user_locations,
    resolve_location_by_name,
    upsert_user_location,
)
from .point_sets import POINT_SET_NAMES, PointSet, get_point_set, visible_lots_for_point_set, visible_planets_for_point_set
from .presets import ELECTIONAL_PRESETS
from .references import dignity_table_lines, lot_reference_lines, system_reference_lines
from .reporting import (
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
    update_shortlist_tags,
)
from .systems import DEFAULT_HOUSE_SYSTEM_ID, DEFAULT_ZODIAC_SYSTEM_ID, HOUSE_SYSTEMS, ZODIAC_SYSTEMS, get_house_system, get_zodiac_system
from .time_utils import normalize_time_text
from .validation import validate_election_inputs, validate_search_inputs

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

SIGN_LABELS = ("Ar", "Ta", "Ge", "Ca", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi")
ZODIAC_SYSTEM_NAMES = tuple(system.name for system in ZODIAC_SYSTEMS)
HOUSE_SYSTEM_NAMES = tuple(system.name for system in HOUSE_SYSTEMS)
PAGE_MODE_LABELS = {
    "wheel": "Wheel",
    "wheel-aspectarian": "Wheel + Aspectarian",
    "classical-point-data": "Classical Point Data",
    "medieval-data": "Medieval Data",
    "transit-search": "Transit Search",
}
PAGE_MODE_NAMES = tuple(PAGE_MODE_LABELS.values())
PAGE_MODE_IDS_BY_NAME = {name: mode_id for mode_id, name in PAGE_MODE_LABELS.items()}
HOME_LOCATION_DEFAULT_LABEL = "Local timezone default"
DETAIL_PAGE_TABS = (
    "Summary",
    "Window",
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
    "Planets",
    "Aspects",
    "Aspectarian",
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
    "Advisor": "Advisor",
    "Improve": "Improve",
    "Decision": "Decision",
    "Compare": "Compare",
    "Search": "Search",
    "Factors": "Factor Explorer",
}
TOP_NAV_SPECIAL_ACTIONS = {"Settings", "Map"}
TOP_NAV_ITEMS = ("Wheel", "Advisor", "Improve", "Decision", "Compare", "Search", "Factors", "Settings", "Map")
RIBBON_PAGE_TARGETS = {
    "Search Page": "Search",
    "Advisor": "Advisor",
    "Improve": "Improve",
    "Decision": "Decision",
    "Compare": "Compare",
    "Factors": "Factor Explorer",
    "Diagnostics": "Diagnostics",
    "Declination": "Declination",
    "Button Health": "Button Health",
}
RIBBON_SPECIAL_ACTIONS = {
    "New Chart",
    "Save",
    "Save Report",
    "Copy",
    "Report",
    "Wheel",
    "Export Wheel",
    "Calendar",
    "Ask",
    "Calculate",
    "Transits",
    "Electional Search",
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
    "Advisor": "Advisor",
    "Improve": "Improve",
    "Decision": "Decision",
    "Compare": "Compare",
    "Search": "Search",
    "Timing": "Timing",
    "Angles": "Angles",
    "Aspects": "Aspects",
    "Aspectarian": "Aspectarian",
    "Point Data": "Point Data",
    "Medieval": "Medieval",
    "Conditions": "Conditions",
    "Shortlist": "Shortlist",
    "Log": "Log",
}
VIEW_PAGE_SPECIAL_ACTIONS = {"Chart Data", "Save Wheel"}
RIBBON_GROUPS = (
    ("Chart", ("New Chart", "Calculate", "Save Report", "Copy", "Report", "Export Wheel", "Calendar", "Shortlist")),
    ("Navigate", ("Advisor", "Improve", "Decision", "Compare", "Factors", "Search Page", "Focus Wheel", "Ask")),
    ("Tools", ("Chart Data", "Diagnostics", "Declination", "Button Health", "Score Audit", "Factor Map", "Cache Stats", "Health", "Void Course", "Clear Cache", "Preferences")),
    ("References", ("Systems", "Bounds", "Lots", "Fixed Stars", "Heliacal Search", "Map")),
)
RIBBON_COLUMNS = 4

PALETTE = {
    "app_bg": "#e8eef3",
    "title_bar": "#101821",
    "top_bar": "#172b3a",
    "top_bar_dark": "#0d1720",
    "top_nav": "#172b3a",
    "top_nav_hover": "#203b4d",
    "top_nav_active": "#0d7b7a",
    "ribbon": "#eef4f5",
    "ribbon_panel": "#ffffff",
    "ribbon_panel_soft": "#f8fbfb",
    "panel": "#eef3f6",
    "panel_alt": "#ffffff",
    "panel_line": "#d5dee6",
    "panel_line_strong": "#b9c7d2",
    "canvas": "#f3f6f8",
    "canvas_grid": "#e9eef2",
    "chart_disc": "#eef4f2",
    "chart_inner": "#fffefa",
    "chart_line": "#425363",
    "chart_line_soft": "#8b99a4",
    "chart_bezel": "#263949",
    "chart_bezel_inner": "#c9d4dc",
    "chart_house_fill": "#fbf8ef",
    "chart_house_fill_alt": "#f0f7f4",
    "chart_ring_fill": "#fdfbf6",
    "chart_tick_major": "#33485a",
    "chart_tick_medium": "#768796",
    "chart_tick_minor": "#bec9d2",
    "text": "#142230",
    "muted": "#607587",
    "accent": "#0d7b7a",
    "accent_dark": "#0d4f63",
    "score": "#0b6076",
    "support": "#1a8d62",
    "stress": "#c05368",
    "warning": "#9d641d",
    "button": "#f9fbfb",
    "button_hover": "#eaf4f3",
    "button_line": "#d8e3e8",
    "button_active": "#dff0ee",
    "selected": "#d7ede9",
    "metric_bg": "#e7f5f3",
    "center_hub": "#ffffff",
    "chip": "#eef4fa",
    "chip_line": "#c2d4e0",
    "surface_shadow": "#d8e1e8",
    "sign_badge_fill": "#fffdf7",
    "sign_badge_line": "#c9b995",
    "planet_fill": "#fffdf6",
    "planet_fill_angular": "#eef8f7",
    "lot_fill": "#f7ead1",
    "node_fill": "#e8f5f7",
    "star_fill": "#f5fbff",
    "aspect_ring": "#aab5b0",
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


def planet_abbreviation(name: str) -> str:
    """Return a compact planet label suitable for the chart wheel."""

    return PLANET_LABELS.get(name, name[:2].title())


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


def midpoint_longitude(start: float, end: float) -> float:
    return (start + ((end - start) % 360) / 2) % 360


def button_health_lines(available_pages: tuple[str, ...] | list[str] | None = None) -> list[str]:
    pages = set(available_pages or DETAIL_PAGE_TABS)
    ribbon_labels = [label for _group, labels in RIBBON_GROUPS for label in labels]
    missing_top_actions = [label for label in TOP_NAV_ITEMS if label not in TOP_NAV_PAGE_TARGETS and label not in TOP_NAV_SPECIAL_ACTIONS]
    missing_ribbon_actions = [label for label in ribbon_labels if label not in RIBBON_PAGE_TARGETS and label not in RIBBON_SPECIAL_ACTIONS]
    missing_view_actions = [label for label in VIEW_PAGE_TARGETS if label not in VIEW_PAGE_TARGETS and label not in VIEW_PAGE_SPECIAL_ACTIONS]
    missing_top_pages = [target for target in TOP_NAV_PAGE_TARGETS.values() if target not in pages]
    missing_ribbon_pages = [target for target in RIBBON_PAGE_TARGETS.values() if target not in pages]
    missing_view_pages = [target for target in VIEW_PAGE_TARGETS.values() if target not in pages]
    problems = missing_top_actions + missing_ribbon_actions + missing_view_actions + missing_top_pages + missing_ribbon_pages + missing_view_pages

    lines = [
        "Button Health",
        f"Top nav buttons: {len(TOP_NAV_ITEMS)}",
        f"Ribbon buttons: {len(ribbon_labels)}",
        f"View page shortcuts: {len(VIEW_PAGE_TARGETS) + len(VIEW_PAGE_SPECIAL_ACTIONS)}",
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


class ElectionalDesktopApp:
    """Tkinter desktop UI that talks directly to the Python electional engine."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Electional Software")
        self.root.geometry("1440x900")
        self.root.minsize(1020, 700)

        self.user_locations = load_user_locations()
        self.home_location_name = load_home_location_name()
        self.location_names = combined_location_names(self.user_locations)
        self.locations_by_name = self._location_map()
        self.presets_by_name = {preset.name: preset for preset in ELECTIONAL_PRESETS}
        self.aspect_vars: dict[str, tk.BooleanVar] = {}
        self.current_location: LocationPreset | None = None
        self.input_snapshot: dict[str, object] | None = None
        self.current_windows: list[dict[str, object]] = []
        self.current_search_summary = ""
        self.current_rejection_summary: dict[str, object] = {}
        self.current_searched_window_count = 0
        self.selected_window: dict[str, object] | None = None
        self.selected_window_index = 0
        self.window_cards: list[tk.Frame] = []
        self.shortlist = load_shortlist()
        self.shortlist_compare_a_id: str | None = self.shortlist[0]["id"] if self.shortlist else None
        self.shortlist_compare_b_id: str | None = self.shortlist[1]["id"] if len(self.shortlist) > 1 else None
        self._resize_job: str | None = None
        self.focus_mode = False
        self.event_log: list[str] = []
        self.session_state = clean_session_state(load_session_state())
        self.metric_vars: dict[str, tk.StringVar] = {}
        self.shortlist_board_cards: list[tk.Frame] = []
        self.focused_body_name: str | None = None
        self.focused_body_kind: str | None = None
        self.top_nav_buttons: dict[str, tk.Button] = {}
        self.active_top_nav_label: str | None = None
        display_options = self.session_state.get("display_options", {})
        self.show_aspects_var = tk.BooleanVar(value=bool(display_options.get("show_aspects", True)))
        self.show_lots_var = tk.BooleanVar(value=bool(display_options.get("show_lots", True)))
        self.show_nodes_var = tk.BooleanVar(value=bool(display_options.get("show_nodes", True)))
        self.show_fixed_stars_var = tk.BooleanVar(value=bool(display_options.get("show_fixed_stars", True)))
        self.compact_wheel_var = tk.BooleanVar(value=bool(display_options.get("compact_wheel", False)))
        self.point_set_var = tk.StringVar(value=get_point_set(display_options.get("point_set")).name)
        self.page_mode_var = tk.StringVar(value=PAGE_MODE_LABELS.get(str(display_options.get("page_mode") or "wheel"), "Wheel"))
        self.wheel_zoom = float(display_options.get("wheel_zoom", 0.88))

        self._configure_style()
        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind("<Alt-Left>", lambda _event: self._select_relative_window(-1))
        self.root.bind("<Alt-Right>", lambda _event: self._select_relative_window(1))
        self.root.bind("<F11>", lambda _event: self._toggle_focus_mode())
        self.calculate()
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
        style.configure("Panel.TLabelframe.Label", background=PALETTE["panel_alt"], foreground=PALETTE["accent_dark"], font=("Segoe UI Semibold", 10))
        style.configure("Ribbon.TLabelframe", background=PALETTE["ribbon_panel"], bordercolor=PALETTE["panel_line"], relief="flat")
        style.configure("Ribbon.TLabelframe.Label", background=PALETTE["ribbon_panel"], foreground=PALETTE["muted"], font=("Segoe UI Semibold", 8))
        style.configure("TNotebook", background=PALETTE["panel"], borderwidth=0)
        style.configure("TNotebook.Tab", background="#dde7ec", foreground=PALETTE["muted"], padding=(15, 8), font=("Segoe UI Semibold", 9))
        style.map("TNotebook.Tab", background=[("selected", PALETTE["panel_alt"]), ("active", "#edf5f7")], foreground=[("selected", PALETTE["accent_dark"]), ("active", PALETTE["text"])])
        style.configure("Title.TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI Semibold", 21))
        style.configure("Small.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
        style.configure("Accent.TLabel", background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Segoe UI Semibold", 9))
        style.configure("Score.TLabel", background=PALETTE["panel_alt"], foreground=PALETTE["score"], font=("Segoe UI Semibold", 32))
        style.configure("TButton", background=PALETTE["button"], foreground=PALETTE["text"], padding=(13, 8), bordercolor=PALETTE["button_line"], lightcolor=PALETTE["button"], darkcolor=PALETTE["button_line"], focusthickness=1, focuscolor=PALETTE["accent"])
        style.configure("Compact.TButton", background=PALETTE["button"], foreground=PALETTE["text"], padding=(8, 6), bordercolor=PALETTE["button_line"], lightcolor=PALETTE["button"], darkcolor=PALETTE["button_line"], focusthickness=1, focuscolor=PALETTE["accent"])
        style.map("TButton", background=[("pressed", PALETTE["button_active"]), ("active", PALETTE["button_hover"])], bordercolor=[("active", PALETTE["accent"])])
        style.map("Compact.TButton", background=[("pressed", PALETTE["button_active"]), ("active", PALETTE["button_hover"])], bordercolor=[("active", PALETTE["accent"])])
        style.configure("TCheckbutton", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
        style.configure("TCombobox", fieldbackground=PALETTE["panel_alt"], background=PALETTE["ribbon_panel"], foreground=PALETTE["text"], arrowsize=14, bordercolor=PALETTE["panel_line"])

    def _location_map(self) -> dict[str, LocationPreset]:
        locations = {location.name: location for location in LOCATION_PRESETS}
        locations.update({location.name: location for location in self.user_locations})
        return locations

    def _refresh_location_choices(self) -> None:
        self.location_names = combined_location_names(self.user_locations)
        self.locations_by_name = self._location_map()
        if hasattr(self, "location_combo"):
            self.location_combo.configure(values=self.location_names)
        self._refresh_location_status()

    def _refresh_location_status(self) -> None:
        if not hasattr(self, "location_status_var"):
            return
        count_text = f"{len(self.user_locations)} custom saved location{'s' if len(self.user_locations) != 1 else ''}."
        home_text = f" Home: {self.home_location_name}." if self.home_location_name else " Home: local timezone default."
        self.location_status_var.set(count_text + home_text)

    def _build_layout(self) -> None:
        self._build_top_bars()

        self.shell = tk.Frame(self.root, bg=PALETTE["app_bg"], padx=10, pady=10)
        self.shell.pack(fill=tk.BOTH, expand=True)

        self.workspace_panes = tk.PanedWindow(
            self.shell,
            orient=tk.HORIZONTAL,
            bg=PALETTE["app_bg"],
            bd=0,
            sashwidth=8,
            sashrelief=tk.FLAT,
            showhandle=True,
            handlesize=18,
            handlepad=48,
        )
        self.workspace_panes.pack(fill=tk.BOTH, expand=True)

        self.left_panel = tk.Frame(self.workspace_panes, bg=PALETTE["panel"], padx=8, pady=8, width=315)
        self.left_panel.pack_propagate(False)
        self._build_left_scroll_area()
        self._build_left_controls()

        self.center_pane = tk.Frame(self.workspace_panes, bg=PALETTE["panel"], padx=0, pady=0, width=720)
        self._build_center_scroll_area()
        self.center_panel.columnconfigure(0, weight=1)
        self.center_panel.rowconfigure(3, weight=1, minsize=260)
        self._build_chart_panel()

        self.right_panel = tk.Frame(self.workspace_panes, bg=PALETTE["panel"], padx=8, pady=8, width=380)
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
        tk.Label(brand, text="Judgment engine and timing workbench", bg=PALETTE["title_bar"], fg="#90a6b8", font=("Segoe UI", 8)).pack(anchor="w")
        tk.Label(
            title_bar,
            text="Python desktop engine",
            bg=PALETTE["title_bar"],
            fg="#b9c5d2",
            font=("Segoe UI Semibold", 9),
        ).pack(side=tk.RIGHT, padx=18, pady=15)

        menu = ttk.Frame(self.root, style="Top.TFrame", padding=(14, 6))
        menu.pack(fill=tk.X)
        for item in TOP_NAV_ITEMS:
            button = self._top_nav_button(menu, item)
            self.top_nav_buttons[item] = button
            button.pack(side=tk.LEFT, padx=(0, 5))

        ribbon = tk.Frame(self.root, bg=PALETTE["ribbon"], padx=12, pady=9)
        ribbon.pack(fill=tk.X)
        for group_title, items in RIBBON_GROUPS:
            self._ribbon_group(ribbon, group_title, items).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

    def _top_nav_button(self, parent: tk.Widget, label: str) -> tk.Button:
        button = tk.Button(
            parent,
            text=label,
            command=lambda: self._run_top_nav_action(label),
            bg=PALETTE["top_nav"],
            fg="#eaf4f1",
            activebackground=PALETTE["top_nav_active"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            bd=0,
            padx=13,
            pady=5,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
        )
        button.bind("<Enter>", lambda _event: self._set_top_nav_hover(label, True))
        button.bind("<Leave>", lambda _event: self._set_top_nav_hover(label, False))
        return button

    def _set_top_nav_hover(self, label: str, active: bool) -> None:
        button = self.top_nav_buttons.get(label)
        if not button:
            return
        if label == self.active_top_nav_label:
            button.configure(bg=PALETTE["top_nav_active"], fg="#ffffff")
        else:
            button.configure(bg=PALETTE["top_nav_hover"] if active else PALETTE["top_nav"], fg="#eaf4f1")

    def _sync_top_nav_selection(self, page_title: str) -> None:
        selected = next((label for label, target in TOP_NAV_PAGE_TARGETS.items() if target == page_title), None)
        if selected is None:
            return
        self.active_top_nav_label = selected
        for label, button in self.top_nav_buttons.items():
            if label == selected:
                button.configure(bg=PALETTE["top_nav_active"], fg="#ffffff")
            else:
                button.configure(bg=PALETTE["top_nav"], fg="#eaf4f1")

    def _ribbon_group(self, parent: tk.Widget, title: str, items: tuple[str, ...]) -> tk.Frame:
        group = tk.Frame(
            parent,
            bg=PALETTE["ribbon_panel"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=9,
            pady=8,
        )
        tk.Frame(group, bg=PALETTE["accent"], height=2).pack(fill=tk.X, pady=(0, 7))
        tk.Label(
            group,
            text=title.upper(),
            bg=PALETTE["ribbon_panel"],
            fg=PALETTE["accent_dark"],
            font=("Segoe UI Semibold", 8),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 7))
        grid = tk.Frame(group, bg=PALETTE["ribbon_panel"])
        grid.pack(fill=tk.X)
        for column in range(RIBBON_COLUMNS):
            grid.columnconfigure(column, weight=1, uniform=f"ribbon-{title}")
        for index, item in enumerate(items):
            row = index // RIBBON_COLUMNS
            column = index % RIBBON_COLUMNS
            self._ribbon_button(grid, item).grid(row=row, column=column, sticky="nsew", padx=(0, 5), pady=(0, 5))
        return group

    def _ribbon_button(self, parent: tk.Widget, label: str) -> tk.Frame:
        descriptions = {
            "New Chart": "Reset",
            "Save": "Report",
            "Save Report": "File",
            "Copy": "Report",
            "Report": "View",
            "Wheel": "Export",
            "Export Wheel": "Image",
            "Calendar": ".ics",
            "Ask": "Help",
            "Calculate": "Run",
            "Search Page": "Open",
            "Shortlist": "Pick",
            "Advisor": "Next",
            "Improve": "Tune",
            "Decision": "Brief",
            "Compare": "Diff",
            "Factors": "Why",
            "Chart Data": "Inspect",
            "Diagnostics": "Signals",
            "Declination": "Parallels",
            "Button Health": "Wiring",
            "Score Audit": "Points",
            "Factor Map": "Layers",
            "Cache Stats": "Speed",
            "Clear Cache": "Reset",
            "Health": "Engine",
            "Focus Wheel": "F11",
            "Void Course": "Moon",
            "Preferences": "Setup",
            "Systems": "Zodiac",
            "Bounds": "Dignity",
            "Lots": "Parts",
            "Fixed Stars": "Stars",
            "Heliacal Search": "Visibility",
            "Map": "Angles",
        }
        title = {
            "New Chart": "New",
            "Save Report": "Save",
            "Copy": "Copy",
            "Report": "Report",
            "Wheel": "Wheel",
            "Export Wheel": "Export",
            "Calculate": "Calc",
            "Search Page": "Search",
            "Advisor": "Advisor",
            "Improve": "Improve",
            "Decision": "Decision",
            "Compare": "Compare",
            "Factors": "Factors",
            "Chart Data": "Data",
            "Diagnostics": "Diag",
            "Declination": "Decl",
            "Button Health": "Buttons",
            "Score Audit": "Audit",
            "Factor Map": "Factors",
            "Cache Stats": "Cache",
            "Clear Cache": "Clear",
            "Focus Wheel": "Focus",
            "Void Course": "VOC",
            "Fixed Stars": "Stars",
            "Heliacal Search": "Heliacal",
            "Map": "Map",
        }.get(label, label)
        button = tk.Frame(
            parent,
            bg=PALETTE["button"],
            highlightbackground=PALETTE["button_line"],
            highlightthickness=1,
            width=68,
            height=48,
        )
        button.pack_propagate(False)
        tk.Frame(button, bg=PALETTE["accent"], height=2).pack(fill=tk.X, pady=(0, 5))
        tk.Label(
            button,
            text=title,
            bg=PALETTE["button"],
            fg=PALETTE["text"],
            font=("Segoe UI Semibold", 8),
            justify=tk.CENTER,
            wraplength=60,
        ).pack(fill=tk.X)
        tk.Label(
            button,
            text=descriptions.get(label, "Open"),
            bg=PALETTE["button"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 7),
            justify=tk.CENTER,
        ).pack(fill=tk.X, pady=(1, 0))
        self._bind_clickable(button, lambda: self._run_ribbon_action(label))
        return button

    def _run_top_nav_action(self, label: str) -> None:
        actions = {
            "Wheel": lambda: (self._scroll_center_to_top(), self._focus_detail_page("Window")),
            "Chart": lambda: (self._scroll_center_to_top(), self._focus_detail_page("Window")),
            "Advisor": lambda: self._focus_detail_page("Advisor"),
            "Improve": lambda: self._focus_detail_page("Improve"),
            "Decision": lambda: self._focus_detail_page("Decision"),
            "Selected Chart": lambda: self._focus_detail_page("Decision"),
            "Compare": lambda: self._focus_detail_page("Compare"),
            "Search": lambda: self._focus_detail_page("Search"),
            "Factors": lambda: self._focus_detail_page("Factor Explorer"),
            "Settings": self._show_preferences_dialog,
            "Configuration": self._show_preferences_dialog,
            "Map": self._show_astro_mapping_dialog,
            "Astro Mapping": self._show_astro_mapping_dialog,
        }
        actions.get(label, lambda: self._show_unknown_action(label))()

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
            tk.Label(chip, text=text, bg=PALETTE["chip"], fg=PALETTE["top_bar_dark"], font=("Segoe UI", 8, "bold")).pack()

    def _run_ribbon_action(self, label: str) -> None:
        actions = {
            "New Chart": self._new_chart,
            "Save": self._save_current_report,
            "Save Report": self._save_current_report,
            "Copy": self._copy_current_report,
            "Report": self._show_current_report_dialog,
            "Wheel": self._save_chart_wheel,
            "Export Wheel": self._save_chart_wheel,
            "Calendar": self._save_selected_calendar_event,
            "Ask": self._show_quick_help,
            "Calculate": self.calculate,
            "Transits": self.calculate,
            "Electional Search": self.calculate,
            "Search Page": lambda: self._focus_detail_page("Search"),
            "Shortlist": self._add_selected_to_shortlist,
            "Advisor": lambda: self._focus_detail_page("Advisor"),
            "Improve": lambda: self._focus_detail_page("Improve"),
            "Decision": lambda: self._focus_detail_page("Decision"),
            "Compare": lambda: self._focus_detail_page("Compare"),
            "Factors": lambda: self._focus_detail_page("Factor Explorer"),
            "Chart Data": self._show_chart_inspector,
            "Diagnostics": lambda: self._focus_detail_page("Diagnostics"),
            "Declination": lambda: self._focus_detail_page("Declination"),
            "Button Health": self._show_button_health,
            "Score Audit": self._show_score_audit_dialog,
            "Factor Map": self._show_factor_map_dialog,
            "Cache Stats": self._show_cache_stats_dialog,
            "Clear Cache": self._clear_search_cache,
            "Health": self._show_calculation_health_dialog,
            "Focus Wheel": self._toggle_focus_mode,
            "Void Course": self._show_void_course_dialog,
            "Preferences": self._show_preferences_dialog,
            "Systems": self._show_systems_dialog,
            "Bounds": self._show_bounds_dialog,
            "Lots": self._show_lots_reference_dialog,
            "Fixed Stars": self._show_fixed_stars_dialog,
            "Heliacal Search": self._show_heliacal_dialog,
            "Map": self._show_astro_mapping_dialog,
        }
        actions.get(label, lambda: self._show_unknown_action(label))()

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
        for var in self.aspect_vars.values():
            var.set(True)
        self.calculate()

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
        preview = report[:3500] + ("\n\n[Report preview truncated]" if len(report) > 3500 else "")
        messagebox.showinfo("Electional report", preview)

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

    def _save_shortlist_tags(self, entry_id: str, tags: list[str]) -> None:
        self.shortlist = update_shortlist_tags(self.shortlist, entry_id, tags)
        save_shortlist(self.shortlist)
        self._refresh_shortlist_text()

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
            tk.Label(empty, text="No shortlisted windows yet.", bg=PALETTE["panel_alt"], fg=PALETTE["muted"], font=("Segoe UI", 10)).pack(anchor="w")
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
        ttk.Button(controls, text="Add Tag", command=lambda entry_id=str(entry.get("id")), var=tag_value: self._add_tag_to_shortlist_entry(entry_id, var.get())).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Set A", command=lambda entry_id=str(entry.get("id")): self._set_shortlist_compare_slot(entry_id, "A")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Set B", command=lambda entry_id=str(entry.get("id")): self._set_shortlist_compare_slot(entry_id, "B")).pack(side=tk.LEFT)

        note = str(entry.get("note", "")).strip()
        if note:
            tk.Label(card, text=note, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 9), wraplength=860, justify="left").pack(anchor="w", pady=(8, 0))

    def _current_report_text(self) -> str:
        report = build_report_text(self.selected_window, self.current_windows, self.current_location)
        if self.input_snapshot and self.selected_window:
            state = (
                "Chart State\n"
                f"Search start: {self.input_snapshot['formattedTime']}\n"
                f"Selected window: {self.selected_window['formattedTime']}\n"
                f"{selection_offset_label(self.input_snapshot, self.selected_window)}\n\n"
            )
            return state + report
        return report

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
        self._dialog_combo_row(workflow, "Home location", home_var, home_choices)

        search = ttk.LabelFrame(body, text="Search Defaults", style="Panel.TLabelframe", padding=10)
        search.pack(fill=tk.X, pady=(10, 0))
        search.columnconfigure(0, weight=1)
        search.columnconfigure(1, weight=1)
        self._dialog_entry_row(search, "Scan hours", scan_var, 0, 0)
        self._dialog_entry_row(search, "Step minutes", step_var, 0, 1)
        self._dialog_entry_row(search, "Minimum score", minimum_var, 1, 0)
        self._dialog_entry_row(search, "Minimum fit", minimum_fit_var, 1, 1)
        self._dialog_entry_row(search, "Minimum confidence", minimum_confidence_var, 2, 0)
        self._dialog_entry_row(search, "Minimum cleanliness", minimum_cleanliness_var, 2, 1)
        self._dialog_entry_row(search, "Maximum volatility", maximum_volatility_var, 3, 0)
        self._dialog_entry_row(search, "Max results", max_results_var, 3, 1)
        ttk.Checkbutton(search, text="Avoid major stress", variable=avoid_major_stress_var).grid(row=4, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        ttk.Checkbutton(search, text="Require applying support", variable=require_applying_support_var).grid(row=4, column=1, sticky="w", padx=(6, 0), pady=(0, 8))
        ttk.Checkbutton(search, text="Require angular benefic", variable=require_angular_benefic_var).grid(row=5, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        ttk.Checkbutton(search, text="Avoid angular malefics", variable=avoid_angular_malefics_var).grid(row=5, column=1, sticky="w", padx=(6, 0), pady=(0, 8))
        ttk.Checkbutton(search, text="Keep Moon non-void", variable=require_moon_non_void_var).grid(row=6, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        ttk.Checkbutton(search, text="Avoid objective anti-patterns", variable=avoid_objective_antipatterns_var).grid(row=6, column=1, sticky="w", padx=(6, 0), pady=(0, 8))

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
                get_point_set("ten-planets").name,
                home_var.get(),
                scan_var.get(),
                step_var.get(),
                minimum_var.get(),
                minimum_fit_var.get(),
                minimum_confidence_var.get(),
                minimum_cleanliness_var.get(),
                maximum_volatility_var.get(),
                max_results_var.get(),
                avoid_major_stress_var.get(),
                require_applying_support_var.get(),
                require_angular_benefic_var.get(),
                avoid_angular_malefics_var.get(),
                require_moon_non_void_var.get(),
                avoid_objective_antipatterns_var.get(),
            ),
        ).pack(side=tk.LEFT)
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
                home_var.get(),
                scan_var.get(),
                step_var.get(),
                minimum_var.get(),
                minimum_fit_var.get(),
                minimum_confidence_var.get(),
                minimum_cleanliness_var.get(),
                maximum_volatility_var.get(),
                max_results_var.get(),
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
        home_location_name: str,
        scan_hours: str,
        step_minutes: str,
        minimum_score: str,
        minimum_fit: str,
        minimum_confidence: str,
        minimum_cleanliness: str,
        maximum_volatility: str,
        max_results: str,
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
        self.avoid_major_stress_var.set(avoid_major_stress)
        self.require_applying_support_var.set(require_applying_support)
        self.require_angular_benefic_var.set(require_angular_benefic)
        self.avoid_angular_malefics_var.set(avoid_angular_malefics)
        self.require_moon_non_void_var.set(require_moon_non_void)
        self.avoid_objective_antipatterns_var.set(avoid_objective_antipatterns)
        self._sync_aspects_to_preset()
        self._update_search_summary()
        self._refresh_location_status()
        self._apply_page_mode(self._current_page_mode_id(), save=False)
        dialog.destroy()
        self.status_var.set("Preferences applied.")
        self.calculate()

    def _selected_aspect_ids(self) -> list[str]:
        return [aspect for aspect, var in self.aspect_vars.items() if var.get()]

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
            f"- Scanned windows: {self.current_searched_window_count}",
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
            *moon_void_course_summary(self.selected_window, self.current_location, self._selected_aspect_ids()),
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
        ttk.Label(card, text="Election Setup", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(6, 4))
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
        self.avoid_major_stress_var = tk.BooleanVar(value=bool(state.get("avoid_major_stress", False)))
        self.require_applying_support_var = tk.BooleanVar(value=bool(state.get("require_applying_support", False)))
        self.require_angular_benefic_var = tk.BooleanVar(value=bool(state.get("require_angular_benefic", False)))
        self.avoid_angular_malefics_var = tk.BooleanVar(value=bool(state.get("avoid_angular_malefics", False)))
        self.require_moon_non_void_var = tk.BooleanVar(value=bool(state.get("require_moon_non_void", False)))
        self.avoid_objective_antipatterns_var = tk.BooleanVar(value=bool(state.get("avoid_objective_antipatterns", False)))
        self.search_summary_var = tk.StringVar(value="")
        self.search_preset_var = tk.StringVar(value="Custom")
        self.validation_var = tk.StringVar(value="Validation: waiting for first calculation")

        control_tabs = ttk.Notebook(parent)
        control_tabs.pack(fill=tk.X, pady=(0, 10))
        setup_tab = ttk.Frame(control_tabs, style="Panel.TFrame", padding=8)
        search_tab = ttk.Frame(control_tabs, style="Panel.TFrame", padding=8)
        focus_tab = ttk.Frame(control_tabs, style="Panel.TFrame", padding=8)
        control_tabs.add(setup_tab, text="Setup")
        control_tabs.add(search_tab, text="Search")
        control_tabs.add(focus_tab, text="Focus")

        timing_box = ttk.LabelFrame(setup_tab, text="Timing", style="Panel.TLabelframe", padding=10)
        timing_box.pack(fill=tk.X, pady=(0, 10))
        self._labeled_entry(timing_box, "Election date", self.date_var)
        self._labeled_entry(timing_box, "Start time", self.time_var)
        self._button_row(
            timing_box,
            (
                ("-2h", lambda: self._shift_time(-2)),
                ("-1h", lambda: self._shift_time(-1)),
                ("Now", self._set_current_time),
                ("+1h", lambda: self._shift_time(1)),
                ("+2h", lambda: self._shift_time(2)),
            ),
            pady=(8, 0),
        )
        self._button_row(
            timing_box,
            (
                ("-15m", lambda: self._shift_time_minutes(-15)),
                ("-5m", lambda: self._shift_time_minutes(-5)),
                ("+5m", lambda: self._shift_time_minutes(5)),
                ("+15m", lambda: self._shift_time_minutes(15)),
            ),
            pady=(6, 0),
        )

        location_box = ttk.LabelFrame(setup_tab, text="Location", style="Panel.TLabelframe", padding=10)
        location_box.pack(fill=tk.X, pady=(0, 10))
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
                ("Save", self._save_location_preset),
                ("Set Home", self._set_home_location),
                ("Home", self._use_home_location),
            ),
            pady=(8, 0),
        )
        self._button_row(
            location_box,
            (
                ("Use Local", self._use_default_location),
                ("Forget", self._forget_location_preset),
            ),
            pady=(6, 0),
        )
        self._refresh_location_status()

        model_box = ttk.LabelFrame(setup_tab, text="Election Model", style="Panel.TLabelframe", padding=10)
        model_box.pack(fill=tk.X, pady=(0, 10))
        self._labeled_combo(model_box, "Objective", self.objective_var, list(OBJECTIVES))
        self._labeled_combo(model_box, "Zodiac system", self.zodiac_system_var, list(ZODIAC_SYSTEM_NAMES))
        self._labeled_combo(model_box, "House system", self.house_system_var, list(HOUSE_SYSTEM_NAMES))
        self.preset_combo = self._labeled_combo(model_box, "Electional model", self.preset_var, [preset.name for preset in ELECTIONAL_PRESETS])
        self.preset_combo.bind("<<ComboboxSelected>>", self._sync_aspects_to_preset)

        search_box = ttk.LabelFrame(search_tab, text="Search Quality", style="Panel.TLabelframe", padding=10)
        search_box.pack(fill=tk.X)
        self._labeled_combo(search_box, "Search preset", self.search_preset_var, list(SEARCH_PRESET_NAMES)).bind("<<ComboboxSelected>>", self._apply_selected_search_preset)
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
        filter_row = ttk.Frame(search_box, style="Panel.TFrame")
        filter_row.pack(fill=tk.X, pady=(6, 0))
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
        preset_filters.pack(fill=tk.X, pady=(6, 0))
        for label in ("Strict Launch", "Clean Negotiation", "Safe Travel", "Conservative Money"):
            ttk.Button(
                preset_filters,
                text=label,
                command=lambda name=label: self._apply_search_filter_preset(name),
            ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            search_box,
            textvariable=self.search_summary_var,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            justify=tk.LEFT,
            wraplength=250,
            font=("Segoe UI", 8),
        ).pack(anchor="w", fill=tk.X, pady=(7, 0))
        self._update_search_summary()

        aspect_box = ttk.LabelFrame(focus_tab, text="Aspect Focus", style="Panel.TLabelframe", padding=10)
        aspect_box.pack(fill=tk.X, pady=(0, 10))
        preset = ELECTIONAL_PRESETS[1]
        session_aspects = state.get("aspects") if isinstance(state.get("aspects"), dict) else {}
        for aspect_id in ("conjunction", "trine", "sextile", "square", "opposition"):
            default_value = bool(session_aspects.get(aspect_id, aspect_id in preset.aspect_ids))
            var = tk.BooleanVar(value=default_value)
            self.aspect_vars[aspect_id] = var
            ttk.Checkbutton(aspect_box, text=aspect_id.title(), variable=var).pack(anchor="w", pady=2)

        tk.Label(
            focus_tab,
            text="Aspect focus controls which contacts are searched and scored. Use the wheel controls above the chart for visual point layers.",
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            justify=tk.LEFT,
            wraplength=250,
            font=("Segoe UI", 8),
        ).pack(anchor="w", fill=tk.X)

        action_box = tk.Frame(parent, bg=PALETTE["panel_alt"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=10, pady=10)
        action_box.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(action_box, text="Calculate Election", command=self.calculate).pack(fill=tk.X)
        self._button_row(
            action_box,
            (
                ("Preferences", self._show_preferences_dialog),
                ("Search Page", lambda: self._focus_detail_page("Search")),
            ),
            pady=(7, 0),
        )
        tk.Label(
            parent,
            textvariable=self.validation_var,
            bg=PALETTE["panel"],
            fg=PALETTE["score"],
            justify=tk.LEFT,
            wraplength=250,
            font=("Segoe UI Semibold", 9),
        ).pack(anchor="w", pady=(10, 0))

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
        self.status_var.set(f"Saved location preset: {location.name}.")
        self._log_event(f"Saved location preset: {location.name}")
        self.calculate()

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
        self.calculate()

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
        self.calculate()

    def _use_default_location(self) -> None:
        location = default_location_for_timezone()
        self.location_var.set(location.name)
        self.location_name_var.set(location.name)
        self.latitude_var.set(f"{location.latitude:.4f}")
        self.longitude_var.set(f"{location.longitude:.4f}")
        self.timezone_var.set(location.timezone)
        self.status_var.set(f"Loaded local default location: {location.name}.")
        self._log_event(f"Loaded local default location: {location.name}")
        self.calculate()

    def _forget_location_preset(self) -> None:
        selected_name = self.location_name_var.get().strip() or self.location_var.get().strip()
        builtin_names = {location.name for location in LOCATION_PRESETS}
        if selected_name in builtin_names:
            self.status_var.set("Built-in locations cannot be forgotten; save a custom copy with a new name.")
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
        self.calculate()

    def _sync_aspects_to_preset(self, _event: object | None = None) -> None:
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        for aspect_id, var in self.aspect_vars.items():
            var.set(aspect_id in preset.aspect_ids)
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
            )
        except ValueError:
            self.search_summary_var.set("Search settings need attention.")
            return
        self.search_summary_var.set(format_search_summary(config))

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
        self.calculate()

    def _set_current_time(self) -> None:
        timezone_name = self.timezone_var.get() or DEFAULT_TIMEZONE
        now = datetime.now(ZoneInfo(timezone_name))
        self.date_var.set(now.strftime("%Y-%m-%d"))
        self.time_var.set(now.strftime("%H:%M"))
        self.calculate()

    def _build_chart_panel(self) -> None:
        header = ttk.Frame(self.center_panel, style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, minsize=88)
        ttk.Label(header, text="RADIX + ELECTIONAL TRANSITS", style="Accent.TLabel").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value="")
        self.title_label = ttk.Label(header, textvariable=self.title_var, style="Title.TLabel", wraplength=520, justify=tk.LEFT)
        self.title_label.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.timing_context_var = tk.StringVar(value="")
        self.timing_context_label = ttk.Label(header, textvariable=self.timing_context_var, style="Small.TLabel", wraplength=520, justify=tk.LEFT)
        self.timing_context_label.grid(row=2, column=0, sticky="ew", pady=(3, 0), padx=(0, 8))
        self.context_chip_frame = tk.Frame(header, bg=PALETTE["panel"])
        self.context_chip_frame.grid(row=3, column=0, sticky="w", pady=(8, 0))
        header.bind("<Configure>", self._resize_header_labels)

        score_card = tk.Frame(
            header,
            bg=PALETTE["panel_alt"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        score_card.grid(row=0, column=1, rowspan=4, sticky="e")
        tk.Frame(score_card, bg=PALETTE["score"], height=2).pack(fill=tk.X, pady=(0, 5))
        self.score_var = tk.StringVar(value="--")
        tk.Label(
            score_card,
            textvariable=self.score_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["score"],
            font=("Segoe UI Semibold", 32),
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
        state_bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
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

        self._build_wheel_display_controls()

        self.canvas = tk.Canvas(
            self.center_panel,
            width=760,
            height=540,
            bg=PALETTE["canvas"],
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
        )
        self.canvas.grid(row=3, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._schedule_redraw)
        self.canvas.bind("<Enter>", lambda _event: self.center_scroll_canvas.bind_all("<MouseWheel>", self._scroll_center_workspace))
        self.canvas.bind("<Leave>", lambda _event: self.center_scroll_canvas.unbind_all("<MouseWheel>"))

        self.focus_body_var = tk.StringVar(value="")
        self._build_chart_page_strip()

        actions = ttk.Frame(self.center_panel, style="Panel.TFrame")
        actions.grid(row=5, column=0, sticky="ew", pady=(7, 0))
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
            bg=PALETTE["top_bar_dark"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=7,
            pady=5,
        )
        strip.grid(row=4, column=0, sticky="ew", pady=(7, 0))
        tk.Label(strip, text="View Page", bg=PALETTE["top_bar_dark"], fg="white", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(strip, text="Mode", bg=PALETTE["top_bar_dark"], fg="white", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        page_mode_combo = ttk.Combobox(strip, textvariable=self.page_mode_var, values=PAGE_MODE_NAMES, state="readonly", width=20)
        page_mode_combo.pack(side=tk.LEFT, padx=(0, 10))
        page_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._page_mode_changed())
        for label, command in (
            ("Interpretation", lambda: self._focus_detail_page("Window")),
            ("Advisor", lambda: self._focus_detail_page("Advisor")),
            ("Improve", lambda: self._focus_detail_page("Improve")),
            ("Decision", lambda: self._focus_detail_page("Decision")),
            ("Compare", lambda: self._focus_detail_page("Compare")),
            ("Search", lambda: self._focus_detail_page("Search")),
            ("Timing", lambda: self._focus_detail_page("Timing")),
            ("Angles", lambda: self._focus_detail_page("Angles")),
            ("Aspects", lambda: self._focus_detail_page("Aspects")),
            ("Aspectarian", lambda: self._focus_detail_page("Aspectarian")),
            ("Point Data", lambda: self._focus_detail_page("Point Data")),
            ("Medieval", lambda: self._focus_detail_page("Medieval")),
            ("Conditions", lambda: self._focus_detail_page("Conditions")),
            ("Shortlist", lambda: self._focus_detail_page("Shortlist")),
            ("Log", lambda: self._focus_detail_page("Log")),
            ("Chart Data", self._show_chart_inspector),
            ("Save Wheel", self._save_chart_wheel),
        ):
            tk.Button(
                strip,
                text=label,
                command=command,
                bg="#edf4f7",
                fg=PALETTE["top_bar_dark"],
                activebackground="#d8eef2",
                relief=tk.FLAT,
                padx=8,
                pady=2,
                font=("Segoe UI", 8, "bold"),
            ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(strip, text="Focus", command=self._focus_selected_body).pack(side=tk.RIGHT, padx=(6, 0))
        self.focus_body_combo = ttk.Combobox(strip, textvariable=self.focus_body_var, values=[], state="readonly", width=16)
        self.focus_body_combo.pack(side=tk.RIGHT)
        self.focus_body_combo.bind("<<ComboboxSelected>>", lambda _event: self._focus_selected_body())
        tk.Label(strip, text="Point", bg=PALETTE["top_bar_dark"], fg="white", font=("Segoe UI", 8, "bold")).pack(side=tk.RIGHT, padx=(8, 6))

    def _resize_header_labels(self, event: object) -> None:
        width = max(240, int(getattr(event, "width", 640)) - 120)
        self.title_label.configure(wraplength=width)
        self.timing_context_label.configure(wraplength=width)

    def _build_wheel_display_controls(self) -> None:
        display = tk.Frame(
            self.center_panel,
            bg=PALETTE["panel_alt"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=9,
            pady=5,
        )
        display.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        tk.Label(display, text="Wheel View", bg=PALETTE["panel_alt"], fg=PALETTE["accent"], font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(display, text="Clean", command=self._apply_clean_wheel_view).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(display, text="Full", command=self._apply_full_wheel_view).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(display, text="Fit", command=self._fit_wheel_view).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(display, text="Zoom -", command=lambda: self._adjust_wheel_zoom(-0.06)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(display, text="Zoom +", command=lambda: self._adjust_wheel_zoom(0.06)).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(display, text="Points", bg=PALETTE["panel_alt"], fg=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        point_combo = ttk.Combobox(display, textvariable=self.point_set_var, values=POINT_SET_NAMES, state="readonly", width=17)
        point_combo.pack(side=tk.LEFT, padx=(0, 10))
        point_combo.bind("<<ComboboxSelected>>", lambda _event: self._point_set_changed())
        ttk.Button(display, text="Reset Panels", command=self._reset_workspace_panels).pack(side=tk.RIGHT)
        ttk.Button(display, text="Bottom", command=self._scroll_center_to_bottom).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(display, text="Top", command=self._scroll_center_to_top).pack(side=tk.RIGHT, padx=(0, 6))
        for label, variable in (
            ("Aspects", self.show_aspects_var),
            ("Lots", self.show_lots_var),
            ("Nodes", self.show_nodes_var),
            ("Fixed Stars", self.show_fixed_stars_var),
            ("Compact", self.compact_wheel_var),
        ):
            tk.Checkbutton(
                display,
                text=label,
                variable=variable,
                command=self._display_option_changed,
                bg=PALETTE["panel_alt"],
                activebackground=PALETTE["panel_alt"],
                fg=PALETTE["muted"],
                selectcolor=PALETTE["panel_alt"],
                font=("Segoe UI", 8, "bold"),
            ).pack(side=tk.LEFT, padx=(0, 10))

    def _display_option_changed(self) -> None:
        self._redraw_selected_window()
        self._save_session()
        self.status_var.set("Updated wheel display options.")

    def _current_page_mode_id(self) -> str:
        return PAGE_MODE_IDS_BY_NAME.get(self.page_mode_var.get(), "wheel")

    def _current_point_set(self) -> PointSet:
        return get_point_set(self.point_set_var.get())

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

    def _page_mode_changed(self) -> None:
        self._apply_page_mode(self._current_page_mode_id())

    def _apply_page_mode(self, mode_id: str, *, save: bool = True) -> None:
        if mode_id == "wheel-aspectarian":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self.show_aspects_var.set(True)
            self.compact_wheel_var.set(False)
            self._focus_detail_page("Aspectarian")
            status = "Page mode: Wheel + Aspectarian."
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
            self.show_aspects_var.set(False)
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
            self._focus_detail_page("Search")
            status = "Page mode: Transit Search."
        else:
            self.page_mode_var.set(PAGE_MODE_LABELS["wheel"])
            self.show_aspects_var.set(True)
            self.compact_wheel_var.set(True)
            self._focus_detail_page("Window")
            status = "Page mode: Wheel."
        self._redraw_selected_window()
        if save:
            self._save_session()
        self.status_var.set(status)

    def _fit_wheel_view(self) -> None:
        self.wheel_zoom = 0.88
        self.compact_wheel_var.set(True)
        self._display_option_changed()
        self.status_var.set("Wheel view fitted with extra label room.")

    def _adjust_wheel_zoom(self, delta: float) -> None:
        self.wheel_zoom = max(0.76, min(1.04, self.wheel_zoom + delta))
        self._display_option_changed()
        self.status_var.set(f"Wheel zoom: {self.wheel_zoom:.0%}.")

    def _scroll_center_to_top(self) -> None:
        if hasattr(self, "center_scroll_canvas"):
            self.center_scroll_canvas.yview_moveto(0)
            self.status_var.set("Middle workspace moved to top.")

    def _scroll_center_to_bottom(self) -> None:
        if hasattr(self, "center_scroll_canvas"):
            self.center_scroll_canvas.yview_moveto(1)
            self.status_var.set("Middle workspace moved to bottom.")

    def _toggle_focus_mode(self) -> None:
        self._set_focus_mode(not self.focus_mode)

    def _pack_workspace_panels(self) -> None:
        for panel in (self.left_panel, self.center_pane, self.right_panel):
            if str(panel) in self.workspace_panes.panes():
                self.workspace_panes.forget(panel)
        self.workspace_panes.add(self.left_panel, minsize=245, width=315, stretch="never", padx=0)
        self.workspace_panes.add(self.center_pane, minsize=420, width=720, stretch="always", padx=8)
        self.workspace_panes.add(self.right_panel, minsize=285, width=380, stretch="never", padx=0)

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
        self.point_set_var.set(get_point_set("classical-7").name)
        self.show_aspects_var.set(True)
        self.show_lots_var.set(False)
        self.show_nodes_var.set(False)
        self.show_fixed_stars_var.set(False)
        self.compact_wheel_var.set(True)
        self._display_option_changed()

    def _apply_full_wheel_view(self) -> None:
        self.point_set_var.set(get_point_set("full-electional").name)
        self.show_aspects_var.set(True)
        self.show_lots_var.set(True)
        self.show_nodes_var.set(True)
        self.show_fixed_stars_var.set(True)
        self.compact_wheel_var.set(False)
        self._display_option_changed()

    def _state_card(self, parent: tk.Widget, title: str, variable: tk.StringVar, column: int, accent_color: str) -> None:
        card = tk.Frame(parent, bg=PALETTE["panel_alt"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=10, pady=7)
        card.grid(row=0, column=column, sticky="ew", padx=(0, 6) if column < 3 else (0, 0))
        tk.Frame(card, bg=accent_color, height=2).pack(fill=tk.X, pady=(0, 5))
        tk.Label(card, text=title, bg=PALETTE["panel_alt"], fg=accent_color, font=("Segoe UI Semibold", 8)).pack(anchor="w")
        tk.Label(card, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=170, justify=tk.LEFT).pack(anchor="w")

    def _build_right_panel(self) -> None:
        self._build_metric_panel()
        self._build_window_list_panel()
        self.detail_notebook = ttk.Notebook(self.right_panel)
        self.detail_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 9))
        self.summary_text = self._text_tab("Summary")
        self.window_detail_text = self._text_tab("Window")
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
        self.planets_text = self._text_tab("Planets")
        self.aspects_text = self._text_tab("Aspects")
        self.aspectarian_text = self._text_tab("Aspectarian")
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
        frame = ttk.LabelFrame(self.right_panel, text="Election Scoreboard", style="Panel.TLabelframe", padding=7)
        frame.pack(fill=tk.X, pady=(0, 9))
        metrics = (
            ("score", "Score", PALETTE["panel_alt"], PALETTE["score"]),
            ("confidence", "Confidence", PALETTE["panel_alt"], PALETTE["accent_dark"]),
            ("fit", "Fit", PALETTE["panel_alt"], PALETTE["accent"]),
            ("support", "Support", PALETTE["panel_alt"], PALETTE["support"]),
            ("stress", "Stress", PALETTE["panel_alt"], PALETTE["stress"]),
            ("angular", "Angular", PALETTE["panel_alt"], PALETTE["top_bar"]),
            ("stars", "Stars", PALETTE["panel_alt"], "#4d66a6"),
            ("rules", "Rules", PALETTE["panel_alt"], PALETTE["warning"]),
        )
        for index, (key, label, bg_color, value_color) in enumerate(metrics):
            var = tk.StringVar(value="--")
            self.metric_vars[key] = var
            card = tk.Frame(
                frame,
                bg=bg_color,
                highlightbackground=PALETTE["panel_line"],
                highlightthickness=1,
                padx=9,
                pady=7,
            )
            card.grid(row=index // 2, column=index % 2, sticky="ew", padx=3, pady=3)
            tk.Frame(card, bg=value_color, height=2).pack(fill=tk.X, pady=(0, 5))
            tk.Label(card, text=label, bg=bg_color, fg=PALETTE["muted"], font=("Segoe UI Semibold", 8)).pack(anchor="w")
            tk.Label(card, textvariable=var, bg=bg_color, fg=value_color, font=("Segoe UI Semibold", 15)).pack(anchor="w")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _build_window_list_panel(self) -> None:
        frame = ttk.LabelFrame(self.right_panel, text="Candidate Windows", style="Panel.TLabelframe", padding=7)
        frame.pack(fill=tk.X, pady=(0, 9))
        viewport = ttk.Frame(frame, style="Panel.TFrame")
        viewport.pack(fill=tk.X)
        self.window_cards_canvas = tk.Canvas(
            viewport,
            height=245,
            bg=PALETTE["panel_alt"],
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
        ttk.Button(buttons, text="Prev", command=lambda: self._select_relative_window(-1)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        ttk.Button(buttons, text="Next", command=lambda: self._select_relative_window(1)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        ttk.Button(buttons, text="Use Time", command=self._use_selected_window_time).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        ttk.Button(buttons, text="Save Pick", command=self._add_selected_to_shortlist).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        ttk.Button(buttons, text="Copy", command=self._copy_current_report).pack(side=tk.LEFT, expand=True, fill=tk.X)

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

    def _text_tab(self, title: str) -> tk.Text:
        frame = ttk.Frame(self.detail_notebook, style="Panel.TFrame", padding=7)
        self.detail_notebook.add(frame, text=title)
        text = tk.Text(
            frame,
            width=40,
            height=16,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            padx=7,
            pady=7,
        )
        text.pack(fill=tk.BOTH, expand=True)
        text.configure(state=tk.DISABLED)
        return text

    def calculate(self) -> None:
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        zodiac_system = get_zodiac_system(self.zodiac_system_var.get())
        house_system = get_house_system(self.house_system_var.get())
        selected_aspects = [aspect for aspect, var in self.aspect_vars.items() if var.get()]
        if not selected_aspects:
            self.validation_var.set("Validation failed:\n- Select at least one aspect focus before calculating.")
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
            )
        except Exception as exc:  # pragma: no cover - exercised manually through the desktop UI.
            messagebox.showerror("Electional calculation failed", str(exc))
            return

        snapshot = report["snapshot"]
        windows = report["windows"]
        selected_window = windows[0] if windows else snapshot
        self.current_location = location
        self.input_snapshot = snapshot
        self.current_windows = list(windows)
        search_mode = str(report.get("searchMode") or "full")
        deep_count = int(report.get("deepWindowCount") or len(windows))
        searched_count = int(report.get("searchedWindowCount") or len(windows))
        cache = report.get("snapshotCache", {})
        cache_text = ""
        if isinstance(cache, dict):
            cache_text = f" Cache hits {cache.get('hits', 0)}, stored {cache.get('currsize', 0)}."
        self.current_search_summary = (
            f"{format_search_summary(search_config)} Mode: {search_mode}; deep-built {deep_count}/{searched_count}.{cache_text}"
        )
        self.current_rejection_summary = dict(report.get("rejectionSummary") or {})
        self.current_searched_window_count = searched_count
        self.selected_window = selected_window

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
        self.validation_var.set("Validation: Pass")
        result_note = f"{len(windows)} matching window{'s' if len(windows) != 1 else ''}"
        if not windows:
            result_note = "No matching windows; showing the input chart"
        self.status_var.set(
            (
                f"Location: {location.name}    Chart time: {selected_window['formattedTime']}    "
                f"Search: {search_config.end_offset_minutes // 60}h/{search_config.step_minutes}m    "
                f"Results: {result_note} of {self.current_searched_window_count} scanned    "
                f"System: {zodiac_system.name} / {house_system.name}    Validation: Pass"
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
        self._populate_window_list(windows)
        self._draw_wheel(selected_window)
        self._render_text_panels(selected_window, windows, location)
        self._save_session()

    def _populate_window_list(self, windows: list[dict[str, object]]) -> None:
        for card in self.window_cards:
            card.destroy()
        self.window_cards = []
        if not windows:
            empty_card = tk.Frame(
                self.window_cards_frame,
                bg=PALETTE["panel_alt"],
                highlightbackground=PALETTE["panel_line"],
                highlightthickness=1,
                padx=9,
                pady=10,
            )
            empty_card.pack(fill=tk.X, padx=4, pady=(4, 6))
            tk.Label(
                empty_card,
                text="No candidate windows matched the current filters.",
                bg=PALETTE["panel_alt"],
                fg=PALETTE["muted"],
                font=("Segoe UI", 9, "bold"),
                wraplength=280,
                justify=tk.LEFT,
            ).pack(fill=tk.X)
            self.selected_window_index = 0
            return
        for index, window in enumerate(windows, start=1):
            self._create_window_card(index - 1, window)
        self.selected_window_index = 0
        self._refresh_window_card_styles()

    def _create_window_card(self, index: int, window: dict[str, object]) -> None:
        card = tk.Frame(
            self.window_cards_frame,
            bg=window_score_color(int(window["score"])),
            highlightbackground=PALETTE["selected"] if index == self.selected_window_index else PALETTE["panel_line"],
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        card.pack(fill=tk.X, padx=4, pady=(4, 6))
        self.window_cards.append(card)
        accent_strip = tk.Frame(card, bg=PALETTE["score"], height=2)
        accent_strip.pack(fill=tk.X, pady=(0, 8))
        header = tk.Frame(card, bg=card["bg"])
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=f"#{index + 1}",
            bg=PALETTE["top_bar"],
            fg="white",
            font=("Segoe UI Semibold", 8),
            padx=7,
            pady=2,
        ).pack(side=tk.LEFT, padx=(0, 7))
        tk.Label(
            header,
            text=str(window["time"]),
            bg=card["bg"],
            fg=PALETTE["accent"],
            font=("Segoe UI Semibold", 11),
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text=f"{score_band_label(int(window['score']))} {window['score']}",
            bg=card["bg"],
            fg=PALETTE["score"],
            font=("Segoe UI Semibold", 10),
            padx=8,
        ).pack(side=tk.RIGHT)
        tk.Label(
            card,
            text=str(window.get("title", "Electional window")),
            bg=card["bg"],
            fg=PALETTE["text"],
            font=("Segoe UI Semibold", 11),
            anchor="w",
        ).pack(fill=tk.X, pady=(5, 1))
        tk.Label(
            card,
            text=str(window.get("note", "")),
            bg=card["bg"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=280,
            justify=tk.LEFT,
        ).pack(fill=tk.X)
        support = sum(1 for aspect in window["detectedAspects"] if aspect["tone"] == "support")
        stress = sum(1 for aspect in window["detectedAspects"] if aspect["tone"] == "stress")
        fixed_stars = fixed_star_contact_count(window)
        breakdown = window.get("scoreBreakdown", {})
        diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, dict) else {}
        confidence = diagnostics.get("confidence", {}) if isinstance(diagnostics, dict) else {}
        cleanliness = diagnostics.get("cleanliness", {}) if isinstance(diagnostics, dict) else {}
        volatility = diagnostics.get("volatility", {}) if isinstance(diagnostics, dict) else {}
        fit_matches = int(breakdown.get("objectiveMatches", 0)) if isinstance(breakdown, dict) else 0
        offset_text = selection_offset_label(self.input_snapshot or window, window)
        tag_row = tk.Frame(card, bg=card["bg"])
        tag_row.pack(fill=tk.X, pady=(6, 0))
        for text, fg, bg in (
            (f"Conf {confidence.get('score', '--')}", PALETTE["score"], "#eaf4f8"),
            (f"Clean {cleanliness.get('score', '--')}", PALETTE["accent_dark"], "#edf7f6"),
            (f"Vol {volatility.get('score', '--')}", PALETTE["warning"], "#fbf2e5"),
            (f"{fit_matches} fit", PALETTE["accent_dark"], "#e6f4f4"),
            (f"+{support} support", PALETTE["support"], "#e7f6ef"),
            (f"!{stress} stress", PALETTE["stress"], "#fae9ed"),
            (f"{fixed_stars} stars", "#3f5f9c", "#edf3ff"),
            (offset_text, PALETTE["top_bar"], "#eaf1f7"),
        ):
            tk.Label(
                tag_row,
                text=text,
                bg=bg,
                fg=fg,
                font=("Segoe UI Semibold", 8),
                padx=7,
                pady=3,
            ).pack(side=tk.LEFT, padx=(0, 4))
        self._bind_card_click(card, lambda selected=index: self._select_window_by_index(selected))
        self._bind_card_click(card, lambda selected=index: self._activate_window_card(selected), double_click=True)

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
        self.score_var.set(str(selected["score"]))
        self.score_band_var.set(f"{score_band_label(int(selected['score']))} window")
        self.status_var.set(
            f"Location: {self.current_location.name}    Chart time: {selected['formattedTime']}    System: {selected['zodiacSystem'].name} / {selected['houseSystem'].name}    Validation: Pass"
        )
        self._log_event(f"Selected window #{index + 1}: {selected['formattedTime']} score {selected['score']}")
        self._set_timing_context(self.input_snapshot or selected, selected, self.current_location)
        self._render_summary_chips(selected)
        self._refresh_window_card_styles()
        self._draw_wheel(selected)
        self._render_text_panels(selected, self.current_windows, self.current_location)

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
            card.configure(highlightbackground=PALETTE["accent"] if selected else PALETTE["panel_line"], highlightthickness=2 if selected else 1)

    def _set_timing_context(
        self,
        input_snapshot: dict[str, object],
        selected_window: dict[str, object],
        location: LocationPreset | None = None,
    ) -> None:
        offset = selection_offset_label(input_snapshot, selected_window)
        self.timing_context_var.set(
            f"{location_summary(location)}    Search: {input_snapshot['formattedTime']}    Selected: {selected_window['formattedTime']}    {offset}"
        )
        self.location_state_var.set(location_summary(location))
        self.input_state_var.set(compact_time_label(input_snapshot))
        self.selected_state_var.set(compact_time_label(selected_window))
        self.offset_state_var.set(offset)

    def _use_selected_window_time(self) -> None:
        if not self.selected_window or not self.current_location:
            return
        local = self.selected_window["date"].astimezone(ZoneInfo(self.current_location.timezone))
        self.date_var.set(local.strftime("%Y-%m-%d"))
        self.time_var.set(local.strftime("%H:%M"))
        self._log_event(f"Applied selected window to input time: {self.date_var.get()} {self.time_var.get()}")
        self.calculate()

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
        cx = width / 2
        cy = height / 2
        side_padding = 126 if not self.compact_wheel_var.get() and self.show_fixed_stars_var.get() else 96
        vertical_padding = 88 if self.compact_wheel_var.get() else 106
        fit_width = max(260, width - side_padding * 2)
        fit_height = max(260, height - vertical_padding * 2)
        outer = max(118, min(fit_width, fit_height) / 2 * self.wheel_zoom)
        zodiac_inner = outer * 0.84
        house_inner = outer * (0.50 if self.compact_wheel_var.get() else 0.44)
        aspect_radius = outer * 0.44

        self._draw_grid(width, height)
        self.canvas.create_oval(cx - outer - 22, cy - outer - 16, cx + outer + 22, cy + outer + 28, fill="#e4ebf0", outline="")
        self.canvas.create_oval(cx - outer - 10, cy - outer - 8, cx + outer + 10, cy + outer + 14, fill="#edf2f5", outline="")
        self.canvas.create_oval(cx - outer + 7, cy - outer + 10, cx + outer + 7, cy + outer + 10, fill=PALETTE["surface_shadow"], outline="")
        self.canvas.create_oval(
            cx - outer,
            cy - outer,
            cx + outer,
            cy + outer,
            fill=PALETTE["chart_ring_fill"],
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

        for index, sign in enumerate(SIGN_LABELS):
            start = wheel_degrees(index * 30, asc_lon)
            self.canvas.create_arc(
                cx - outer,
                cy - outer,
                cx + outer,
                cy + outer,
                start=start,
                extent=30,
                fill=SIGN_COLORS[index],
                outline="#fffdf8",
                width=1,
            )
            label_angle = wheel_degrees(index * 30 + 15, asc_lon)
            lx, ly = _polar(cx, cy, outer * 0.905, label_angle)
            self._draw_sign_badge(lx, ly, sign, SIGN_COLORS[index])

        self.canvas.create_oval(cx - outer + 1, cy - outer + 1, cx + outer - 1, cy + outer - 1, outline="#ffffff", width=1)
        self.canvas.create_oval(cx - outer + 11, cy - outer + 11, cx + outer - 11, cy + outer - 11, outline="#ffffff", width=1)
        self._draw_degree_ticks(cx, cy, outer, zodiac_inner, asc_lon)

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
        for house_index, cusp in enumerate(house_cusps):
            next_cusp = house_cusps[(house_index + 1) % 12]
            cusp_longitude = float(cusp["longitude"])
            label_longitude = midpoint_longitude(cusp_longitude, float(next_cusp["longitude"]))
            angle = wheel_degrees(cusp_longitude, asc_lon)
            x1, y1 = _polar(cx, cy, house_inner, angle)
            x2, y2 = _polar(cx, cy, zodiac_inner, angle)
            self.canvas.create_line(x1, y1, x2, y2, fill=PALETTE["chart_line"], width=1)
            label_angle = wheel_degrees(label_longitude, asc_lon)
            lx, ly = _polar(cx, cy, outer * 0.64, label_angle)
            self.canvas.create_text(lx, ly, text=str(cusp["house"]), fill=PALETTE["accent_dark"], font=("Segoe UI Semibold", 10 if self.compact_wheel_var.get() else 12))

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

    def _draw_center_hub(self, cx: float, cy: float, snapshot: dict[str, object]) -> None:
        self.canvas.create_oval(cx - 63, cy - 58, cx + 63, cy + 68, fill="#dde7ec", outline="")
        self.canvas.create_oval(cx - 60, cy - 60, cx + 60, cy + 60, fill=PALETTE["center_hub"], outline=PALETTE["chart_bezel"], width=2)
        self.canvas.create_oval(cx - 49, cy - 49, cx + 49, cy + 49, outline=PALETTE["chart_bezel_inner"], width=1)
        self.canvas.create_oval(cx - 37, cy - 37, cx + 37, cy + 37, outline="#edf4f2", width=1)
        self.canvas.create_line(cx - 30, cy + 2, cx + 30, cy + 2, fill=PALETTE["chart_bezel_inner"], width=1)
        self.canvas.create_text(cx, cy - 12, text=f"Score {snapshot['score']}", fill=PALETTE["top_bar_dark"], font=("Segoe UI Semibold", 13 if self.compact_wheel_var.get() else 15))
        self.canvas.create_text(cx, cy + 15, text=score_band_label(int(snapshot["score"])), fill=PALETTE["accent_dark"], font=("Segoe UI Semibold", 8 if self.compact_wheel_var.get() else 9))

    def _is_focused_body(self, kind: str, name: str) -> bool:
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
    ) -> None:
        house_cusps = sorted(snapshot.get("houseCusps", []), key=lambda cusp: int(cusp["house"]))
        if not house_cusps:
            return
        fills = (PALETTE["chart_house_fill"], PALETTE["chart_house_fill_alt"])
        for index, cusp in enumerate(house_cusps):
            next_cusp = house_cusps[(index + 1) % len(house_cusps)]
            start = wheel_degrees(float(cusp["longitude"]), asc_lon)
            end = wheel_degrees(float(next_cusp["longitude"]), asc_lon)
            outer_points = _arc_points(cx, cy, outer_radius, start, end)
            inner_points = _arc_points(cx, cy, inner_radius, end, start)
            self.canvas.create_polygon(
                outer_points + inner_points,
                fill=fills[index % len(fills)],
                outline="",
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
        for x in range(0, width, 72):
            self.canvas.create_line(x, 0, x, height, fill=PALETTE["canvas_grid"], width=1)
        for y in range(0, height, 72):
            self.canvas.create_line(0, y, width, y, fill=PALETTE["canvas_grid"], width=1)

    def _draw_wheel_legend(self, width: int, height: int) -> None:
        if self.compact_wheel_var.get():
            return
        x = 16
        y = max(16, height - 88)
        self.canvas.create_rectangle(
            x,
            y,
            x + 198,
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

    def _draw_angles(self, snapshot: dict[str, object], cx: float, cy: float, outer: float, asc_lon: float) -> None:
        for angle in snapshot["angles"]:
            degrees = wheel_degrees(float(angle["longitude"]), asc_lon)
            x1, y1 = _polar(cx, cy, outer * 0.33, degrees)
            x2, y2 = _polar(cx, cy, outer * 0.965, degrees)
            self.canvas.create_line(x1, y1, x2, y2, fill="#ffffff", width=5)
            self.canvas.create_line(x1, y1, x2, y2, fill=PALETTE["accent_dark"], width=2)
            lx, ly = _polar(cx, cy, outer - 35, degrees)
            label_size = 18 if self.compact_wheel_var.get() else 20
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
                outline=PALETTE["accent_dark"],
                width=1,
            )
            self.canvas.create_text(lx, ly, text=angle["shortName"], fill=PALETTE["accent_dark"], font=("Segoe UI Semibold", 11 if self.compact_wheel_var.get() else 12))

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
        offsets = planet_marker_offsets([float(planet["longitude"]) for planet in planets], compact=self.compact_wheel_var.get())
        base_radius = outer * (0.70 if self.compact_wheel_var.get() else 0.695)
        marker_size = 11 if self.compact_wheel_var.get() else 13
        for planet, (angle_offset, radial_offset) in zip(planets, offsets):
            degrees = wheel_degrees(float(planet["longitude"]), asc_lon) + angle_offset
            radius = max(outer * 0.53, base_radius - radial_offset)
            x, y = _polar(cx, cy, radius, degrees)
            fill = PALETTE["planet_fill_angular"] if planet.get("isAngular") else PALETTE["planet_fill"]
            if planet.get("isPresetPoint"):
                fill = "#f7f0dc"
            outline = PALETTE["accent_dark"] if planet.get("isAngular") else PALETTE["chart_line"]
            planet_tag = f"planet:{planet['id']}"
            focused = self._is_focused_body("planet", str(planet["name"]))
            focus_outline = PALETTE["warning"] if focused else outline
            self.canvas.create_oval(x - marker_size + 2, y - marker_size + 3, x + marker_size + 2, y + marker_size + 3, fill="#d7e0e5", outline="", tags=("planet-marker", planet_tag))
            self.canvas.create_oval(x - marker_size, y - marker_size, x + marker_size, y + marker_size, fill=fill, outline=outline, width=2, tags=("planet-marker", planet_tag))
            self.canvas.create_oval(x - marker_size + 3, y - marker_size + 3, x + marker_size - 3, y + marker_size - 3, outline=PALETTE["chart_bezel_inner"], width=1, tags=("planet-marker", planet_tag))
            if focused:
                self.canvas.create_oval(x - marker_size - 4, y - marker_size - 4, x + marker_size + 4, y + marker_size + 4, outline=focus_outline, width=2, tags=("planet-marker", planet_tag))
            self.canvas.create_text(
                x,
                y,
                text=planet_abbreviation(str(planet["name"])),
                fill=PALETTE["top_bar_dark"],
                font=("Segoe UI Semibold", 8 if self.compact_wheel_var.get() else 9),
                tags=("planet-marker", planet_tag),
            )
            self.canvas.tag_bind(planet_tag, "<Button-1>", lambda _event, planet_id=str(planet["id"]): self._select_planet_by_id(planet_id))
            self.canvas.tag_bind(planet_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(planet_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_lots(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        lots = self._visible_lots(snapshot)
        offsets = body_marker_offsets([float(lot["longitude"]) for lot in lots], compact=self.compact_wheel_var.get(), crowd_threshold=10.0, angle_step=4.5, radial_step=10.0)
        base_radius = outer * 0.58
        for lot, (angle_offset, radial_offset) in zip(lots, offsets):
            degrees = wheel_degrees(float(lot["longitude"]), asc_lon) + angle_offset
            radius = min(outer * 0.76, max(outer * 0.50, base_radius + radial_offset * 0.7))
            x, y = _polar(cx, cy, radius, degrees)
            lot_tag = f"lot:{lot['id']}"
            focused = self._is_focused_body("lot", str(lot["name"]))
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
        offsets = body_marker_offsets([float(node["longitude"]) for node in nodes], compact=self.compact_wheel_var.get(), crowd_threshold=9.0, angle_step=4.0, radial_step=9.0)
        base_radius = outer * 0.42
        for node, (angle_offset, radial_offset) in zip(nodes, offsets):
            degrees = wheel_degrees(float(node["longitude"]), asc_lon) + angle_offset
            radius = max(outer * 0.34, base_radius - radial_offset * 0.8)
            x, y = _polar(cx, cy, radius, degrees)
            node_tag = f"node:{node['id']}"
            focused = self._is_focused_body("node", str(node["name"]))
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

    def _render_text_panels(self, snapshot: dict[str, object], windows: list[dict[str, object]], location: object) -> None:
        support = sum(1 for aspect in snapshot["detectedAspects"] if aspect["tone"] == "support")
        stress = sum(1 for aspect in snapshot["detectedAspects"] if aspect["tone"] == "stress")
        angular = sum(1 for planet in snapshot["positions"] if planet.get("isAngular"))
        self._set_text(
            self.summary_text,
            (
                f"Score: {snapshot['score']}\n"
                f"Score explanation: {format_score_breakdown(snapshot)}\n"
                f"Lunar phase: {format_lunar_phase(snapshot)}\n"
                f"Timezone: {location.timezone}\n"
                f"Zodiac: {snapshot['zodiacSystem'].name}\n"
                f"House system: {snapshot['houseSystem'].name}\n"
                f"Ayanamsha: {float(snapshot['ayanamsha']):.3f} deg\n"
                f"Fixed-star score: {float(snapshot['scoreBreakdown'].get('fixedStar', 0)):+.1f}\n"
                f"Calculation engine: {snapshot['calculationBackend']['activeEngine']}\n"
                f"Model: {snapshot['preset'].name}\n"
                f"Engine: {snapshot['engine']}"
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
        self._refresh_shortlist_text()

        selected_rank = next((index for index, window in enumerate(windows, start=1) if window["date"] == snapshot["date"]), 1)
        aspect_labels = ", ".join(format_aspect_summary(aspect) for aspect in snapshot["detectedAspects"][:3]) or "No selected major aspects"
        self._set_text(
            self.window_detail_text,
            (
                f"Rank: {selected_rank} of {len(windows)}\n"
                f"Time: {snapshot['formattedTime']}\n"
                f"Score: {snapshot['score']} - {snapshot.get('title', 'Election')}\n"
                f"Lunar phase: {format_lunar_phase(snapshot)}\n"
                f"Score explanation: {format_score_breakdown(snapshot)}\n"
                f"{chr(10).join(score_reason_lines(snapshot)[:4])}\n"
                f"{snapshot.get('note', '')}\n"
                f"{aspect_labels}"
            ),
        )
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
        self._set_text(self.significators_text, "\n".join(judgment_context_lines(snapshot, "significatorContext")))
        self._set_text(self.moon_judgment_text, "\n".join(judgment_context_lines(snapshot, "moonCondition")))
        self._set_text(self.house_rulers_text, "\n".join(judgment_context_lines(snapshot, "houseRulerContext")))
        self._set_text(self.reception_text, "\n".join(judgment_context_lines(snapshot, "receptionContext")))
        self._set_text(self.planet_condition_text, "\n".join(judgment_context_lines(snapshot, "planetConditionContext")))
        self._set_text(self.declination_text, "\n".join(judgment_context_lines(snapshot, "declinationContext")))
        self._set_text(self.advanced_aspects_text, "\n".join(judgment_context_lines(snapshot, "advancedAspectContext")))
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
            f"House {cusp['house']:<2} {format_position(cusp):<16}"
            for cusp in snapshot.get("houseCusps", [])
        ]
        self._set_text(
            self.cusps_text,
            (
                f"{snapshot['houseSystem'].name} cusps\n"
                f"Zodiac: {snapshot['zodiacSystem'].name}\n"
                f"Ayanamsha: {float(snapshot['ayanamsha']):.3f} deg\n\n"
                + "\n".join(cusp_lines)
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
            self._set_text(self.timing_text, "Timing profile unavailable.")

        aspect_lines = []
        for aspect in snapshot["detectedAspects"]:
            aspect_lines.append(f"{format_aspect_summary(aspect)} - {aspect['tone']}")
        self._set_text(self.aspects_text, "\n".join(aspect_lines) or "No selected major aspects in orb.")
        self._set_text(self.aspectarian_text, format_aspectarian(snapshot))

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
            "aspects": {aspect_id: var.get() for aspect_id, var in self.aspect_vars.items()},
            "scan_hours": self.scan_hours_var.get(),
            "step_minutes": self.step_minutes_var.get(),
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
            "display_options": {
                "show_aspects": self.show_aspects_var.get(),
                "show_lots": self.show_lots_var.get(),
                "show_nodes": self.show_nodes_var.get(),
                "show_fixed_stars": self.show_fixed_stars_var.get(),
                "compact_wheel": self.compact_wheel_var.get(),
                "wheel_zoom": self.wheel_zoom,
                "point_set": get_point_set(self.point_set_var.get()).id,
                "page_mode": self._current_page_mode_id(),
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
