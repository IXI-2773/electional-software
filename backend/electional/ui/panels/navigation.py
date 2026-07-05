"""Top navigation, ribbon, and workspace routing methods."""

from __future__ import annotations


def bind_desktop_globals(namespace: dict[str, object]) -> None:
    """Bind the shared desktop shell namespace after desktop.py is initialized."""

    protected = {"__name__", "__package__", "__spec__", "__loader__", "__file__", "__cached__", "__builtins__"}
    globals().update({name: value for name, value in namespace.items() if name not in protected})


class DesktopNavigationMixin:
    def _announce_visible_action(self, message: str) -> None:
        if hasattr(self, "timing_context_var"):
            current = str(self.timing_context_var.get() or "").strip()
            base = current.split(" | Action: ", 1)[0].strip()
            self.timing_context_var.set(f"{base} | Action: {message}" if base else f"Action: {message}")
        if hasattr(self, "status_var"):
            self.status_var.set(message)

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
        title_bar = tk.Frame(self.root, bg=PALETTE["title_bar"], height=24)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)
        brand = tk.Frame(title_bar, bg=PALETTE["title_bar"])
        brand.pack(side=tk.LEFT, padx=12, pady=2)
        tk.Label(brand, text=f"Electional Software  |  {APP_BUILD_LABEL}", bg=PALETTE["title_bar"], fg="#ffffff", font=("Segoe UI Semibold", 9)).pack(anchor="w")
        top_actions = tk.Frame(title_bar, bg=PALETTE["title_bar"])
        top_actions.pack(side=tk.RIGHT, padx=8, pady=2)
        self.tools_toggle_button = tk.Button(
            top_actions,
            text=tools_ribbon_label(self.show_tools_var.get()),
            command=self._toggle_tools_ribbon,
            bg=PALETTE["top_nav"],
            fg="#f8f2de",
            activebackground=PALETTE["top_nav_active"],
            activeforeground="#fffdf6",
            relief=tk.FLAT,
            bd=0,
            padx=TOP_NAV_BUTTON_METRICS["padx"],
            pady=TOP_NAV_BUTTON_METRICS["pady"],
            cursor="hand2",
            font=("Georgia", TOP_NAV_BUTTON_METRICS["font_size"], "bold"),
            highlightthickness=1,
            highlightbackground=PALETTE["top_bar_dark"],
        )
        self.tools_toggle_button.pack(side=tk.RIGHT)
        self.top_menu_frame = tk.Frame(self.root, bg=PALETTE["top_bar"], padx=10, pady=3)
        self.top_menu_frame.pack(fill=tk.X)
        nav_group = tk.Frame(self.top_menu_frame, bg=PALETTE["top_bar"])
        nav_group.pack(side=tk.LEFT)
        for item in TOP_NAV_ITEMS:
            button = self._top_nav_button(nav_group, item)
            self.top_nav_buttons[item] = button
            button.pack(side=tk.LEFT, padx=(0, 5))
        quick_group = tk.Frame(self.top_menu_frame, bg=PALETTE["top_bar"])
        quick_group.pack(side=tk.RIGHT)
        for label, command in (
            ("Current", lambda: self.calculate(show_input_chart=True)),
            ("Find Best", self._run_electional_search_workbench),
            ("Live Sky", lambda: self._apply_page_mode("live-sky")),
        ):
            tk.Button(
                quick_group,
                text=label,
                command=command,
                bg=PALETTE["top_bar_dark"],
                fg="#f8f2de",
                activebackground=PALETTE["top_nav_hover"],
                activeforeground="#fffdf6",
                relief=tk.FLAT,
                bd=0,
                padx=10,
                pady=3,
                cursor="hand2",
                font=("Segoe UI Semibold", 8),
                highlightthickness=1,
                highlightbackground=PALETTE["top_bar"],
            ).pack(side=tk.LEFT, padx=(5, 0))

        self.ribbon_frame = tk.Frame(self.root, bg=PALETTE["ribbon"], padx=8, pady=3)
        self.ribbon_frame.pack(fill=tk.X)
        for index, (group_title, items) in enumerate(RIBBON_GROUPS):
            self.ribbon_frame.columnconfigure(index, weight=1, uniform="ribbon-groups")
            self._ribbon_group(self.ribbon_frame, group_title, items).grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0 if index == 0 else 4, 0 if index == len(RIBBON_GROUPS) - 1 else 4),
                pady=(0, 1),
            )
        self._apply_tools_ribbon_visibility(save=False)

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
            padx=TOP_NAV_BUTTON_METRICS["padx"],
            pady=TOP_NAV_BUTTON_METRICS["pady"],
            cursor="hand2",
            font=("Segoe UI Semibold", TOP_NAV_BUTTON_METRICS["font_size"]),
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

    def _toggle_tools_ribbon(self) -> None:
        self.show_tools_var.set(not self.show_tools_var.get())
        self._apply_tools_ribbon_visibility(save=True)

    def _apply_tools_ribbon_visibility(self, *, save: bool = False) -> None:
        visible = bool(self.show_tools_var.get())
        if hasattr(self, "ribbon_frame") and hasattr(self, "top_menu_frame"):
            if visible:
                if not self.ribbon_frame.winfo_ismapped():
                    self.ribbon_frame.pack(fill=tk.X, after=self.top_menu_frame)
            else:
                self.ribbon_frame.pack_forget()
        if hasattr(self, "tools_toggle_button"):
            self.tools_toggle_button.configure(text=tools_ribbon_label(visible))
        if hasattr(self, "status_var"):
            self.status_var.set(tools_ribbon_status(visible))
        if save:
            self._save_session()

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
            padx=7,
            pady=4,
        )
        tk.Frame(group, bg=PALETTE["accent"], height=1).pack(fill=tk.X, pady=(0, 3))
        tk.Label(
            group,
            text=title.upper(),
            bg=PALETTE["ribbon_panel"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 7, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 3))
        grid = tk.Frame(group, bg=PALETTE["ribbon_panel"])
        grid.pack(fill=tk.X)
        for column in range(RIBBON_COLUMNS):
            grid.columnconfigure(column, weight=1, uniform=f"ribbon-{title}")
        for index, item in enumerate(items):
            row = index // RIBBON_COLUMNS
            column = index % RIBBON_COLUMNS
            self._ribbon_button(grid, item).grid(row=row, column=column, sticky="nsew", padx=(0, 3), pady=(0, 2))
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
            width=12,
            height=1,
            cursor="hand2",
            font=("Georgia", 7, "bold"),
            justify=tk.CENTER,
            wraplength=104,
            padx=2,
            pady=2,
        )
        return button

    def _run_top_nav_action(self, label: str) -> None:
        self._set_active_top_nav(label)
        self._announce_visible_action(f"Opening {label}...")
        try:
            self.root.update_idletasks()
        except tk.TclError:
            pass
        self._scroll_center_to_top()
        actions = {
            "Guide": self._open_guided_workflow_page,
            "Wheel": lambda: self._open_main_page("Wheel", "Window"),
            "Search": self._open_search_workbench_page,
            "Analysis": lambda: self._apply_page_mode("analysis"),
            "Timeline": self._open_timeline_workbench,
            "Validation": lambda: self._apply_page_mode("validation"),
            "Reports": lambda: self._apply_page_mode("reports"),
        }
        action = actions.get(label)
        if action is None:
            self._show_unknown_action(label)
            return
        try:
            action()
            self._announce_visible_action(f"{label} opened.")
        except Exception as exc:
            self._announce_visible_action(f"{label} failed: {exc}")
            self._show_text_dialog(f"{label} Error", f"{label} could not complete:\n\n{exc}")

    def _set_workspace_page(self, label: str) -> None:
        if label in TOP_NAV_ITEMS:
            self._set_active_top_nav(label)
        if hasattr(self, "_set_search_workbench_visible"):
            self._set_search_workbench_visible(label == "Search")
        if hasattr(self, "workspace_page_var"):
            self.workspace_page_var.set(f"Main page: {label}")
        if hasattr(self, "workspace_page_summary_var"):
            self.workspace_page_summary_var.set(TOP_NAV_WORKSPACE_SUMMARIES.get(label, "Workspace page opened."))

    def _open_main_page(self, label: str, detail_page: str) -> None:
        self._set_workspace_page(label)
        self._scroll_center_to_top()
        self._focus_detail_page(detail_page)
        self._announce_visible_action(f"Opened {label} workspace page.")

    def _open_guided_workflow_page(self) -> None:
        if hasattr(self, "show_tools_var") and self.show_tools_var.get():
            self.show_tools_var.set(False)
            self._apply_tools_ribbon_visibility(save=False)
        if hasattr(self, "page_mode_var"):
            self.page_mode_var.set(PAGE_MODE_LABELS["guide"])
        self._set_workspace_page("Guide")
        self._scroll_center_to_top()
        self._focus_detail_page("Summary")
        self._refresh_guided_workflow()
        self._announce_visible_action("Opened the guided election path.")
        self._save_session()

    def _mark_search_workbench_action(self, action: str, *, running: bool = False) -> None:
        self.search_workbench_run_count += 1
        stamp = datetime.now().strftime("%H:%M:%S")
        self.search_workbench_last_action = f"{action} #{self.search_workbench_run_count} at {stamp}"
        if hasattr(self, "search_workbench_title_var"):
            self.search_workbench_title_var.set(f"Search Console | {action}")
        if hasattr(self, "search_workbench_summary_var"):
            state = "Running" if running else "Opened"
            self.search_workbench_summary_var.set(f"{state}: {self.search_workbench_last_action}")
        if hasattr(self, "search_workbench_detail_var"):
            self.search_workbench_detail_var.set("Updating visible search diagnostics...")
        self._announce_visible_action(f"{action}: updating Search Workbench.")
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
        self._announce_visible_action("Opened Search Workbench with active filters, aspect profile, candidates, and rejection diagnostics.")

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
        if not hasattr(self, "context_chip_frame"):
            return
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
        self._announce_visible_action(f"Running {label}...")
        try:
            self.root.update_idletasks()
        except tk.TclError:
            pass
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
            "Find Best": self._run_electional_search_workbench,
            "Transits": self._open_timeline_workbench,
            "Transits/Timeline": self._open_timeline_workbench,
            "Electional Search": self._run_electional_search_workbench,
            "Search Page": self._open_search_workbench_page,
            "Shortlist": self._add_selected_to_shortlist,
            "Advisor": lambda: self._open_detail_page("Advisor"),
            "Improve": lambda: self._open_detail_page("Improve"),
            "Decision": lambda: self._open_detail_page("Decision"),
            "Compare": lambda: self._open_detail_page("Compare"),
            "Factors": lambda: self._open_detail_page("Factors"),
            "Chart Data": self._show_chart_inspector,
            "Diagnostics": lambda: self._open_detail_page("Diagnostics"),
            "Aspects": self._show_wheel_aspects,
            "Aspect Strength": lambda: self._open_detail_page("Aspect Strength"),
            "Declination": lambda: self._open_detail_page("Declination"),
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
        action = actions.get(label)
        if action is None:
            self._show_unknown_action(label)
            return
        try:
            action()
            if hasattr(self, "show_tools_var") and self.show_tools_var.get():
                self.show_tools_var.set(False)
                self._apply_tools_ribbon_visibility(save=False)
            self._announce_visible_action(f"{label} done.")
        except Exception as exc:
            self._announce_visible_action(f"{label} failed: {exc}")
            self._show_text_dialog(f"{label} Error", f"{label} could not complete:\n\n{exc}")
