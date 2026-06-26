"""Right judgment, detail notebook, and candidate board methods."""

from __future__ import annotations


def bind_desktop_globals(namespace: dict[str, object]) -> None:
    """Bind the shared desktop shell namespace after desktop.py is initialized."""

    protected = {"__name__", "__package__", "__spec__", "__loader__", "__file__", "__cached__", "__builtins__"}
    globals().update({name: value for name, value in namespace.items() if name not in protected})


class DesktopRightPanelMixin:
    def _build_right_panel(self) -> None:
        self._build_metric_panel()
        self._build_window_list_panel()
        self.detail_notebook = ttk.Notebook(self.right_panel)
        self.detail_notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 9))
        self.summary_text = self._text_tab("Summary")
        self.window_detail_text = self._text_tab("Window")
        self.analysis_canvas, self.analysis_frame = self._visual_tab("Analysis")
        self.timeline_canvas, self.timeline_frame = self._visual_tab("Timeline")
        self.validation_canvas, self.validation_frame = self._visual_tab("Validation")
        self.reports_canvas, self.reports_frame = self._visual_tab("Reports")
        self._build_more_detail_tab()
        self.advisor_text = self._more_text_page("Advisor")
        self.improve_text = self._more_text_page("Improve")
        self.decision_text = self._more_text_page("Decision")
        self.compare_text = self._more_text_page("Compare")
        self.diagnostics_text = self._more_text_page("Diagnostics")
        self.search_text = self._more_text_page("Search")
        self.interpretation_text = self._more_text_page("Focus")
        self.score_detail_text = self._more_text_page("Score")
        self.accounting_text = self._more_text_page("Accounting")
        self.conditions_text = self._more_text_page("Conditions")
        self.angles_text = self._more_text_page("Angles")
        self.classical_point_data_text = self._more_text_page("Point Data")
        self.medieval_text = self._more_text_page("Medieval")
        self.rules_text = self._more_text_page("Rules")
        self.significators_text = self._more_text_page("Significators")
        self.moon_judgment_text = self._more_text_page("Moon")
        self.retrogrades_text = self._more_text_page("Retrogrades")
        self.midpoints_text = self._more_text_page("Midpoints")
        self.live_sky_text = self._more_text_page("Live Sky")
        self.house_rulers_text = self._more_text_page("House Rulers")
        self.reception_text = self._more_text_page("Reception")
        self.planet_condition_text = self._more_text_page("Planet Condition")
        self.declination_text = self._more_text_page("Declination")
        self.advanced_aspects_text = self._more_text_page("Advanced")
        self.factor_explorer_text = self._more_text_page("Factor Explorer")
        self.constellations_text = self._more_text_page("Constellations")
        self.cusps_text = self._more_text_page("Cusps")
        self.lots_text = self._more_text_page("Lots")
        self.nodes_text = self._more_text_page("Nodes")
        self.timing_text = self._more_text_page("Timing")
        self.planets_text = self._more_text_page("Planets")
        self.aspects_text = self._more_text_page("Aspects")
        self.aspectarian_text = self._more_text_page("Aspectarian")
        self.aspect_strength_text = self._more_text_page("Aspect Strength")
        self.fixed_stars_text = self._more_text_page("Fixed Stars")
        self.button_health_text = self._more_text_page("Button Health")
        shortlist_board = self._more_frame_page("Shortlist Board")
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
        self.shortlist_text = self._more_text_page("Shortlist")
        self.shortlist_compare_text = self._more_text_page("Pick Compare")
        shortlist_actions = self._more_frame_page("Pick Tools")
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
        self.log_text = self._more_text_page("Log")
        self._refresh_more_detail_selector()
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
        detail_toggle_row = tk.Frame(frame, bg=PALETTE["astrolabe_panel"])
        detail_toggle_row.pack(fill=tk.X, pady=(6, 0))
        self.right_detail_visible_var = tk.BooleanVar(value=False)
        self.right_detail_toggle_button = self._astrolabe_button(
            detail_toggle_row,
            "Show Audit Details",
            self._toggle_right_detail_blocks,
        )
        self.right_detail_toggle_button.pack(side=tk.LEFT)
        tk.Label(
            detail_toggle_row,
            text="Health, geometry, and aspect dashboard are tucked away until needed.",
            bg=PALETTE["astrolabe_panel"],
            fg=PALETTE["astrolabe_muted"],
            font=("Segoe UI", 7),
            anchor="w",
            wraplength=210,
            justify=tk.LEFT,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(7, 0))
        self.right_detail_container = tk.Frame(frame, bg=PALETTE["astrolabe_panel"])
        self.validation_panel_vars = [tk.StringVar(value="") for _index in range(4)]
        validation_block = tk.Frame(self.right_detail_container, bg=PALETTE["panel"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=7, pady=5)
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
        house_block = tk.Frame(self.right_detail_container, bg=PALETTE["panel"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=7, pady=5)
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
        aspect_block = tk.Frame(self.right_detail_container, bg=PALETTE["panel"], highlightbackground=PALETTE["panel_line"], highlightthickness=1, padx=7, pady=5)
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
        self._apply_right_detail_visibility()

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

    def _toggle_right_detail_blocks(self) -> None:
        if not hasattr(self, "right_detail_visible_var"):
            return
        self.right_detail_visible_var.set(not self.right_detail_visible_var.get())
        self._apply_right_detail_visibility()

    def _apply_right_detail_visibility(self) -> None:
        if not hasattr(self, "right_detail_container"):
            return
        visible = bool(self.right_detail_visible_var.get()) if hasattr(self, "right_detail_visible_var") else False
        if visible:
            self.right_detail_container.pack(fill=tk.X)
        else:
            self.right_detail_container.pack_forget()
        if hasattr(self, "right_detail_toggle_button"):
            self.right_detail_toggle_button.configure(text="Hide Audit Details" if visible else "Show Audit Details")

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
            "Retrogrades": "Planet motion status, stations, and retrograde electional cautions.",
            "Midpoints": "Primary planet midpoint axes and close midpoint contacts.",
            "Live Sky": "Live/manual orbital sky map for date navigation and planetary position context.",
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
            font=("Segoe UI", 9),
            padx=8,
            pady=7,
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

    def _build_more_detail_tab(self) -> None:
        self.more_detail_pages: dict[str, tk.Widget] = {}
        self.more_detail_page_titles: list[str] = []
        self.more_detail_tab = ttk.Frame(self.detail_notebook, style="Panel.TFrame", padding=6)
        self.detail_notebook.add(self.more_detail_tab, text="More")
        self.more_detail_tab.columnconfigure(0, weight=1)
        self.more_detail_tab.rowconfigure(1, weight=1)
        header = tk.Frame(self.more_detail_tab, bg=PALETTE["panel"])
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header.columnconfigure(1, weight=1)
        tk.Label(
            header,
            text="More Detail",
            bg=PALETTE["panel"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.more_detail_var = tk.StringVar(value="")
        self.more_detail_combo = ttk.Combobox(
            header,
            textvariable=self.more_detail_var,
            values=(),
            state="readonly",
            width=22,
        )
        self.more_detail_combo.grid(row=0, column=1, sticky="ew")
        self.more_detail_combo.bind("<<ComboboxSelected>>", lambda _event: self._show_more_detail_page(self.more_detail_var.get()))
        self.more_detail_stack = tk.Frame(
            self.more_detail_tab,
            bg=PALETTE["panel"],
            highlightbackground=PALETTE["panel_line"],
            highlightthickness=1,
        )
        self.more_detail_stack.grid(row=1, column=0, sticky="nsew")
        self.more_detail_stack.columnconfigure(0, weight=1)
        self.more_detail_stack.rowconfigure(0, weight=1)

    def _refresh_more_detail_selector(self) -> None:
        if not hasattr(self, "more_detail_combo"):
            return
        titles = tuple(self.more_detail_page_titles)
        self.more_detail_combo.configure(values=titles)
        current = self.more_detail_var.get()
        if titles and current not in titles:
            self._show_more_detail_page(titles[0])

    def _show_more_detail_page(self, title: str) -> bool:
        if not hasattr(self, "more_detail_pages") or title not in self.more_detail_pages:
            return False
        for page_title, page in self.more_detail_pages.items():
            if page_title == title:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_remove()
        if hasattr(self, "more_detail_var"):
            self.more_detail_var.set(title)
        return True

    def _more_frame_page(self, title: str) -> ttk.Frame:
        frame = ttk.Frame(self.more_detail_stack, style="Panel.TFrame", padding=4)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_remove()
        self.more_detail_pages[title] = frame
        self.more_detail_page_titles.append(title)
        return frame

    def _more_text_page(self, title: str) -> tk.Text:
        frame = self._more_frame_page(title)
        text = tk.Text(
            frame,
            width=40,
            height=16,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            padx=8,
            pady=7,
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
        )
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, self._tab_placeholder_text(title))
        text.configure(state=tk.DISABLED)
        return text

    def _populate_window_list(self, windows: list[dict[str, object]]) -> None:
        for card in self.window_cards:
            card.destroy()
        self.window_cards = []
        self._refresh_candidate_board_summary(windows)
        if not windows:
            if hasattr(self, "window_cards_canvas"):
                self.window_cards_canvas.configure(height=210)
            empty_card = tk.Frame(
                self.window_cards_frame,
                bg=PALETTE["panel_alt"],
                highlightbackground=PALETTE["astrolabe_line"],
                highlightthickness=1,
                padx=8,
                pady=8,
            )
            empty_card.pack(fill=tk.X, padx=5, pady=(5, 7))
            tk.Label(
                empty_card,
                text="No candidate windows matched.",
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
                reason_text = "Top blockers: " + "; ".join(f"{reason} ({count})" for reason, count in top_reasons[:3])
                tk.Label(
                    empty_card,
                    text=reason_text,
                    bg=PALETTE["panel_alt"],
                    fg=PALETTE["astrolabe_ink"],
                    font=("Segoe UI", 8),
                    wraplength=300,
                    justify=tk.LEFT,
                    anchor="w",
                ).pack(fill=tk.X, pady=(5, 0))
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
                for suggestion in suggestions[:2]:
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
        if hasattr(self, "window_cards_canvas"):
            self.window_cards_canvas.configure(height=310)
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
        action_note = f"Last action: {self.search_workbench_last_action}. "
        title, summary, detail = search_workbench_compact_lines(
            profile_name=profile_name,
            action_note=action_note.rstrip(),
            windows=windows,
            selected_time=selected_time,
            search_mode=self.search_quality_mode_var.get(),
            scan_hours=self.scan_hours_var.get(),
            step_minutes=self.step_minutes_var.get(),
            active_aspects=active_aspects,
            rejection_summary=self.current_rejection_summary if isinstance(self.current_rejection_summary, Mapping) else {},
        )
        self.search_workbench_title_var.set(title)
        self.search_workbench_summary_var.set(summary)
        self.search_workbench_detail_var.set(detail)
        self._refresh_guided_workflow()

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
        self.timing_context_var.set(
            displayed_chart_state_line(
                input_snapshot,
                selected_window,
                displayed_source=self.displayed_chart_source,
                selected_index=self.selected_window_index,
            )
        )
        self._refresh_workspace_hub(selected_window, input_snapshot, location)

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
