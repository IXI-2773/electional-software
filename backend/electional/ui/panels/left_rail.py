"""Left workflow rail construction and interaction methods."""

from __future__ import annotations


def bind_desktop_globals(namespace: dict[str, object]) -> None:
    """Bind the shared desktop shell namespace after desktop.py is initialized."""

    protected = {"__name__", "__package__", "__spec__", "__loader__", "__file__", "__cached__", "__builtins__"}
    globals().update({name: value for name, value in namespace.items() if name not in protected})


class DesktopLeftRailMixin:
    def _location_map(self) -> dict[str, LocationPreset]:
        locations = {location.name: location for location in LOCATION_PRESETS}
        locations.update({location.name: location for location in self.recent_locations})
        locations.update({location.name: location for location in self.user_locations})
        return locations

    def _refresh_location_choices(self) -> None:
        self.location_names = combined_visible_location_names([*self.recent_locations, *self.user_locations], self.hidden_builtin_location_ids)
        self.locations_by_name = self._location_map()
        if hasattr(self, "location_combo"):
            self.location_combo.configure(values=self.location_names)
        self._refresh_location_status()

    def _refresh_location_status(self) -> None:
        if not hasattr(self, "location_status_var"):
            return
        count_text = f"{len(self.user_locations)} custom saved location{'s' if len(self.user_locations) != 1 else ''}."
        home_text = f" Home: {self.home_location_name}." if self.home_location_name else " Home: local timezone default."
        recent_text = f" Recent: {', '.join(location.name for location in self.recent_locations[:3])}." if self.recent_locations else " Recent: none yet."
        hidden_count = len(self.hidden_builtin_location_ids)
        hidden_text = f" Hidden built-ins: {hidden_count}." if hidden_count else " Built-ins visible."
        current_location = self._current_location_from_fields() if hasattr(self, "location_name_var") else None
        warning_text = f" {timezone_warning_for_location(current_location)}" if current_location else ""
        self.location_status_var.set(count_text + home_text + recent_text + hidden_text + warning_text)

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

    def _build_left_controls(self) -> None:
        parent = getattr(self, "left_controls_parent", self.left_panel)
        header = tk.Frame(
            parent,
            bg=PALETTE["surface_sage"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=9,
            pady=6,
        )
        header.pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            header,
            text="Election Setup",
            bg=PALETTE["surface_sage"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 10, "bold"),
        ).pack(side=tk.LEFT)
        self.natal_summary = tk.Label(
            header,
            text="Tune chart, search, judge.",
            bg=PALETTE["surface_sage"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 7),
            justify=tk.RIGHT,
            anchor="e",
            wraplength=150,
        )
        self.natal_summary.pack(side=tk.RIGHT, fill=tk.X, expand=True)

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
        self.election_strategy_var = tk.StringVar(value=str(state.get("election_strategy") or "Manual"))
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
        self.target_aspect_var = tk.StringVar(value=str(state.get("target_aspect") or ""))
        self.target_aspect_body_var = tk.StringVar(value=str(state.get("target_aspect_body") or ""))
        self.target_planet_var = tk.StringVar(value=str(state.get("target_planet") or ""))
        self.target_sign_var = tk.StringVar(value=str(state.get("target_sign") or ""))
        self.target_house_var = tk.StringVar(value=str(state.get("target_house") or ""))
        self.exact_search_query_var = tk.StringVar(value=str(state.get("exact_search_query") or ""))
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
        self.location_search_var = tk.StringVar(value="")
        self.location_search_result_var = tk.StringVar(value="")
        self.location_search_status_var = tk.StringVar(value="Search a city to auto-fill coordinates and timezone.")
        scrub_state = state.get("scrub_preview") if isinstance(state.get("scrub_preview"), dict) else {}
        scrub_offset = int(scrub_state.get("offsetMinutes", 0) or 0)
        self.time_scrub_minutes_var = tk.IntVar(value=scrub_offset)
        self.time_scrub_status_var = tk.StringVar(
            value=f"Preview offset restored: {scrub_offset:+d} minutes." if scrub_offset else "Scrub preview is centered."
        )
        self.time_scrub_base_date: str | None = str(scrub_state.get("baseDate") or "") or None
        self.time_scrub_base_time: str | None = str(scrub_state.get("baseTime") or "") or None
        self.time_scrub_after_id: str | None = None

        current_box = self._left_section(parent, "Action Hub", "Next useful move for the current workflow.")
        self._build_workflow_next_step(current_box)

        timing_box = self._left_section(parent, "Timing", "")
        timing_fields = ttk.Frame(timing_box, style="Panel.TFrame")
        timing_fields.pack(fill=tk.X)
        timing_fields.columnconfigure(0, weight=1)
        timing_fields.columnconfigure(1, weight=1)
        self._labeled_entry(timing_fields, "Date", self.date_var, compact=True, column=0)
        self._labeled_entry(timing_fields, "Time", self.time_var, compact=True, column=1)
        self._button_row(
            timing_box,
            (
                ("Now", self._set_current_time),
                ("Exact", lambda: self.calculate(show_input_chart=True)),
            ),
            pady=(5, 0),
        )
        self._timing_adjustment_grid(timing_box)

        location_box = self._left_section(parent, "Location", "Save, reuse, or correct your working place.")
        self._labeled_entry(location_box, "Search city", self.location_search_var)
        self.location_search_combo = ttk.Combobox(location_box, textvariable=self.location_search_result_var, values=[], state="readonly")
        self.location_search_combo.pack(fill=tk.X, ipady=5, pady=(4, 0))
        self._button_row(
            location_box,
            (
                ("Search City", self._search_city_locations),
                ("Use Result", self._use_location_search_result),
                ("Home Wizard", self._open_home_location_wizard),
            ),
            pady=(7, 0),
        )
        tk.Label(
            location_box,
            textvariable=self.location_search_status_var,
            bg=PALETTE["surface_sage"],
            fg=PALETTE["accent_dark"],
            justify=tk.LEFT,
            wraplength=260,
            font=("Segoe UI", 8),
        ).pack(anchor="w", fill=tk.X, pady=(7, 0))
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
        self._labeled_combo(model_box, "Strategy builder", self.election_strategy_var, list(ELECTION_STRATEGY_NAMES)).bind("<<ComboboxSelected>>", self._apply_election_strategy)
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
        target_aspect_row = ttk.Frame(search_box, style="Panel.TFrame")
        target_aspect_row.pack(fill=tk.X)
        target_aspect_row.columnconfigure(0, weight=1)
        target_aspect_row.columnconfigure(1, weight=1)
        self._labeled_combo(target_aspect_row, "Find aspect", self.target_aspect_var, list(SEARCH_TARGET_ASPECTS), compact=True, column=0).bind("<<ComboboxSelected>>", lambda _event: self._update_search_summary())
        self._labeled_combo(target_aspect_row, "Involving", self.target_aspect_body_var, list(SEARCH_TARGET_PLANETS), compact=True, column=1).bind("<<ComboboxSelected>>", lambda _event: self._update_search_summary())
        target_placement_row = ttk.Frame(search_box, style="Panel.TFrame")
        target_placement_row.pack(fill=tk.X)
        target_placement_row.columnconfigure(0, weight=1)
        target_placement_row.columnconfigure(1, weight=1)
        self._labeled_combo(target_placement_row, "Planet target", self.target_planet_var, list(SEARCH_TARGET_PLANETS), compact=True, column=0).bind("<<ComboboxSelected>>", lambda _event: self._update_search_summary())
        self._labeled_combo(target_placement_row, "Sign target", self.target_sign_var, list(SEARCH_TARGET_SIGNS), compact=True, column=1).bind("<<ComboboxSelected>>", lambda _event: self._update_search_summary())
        house_target_row = ttk.Frame(search_box, style="Panel.TFrame")
        house_target_row.pack(fill=tk.X)
        house_target_row.columnconfigure(0, weight=1)
        house_target_row.columnconfigure(1, weight=1)
        self._labeled_combo(house_target_row, "House target", self.target_house_var, list(SEARCH_TARGET_HOUSES), compact=True, column=0).bind("<<ComboboxSelected>>", lambda _event: self._update_search_summary())
        ttk.Button(house_target_row, text="Clear targets", command=self._clear_search_targets, style="Compact.TButton").grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=(22, 0))
        self._labeled_entry(search_box, "Exact search query", self.exact_search_query_var)
        self._button_row(
            search_box,
            (
                ("Apply Query", self._apply_exact_search_query),
                ("Aspect Search", self._run_aspect_planet_search_workbench),
            ),
            pady=(6, 0),
        )
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
        self._button_row(
            action_box,
            (
                ("Why Not?", self._show_why_not_this_time_dialog),
                ("Find Peaks", self._show_aspect_peak_finder_dialog),
                ("Alerts", self._show_election_alerts_dialog),
            ),
            pady=(7, 0),
        )
        self._button_row(
            action_box,
            (
                ("Aspect Search", self._run_aspect_planet_search_workbench),
                ("Compare Top", lambda: self._focus_detail_page("Compare")),
            ),
            pady=(7, 0),
        )
        self._button_row(
            action_box,
            (("PDF Intake", lambda: self._focus_detail_page("PDF Intake")),),
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

    def _left_section(self, parent: tk.Widget, title: str, subtitle: str = "", *, collapsed: bool | None = None) -> tk.Frame:
        collapsed = left_section_initially_collapsed(title) if collapsed is None else bool(collapsed)
        section = tk.Frame(
            parent,
            bg=PALETTE["panel_alt"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=9,
            pady=7,
        )
        section.pack(fill=tk.X, pady=(0, 8))
        tk.Frame(section, bg=PALETTE["accent"], height=2).pack(fill=tk.X, pady=(0, 5))
        header = tk.Frame(section, bg=PALETTE["panel_alt"])
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=title,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 9, "bold"),
            anchor="w",
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        toggle_var = tk.StringVar(value="Show" if collapsed else "Hide")
        self.left_section_toggle_vars[title] = toggle_var
        toggle = tk.Button(
            header,
            textvariable=toggle_var,
            command=lambda name=title: self._toggle_left_section(name),
            bg=PALETTE["button"],
            fg=PALETTE["accent_dark"],
            activebackground=PALETTE["button_hover"],
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=1,
            font=("Segoe UI", 7, "bold"),
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=PALETTE["button_line"],
        )
        toggle.pack(side=tk.RIGHT)
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
            ).pack(fill=tk.X, pady=(1, 2))
        body = tk.Frame(section, bg=PALETTE["panel_alt"])
        if not hasattr(self, "left_section_frames"):
            self.left_section_frames = {}
        self.left_section_frames[title] = section
        self.left_section_bodies[title] = body
        if not collapsed:
            body.pack(fill=tk.X)
        return body

    def _scroll_left_section_into_view(self, title: str) -> None:
        section = getattr(self, "left_section_frames", {}).get(title)
        if section is None or not hasattr(self, "left_scroll_canvas"):
            return
        self.left_scroll_canvas.update_idletasks()
        canvas = self.left_scroll_canvas
        bbox = canvas.bbox("all")
        if not bbox:
            return
        scroll_height = max(1, bbox[3] - bbox[1])
        target = max(0, section.winfo_y() - 12)
        canvas.yview_moveto(min(1.0, target / scroll_height))

    def _toggle_left_section(self, title: str) -> None:
        body = self.left_section_bodies.get(title)
        variable = self.left_section_toggle_vars.get(title)
        if body is None or variable is None:
            return
        if body.winfo_ismapped():
            body.pack_forget()
            variable.set("Show")
            state = "collapsed"
        else:
            body.pack(fill=tk.X)
            variable.set("Hide")
            state = "expanded"
        if hasattr(self, "left_scroll_canvas"):
            self.left_scroll_canvas.configure(scrollregion=self.left_scroll_canvas.bbox("all"))
        if hasattr(self, "status_var"):
            self.status_var.set(f"{title} section {state}.")
        if state == "expanded":
            self._scroll_left_section_into_view(title)

    def _build_left_status_chips(self, parent: tk.Widget) -> None:
        self.left_status_chip_vars = [tk.StringVar(value="") for _ in range(4)]
        grid = tk.Frame(parent, bg=PALETTE["panel"])
        grid.pack(fill=tk.X, pady=(5, 0))
        for column in range(2):
            grid.columnconfigure(column, weight=1, uniform="left-status")
        for variable in self.left_status_chip_vars:
            index = len([child for child in grid.winfo_children() if isinstance(child, tk.Frame)])
            chip = tk.Frame(
                grid,
                bg=PALETTE["chip"],
                highlightbackground=PALETTE["chip_line"],
                highlightthickness=1,
                padx=6,
                pady=4,
            )
            chip.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0 if index % 2 == 0 else 3, 0 if index % 2 == 1 else 3),
                pady=(0 if index < 2 else 5, 0),
            )
            tk.Label(
                chip,
                textvariable=variable,
                bg=PALETTE["chip"],
                fg=PALETTE["top_bar_dark"],
                font=("Segoe UI Semibold", 7),
                wraplength=126,
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
            padx=7,
            pady=5,
        )
        guide.pack(fill=tk.X, pady=(2, 0))
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
        ).pack(fill=tk.X)
        tk.Label(
            guide,
            textvariable=self.workflow_step_body_var,
            bg=PALETTE["surface_sage"],
            fg=PALETTE["text"],
            font=("Segoe UI", 7),
            wraplength=260,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(1, 0))
        self._button_row(
            guide,
            (
                ("Current", lambda: self.calculate(show_input_chart=True)),
                ("Find Best", self._run_electional_search_workbench),
                ("Analysis", lambda: self._focus_detail_page("Analysis")),
            ),
            pady=(5, 0),
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
        if isinstance(getattr(self, "selected_window", None), dict):
            self._refresh_workspace_hub(self.selected_window, self.input_snapshot or self.selected_window, self.current_location)
        self._refresh_guided_workflow()

    def _refresh_workspace_hub(
        self,
        snapshot: dict[str, object] | None,
        input_snapshot: dict[str, object] | None,
        location: LocationPreset | None,
    ) -> None:
        if not hasattr(self, "input_state_var"):
            return
        cards = workspace_hub_cards(
            snapshot,
            input_snapshot,
            location,
            self.current_aspect_highlights if isinstance(self.current_aspect_highlights, Mapping) else {},
            self.current_windows,
            selected_index=int(getattr(self, "selected_window_index", -1)),
            displayed_source=str(getattr(self, "displayed_chart_source", "")),
            rejection_summary=self.current_rejection_summary if isinstance(self.current_rejection_summary, Mapping) else {},
        )
        variables = (self.input_state_var, self.selected_state_var, self.offset_state_var)
        for variable, (_title, headline, detail, _tone) in zip(variables, cards):
            variable.set(f"{headline}\n{detail}")

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
        grid.pack(fill=tk.X, pady=(5, 0))
        for column in range(4):
            grid.columnconfigure(column, weight=1, uniform="timing-grid")

        def section_label(text: str, row: int) -> None:
            tk.Label(
                grid,
                text=text,
                bg=PALETTE["panel"],
                fg=PALETTE["accent_dark"],
                font=("Segoe UI", 7, "bold"),
                anchor="w",
            ).grid(row=row, column=0, columnspan=4, sticky="ew", pady=(0 if row == 0 else 4, 2))

        def button_row(row: int, actions: tuple[tuple[str, Callable[[], None]], ...]) -> None:
            for column, (label, command) in enumerate(actions):
                ttk.Button(grid, text=label, command=command, style="Compact.TButton").grid(
                    row=row,
                    column=column,
                    sticky="ew",
                    padx=(0 if column == 0 else 3, 0 if column == len(actions) - 1 else 3),
                )

        section_label("Hours", 0)
        button_row(
            1,
            (
                ("-2h", lambda: self._shift_time(-2)),
                ("-1h", lambda: self._shift_time(-1)),
                ("+1h", lambda: self._shift_time(1)),
                ("+2h", lambda: self._shift_time(2)),
            ),
        )
        section_label("Fine tune", 2)
        button_row(
            3,
            (
                ("-15m", lambda: self._shift_time_minutes(-15)),
                ("-5m", lambda: self._shift_time_minutes(-5)),
                ("+5m", lambda: self._shift_time_minutes(5)),
                ("+15m", lambda: self._shift_time_minutes(15)),
            ),
        )
        ttk.Button(grid, text="Calculate exact chart time", command=lambda: self.calculate(show_input_chart=True), style="Compact.TButton").grid(
            row=4,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(5, 0),
        )
        tk.Scale(
            grid,
            from_=-180,
            to=180,
            resolution=5,
            orient=tk.HORIZONTAL,
            variable=self.time_scrub_minutes_var,
            command=self._time_scrub_changed,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            troughcolor=PALETTE["surface_sage"],
            highlightthickness=0,
            showvalue=True,
            length=180,
            font=("Segoe UI", 7),
        ).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(7, 0), padx=(0, 4))
        ttk.Button(grid, text="Commit", command=self._commit_time_scrub, style="Compact.TButton").grid(
            row=5,
            column=3,
            sticky="ew",
            pady=(7, 0),
        )
        ttk.Button(grid, text="Reset scrub", command=self._reset_time_scrub, style="Compact.TButton").grid(
            row=6,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(5, 0),
            padx=(0, 3),
        )
        ttk.Button(grid, text="Preview now", command=self._preview_time_scrub, style="Compact.TButton").grid(
            row=6,
            column=2,
            columnspan=2,
            sticky="ew",
            pady=(5, 0),
            padx=(3, 0),
        )
        tk.Label(
            grid,
            textvariable=self.time_scrub_status_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["muted"],
            justify=tk.LEFT,
            wraplength=255,
            font=("Segoe UI", 7),
        ).grid(row=7, column=0, columnspan=4, sticky="ew", pady=(5, 0))

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

    def _labeled_combo(
        self,
        parent: tk.Widget,
        label: str,
        variable: tk.StringVar,
        values: list[str],
        *,
        compact: bool = False,
        column: int | None = None,
    ) -> ttk.Combobox:
        container = ttk.Frame(parent, style="Panel.TFrame")
        if column is None:
            container.pack(fill=tk.X, pady=(7 if compact else 10, 0))
        else:
            container.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 6, 0))
        ttk.Label(container, text=label, style="Small.TLabel").pack(anchor="w", pady=(0, 3))
        combo = ttk.Combobox(container, textvariable=variable, values=values, state="readonly")
        combo.pack(fill=tk.X, ipady=3 if compact else 5)
        return combo

    def _current_location_from_fields(self) -> LocationPreset | None:
        try:
            return build_custom_location(
                self.location_name_var.get(),
                self.latitude_var.get(),
                self.longitude_var.get(),
                self.timezone_var.get(),
            )
        except (TypeError, ValueError):
            return None

    def _apply_location_fields(self, location: LocationPreset, *, remember: bool = True, calculate: bool = True) -> None:
        self.location_var.set(location.name)
        self.location_name_var.set(location.name)
        self.latitude_var.set(f"{location.latitude:.4f}")
        self.longitude_var.set(f"{location.longitude:.4f}")
        self.timezone_var.set(location.timezone)
        if remember:
            self.recent_locations = remember_recent_location(location)
            self._refresh_location_choices()
            self.location_var.set(location.name)
        self._refresh_location_status()
        if calculate:
            self.calculate(show_input_chart=True)

    def _search_city_locations(self) -> None:
        query = self.location_search_var.get().strip() or self.location_name_var.get().strip() or self.location_var.get().strip()
        self.location_search_results = search_city_locations(
            query,
            saved_locations=self.user_locations,
            recent_locations=self.recent_locations,
        )
        labels = [location_search_result_label(result) for result in self.location_search_results]
        self.location_search_result_labels = dict(zip(labels, self.location_search_results))
        if hasattr(self, "location_search_combo"):
            self.location_search_combo.configure(values=labels)
        if labels:
            self.location_search_result_var.set(labels[0])
            first_location = self.location_search_results[0].location
            self.location_search_status_var.set(
                f"{len(labels)} match{'es' if len(labels) != 1 else ''}. Best: {first_location.name}. {timezone_warning_for_location(first_location)}"
            )
            self.status_var.set(f"City search found {len(labels)} location match{'es' if len(labels) != 1 else ''}.")
        else:
            self.location_search_result_var.set("")
            self.location_search_status_var.set("No city match found. Try city + state/country, or enter coordinates manually.")
            self.status_var.set("No city search results.")

    def _selected_location_search_result(self) -> LocationSearchResult | None:
        label = self.location_search_result_var.get()
        result = self.location_search_result_labels.get(label)
        if result:
            return result
        if not self.location_search_results:
            self._search_city_locations()
        return self.location_search_results[0] if self.location_search_results else None

    def _use_location_search_result(self) -> None:
        result = self._selected_location_search_result()
        if not result:
            return
        location = result.location
        self._apply_location_fields(location)
        self.location_search_status_var.set(timezone_warning_for_location(location))
        self.status_var.set(f"Using searched location: {location.name}.")
        self._log_event(f"Used searched location: {location.name}")

    def _open_home_location_wizard(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Home Location Setup")
        dialog.geometry("560x300")
        dialog.configure(bg=PALETTE["app_bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        query_var = tk.StringVar(value=self.location_search_var.get() or self.location_name_var.get())
        result_var = tk.StringVar(value="")
        status_var = tk.StringVar(value="Search your home city, choose the best match, then save it as Home.")
        result_map: dict[str, LocationSearchResult] = {}

        frame = tk.Frame(dialog, bg=PALETTE["panel_alt"], padx=14, pady=12)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        tk.Label(frame, text="Home Location Setup", bg=PALETTE["panel_alt"], fg=PALETTE["accent_dark"], font=("Georgia", 12, "bold")).pack(anchor="w")
        tk.Label(
            frame,
            text="This controls the app default, recent places, timezone, and guided workflow location step.",
            bg=PALETTE["panel_alt"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 8),
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(2, 8))
        entry = tk.Entry(frame, textvariable=query_var, bg=PALETTE["panel"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"])
        entry.pack(fill=tk.X, ipady=6)
        combo = ttk.Combobox(frame, textvariable=result_var, values=[], state="readonly")
        combo.pack(fill=tk.X, ipady=5, pady=(8, 0))
        tk.Label(frame, textvariable=status_var, bg=PALETTE["surface_sage"], fg=PALETTE["accent_dark"], font=("Segoe UI", 8), wraplength=520, justify=tk.LEFT).pack(fill=tk.X, pady=(8, 0))

        def run_search() -> None:
            nonlocal result_map
            results = search_city_locations(query_var.get(), saved_locations=self.user_locations, recent_locations=self.recent_locations)
            labels = [location_search_result_label(result) for result in results]
            result_map = dict(zip(labels, results))
            combo.configure(values=labels)
            if labels:
                result_var.set(labels[0])
                status_var.set(f"Best match: {results[0].location.name}. {timezone_warning_for_location(results[0].location)}")
            else:
                result_var.set("")
                status_var.set("No match yet. Try a more specific city, state, or country.")

        def save_home() -> None:
            result = result_map.get(result_var.get())
            if not result:
                run_search()
                result = result_map.get(result_var.get())
            if not result:
                return
            location = result.location
            builtin_names = {preset.name for preset in LOCATION_PRESETS}
            if location.name not in builtin_names:
                self.user_locations = upsert_user_location(self.user_locations, location)
                save_user_locations(self.user_locations)
            self.home_location_name = location.name
            save_home_location_name(location.name)
            self._apply_location_fields(location, remember=True, calculate=True)
            self.status_var.set(f"Home location wizard saved: {location.name}.")
            self._log_event(f"Home location wizard saved: {location.name}")
            dialog.destroy()

        buttons = tk.Frame(frame, bg=PALETTE["panel_alt"])
        buttons.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(buttons, text="Search", command=run_search, style="Compact.TButton").pack(side=tk.LEFT)
        ttk.Button(buttons, text="Save As Home", command=save_home, style="Compact.TButton").pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy, style="Compact.TButton").pack(side=tk.RIGHT)
        entry.bind("<Return>", lambda _event: run_search())
        run_search()

    def _load_selected_location(self, _event: object | None = None) -> None:
        location = self.locations_by_name.get(self.location_var.get(), get_location(None))
        self._apply_location_fields(location, remember=True, calculate=False)

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
        self.recent_locations = remember_recent_location(location)
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
        self.recent_locations = remember_recent_location(location)
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
        self._apply_location_fields(location, remember=True, calculate=False)
        label = "saved home" if self.home_location_name else "local default"
        self.status_var.set(f"Loaded {label} location: {location.name}.")
        self._log_event(f"Loaded {label} location: {location.name}")
        self.calculate(show_input_chart=True)

    def _use_default_location(self) -> None:
        location = default_location_for_timezone()
        self._apply_location_fields(location, remember=True, calculate=False)
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
        self._apply_location_fields(fallback, remember=True, calculate=False)
        self.status_var.set(f"Hid built-in location: {location.name}. Use Reset Locations to restore it.")
        self._log_event(f"Hid built-in location: {location.name}")
        self.calculate(show_input_chart=True)

    def _reset_locations(self) -> None:
        self.hidden_builtin_location_ids = set()
        self.home_location_name = None
        self.recent_locations = []
        save_recent_locations([])
        reset_location_defaults()
        self._refresh_location_choices()
        location = home_location_for_app(user_locations=self.user_locations)
        self._apply_location_fields(location, remember=False, calculate=False)
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
        self._apply_location_fields(fallback, remember=True, calculate=False)
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

    def _apply_election_strategy(self, _event: object | None = None) -> None:
        strategy_name = self.election_strategy_var.get()
        values = election_strategy_values(strategy_name)
        if not values:
            self.election_strategy_var.set("Manual")
            self.status_var.set("Strategy builder set to Manual; current filters stay unchanged.")
            self._update_search_summary()
            return
        if values.get("objective"):
            self.objective_var.set(str(values["objective"]))
        if values.get("search_preset"):
            self._apply_search_filter_preset(str(values["search_preset"]))
        if values.get("quality_mode"):
            self.search_quality_mode_var.set(str(values["quality_mode"]))
        for variable_name, key in (
            ("scan_hours_var", "scan_hours"),
            ("step_minutes_var", "step_minutes"),
            ("target_aspect_var", "target_aspect"),
            ("target_aspect_body_var", "target_aspect_body"),
            ("target_planet_var", "target_planet"),
            ("target_sign_var", "target_sign"),
            ("target_house_var", "target_house"),
        ):
            if key in values:
                getattr(self, variable_name).set(str(values.get(key) or ""))
        for variable_name, key in (
            ("require_applying_support_var", "require_applying_support"),
            ("require_angular_benefic_var", "require_angular_benefic"),
            ("avoid_major_stress_var", "avoid_major_stress"),
            ("avoid_angular_malefics_var", "avoid_angular_malefics"),
            ("require_moon_non_void_var", "require_moon_non_void"),
            ("avoid_objective_antipatterns_var", "avoid_objective_antipatterns"),
        ):
            if key in values:
                getattr(self, variable_name).set(bool(values[key]))
        self._update_search_summary()
        self._save_session()
        self.status_var.set(f"Applied {strategy_name}: objective, filters, target aspect, and target placement updated.")

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

    def _apply_exact_search_query(self) -> None:
        parsed = parse_exact_search_query(self.exact_search_query_var.get())
        if not parsed:
            self.status_var.set("Exact search query is empty or could not be parsed.")
            return
        mapping = (
            ("target_aspect", self.target_aspect_var),
            ("target_aspect_body", self.target_aspect_body_var),
            ("target_planet", self.target_planet_var),
            ("target_sign", self.target_sign_var),
            ("target_house", self.target_house_var),
        )
        for key, variable in mapping:
            if key in parsed:
                variable.set(str(parsed[key]))
        self._update_search_summary()
        self._save_session()
        self.status_var.set(exact_search_query_summary(self.exact_search_query_var.get()))

    def _update_search_summary(self) -> None:
        try:
            config = self._current_search_config()
        except ValueError:
            self.search_summary_var.set("Search settings need attention.")
            self._refresh_left_status_chips()
            return
        self.search_summary_var.set(format_search_summary(config))
        if hasattr(self, "exact_search_query_var") and self.exact_search_query_var.get().strip():
            self.search_summary_var.set(f"{format_search_summary(config)}\n{exact_search_query_summary(self.exact_search_query_var.get())}")
        self._refresh_left_status_chips()

    def _current_search_config(self) -> SearchConfig:
        return build_search_config_from_text(
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

    def _clear_search_targets(self) -> None:
        for variable in (
            self.target_aspect_var,
            self.target_aspect_body_var,
            self.target_planet_var,
            self.target_sign_var,
            self.target_house_var,
            self.exact_search_query_var,
        ):
            variable.set("")
        self._update_search_summary()
        self.status_var.set("Cleared targeted aspect and planet-placement search filters.")

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

    def _apply_time_scrub(self) -> None:
        minutes = int(self.time_scrub_minutes_var.get())
        if minutes == 0:
            self.status_var.set("Time scrubber is centered; no time change applied.")
            return
        self.time_scrub_minutes_var.set(0)
        self._shift_time_minutes(minutes)

    def _time_scrub_changed(self, _value: object | None = None) -> None:
        if self.time_scrub_base_date is None:
            self.time_scrub_base_date = self.date_var.get()
            self.time_scrub_base_time = self.time_var.get()
        minutes = int(self.time_scrub_minutes_var.get())
        if minutes == 0:
            self.time_scrub_status_var.set("Scrub preview is centered.")
        else:
            sign = "+" if minutes > 0 else ""
            self.time_scrub_status_var.set(f"Preview pending: {sign}{minutes} minutes from {self.time_scrub_base_date} {self.time_scrub_base_time}.")
        if self.time_scrub_after_id:
            try:
                self.root.after_cancel(self.time_scrub_after_id)
            except tk.TclError:
                pass
        self.time_scrub_after_id = self.root.after(450, self._preview_time_scrub)

    def _preview_time_scrub(self) -> None:
        self.time_scrub_after_id = None
        minutes = int(self.time_scrub_minutes_var.get())
        if minutes == 0:
            return
        base_date = self.time_scrub_base_date or self.date_var.get()
        base_time = self.time_scrub_base_time or self.time_var.get()
        try:
            preview_date, preview_time = shift_local_datetime_minutes(base_date, base_time, self.timezone_var.get(), minutes)
        except Exception as exc:
            self.time_scrub_status_var.set(f"Preview failed: {exc}")
            return
        current_date, current_time = self.date_var.get(), self.time_var.get()
        try:
            self.date_var.set(preview_date)
            self.time_var.set(preview_time)
            self.calculate(show_input_chart=True)
        finally:
            self.date_var.set(base_date)
            self.time_var.set(base_time)
            self._save_session()
        if self.input_snapshot and self.selected_window:
            self.displayed_chart_source = "preview"
            self._set_timing_context(self.input_snapshot, self.selected_window, self.current_location)
        sign = "+" if minutes > 0 else ""
        self.time_scrub_status_var.set(f"Previewing {sign}{minutes}m: {preview_date} {preview_time}. Commit to make it the input time.")
        self.status_var.set(f"Previewed scrubbed chart at {preview_date} {preview_time}; input remains {current_date} {current_time}.")

    def _commit_time_scrub(self) -> None:
        minutes = int(self.time_scrub_minutes_var.get())
        if minutes == 0:
            self.status_var.set("Time scrubber is centered; nothing to commit.")
            return
        base_date = self.time_scrub_base_date or self.date_var.get()
        base_time = self.time_scrub_base_time or self.time_var.get()
        next_date, next_time = shift_local_datetime_minutes(base_date, base_time, self.timezone_var.get(), minutes)
        self.time_scrub_minutes_var.set(0)
        self.time_scrub_base_date = None
        self.time_scrub_base_time = None
        self.date_var.set(next_date)
        self.time_var.set(next_time)
        self.displayed_chart_source = "input chart"
        self.time_scrub_status_var.set(f"Committed scrubbed time: {next_date} {next_time}.")
        self.calculate(show_input_chart=True)

    def _reset_time_scrub(self) -> None:
        if self.time_scrub_after_id:
            try:
                self.root.after_cancel(self.time_scrub_after_id)
            except tk.TclError:
                pass
            self.time_scrub_after_id = None
        self.time_scrub_minutes_var.set(0)
        if self.time_scrub_base_date and self.time_scrub_base_time:
            self.date_var.set(self.time_scrub_base_date)
            self.time_var.set(self.time_scrub_base_time)
        self.time_scrub_base_date = None
        self.time_scrub_base_time = None
        self.time_scrub_status_var.set("Scrub preview reset.")
        self.calculate(show_input_chart=True)

    def _set_current_time(self) -> None:
        timezone_name = self.timezone_var.get() or DEFAULT_TIMEZONE
        now = datetime.now(ZoneInfo(timezone_name))
        self.date_var.set(now.strftime("%Y-%m-%d"))
        self.time_var.set(now.strftime("%H:%M"))
        self.calculate(show_input_chart=True)

    def _build_guided_workflow_panel(self) -> None:
        panel = tk.Frame(
            self.center_panel,
            bg=PALETTE["surface_sage"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
            padx=7,
            pady=3,
        )
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        panel.columnconfigure(0, weight=1)
        title = tk.Frame(panel, bg=PALETTE["surface_sage"])
        title.grid(row=0, column=0, sticky="ew")
        title.columnconfigure(1, weight=1)
        tk.Label(
            title,
            text="Guided Election Workbench",
            bg=PALETTE["surface_sage"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 8, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self.guided_workflow_summary_var = tk.StringVar(value="Follow the seven-step election workflow.")
        tk.Label(
            title,
            textvariable=self.guided_workflow_summary_var,
            bg=PALETTE["surface_sage"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 7),
            wraplength=620,
            justify=tk.LEFT,
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(10, 0))
        steps_frame = tk.Frame(panel, bg=PALETTE["surface_sage"])
        steps_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))
        self.guided_step_widgets: dict[str, dict[str, tk.Widget | tk.StringVar]] = {}
        for index, (step_id, number, label) in enumerate(GUIDED_WORKFLOW_STEPS):
            steps_frame.columnconfigure(index, weight=1, uniform="guided-steps")
            card = tk.Frame(
                steps_frame,
                bg=PALETTE["button"],
                highlightbackground=PALETTE["panel_line"],
                highlightthickness=1,
                padx=5,
                pady=4,
            )
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 2, 0 if index == len(GUIDED_WORKFLOW_STEPS) - 1 else 2))
            title_var = tk.StringVar(value=f"{number} {label}")
            value_var = tk.StringVar(value="")
            action_var = tk.StringVar(value="Open")
            title_label = tk.Label(card, textvariable=title_var, bg=PALETTE["button"], fg=PALETTE["accent_dark"], font=("Segoe UI", 7, "bold"))
            title_label.pack(fill=tk.X)
            value_label = tk.Label(card, textvariable=value_var, bg=PALETTE["button"], fg=PALETTE["text"], font=("Segoe UI", 7), wraplength=118, justify=tk.CENTER)
            value_label.pack(fill=tk.X, pady=(1, 1))
            button = tk.Button(
                card,
                textvariable=action_var,
                command=lambda target=step_id: self._guided_step_action(target),
                bg=PALETTE["button"],
                fg=PALETTE["accent_dark"],
                activebackground=PALETTE["button_hover"],
                activeforeground=PALETTE["accent_dark"],
                relief=tk.FLAT,
                bd=0,
                highlightbackground=PALETTE["button_line"],
                highlightthickness=1,
                padx=4,
                pady=1,
                font=("Segoe UI", 7, "bold"),
                cursor="hand2",
            )
            button.pack(fill=tk.X)
            self.guided_step_widgets[step_id] = {
                "card": card,
                "title": title_var,
                "value": value_var,
                "action": action_var,
                "button": button,
                "value_label": value_label,
            }
        self.location_intelligence_var = tk.StringVar(value="Location intelligence waiting.")
        tk.Label(
            panel,
            textvariable=self.location_intelligence_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["accent_dark"],
            font=("Segoe UI", 8),
            justify=tk.LEFT,
            anchor="w",
            wraplength=720,
            padx=8,
            pady=5,
        ).grid(row=2, column=0, sticky="ew", pady=(5, 0))
        location_actions = tk.Frame(panel, bg=PALETTE["surface_sage"])
        location_actions.grid(row=3, column=0, sticky="e", pady=(4, 0))
        for label, command in (
            ("Search City", self._search_city_locations),
            ("Use Home", self._use_home_location),
            ("Home Wizard", self._open_home_location_wizard),
        ):
            ttk.Button(location_actions, text=label, command=command, style="Compact.TButton").pack(side=tk.LEFT, padx=(0, 5))
        self._refresh_guided_workflow()

    def _guided_step_colors(self, status: str) -> tuple[str, str]:
        if status == "done":
            return PALETTE["surface_support"], PALETTE["support"]
        if status == "active":
            return PALETTE["surface_gold"], PALETTE["warning"]
        return PALETTE["surface_soft"], PALETTE["muted"]

    def _guided_workflow_rows(self) -> tuple[dict[str, str], ...]:
        return guided_workflow_rows(
            objective=self.objective_var.get() if hasattr(self, "objective_var") else "",
            location_name=self.location_name_var.get() if hasattr(self, "location_name_var") else "",
            date_text=self.date_var.get() if hasattr(self, "date_var") else "",
            time_text=self.time_var.get() if hasattr(self, "time_var") else "",
            scan_hours=self.scan_hours_var.get() if hasattr(self, "scan_hours_var") else "",
            step_minutes=self.step_minutes_var.get() if hasattr(self, "step_minutes_var") else "",
            has_chart=bool(self.selected_window or self.input_snapshot),
            candidate_count=len(getattr(self, "current_windows", [])),
            shortlisted_count=len(getattr(self, "shortlist", [])),
            selected_index=int(getattr(self, "selected_window_index", -1)),
            displayed_source=str(getattr(self, "displayed_chart_source", "")),
        )

    def _refresh_guided_workflow(self) -> None:
        if not hasattr(self, "guided_step_widgets"):
            return
        rows = self._guided_workflow_rows()
        counts = guided_workflow_status_counts(rows)
        if hasattr(self, "guided_workflow_summary_var"):
            headline, detail = guided_workbench_summary(rows)
            self.guided_workflow_summary_var.set(f"{headline}. {detail}")
        if hasattr(self, "location_intelligence_var"):
            current_location = self._current_location_from_fields() if hasattr(self, "location_name_var") else None
            warning = timezone_warning_for_location(current_location) if current_location else "Timezone check waiting."
            self.location_intelligence_var.set(
                "\n".join(
                    location_intelligence_lines(
                        location_name=self.location_name_var.get() if hasattr(self, "location_name_var") else "",
                        timezone_name=self.timezone_var.get() if hasattr(self, "timezone_var") else "",
                        latitude=self.latitude_var.get() if hasattr(self, "latitude_var") else "",
                        longitude=self.longitude_var.get() if hasattr(self, "longitude_var") else "",
                        home_location_name=getattr(self, "home_location_name", None),
                        recent_locations=getattr(self, "recent_locations", []),
                        saved_count=len(getattr(self, "user_locations", [])),
                        timezone_warning=warning,
                    )
                )
            )
        for row in rows:
            step_id = row["id"]
            widgets = self.guided_step_widgets.get(step_id)
            if not widgets:
                continue
            bg, accent = self._guided_step_colors(row["status"])
            card = widgets["card"]
            button = widgets["button"]
            value_label = widgets.get("value_label")
            if isinstance(card, tk.Frame):
                card.configure(bg=bg, highlightbackground=accent)
                for child in card.winfo_children():
                    if isinstance(child, (tk.Label, tk.Button)):
                        child.configure(bg=bg)
            elif isinstance(card, tk.Button):
                card.configure(bg=bg, activebackground=bg, highlightbackground=accent)
            if isinstance(value_label, tk.Label):
                value_label.configure(fg=PALETTE["text"])
            if isinstance(button, tk.Button):
                button.configure(fg=accent, activebackground=bg)
            title_var = widgets["title"]
            value_var = widgets["value"]
            action_var = widgets["action"]
            if isinstance(title_var, tk.StringVar):
                title_var.set(f"{row['number']} {row['label']}")
            if isinstance(value_var, tk.StringVar):
                value_var.set(row["value"])
            if isinstance(action_var, tk.StringVar):
                action_var.set(row["action"])

    def _show_left_section(self, title: str) -> None:
        body = self.left_section_bodies.get(title)
        variable = self.left_section_toggle_vars.get(title)
        if body is not None and not body.winfo_ismapped():
            body.pack(fill=tk.X)
            if variable is not None:
                variable.set("Hide")
            if hasattr(self, "left_scroll_canvas"):
                self.left_scroll_canvas.configure(scrollregion=self.left_scroll_canvas.bbox("all"))

    def _guided_step_action(self, step_id: str) -> None:
        if step_id == "objective":
            self._show_left_section("Election Model")
            self._scroll_left_section_into_view("Election Model")
            self._announce_visible_action("Step 1: choose what you are electing in Election Model.")
        elif step_id == "location":
            self._show_left_section("Location")
            self._scroll_left_section_into_view("Location")
            self._announce_visible_action("Step 2: confirm where the election happens.")
        elif step_id == "range":
            self._show_left_section("Search Strategy")
            self._scroll_left_section_into_view("Search Strategy")
            self._announce_visible_action("Step 3: set the allowed scan range.")
        elif step_id == "times":
            self._show_left_section("Timing")
            self._scroll_left_section_into_view("Timing")
            self._announce_visible_action("Step 4: set realistic start time and step size.")
        elif step_id == "search":
            self._run_electional_search_workbench()
        elif step_id == "compare":
            self._focus_detail_page("Compare")
            self._announce_visible_action("Step 6: compare top windows, then shortlist serious picks.")
        elif step_id == "export":
            if self.shortlist:
                self._save_comparison_sheet()
            else:
                self._save_current_report()
        self._refresh_guided_workflow()
