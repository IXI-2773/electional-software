"""Timeline, analysis, validation, reports, text panels, and focus-page rendering."""

from __future__ import annotations


def bind_desktop_globals(namespace: dict[str, object]) -> None:
    """Bind the shared desktop shell namespace after desktop.py is initialized."""

    protected = {"__name__", "__package__", "__spec__", "__loader__", "__file__", "__cached__", "__builtins__"}
    globals().update({name: value for name, value in namespace.items() if name not in protected})


class DesktopPagesMixin:
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
        self._analysis_text_section(
            "Houses And Angles",
            [
                *angle_testimony_lines(snapshot),
                *judgment_context_lines(snapshot, "houseRulerContext"),
                "",
                *judgment_context_lines(snapshot, "matterLordContext"),
            ],
        )
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
                "Guided Election Workbench\n"
                f"{guided_workbench_summary(self._guided_workflow_rows())[0]}\n"
                f"{guided_workbench_summary(self._guided_workflow_rows())[1]}\n\n"
                "Main path\n"
                + "\n".join(
                    f"{row['number']}. {row['label']}: {row['value']} [{row['status']}] - {row['action']}"
                    for row in self._guided_workflow_rows()
                )
                + "\n\n"
                "Location intelligence\n"
                + "\n".join(
                    location_intelligence_lines(
                        location_name=getattr(location, "name", ""),
                        timezone_name=getattr(location, "timezone", ""),
                        latitude=str(getattr(location, "latitude", "")),
                        longitude=str(getattr(location, "longitude", "")),
                        home_location_name=getattr(self, "home_location_name", None),
                        recent_locations=getattr(self, "recent_locations", []),
                        saved_count=len(getattr(self, "user_locations", [])),
                        timezone_warning=timezone_warning_for_location(location),
                    )
                )
                + "\n\n"
                "Current chart\n"
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
        self._set_text(self.retrogrades_text, "\n".join(retrograde_page_lines(snapshot)))
        self._set_text(self.midpoints_text, "\n".join(midpoint_page_lines(snapshot)))
        live_sky_lines = [
            "Live Sky",
            "",
            live_sky_timestamp_line(snapshot, location, "manual"),
            "",
            "Bodies",
            *[
                f"- {row['glyph']} {row['name']}: {row['position']} | display orbit {float(row.get('radiusFactor', 0.0)):.2f}"
                for row in live_sky_body_rows(snapshot)[:12]
            ],
            "",
            "Controls",
            "- Live Now recalculates for the selected location timezone.",
            "- Manual Date uses the date/time fields in the Live Sky page.",
            "- Sync Chart copies the displayed chart time into the Live Sky page.",
        ]
        self._set_text(self.live_sky_text, "\n".join(live_sky_lines))
        if self.page_mode_var.get() == PAGE_MODE_LABELS["live-sky"]:
            self.live_sky_snapshot = snapshot
            self._update_live_sky("chart")
        self._set_text(
            self.house_rulers_text,
            self._context_page_text(
                "House Rulers",
                [
                    *judgment_context_lines(snapshot, "houseRulerContext"),
                    "",
                    *judgment_context_lines(snapshot, "matterLordContext"),
                ],
                snapshot,
            ),
        )
        self._set_text(self.reception_text, self._context_page_text("Reception", judgment_context_lines(snapshot, "receptionContext"), snapshot))
        planet_strength_rows = (
            snapshot.get("scoreBreakdown", {})
            .get("diagnostics", {})
            .get("planetStrength", [])
            if isinstance(snapshot.get("scoreBreakdown", {}), dict)
            else []
        )
        planet_strength_detail_lines = planet_strength_workbench_lines(snapshot, limit=12)
        self._set_text(
            self.planet_condition_text,
            self._context_page_text(
                "Planet Conditions",
                [*planet_strength_detail_lines, "", *judgment_context_lines(snapshot, "planetConditionContext")],
                snapshot,
            ),
        )
        self._set_text(self.declination_text, self._context_page_text("Declination", judgment_context_lines(snapshot, "declinationContext"), snapshot))
        self._set_text(self.advanced_aspects_text, self._context_page_text("Advanced Aspects", judgment_context_lines(snapshot, "advancedAspectContext"), snapshot))
        self._set_text(self.factor_explorer_text, "\n".join(factor_explorer_lines(snapshot, self.input_snapshot)))
        self._set_text(self.constellations_text, "\n".join(constellation_lines(snapshot)))

        strength_by_planet = {
            str(row.get("planet")): row
            for row in planet_strength_rows
            if isinstance(row, Mapping)
        } if isinstance(planet_strength_rows, list) else {}
        planet_lines = []
        for planet in snapshot["positions"]:
            angular = " angular" if planet.get("isAngular") else ""
            dignity = format_dignity_summary(planet)
            constellation = planet.get("constellation", {})
            constellation_text = ""
            if isinstance(constellation, dict):
                constellation_text = f"; {constellation.get('name')} {float(constellation.get('spanDegrees', 0)):.0f}deg"
            strength = strength_by_planet.get(str(planet.get("name")), {})
            strength_text = f"; strength {strength.get('score')} {strength.get('band')}" if strength else ""
            planet_lines.append(
                f"{planet['name']:<8} {format_position(planet):<15} H{planet['house']:<2} "
                f"{dignity}; {format_motion_summary(planet)}{angular}{constellation_text}{strength_text}"
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
