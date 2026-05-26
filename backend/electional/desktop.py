"""Native desktop application shell for Electional Software."""

from __future__ import annotations

from datetime import date
import math
import tkinter as tk
from tkinter import messagebox, ttk

from .chart import build_snapshot, build_transit_windows, format_angle, format_position
from .locations import LOCATION_PRESETS, get_location
from .presets import ELECTIONAL_PRESETS

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
SIGN_COLORS = (
    "#d6657f",
    "#c9a66f",
    "#28b7a7",
    "#b6c89a",
    "#f4bb74",
    "#f1d9a7",
    "#27b4a7",
    "#af579f",
    "#f2a968",
    "#c5a06b",
    "#28b2b2",
    "#b25aa1",
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

        self._configure_style()
        self._build_layout()
        self.calculate()

    def _configure_style(self) -> None:
        self.root.configure(bg="#d98c65")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background="#efc58e")
        style.configure("Top.TFrame", background="#263c79")
        style.configure("Ribbon.TFrame", background="#d1845e")
        style.configure("Panel.TFrame", background="#efc58e", relief="solid", borderwidth=1)
        style.configure("Panel.TLabelframe", background="#efc58e", bordercolor="#805b32")
        style.configure("Panel.TLabelframe.Label", background="#efc58e", foreground="#004e52", font=("Segoe UI", 9, "bold"))
        style.configure("Title.TLabel", background="#efc58e", foreground="#1b160f", font=("Segoe UI", 18, "bold"))
        style.configure("Small.TLabel", background="#efc58e", foreground="#4f4336", font=("Segoe UI", 9))
        style.configure("Accent.TLabel", background="#efc58e", foreground="#00666b", font=("Segoe UI", 9, "bold"))
        style.configure("Score.TLabel", background="#f6d9a6", foreground="#005d62", font=("Segoe UI", 30, "bold"))
        style.configure("TButton", background="#e8a480", foreground="#1b160f", padding=(12, 6))
        style.map("TButton", background=[("active", "#f0bb95")])
        style.configure("TCheckbutton", background="#efc58e", foreground="#4f4336")
        style.configure("TCombobox", fieldbackground="#ffe7b7", background="#e8a480")

    def _build_layout(self) -> None:
        self._build_top_bars()

        shell = ttk.Frame(self.root, style="Ribbon.TFrame", padding=(12, 10, 12, 8))
        shell.pack(fill=tk.BOTH, expand=True)
        shell.columnconfigure(2, weight=1)
        shell.rowconfigure(0, weight=1)

        self.left_panel = ttk.Frame(shell, style="Panel.TFrame", padding=12)
        self.left_panel.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self._build_left_controls()

        self.number_strip = ttk.Frame(shell, style="Panel.TFrame", padding=(8, 14))
        self.number_strip.grid(row=0, column=1, sticky="ns", padx=(0, 10))
        self._build_number_strip()

        self.center_panel = ttk.Frame(shell, style="Panel.TFrame", padding=12)
        self.center_panel.grid(row=0, column=2, sticky="nsew", padx=(0, 10))
        self.center_panel.columnconfigure(0, weight=1)
        self.center_panel.rowconfigure(2, weight=1)
        self._build_chart_panel()

        self.right_panel = ttk.Frame(shell, style="Panel.TFrame", padding=10)
        self.right_panel.grid(row=0, column=3, sticky="ns")
        self._build_right_panel()

        self.status_var = tk.StringVar(value="Backend: Python desktop engine")
        status = tk.Label(
            self.root,
            textvariable=self.status_var,
            anchor="w",
            bg="#f4d293",
            fg="#1c2530",
            font=("Segoe UI", 9),
            padx=10,
        )
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_top_bars(self) -> None:
        title_bar = tk.Frame(self.root, bg="#ef9bab", height=24)
        title_bar.pack(fill=tk.X)
        tk.Label(
            title_bar,
            text="Electional Software",
            bg="#ef9bab",
            fg="#141d42",
            font=("Segoe UI", 9, "bold"),
        ).pack()

        menu = ttk.Frame(self.root, style="Top.TFrame", padding=(12, 5))
        menu.pack(fill=tk.X)
        for item in ("Chart", "Selected Chart", "View Page", "Search", "Utility", "Configuration Editors", "Astro Mapping"):
            tk.Label(menu, text=item, bg="#263c79", fg="white", font=("Segoe UI", 9, "bold"), padx=13).pack(side=tk.LEFT)

        ribbon = ttk.Frame(self.root, style="Ribbon.TFrame", padding=(10, 8))
        ribbon.pack(fill=tk.X)
        for item in ("New Chart", "Transits", "Electional Search", "Void Course", "Bounds"):
            ttk.Button(ribbon, text=item).pack(side=tk.LEFT, padx=(0, 7))

    def _build_left_controls(self) -> None:
        card = ttk.Frame(self.left_panel, style="Panel.TFrame", padding=12)
        card.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(card, text="NATAL CHART", style="Accent.TLabel").pack(anchor="w")
        ttk.Label(card, text="Natal Chart", background="#efc58e", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(6, 4))
        self.natal_summary = ttk.Label(card, text="", style="Small.TLabel", justify=tk.LEFT)
        self.natal_summary.pack(anchor="w")

        today = date.today()
        self.date_var = tk.StringVar(value=today.strftime("%Y-%m-%d"))
        self.time_var = tk.StringVar(value="09:00")
        self.location_var = tk.StringVar(value=LOCATION_PRESETS[0].name)
        self.objective_var = tk.StringVar(value="Launch or publish")
        self.preset_var = tk.StringVar(value=ELECTIONAL_PRESETS[1].name)

        self._labeled_entry("Election date", self.date_var)
        self._labeled_entry("Start time", self.time_var)
        self._labeled_combo("Location preset", self.location_var, [location.name for location in LOCATION_PRESETS])
        self._labeled_combo("Objective", self.objective_var, ["Launch or publish", "Begin a relationship", "Sign agreement", "Travel departure"])
        self._labeled_combo("Electional model", self.preset_var, [preset.name for preset in ELECTIONAL_PRESETS])

        aspect_box = ttk.LabelFrame(self.left_panel, text="Aspect focus", style="Panel.TLabelframe", padding=10)
        aspect_box.pack(fill=tk.X, pady=(8, 12))
        preset = ELECTIONAL_PRESETS[1]
        for aspect_id in ("conjunction", "trine", "sextile", "square", "opposition"):
            var = tk.BooleanVar(value=aspect_id in preset.aspect_ids)
            self.aspect_vars[aspect_id] = var
            ttk.Checkbutton(aspect_box, text=aspect_id.title(), variable=var).pack(anchor="w", pady=2)

        ttk.Button(self.left_panel, text="Calculate Election", command=self.calculate).pack(fill=tk.X, pady=(2, 0))

    def _labeled_entry(self, label: str, variable: tk.StringVar) -> None:
        ttk.Label(self.left_panel, text=label, style="Small.TLabel").pack(anchor="w", pady=(10, 3))
        entry = tk.Entry(self.left_panel, textvariable=variable, bg="#ffe7b7", relief=tk.SOLID, bd=1, font=("Segoe UI", 10, "bold"))
        entry.pack(fill=tk.X, ipady=7)

    def _labeled_combo(self, label: str, variable: tk.StringVar, values: list[str]) -> None:
        ttk.Label(self.left_panel, text=label, style="Small.TLabel").pack(anchor="w", pady=(10, 3))
        combo = ttk.Combobox(self.left_panel, textvariable=variable, values=values, state="readonly")
        combo.pack(fill=tk.X, ipady=5)

    def _build_number_strip(self) -> None:
        for text in ("5\n6\n12", "11\n1\n3", "6\n8"):
            badge = tk.Label(
                self.number_strip,
                text=text,
                bg="#f8df9d",
                fg="#3a4c38",
                relief=tk.SOLID,
                bd=1,
                font=("Segoe UI", 13),
                width=4,
                height=3,
            )
            badge.pack(pady=(0, 18))

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

        self.canvas = tk.Canvas(self.center_panel, width=760, height=640, bg="#f6d39b", highlightthickness=1, highlightbackground="#986a3c")
        self.canvas.grid(row=2, column=0, sticky="nsew")

    def _build_right_panel(self) -> None:
        self.summary_text = self._text_panel("Score Summary", height=7)
        self.windows_text = self._text_panel("Candidate Windows", height=13)
        self.planets_text = self._text_panel("Planets", height=12)
        self.aspects_text = self._text_panel("Aspects", height=9)

    def _text_panel(self, title: str, height: int) -> tk.Text:
        frame = ttk.LabelFrame(self.right_panel, text=title, style="Panel.TLabelframe", padding=7)
        frame.pack(fill=tk.X, pady=(0, 9))
        text = tk.Text(
            frame,
            width=40,
            height=height,
            bg="#f8dca6",
            fg="#1f1a14",
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
        )
        text.pack(fill=tk.X)
        text.configure(state=tk.DISABLED)
        return text

    def calculate(self) -> None:
        location = self.locations_by_name.get(self.location_var.get(), get_location(None))
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        selected_aspects = [aspect for aspect, var in self.aspect_vars.items() if var.get()]

        try:
            snapshot = build_snapshot(self.date_var.get(), self.time_var.get(), location, preset.id, selected_aspects)
            windows = build_transit_windows(self.date_var.get(), self.time_var.get(), location, preset.id, selected_aspects)
        except Exception as exc:  # pragma: no cover - exercised manually through the desktop UI.
            messagebox.showerror("Electional calculation failed", str(exc))
            return

        self.title_var.set(f"{self.objective_var.get()} windows near {location.name}")
        self.natal_summary.configure(
            text=(
                f"{self.date_var.get()} {self.time_var.get()}\n"
                f"{location.name}\n"
                f"{location.latitude:.4f}, {location.longitude:.4f}\n"
                f"{location.timezone}"
            )
        )
        self.score_var.set(str(windows[0]["score"] if windows else snapshot["score"]))
        self.status_var.set(
            f"Location: {location.name}    Chart time: {snapshot['formattedTime']}    Validation: Pass    Engine: {snapshot['engine']}"
        )
        self._draw_wheel(snapshot)
        self._render_text_panels(snapshot, windows, location)

    def _draw_wheel(self, snapshot: dict[str, object]) -> None:
        self.canvas.delete("all")
        width = int(self.canvas.cget("width"))
        height = int(self.canvas.cget("height"))
        cx = width / 2
        cy = height / 2 + 8
        outer = 275
        zodiac_inner = 230
        house_inner = 122
        aspect_radius = 122

        self._draw_grid(width, height)
        self.canvas.create_oval(cx - outer, cy - outer, cx + outer, cy + outer, fill="#efd29a", outline="#754f30", width=2)

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
                extent=-30,
                fill=SIGN_COLORS[index],
                outline="#67412d",
                width=1,
            )
            self.canvas.create_arc(
                cx - zodiac_inner,
                cy - zodiac_inner,
                cx + zodiac_inner,
                cy + zodiac_inner,
                start=start,
                extent=-30,
                fill="#efc58e",
                outline="#67412d",
                width=1,
            )
            label_angle = wheel_degrees(index * 30 + 15, asc_lon)
            lx, ly = _polar(cx, cy, 252, label_angle)
            self.canvas.create_text(lx, ly, text=sign, fill="#f5e9c6", font=("Segoe UI", 15, "bold"))

        self.canvas.create_oval(cx - zodiac_inner, cy - zodiac_inner, cx + zodiac_inner, cy + zodiac_inner, outline="#765238", width=2)
        self.canvas.create_oval(cx - house_inner, cy - house_inner, cx + house_inner, cy + house_inner, fill="#f6dca8", outline="#8a6547", width=2)
        self.canvas.create_oval(cx - 72, cy - 72, cx + 72, cy + 72, outline="#8a6547", width=2)

        for house_index in range(12):
            angle = wheel_degrees(asc_lon + house_index * 30, asc_lon)
            x1, y1 = _polar(cx, cy, house_inner, angle)
            x2, y2 = _polar(cx, cy, zodiac_inner, angle)
            self.canvas.create_line(x1, y1, x2, y2, fill="#6f4d35", width=1)
            lx, ly = _polar(cx, cy, 175, angle - 15)
            self.canvas.create_text(lx, ly, text=str(house_index + 1), fill="#7a4f34", font=("Segoe UI", 12, "bold"))

        self._draw_aspects(snapshot, cx, cy, aspect_radius, asc_lon)
        self._draw_angles(snapshot, cx, cy, outer, asc_lon)
        self._draw_planets(snapshot, cx, cy, asc_lon)

        self.canvas.create_text(cx, cy - 8, text="Election", fill="#263044", font=("Segoe UI", 18, "bold"))
        self.canvas.create_text(cx, cy + 25, text="Python Astronomy Engine", fill="#5b4a39", font=("Segoe UI", 10))

    def _draw_grid(self, width: int, height: int) -> None:
        for x in range(0, width, 24):
            self.canvas.create_line(x, 0, x, height, fill="#e9c88d", width=1)
        for y in range(0, height, 24):
            self.canvas.create_line(0, y, width, y, fill="#e9c88d", width=1)

    def _draw_angles(self, snapshot: dict[str, object], cx: float, cy: float, outer: float, asc_lon: float) -> None:
        for angle in snapshot["angles"]:
            degrees = wheel_degrees(float(angle["longitude"]), asc_lon)
            x1, y1 = _polar(cx, cy, 92, degrees)
            x2, y2 = _polar(cx, cy, outer, degrees)
            self.canvas.create_line(x1, y1, x2, y2, fill="#0d6681", width=3)
            lx, ly = _polar(cx, cy, outer - 18, degrees)
            self.canvas.create_text(lx, ly, text=angle["shortName"], fill="#1c3765", font=("Segoe UI", 14, "bold"))

    def _draw_planets(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float) -> None:
        for index, planet in enumerate(snapshot["positions"]):
            degrees = wheel_degrees(float(planet["longitude"]), asc_lon)
            radius = 202 - (index % 3) * 18
            x, y = _polar(cx, cy, radius, degrees)
            fill = "#fff0c9" if planet.get("isPresetPoint") else "#ddcfb2"
            outline = "#23445b" if planet.get("isAngular") else "#6d513d"
            self.canvas.create_oval(x - 14, y - 14, x + 14, y + 14, fill=fill, outline=outline, width=2)
            self.canvas.create_text(x, y, text=planet_abbreviation(str(planet["name"])), fill="#18284f", font=("Segoe UI", 9, "bold"))

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
            color = "#219b9d" if aspect["tone"] == "support" else "#d5657b"
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

        window_lines = []
        for window in windows:
            aspect_labels = ", ".join(aspect["label"] for aspect in window["detectedAspects"][:2]) or "No selected major aspects"
            window_lines.append(f"{window['time']}  Score {window['score']}\n{window['title']}\n{window['note']}\n{aspect_labels}\n")
        self._set_text(self.windows_text, "\n".join(window_lines))

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
