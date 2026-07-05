"""Wheel rendering, interaction, and Moon-drag methods."""

from __future__ import annotations


def bind_desktop_globals(namespace: dict[str, object]) -> None:
    """Bind the shared desktop shell namespace after desktop.py is initialized."""

    protected = {"__name__", "__package__", "__spec__", "__loader__", "__file__", "__cached__", "__builtins__"}
    globals().update({name: value for name, value in namespace.items() if name not in protected})


class DesktopWheelMixin:
    def _event_wheel_degrees(self, event: tk.Event) -> float | None:
        geometry = getattr(self, "_wheel_drag_geometry", {})
        if not geometry:
            return None
        try:
            return wheel_degrees_from_xy(float(geometry["cx"]), float(geometry["cy"]), float(event.x), float(event.y))
        except (KeyError, TypeError, ValueError):
            return None

    def _start_moon_drag(self, event: tk.Event, planet_id: str) -> None:
        if not self.selected_window:
            return
        self._moon_drag_state = {
            "planet_id": planet_id,
            "start_x": float(event.x),
            "start_y": float(event.y),
            "moved": False,
            "target_degrees": self._event_wheel_degrees(event),
        }
        self.canvas.configure(cursor="fleur")
        body_name = self._drag_body_name(planet_id)
        self.status_var.set(f"{body_name} drag ready: move around the wheel, then release to solve chart time.")

    def _drag_moon_marker(self, event: tk.Event) -> None:
        state = getattr(self, "_moon_drag_state", {})
        if not state:
            return
        start_x = float(state.get("start_x", event.x))
        start_y = float(state.get("start_y", event.y))
        moved = math.hypot(float(event.x) - start_x, float(event.y) - start_y) >= 4.0
        target_degrees = self._event_wheel_degrees(event)
        state["moved"] = bool(state.get("moved")) or moved
        state["target_degrees"] = target_degrees
        self._moon_drag_state = state
        self._draw_moon_drag_preview(target_degrees)
        if target_degrees is not None:
            body_name = self._drag_body_name(str(state.get("planet_id") or ""))
            self.status_var.set(f"{body_name} drag target: {target_degrees:.1f} deg on wheel. Release to solve chart time.")

    def _release_moon_drag(self, event: tk.Event, planet_id: str) -> None:
        state = getattr(self, "_moon_drag_state", {})
        self._moon_drag_state = {}
        self.canvas.delete("moon-drag-preview")
        self.canvas.configure(cursor="")
        if not state or not state.get("moved"):
            self._select_planet_by_id(planet_id)
            return
        target_degrees = self._event_wheel_degrees(event)
        if target_degrees is None:
            target_degrees = state.get("target_degrees")
        if target_degrees is None:
            self.status_var.set("Moon drag cancelled: wheel target was unavailable.")
            return
        self._apply_body_drag_time(planet_id, float(target_degrees))

    def _draw_moon_drag_preview(self, target_degrees: float | None) -> None:
        self.canvas.delete("moon-drag-preview")
        if target_degrees is None:
            return
        geometry = getattr(self, "_wheel_drag_geometry", {})
        try:
            cx = float(geometry["cx"])
            cy = float(geometry["cy"])
            outer = float(geometry["outer"])
        except (KeyError, TypeError, ValueError):
            return
        radius = outer * (0.720 if self._is_classic_wheel_theme() else 0.645)
        x, y = _polar(cx, cy, radius, target_degrees)
        inner_x, inner_y = _polar(cx, cy, max(30.0, radius - 55.0), target_degrees)
        self.canvas.create_line(inner_x, inner_y, x, y, fill=PALETTE["warning"], width=2, dash=(4, 4), tags=("moon-drag-preview",))
        self.canvas.create_oval(x - 15, y - 15, x + 15, y + 15, outline=PALETTE["warning"], width=2, tags=("moon-drag-preview",))
        self.canvas.create_text(
            x,
            y,
            text=planet_glyph("Moon"),
            fill=CLASSIC_PLANET_COLORS.get("Moon", PALETTE["warning"]),
            font=("Segoe UI Symbol", 18, "bold"),
            tags=("moon-drag-preview",),
        )

    def _drag_body_name(self, planet_id: str) -> str:
        if self.selected_window:
            for planet in self.selected_window.get("positions", []):
                if isinstance(planet, dict) and str(planet.get("id")) == str(planet_id):
                    return str(planet.get("name") or "Body")
        return "Body"

    def _apply_moon_drag_time(self, target_degrees: float) -> None:
        self._apply_body_drag_time("moon", target_degrees)

    def _apply_body_drag_time(self, planet_id: str, target_degrees: float) -> None:
        if not self.selected_window or not self.current_location:
            self.status_var.set("Planet drag needs an active calculated chart first.")
            return
        body_name = self._drag_body_name(planet_id)
        try:
            matched_time, matched_distance = self._find_time_for_body_wheel_degrees(planet_id, target_degrees)
        except Exception as exc:  # pragma: no cover - UI resilience path.
            debug_path = record_desktop_exception("Planet drag timing solve failed")
            detail = f" Debug trace: {debug_path}" if debug_path else ""
            self._log_event(f"{body_name} drag failed: {exc}")
            self.status_var.set(f"{body_name} drag failed: {exc}.{detail}")
            return
        local = matched_time.astimezone(ZoneInfo(self.current_location.timezone))
        self.status_var.set(
            f"{body_name} drag preview solved {local:%Y-%m-%d %H:%M}; miss {matched_distance:.2f} deg. Waiting for confirmation."
        )
        try:
            should_apply = messagebox.askyesno(
                "Apply Planet Drag Time?",
                (
                    f"{body_name} drag found this chart time:\n\n"
                    f"{local:%Y-%m-%d %H:%M} {local.tzname()}\n"
                    f"Wheel-angle miss: {matched_distance:.2f} degrees\n\n"
                    "Apply this as the input chart time?"
                ),
            )
        except Exception:
            should_apply = True
        if not should_apply:
            self.status_var.set(f"{body_name} drag cancelled; input chart time was not changed.")
            self._log_event(f"{body_name} drag preview cancelled at miss {matched_distance:.2f} deg")
            return
        self.date_var.set(local.strftime("%Y-%m-%d"))
        self.time_var.set(local.strftime("%H:%M"))
        self._log_event(
            f"{body_name} drag set input time to {self.date_var.get()} {self.time_var.get()} "
            f"for wheel angle {target_degrees:.1f} deg (miss {matched_distance:.2f} deg)"
        )
        self.status_var.set(
            f"{body_name} drag solved: {local:%Y-%m-%d %H:%M} local; miss {matched_distance:.2f} deg; recalculating."
        )
        self.calculate(show_input_chart=True)

    def _find_time_for_moon_wheel_degrees(self, target_degrees: float) -> tuple[datetime, float]:
        return self._find_time_for_body_wheel_degrees("moon", target_degrees)

    def _find_time_for_body_wheel_degrees(self, planet_id: str, target_degrees: float) -> tuple[datetime, float]:
        if not self.selected_window or not self.current_location:
            raise ValueError("No active chart/location is available.")
        start_moment = self.selected_window["date"]
        body_name = self._drag_body_name(planet_id)
        preset = self.presets_by_name.get(self.preset_var.get(), ELECTIONAL_PRESETS[1])
        zodiac_system = get_zodiac_system(self.zodiac_system_var.get())
        house_system = get_house_system(self.house_system_var.get())
        selected_aspects = self._selected_aspect_ids()
        aspect_definitions = self._active_aspect_definitions()

        def _body_angle(moment: datetime) -> float:
            snapshot = build_snapshot_for_moment(
                moment,
                self.current_location,
                preset,
                selected_aspects,
                zodiac_system.id,
                house_system.id,
                self.objective_var.get(),
                "fast",
                aspect_definitions,
            )
            ascendant = next(angle for angle in snapshot["angles"] if angle["id"] == "asc")
            body = next(planet for planet in snapshot["positions"] if planet["name"] == body_name)
            return wheel_degrees(float(body["longitude"]), float(ascendant["longitude"]))

        best_moment = start_moment
        best_distance = 999.0
        for offset_minutes in range(-18 * 60, 18 * 60 + 1, 10):
            moment = start_moment + timedelta(minutes=offset_minutes)
            distance = circular_distance_degrees(_body_angle(moment), target_degrees)
            if distance < best_distance:
                best_moment = moment
                best_distance = distance
        refined_center = best_moment
        for offset_minutes in range(-12, 13):
            moment = refined_center + timedelta(minutes=offset_minutes)
            distance = circular_distance_degrees(_body_angle(moment), target_degrees)
            if distance < best_distance:
                best_moment = moment
                best_distance = distance
        return best_moment, best_distance

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
        if self._is_classic_wheel_theme():
            self._draw_classic_wheel(snapshot, width, height)
            return
        cx = width / 2
        cy = height / 2
        side_padding = 96 if not self.compact_wheel_var.get() and self.show_fixed_stars_var.get() else 70
        vertical_padding = 62 if self.compact_wheel_var.get() else 76
        fit_width = max(320, width - side_padding * 2)
        fit_height = max(320, height - vertical_padding * 2)
        outer = max(150, min(fit_width, fit_height) / 2 * self.wheel_zoom)
        constellation_inner = outer * 0.895
        sign_outer = outer * 0.885
        zodiac_inner = outer * 0.755
        house_inner = outer * (0.52 if self.compact_wheel_var.get() else 0.47)
        aspect_radius = outer * 0.425

        self._draw_grid(width, height)
        self.canvas.create_oval(cx - outer - 22, cy - outer - 16, cx + outer + 22, cy + outer + 28, fill="#e4ebf0", outline="")
        self.canvas.create_oval(cx - outer - 10, cy - outer - 8, cx + outer + 10, cy + outer + 14, fill="#edf2f5", outline="")
        self.canvas.create_oval(cx - outer + 7, cy - outer + 10, cx + outer + 7, cy + outer + 10, fill=PALETTE["surface_shadow"], outline="")
        self.canvas.create_oval(
            cx - outer,
            cy - outer,
            cx + outer,
            cy + outer,
            fill="#f7fafb",
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
        self._wheel_drag_geometry = {"cx": cx, "cy": cy, "outer": outer, "asc_lon": asc_lon}

        self._draw_constellation_band(cx, cy, outer, constellation_inner, asc_lon)
        self.canvas.create_oval(
            cx - constellation_inner,
            cy - constellation_inner,
            cx + constellation_inner,
            cy + constellation_inner,
            fill=PALETTE["chart_ring_fill"],
            outline="#ffffff",
            width=1,
        )

        for index, sign in enumerate(SIGN_LABELS):
            start = wheel_degrees(index * 30, asc_lon)
            self.canvas.create_arc(
                cx - sign_outer,
                cy - sign_outer,
                cx + sign_outer,
                cy + sign_outer,
                start=start,
                extent=30,
                fill=SIGN_COLORS[index],
                outline="#fffdf8",
                width=1,
            )
            label_angle = wheel_degrees(index * 30 + 15, asc_lon)
            lx, ly = _polar(cx, cy, sign_outer * 0.93, label_angle)
            self._draw_sign_badge(lx, ly, sign, SIGN_COLORS[index])

        self.canvas.create_oval(cx - sign_outer + 1, cy - sign_outer + 1, cx + sign_outer - 1, cy + sign_outer - 1, outline="#ffffff", width=1)
        self.canvas.create_oval(cx - sign_outer + 11, cy - sign_outer + 11, cx + sign_outer - 11, cy + sign_outer - 11, outline="#ffffff", width=1)
        self._draw_degree_ticks(cx, cy, sign_outer, zodiac_inner, asc_lon)

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
        span_by_house = {int(row["house"]): row["span"] for row in house_span_rows(snapshot)}
        for house_index, cusp in enumerate(house_cusps):
            next_cusp = house_cusps[(house_index + 1) % len(house_cusps)]
            house_no = int(cusp["house"])
            cusp_longitude = float(cusp["longitude"])
            label_longitude = midpoint_longitude(cusp_longitude, float(next_cusp["longitude"]))
            angle = wheel_degrees(cusp_longitude, asc_lon)
            x1, y1 = _polar(cx, cy, house_inner, angle)
            x2, y2 = _polar(cx, cy, zodiac_inner, angle)
            self.canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                fill=PALETTE["chart_line"],
                width=2 if house_no in {1, 4, 7, 10} else 1,
            )
            label_angle = wheel_degrees(label_longitude, asc_lon)
            lx, ly = _polar(cx, cy, outer * 0.64, label_angle)
            self.canvas.create_text(lx, ly, text=str(house_no), fill=PALETTE["accent_dark"], font=("Segoe UI Semibold", 10 if self.compact_wheel_var.get() else 12))
            span_text = house_span_label(span_by_house.get(house_no))
            if span_text and self._is_diagnostic_wheel_preset():
                sx, sy = _polar(cx, cy, outer * 0.585, label_angle)
                self._draw_halo_text(
                    sx,
                    sy,
                    text=span_text,
                    fill=PALETTE["muted"],
                    halo=PALETTE["surface"],
                    font=("Segoe UI", 7 if self.compact_wheel_var.get() else 8),
                    tags=("house-span",),
                )

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

    def _draw_classic_wheel(self, snapshot: dict[str, object], width: int, height: int) -> None:
        clean_mode = self._current_wheel_preset_id() == "clean"
        metadata_width = 0 if clean_mode else 142 if width >= 600 else 0
        chart_width = max(320, width - metadata_width)
        cx = metadata_width + chart_width / 2
        cy = height / 2
        side_padding = 14 if self.show_fixed_stars_var.get() else 10
        fit_width = max(320, chart_width - side_padding * 2)
        fit_height = max(320, height - 14)
        outer = max(150, min(fit_width, fit_height) / 2 * self.wheel_zoom)
        sign_outer = outer * 0.958
        tick_outer = outer * 0.878
        zodiac_inner = outer * 0.760
        house_outer = outer * 0.525
        house_inner = outer * 0.385
        aspect_radius = outer * 0.382
        house_label_radius = (house_outer + house_inner) / 2
        self._classic_center_radius = aspect_radius

        self._draw_grid(width, height)
        if metadata_width:
            self._draw_classic_chart_info(snapshot, 10, 10, metadata_width - 20)
        self.canvas.create_oval(cx - outer - 8, cy - outer - 8, cx + outer + 8, cy + outer + 8, fill="#d6dbce", outline="")
        self.canvas.create_oval(cx - outer, cy - outer, cx + outer, cy + outer, fill=CLASSIC_CONSTELLATION_FILL, outline=CLASSIC_HOUSE_LINE, width=1)
        self.canvas.create_oval(cx - sign_outer, cy - sign_outer, cx + sign_outer, cy + sign_outer, fill="#eee6c7", outline="#000000", width=1)

        ascendant = next(angle for angle in snapshot["angles"] if angle["id"] == "asc")
        asc_lon = float(ascendant["longitude"])
        self._wheel_drag_geometry = {"cx": cx, "cy": cy, "outer": outer, "asc_lon": asc_lon}
        zodiac_system = snapshot.get("zodiacSystem")
        system_id = getattr(zodiac_system, "id", None) or getattr(zodiac_system, "name", None)
        segments = zodiac_arc_segments(system_id)

        for segment in segments:
            start = wheel_degrees(float(segment["start"]), asc_lon)
            self.canvas.create_arc(
                cx - sign_outer,
                cy - sign_outer,
                cx + sign_outer,
                cy + sign_outer,
                start=start,
                extent=float(segment["extent"]),
                fill=str(segment["color"]),
                outline="#f9f6df",
                width=1,
            )
            if float(segment["extent"]) < 4:
                continue
            label_angle = wheel_degrees(float(segment["midpoint"]), asc_lon)
            lx, ly = _polar(cx, cy, outer * 0.908, label_angle)
            label_font = ("Segoe UI Symbol", 12 if self.compact_wheel_var.get() else 14, "bold")
            if bool(segment.get("isOphiuchus")):
                self._draw_ophiuchus_symbol(lx, ly, 10 if self.compact_wheel_var.get() else 12)
            else:
                self._draw_halo_text(
                    lx,
                    ly,
                    text=str(segment.get("label") or segment.get("fallbackLabel") or ""),
                    fill=CLASSIC_SIGN_TEXT,
                    halo=CLASSIC_SIGN_HALO,
                    font=label_font,
                    tags=("sign-label",),
                )

        self.canvas.create_oval(cx - tick_outer, cy - tick_outer, cx + tick_outer, cy + tick_outer, fill=CLASSIC_TICK_RING, outline="#000000", width=1)
        self._draw_degree_ticks(cx, cy, tick_outer, zodiac_inner, asc_lon)
        self.canvas.create_oval(cx - zodiac_inner, cy - zodiac_inner, cx + zodiac_inner, cy + zodiac_inner, fill=CLASSIC_PLANET_FIELD, outline="#000000", width=1)
        self._draw_house_sectors(
            snapshot,
            cx,
            cy,
            zodiac_inner,
            house_outer,
            asc_lon,
            fills=CLASSIC_HOUSE_FIELD_COLORS,
            outline=CLASSIC_HOUSE_FIELD_LINE,
            width=1,
        )
        self._draw_house_sectors(snapshot, cx, cy, house_outer, house_inner, asc_lon, fills=CLASSIC_HOUSE_RING_COLORS, outline="#4b2345", width=1)
        self.canvas.create_oval(cx - house_outer, cy - house_outer, cx + house_outer, cy + house_outer, outline="#101010", width=1)
        self.canvas.create_oval(cx - house_inner, cy - house_inner, cx + house_inner, cy + house_inner, fill=CLASSIC_ASPECT_CENTER, outline=CLASSIC_HOUSE_LINE, width=1)

        house_cusps = sorted(snapshot.get("houseCusps", []), key=lambda cusp: int(cusp["house"]))
        span_by_house = {int(row["house"]): row["span"] for row in house_span_rows(snapshot)}
        house_labels: list[tuple[float, float, str]] = []
        house_span_labels: list[tuple[float, float, str]] = []
        for house_index, cusp in enumerate(house_cusps):
            next_cusp = house_cusps[(house_index + 1) % len(house_cusps)]
            house_no = int(cusp["house"])
            cusp_longitude = float(cusp["longitude"])
            next_longitude = float(next_cusp["longitude"])
            angle = wheel_degrees(cusp_longitude, asc_lon)
            x1, y1 = _polar(cx, cy, aspect_radius, angle)
            x2, y2 = _polar(cx, cy, zodiac_inner, angle)
            self.canvas.create_line(x1, y1, x2, y2, fill=CLASSIC_HOUSE_LINE, width=3 if house_no in {1, 4, 7, 10} else 2)
            marker_inner_x, marker_inner_y = _polar(cx, cy, house_outer - 5, angle)
            marker_outer_x, marker_outer_y = _polar(cx, cy, zodiac_inner + 3, angle)
            self.canvas.create_line(
                marker_inner_x,
                marker_inner_y,
                marker_outer_x,
                marker_outer_y,
                fill="#0f1534",
                width=2 if house_no in {1, 4, 7, 10} else 1,
                tags=("house-projection",),
            )
            label_angle = wheel_degrees(midpoint_longitude(cusp_longitude, next_longitude), asc_lon)
            lx, ly = _polar(cx, cy, house_label_radius, label_angle)
            house_labels.append((lx, ly, str(house_no)))
            span_text = house_span_label(span_by_house.get(house_no))
            if span_text and self._is_diagnostic_wheel_preset():
                sx, sy = _polar(cx, cy, house_outer + (zodiac_inner - house_outer) * 0.22, label_angle)
                house_span_labels.append((sx, sy, span_text))

        if self.show_aspects_var.get():
            self._draw_classic_aspects(snapshot, cx, cy, aspect_radius * 0.94, asc_lon)
        self._draw_angles(snapshot, cx, cy, outer, asc_lon)
        point_set = get_point_set(self.point_set_var.get())
        if self.show_fixed_stars_var.get() and point_set.show_fixed_stars:
            self._draw_fixed_stars(snapshot, cx, cy, asc_lon, outer)
        self._draw_planets(snapshot, cx, cy, asc_lon, outer)
        if self.show_lots_var.get() and point_set.show_lots:
            self._draw_lots(snapshot, cx, cy, asc_lon, outer)
        if self.show_nodes_var.get() and point_set.show_nodes:
            self._draw_nodes(snapshot, cx, cy, asc_lon, outer)
        for sx, sy, span_text in house_span_labels:
            self._draw_house_span_label(sx, sy, span_text)
        for lx, ly, house_text in house_labels:
            self._draw_house_number_badge(lx, ly, house_text)
        self._draw_focused_body_callout(snapshot, cx, cy, outer, asc_lon)
        self._draw_center_hub(cx, cy, snapshot)
        footer_y = min(height - 14, cy + outer + 18)
        zodiac_label = "Zodiac 13" if str(getattr(snapshot.get("zodiacSystem"), "id", "")).lower() == "true-13-sign" else str(getattr(snapshot.get("zodiacSystem"), "name", "Zodiac"))
        self.canvas.create_text(
            cx,
            footer_y,
            text=f"{zodiac_label} - Astrology Data Sheet",
            fill=CLASSIC_PANEL_TEXT,
            font=("Georgia", 9),
            tags=("classic-footer",),
        )
        if self._is_diagnostic_wheel_preset():
            self.canvas.create_text(
                cx,
                min(height - 4, footer_y + 12),
                text=house_geometry_summary(snapshot),
                fill=CLASSIC_PANEL_MUTED,
                font=("Segoe UI", 7),
                tags=("classic-footer",),
            )

    def _draw_house_number_badge(self, x: float, y: float, text: str) -> None:
        self._draw_halo_text(
            x,
            y,
            text=text,
            fill="#10121f",
            halo="#d6c1c9",
            font=("Georgia", 11 if self.compact_wheel_var.get() else 13, "bold"),
            tags=("house-label",),
        )

    def _draw_house_span_label(self, x: float, y: float, text: str) -> None:
        self._draw_halo_text(
            x,
            y,
            text=text,
            fill=CLASSIC_HOUSE_SPAN_TEXT,
            halo=CLASSIC_HOUSE_SPAN_HALO,
            font=("Segoe UI", 7 if self.compact_wheel_var.get() else 8, "bold"),
            tags=("house-span",),
        )

    def _draw_classic_aspects(self, snapshot: dict[str, object], cx: float, cy: float, radius: float, asc_lon: float) -> None:
        positions = {planet["name"]: planet for planet in self._visible_planets(snapshot)}
        ranked_aspects = sorted(
            [
                aspect
                for aspect in snapshot.get("detectedAspects", [])
                if isinstance(aspect, dict)
                and isinstance(aspect.get("bodies"), list)
                and len(aspect.get("bodies", [])) == 2
            ],
            key=lambda aspect: (
                bool(aspect.get("isApplying")),
                float(aspect.get("strength", 0) or 0),
                -float(aspect.get("orb", 99) or 99),
            ),
            reverse=True,
        )
        for aspect in ranked_aspects[:14]:
            body_a, body_b = aspect["bodies"]
            if body_a not in positions or body_b not in positions:
                continue
            angle_a = wheel_degrees(float(positions[body_a]["longitude"]), asc_lon)
            angle_b = wheel_degrees(float(positions[body_b]["longitude"]), asc_lon)
            x1, y1 = _polar(cx, cy, radius, angle_a)
            x2, y2 = _polar(cx, cy, radius, angle_b)
            tone = str(aspect.get("tone") or "")
            color = CLASSIC_ASPECT_SUPPORT if tone == "support" else CLASSIC_ASPECT_STRESS if tone == "stress" else CLASSIC_ASPECT_NEUTRAL
            width = 3 if aspect.get("isApplying") else 2
            dash = () if aspect.get("isApplying") else (5, 5)
            self.canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                fill=color,
                width=width,
                dash=dash,
                tags=("classic-aspect",),
            )

    def _draw_ophiuchus_symbol(self, x: float, y: float, size: float) -> None:
        color = CLASSIC_SIGN_TEXT
        halo = CLASSIC_SIGN_HALO
        self.canvas.create_line(x, y - size, x, y + size, fill=halo, width=4, tags=("sign-label-halo",))
        self.canvas.create_line(x - size * 0.55, y - size * 0.55, x + size * 0.55, y - size * 0.55, fill=halo, width=4, tags=("sign-label-halo",))
        self.canvas.create_line(x, y - size, x, y + size, fill=color, width=2, tags=("sign-label",))
        self.canvas.create_line(x - size * 0.55, y - size * 0.55, x + size * 0.55, y - size * 0.55, fill=color, width=2, tags=("sign-label-vector",))
        points = [
            x - size * 0.55,
            y + size * 0.25,
            x - size * 0.18,
            y + size * 0.55,
            x + size * 0.20,
            y + size * 0.10,
            x + size * 0.55,
            y + size * 0.45,
        ]
        self.canvas.create_line(*points, fill=halo, width=5, smooth=True, tags=("sign-label-halo",))
        self.canvas.create_line(*points, fill=color, width=2, smooth=True, tags=("sign-label-vector",))

    def _draw_center_hub(self, cx: float, cy: float, snapshot: dict[str, object]) -> None:
        if self._is_classic_wheel_theme():
            center_radius = float(getattr(self, "_classic_center_radius", 112.0))
            self.canvas.create_oval(cx - center_radius, cy - center_radius, cx + center_radius, cy + center_radius, fill="", outline=CLASSIC_CENTER_LINE, width=1)
            self.canvas.create_oval(cx - center_radius * 0.68, cy - center_radius * 0.68, cx + center_radius * 0.68, cy + center_radius * 0.68, fill="", outline=CLASSIC_CENTER_LINE, width=1)
            if self.show_score_overlay_var.get():
                self.canvas.create_text(cx, cy - 10, text=f"Score {snapshot['score']}", fill="#18214e", font=("Segoe UI Semibold", 13))
                self.canvas.create_text(cx, cy + 14, text=score_band_label(int(snapshot["score"])), fill="#00607b", font=("Segoe UI", 9, "bold"))
            return
        self.canvas.create_oval(cx - 63, cy - 58, cx + 63, cy + 68, fill="#dde7ec", outline="")
        self.canvas.create_oval(cx - 60, cy - 60, cx + 60, cy + 60, fill=PALETTE["center_hub"], outline=PALETTE["chart_bezel"], width=2)
        self.canvas.create_oval(cx - 49, cy - 49, cx + 49, cy + 49, outline=PALETTE["chart_bezel_inner"], width=1)
        self.canvas.create_oval(cx - 37, cy - 37, cx + 37, cy + 37, outline="#edf4f2", width=1)
        self.canvas.create_line(cx - 30, cy + 2, cx + 30, cy + 2, fill=PALETTE["chart_bezel_inner"], width=1)
        self.canvas.create_text(cx, cy - 12, text=f"Score {snapshot['score']}", fill=PALETTE["top_bar_dark"], font=("Segoe UI Semibold", 13 if self.compact_wheel_var.get() else 15))
        self.canvas.create_text(cx, cy + 15, text=score_band_label(int(snapshot["score"])), fill=PALETTE["accent_dark"], font=("Segoe UI Semibold", 8 if self.compact_wheel_var.get() else 9))

    def _draw_halo_text(
        self,
        x: float,
        y: float,
        *,
        text: str,
        fill: str,
        halo: str,
        font: tuple[str, int] | tuple[str, int, str],
        anchor: str = "center",
        tags: tuple[str, ...] = (),
    ) -> None:
        halo_tags = tuple(f"{tag}-halo" for tag in tags) if tags else ()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.canvas.create_text(x + dx, y + dy, text=text, fill=halo, font=font, anchor=anchor, tags=halo_tags)
        self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor, tags=tags)

    def _is_focused_body(self, kind: str, name: str) -> bool:
        if kind == "planet" and name in getattr(self, "focused_aspect_bodies", set()):
            return True
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
        if self._is_classic_wheel_theme():
            label_x, label_y = _polar(cx, cy, outer * 1.10, degrees)
            label_anchor = "w" if math.cos(math.radians(degrees)) >= 0 else "e"
            position_text = classic_planet_degree_text(body)
            if not position_text and isinstance(body, Mapping) and "zodiac" in body:
                position_text = format_position(body)
            label_text = f"{body.get('name', kind.title())}  {position_text}".strip()
            self.canvas.create_line(anchor_x, anchor_y, tip_x, tip_y, label_x, label_y, fill="#385f94", width=1, smooth=True)
            self.canvas.create_text(
                label_x,
                label_y,
                text=label_text,
                anchor=label_anchor,
                fill="#203f73",
                font=("Segoe UI", 9, "bold"),
            )
            return
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
        fills: tuple[str, ...] | None = None,
        outline: str = "",
        width: int = 1,
    ) -> None:
        house_cusps = sorted(snapshot.get("houseCusps", []), key=lambda cusp: int(cusp["house"]))
        if not house_cusps:
            return
        fills = fills or (PALETTE["chart_house_fill"], PALETTE["chart_house_fill_alt"])
        for index, cusp in enumerate(house_cusps):
            next_cusp = house_cusps[(index + 1) % len(house_cusps)]
            start = wheel_degrees(float(cusp["longitude"]), asc_lon)
            end = wheel_degrees(float(next_cusp["longitude"]), asc_lon)
            outer_points = _arc_points(cx, cy, outer_radius, start, end)
            inner_points = _arc_points(cx, cy, inner_radius, end, start)
            self.canvas.create_polygon(
                outer_points + inner_points,
                fill=fills[index % len(fills)],
                outline=outline,
                width=width,
            )

    def _draw_constellation_band(self, cx: float, cy: float, outer: float, inner: float, asc_lon: float) -> None:
        for segment in constellation_arc_segments():
            start = wheel_degrees(float(segment["start"]), asc_lon)
            extent = float(segment["extent"])
            self.canvas.create_arc(
                cx - outer,
                cy - outer,
                cx + outer,
                cy + outer,
                start=start,
                extent=extent,
                fill=str(segment["color"]),
                outline="#ffffff",
                width=1,
            )
        self.canvas.create_oval(cx - inner, cy - inner, cx + inner, cy + inner, fill="#f7fafb", outline=PALETTE["chart_bezel_inner"], width=1)
        if self.compact_wheel_var.get():
            return
        for segment in constellation_arc_segments():
            if float(segment["extent"]) < 10:
                continue
            label_angle = wheel_degrees(float(segment["midpoint"]), asc_lon)
            lx, ly = _polar(cx, cy, outer * 0.947, label_angle)
            self.canvas.create_text(
                lx,
                ly,
                text=str(segment["abbreviation"]),
                fill=PALETTE["top_bar_dark"],
                font=("Segoe UI Semibold", 7),
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
            if self._is_classic_wheel_theme():
                if degree % 30 == 0:
                    tick_length = 18
                    line_width = 2
                    color = "#000000"
                elif degree % 10 == 0:
                    tick_length = 10
                    line_width = 1
                    color = "#1c1c1c"
                elif degree % 5 == 0:
                    tick_length = 7
                    line_width = 1
                    color = "#2c2c2c"
                else:
                    tick_length = 4
                    line_width = 1
                    color = "#3d3d3d"
            else:
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
        if self._is_classic_wheel_theme():
            return
        for x in range(0, width, 72):
            self.canvas.create_line(x, 0, x, height, fill=PALETTE["canvas_grid"], width=1)
        for y in range(0, height, 72):
            self.canvas.create_line(0, y, width, y, fill=PALETTE["canvas_grid"], width=1)

    def _draw_wheel_legend(self, width: int, height: int) -> None:
        if self.compact_wheel_var.get() or self._is_classic_wheel_theme():
            return
        x = 16
        y = max(16, height - 88)
        self.canvas.create_rectangle(
            x,
            y,
            x + 290,
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
        self.canvas.create_arc(x + 128, y + 10, x + 156, y + 38, start=20, extent=80, fill=CONSTELLATION_COLORS[2], outline="#ffffff")
        self.canvas.create_text(x + 164, y + 24, text="unequal constellations", anchor="w", fill=PALETTE["muted"], font=("Segoe UI", 8))

    def _draw_angles(self, snapshot: dict[str, object], cx: float, cy: float, outer: float, asc_lon: float) -> None:
        for angle in snapshot["angles"]:
            degrees = wheel_degrees(float(angle["longitude"]), asc_lon)
            angle_id = str(angle.get("id", ""))
            if self._is_classic_wheel_theme():
                x0, y0 = _polar(cx, cy, outer * 0.02, degrees)
                x2, y2 = _polar(cx, cy, outer * 0.992, degrees)
                self.canvas.create_line(x0, y0, x2, y2, fill=CLASSIC_AXIS, width=2 if angle_id in {"asc", "dsc", "mc", "ic"} else 1)
                lx, ly = _polar(cx, cy, outer - 7, degrees)
                label_size = 15
                label_outline = "#c78a2b" if angle_id in {"mc", "ic"} else "#3f76b4"
                label_fill = "#5e4a1f" if angle_id in {"mc", "ic"} else "#29598e"
                self.canvas.create_oval(
                    lx - label_size,
                    ly - label_size,
                    lx + label_size,
                    ly + label_size,
                    fill="#fdfbf0",
                    outline=label_outline,
                    width=1,
                )
                self.canvas.create_text(lx, ly, text=ANGLE_GLYPHS.get(angle_id, angle["shortName"]), fill=label_fill, font=("Georgia", 10, "bold"))
            else:
                color = ANGLE_COLORS.get(angle_id, PALETTE["accent_dark"])
                x0, y0 = _polar(cx, cy, outer * 0.245, degrees)
                x1, y1 = _polar(cx, cy, outer * 0.39, degrees)
                x2, y2 = _polar(cx, cy, outer * 0.985, degrees)
                self.canvas.create_line(x0, y0, x2, y2, fill="#ffffff", width=7)
                self.canvas.create_line(x1, y1, x2, y2, fill=color, width=3)
                lx, ly = _polar(cx, cy, outer - 28, degrees)
                label_size = 19 if self.compact_wheel_var.get() else 22
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
                    outline=color,
                    width=2,
                )
                self.canvas.create_text(lx, ly - 1, text=angle["shortName"], fill=color, font=("Segoe UI Semibold", 11 if self.compact_wheel_var.get() else 13))
                constellation = angle.get("constellation", {})
                if isinstance(constellation, dict) and not self.compact_wheel_var.get():
                    self.canvas.create_text(
                        lx,
                        ly + label_size + 8,
                        text=str(constellation.get("abbreviation", "")),
                        fill=PALETTE["muted"],
                        font=("Segoe UI", 7, "bold"),
                    )

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
        classic_theme = self._is_classic_wheel_theme()
        if classic_theme:
            offsets = body_marker_offsets(
                [float(planet["longitude"]) for planet in planets],
                compact=self.compact_wheel_var.get(),
                crowd_threshold=8.5 if self.compact_wheel_var.get() else 10.5,
                angle_step=4.8 if self.compact_wheel_var.get() else 5.8,
                radial_step=5.6 if self.compact_wheel_var.get() else 7.0,
            )
            base_radius = outer * (0.708 if self.compact_wheel_var.get() else 0.720)
            marker_size = 16 if self.compact_wheel_var.get() else 19
        else:
            offsets = planet_marker_offsets([float(planet["longitude"]) for planet in planets], compact=self.compact_wheel_var.get())
            base_radius = outer * (0.665 if self.compact_wheel_var.get() else 0.645)
            marker_size = 12 if self.compact_wheel_var.get() else 15
        for planet, (angle_offset, radial_offset) in zip(planets, offsets):
            anchor_degrees = wheel_degrees(float(planet["longitude"]), asc_lon)
            degrees = anchor_degrees + angle_offset
            if classic_theme:
                anchor_radius = outer * 0.748
                radius = min(outer * 0.755, max(outer * 0.650, base_radius - radial_offset * 0.35))
            else:
                radius = max(outer * 0.53, base_radius - radial_offset)
            x, y = _polar(cx, cy, radius, degrees)
            if not classic_theme:
                fill = PALETTE["planet_fill_angular"] if planet.get("isAngular") else PALETTE["planet_fill"]
                if planet.get("isPresetPoint"):
                    fill = "#f7f0dc"
                outline = PALETTE["accent_dark"] if planet.get("isAngular") else PALETTE["chart_line"]
            planet_tag = f"planet:{planet['id']}"
            focused = self._is_focused_body("planet", str(planet["name"]))
            if classic_theme:
                ax, ay = _polar(cx, cy, anchor_radius, anchor_degrees)
                ix, iy = _polar(cx, cy, outer * 0.735, anchor_degrees)
                self.canvas.create_line(ix, iy, ax, ay, fill=CLASSIC_HOUSE_LINE, width=1, tags=("planet-anchor", planet_tag))
                if abs(angle_offset) > 0.2 or abs(radial_offset) > 0.2:
                    self.canvas.create_line(ax, ay, x, y, fill="#245e75", width=1, tags=("planet-anchor", planet_tag))
                hit_size = marker_size + 8
                self.canvas.create_oval(
                    x - hit_size,
                    y - hit_size,
                    x + hit_size,
                    y + hit_size,
                    fill="",
                    outline="",
                    tags=("planet-marker", planet_tag),
                )
                if focused:
                    self.canvas.create_oval(
                        x - marker_size - 5,
                        y - marker_size - 5,
                        x + marker_size + 5,
                        y + marker_size + 5,
                        outline=PALETTE["warning"],
                        width=2,
                        tags=("planet-marker", planet_tag),
                    )
                marker_color = CLASSIC_PLANET_COLORS.get(str(planet["name"]), PALETTE["top_bar_dark"])
                glyph_size = 30 if self.compact_wheel_var.get() else 34
                self._draw_halo_text(
                    x,
                    y,
                    text=planet_glyph(str(planet["name"])),
                    fill=marker_color,
                    halo=CLASSIC_HOUSE_HALO,
                    font=self._planet_marker_font(glyph_size),
                    tags=("planet-marker", planet_tag),
                )
                degree_text = classic_planet_degree_text(planet)
                radius_distance = math.hypot(x - cx, y - cy) or 1.0
                radial_x = (x - cx) / radius_distance
                radial_y = (y - cy) / radius_distance
                tangent_x = -radial_y
                tangent_y = radial_x
                if degree_text:
                    degree_tangent = 20 if self.compact_wheel_var.get() else 24
                    degree_radial = 11 if self.compact_wheel_var.get() else 14
                    tangent_sign = -1 if x >= cx else 1
                    degree_x = x + tangent_x * degree_tangent * tangent_sign + radial_x * degree_radial
                    degree_y = y + tangent_y * degree_tangent * tangent_sign + radial_y * degree_radial
                    self.canvas.create_text(
                        degree_x,
                        degree_y,
                        text=degree_text,
                        fill=CLASSIC_PLANET_DEGREE,
                        font=("Segoe UI Semibold", 11 if self.compact_wheel_var.get() else 12),
                        tags=("planet-marker", planet_tag),
                    )
                if planet.get("isRetrograde"):
                    retro_tangent = 8 if self.compact_wheel_var.get() else 10
                    retro_radial = 2 if self.compact_wheel_var.get() else 3
                    tangent_sign = 1 if x >= cx else -1
                    retro_x = x + tangent_x * retro_tangent * tangent_sign - radial_x * retro_radial
                    retro_y = y + tangent_y * retro_tangent * tangent_sign - radial_y * retro_radial
                    self.canvas.create_text(
                        retro_x,
                        retro_y,
                        text="R",
                        fill=CLASSIC_PLANET_RETROGRADE,
                        font=("Segoe UI", 7, "bold"),
                        tags=("planet-marker", planet_tag),
                    )
            else:
                focus_outline = PALETTE["warning"] if focused else outline
                self.canvas.create_oval(x - marker_size + 2, y - marker_size + 4, x + marker_size + 2, y + marker_size + 4, fill="#cfd9df", outline="", tags=("planet-marker", planet_tag))
                self.canvas.create_oval(x - marker_size, y - marker_size, x + marker_size, y + marker_size, fill=fill, outline=outline, width=2, tags=("planet-marker", planet_tag))
                self.canvas.create_arc(x - marker_size + 3, y - marker_size + 3, x + marker_size - 3, y + marker_size - 3, start=35, extent=125, outline="#ffffff", width=1, tags=("planet-marker", planet_tag))
                if focused:
                    self.canvas.create_oval(x - marker_size - 4, y - marker_size - 4, x + marker_size + 4, y + marker_size + 4, outline=focus_outline, width=2, tags=("planet-marker", planet_tag))
                self.canvas.create_text(
                    x,
                    y,
                    text=planet_abbreviation(str(planet["name"])),
                    fill=PALETTE["top_bar_dark"],
                    font=self._planet_marker_font(9 if self.compact_wheel_var.get() else 10),
                    tags=("planet-marker", planet_tag),
                )
            planet_id = str(planet["id"])
            self.canvas.tag_bind(planet_tag, "<ButtonPress-1>", lambda event, target_id=planet_id: self._start_moon_drag(event, target_id))
            self.canvas.tag_bind(planet_tag, "<B1-Motion>", self._drag_moon_marker)
            self.canvas.tag_bind(planet_tag, "<ButtonRelease-1>", lambda event, target_id=planet_id: self._release_moon_drag(event, target_id))
            self.canvas.tag_bind(planet_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="fleur"))
            self.canvas.tag_bind(planet_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))

    def _draw_lots(self, snapshot: dict[str, object], cx: float, cy: float, asc_lon: float, outer: float) -> None:
        lots = self._visible_lots(snapshot)
        classic_theme = self._is_classic_wheel_theme()
        offsets = body_marker_offsets([float(lot["longitude"]) for lot in lots], compact=self.compact_wheel_var.get(), crowd_threshold=10.0, angle_step=4.5, radial_step=10.0)
        base_radius = outer * (0.565 if classic_theme else 0.58)
        for lot, (angle_offset, radial_offset) in zip(lots, offsets):
            degrees = wheel_degrees(float(lot["longitude"]), asc_lon) + angle_offset
            radius = min(outer * (0.635 if classic_theme else 0.76), max(outer * 0.48, base_radius + radial_offset * (0.35 if classic_theme else 0.7)))
            x, y = _polar(cx, cy, radius, degrees)
            lot_tag = f"lot:{lot['id']}"
            focused = self._is_focused_body("lot", str(lot["name"]))
            if classic_theme:
                size = 6 if not focused else 9
                self.canvas.create_polygon(
                    x,
                    y - size,
                    x + size,
                    y,
                    x,
                    y + size,
                    x - size,
                    y,
                    fill="#f5efd6",
                    outline=PALETTE["warning"] if focused else "#6f6040",
                    width=2 if focused else 1,
                    tags=("lot-marker", lot_tag),
                )
                if focused:
                    self.canvas.create_text(
                        x + 13,
                        y,
                        text=lot_abbreviation(str(lot["name"])),
                        fill=CLASSIC_HOUSE_TEXT,
                        font=("Segoe UI Semibold", 8),
                        anchor="w",
                        tags=("lot-marker", lot_tag),
                    )
                self.canvas.tag_bind(lot_tag, "<Button-1>", lambda _event, lot_id=str(lot["id"]): self._select_lot_by_id(lot_id))
                self.canvas.tag_bind(lot_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
                self.canvas.tag_bind(lot_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))
                continue
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
        classic_theme = self._is_classic_wheel_theme()
        offsets = body_marker_offsets([float(node["longitude"]) for node in nodes], compact=self.compact_wheel_var.get(), crowd_threshold=9.0, angle_step=4.0, radial_step=9.0)
        base_radius = outer * (0.62 if classic_theme else 0.42)
        for node, (angle_offset, radial_offset) in zip(nodes, offsets):
            degrees = wheel_degrees(float(node["longitude"]), asc_lon) + angle_offset
            radius = max(outer * (0.56 if classic_theme else 0.34), base_radius - radial_offset * (0.35 if classic_theme else 0.8))
            x, y = _polar(cx, cy, radius, degrees)
            node_tag = f"node:{node['id']}"
            focused = self._is_focused_body("node", str(node["name"]))
            if classic_theme:
                self.canvas.create_text(
                    x,
                    y,
                    text="☊" if "North" in str(node.get("name")) else "☋",
                    fill=PALETTE["warning"] if focused else "#26335f",
                    font=("Segoe UI Symbol", 13 if focused else 11, "bold"),
                    tags=("node-marker", node_tag),
                )
                if focused:
                    self.canvas.create_oval(x - 12, y - 12, x + 12, y + 12, outline=PALETTE["warning"], width=1, tags=("node-marker", node_tag))
                self.canvas.tag_bind(node_tag, "<Button-1>", lambda _event, node_id=str(node["id"]): self._select_node_by_id(node_id))
                self.canvas.tag_bind(node_tag, "<Enter>", lambda _event: self.canvas.configure(cursor="hand2"))
                self.canvas.tag_bind(node_tag, "<Leave>", lambda _event: self.canvas.configure(cursor=""))
                continue
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
            line_width = 2.8 if aspect.get("isApplying") else 2.0
            self.canvas.create_line(
                *aspect_curve_points(cx, cy, radius, angle_a, angle_b, compact=self.compact_wheel_var.get(), lane_index=lane_index),
                fill=color,
                width=line_width,
                dash=() if aspect.get("isApplying") else (5, 4),
                smooth=True,
            )
