"""Dialogs, exports, preferences, shortlist, and utility actions."""

from __future__ import annotations

import html
import threading


def bind_desktop_globals(namespace: dict[str, object]) -> None:
    """Bind the shared desktop shell namespace after desktop.py is initialized."""

    protected = {"__name__", "__package__", "__spec__", "__loader__", "__file__", "__cached__", "__builtins__"}
    globals().update({name: value for name, value in namespace.items() if name not in protected})


class DesktopActionsMixin:
    def _show_wheel_aspects(self) -> None:
        self.show_aspects_var.set(True)
        self.compact_wheel_var.set(False)
        self._display_option_changed()
        self._focus_detail_page("Aspects")
        self.status_var.set("Wheel aspects enabled and aspect list opened.")

    def _show_capricorn_asset_audit(self) -> None:
        inventory = inventory_capricorn_assets()
        self._show_text_dialog("CapricornPROMETHEUS Assets", format_capricorn_asset_audit(inventory))
        if inventory.exists and inventory.root:
            self.status_var.set(f"Opened Capricorn asset audit for {inventory.root}.")
        else:
            self.status_var.set("Capricorn asset folder not found in the usual locations.")

    def _import_capricorn_aspect_profiles(self) -> None:
        result = import_capricorn_aspect_profiles()
        self.aspect_profiles = load_aspect_profiles()
        self.active_aspect_profile = self.aspect_profiles[-1] if self.aspect_profiles else self.active_aspect_profile
        self.aspect_profile_var.set(self.active_aspect_profile.name)
        if hasattr(self, "aspect_profile_combo"):
            self.aspect_profile_combo.configure(values=self._aspect_profile_names())
        self._refresh_aspect_focus_controls()
        self._refresh_left_status_chips()
        self._save_session()
        self._show_text_dialog("Capricorn Aspect Import", format_capricorn_aspect_import_result(result))
        self.status_var.set(f"Imported {result.imported_profiles} Capricorn aspect profiles.")

    def _open_timeline_workbench(self) -> None:
        self._mark_search_workbench_action("Timeline")
        if not self.selected_window:
            self.calculate(show_input_chart=True)
        if not self.selected_window:
            return
        self._set_workspace_page("Timeline")
        self._scroll_center_to_top()
        self.page_mode_var.set(PAGE_MODE_LABELS["transit-search"])
        self.show_aspects_var.set(True)
        self._refresh_search_workbench_strip()
        self._focus_detail_page("Timeline")
        self._save_session()
        self._announce_visible_action("Opened transit/timeline workbench with current, local-day, and next-24h aspect scans.")

    def _run_electional_search_workbench(self) -> None:
        self._mark_search_workbench_action("Electional Search", running=True)
        self._set_workspace_page("Search")
        self._scroll_center_to_top()
        self._apply_page_mode("transit-search")
        self._refresh_search_workbench_strip()
        self._focus_detail_page("Search")

        def finish() -> None:
            self._set_workspace_page("Search")
            self._scroll_center_to_top()
            self._apply_page_mode("transit-search")
            self._refresh_search_workbench_strip()
            self._focus_detail_page("Search")
            if self.current_windows:
                self._announce_visible_action("Electional Search completed with ranked candidates and rejection diagnostics.")
            else:
                self._announce_visible_action("Electional Search completed with no matches; blockers and relax suggestions are visible.")

        if not self.calculate_in_background(show_input_chart=False, job_name="Electional Search", on_complete=finish):
            self._refresh_search_workbench_strip()

    def _displayed_window_pool(self) -> list[dict[str, object]]:
        windows: list[dict[str, object]] = []
        for candidate in (getattr(self, "selected_window", None), getattr(self, "input_snapshot", None)):
            if isinstance(candidate, dict) and candidate not in windows:
                windows.append(candidate)
        for window in getattr(self, "current_windows", []):
            if isinstance(window, dict) and window not in windows:
                windows.append(window)
        return windows

    def _show_why_not_this_time_dialog(self) -> None:
        if not self.selected_window:
            self.calculate(show_input_chart=True)
        if not self.selected_window:
            return
        try:
            config = self._current_search_config()
        except ValueError as exc:
            messagebox.showerror("Why Not This Time", f"Search filters need attention:\n{exc}")
            return
        lines = why_not_time_lines(self.selected_window, config, self.input_snapshot, self._current_candidate_pool())
        self._show_text_dialog("Why Not This Time?", "\n".join(lines))
        self._announce_visible_action("Opened exact-time filter and quality explanation.")

    def _show_aspect_peak_finder_dialog(self) -> None:
        if not self.selected_window:
            self.calculate(show_input_chart=True)
        if not self.selected_window or not self.current_location:
            messagebox.showinfo("Aspect Peak Finder", "Calculate or run a search before finding aspect peaks.")
            return
        try:
            config = self._current_search_config()
        except ValueError as exc:
            messagebox.showerror("Aspect Peak Finder", f"Search filters need attention:\n{exc}")
            return
        scan_config = SearchConfig(
            end_offset_minutes=config.end_offset_minutes,
            step_minutes=max(5, min(15, config.step_minutes)),
            max_results=48,
            target_aspect_text=config.target_aspect_text,
            target_aspect_body_text=config.target_aspect_body_text,
            target_planet_text=config.target_planet_text,
            target_sign_text=config.target_sign_text,
            target_house=config.target_house,
            quality_mode=config.quality_mode,
            refine_candidates=True,
            refinement_step_minutes=5,
            refinement_seed_count=8,
        )
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        zodiac_system = get_zodiac_system(self.zodiac_system_var.get())
        house_system = get_house_system(self.house_system_var.get())
        date_text = self.date_var.get()
        time_text = self.time_var.get()
        location = self.current_location
        selected_aspects = self._selected_aspect_ids()
        objective = self.objective_var.get()
        aspect_definitions = self._active_aspect_definitions()
        selected_window = self.selected_window
        scan_note = f"Scan: {config.end_offset_minutes // 60}h at {max(5, min(15, config.step_minutes))}m with 5m refinement seeds; capped to 48 result windows."
        self._focus_detail_page("Aspect Strength")
        self._announce_visible_action("Aspect Peak Finder is scanning in the background...")

        def worker() -> None:
            try:
                peak_report = build_election_report(
                    date_text,
                    time_text,
                    location,
                    preset.id,
                    selected_aspects,
                    zodiac_system.id,
                    house_system.id,
                    scan_config,
                    objective,
                    aspect_definitions,
                )
                windows = [peak_report.get("snapshot", selected_window), *list(peak_report.get("windows", []))]
                lines = aspect_peak_lines(
                    windows,
                    config.target_aspect_text,
                    config.target_aspect_body_text,
                    limit=12,
                )
                lines.insert(3, scan_note)
            except Exception as exc:  # pragma: no cover - desktop resilience path.
                error_text = str(exc)
                self.root.after(0, lambda text=error_text: messagebox.showerror("Aspect Peak Finder", f"Peak scan failed:\n{text}"))
                self.root.after(0, lambda: self._announce_visible_action("Aspect Peak Finder failed."))
                return

            def finish() -> None:
                self._show_text_dialog("Aspect Peak Finder", "\n".join(lines))
                self._announce_visible_action("Opened refined aspect peak scan using the active target filters.")

            self.root.after(0, finish)

        threading.Thread(target=worker, name="aspect-peak-finder", daemon=True).start()

    def _run_aspect_planet_search_workbench(self) -> None:
        try:
            config = self._current_search_config()
        except ValueError as exc:
            messagebox.showerror("Aspect / Planet Search", f"Search filters need attention:\n{exc}")
            return
        if not (config.target_aspect_text or config.target_aspect_body_text or config.target_planet_text):
            self._show_text_dialog(
                "Aspect / Planet Search",
                "\n".join(
                    [
                        "Aspect / Planet Search",
                        "Set one or more target fields in Search Strategy first:",
                        "- Find aspect, such as Trine, Square, Conjunction, or a custom aspect.",
                        "- Involving, such as Moon, Jupiter, Venus, or Mars.",
                        "- Planet target plus sign/house target.",
                        "",
                        "Then press Aspect Search again to run a targeted election search.",
                    ]
                ),
            )
            self._show_left_section("Search Strategy")
            self._scroll_left_section_into_view("Search Strategy")
            return
        self._run_electional_search_workbench()
        target_bits = []
        if config.target_aspect_text:
            target_bits.append(f"aspect {config.target_aspect_text}")
        if config.target_aspect_body_text:
            target_bits.append(f"involving {config.target_aspect_body_text}")
        if config.target_planet_text:
            placement = [config.target_planet_text]
            if config.target_sign_text:
                placement.append(f"in {config.target_sign_text}")
            if config.target_house is not None:
                placement.append(f"H{config.target_house}")
            target_bits.append(" ".join(placement))
        self._announce_visible_action("Aspect Search: " + "; ".join(target_bits))

    def _show_election_alerts_dialog(self) -> None:
        if not self.current_windows:
            self.calculate(show_input_chart=False)
        windows = list(getattr(self, "current_windows", []))
        if not windows and isinstance(getattr(self, "selected_window", None), dict):
            windows = [self.selected_window]
        if not windows:
            messagebox.showinfo("Election Alerts", "Run a search before reviewing election alerts.")
            return
        try:
            config = self._current_search_config()
        except ValueError as exc:
            messagebox.showerror("Election Alerts", f"Search filters need attention:\n{exc}")
            return
        try:
            threshold = int(self.minimum_score_var.get()) if self.minimum_score_var.get().strip() else None
        except (AttributeError, TypeError, ValueError):
            threshold = None
        lines = election_alert_lines(windows, config, min_score=threshold, limit=12)
        self._set_workspace_page("Search")
        self._focus_detail_page("Search")
        self._show_text_dialog("Election Alerts", "\n".join(lines))
        self._announce_visible_action("Opened alert windows and blockers from the active search gates.")

    def _show_out_of_bounds_dialog(self) -> None:
        if not self.selected_window:
            messagebox.showinfo("Out of Bounds", "Calculate a chart before checking declination and out-of-bounds diagnostics.")
            return
        lines = judgment_context_lines(self.selected_window, "declinationContext")
        if not lines:
            lines = [
                "Declination / Out-of-Bounds Diagnostics",
                "- Declination data is not available for the current point set or backend response.",
                "- Recalculate with the full electional point set, then open this tool again.",
            ]
        self._focus_detail_page("Declination")
        self._show_text_dialog("Out of Bounds / Declination", "\n".join(lines))
        self._announce_visible_action("Opened out-of-bounds and declination diagnostics.")

    def _unique_aspect_profile_id(self, name: str, replacing: str | None = None) -> str:
        base = sanitize_aspect_id(name)
        if base == DEFAULT_ASPECT_PROFILE_ID:
            base = "custom-aspect-profile"
        used = {profile.id for profile in self.aspect_profiles if profile.id != replacing}
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _show_aspect_config_dialog(self) -> None:
        working_aspects = list(self.active_aspect_profile.aspects)
        dialog = tk.Toplevel(self.root)
        dialog.title("Aspect Configuration")
        dialog.geometry("900x620")
        dialog.configure(bg=PALETTE["app_bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        header = tk.Frame(dialog, bg=PALETTE["top_bar"], padx=12, pady=8)
        header.pack(fill=tk.X)
        tk.Label(header, text="Aspect Configuration Dialog", bg=PALETTE["top_bar"], fg="white", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(
            header,
            text="Create and tune the aspects used by chart detection, election search, scoring, reports, and the wheel.",
            bg=PALETTE["top_bar"],
            fg="#dce8e2",
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(2, 0))

        body = tk.Frame(dialog, bg=PALETTE["panel"], padx=12, pady=12)
        body.pack(fill=tk.BOTH, expand=True)
        profile_grid = tk.Frame(body, bg=PALETTE["panel"])
        profile_grid.pack(fill=tk.X, pady=(0, 10))
        profile_grid.columnconfigure(1, weight=1)
        profile_grid.columnconfigure(3, weight=2)
        name_var = tk.StringVar(value=self.active_aspect_profile.name)
        description_var = tk.StringVar(value=self.active_aspect_profile.description)
        tk.Label(profile_grid, text="Name", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 6))
        tk.Entry(profile_grid, textvariable=name_var, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]).grid(row=0, column=1, sticky="ew", padx=(0, 12), ipady=5)
        tk.Label(profile_grid, text="Description", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold")).grid(row=0, column=2, sticky="w", padx=(0, 6))
        tk.Entry(profile_grid, textvariable=description_var, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]).grid(row=0, column=3, sticky="ew", ipady=5)

        table_wrap = tk.Frame(body, bg=PALETTE["panel"], highlightbackground=PALETTE["panel_line"], highlightthickness=1)
        table_wrap.pack(fill=tk.BOTH, expand=True)
        columns = ("enabled", "glyph", "name", "line", "abbr", "angle", "orb", "tone", "kind")
        tree = ttk.Treeview(table_wrap, columns=columns, show="headings", height=14)
        headings = {
            "enabled": "On",
            "glyph": "Glyph",
            "name": "Aspect",
            "line": "Line",
            "abbr": "Abv",
            "angle": "Angle Exact",
            "orb": "Orb",
            "tone": "Tone",
            "kind": "Kind",
        }
        widths = {"enabled": 48, "glyph": 60, "name": 190, "line": 82, "abbr": 70, "angle": 95, "orb": 80, "tone": 85, "kind": 78}
        for column in columns:
            tree.heading(column, text=headings[column])
            tree.column(column, width=widths[column], minwidth=widths[column], stretch=column == "name")
        scrollbar = ttk.Scrollbar(table_wrap, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def refresh_tree(select_index: int | None = None) -> None:
            tree.delete(*tree.get_children())
            for index, aspect in enumerate(working_aspects):
                tree.insert(
                    "",
                    tk.END,
                    iid=str(index),
                    values=(
                        "yes" if aspect.enabled else "no",
                        aspect.glyph or aspect.abbreviation,
                        aspect.name,
                        aspect.color,
                        aspect.abbreviation,
                        f"{float(aspect.angle):06.2f}",
                        f"{float(aspect.default_orb):.2f}",
                        aspect.tone,
                        "built-in" if aspect.built_in else "custom",
                    ),
                )
            if select_index is not None and 0 <= select_index < len(working_aspects):
                tree.selection_set(str(select_index))
                tree.see(str(select_index))

        def selected_index() -> int | None:
            selection = tree.selection()
            if not selection:
                return None
            try:
                return int(selection[0])
            except ValueError:
                return None

        def open_editor(index: int | None = None) -> None:
            existing = working_aspects[index] if index is not None else None
            editor = tk.Toplevel(dialog)
            editor.title("Edit Aspect" if existing else "Add Aspect")
            editor.geometry("430x440")
            editor.configure(bg=PALETTE["panel"])
            editor.transient(dialog)
            editor.grab_set()
            form = tk.Frame(editor, bg=PALETTE["panel"], padx=12, pady=12)
            form.pack(fill=tk.BOTH, expand=True)
            name_field = tk.StringVar(value=existing.name if existing else "")
            id_field = tk.StringVar(value=existing.id if existing else "")
            abbr_field = tk.StringVar(value=existing.abbreviation if existing else "")
            glyph_field = tk.StringVar(value=existing.glyph if existing else "")
            angle_field = tk.StringVar(value=f"{float(existing.angle):g}" if existing else "45")
            orb_field = tk.StringVar(value=f"{float(existing.default_orb):g}" if existing else "2")
            tone_field = tk.StringVar(value=existing.tone if existing else "mixed")
            color_field = tk.StringVar(value=existing.color if existing else "#536d8d")
            enabled_field = tk.BooleanVar(value=existing.enabled if existing else True)

            def row(label: str, widget: tk.Widget) -> None:
                tk.Label(form, text=label, bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 8, "bold")).pack(anchor="w", pady=(7, 2))
                widget.pack(fill=tk.X, ipady=4)

            row("Name", tk.Entry(form, textvariable=name_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            row("Identifier", tk.Entry(form, textvariable=id_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            row("Abbreviation", tk.Entry(form, textvariable=abbr_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            row("Glyph / fallback text", tk.Entry(form, textvariable=glyph_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            number_row = tk.Frame(form, bg=PALETTE["panel"])
            number_row.pack(fill=tk.X)
            number_row.columnconfigure(0, weight=1)
            number_row.columnconfigure(1, weight=1)
            for column, (label, variable) in enumerate((("Exact angle", angle_field), ("Orb degrees", orb_field))):
                cell = tk.Frame(number_row, bg=PALETTE["panel"])
                cell.grid(row=0, column=column, sticky="ew", padx=(0, 5) if column == 0 else (5, 0))
                tk.Label(cell, text=label, bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 8, "bold")).pack(anchor="w", pady=(7, 2))
                tk.Entry(cell, textvariable=variable, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]).pack(fill=tk.X, ipady=4)
            row("Tone", ttk.Combobox(form, textvariable=tone_field, values=("support", "stress", "mixed"), state="readonly"))
            row("Line / color", tk.Entry(form, textvariable=color_field, bg=PALETTE["panel_alt"], relief=tk.FLAT, highlightthickness=1, highlightbackground=PALETTE["panel_line"]))
            tk.Checkbutton(form, text="Enabled in this profile", variable=enabled_field, bg=PALETTE["panel"], fg=PALETTE["text"], activebackground=PALETTE["panel"], selectcolor=PALETTE["panel_alt"]).pack(anchor="w", pady=(8, 0))

            def save_aspect() -> None:
                name = name_field.get().strip()
                aspect_id = sanitize_aspect_id(id_field.get() or name)
                try:
                    angle = float(angle_field.get())
                    orb = float(orb_field.get())
                except ValueError:
                    messagebox.showerror("Aspect validation", "Angle and orb must be numbers.", parent=editor)
                    return
                duplicate = any(aspect.id == aspect_id and idx != index for idx, aspect in enumerate(working_aspects))
                candidate = Aspect(
                    id=aspect_id,
                    name=name,
                    angle=angle,
                    default_orb=orb,
                    tone=tone_field.get(),
                    meaning=(existing.meaning if existing else "Custom aspect definition."),
                    abbreviation=abbr_field.get().strip() or name[:4].title(),
                    glyph=glyph_field.get().strip() or abbr_field.get().strip() or name[:2].title(),
                    color=color_field.get().strip() or "#536d8d",
                    enabled=enabled_field.get(),
                    built_in=bool(existing.built_in) if existing else False,
                )
                errors = []
                if duplicate:
                    errors.append(f"Duplicate aspect id: {aspect_id}.")
                errors.extend(validate_aspect_profile(AspectProfile("edit", "Edit", "", tuple([candidate]))))
                if errors:
                    messagebox.showerror("Aspect validation", "\n".join(errors), parent=editor)
                    return
                if index is None:
                    working_aspects.append(candidate)
                    refresh_tree(len(working_aspects) - 1)
                else:
                    working_aspects[index] = candidate
                    refresh_tree(index)
                editor.destroy()

            actions = tk.Frame(editor, bg=PALETTE["panel"], padx=12, pady=10)
            actions.pack(fill=tk.X)
            ttk.Button(actions, text="Save Aspect", command=save_aspect).pack(side=tk.RIGHT)
            ttk.Button(actions, text="Cancel", command=editor.destroy).pack(side=tk.RIGHT, padx=(0, 8))

        def delete_or_disable() -> None:
            index = selected_index()
            if index is None:
                return
            aspect = working_aspects[index]
            if aspect.built_in:
                working_aspects[index] = Aspect(
                    id=aspect.id,
                    name=aspect.name,
                    angle=aspect.angle,
                    default_orb=aspect.default_orb,
                    tone=aspect.tone,
                    meaning=aspect.meaning,
                    abbreviation=aspect.abbreviation,
                    glyph=aspect.glyph,
                    color=aspect.color,
                    enabled=False,
                    built_in=True,
                )
                refresh_tree(index)
                return
            del working_aspects[index]
            refresh_tree(min(index, len(working_aspects) - 1))

        def move(delta: int) -> None:
            index = selected_index()
            if index is None:
                return
            target = index + delta
            if target < 0 or target >= len(working_aspects):
                return
            working_aspects[index], working_aspects[target] = working_aspects[target], working_aspects[index]
            refresh_tree(target)

        def save_profile() -> None:
            profile_name = name_var.get().strip() or "Custom Aspect Profile"
            profile_id = self.active_aspect_profile.id
            if profile_id == DEFAULT_ASPECT_PROFILE_ID:
                if profile_name == self.active_aspect_profile.name:
                    profile_name = f"{profile_name} Custom"
                profile_id = self._unique_aspect_profile_id(profile_name)
            profile = AspectProfile(profile_id, profile_name, description_var.get().strip(), tuple(working_aspects))
            errors = validate_aspect_profile(profile)
            if errors:
                messagebox.showerror("Aspect profile validation", "\n".join(errors), parent=dialog)
                return
            replaced = False
            next_profiles: list[AspectProfile] = []
            for existing_profile in self.aspect_profiles:
                if existing_profile.id == profile.id:
                    next_profiles.append(profile)
                    replaced = True
                else:
                    next_profiles.append(existing_profile)
            if not replaced:
                next_profiles.append(profile)
            self.aspect_profiles = next_profiles
            save_aspect_profiles(self.aspect_profiles)
            self.active_aspect_profile = profile
            self.aspect_profile_var.set(profile.name)
            if hasattr(self, "aspect_profile_combo"):
                self.aspect_profile_combo.configure(values=self._aspect_profile_names())
            self._refresh_aspect_focus_controls()
            self._refresh_left_status_chips()
            self._save_session()
            self._log_event(f"Saved aspect profile: {profile.name} ({len(profile.aspects)} aspects)")
            self.status_var.set(f"Saved aspect profile: {profile.name}. Recalculate when ready.")
            dialog.destroy()

        button_bar = tk.Frame(body, bg=PALETTE["panel"])
        button_bar.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(button_bar, text="Add", command=lambda: open_editor()).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Edit", command=lambda: open_editor(selected_index()) if selected_index() is not None else None).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Delete / Disable", command=delete_or_disable).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Move Up", command=lambda: move(-1)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Move Down", command=lambda: move(1)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_bar, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_bar, text="OK and Save", command=save_profile).pack(side=tk.RIGHT, padx=(0, 8))
        refresh_tree(0)

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
        enabled_by_id = {aspect.id: aspect.enabled for aspect in self.active_aspect_profile.aspects}
        for aspect_id, var in self.aspect_vars.items():
            var.set(bool(enabled_by_id.get(aspect_id, True)))
        self.calculate(show_input_chart=True)

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
        self._show_text_dialog("Electional Report", report)
        self.status_var.set("Opened full electional report.")

    def _show_daily_aspect_report_dialog(self) -> None:
        if not self.selected_window or not self.current_location:
            messagebox.showinfo("Day Report", "Calculate a chart/search before opening the daily aspect report.")
            return
        dashboard = format_aspect_highlight_dashboard(self.current_aspect_highlights)
        timeline = self.current_aspect_highlights.get("timeline", []) if isinstance(self.current_aspect_highlights, dict) else []
        timeline_lines = [
            f"- {format_aspect_highlight(item)}"
            for item in timeline[:12]
            if isinstance(item, Mapping)
        ]
        try:
            preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
            zodiac_system = get_zodiac_system(self.zodiac_system_var.get())
            house_system = get_house_system(self.house_system_var.get())
            step_minutes = int(self.step_minutes_var.get().strip() or DEFAULT_STEP_MINUTES)
            max_results = max(12, int(self.max_results_var.get().strip())) if self.max_results_var.get().strip() else 12
            daily_config = SearchConfig(
                end_offset_minutes=24 * 60,
                step_minutes=step_minutes,
                max_results=max_results,
                minimum_score=None,
                minimum_fit=None,
                minimum_confidence=None,
                minimum_cleanliness=None,
                maximum_volatility=None,
                avoid_major_stress=False,
                require_applying_support=False,
                require_angular_benefic=False,
                avoid_angular_malefics=False,
                require_moon_non_void=False,
                avoid_objective_antipatterns=False,
            )
            daily_report = build_election_report(
                self.date_var.get(),
                self.time_var.get(),
                self.current_location,
                preset.id,
                self._selected_aspect_ids(),
                zodiac_system.id,
                house_system.id,
                daily_config,
                self.objective_var.get(),
                self._active_aspect_definitions(),
            )
        except Exception as exc:  # pragma: no cover - exercised through desktop UI.
            messagebox.showerror("Day Report", f"Could not build the 24-hour day report:\n{exc}")
            return
        windows = list(daily_report.get("windows", []))
        selected = windows[0] if windows else daily_report.get("snapshot", self.selected_window)
        daily_searched = int(daily_report.get("searchedWindowCount", len(windows)) or len(windows))
        daily_evaluated = int(daily_report.get("evaluatedWindowCount", daily_searched) or daily_searched)
        daily_refined = int(daily_report.get("refinedWindowCount", 0) or 0)
        body = build_transit_search_page(
            daily_report.get("snapshot", self.input_snapshot or self.selected_window),
            selected,
            windows,
            self.current_location,
            format_search_summary(daily_config)
            + " Mode: 24-hour best-overall aspect report; hard filters are omitted for ranking visibility; "
            + f"evaluated {daily_evaluated} ({daily_searched} coarse + {daily_refined} refined); "
            + f"deep-built {daily_report.get('deepWindowCount', len(windows))}.",
            dict(daily_report.get("rejectionSummary") or {}),
        )
        report_text = (
            "Daily Aspect Report\n\n"
            "Current / Local Day / Next 24 Hours\n"
            f"{dashboard}\n\n"
            "Local-Day Timeline\n"
            + ("\n".join(timeline_lines) if timeline_lines else "- No local-day aspect highlights available.")
            + "\n\nRanked Election Windows\n"
            + body
        )
        self._show_text_dialog("Daily Aspect Report", report_text)
        self._focus_detail_page("Analysis")
        self.status_var.set("Opened 24-hour best-aspects-through-the-day report.")

    def _save_chart_wheel(self) -> None:
        if not self.selected_window:
            self.status_var.set("Nothing to export yet. Calculate a chart first.")
            return
        reports_dir = Path.cwd() / "reports"
        reports_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = reports_dir / f"electional-wheel-{stamp}.ps"
        self.canvas.update_idletasks()
        width = self.canvas.winfo_width() if self.canvas.winfo_width() > 1 else int(self.canvas.cget("width"))
        height = self.canvas.winfo_height() if self.canvas.winfo_height() > 1 else int(self.canvas.cget("height"))
        export_options = wheel_export_postscript_options(width, height, self.wheel_export_scale)
        self.canvas.postscript(file=str(path), colormode="color", **export_options)
        quality = wheel_export_scale_label(self.wheel_export_scale)
        self.status_var.set(f"Saved {quality} chart wheel: {path}")
        self._log_event(f"Saved {quality} wheel export: {path.name}")

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
        self._refresh_guided_workflow()

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
        export_text = build_comparison_export_text(
            self.input_snapshot or self.selected_window,
            self.selected_window,
            self.current_windows,
            self.objective_var.get(),
            self.current_location,
            self.manual_validation_result,
        )
        path.write_text(export_text, encoding="utf-8")
        html_path = reports_dir / f"electional-decision-sheet-{stamp}.html"
        html_path.write_text(
            (
                "<!doctype html><html><head><meta charset=\"utf-8\">"
                "<title>Electional Decision Sheet</title>"
                "<style>"
                "body{font-family:Georgia,'Times New Roman',serif;background:#f8f6ec;color:#17251f;margin:32px;}"
                "main{max-width:980px;margin:auto;background:#fffdf6;border:1px solid #b9aa7b;padding:28px;}"
                "pre{white-space:pre-wrap;font-family:'Segoe UI',sans-serif;font-size:14px;line-height:1.45;}"
                "h1{margin-top:0;color:#1e6a63;}"
                "</style></head><body><main><h1>Electional Decision Sheet</h1><pre>"
                + html.escape(export_text)
                + "</pre></main></body></html>"
            ),
            encoding="utf-8",
        )
        self.status_var.set(f"Saved decision sheet: {path} and {html_path.name}")
        self._log_event(f"Saved decision sheet: {path.name}; HTML companion: {html_path.name}")

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

    def _focus_detail_page(self, page_title: str) -> bool:
        if not hasattr(self, "detail_notebook"):
            return False
        if page_title == "Button Health":
            self._refresh_button_health_text()
        for tab_id in self.detail_notebook.tabs():
            if self.detail_notebook.tab(tab_id, "text") == page_title:
                self.detail_notebook.select(tab_id)
                self._sync_top_nav_selection(page_title)
                if hasattr(self, "active_detail_var"):
                    self.active_detail_var.set(f"Active detail: {page_title}")
                self.status_var.set(f"Opened {page_title} detail page.")
                return True
        if hasattr(self, "more_detail_pages") and page_title in self.more_detail_pages:
            for tab_id in self.detail_notebook.tabs():
                if self.detail_notebook.tab(tab_id, "text") == "More":
                    self.detail_notebook.select(tab_id)
                    break
            if hasattr(self, "_show_more_detail_page"):
                self._show_more_detail_page(page_title)
            if hasattr(self, "active_detail_var"):
                self.active_detail_var.set(f"Active detail: {page_title}")
            self.status_var.set(f"Opened {page_title} in More Detail.")
            return True
        self.status_var.set(f"{page_title} detail page is not available yet.")
        if hasattr(self, "active_detail_var"):
            self.active_detail_var.set(f"Missing detail: {page_title}")
        return False

    def _open_detail_page(self, label: str, detail_page: str | None = None) -> bool:
        target = detail_page or VIEW_PAGE_TARGETS.get(label) or RIBBON_PAGE_TARGETS.get(label) or label
        if label in VIEW_PAGE_STRIP_ACTIONS:
            self.view_page_action_var.set(label)
        opened = self._focus_detail_page(target)
        if opened:
            if label in {"Retrogrades", "Midpoints"}:
                self._set_workspace_page(label)
            if hasattr(self, "workspace_page_summary_var") and label not in TOP_NAV_ITEMS:
                self.workspace_page_summary_var.set(TOP_NAV_WORKSPACE_SUMMARIES.get(label, f"Detail page opened: {target}."))
            self._announce_visible_action(f"Opened {target} from More Detail.")
        return opened

    def _available_detail_pages(self) -> tuple[str, ...]:
        if not hasattr(self, "detail_notebook"):
            return DETAIL_PAGE_TABS
        visible = [str(self.detail_notebook.tab(tab_id, "text")) for tab_id in self.detail_notebook.tabs()]
        more_pages = list(getattr(self, "more_detail_page_titles", []))
        return tuple([*visible, *more_pages])

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
            "- Use Load Chart on a shortlist card to reopen that saved election in the main workspace.\n"
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

    def _load_shortlist_entry(self, entry_id: str) -> None:
        entry = shortlist_entry_by_id(self.shortlist, entry_id)
        if not entry:
            self.status_var.set("That shortlisted window is no longer available.")
            return

        entry_datetime = str(entry.get("datetime", "")).strip()
        date_text = ""
        time_text = ""
        if "T" in entry_datetime:
            try:
                parsed = datetime.fromisoformat(entry_datetime)
                date_text = parsed.date().isoformat()
                time_text = parsed.strftime("%H:%M")
            except ValueError:
                date_text = ""
                time_text = ""
        if not date_text:
            date_text = self.date_var.get()
            time_text = normalize_time_text(self.time_var.get())

        location_name = str(entry.get("location", "")).strip()
        timezone_name = str(entry.get("timezone", "")).strip() or self.timezone_var.get()
        resolved_location = self.locations_by_name.get(location_name)
        latitude = entry.get("latitude", getattr(resolved_location, "latitude", self.latitude_var.get()))
        longitude = entry.get("longitude", getattr(resolved_location, "longitude", self.longitude_var.get()))

        self.date_var.set(date_text)
        self.time_var.set(time_text)
        self.objective_var.set(str(entry.get("objective", self.objective_var.get())))
        self.location_name_var.set(location_name or self.location_name_var.get())
        self.latitude_var.set(f"{float(latitude):.4f}" if isinstance(latitude, (int, float)) else str(latitude))
        self.longitude_var.set(f"{float(longitude):.4f}" if isinstance(longitude, (int, float)) else str(longitude))
        self.timezone_var.set(timezone_name)
        if location_name in self.location_names:
            self.location_var.set(location_name)
        else:
            self.location_var.set("Custom")

        self.calculate(show_input_chart=True)
        target_time = str(entry.get("formattedTime", "")).strip()
        matched_window = next((window for window in self.current_windows if str(window.get("formattedTime", "")).strip() == target_time), None)
        if matched_window:
            self._select_window(matched_window)
        self._focus_detail_page("Summary")
        self.status_var.set(f"Loaded shortlisted window {target_time or 'into the workspace'}.")
        self._log_event(f"Loaded shortlist entry: {target_time or entry_id}")

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
            tk.Label(empty, text="No shortlisted windows yet.", bg=PALETTE["panel_alt"], fg=PALETTE["accent_dark"], font=("Georgia", 10, "bold")).pack(anchor="w")
            tk.Label(
                empty,
                text=(
                    "Run Find Best, click a candidate card, then press Shortlist or Save Pick. "
                    "Once saved, this board will rank candidates by score, confidence, cleanliness, steadiness, and tags."
                ),
                bg=PALETTE["panel_alt"],
                fg=PALETTE["text"],
                font=("Segoe UI", 8),
                wraplength=320,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(5, 0))
            tk.Label(
                empty,
                text="Good tags to start with: best for launch, backup, client-safe, needs review.",
                bg=PALETTE["panel_alt"],
                fg=PALETTE["muted"],
                font=("Segoe UI", 8),
                wraplength=320,
                justify=tk.LEFT,
                anchor="w",
            ).pack(fill=tk.X, pady=(5, 0))
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
        ttk.Button(controls, text="Load Chart", command=lambda entry_id=str(entry.get("id")): self._load_shortlist_entry(entry_id)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Add Tag", command=lambda entry_id=str(entry.get("id")), var=tag_value: self._add_tag_to_shortlist_entry(entry_id, var.get())).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Set A", command=lambda entry_id=str(entry.get("id")): self._set_shortlist_compare_slot(entry_id, "A")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="Set B", command=lambda entry_id=str(entry.get("id")): self._set_shortlist_compare_slot(entry_id, "B")).pack(side=tk.LEFT)

        note = str(entry.get("note", "")).strip()
        if note:
            tk.Label(card, text=note, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 9), wraplength=860, justify="left").pack(anchor="w", pady=(8, 0))

    def _current_report_text(self) -> str:
        report = build_report_text(self.selected_window, self.current_windows, self.current_location)
        analysis = ""
        if self.selected_window and self.current_location:
            analysis = "\n\n" + build_analysis_page(
                self.selected_window,
                self.current_windows,
                self.current_location,
                self.current_aspect_highlights,
                self.current_search_summary,
                self.current_rejection_summary,
            )
        if self.input_snapshot and self.selected_window:
            state = (
                "Chart State\n"
                f"Search start: {self.input_snapshot['formattedTime']}\n"
                f"Displayed chart: {self.displayed_chart_source} at {self.selected_window['formattedTime']}\n"
                f"{selection_offset_label(self.input_snapshot, self.selected_window)}\n\n"
            )
            return state + report + analysis
        return report + analysis

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
                "- Day Report opens the ranked best-aspects-through-the-day search report.",
                "- Search Page shows scan filters, rejected windows, and candidate-window diagnostics.",
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
        self._set_workspace_page("Settings")
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
        right_panel_theme_var = tk.StringVar(value=self.right_panel_theme_var.get())
        wheel_view_preset_var = tk.StringVar(value=self.wheel_view_preset_var.get())
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
        search_quality_mode_var = tk.StringVar(value=self.search_quality_mode_var.get())
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
        self._dialog_combo_row(workflow, "Wheel presentation", right_panel_theme_var, list(RIGHT_PANEL_THEME_NAMES))
        self._dialog_combo_row(workflow, "Wheel preset", wheel_view_preset_var, list(WHEEL_VIEW_PRESET_NAMES))
        self._dialog_combo_row(workflow, "Home location", home_var, home_choices)

        search = ttk.LabelFrame(body, text="Search Defaults", style="Panel.TLabelframe", padding=10)
        search.pack(fill=tk.X, pady=(10, 0))
        search.columnconfigure(0, weight=1)
        search.columnconfigure(1, weight=1)
        mode_frame = ttk.Frame(search, style="Panel.TFrame")
        mode_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(mode_frame, text="Search mode", style="Small.TLabel").pack(anchor="w", pady=(0, 3))
        ttk.Combobox(mode_frame, textvariable=search_quality_mode_var, values=list(SEARCH_QUALITY_MODE_NAMES), state="readonly").pack(fill=tk.X, ipady=5)
        self._dialog_entry_row(search, "Scan hours", scan_var, 1, 0)
        self._dialog_entry_row(search, "Step minutes", step_var, 1, 1)
        self._dialog_entry_row(search, "Minimum score", minimum_var, 2, 0)
        self._dialog_entry_row(search, "Minimum fit", minimum_fit_var, 2, 1)
        self._dialog_entry_row(search, "Minimum confidence", minimum_confidence_var, 3, 0)
        self._dialog_entry_row(search, "Minimum cleanliness", minimum_cleanliness_var, 3, 1)
        self._dialog_entry_row(search, "Maximum volatility", maximum_volatility_var, 4, 0)
        self._dialog_entry_row(search, "Max results", max_results_var, 4, 1)
        ttk.Checkbutton(search, text="Avoid major stress", variable=avoid_major_stress_var).grid(row=5, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        ttk.Checkbutton(search, text="Require applying support", variable=require_applying_support_var).grid(row=5, column=1, sticky="w", padx=(6, 0), pady=(0, 8))
        ttk.Checkbutton(search, text="Require angular benefic", variable=require_angular_benefic_var).grid(row=6, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        ttk.Checkbutton(search, text="Avoid angular malefics", variable=avoid_angular_malefics_var).grid(row=6, column=1, sticky="w", padx=(6, 0), pady=(0, 8))
        ttk.Checkbutton(search, text="Keep Moon non-void", variable=require_moon_non_void_var).grid(row=7, column=0, sticky="w", padx=(0, 6), pady=(0, 8))
        ttk.Checkbutton(search, text="Avoid objective anti-patterns", variable=avoid_objective_antipatterns_var).grid(row=7, column=1, sticky="w", padx=(6, 0), pady=(0, 8))

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
                get_point_set("full-electional").name,
                RIGHT_PANEL_THEME_LABELS["classic-natal"],
                WHEEL_VIEW_PRESET_LABELS["full-classic"],
                home_var.get(),
                scan_var.get(),
                step_var.get(),
                minimum_var.get(),
                minimum_fit_var.get(),
                minimum_confidence_var.get(),
                minimum_cleanliness_var.get(),
                maximum_volatility_var.get(),
                max_results_var.get(),
                search_quality_mode_var.get(),
                avoid_major_stress_var.get(),
                require_applying_support_var.get(),
                require_angular_benefic_var.get(),
                avoid_angular_malefics_var.get(),
                require_moon_non_void_var.get(),
                avoid_objective_antipatterns_var.get(),
            ),
        ).pack(side=tk.LEFT)
        ttk.Button(actions, text="Reset Locations", command=lambda: (dialog.destroy(), self._reset_locations())).pack(side=tk.LEFT, padx=(6, 0))
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
                right_panel_theme_var.get(),
                wheel_view_preset_var.get(),
                home_var.get(),
                scan_var.get(),
                step_var.get(),
                minimum_var.get(),
                minimum_fit_var.get(),
                minimum_confidence_var.get(),
                minimum_cleanliness_var.get(),
                maximum_volatility_var.get(),
                max_results_var.get(),
                search_quality_mode_var.get(),
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
        right_panel_theme: str,
        wheel_view_preset: str,
        home_location_name: str,
        scan_hours: str,
        step_minutes: str,
        minimum_score: str,
        minimum_fit: str,
        minimum_confidence: str,
        minimum_cleanliness: str,
        maximum_volatility: str,
        max_results: str,
        search_quality_mode: str,
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
        self.right_panel_theme_var.set(right_panel_theme if right_panel_theme in RIGHT_PANEL_THEME_NAMES else RIGHT_PANEL_THEME_LABELS["classic-natal"])
        self.wheel_view_preset_var.set(wheel_view_preset if wheel_view_preset in WHEEL_VIEW_PRESET_NAMES else WHEEL_VIEW_PRESET_LABELS["full-classic"])
        self._apply_wheel_view_preset(self._current_wheel_preset_id(), save=False)
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
        self.search_quality_mode_var.set(search_quality_mode if search_quality_mode in SEARCH_QUALITY_MODE_NAMES else SEARCH_QUALITY_MODE_NAMES[0])
        self.avoid_major_stress_var.set(avoid_major_stress)
        self.require_applying_support_var.set(require_applying_support)
        self.require_angular_benefic_var.set(require_angular_benefic)
        self.avoid_angular_malefics_var.set(avoid_angular_malefics)
        self.require_moon_non_void_var.set(require_moon_non_void)
        self.avoid_objective_antipatterns_var.set(avoid_objective_antipatterns)
        self._sync_aspects_to_preset()
        self._update_search_summary()
        self._refresh_location_status()
        self._apply_current_theme()
        self._apply_page_mode(self._current_page_mode_id(), save=False)
        dialog.destroy()
        self.status_var.set("Preferences applied.")
        self.calculate(show_input_chart=True)

    def _selected_aspect_ids(self) -> list[str]:
        return [aspect for aspect, var in self.aspect_vars.items() if var.get()]

    def _aspect_profile_names(self) -> list[str]:
        return [profile.name for profile in self.aspect_profiles]

    def _profile_by_name(self, name: str) -> AspectProfile:
        for profile in self.aspect_profiles:
            if profile.name == name:
                return profile
        return self.aspect_profiles[0] if self.aspect_profiles else self.active_aspect_profile

    def _active_aspect_definitions(self) -> tuple[Aspect, ...]:
        return self.active_aspect_profile.aspects

    def _aspect_profile_changed(self, _event: object | None = None) -> None:
        previous = {aspect_id: var.get() for aspect_id, var in self.aspect_vars.items()}
        self.active_aspect_profile = self._profile_by_name(self.aspect_profile_var.get())
        self.aspect_profile_var.set(self.active_aspect_profile.name)
        self._refresh_aspect_focus_controls(previous)
        self._refresh_left_status_chips()
        self._save_session()
        self.status_var.set(f"Aspect profile active: {self.active_aspect_profile.name}.")

    def _refresh_aspect_focus_controls(
        self,
        selections: Mapping[str, object] | None = None,
        preset: object | None = None,
    ) -> None:
        if not hasattr(self, "aspect_focus_options_frame"):
            return
        for child in self.aspect_focus_options_frame.winfo_children():
            child.destroy()
        preset = preset or self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        selection_map = selections if isinstance(selections, Mapping) else {}
        self.aspect_vars = {}
        for aspect in self.active_aspect_profile.aspects:
            if aspect.id in selection_map:
                checked = bool(selection_map[aspect.id]) and aspect.enabled
            else:
                checked = bool(aspect.enabled and (aspect.id in preset.aspect_ids or not aspect.built_in))
            var = tk.BooleanVar(value=checked)
            self.aspect_vars[aspect.id] = var
            label = (
                f"{aspect.glyph or aspect.abbreviation}  {aspect.name}  "
                f"{float(aspect.angle):g}deg / orb {float(aspect.default_orb):g}deg"
            )
            check = ttk.Checkbutton(self.aspect_focus_options_frame, text=label, variable=var)
            check.pack(anchor="w", pady=2)
            if not aspect.enabled:
                check.state(["disabled"])
        if not self.aspect_vars:
            tk.Label(
                self.aspect_focus_options_frame,
                text="No aspect definitions are available. Open Aspect Config to restore the built-ins.",
                bg=PALETTE["panel_alt"],
                fg=PALETTE["stress"],
                font=("Segoe UI", 8, "bold"),
                wraplength=265,
                justify=tk.LEFT,
            ).pack(fill=tk.X)

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
        self._set_workspace_page("Map")
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
            f"- Evaluated windows: {self.current_searched_window_count}",
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
            *moon_void_course_summary(
                self.selected_window,
                self.current_location,
                self._selected_aspect_ids(),
                self._active_aspect_definitions(),
            ),
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
        calculation_confidence = self.selected_window.get("calculationConfidence", {})
        notes = self.selected_window.get("calculationNotes", [])
        cusp_sources = sorted({str(cusp.get("source", "native")) for cusp in self.selected_window.get("houseCusps", [])})
        planetary_hour = self.selected_window.get("planetaryHour", {})
        trust_lines = [
            "Calculation Trust",
            (
                f"- {calculation_confidence.get('score', 'n/a')} / 99 "
                f"({calculation_confidence.get('band', 'n/a')}); "
                f"penalty -{calculation_confidence.get('penalty', 0)}"
                if isinstance(calculation_confidence, dict)
                else "- Calculation trust unavailable."
            ),
        ]
        if isinstance(calculation_confidence, dict):
            for penalty in calculation_confidence.get("penalties", [])[:6]:
                if isinstance(penalty, dict):
                    trust_lines.append(f"- {penalty.get('label')}: {penalty.get('value')} confidence. {penalty.get('detail')}")
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
            *trust_lines,
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
