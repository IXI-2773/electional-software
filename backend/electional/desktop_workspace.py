"""Center workspace, chart shell, live-sky page, and wheel option controls."""

from __future__ import annotations


def bind_desktop_globals(namespace: dict[str, object]) -> None:
    """Bind the shared desktop shell namespace after desktop.py is initialized."""

    protected = {"__name__", "__package__", "__spec__", "__loader__", "__file__", "__cached__", "__builtins__"}
    globals().update({name: value for name, value in namespace.items() if name not in protected})


class DesktopWorkspaceMixin:
    def _build_chart_panel(self) -> None:
        header = ttk.Frame(self.center_panel, style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="RADIX + ELECTIONAL TRANSITS", style="Accent.TLabel").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value="")
        self.title_label = ttk.Label(header, textvariable=self.title_var, style="Title.TLabel", wraplength=520, justify=tk.LEFT)
        self.title_label.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.timing_context_var = tk.StringVar(value="")
        self.timing_context_label = ttk.Label(header, textvariable=self.timing_context_var, style="Small.TLabel", wraplength=520, justify=tk.LEFT)
        self.timing_context_label.grid(row=2, column=0, sticky="ew", pady=(1, 0), padx=(0, 8))
        self.workspace_page_var = tk.StringVar(value="Main page: Wheel")
        self.workspace_page_summary_var = tk.StringVar(value=TOP_NAV_WORKSPACE_SUMMARIES["Wheel"])
        header.bind("<Configure>", self._resize_header_labels)
        self.score_var = tk.StringVar(value="--")
        self.score_band_var = tk.StringVar(value="waiting")

        self._build_guided_workflow_panel()

        self.location_state_var = tk.StringVar(value="")
        self.input_state_var = tk.StringVar(value="No current aspect yet")
        self.selected_state_var = tk.StringVar(value="Next: show current chart")
        self.offset_state_var = tk.StringVar(value="Score --")

        self.search_workbench_frame = tk.Frame(
            self.center_panel,
            bg=PALETTE["surface_sage"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=8,
            pady=3,
        )
        self.search_workbench_frame.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        self.search_workbench_frame.columnconfigure(0, weight=1)
        self.search_workbench_frame.columnconfigure(1, weight=1)
        self.search_workbench_frame.columnconfigure(2, weight=0)
        self.search_workbench_title_var = tk.StringVar(value="Search Console")
        self.search_workbench_summary_var = tk.StringVar(value="Waiting for calculation. Use Electional Search to rank candidate windows.")
        self.search_workbench_detail_var = tk.StringVar(value="Aspect profile and filters will appear here.")
        tk.Label(
            self.search_workbench_frame,
            textvariable=self.search_workbench_title_var,
            bg=PALETTE["surface_sage"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 8, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tk.Label(
            self.search_workbench_frame,
            textvariable=self.search_workbench_summary_var,
            bg=PALETTE["surface_sage"],
            fg=PALETTE["text"],
            font=("Segoe UI Semibold", 7),
            anchor="w",
            justify=tk.LEFT,
            wraplength=440,
        ).grid(row=0, column=1, sticky="ew", padx=(0, 12))
        quick_actions = tk.Frame(self.search_workbench_frame, bg=PALETTE["surface_sage"])
        quick_actions.grid(row=0, column=2, sticky="e")
        ttk.Button(quick_actions, text="Run", command=self._run_electional_search_workbench, style="Compact.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_actions, text="Timeline", command=self._open_timeline_workbench, style="Compact.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_actions, text="Aspects", command=self._show_aspect_config_dialog, style="Compact.TButton").pack(side=tk.LEFT)
        self.search_workbench_frame.grid_remove()

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
            width=WHEEL_CANVAS_DEFAULT_WIDTH,
            height=WHEEL_CANVAS_DEFAULT_HEIGHT,
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
        self._build_live_sky_workspace()
        self.live_sky_workspace.grid_remove()

    def _build_live_sky_workspace(self) -> None:
        self.center_panel.rowconfigure(3, weight=1, minsize=CENTER_WORKSPACE_MIN_HEIGHT)
        self.live_sky_workspace = tk.Frame(
            self.center_panel,
            bg="#05072b",
            highlightbackground=PALETTE["panel_line_strong"],
            highlightthickness=1,
            padx=8,
            pady=8,
        )
        self.live_sky_workspace.grid(row=3, column=0, sticky="nsew")
        self.live_sky_workspace.columnconfigure(0, weight=1)
        self.live_sky_workspace.columnconfigure(1, weight=0)
        self.live_sky_workspace.rowconfigure(1, weight=1)
        controls = tk.Frame(self.live_sky_workspace, bg="#05072b")
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        controls.columnconfigure(8, weight=1)
        tk.Label(controls, text="Live Sky", bg="#05072b", fg="#e7e2b3", font=("Georgia", 13, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 10))
        tk.Label(controls, text="Date", bg="#05072b", fg="#b8c4e8", font=("Segoe UI", 8, "bold")).grid(row=0, column=1, sticky="e", padx=(0, 4))
        tk.Entry(controls, textvariable=self.live_sky_date_var, width=12, bg="#10143f", fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT).grid(row=0, column=2, sticky="w", padx=(0, 8), ipady=4)
        tk.Label(controls, text="Time", bg="#05072b", fg="#b8c4e8", font=("Segoe UI", 8, "bold")).grid(row=0, column=3, sticky="e", padx=(0, 4))
        tk.Entry(controls, textvariable=self.live_sky_time_var, width=8, bg="#10143f", fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT).grid(row=0, column=4, sticky="w", padx=(0, 8), ipady=4)
        actions = (
            ("Live Now", lambda: self._update_live_sky("live")),
            ("Manual Date", lambda: self._update_live_sky("manual")),
            ("Sync Chart", lambda: self._update_live_sky("chart")),
            ("-1h", lambda: self._shift_live_sky_minutes(-60)),
            ("+1h", lambda: self._shift_live_sky_minutes(60)),
            ("-1d", lambda: self._shift_live_sky_minutes(-1440)),
            ("+1d", lambda: self._shift_live_sky_minutes(1440)),
        )
        for index, (label, command) in enumerate(actions, start=5):
            tk.Button(
                controls,
                text=label,
                command=command,
                bg="#141a4f",
                fg="#f4f0cf",
                activebackground="#243074",
                activeforeground="#ffffff",
                relief=tk.FLAT,
                bd=0,
                padx=7,
                pady=4,
                font=("Segoe UI", 8, "bold"),
                cursor="hand2",
            ).grid(row=0, column=index, sticky="ew", padx=(0, 5))
        self.live_sky_canvas = tk.Canvas(
            self.live_sky_workspace,
            bg="#020426",
            highlightthickness=1,
            highlightbackground="#273262",
            width=980,
            height=680,
        )
        self.live_sky_canvas.grid(row=1, column=0, sticky="nsew")
        self.live_sky_canvas.bind("<Configure>", lambda _event: self._draw_live_sky())
        side = tk.Frame(self.live_sky_workspace, bg="#080b32", highlightbackground="#273262", highlightthickness=1, padx=9, pady=8, width=250)
        side.grid(row=1, column=1, sticky="nse", padx=(8, 0))
        side.grid_propagate(False)
        tk.Label(side, text="Sky Date Control", bg="#080b32", fg="#e7e2b3", font=("Georgia", 10, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(side, textvariable=self.live_sky_status_var, bg="#080b32", fg="#d8def5", font=("Segoe UI", 8), wraplength=225, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(6, 8))
        tk.Label(side, text="Bodies", bg="#080b32", fg="#e7e2b3", font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        tk.Label(side, textvariable=self.live_sky_info_var, bg="#080b32", fg="#d8def5", font=("Consolas", 8), wraplength=225, justify=tk.LEFT, anchor="w").pack(fill=tk.X, pady=(5, 0))

    def _show_wheel_workspace(self) -> None:
        if hasattr(self, "live_sky_workspace"):
            self.live_sky_workspace.grid_remove()
        if hasattr(self, "wheel_workspace"):
            self.wheel_workspace.grid()

    def _show_live_sky_workspace(self) -> None:
        if hasattr(self, "wheel_workspace"):
            self.wheel_workspace.grid_remove()
        if hasattr(self, "live_sky_workspace"):
            self.live_sky_workspace.grid()
        self._update_live_sky("chart" if self.selected_window else "manual")

    def _live_sky_snapshot_for_mode(self, mode: str) -> tuple[dict[str, object], LocationPreset, str]:
        location = self.current_location or build_custom_location(
            self.location_name_var.get(),
            self.latitude_var.get(),
            self.longitude_var.get(),
            self.timezone_var.get(),
        )
        if mode == "chart" and self.selected_window:
            snapshot = self.selected_window
            local = snapshot["date"].astimezone(ZoneInfo(location.timezone))
            self.live_sky_date_var.set(local.strftime("%Y-%m-%d"))
            self.live_sky_time_var.set(local.strftime("%H:%M"))
            return snapshot, location, "manual"
        if mode == "live":
            local_now = datetime.now(ZoneInfo(location.timezone))
            self.live_sky_date_var.set(local_now.strftime("%Y-%m-%d"))
            self.live_sky_time_var.set(local_now.strftime("%H:%M"))
            moment = local_now.astimezone(timezone.utc)
            mode_id = "live"
        else:
            moment = zoned_time_to_utc(self.live_sky_date_var.get(), self.live_sky_time_var.get(), location.timezone)
            mode_id = "manual"
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        snapshot = build_snapshot_for_moment(
            moment,
            location,
            preset,
            self._selected_aspect_ids(),
            get_zodiac_system(self.zodiac_system_var.get()).id,
            get_house_system(self.house_system_var.get()).id,
            self.objective_var.get(),
            aspect_definitions=self._active_aspect_definitions(),
        )
        return snapshot, location, mode_id

    def _update_live_sky(self, mode: str = "manual") -> None:
        if not hasattr(self, "live_sky_canvas"):
            return
        try:
            snapshot, location, mode_id = self._live_sky_snapshot_for_mode(mode)
        except Exception as exc:
            self.live_sky_status_var.set(f"Live Sky could not calculate this date/time: {exc}")
            self.status_var.set("Live Sky calculation failed.")
            return
        self.live_sky_snapshot = snapshot
        self.live_sky_mode_var.set("Live" if mode_id == "live" else "Manual")
        self.live_sky_status_var.set(live_sky_timestamp_line(snapshot, location, mode_id))
        rows = live_sky_body_rows(snapshot)
        self.live_sky_info_var.set("\n".join(f"{row['glyph']:<2} {row['name']:<8} {row['position']}" for row in rows[:12]))
        self._draw_live_sky()
        self.status_var.set("Live Sky updated.")

    def _shift_live_sky_minutes(self, minutes: int) -> None:
        try:
            location = self.current_location or build_custom_location(
                self.location_name_var.get(),
                self.latitude_var.get(),
                self.longitude_var.get(),
                self.timezone_var.get(),
            )
            moment = zoned_time_to_utc(self.live_sky_date_var.get(), self.live_sky_time_var.get(), location.timezone)
            shifted = (moment + timedelta(minutes=minutes)).astimezone(ZoneInfo(location.timezone))
            self.live_sky_date_var.set(shifted.strftime("%Y-%m-%d"))
            self.live_sky_time_var.set(shifted.strftime("%H:%M"))
        except Exception as exc:
            self.live_sky_status_var.set(f"Could not shift Live Sky time: {exc}")
            return
        self._update_live_sky("manual")

    def _draw_live_sky(self) -> None:
        if not hasattr(self, "live_sky_canvas"):
            return
        canvas = self.live_sky_canvas
        canvas.delete("all")
        width = canvas.winfo_width() if canvas.winfo_width() > 1 else int(canvas.cget("width"))
        height = canvas.winfo_height() if canvas.winfo_height() > 1 else int(canvas.cget("height"))
        cx = width * 0.50
        cy = height * 0.52
        outer = min(width * 0.46, height * 0.44)
        canvas.create_rectangle(0, 0, width, height, fill="#020426", outline="")
        for step in range(12):
            angle = step * 30.0
            x1, y1 = _polar(cx, cy, outer * 1.16, angle)
            canvas.create_line(cx, cy, x1, y1, fill="#313255", width=1)
        for index in range(1, 13):
            radius = outer * (0.14 + index * 0.068)
            color = "#8b44dc" if index < 9 else "#14944b"
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=color, width=1)
        for index, sign in enumerate(SIGN_LABELS):
            angle = index * 30.0 + 15.0
            sx, sy = _polar(cx, cy, outer * 1.20, angle)
            canvas.create_text(sx, sy - 8, text=sign_glyph(sign), fill="#6f7435", font=("Georgia", 21, "bold"))
            canvas.create_text(sx, sy + 12, text=sign, fill="#6f7435", font=("Georgia", 8, "bold"))
        snapshot = self.live_sky_snapshot or self.selected_window or self.input_snapshot
        if not isinstance(snapshot, dict):
            canvas.create_text(cx, cy, text="Live Sky waiting for chart data", fill="#e7e2b3", font=("Georgia", 14, "bold"))
            return
        rows = live_sky_body_rows(snapshot)
        label_offsets: dict[int, int] = {}
        for row in rows:
            name = str(row["name"])
            if name == "Sun":
                canvas.create_oval(cx - 23, cy - 23, cx + 23, cy + 23, fill="#ffef28", outline="#ff8d00", width=3)
                canvas.create_text(cx + 32, cy, text="Sol", fill="#f8f0ba", font=("Segoe UI", 9, "bold"), anchor="w")
                continue
            longitude = float(row["longitude"])
            angle = wheel_degrees(longitude, 180.0)
            radius = outer * float(row.get("radiusFactor", 0.5))
            x, y = _polar(cx, cy, radius, angle)
            bucket = int(angle // 8)
            offset = label_offsets.get(bucket, 0)
            label_offsets[bucket] = offset + 1
            size = 8 if name in {"Mercury", "Venus", "Mars"} else 10
            if name == "Earth":
                size = 13
            if name == "Moon":
                size = 6
            color = str(row.get("color") or "#cfd8dc")
            canvas.create_oval(x - size, y - size, x + size, y + size, fill=color, outline="#f4f0cf" if name == "Earth" else "#101324", width=1)
            label_x = x + 12
            label_y = y - 8 - offset * 11
            canvas.create_text(label_x, label_y, text=name if name != "Moon" else "Luna", fill="#f6f3dc", font=("Segoe UI", 8, "bold"), anchor="w")
            if name == "Earth":
                moon_x, moon_y = _polar(x, y, 22, angle + 55)
                canvas.create_oval(moon_x - 5, moon_y - 5, moon_x + 5, moon_y + 5, fill=LIVE_SKY_BODY_COLORS["Moon"], outline="#f4f0cf")
                canvas.create_text(moon_x + 8, moon_y + 4, text="Luna", fill="#f6f3dc", font=("Segoe UI", 7, "bold"), anchor="w")
        canvas.create_text(width - 16, 16, text=self.live_sky_status_var.get(), fill="#ffffff", font=("Segoe UI", 12, "bold"), anchor="ne")
        canvas.create_text(
            16,
            height - 18,
            text="Map uses chart ecliptic longitudes for date navigation; distances are readable display bands.",
            fill="#9da7cf",
            font=("Segoe UI", 8),
            anchor="sw",
        )

    def _build_chart_page_strip(self) -> None:
        strip = tk.Frame(
            self.center_panel,
            bg=PALETTE["surface_soft"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=8,
            pady=6,
        )
        strip.grid(row=5, column=0, sticky="ew", pady=(5, 0))
        nav_row = tk.Frame(strip, bg=PALETTE["surface_soft"])
        nav_row.pack(fill=tk.X)
        quick_row = tk.Frame(strip, bg=PALETTE["surface_soft"])
        quick_row.pack(fill=tk.X, pady=(5, 0))

        for column, weight in ((0, 0), (1, 0), (2, 0), (3, 1), (4, 0), (5, 0)):
            nav_row.columnconfigure(column, weight=weight)
        tk.Label(nav_row, text="More detail", bg=PALETTE["surface_soft"], fg=PALETTE["accent"], font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 6))
        page_action_combo = ttk.Combobox(nav_row, textvariable=self.view_page_action_var, values=VIEW_PAGE_STRIP_ACTIONS, state="readonly", width=24)
        page_action_combo.grid(row=0, column=1, sticky="w", padx=(0, 5))
        page_action_combo.bind("<<ComboboxSelected>>", lambda _event: self._run_view_page_action(self.view_page_action_var.get()))
        ttk.Button(nav_row, text="Open Detail", command=lambda: self._run_view_page_action(self.view_page_action_var.get()), style="Compact.TButton").grid(row=0, column=2, sticky="w", padx=(0, 10))
        tk.Label(
            nav_row,
            textvariable=self.active_detail_var,
            bg=PALETTE["surface_sage"],
            fg=PALETTE["accent_dark"],
            font=("Segoe UI Semibold", 8),
            padx=8,
            pady=3,
            anchor="w",
        ).grid(row=0, column=3, sticky="ew", padx=(0, 10))
        tk.Label(nav_row, text="Workspace mode", bg=PALETTE["surface_soft"], fg=PALETTE["muted"], font=("Segoe UI", 8, "bold")).grid(row=0, column=4, sticky="e", padx=(0, 6))
        page_mode_combo = ttk.Combobox(nav_row, textvariable=self.page_mode_var, values=PAGE_MODE_NAMES, state="readonly", width=22)
        page_mode_combo.grid(row=0, column=5, sticky="e")
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
        try:
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
            elif label == "Retrogrades":
                self._apply_page_mode("retrogrades")
            elif label == "Midpoints":
                self._apply_page_mode("midpoints")
            elif label == "Live Sky":
                self._apply_page_mode("live-sky")
            elif label == "Chart Data":
                self._show_chart_inspector()
            elif label == "Save Wheel":
                self._save_chart_wheel()
            else:
                self._open_detail_page(label)
        except Exception as exc:
            self._announce_visible_action(f"{label} failed: {exc}")
            self._show_text_dialog(f"{label} Error", f"{label} could not complete:\n\n{exc}")
        else:
            self._announce_visible_action(f"{label} opened.")

    def _resize_header_labels(self, event: object) -> None:
        width = max(240, int(getattr(event, "width", 640)) - 120)
        self.title_label.configure(wraplength=width)
        self.timing_context_label.configure(wraplength=width)

    def _build_wheel_display_controls(self) -> None:
        display = tk.Frame(
            self.wheel_workspace,
            bg=PALETTE["ribbon_panel_soft"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=7,
            pady=5,
        )
        display.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        display.columnconfigure(0, weight=1)
        toolbar_row = tk.Frame(display, bg=PALETTE["ribbon_panel_soft"])
        toolbar_row.pack(fill=tk.X)
        settings_row = tk.Frame(display, bg=PALETTE["ribbon_panel_soft"])
        settings_row.pack(fill=tk.X, pady=(4, 0))
        overlay_row = tk.Frame(settings_row, bg=PALETTE["ribbon_panel_soft"])
        overlay_row.pack(side=tk.LEFT, fill=tk.X, expand=True)

        def option_label(parent: tk.Widget, text: str, *, accent: bool = False) -> tk.Label:
            return tk.Label(
                parent,
                text=text,
                bg=parent["bg"] if isinstance(parent, tk.Frame) else PALETTE["ribbon_panel_soft"],
                fg=PALETTE["accent_dark"] if accent else PALETTE["muted"],
                font=("Segoe UI", 8, "bold"),
            )

        def command_button(parent: tk.Widget, label: str, command: Callable[[], None], *, primary: bool = False) -> tk.Button:
            bg = PALETTE["accent"] if primary else PALETTE["button"]
            fg = "#fffdf6" if primary else PALETTE["text"]
            return tk.Button(
                parent,
                text=label,
                command=command,
                bg=bg,
                fg=fg,
                activebackground=PALETTE["top_nav_hover"] if primary else PALETTE["button_hover"],
                activeforeground="#fffdf6" if primary else PALETTE["accent_dark"],
                relief=tk.FLAT,
                bd=0,
                padx=7,
                pady=2,
                font=("Segoe UI Semibold", 8),
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=PALETTE["button_line"],
            )

        def combo_group(parent: tk.Widget, title: str) -> tk.Frame:
            group = tk.Frame(parent, bg=PALETTE["ribbon_panel_soft"])
            group.pack(side=tk.LEFT, padx=(0, 7))
            option_label(group, title).pack(side=tk.LEFT, padx=(0, 5))
            return group

        tk.Label(
            toolbar_row,
            text="Wheel",
            bg=PALETTE["ribbon_panel_soft"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 9, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 7))
        preset_combo = ttk.Combobox(toolbar_row, textvariable=self.wheel_view_preset_var, values=WHEEL_VIEW_PRESET_NAMES, state="readonly", width=13)
        preset_combo.pack(side=tk.LEFT, padx=(0, 6))
        preset_combo.bind("<<ComboboxSelected>>", lambda _event: self._wheel_preset_changed())
        preset_group = tk.Frame(toolbar_row, bg=PALETTE["ribbon_panel_soft"])
        preset_group.pack(side=tk.LEFT, padx=(0, 6))
        for label, command in (
            ("Clean", self._apply_clean_wheel_view),
            ("Full Classic", self._apply_full_wheel_view),
            ("Diagnostic", self._apply_diagnostic_wheel_view),
        ):
            command_button(preset_group, label, command, primary=(label == "Full Classic")).pack(side=tk.LEFT, padx=(0, 4))

        tk.Frame(toolbar_row, bg=PALETTE["panel_line"], width=1, height=22).pack(side=tk.LEFT, padx=(1, 7))
        view_group = tk.Frame(toolbar_row, bg=PALETTE["ribbon_panel_soft"])
        view_group.pack(side=tk.LEFT, fill=tk.X, expand=True)
        for label, command in (
            ("Fit", self._fit_wheel_view),
            ("Zoom -", lambda: self._adjust_wheel_zoom(-0.06)),
            ("Zoom +", lambda: self._adjust_wheel_zoom(0.06)),
        ):
            command_button(view_group, label, command).pack(side=tk.LEFT, padx=(0, 4))
        command_button(toolbar_row, "Reset Panels", self._reset_workspace_panels).pack(side=tk.RIGHT)

        theme_group = combo_group(settings_row, "Theme")
        theme_combo = ttk.Combobox(theme_group, textvariable=self.right_panel_theme_var, values=RIGHT_PANEL_THEME_NAMES, state="readonly", width=13)
        theme_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        theme_combo.bind("<<ComboboxSelected>>", lambda _event: self._wheel_theme_changed())
        point_group = combo_group(settings_row, "Points")
        point_combo = ttk.Combobox(point_group, textvariable=self.point_set_var, values=POINT_SET_NAMES, state="readonly", width=15)
        point_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        point_combo.bind("<<ComboboxSelected>>", lambda _event: self._point_set_changed())
        export_group = combo_group(settings_row, "Export")
        quality_combo = ttk.Combobox(
            export_group,
            textvariable=self.wheel_export_quality_var,
            values=WHEEL_EXPORT_QUALITY_LABELS,
            state="readonly",
            width=10,
        )
        quality_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        quality_combo.bind("<<ComboboxSelected>>", lambda _event: self._wheel_export_quality_changed())
        option_label(overlay_row, "Layers", accent=True).pack(side=tk.LEFT, padx=(0, 6))
        for label, variable in (
            ("Aspects", self.show_aspects_var),
            ("Score", self.show_score_overlay_var),
            ("Lots", self.show_lots_var),
            ("Nodes", self.show_nodes_var),
            ("Fixed Stars", self.show_fixed_stars_var),
            ("Compact", self.compact_wheel_var),
        ):
            tk.Checkbutton(
                overlay_row,
                text=label,
                variable=variable,
                command=self._display_option_changed,
                bg=PALETTE["ribbon_panel_soft"],
                activebackground=PALETTE["ribbon_panel_soft"],
                fg=PALETTE["accent_dark"],
                selectcolor=PALETTE["ribbon_panel_soft"],
                font=("Segoe UI", 7),
            ).pack(side=tk.LEFT, padx=(0, 5))
        self.wheel_preset_help_var = tk.StringVar(value="")
        self._refresh_wheel_display_help()

    def _display_option_changed(self) -> None:
        self._refresh_wheel_display_help()
        self._redraw_selected_window()
        self._save_session()
        self.status_var.set("Updated wheel display options.")

    def _wheel_export_quality_changed(self) -> None:
        self.wheel_export_scale = wheel_export_scale_value(self.wheel_export_quality_var.get())
        self.wheel_export_quality_var.set(wheel_export_scale_label(self.wheel_export_scale))
        self._refresh_wheel_display_help()
        self._save_session()
        self.status_var.set(f"Wheel export quality: {wheel_export_scale_label(self.wheel_export_scale)}.")

    def _refresh_wheel_display_help(self) -> None:
        if not hasattr(self, "wheel_preset_help_var"):
            return
        preset_id = self._current_wheel_preset_id()
        overlay_text = wheel_overlay_summary(
            aspects=bool(self.show_aspects_var.get()),
            lots=bool(self.show_lots_var.get()),
            nodes=bool(self.show_nodes_var.get()),
            fixed_stars=bool(self.show_fixed_stars_var.get()),
            score=bool(self.show_score_overlay_var.get()),
            compact=bool(self.compact_wheel_var.get()),
        )
        self.wheel_preset_help_var.set(f"{wheel_preset_help_text(preset_id)}  {overlay_text}. Export: {wheel_export_scale_label(self.wheel_export_scale)}.")

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
        self._scroll_center_to_top()
        if mode_id != "live-sky":
            self._show_wheel_workspace()
        if mode_id == "guide":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            if hasattr(self, "show_tools_var") and self.show_tools_var.get():
                self.show_tools_var.set(False)
                self._apply_tools_ribbon_visibility(save=False)
            self.show_aspects_var.set(True)
            self._show_wheel_workspace()
            self._set_workspace_page("Guide")
            self._focus_detail_page("Summary")
            self._refresh_guided_workflow()
            status = "Page mode: Guide."
        elif mode_id == "wheel-aspectarian":
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
        elif mode_id == "retrogrades":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self.show_aspects_var.set(True)
            self.compact_wheel_var.set(True)
            self._set_workspace_page("Retrogrades")
            self._focus_detail_page("Retrogrades")
            status = "Page mode: Retrogrades."
        elif mode_id == "midpoints":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self.show_aspects_var.set(True)
            self.compact_wheel_var.set(True)
            self._set_workspace_page("Midpoints")
            self._focus_detail_page("Midpoints")
            status = "Page mode: Midpoints."
        elif mode_id == "live-sky":
            self.page_mode_var.set(PAGE_MODE_LABELS[mode_id])
            self._set_workspace_page("Live Sky")
            self._focus_detail_page("Live Sky")
            self._show_live_sky_workspace()
            status = "Page mode: Live Sky."
        else:
            self.page_mode_var.set(PAGE_MODE_LABELS["wheel"])
            self.show_aspects_var.set(True)
            self._show_wheel_workspace()
            self._set_workspace_page("Wheel")
            self._focus_detail_page("Window")
            status = "Page mode: Wheel."
        self._redraw_selected_window()
        if save:
            self._save_session()
        self.status_var.set(status)

    def _set_search_workbench_visible(self, visible: bool) -> None:
        if not hasattr(self, "search_workbench_frame"):
            return
        if visible:
            self.search_workbench_frame.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        else:
            self.search_workbench_frame.grid_remove()

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
        self.workspace_panes.add(self.left_panel, minsize=280, width=305, stretch="never", padx=0)
        self.workspace_panes.add(self.center_pane, minsize=780, width=CENTER_PANE_DEFAULT_WIDTH, stretch="always", padx=6)
        self.workspace_panes.add(self.right_panel, minsize=300, width=330, stretch="never", padx=0)

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
        self._refresh_wheel_display_help()
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
        total_columns = 3
        card = tk.Frame(parent, bg=PALETTE["panel_alt"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=8, pady=4)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 7) if column < total_columns - 1 else (0, 0))
        tk.Frame(card, bg=accent_color, height=1).pack(fill=tk.X, pady=(0, 3))
        tk.Label(card, text=title, bg=PALETTE["panel_alt"], fg=accent_color, font=("Georgia", 8, "bold")).pack(anchor="w")
        tk.Label(card, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 7), wraplength=230, justify=tk.LEFT).pack(anchor="w", fill=tk.X)

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
        location_text = compact_place_name(location.name) if location else "Location unavailable"
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
