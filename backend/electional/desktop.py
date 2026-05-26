"""Native desktop application shell for Electional Software."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .chart import build_election_report, format_angle, format_position
from .locations import LOCATION_PRESETS, LocationPreset, get_location
from .presets import ELECTIONAL_PRESETS
from .time_utils import normalize_time_text

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
OBJECTIVES = ("Launch or publish", "Meeting or negotiation", "Creative work", "Relationship timing", "Travel departure")
DEFAULT_TIMEZONE = "America/Los_Angeles"
SESSION_PATH = Path.cwd() / ".electional-session.json"

PALETTE = {
    "app_bg": "#edf1f5",
    "title_bar": "#ef9eab",
    "top_bar": "#233e7d",
    "top_bar_dark": "#152858",
    "ribbon": "#f4c2cb",
    "ribbon_panel": "#fff0f3",
    "panel": "#fff4cb",
    "panel_alt": "#fff9df",
    "panel_line": "#6f7783",
    "canvas": "#eee6ca",
    "canvas_grid": "#ddd5bd",
    "chart_disc": "#e3dcc7",
    "chart_inner": "#f7edd1",
    "chart_line": "#646b71",
    "text": "#151923",
    "muted": "#4e5965",
    "accent": "#006875",
    "score": "#005f67",
    "support": "#148b9b",
    "stress": "#d75a7b",
    "button": "#fff9df",
    "button_hover": "#ffffff",
    "button_line": "#9d7b9a",
    "selected": "#dbeff2",
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


def wheel_degrees(longitude: float, ascendant_longitude: float) -> float:
    """Convert ecliptic longitude into desktop chart-wheel screen degrees."""

    return 180 - ((longitude - ascendant_longitude) % 360)


def _polar(center_x: float, center_y: float, radius: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees)
    return center_x + math.cos(radians) * radius, center_y - math.sin(radians) * radius


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

    try:
        ZoneInfo(timezone_text.strip() or "UTC")
    except Exception:
        errors.append("Time zone must be a valid IANA name like America/Los_Angeles.")

    return errors


def build_custom_location(name: str, latitude_text: str, longitude_text: str, timezone_text: str) -> LocationPreset:
    label = name.strip() or "Custom Location"
    return LocationPreset("custom", label, float(latitude_text), float(longitude_text), timezone_text.strip() or "UTC")


def default_location_for_timezone(timezone_name: str = DEFAULT_TIMEZONE) -> LocationPreset:
    for location in LOCATION_PRESETS:
        if location.timezone == timezone_name:
            return location
    return LOCATION_PRESETS[0]


def shift_local_datetime(date_text: str, time_text: str, timezone_name: str, hours: int) -> tuple[str, str]:
    local_time = datetime.strptime(f"{date_text} {normalize_time_text(time_text)}", "%Y-%m-%d %H:%M")
    zoned = local_time.replace(tzinfo=ZoneInfo(timezone_name or "UTC"))
    shifted = zoned + timedelta(hours=hours)
    return shifted.strftime("%Y-%m-%d"), shifted.strftime("%H:%M")


def format_window_label(rank: int, window: dict[str, object]) -> str:
    support = sum(1 for aspect in window["detectedAspects"] if aspect["tone"] == "support")
    stress = sum(1 for aspect in window["detectedAspects"] if aspect["tone"] == "stress")
    return f"{rank}. {window['time']}  Score {window['score']}  +{support}/!{stress}  {window['title']}"


def load_session_state(path: Path = SESSION_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_session_state(state: dict[str, Any], path: Path = SESSION_PATH) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def clean_session_state(state: dict[str, Any]) -> dict[str, Any]:
    default_location = default_location_for_timezone()
    date_text = str(state.get("date") or date.today().isoformat())
    time_text = str(state.get("time") or "09:00")
    location_name = str(state.get("location_name") or default_location.name)
    latitude = str(state.get("latitude") or f"{default_location.latitude:.4f}")
    longitude = str(state.get("longitude") or f"{default_location.longitude:.4f}")
    timezone = str(state.get("timezone") or default_location.timezone)
    if validate_election_inputs(date_text, time_text, latitude, longitude, timezone):
        date_text = date.today().isoformat()
        time_text = "09:00"
        location_name = default_location.name
        latitude = f"{default_location.latitude:.4f}"
        longitude = f"{default_location.longitude:.4f}"
        timezone = default_location.timezone

    preset_names = {preset.name for preset in ELECTIONAL_PRESETS}
    objective = str(state.get("objective") or OBJECTIVES[0])
    preset = str(state.get("preset") or ELECTIONAL_PRESETS[1].name)
    aspects = state.get("aspects") if isinstance(state.get("aspects"), dict) else {}

    return {
        "date": date_text,
        "time": normalize_time_text(time_text),
        "location_preset": str(state.get("location_preset") or location_name),
        "location_name": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "objective": objective if objective in OBJECTIVES else OBJECTIVES[0],
        "preset": preset if preset in preset_names else ELECTIONAL_PRESETS[1].name,
        "aspects": {str(key): bool(value) for key, value in aspects.items()},
    }


class ElectionalDesktopApp:
    """Tkinter desktop UI that talks directly to the Python electional engine."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Electional Software")
        self.root.geometry("1440x900")
        self.root.minsize(1160, 760)

        self.locations_by_name = {location.name: location for location in LOCATION_PRESETS}
        self.presets_by_name = {preset.name: preset for preset in ELECTIONAL_PRESETS}
        self.aspect_vars: dict[str, tk.BooleanVar] = {}
        self.current_location: LocationPreset | None = None
        self.current_windows: list[dict[str, object]] = []
        self.selected_window: dict[str, object] | None = None
        self._resize_job: str | None = None
        self.session_state = clean_session_state(load_session_state())

        self._configure_style()
        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.calculate()

    def _configure_style(self) -> None:
        self.root.configure(bg=PALETTE["app_bg"])
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=PALETTE["panel"])
        style.configure("Top.TFrame", background=PALETTE["top_bar"])
        style.configure("Ribbon.TFrame", background=PALETTE["ribbon"])
        style.configure("Workbench.TFrame", background=PALETTE["app_bg"])
        style.configure("Panel.TFrame", background=PALETTE["panel"], relief="solid", borderwidth=1)
        style.configure("RibbonPanel.TFrame", background=PALETTE["ribbon_panel"], relief="ridge", borderwidth=1)
        style.configure("Panel.TLabelframe", background=PALETTE["panel"], bordercolor=PALETTE["panel_line"])
        style.configure("Panel.TLabelframe.Label", background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Segoe UI", 9, "bold"))
        style.configure("Title.TLabel", background=PALETTE["panel"], foreground=PALETTE["text"], font=("Segoe UI", 18, "bold"))
        style.configure("Small.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
        style.configure("Accent.TLabel", background=PALETTE["panel"], foreground=PALETTE["accent"], font=("Segoe UI", 9, "bold"))
        style.configure("Score.TLabel", background=PALETTE["panel_alt"], foreground=PALETTE["score"], font=("Segoe UI", 30, "bold"))
        style.configure("TButton", background="#f1c5ca", foreground=PALETTE["text"], padding=(12, 6), bordercolor="#8b6a82")
        style.map("TButton", background=[("active", "#f8d7db")])
        style.configure("TCheckbutton", background=PALETTE["panel"], foreground=PALETTE["muted"])
        style.configure("TCombobox", fieldbackground=PALETTE["panel_alt"], background=PALETTE["ribbon_panel"], foreground=PALETTE["text"])

    def _build_layout(self) -> None:
        self._build_top_bars()

        shell = ttk.Frame(self.root, style="Workbench.TFrame", padding=(12, 10, 12, 8))
        shell.pack(fill=tk.BOTH, expand=True)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)

        self.left_panel = ttk.Frame(shell, style="Panel.TFrame", padding=12, width=290)
        self.left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.left_panel.grid_propagate(False)
        self._build_left_controls()

        self.center_panel = ttk.Frame(shell, style="Panel.TFrame", padding=12)
        self.center_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        self.center_panel.columnconfigure(0, weight=1)
        self.center_panel.rowconfigure(2, weight=1)
        self._build_chart_panel()

        self.right_panel = ttk.Frame(shell, style="Panel.TFrame", padding=10, width=360)
        self.right_panel.grid(row=0, column=2, sticky="ns")
        self.right_panel.grid_propagate(False)
        self._build_right_panel()

        self.status_var = tk.StringVar(value="Backend: Python desktop engine")
        status = tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            font=("Segoe UI", 9),
            padx=10,
        )
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_top_bars(self) -> None:
        title_bar = tk.Frame(self.root, bg=PALETTE["title_bar"], height=24)
        title_bar.pack(fill=tk.X)
        tk.Label(
            title_bar,
            text="Electional Software",
            bg=PALETTE["title_bar"],
            fg=PALETTE["top_bar_dark"],
            font=("Segoe UI", 9, "bold"),
        ).pack()

        menu = ttk.Frame(self.root, style="Top.TFrame", padding=(12, 5))
        menu.pack(fill=tk.X)
        for item in ("Chart", "Selected Chart", "View Page", "Search", "Utility", "Configuration Editors", "Astro Mapping"):
            tk.Label(menu, text=item, bg=PALETTE["top_bar"], fg="white", font=("Segoe UI", 9, "bold"), padx=13).pack(side=tk.LEFT)

        ribbon = ttk.Frame(self.root, style="Ribbon.TFrame", padding=(10, 8))
        ribbon.pack(fill=tk.X)
        groups = (
            ("Chart", ("New Chart", "Save", "Ask")),
            ("Calculate", ("Transits", "Electional Search")),
            ("Advanced", ("Primary Directions", "Void Course")),
            ("Utility", ("Bounds", "Heliacal Search")),
        )
        for group_title, items in groups:
            group = ttk.Frame(ribbon, style="RibbonPanel.TFrame", padding=(10, 7))
            group.pack(side=tk.LEFT, padx=(0, 8))
            row = ttk.Frame(group, style="RibbonPanel.TFrame")
            row.pack()
            for item in items:
                self._ribbon_button(row, item).pack(side=tk.LEFT, padx=(0, 6))
            tk.Label(
                group,
                text=group_title,
                bg=PALETTE["ribbon_panel"],
                fg=PALETTE["top_bar_dark"],
                font=("Segoe UI", 8),
            ).pack(fill=tk.X, pady=(4, 0))

    def _ribbon_button(self, parent: tk.Widget, label: str) -> tk.Frame:
        button = tk.Frame(
            parent,
            bg=PALETTE["button"],
            highlightbackground=PALETTE["button_line"],
            highlightthickness=1,
            padx=10,
            pady=6,
        )
        tk.Label(
            button,
            text=label,
            bg=PALETTE["button"],
            fg=PALETTE["text"],
            font=("Segoe UI", 9, "bold"),
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

    def _run_ribbon_action(self, label: str) -> None:
        actions = {
            "New Chart": self._new_chart,
            "Save": self._save_current_report,
            "Ask": self._show_quick_help,
            "Transits": self.calculate,
            "Electional Search": self.calculate,
            "Primary Directions": lambda: self._feature_pending("Primary Directions"),
            "Void Course": lambda: self._feature_pending("Void of Course search"),
            "Bounds": lambda: self._feature_pending("Bounds table"),
            "Heliacal Search": lambda: self._feature_pending("Heliacal search"),
        }
        actions.get(label, lambda: self._feature_pending(label))()

    def _new_chart(self) -> None:
        location = default_location_for_timezone()
        self.date_var.set(date.today().isoformat())
        self.time_var.set("09:00")
        self.location_var.set(location.name)
        self.location_name_var.set(location.name)
        self.latitude_var.set(f"{location.latitude:.4f}")
        self.longitude_var.set(f"{location.longitude:.4f}")
        self.timezone_var.set(location.timezone)
        self.objective_var.set(OBJECTIVES[0])
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

    def _current_report_text(self) -> str:
        if not self.selected_window or not self.current_location:
            return "No electional report calculated."
        aspects = "\n".join(f"- {aspect['label']} ({aspect['orbText']})" for aspect in self.selected_window["detectedAspects"])
        planets = "\n".join(
            f"- {planet['name']}: {format_position(planet)} House {planet['house']}" for planet in self.selected_window["positions"]
        )
        windows = "\n".join(format_window_label(index, window) for index, window in enumerate(self.current_windows, start=1))
        return (
            "Electional Software Report\n"
            f"Location: {self.current_location.name}\n"
            f"Time: {self.selected_window['formattedTime']}\n"
            f"Score: {self.selected_window['score']}\n"
            f"Window: {self.selected_window.get('title', 'Electional window')}\n"
            f"Note: {self.selected_window.get('note', '')}\n\n"
            f"Ranked Windows:\n{windows}\n\n"
            f"Aspects:\n{aspects or '- No selected major aspects in orb.'}\n\n"
            f"Planets:\n{planets}\n"
        )

    def _show_quick_help(self) -> None:
        messagebox.showinfo(
            "Electional Software help",
            "Choose a location, date, time, and electional model, then calculate. "
            "Select a candidate window on the right to redraw the wheel for that exact time.",
        )

    def _feature_pending(self, feature_name: str) -> None:
        self.status_var.set(f"{feature_name} is queued for a later build.")
        messagebox.showinfo(feature_name, f"{feature_name} is not wired to the engine yet, but the button is now active.")

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
        self.validation_var = tk.StringVar(value="Validation: waiting for first calculation")

        self._labeled_entry("Election date", self.date_var)
        self._labeled_entry("Start time", self.time_var)
        quick_time = ttk.Frame(self.left_panel, style="Panel.TFrame")
        quick_time.pack(fill=tk.X, pady=(6, 0))
        for label, hours in (("-2h", -2), ("-1h", -1), ("Now", 0), ("+1h", 1), ("+2h", 2)):
            ttk.Button(
                quick_time,
                text=label,
                command=(self._set_current_time if hours == 0 else lambda delta=hours: self._shift_time(delta)),
            ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4))
        self.location_combo = self._labeled_combo("Location preset", self.location_var, [location.name for location in LOCATION_PRESETS])
        self.location_combo.bind("<<ComboboxSelected>>", self._load_selected_location)
        self._labeled_entry("Location name", self.location_name_var)
        self._labeled_entry("Latitude", self.latitude_var)
        self._labeled_entry("Longitude", self.longitude_var)
        self._labeled_entry("Time zone", self.timezone_var)
        self._labeled_combo("Objective", self.objective_var, list(OBJECTIVES))
        self.preset_combo = self._labeled_combo("Electional model", self.preset_var, [preset.name for preset in ELECTIONAL_PRESETS])
        self.preset_combo.bind("<<ComboboxSelected>>", self._sync_aspects_to_preset)

        aspect_box = ttk.LabelFrame(self.left_panel, text="Aspect focus", style="Panel.TLabelframe", padding=10)
        aspect_box.pack(fill=tk.X, pady=(8, 12))
        preset = ELECTIONAL_PRESETS[1]
        session_aspects = state.get("aspects") if isinstance(state.get("aspects"), dict) else {}
        for aspect_id in ("conjunction", "trine", "sextile", "square", "opposition"):
            default_value = bool(session_aspects.get(aspect_id, aspect_id in preset.aspect_ids))
            var = tk.BooleanVar(value=default_value)
            self.aspect_vars[aspect_id] = var
            ttk.Checkbutton(aspect_box, text=aspect_id.title(), variable=var).pack(anchor="w", pady=2)

        ttk.Button(self.left_panel, text="Calculate Election", command=self.calculate).pack(fill=tk.X, pady=(2, 0))
        tk.Label(
            self.left_panel,
            textvariable=self.validation_var,
            bg=PALETTE["panel"],
            fg=PALETTE["score"],
            justify=tk.LEFT,
            wraplength=250,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(10, 0))

    def _labeled_entry(self, label: str, variable: tk.StringVar) -> None:
        ttk.Label(self.left_panel, text=label, style="Small.TLabel").pack(anchor="w", pady=(10, 3))
        entry = tk.Entry(self.left_panel, textvariable=variable, bg=PALETTE["panel_alt"], relief=tk.SOLID, bd=1, font=("Segoe UI", 10, "bold"))
        entry.pack(fill=tk.X, ipady=7)

    def _labeled_combo(self, label: str, variable: tk.StringVar, values: list[str]) -> ttk.Combobox:
        ttk.Label(self.left_panel, text=label, style="Small.TLabel").pack(anchor="w", pady=(10, 3))
        combo = ttk.Combobox(self.left_panel, textvariable=variable, values=values, state="readonly")
        combo.pack(fill=tk.X, ipady=5)
        return combo

    def _load_selected_location(self, _event: object | None = None) -> None:
        location = self.locations_by_name.get(self.location_var.get(), get_location(None))
        self.location_name_var.set(location.name)
        self.latitude_var.set(f"{location.latitude:.4f}")
        self.longitude_var.set(f"{location.longitude:.4f}")
        self.timezone_var.set(location.timezone)

    def _sync_aspects_to_preset(self, _event: object | None = None) -> None:
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        for aspect_id, var in self.aspect_vars.items():
            var.set(aspect_id in preset.aspect_ids)
        self.status_var.set(f"Aspect focus updated for {preset.name}.")

    def _shift_time(self, hours: int) -> None:
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
        next_date, next_time = shift_local_datetime(self.date_var.get(), self.time_var.get(), self.timezone_var.get(), hours)
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
        ttk.Label(header, text="RADIX + ELECTIONAL TRANSITS", style="Accent.TLabel").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.title_var, style="Title.TLabel").grid(row=1, column=0, sticky="w")

        score_card = ttk.Frame(header, style="Panel.TFrame", padding=(18, 8))
        score_card.grid(row=0, column=1, rowspan=2, sticky="e")
        self.score_var = tk.StringVar(value="--")
        ttk.Label(score_card, textvariable=self.score_var, style="Score.TLabel").pack()
        ttk.Label(score_card, text="top window score", style="Small.TLabel").pack()

        self.canvas = tk.Canvas(
            self.center_panel,
            width=760,
            height=640,
            bg=PALETTE["canvas"],
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
        )
        self.canvas.grid(row=2, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._schedule_redraw)

        interpretation = ttk.LabelFrame(self.center_panel, text="Point Interpretation", style="Panel.TLabelframe", padding=7)
        interpretation.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.interpretation_text = tk.Text(
            interpretation,
            height=4,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
        )
        self.interpretation_text.pack(fill=tk.X)
        self.interpretation_text.configure(state=tk.DISABLED)

    def _build_right_panel(self) -> None:
        self.summary_text = self._text_panel("Score Summary", height=7)
        self._build_window_list_panel()
        self.window_detail_text = self._text_panel("Selected Window", height=7)
        self.planets_text = self._text_panel("Planets", height=10)
        self.aspects_text = self._text_panel("Aspects", height=8)

    def _build_window_list_panel(self) -> None:
        frame = ttk.LabelFrame(self.right_panel, text="Candidate Windows", style="Panel.TLabelframe", padding=7)
        frame.pack(fill=tk.X, pady=(0, 9))
        self.windows_list = tk.Listbox(
            frame,
            width=40,
            height=7,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.FLAT,
            activestyle="dotbox",
            font=("Segoe UI", 9),
            selectbackground=PALETTE["selected"],
            selectforeground=PALETTE["text"],
        )
        self.windows_list.pack(fill=tk.X)
        self.windows_list.bind("<<ListboxSelect>>", self._select_window_from_list)
        ttk.Button(frame, text="Use Selected Time", command=self._use_selected_window_time).pack(fill=tk.X, pady=(7, 0))

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

    def calculate(self) -> None:
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        selected_aspects = [aspect for aspect, var in self.aspect_vars.items() if var.get()]
        errors = validate_election_inputs(
            self.date_var.get(),
            self.time_var.get(),
            self.latitude_var.get(),
            self.longitude_var.get(),
            self.timezone_var.get(),
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

        try:
            report = build_election_report(self.date_var.get(), normalized_time, location, preset.id, selected_aspects)
        except Exception as exc:  # pragma: no cover - exercised manually through the desktop UI.
            messagebox.showerror("Electional calculation failed", str(exc))
            return

        snapshot = report["snapshot"]
        windows = report["windows"]
        selected_window = windows[0] if windows else snapshot
        self.current_location = location
        self.current_windows = list(windows)
        self.selected_window = selected_window

        self.title_var.set(f"{self.objective_var.get()} windows near {location.name}")
        self.natal_summary.configure(
            text=(
                f"{self.date_var.get()} {self.time_var.get()}\n"
                f"{location.name}\n"
                f"{location.latitude:.4f}, {location.longitude:.4f}\n"
                f"{location.timezone}"
            )
        )
        self.score_var.set(str(selected_window["score"]))
        self.validation_var.set("Validation: Pass")
        self.status_var.set(
            f"Location: {location.name}    Chart time: {selected_window['formattedTime']}    Validation: Pass    Engine: {selected_window['engine']}"
        )
        self._populate_window_list(windows)
        self._draw_wheel(selected_window)
        self._render_text_panels(selected_window, windows, location)
        self._save_session()

    def _populate_window_list(self, windows: list[dict[str, object]]) -> None:
        self.windows_list.delete(0, tk.END)
        for index, window in enumerate(windows, start=1):
            self.windows_list.insert(tk.END, format_window_label(index, window))
        if windows:
            self.windows_list.selection_set(0)
            self.windows_list.activate(0)

    def _select_window_from_list(self, _event: object | None = None) -> None:
        if not self.current_windows or not self.current_location:
            return
        selection = self.windows_list.curselection()
        if not selection:
            return
        selected = self.current_windows[int(selection[0])]
        self.selected_window = selected
        self.score_var.set(str(selected["score"]))
        self.status_var.set(
            f"Location: {self.current_location.name}    Chart time: {selected['formattedTime']}    Validation: Pass    Engine: {selected['engine']}"
        )
        self._draw_wheel(selected)
        self._render_text_panels(selected, self.current_windows, self.current_location)

    def _use_selected_window_time(self) -> None:
        if not self.selected_window or not self.current_location:
            return
        local = self.selected_window["date"].astimezone(ZoneInfo(self.current_location.timezone))
        self.date_var.set(local.strftime("%Y-%m-%d"))
        self.time_var.set(local.strftime("%H:%M"))
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
        cy = height / 2 + 8
        outer = max(180, min(width, height) / 2 - 34)
        zodiac_inner = outer * 0.84
        house_inner = outer * 0.44
        aspect_radius = outer * 0.44

        self._draw_grid(width, height)
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
            self.canvas.create_text(lx, ly, text=sign, fill="#17234f", font=("Segoe UI", 15, "bold"))

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
        self.canvas.create_oval(cx - 72, cy - 72, cx + 72, cy + 72, outline=PALETTE["chart_line"], width=2)

        for house_index in range(12):
            angle = wheel_degrees(asc_lon + house_index * 30, asc_lon)
            x1, y1 = _polar(cx, cy, house_inner, angle)
            x2, y2 = _polar(cx, cy, zodiac_inner, angle)
            self.canvas.create_line(x1, y1, x2, y2, fill=PALETTE["chart_line"], width=1)
            lx, ly = _polar(cx, cy, outer * 0.64, angle - 15)
            self.canvas.create_text(lx, ly, text=str(house_index + 1), fill=PALETTE["muted"], font=("Segoe UI", 12, "bold"))

        self._draw_aspects(snapshot, cx, cy, aspect_radius, asc_lon)
        self._draw_angles(snapshot, cx, cy, outer, asc_lon)
        self._draw_planets(snapshot, cx, cy, asc_lon, outer)

        self.canvas.create_text(cx, cy - 10, text=f"Score {snapshot['score']}", fill=PALETTE["top_bar_dark"], font=("Segoe UI", 16, "bold"))
        self.canvas.create_text(cx, cy + 18, text=str(snapshot["formattedTime"]), fill=PALETTE["muted"], font=("Segoe UI", 9))

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

    def _draw_planets(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        for index, planet in enumerate(snapshot["positions"]):
            degrees = wheel_degrees(float(planet["longitude"]), asc_lon)
            radius = outer * 0.74 - (index % 3) * 18
            x, y = _polar(cx, cy, radius, degrees)
            fill = PALETTE["panel_alt"] if planet.get("isPresetPoint") else "#dfe2d2"
            outline = PALETTE["top_bar"] if planet.get("isAngular") else PALETTE["chart_line"]
            self.canvas.create_oval(x - 14, y - 14, x + 14, y + 14, fill=fill, outline=outline, width=2)
            self.canvas.create_text(x, y, text=planet_abbreviation(str(planet["name"])), fill=PALETTE["top_bar_dark"], font=("Segoe UI", 9, "bold"))

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
                f"Benefic/support contacts: {support}\n"
                f"Stress contacts: {stress}\n"
                f"Angular bodies: {angular}\n"
                f"Timezone: {location.timezone}\n"
                f"Model: {snapshot['preset'].name}\n"
                f"Engine: {snapshot['engine']}"
            ),
        )

        selected_rank = next((index for index, window in enumerate(windows, start=1) if window["date"] == snapshot["date"]), 1)
        aspect_labels = ", ".join(aspect["label"] for aspect in snapshot["detectedAspects"][:3]) or "No selected major aspects"
        self._set_text(
            self.window_detail_text,
            (
                f"Rank: {selected_rank} of {len(windows)}\n"
                f"Time: {snapshot['formattedTime']}\n"
                f"Score: {snapshot['score']} - {snapshot.get('title', 'Election')}\n"
                f"{snapshot.get('note', '')}\n"
                f"{aspect_labels}"
            ),
        )
        self._set_text(
            self.interpretation_text,
            self._selected_window_interpretation(snapshot, selected_rank, len(windows)),
        )

        planet_lines = []
        for planet in snapshot["positions"]:
            angular = " angular" if planet.get("isAngular") else ""
            dignity = planet.get("dignity", {}).get("label", "Unknown")
            planet_lines.append(f"{planet['name']:<8} {format_position(planet):<15} H{planet['house']:<2} {dignity}{angular}")
        angle_lines = ["", "Angles:"]
        angle_lines.extend(format_angle(angle) for angle in snapshot["angles"])
        self._set_text(self.planets_text, "\n".join(planet_lines + angle_lines))

        aspect_lines = []
        for aspect in snapshot["detectedAspects"]:
            aspect_lines.append(f"{aspect['label']} ({aspect['orbText']}) - {aspect['tone']}")
        self._set_text(self.aspects_text, "\n".join(aspect_lines) or "No selected major aspects in orb.")

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
        ]
        if support:
            lines.append("Support: " + ", ".join(support[:3]) + ".")
        if stress:
            lines.append("Watch: " + ", ".join(stress[:3]) + ".")
        if angular:
            lines.append("Angles: " + ", ".join(angular[:3]) + ".")
        return "\n".join(lines)

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
            "aspects": {aspect_id: var.get() for aspect_id, var in self.aspect_vars.items()},
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


def main() -> None:
    root = tk.Tk()
    ElectionalDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
