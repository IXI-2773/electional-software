"""Native desktop application shell for Electional Software."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import math
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .chart import build_election_report, format_angle, format_position
from .locations import (
    DEFAULT_TIMEZONE,
    LOCATION_PRESETS,
    LocationPreset,
    build_custom_location,
    combined_location_names,
    default_location_for_timezone,
    get_location,
    load_user_locations,
    save_user_locations,
    upsert_user_location,
)
from .presets import ELECTIONAL_PRESETS
from .references import dignity_table_lines, lot_reference_lines, system_reference_lines
from .reporting import (
    build_report_text,
    condition_lines,
    format_aspectarian,
    format_dignity_summary,
    format_aspect_summary,
    format_fixed_star_contact,
    format_lunar_phase,
    format_motion_summary,
    format_planet_focus,
    format_score_breakdown,
    format_window_label,
    rule_lines,
    score_reason_lines,
)
from .screening import moon_void_course_summary, solar_elongation_summary
from .search import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_MINIMUM_SCORE,
    DEFAULT_SCAN_HOURS,
    DEFAULT_STEP_MINUTES,
    build_search_config_from_text,
    format_search_summary,
)
from .session import OBJECTIVES, clean_session_state, load_session_state, save_session_state
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

PALETTE = {
    "app_bg": "#e8eef3",
    "title_bar": "#f2a0ad",
    "top_bar": "#17395c",
    "top_bar_dark": "#0f2238",
    "ribbon": "#eef4f8",
    "ribbon_panel": "#f9fbfd",
    "panel": "#f8fafb",
    "panel_alt": "#ffffff",
    "panel_line": "#c4ced7",
    "canvas": "#eef1e7",
    "canvas_grid": "#dde4dc",
    "chart_disc": "#e9ecdd",
    "chart_inner": "#fbf7e9",
    "chart_line": "#526170",
    "text": "#16202c",
    "muted": "#526273",
    "accent": "#00727d",
    "score": "#005b66",
    "support": "#118875",
    "stress": "#d6536d",
    "warning": "#b36a00",
    "button": "#ffffff",
    "button_hover": "#e8f5f7",
    "button_line": "#b7c3cf",
    "selected": "#d9f3f4",
    "metric_bg": "#edf8f7",
    "center_hub": "#fffdf5",
    "chip": "#e9f4f5",
    "chip_line": "#a6cbd0",
}

SIGN_COLORS = (
    "#ef6b86",
    "#d8c36e",
    "#22c3b1",
    "#b6d7a8",
    "#f0b46a",
    "#d4d8bd",
    "#22b8b0",
    "#c0569f",
    "#f1976d",
    "#bfc7ba",
    "#30b8c3",
    "#c968ad",
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

    return 180 - ((longitude - ascendant_longitude) % 360)


def midpoint_longitude(start: float, end: float) -> float:
    return (start + ((end - start) % 360) / 2) % 360


def _polar(center_x: float, center_y: float, radius: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    return center_x + math.cos(radians) * radius, center_y - math.sin(radians) * radius


def shift_local_datetime_minutes(date_text: str, time_text: str, timezone_name: str, minutes: int) -> tuple[str, str]:
    local_time = datetime.strptime(f"{date_text} {normalize_time_text(time_text)}", "%Y-%m-%d %H:%M")
    zoned = local_time.replace(tzinfo=ZoneInfo(timezone_name or "UTC"))
    shifted = zoned + timedelta(minutes=minutes)
    return shifted.strftime("%Y-%m-%d"), shifted.strftime("%H:%M")


def shift_local_datetime(date_text: str, time_text: str, timezone_name: str, hours: int) -> tuple[str, str]:
    return shift_local_datetime_minutes(date_text, time_text, timezone_name, hours * 60)


def window_score_color(score: int) -> str:
    if score >= 86:
        return "#d9f4e7"
    if score >= 76:
        return "#e8f6f1"
    if score >= 60:
        return "#fff4d6"
    return "#f8dde3"


def score_band_label(score: int) -> str:
    if score >= 86:
        return "Prime"
    if score >= 76:
        return "Strong"
    if score >= 60:
        return "Workable"
    return "Caution"


def fixed_star_contact_count(snapshot: dict[str, object]) -> int:
    contacts = snapshot.get("fixedStarContacts", [])
    return len(contacts) if isinstance(contacts, list) else 0


def summary_chip_lines(snapshot: dict[str, object]) -> list[str]:
    aspects = snapshot.get("detectedAspects", [])
    positions = snapshot.get("positions", [])
    support = sum(1 for aspect in aspects if isinstance(aspect, dict) and aspect.get("tone") == "support")
    stress = sum(1 for aspect in aspects if isinstance(aspect, dict) and aspect.get("tone") == "stress")
    angular = sum(1 for planet in positions if isinstance(planet, dict) and planet.get("isAngular"))
    phase = snapshot.get("lunarPhase", {})
    phase_name = phase.get("name", "Moon phase unknown") if isinstance(phase, dict) else "Moon phase unknown"
    rule_evaluations = snapshot.get("ruleEvaluations", {})
    rules = rule_evaluations.get("rules", []) if isinstance(rule_evaluations, dict) else []
    planetary_hour = snapshot.get("planetaryHour", {})
    hour_ruler = planetary_hour.get("hourRuler", "n/a") if isinstance(planetary_hour, dict) and planetary_hour.get("available") else "n/a"
    return [
        f"Moon: {phase_name}",
        f"Hour: {hour_ruler}",
        f"Aspects: +{support} / !{stress}",
        f"Angular: {angular}",
        f"Fixed stars: {fixed_star_contact_count(snapshot)}",
        f"Rules: {len(rules) if isinstance(rules, list) else 0}",
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
        self.root.minsize(1160, 760)

        self.user_locations = load_user_locations()
        self.location_names = combined_location_names(self.user_locations)
        self.locations_by_name = self._location_map()
        self.presets_by_name = {preset.name: preset for preset in ELECTIONAL_PRESETS}
        self.aspect_vars: dict[str, tk.BooleanVar] = {}
        self.current_location: LocationPreset | None = None
        self.input_snapshot: dict[str, object] | None = None
        self.current_windows: list[dict[str, object]] = []
        self.selected_window: dict[str, object] | None = None
        self.selected_window_index = 0
        self.window_cards: list[tk.Frame] = []
        self._resize_job: str | None = None
        self.focus_mode = False
        self.event_log: list[str] = []
        self.session_state = clean_session_state(load_session_state())
        self.metric_vars: dict[str, tk.StringVar] = {}
        display_options = self.session_state.get("display_options", {})
        self.show_aspects_var = tk.BooleanVar(value=bool(display_options.get("show_aspects", True)))
        self.show_lots_var = tk.BooleanVar(value=bool(display_options.get("show_lots", True)))
        self.show_nodes_var = tk.BooleanVar(value=bool(display_options.get("show_nodes", True)))
        self.show_fixed_stars_var = tk.BooleanVar(value=bool(display_options.get("show_fixed_stars", True)))
        self.compact_wheel_var = tk.BooleanVar(value=bool(display_options.get("compact_wheel", False)))

        self._configure_style()
        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.root.bind("<Alt-Left>", lambda _event: self._select_relative_window(-1))
        self.root.bind("<Alt-Right>", lambda _event: self._select_relative_window(1))
        self.root.bind("<F11>", lambda _event: self._toggle_focus_mode())
        self.calculate()

    def _configure_style(self) -> None:
        self.root.configure(bg=PALETTE["app_bg"])
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=PALETTE["panel"])
        style.configure("Top.TFrame", background=PALETTE["top_bar"])
        style.configure("Ribbon.TFrame", background=PALETTE["ribbon"])
        style.configure("Workbench.TFrame", background=PALETTE["app_bg"])
        style.configure("Panel.TFrame", background=PALETTE["panel"], relief="flat", borderwidth=0)
        style.configure("Card.TFrame", background=PALETTE["panel_alt"], relief="solid", borderwidth=1)
        style.configure("RibbonPanel.TFrame", background=PALETTE["ribbon_panel"], relief="flat", borderwidth=0)
        style.configure("Panel.TLabelframe", background=PALETTE["panel"], bordercolor=PALETTE["panel_line"])
        style.configure("Panel.TLabelframe.Label", background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Segoe UI", 9, "bold"))
        style.configure("Ribbon.TLabelframe", background=PALETTE["ribbon_panel"], bordercolor="#b6c1cc")
        style.configure("Ribbon.TLabelframe.Label", background=PALETTE["ribbon_panel"], foreground=PALETTE["top_bar_dark"], font=("Segoe UI", 8, "bold"))
        style.configure("TNotebook", background=PALETTE["panel"], borderwidth=0)
        style.configure("TNotebook.Tab", background="#e8eef3", foreground=PALETTE["top_bar_dark"], padding=(10, 5), font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", PALETTE["panel_alt"])], foreground=[("selected", PALETTE["accent"])])
        style.configure("Title.TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 18, "bold"))
        style.configure("Small.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
        style.configure("Accent.TLabel", background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Segoe UI", 9, "bold"))
        style.configure("Score.TLabel", background=PALETTE["panel_alt"], foreground=PALETTE["score"], font=("Segoe UI", 30, "bold"))
        style.configure("TButton", background=PALETTE["button"], foreground=PALETTE["text"], padding=(12, 7), bordercolor=PALETTE["button_line"])
        style.map("TButton", background=[("active", PALETTE["button_hover"])])
        style.configure("TCheckbutton", background=PALETTE["panel"], foreground=PALETTE["muted"])
        style.configure("TCombobox", fieldbackground=PALETTE["panel_alt"], background=PALETTE["ribbon_panel"], foreground=PALETTE["text"])

    def _location_map(self) -> dict[str, LocationPreset]:
        locations = {location.name: location for location in LOCATION_PRESETS}
        locations.update({location.name: location for location in self.user_locations})
        return locations

    def _refresh_location_choices(self) -> None:
        self.location_names = combined_location_names(self.user_locations)
        self.locations_by_name = self._location_map()
        if hasattr(self, "location_combo"):
            self.location_combo.configure(values=self.location_names)
        if hasattr(self, "location_status_var"):
            self.location_status_var.set(f"{len(self.user_locations)} custom saved location{'s' if len(self.user_locations) != 1 else ''}.")

    def _build_layout(self) -> None:
        self._build_top_bars()

        self.shell = tk.Frame(self.root, bg=PALETTE["app_bg"], padx=10, pady=10)
        self.shell.pack(fill=tk.BOTH, expand=True)

        self.left_panel = tk.Frame(self.shell, bg=PALETTE["panel"], padx=10, pady=10, width=305)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        self.left_panel.pack_propagate(False)
        self._build_left_controls()

        self.center_panel = ttk.Frame(self.shell, style="Panel.TFrame", padding=10)
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))
        self.center_panel.columnconfigure(0, weight=1)
        self.center_panel.rowconfigure(3, weight=1, minsize=360)
        self._build_chart_panel()

        self.right_panel = tk.Frame(self.shell, bg=PALETTE["panel"], padx=8, pady=8, width=360)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
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

    def _build_top_bars(self) -> None:
        title_bar = tk.Frame(self.root, bg=PALETTE["title_bar"], height=30)
        title_bar.pack(fill=tk.X)
        tk.Label(
            title_bar,
            text="Electional Software",
            bg=PALETTE["title_bar"],
            fg=PALETTE["top_bar_dark"],
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT, padx=16, pady=5)
        tk.Label(
            title_bar,
            text="Sidereal electional workspace",
            bg=PALETTE["title_bar"],
            fg=PALETTE["top_bar_dark"],
            font=("Segoe UI", 9),
        ).pack(side=tk.RIGHT, padx=16)

        menu = ttk.Frame(self.root, style="Top.TFrame", padding=(12, 5))
        menu.pack(fill=tk.X)
        for item in ("Chart", "Selected Chart", "Search", "Configuration", "Astro Mapping"):
            tk.Label(menu, text=item, bg=PALETTE["top_bar"], fg="white", font=("Segoe UI", 9, "bold"), padx=16).pack(side=tk.LEFT)

        ribbon = ttk.Frame(self.root, style="Ribbon.TFrame", padding=(12, 9))
        ribbon.pack(fill=tk.X)
        groups = (
            ("Chart", ("New Chart", "Save", "Ask")),
            ("Calculate", ("Transits", "Electional Search")),
            ("Advanced", ("Chart Data", "Health", "Focus Wheel", "Void Course", "Preferences")),
            ("Utility", ("Systems", "Bounds", "Lots", "Fixed Stars", "Heliacal Search")),
        )
        for group_title, items in groups:
            group = ttk.LabelFrame(ribbon, text=group_title, style="Ribbon.TLabelframe", padding=(9, 7))
            group.pack(side=tk.LEFT, padx=(0, 8))
            row = ttk.Frame(group, style="RibbonPanel.TFrame")
            row.pack()
            for item in items:
                self._ribbon_button(row, item).pack(side=tk.LEFT, padx=(0, 6))

    def _ribbon_button(self, parent: tk.Widget, label: str) -> tk.Frame:
        descriptions = {
            "New Chart": "Reset",
            "Save": "Report",
            "Ask": "Help",
            "Transits": "Refresh",
            "Electional Search": "Rank",
            "Chart Data": "Inspect",
            "Health": "Engine",
            "Focus Wheel": "F11",
            "Void Course": "Moon",
            "Preferences": "Setup",
            "Systems": "Zodiac",
            "Bounds": "Dignity",
            "Lots": "Parts",
            "Fixed Stars": "Stars",
            "Heliacal Search": "Visibility",
        }
        button = tk.Frame(
            parent,
            bg=PALETTE["button"],
            highlightbackground=PALETTE["button_line"],
            highlightthickness=1,
            padx=10,
            pady=7,
        )
        tk.Label(
            button,
            text=label,
            bg=PALETTE["button"],
            fg=PALETTE["text"],
            font=("Segoe UI", 8, "bold"),
            justify=tk.CENTER,
        ).pack()
        tk.Label(
            button,
            text=descriptions.get(label, "Open"),
            bg=PALETTE["button"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 7),
            justify=tk.CENTER,
        ).pack()
        self._bind_clickable(button, lambda: self._run_ribbon_action(label))
        return button

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

    def _render_summary_chips(self, snapshot: dict[str, object]) -> None:
        for child in self.context_chip_frame.winfo_children():
            child.destroy()
        for text in summary_chip_lines(snapshot):
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
            "Ask": self._show_quick_help,
            "Transits": self.calculate,
            "Electional Search": self.calculate,
            "Chart Data": self._show_chart_inspector,
            "Health": self._show_calculation_health_dialog,
            "Focus Wheel": self._toggle_focus_mode,
            "Void Course": self._show_void_course_dialog,
            "Preferences": self._show_preferences_dialog,
            "Systems": self._show_systems_dialog,
            "Bounds": self._show_bounds_dialog,
            "Lots": self._show_lots_reference_dialog,
            "Fixed Stars": self._show_fixed_stars_dialog,
            "Heliacal Search": self._show_heliacal_dialog,
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

    def _focus_detail_page(self, page_title: str) -> None:
        if not hasattr(self, "detail_notebook"):
            return
        for tab_id in self.detail_notebook.tabs():
            if self.detail_notebook.tab(tab_id, "text") == page_title:
                self.detail_notebook.select(tab_id)
                self.status_var.set(f"Opened {page_title} detail page.")
                return
        self.status_var.set(f"{page_title} detail page is not available yet.")

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
        self.status_var.set(f"{feature_name} is queued for a later build.")
        messagebox.showinfo(feature_name, f"{feature_name} is queued for a later build, but every visible ribbon action should now explain its purpose.")

    def _show_preferences_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Preferences")
        dialog.geometry("560x520")
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
        scan_var = tk.StringVar(value=self.scan_hours_var.get())
        step_var = tk.StringVar(value=self.step_minutes_var.get())
        minimum_var = tk.StringVar(value=self.minimum_score_var.get())
        max_results_var = tk.StringVar(value=self.max_results_var.get())

        self._dialog_combo_row(body, "Zodiac system", zodiac_var, list(ZODIAC_SYSTEM_NAMES))
        self._dialog_combo_row(body, "House system", house_var, list(HOUSE_SYSTEM_NAMES))
        self._dialog_combo_row(body, "Objective", objective_var, list(OBJECTIVES))
        self._dialog_combo_row(body, "Electional model", preset_var, [preset.name for preset in ELECTIONAL_PRESETS])

        search = ttk.LabelFrame(body, text="Search Defaults", style="Panel.TLabelframe", padding=10)
        search.pack(fill=tk.X, pady=(10, 0))
        search.columnconfigure(0, weight=1)
        search.columnconfigure(1, weight=1)
        self._dialog_entry_row(search, "Scan hours", scan_var, 0, 0)
        self._dialog_entry_row(search, "Step minutes", step_var, 0, 1)
        self._dialog_entry_row(search, "Minimum score", minimum_var, 1, 0)
        self._dialog_entry_row(search, "Max results", max_results_var, 1, 1)

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
                scan_var.get(),
                step_var.get(),
                minimum_var.get(),
                max_results_var.get(),
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
                scan_var.get(),
                step_var.get(),
                minimum_var.get(),
                max_results_var.get(),
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
        scan_hours: str,
        step_minutes: str,
        minimum_score: str,
        max_results: str,
    ) -> None:
        errors = validate_search_inputs(scan_hours, step_minutes, minimum_score, max_results)
        if errors:
            messagebox.showerror("Preference validation failed", "Fix these search defaults:\n" + "\n".join(f"- {error}" for error in errors))
            return
        self.zodiac_system_var.set(get_zodiac_system(zodiac).name)
        self.house_system_var.set(get_house_system(house).name)
        self.objective_var.set(objective if objective in OBJECTIVES else OBJECTIVES[0])
        self.preset_var.set(preset if preset in self.presets_by_name else ELECTIONAL_PRESETS[1].name)
        self.scan_hours_var.set(scan_hours)
        self.step_minutes_var.set(step_minutes)
        self.minimum_score_var.set(minimum_score)
        self.max_results_var.set(max_results)
        self._sync_aspects_to_preset()
        self._update_search_summary()
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
            "Contacts within 1 degree",
            *(contact_lines or ["No fixed-star conjunctions within 1 degree."]),
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
            "Note: this is a screening view based on angular separation from the Sun.",
            "A full heliacal visibility model will later add latitude, horizon, magnitude, and twilight rules.",
        ]
        self._show_text_dialog("Heliacal Search", "\n".join(lines))
        self.status_var.set("Opened solar elongation screening.")

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
            f"{fixed_star_contacts or 'No fixed-star conjunctions within 1 degree.'}\n\n"
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
        card = ttk.Frame(self.left_panel, style="Panel.TFrame", padding=12)
        card.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(card, text="NATAL CHART", style="Accent.TLabel").pack(anchor="w")
        ttk.Label(card, text="Natal Chart", background=PALETTE["panel"], font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(6, 4))
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
        self.max_results_var = tk.StringVar(value=str(state.get("max_results") or DEFAULT_MAX_RESULTS))
        self.search_summary_var = tk.StringVar(value="")
        self.validation_var = tk.StringVar(value="Validation: waiting for first calculation")

        timing_box = ttk.LabelFrame(self.left_panel, text="Timing", style="Panel.TLabelframe", padding=10)
        timing_box.pack(fill=tk.X, pady=(0, 10))
        self._labeled_entry(timing_box, "Election date", self.date_var)
        self._labeled_entry(timing_box, "Start time", self.time_var)
        quick_time = ttk.Frame(timing_box, style="Panel.TFrame")
        quick_time.pack(fill=tk.X, pady=(7, 0))
        for label, hours in (("-2h", -2), ("-1h", -1), ("Now", 0), ("+1h", 1), ("+2h", 2)):
            ttk.Button(
                quick_time,
                text=label,
                command=(self._set_current_time if hours == 0 else lambda delta=hours: self._shift_time(delta)),
            ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        fine_time = ttk.Frame(timing_box, style="Panel.TFrame")
        fine_time.pack(fill=tk.X, pady=(5, 0))
        for label, minutes in (("-15m", -15), ("-5m", -5), ("+5m", 5), ("+15m", 15)):
            ttk.Button(
                fine_time,
                text=label,
                command=lambda delta=minutes: self._shift_time_minutes(delta),
            ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))

        location_box = ttk.LabelFrame(self.left_panel, text="Location", style="Panel.TLabelframe", padding=10)
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
            value=f"{len(self.user_locations)} custom saved location{'s' if len(self.user_locations) != 1 else ''}."
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
        location_actions = ttk.Frame(location_box, style="Panel.TFrame")
        location_actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(location_actions, text="Save/Update", command=self._save_location_preset).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        ttk.Button(location_actions, text="Local", command=self._use_default_location).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        ttk.Button(location_actions, text="Forget", command=self._forget_location_preset).pack(side=tk.LEFT, expand=True, fill=tk.X)

        model_box = ttk.LabelFrame(self.left_panel, text="Election Model", style="Panel.TLabelframe", padding=10)
        model_box.pack(fill=tk.X, pady=(0, 10))
        self._labeled_combo(model_box, "Objective", self.objective_var, list(OBJECTIVES))
        self._labeled_combo(model_box, "Zodiac system", self.zodiac_system_var, list(ZODIAC_SYSTEM_NAMES))
        self._labeled_combo(model_box, "House system", self.house_system_var, list(HOUSE_SYSTEM_NAMES))
        self.preset_combo = self._labeled_combo(model_box, "Electional model", self.preset_var, [preset.name for preset in ELECTIONAL_PRESETS])
        self.preset_combo.bind("<<ComboboxSelected>>", self._sync_aspects_to_preset)

        search_box = ttk.LabelFrame(model_box, text="Search range", style="Panel.TLabelframe", padding=8)
        search_box.pack(fill=tk.X, pady=(10, 0))
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
        self._labeled_entry(result_row, "Max results", self.max_results_var, compact=True, column=1)
        presets = ttk.Frame(search_box, style="Panel.TFrame")
        presets.pack(fill=tk.X, pady=(8, 0))
        for label, hours, step in (("6h", "6", "60"), ("12h", "12", "60"), ("24h", "24", "120")):
            ttk.Button(presets, text=label, command=lambda scan=hours, minutes=step: self._set_search_preset(scan, minutes)).pack(
                side=tk.LEFT,
                expand=True,
                fill=tk.X,
                padx=(0, 4),
            )
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

        aspect_box = ttk.LabelFrame(model_box, text="Aspect focus", style="Panel.TLabelframe", padding=8)
        aspect_box.pack(fill=tk.X, pady=(10, 12))
        preset = ELECTIONAL_PRESETS[1]
        session_aspects = state.get("aspects") if isinstance(state.get("aspects"), dict) else {}
        for aspect_id in ("conjunction", "trine", "sextile", "square", "opposition"):
            default_value = bool(session_aspects.get(aspect_id, aspect_id in preset.aspect_ids))
            var = tk.BooleanVar(value=default_value)
            self.aspect_vars[aspect_id] = var
            ttk.Checkbutton(aspect_box, text=aspect_id.title(), variable=var).pack(anchor="w", pady=2)

        ttk.Button(model_box, text="Calculate Election", command=self.calculate).pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            self.left_panel,
            textvariable=self.validation_var,
            bg=PALETTE["panel"],
            fg=PALETTE["score"],
            justify=tk.LEFT,
            wraplength=250,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(10, 0))

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
        entry = tk.Entry(container, textvariable=variable, bg=PALETTE["panel_alt"], relief=tk.SOLID, bd=1, font=("Segoe UI", 10, "bold"))
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
        save_user_locations(self.user_locations)
        self._refresh_location_choices()
        fallback = default_location_for_timezone()
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
        self._update_search_summary()

    def _update_search_summary(self) -> None:
        try:
            config = build_search_config_from_text(
                self.scan_hours_var.get(),
                self.step_minutes_var.get(),
                self.minimum_score_var.get(),
                self.max_results_var.get(),
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

        score_card = ttk.Frame(header, style="Panel.TFrame", padding=(10, 8))
        score_card.grid(row=0, column=1, rowspan=4, sticky="e")
        self.score_var = tk.StringVar(value="--")
        ttk.Label(score_card, textvariable=self.score_var, style="Score.TLabel").pack()
        self.score_band_var = tk.StringVar(value="waiting")
        ttk.Label(score_card, textvariable=self.score_band_var, style="Small.TLabel").pack()

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
            height=640,
            bg=PALETTE["canvas"],
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
        )
        self.canvas.grid(row=3, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._schedule_redraw)

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
        for label, command in (
            ("Interpretation", lambda: self._focus_detail_page("Window")),
            ("Timing", lambda: self._focus_detail_page("Timing")),
            ("Aspects", lambda: self._focus_detail_page("Aspects")),
            ("Aspectarian", lambda: self._focus_detail_page("Aspectarian")),
            ("Conditions", lambda: self._focus_detail_page("Conditions")),
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

    def _toggle_focus_mode(self) -> None:
        self._set_focus_mode(not self.focus_mode)

    def _pack_workspace_panels(self) -> None:
        self.left_panel.pack_forget()
        self.center_panel.pack_forget()
        self.right_panel.pack_forget()
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

    def _set_focus_mode(self, enabled: bool) -> None:
        self.focus_mode = enabled
        if enabled:
            self.left_panel.pack_forget()
            self.right_panel.pack_forget()
            self.center_panel.pack_forget()
            self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=0)
            self.focus_mode_button_var.set("Exit Focus")
            self.status_var.set("Focus wheel mode: side panels hidden. Press F11 to restore.")
        else:
            self._pack_workspace_panels()
            self.focus_mode_button_var.set("Focus Wheel")
            self.status_var.set("Focus wheel mode off: side panels restored.")
        self._schedule_redraw()

    def _apply_clean_wheel_view(self) -> None:
        self.show_aspects_var.set(True)
        self.show_lots_var.set(False)
        self.show_nodes_var.set(False)
        self.show_fixed_stars_var.set(False)
        self.compact_wheel_var.set(True)
        self._display_option_changed()

    def _apply_full_wheel_view(self) -> None:
        self.show_aspects_var.set(True)
        self.show_lots_var.set(True)
        self.show_nodes_var.set(True)
        self.show_fixed_stars_var.set(True)
        self.compact_wheel_var.set(False)
        self._display_option_changed()

    def _state_card(self, parent: tk.Widget, title: str, variable: tk.StringVar, column: int, accent_color: str) -> None:
        card = tk.Frame(parent, bg=PALETTE["panel_alt"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=9, pady=6)
        card.grid(row=0, column=column, sticky="ew", padx=(0, 6) if column < 3 else (0, 0))
        tk.Label(card, text=title, bg=PALETTE["panel_alt"], fg=accent_color, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=170, justify=tk.LEFT).pack(anchor="w")

    def _build_right_panel(self) -> None:
        self._build_metric_panel()
        self._build_window_list_panel()
        self.detail_notebook = ttk.Notebook(self.right_panel)
        self.detail_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 9))
        self.summary_text = self._text_tab("Summary")
        self.window_detail_text = self._text_tab("Window")
        self.interpretation_text = self._text_tab("Focus")
        self.score_detail_text = self._text_tab("Score")
        self.conditions_text = self._text_tab("Conditions")
        self.rules_text = self._text_tab("Rules")
        self.cusps_text = self._text_tab("Cusps")
        self.lots_text = self._text_tab("Lots")
        self.nodes_text = self._text_tab("Nodes")
        self.timing_text = self._text_tab("Timing")
        self.planets_text = self._text_tab("Planets")
        self.aspects_text = self._text_tab("Aspects")
        self.aspectarian_text = self._text_tab("Aspectarian")
        self.fixed_stars_text = self._text_tab("Fixed Stars")
        self.log_text = self._text_tab("Log")
        self._refresh_event_log()

    def _build_metric_panel(self) -> None:
        frame = ttk.LabelFrame(self.right_panel, text="Election Scoreboard", style="Panel.TLabelframe", padding=7)
        frame.pack(fill=tk.X, pady=(0, 9))
        metrics = (
            ("score", "Score", PALETTE["metric_bg"], PALETTE["score"]),
            ("support", "Support", "#e7f4ec", "#087a48"),
            ("stress", "Stress", "#f9e5ea", PALETTE["stress"]),
            ("angular", "Angular", "#edf0fb", PALETTE["top_bar"]),
            ("stars", "Stars", "#eef3ff", "#3f5f9c"),
            ("phase", "Moon", "#f4eefb", "#6d4d8f"),
            ("hour", "Hour", "#edf8ee", "#407144"),
            ("rules", "Rules", "#fff0e7", PALETTE["warning"]),
        )
        for index, (key, label, bg_color, value_color) in enumerate(metrics):
            var = tk.StringVar(value="--")
            self.metric_vars[key] = var
            card = tk.Frame(
                frame,
                bg=bg_color,
                highlightbackground=PALETTE["panel_line"],
                highlightthickness=1,
                padx=8,
                pady=6,
            )
            card.grid(row=index // 2, column=index % 2, sticky="ew", padx=3, pady=3)
            tk.Label(card, text=label, bg=bg_color, fg=PALETTE["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
            tk.Label(card, textvariable=var, bg=bg_color, fg=value_color, font=("Segoe UI", 15, "bold")).pack(anchor="w")
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
                f"Results: {result_note}    System: {zodiac_system.name} / {house_system.name}    Validation: Pass"
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
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=9,
            pady=7,
        )
        card.pack(fill=tk.X, padx=4, pady=(4, 6))
        self.window_cards.append(card)
        header = tk.Frame(card, bg=card["bg"])
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=f"#{index + 1}",
            bg=PALETTE["top_bar"],
            fg="white",
            font=("Segoe UI", 8, "bold"),
            padx=6,
            pady=1,
        ).pack(side=tk.LEFT, padx=(0, 7))
        tk.Label(
            header,
            text=str(window["time"]),
            bg=card["bg"],
            fg=PALETTE["accent"],
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text=f"{score_band_label(int(window['score']))} {window['score']}",
            bg=card["bg"],
            fg=PALETTE["score"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
        ).pack(side=tk.RIGHT)
        tk.Label(
            card,
            text=str(window.get("title", "Electional window")),
            bg=card["bg"],
            fg=PALETTE["text"],
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(5, 1))
        tk.Label(
            card,
            text=str(window.get("note", "")),
            bg=card["bg"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=280,
            justify=tk.LEFT,
        ).pack(fill=tk.X)
        support = sum(1 for aspect in window["detectedAspects"] if aspect["tone"] == "support")
        stress = sum(1 for aspect in window["detectedAspects"] if aspect["tone"] == "stress")
        fixed_stars = fixed_star_contact_count(window)
        tag_row = tk.Frame(card, bg=card["bg"])
        tag_row.pack(fill=tk.X, pady=(6, 0))
        for text, fg, bg in (
            (f"+{support} support", PALETTE["support"], "#e6f5ef"),
            (f"!{stress} stress", PALETTE["stress"], "#fae6ea"),
            (f"{fixed_stars} stars", "#3f5f9c", "#eef3ff"),
        ):
            tk.Label(
                tag_row,
                text=text,
                bg=bg,
                fg=fg,
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=2,
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
        width = max(self.canvas.winfo_width(), int(self.canvas.cget("width")))
        height = max(self.canvas.winfo_height(), int(self.canvas.cget("height")))
        cx = width / 2
        cy = height / 2
        side_padding = 70 if not self.compact_wheel_var.get() and self.show_fixed_stars_var.get() else 34
        vertical_padding = 42
        fit_width = max(260, width - side_padding * 2)
        fit_height = max(260, height - vertical_padding * 2)
        outer = max(150, min(fit_width, fit_height) / 2)
        zodiac_inner = outer * 0.84
        house_inner = outer * (0.50 if self.compact_wheel_var.get() else 0.44)
        aspect_radius = outer * 0.44

        self._draw_grid(width, height)
        self.canvas.create_oval(
            cx - outer + 6,
            cy - outer + 8,
            cx + outer + 6,
            cy + outer + 8,
            fill="#c9c2ad",
            outline="",
        )
        self.canvas.create_oval(
            cx - outer,
            cy - outer,
            cx + outer,
            cy + outer,
            fill=PALETTE["chart_disc"],
            outline=PALETTE["chart_line"],
            width=2,
        )

        ascendant = next(angle for angle in snapshot["angles"] if angle["id"] == "asc")
        asc_lon = float(ascendant["longitude"])
        self._draw_degree_ticks(cx, cy, outer, zodiac_inner, asc_lon)

        for index, sign in enumerate(SIGN_LABELS):
            start = wheel_degrees(index * 30, asc_lon)
            self.canvas.create_arc(
                cx - outer,
                cy - outer,
                cx + outer,
                cy + outer,
                start=start,
                extent=-30,
                fill=SIGN_COLORS[index],
                outline=PALETTE["chart_line"],
                width=1,
            )
            self.canvas.create_arc(
                cx - zodiac_inner,
                cy - zodiac_inner,
                cx + zodiac_inner,
                cy + zodiac_inner,
                start=start,
                extent=-30,
                fill=PALETTE["chart_disc"],
                outline=PALETTE["chart_line"],
                width=1,
            )
            label_angle = wheel_degrees(index * 30 + 15, asc_lon)
            lx, ly = _polar(cx, cy, outer * 0.92, label_angle)
            self.canvas.create_text(lx, ly, text=sign, fill="#17234f", font=("Segoe UI", 13 if self.compact_wheel_var.get() else 15, "bold"))

        self.canvas.create_oval(cx - zodiac_inner, cy - zodiac_inner, cx + zodiac_inner, cy + zodiac_inner, outline=PALETTE["chart_line"], width=2)
        self.canvas.create_oval(
            cx - house_inner,
            cy - house_inner,
            cx + house_inner,
            cy + house_inner,
            fill=PALETTE["chart_inner"],
            outline=PALETTE["chart_line"],
            width=2,
        )
        self.canvas.create_oval(
            cx - aspect_radius,
            cy - aspect_radius,
            cx + aspect_radius,
            cy + aspect_radius,
            outline="#9aa9ad",
            width=1,
            dash=(4, 5),
        )
        self.canvas.create_oval(cx - 72, cy - 72, cx + 72, cy + 72, outline=PALETTE["chart_line"], width=2)

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
            self.canvas.create_text(lx, ly, text=str(cusp["house"]), fill=PALETTE["muted"], font=("Segoe UI", 10 if self.compact_wheel_var.get() else 12, "bold"))

        if self.show_aspects_var.get():
            self._draw_aspects(snapshot, cx, cy, aspect_radius, asc_lon)
        self._draw_angles(snapshot, cx, cy, outer, asc_lon)
        if self.show_fixed_stars_var.get() and not self.compact_wheel_var.get():
            self._draw_fixed_stars(snapshot, cx, cy, asc_lon, outer)
        self._draw_planets(snapshot, cx, cy, asc_lon, outer)
        if self.show_lots_var.get() and not self.compact_wheel_var.get():
            self._draw_lots(snapshot, cx, cy, asc_lon, outer)
        if self.show_nodes_var.get() and not self.compact_wheel_var.get():
            self._draw_nodes(snapshot, cx, cy, asc_lon, outer)
        self._draw_center_hub(cx, cy, snapshot)

    def _draw_center_hub(self, cx: float, cy: float, snapshot: dict[str, object]) -> None:
        self.canvas.create_oval(cx - 58, cy - 58, cx + 58, cy + 58, fill=PALETTE["center_hub"], outline="#b9c2c8", width=2)
        self.canvas.create_text(cx, cy - 8, text=f"Score {snapshot['score']}", fill=PALETTE["top_bar_dark"], font=("Segoe UI", 13 if self.compact_wheel_var.get() else 15, "bold"))
        self.canvas.create_text(cx, cy + 15, text=score_band_label(int(snapshot["score"])), fill=PALETTE["accent"], font=("Segoe UI", 8 if self.compact_wheel_var.get() else 9, "bold"))

    def _draw_degree_ticks(self, cx: float, cy: float, outer: float, zodiac_inner: float, asc_lon: float) -> None:
        for degree in range(0, 360, 5):
            angle = wheel_degrees(degree, asc_lon)
            tick_length = 16 if degree % 30 == 0 else 8
            x1, y1 = _polar(cx, cy, zodiac_inner, angle)
            x2, y2 = _polar(cx, cy, min(outer, zodiac_inner + tick_length), angle)
            width = 2 if degree % 30 == 0 else 1
            self.canvas.create_line(x1, y1, x2, y2, fill=PALETTE["chart_line"], width=width)

    def _draw_grid(self, width: int, height: int) -> None:
        for x in range(0, width, 24):
            self.canvas.create_line(x, 0, x, height, fill=PALETTE["canvas_grid"], width=1)
        for y in range(0, height, 24):
            self.canvas.create_line(0, y, width, y, fill=PALETTE["canvas_grid"], width=1)

    def _draw_angles(self, snapshot: dict[str, object], cx: float, cy: float, outer: float, asc_lon: float) -> None:
        for angle in snapshot["angles"]:
            degrees = wheel_degrees(float(angle["longitude"]), asc_lon)
            x1, y1 = _polar(cx, cy, outer * 0.33, degrees)
            x2, y2 = _polar(cx, cy, outer, degrees)
            self.canvas.create_line(x1, y1, x2, y2, fill=PALETTE["accent"], width=3)
            lx, ly = _polar(cx, cy, outer - 20, degrees)
            self.canvas.create_text(lx, ly, text=angle["shortName"], fill=PALETTE["top_bar"], font=("Segoe UI", 14, "bold"))

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
            x, y = _polar(cx, cy, outer * 0.985, degrees)
            label_x, label_y = _polar(cx, cy, outer * 1.045, degrees)
            active_contact = str(star.get("name")) in contacted
            size = 7 if active_contact else 5
            fill = "#fff8d8" if active_contact else "#f5fbff"
            outline = PALETTE["warning"] if active_contact else "#7893a4"
            star_tag = f"star:{star['id']}"
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
                outline=outline,
                width=2 if active_contact else 1,
                tags=("fixed-star-marker", star_tag),
            )
            self.canvas.create_text(
                label_x,
                label_y,
                text=star_abbreviation(str(star["name"])),
                fill=outline,
                font=("Segoe UI", 7, "bold"),
                tags=("fixed-star-marker", star_tag),
            )
            self.canvas.tag_bind(star_tag, "<Button-1>", lambda _event, star_id=str(star["id"]): self._select_fixed_star_by_id(star_id))
            self.canvas.tag_bind(star_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(star_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_planets(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        for index, planet in enumerate(snapshot["positions"]):
            degrees = wheel_degrees(float(planet["longitude"]), asc_lon)
            stack = 2 if self.compact_wheel_var.get() else 3
            radius = outer * 0.74 - (index % stack) * (14 if self.compact_wheel_var.get() else 18)
            x, y = _polar(cx, cy, radius, degrees)
            fill = PALETTE["panel_alt"] if planet.get("isPresetPoint") else "#dfe2d2"
            outline = PALETTE["top_bar"] if planet.get("isAngular") else PALETTE["chart_line"]
            planet_tag = f"planet:{planet['id']}"
            marker_size = 12 if self.compact_wheel_var.get() else 14
            self.canvas.create_oval(x - marker_size, y - marker_size, x + marker_size, y + marker_size, fill=fill, outline=outline, width=2, tags=("planet-marker", planet_tag))
            self.canvas.create_text(
                x,
                y,
                text=planet_abbreviation(str(planet["name"])),
                fill=PALETTE["top_bar_dark"],
                font=("Segoe UI", 8 if self.compact_wheel_var.get() else 9, "bold"),
                tags=("planet-marker", planet_tag),
            )
            self.canvas.tag_bind(planet_tag, "<Button-1>", lambda _event, planet_id=str(planet["id"]): self._select_planet_by_id(planet_id))
            self.canvas.tag_bind(planet_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(planet_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_lots(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        for index, lot in enumerate(snapshot.get("lots", [])):
            degrees = wheel_degrees(float(lot["longitude"]), asc_lon)
            radius = outer * (0.48 + (index % 4) * 0.055)
            x, y = _polar(cx, cy, radius, degrees)
            lot_tag = f"lot:{lot['id']}"
            self.canvas.create_rectangle(
                x - 13,
                y - 13,
                x + 13,
                y + 13,
                fill="#f7ead1",
                outline=PALETTE["accent"],
                width=2,
                tags=("lot-marker", lot_tag),
            )
            self.canvas.create_text(
                x,
                y,
                text=lot_abbreviation(str(lot["name"])),
                fill=PALETTE["top_bar_dark"],
                font=("Segoe UI", 8, "bold"),
                tags=("lot-marker", lot_tag),
            )
            self.canvas.tag_bind(lot_tag, "<Button-1>", lambda _event, lot_id=str(lot["id"]): self._select_lot_by_id(lot_id))
            self.canvas.tag_bind(lot_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(lot_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_nodes(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        for index, node in enumerate(snapshot.get("lunarNodes", [])):
            degrees = wheel_degrees(float(node["longitude"]), asc_lon)
            radius = outer * (0.36 + (index % 2) * 0.055)
            x, y = _polar(cx, cy, radius, degrees)
            node_tag = f"node:{node['id']}"
            self.canvas.create_polygon(
                x,
                y - 13,
                x + 12,
                y + 10,
                x - 12,
                y + 10,
                fill="#e8f5f7",
                outline=PALETTE["accent"],
                width=2,
                tags=("node-marker", node_tag),
            )
            self.canvas.create_text(
                x,
                y + 2,
                text=node_abbreviation(str(node["name"])),
                fill=PALETTE["top_bar_dark"],
                font=("Segoe UI", 8, "bold"),
                tags=("node-marker", node_tag),
            )
            self.canvas.tag_bind(node_tag, "<Button-1>", lambda _event, node_id=str(node["id"]): self._select_node_by_id(node_id))
            self.canvas.tag_bind(node_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
            self.canvas.tag_bind(node_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_aspects(self, snapshot: dict[str, object], cx: float, cy: float, radius: float, asc_lon: float) -> None:
        positions = {planet["name"]: planet for planet in snapshot["positions"]}
        for aspect in snapshot["detectedAspects"][:10]:
            body_a, body_b = aspect["bodies"]
            if body_a not in positions or body_b not in positions:
                continue
            angle_a = wheel_degrees(float(positions[body_a]["longitude"]), asc_lon)
            angle_b = wheel_degrees(float(positions[body_b]["longitude"]), asc_lon)
            x1, y1 = _polar(cx, cy, radius, angle_a)
            x2, y2 = _polar(cx, cy, radius, angle_b)
            color = PALETTE["support"] if aspect["tone"] == "support" else PALETTE["stress"]
            self.canvas.create_line(x1, y1, x2, y2, fill=color, width=2)

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
        self.metric_vars["support"].set(str(support))
        self.metric_vars["stress"].set(str(stress))
        self.metric_vars["angular"].set(str(angular))
        self.metric_vars["stars"].set(str(fixed_star_contact_count(snapshot)))
        phase = snapshot.get("lunarPhase", {})
        phase_name = str(phase.get("name", "n/a")) if isinstance(phase, dict) else "n/a"
        self.metric_vars["phase"].set(phase_name.replace(" Moon", ""))
        planetary_hour = snapshot.get("planetaryHour", {})
        self.metric_vars["hour"].set(str(planetary_hour.get("hourRuler", "n/a")) if isinstance(planetary_hour, dict) else "n/a")
        rule_evaluations = snapshot.get("ruleEvaluations", {})
        rules = rule_evaluations.get("rules", []) if isinstance(rule_evaluations, dict) else []
        self.metric_vars["rules"].set(str(len(rules) if isinstance(rules, list) else 0))

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
            self.interpretation_text,
            self._selected_window_interpretation(snapshot, selected_rank, len(windows)),
        )
        body_names = [str(planet["name"]) for planet in snapshot["positions"]]
        body_names.extend(str(lot["name"]) for lot in snapshot.get("lots", []))
        body_names.extend(str(node["name"]) for node in snapshot.get("lunarNodes", []))
        body_names.extend(str(star["name"]) for star in snapshot.get("fixedStars", []))
        self.focus_body_combo.configure(values=body_names)
        if self.focus_body_var.get() not in body_names and body_names:
            self.focus_body_var.set(body_names[0])

        self._set_text(
            self.score_detail_text,
            (
                f"Score: {snapshot['score']}\n"
                f"{format_score_breakdown(snapshot)}\n\n"
                "Reason Lines\n"
                + "\n".join(score_reason_lines(snapshot))
            ),
        )
        self._set_text(self.conditions_text, "\n".join(condition_lines(snapshot)))
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

        planet_lines = []
        for planet in snapshot["positions"]:
            angular = " angular" if planet.get("isAngular") else ""
            dignity = format_dignity_summary(planet)
            planet_lines.append(
                f"{planet['name']:<8} {format_position(planet):<15} H{planet['house']:<2} "
                f"{dignity}; {format_motion_summary(planet)}{angular}"
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
                "Contacts within 1 degree\n"
                + ("\n".join(contact_lines) if contact_lines else "No fixed-star conjunctions within 1 degree.")
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
        self.focus_body_var.set(str(lot["name"]))
        text = (
            f"{lot['name']}: {format_position(lot)} in House {lot['house']}.\n"
            f"Formula: {lot['formula']} ({lot['sect']} chart).\n"
            f"Topic: {lot.get('topic', 'n/a')}.\n"
            f"Closest angle: {lot['closestAngle']['shortName']} at {lot['closestAngle']['distance']:.1f} deg."
        )
        self._set_text(self.interpretation_text, text)
        self.status_var.set(f"Focused {lot['name']} at {format_position(lot)}.")
        self._log_event(f"Focused lot: {lot['name']} {format_position(lot)}")

    def _show_node_focus(self, node: dict[str, object]) -> None:
        self.focus_body_var.set(str(node["name"]))
        text = (
            f"{node['name']}: {format_position(node)} in House {node['house']}.\n"
            f"Calculation: {node.get('calculation', 'node calculation')}.\n"
            f"Closest angle: {node['closestAngle']['shortName']} at {node['closestAngle']['distance']:.1f} deg.\n"
            "Electional use: nodes can mark karmic, public, or fated-feeling emphasis; confirm by aspects and house topic."
        )
        self._set_text(self.interpretation_text, text)
        self.status_var.set(f"Focused {node['name']} at {format_position(node)}.")
        self._log_event(f"Focused node: {node['name']} {format_position(node)}")

    def _show_fixed_star_focus(self, star: dict[str, object]) -> None:
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
            f"Contacts: {', '.join(contact_lines) if contact_lines else 'No conjunctions within 1 degree.'}"
        )
        self._set_text(self.interpretation_text, text)
        self.status_var.set(f"Focused fixed star {star['name']} at {format_position(star)}.")
        self._log_event(f"Focused fixed star: {star['name']} {format_position(star)}")

    def _show_planet_focus(self, planet: dict[str, object]) -> None:
        self.focus_body_var.set(str(planet["name"]))
        self._set_text(self.interpretation_text, format_planet_focus(planet, self.selected_window["detectedAspects"]))
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
            "max_results": self.max_results_var.get(),
            "display_options": {
                "show_aspects": self.show_aspects_var.get(),
                "show_lots": self.show_lots_var.get(),
                "show_nodes": self.show_nodes_var.get(),
                "show_fixed_stars": self.show_fixed_stars_var.get(),
                "compact_wheel": self.compact_wheel_var.get(),
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
