from __future__ import annotations

from datetime import datetime
import inspect
import math
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import zlib
from backend.electional.desktop import (
    DETAIL_PAGE_TABS,
    ElectionalDesktopApp,
    LEFT_GUIDED_COLLAPSED_SECTIONS,
    PAGE_MODE_LABELS,
    RIBBON_COLUMNS,
    RIBBON_GROUPS,
    TOP_NAV_ITEMS,
    VIEW_PAGE_QUICK_ACTIONS,
    VIEW_PAGE_TARGETS,
    VIEW_PAGE_STRIP_ACTIONS,
    WHEEL_CANVAS_DEFAULT_HEIGHT,
    WHEEL_CANVAS_DEFAULT_WIDTH,
    WHEEL_VIEW_PRESET_LABELS,
    _polar,
    aspect_curve_points,
    build_manual_validation_comparison,
    button_health_lines,
    candidate_board_summary,
    candidate_metric_badges,
    classic_dignity_table_text,
    classic_planet_degree_text,
    compact_aspect_headline,
    constellation_arc_segments,
    analysis_metric_cards,
    analysis_notice_lines,
    displayed_chart_state_line,
    body_marker_offsets,
    fixed_star_contact_count,
    format_manual_validation_comparison,
    guided_workflow_rows,
    guided_workflow_status_counts,
    guided_workbench_summary,
    house_geometry_lines,
    house_geometry_insight_lines,
    house_geometry_summary,
    house_label_screen_angle,
    house_span_label,
    house_span_rows,
    left_status_chip_lines,
    location_intelligence_lines,
    left_section_initially_collapsed,
    live_sky_body_rows,
    live_sky_timestamp_line,
    midpoint_contact_rows,
    midpoint_page_lines,
    midpoint_pair_rows,
    timeline_item_display,
    timeline_visual_rows,
    compact_time_label,
    compact_judgment_lines,
    compact_place_name,
    tools_ribbon_label,
    tools_ribbon_status,
    top_nav_button_metrics,
    location_summary,
    location_coordinate_summary,
    manual_validation_result_summary,
    parse_manual_validation_values,
    planet_abbreviation,
    planet_glyph,
    planet_marker_offsets,
    retrograde_motion_rows,
    retrograde_page_lines,
    star_abbreviation,
    sign_glyph,
    score_band_label,
    search_workbench_compact_lines,
    selection_offset_label,
    shift_local_datetime,
    shift_local_datetime_minutes,
    summary_chip_lines,
    uses_classic_wheel_theme,
    wheel_degrees,
    wheel_degrees_from_xy,
    window_score_color,
    workspace_hub_cards,
    workflow_next_step_lines,
    validation_workbench_lines,
    validation_quick_read_lines,
    tk_scaling_for_dpi,
    wheel_export_postscript_options,
    wheel_export_scale_label,
    wheel_export_scale_value,
    wheel_overlay_summary,
    wheel_preset_help_text,
)
from backend.electional.capricorn_assets import (
    classify_capricorn_asset,
    format_capricorn_asset_audit,
    import_capricorn_aspect_profiles,
    inventory_capricorn_assets,
    parse_capricorn_aspect_config,
)
from backend.electional.chart import build_snapshot
from backend.electional.locations import (
    DEFAULT_TIMEZONE,
    LocationPreset,
    build_custom_location,
    combined_visible_location_names,
    combined_location_names,
    default_location_for_timezone,
    home_location_for_app,
    get_location,
    load_hidden_builtin_location_ids,
    load_home_location_name,
    load_recent_locations,
    load_user_locations,
    remember_recent_location,
    reset_location_defaults,
    save_hidden_builtin_location_ids,
    save_home_location_name,
    save_recent_locations,
    save_user_locations,
    upsert_user_location,
)
from backend.electional.location_search import (
    expected_timezone_for_coordinates,
    location_search_result_label,
    search_city_locations,
    timezone_warning_for_location,
)
from backend.electional.presets import get_preset
from backend.electional.references import dignity_table_lines, lot_reference_lines, system_reference_lines
from backend.electional.reporting import (
    advisor_lines,
    angle_testimony_lines,
    build_classical_point_data_page,
    build_comparison_export_text,
    build_decision_brief_page,
    build_diagnostics_page,
    build_medieval_data_page,
    build_report_text,
    build_transit_search_page,
    build_window_comparison_page,
    condition_lines,
    constellation_lines,
    election_flag_lines,
    format_aspectarian,
    format_aspect_highlight_dashboard,
    format_aspect_summary,
    format_dignity_summary,
    format_fixed_star_contact,
    format_lunar_phase,
    format_motion_summary,
    format_planet_focus,
    format_score_breakdown,
    format_window_label,
    factor_explorer_lines,
    improvement_guide_lines,
    judgment_context_lines,
    rule_lines,
    score_accounting_lines,
    score_diagnostic_lines,
    score_evaluation_lines,
    strongest_aspect_analysis_lines,
)
from backend.electional.scoring import score_breakdown
from backend.electional.search import (
    SEARCH_PRESET_NAMES,
    SEARCH_QUALITY_MODE_NAMES,
    build_search_config_from_text,
    candidate_refinement_offsets,
    candidate_explanation_lines,
    fails_objective_antipattern,
    format_search_summary,
    has_angular_benefic,
    has_angular_malefic,
    has_applying_support,
    has_major_stress,
    moon_is_non_void,
    rejection_reasons,
    rejection_summary,
    rank_search_windows,
    search_preset_values,
    split_ranked_windows,
)
from backend.electional.screening import solar_elongation_summary
from backend.electional.session import clean_session_state, load_session_state, save_session_state
from backend.electional.shortlist import (
    SHORTLIST_TAG_CHOICES,
    add_shortlist_entry,
    add_shortlist_tag,
    build_shortlist_compare_text,
    build_shortlist_entry,
    format_shortlist_batch_diagnostics,
    format_shortlist_entries,
    normalize_shortlist_tags,
    remove_shortlist_tag,
    shortlist_batch_diagnostics,
    shortlist_entry_by_id,
    update_shortlist_tags,
)
from backend.electional.validation import validate_election_inputs, validate_search_inputs


class DesktopUiHelpersTest(unittest.TestCase):
    def test_desktop_subsystems_live_in_focused_modules(self) -> None:
        self.assertEqual(ElectionalDesktopApp._build_top_bars.__module__, "backend.electional.desktop_navigation")
        self.assertEqual(ElectionalDesktopApp._show_aspect_config_dialog.__module__, "backend.electional.desktop_actions")
        self.assertEqual(ElectionalDesktopApp._build_chart_panel.__module__, "backend.electional.desktop_workspace")
        self.assertEqual(ElectionalDesktopApp._render_text_panels.__module__, "backend.electional.desktop_pages")
        self.assertEqual(ElectionalDesktopApp._build_left_controls.__module__, "backend.electional.desktop_left_rail")
        self.assertEqual(ElectionalDesktopApp._build_right_panel.__module__, "backend.electional.desktop_right_panel")
        self.assertEqual(ElectionalDesktopApp._draw_wheel.__module__, "backend.electional.desktop_wheel")

    def test_top_navigation_uses_current_workspace_labels(self) -> None:
        self.assertEqual(TOP_NAV_ITEMS, ("Guide", "Wheel", "Search", "Analysis", "Timeline", "Validation", "Reports"))
        self.assertNotIn("Selected Chart", TOP_NAV_ITEMS)
        self.assertNotIn("Configuration", TOP_NAV_ITEMS)
        self.assertNotIn("Astro Mapping", TOP_NAV_ITEMS)
        self.assertNotIn("Settings", TOP_NAV_ITEMS)

    def test_open_detail_page_resolves_ribbon_targets_with_feedback(self) -> None:
        class FakeVar:
            def __init__(self) -> None:
                self.value = ""

            def set(self, value: str) -> None:
                self.value = value

        app = object.__new__(ElectionalDesktopApp)
        opened_targets: list[str] = []
        app._focus_detail_page = lambda target: opened_targets.append(target) or True
        app.status_var = FakeVar()
        app.workspace_page_summary_var = FakeVar()

        self.assertTrue(app._open_detail_page("Factors"))
        self.assertEqual(opened_targets, ["Factor Explorer"])
        self.assertIn("Factor Explorer", app.status_var.value)
        self.assertIn("Factor Explorer", app.workspace_page_summary_var.value)

    def test_wheel_option_overlay_controls_use_overlay_row(self) -> None:
        source = inspect.getsource(ElectionalDesktopApp._build_wheel_display_controls)

        self.assertIn("overlay_row", source)
        self.assertNotIn("option_row", source)

    def test_guided_workflow_rows_track_main_election_path(self) -> None:
        rows = guided_workflow_rows(
            objective="Launch or publish",
            location_name="Indio, California",
            date_text="2026-06-08",
            time_text="18:24",
            scan_hours="12",
            step_minutes="15",
            has_chart=True,
            candidate_count=3,
            shortlisted_count=0,
            selected_index=-1,
            displayed_source="input chart",
        )
        by_id = {row["id"]: row for row in rows}

        self.assertEqual(by_id["objective"]["status"], "done")
        self.assertEqual(by_id["location"]["status"], "done")
        self.assertEqual(by_id["range"]["status"], "done")
        self.assertEqual(by_id["times"]["status"], "done")
        self.assertEqual(by_id["search"]["status"], "done")
        self.assertEqual(by_id["compare"]["status"], "active")
        self.assertEqual(by_id["export"]["status"], "pending")
        self.assertIn("Indio", by_id["location"]["value"])
        self.assertEqual(guided_workflow_status_counts(rows), {"done": 5, "active": 1, "pending": 1})

    def test_guided_workflow_export_waits_for_real_pick_or_shortlist(self) -> None:
        waiting_rows = guided_workflow_rows(
            objective="Launch",
            location_name="Indio",
            date_text="2026-06-08",
            time_text="18:24",
            scan_hours="12",
            step_minutes="15",
            has_chart=True,
            candidate_count=0,
            shortlisted_count=0,
            selected_index=0,
            displayed_source="input chart",
        )
        ready_rows = guided_workflow_rows(
            objective="Launch",
            location_name="Indio",
            date_text="2026-06-08",
            time_text="18:24",
            scan_hours="12",
            step_minutes="15",
            has_chart=True,
            candidate_count=3,
            shortlisted_count=2,
            selected_index=0,
            displayed_source="selected candidate",
        )

        self.assertEqual({row["id"]: row for row in waiting_rows}["export"]["status"], "pending")
        ready_by_id = {row["id"]: row for row in ready_rows}
        self.assertEqual(ready_by_id["compare"]["status"], "done")
        self.assertEqual(ready_by_id["export"]["status"], "active")

    def test_guided_workbench_summary_names_next_active_step(self) -> None:
        rows = guided_workflow_rows(
            objective="Launch",
            location_name="Indio",
            date_text="2026-06-08",
            time_text="18:24",
            scan_hours="12",
            step_minutes="15",
            has_chart=True,
            candidate_count=0,
            shortlisted_count=0,
            selected_index=-1,
            displayed_source="input chart",
        )

        headline, detail = guided_workbench_summary(rows)

        self.assertIn("steps ready", headline)
        self.assertIn("Find", detail)
        self.assertIn("Find best", detail)

    def test_location_intelligence_lines_compact_home_recent_and_timezone(self) -> None:
        lines = location_intelligence_lines(
            location_name="Rancho Mirage, CA",
            timezone_name="America/Los_Angeles",
            latitude="33.7397",
            longitude="-116.4128",
            home_location_name="Indio, California",
            recent_locations=[
                LocationPreset("recent-indio", "Indio, CA", 33.7206, -116.2156, "America/Los_Angeles"),
                LocationPreset("recent-paris", "Paris, France", 48.8566, 2.3522, "Europe/Paris"),
            ],
            saved_count=2,
            timezone_warning="Timezone OK: America/Los_Angeles matches the selected place.",
        )

        self.assertIn("Rancho Mirage", lines[0])
        self.assertIn("33.740", lines[1])
        self.assertIn("Home: Indio", lines[1])
        self.assertIn("Saved: 2", lines[2])
        self.assertIn("Recent: Indio", lines[2])
        self.assertIn("Timezone OK", lines[2])

    def test_ribbon_groups_keep_primary_actions_visible(self) -> None:
        labels = [label for _group, items in RIBBON_GROUPS for label in items]

        for expected in (
            "Show Current",
            "Find Best",
            "Transits/Timeline",
            "Electional Search",
            "Void Course",
            "Heliacal Search",
            "Out of Bounds",
            "Aspect Config",
            "Assets",
            "Search Page",
            "Day Report",
            "Report",
            "Map",
        ):
            self.assertIn(expected, labels)
        self.assertIn("Aspects", labels)
        self.assertIn("Aspect Strength", labels)
        self.assertNotIn("Export Wheel", labels)
        self.assertNotIn("Button Health", labels)
        self.assertLessEqual(len(labels), 25)
        self.assertNotIn("Transits", labels)
        self.assertLessEqual(RIBBON_COLUMNS, 3)

    def test_tools_ribbon_toggle_labels_explain_visibility(self) -> None:
        self.assertEqual(tools_ribbon_label(False), "Show Tools")
        self.assertEqual(tools_ribbon_label(True), "Hide Tools")
        self.assertIn("hidden", tools_ribbon_status(False))
        self.assertIn("visible", tools_ribbon_status(True))

    def test_guided_left_sections_default_advanced_controls_collapsed(self) -> None:
        self.assertIn("Search Strategy", LEFT_GUIDED_COLLAPSED_SECTIONS)
        self.assertIn("Safety Filters", LEFT_GUIDED_COLLAPSED_SECTIONS)
        self.assertTrue(left_section_initially_collapsed("Search Strategy"))
        self.assertTrue(left_section_initially_collapsed("Aspect Focus"))
        self.assertFalse(left_section_initially_collapsed("Timing"))
        self.assertFalse(left_section_initially_collapsed("Actions"))

    def test_top_navigation_uses_readable_button_metrics(self) -> None:
        metrics = top_nav_button_metrics()

        self.assertGreaterEqual(metrics["padx"], 12)
        self.assertGreaterEqual(metrics["pady"], 4)
        self.assertGreaterEqual(metrics["font_size"], 10)

    def test_capricorn_asset_inventory_classifies_safe_import_targets(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Aspect Configurations").mkdir()
            (root / "Backgrounds").mkdir()
            (root / "Aspect Configurations" / "Major.asp_conf").write_bytes(b"config")
            (root / "Backgrounds" / "background.bmp").write_bytes(b"bitmap")
            (root / "manifest").write_text("manifest", encoding="utf-8")

            inventory = inventory_capricorn_assets(root)
            audit = format_capricorn_asset_audit(inventory)

        self.assertEqual(classify_capricorn_asset(Path("Major.asp_conf")), "importable-config")
        self.assertEqual(classify_capricorn_asset(Path("background.bmp")), "reference-only")
        self.assertTrue(inventory.exists)
        self.assertEqual(inventory.importable_config_count, 1)
        self.assertEqual(inventory.reference_only_count, 2)
        self.assertIn("Safe import policy", audit)
        self.assertIn("Aspect Configurations", audit)

    def test_capricorn_aspect_import_converts_binary_config_facts(self) -> None:
        def int_field(field_id: int, value: int) -> bytes:
            return bytes((0x02, 0x00, field_id, 0x00)) + b"\x00\x00\x00\x00" + struct.pack("<i", value)

        def double_field(field_id: int, degrees: float) -> bytes:
            return bytes((0x01, 0x00, field_id, 0x00)) + b"\x00\x00\x00\x00" + struct.pack("<d", math.radians(degrees))

        def string_field(field_id: int, text: str) -> bytes:
            return bytes((0x04, 0x00, field_id, 0x00)) + b"\x00\x00\x00\x00" + text.encode("utf-16le") + b"\x00\x00"

        def record(name: str, abbr: str, active: int, nature: int, angle: float, orb: float) -> bytes:
            before_name = int_field(0x23, active) + int_field(0x24, 1) + string_field(0x03, name)[:8]
            return (
                b"\x00" * (96 - len(before_name))
                + before_name
                + name.encode("utf-16le")
                + b"\x00\x00"
                + string_field(0x25, abbr)
                + int_field(0x26, nature)
                + double_field(0x27, angle)
                + double_field(0x2B, orb)
                + b"\x00" * 96
            )

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            aspect_dir = root / "Aspect Configurations"
            aspect_dir.mkdir()
            path = aspect_dir / "Tiny.asp_conf"
            payload = b"\x00" * 2500 + record("Conjunction", "Cnj", 1, 0, 0, 10) + record("Semisquare", "Sem", 0, 2, 45, 3)
            path.write_bytes(b"A\x00A\x00" + zlib.compress(payload))
            profile = parse_capricorn_aspect_config(path)
            result = import_capricorn_aspect_profiles(root, profile_path=root / "profiles.json")

        by_id = {aspect.id: aspect for aspect in profile.aspects}
        self.assertEqual(profile.name, "Capricorn Tiny")
        self.assertTrue(by_id["conjunction"].enabled)
        self.assertFalse(by_id["semisquare"].enabled)
        self.assertEqual(by_id["semisquare"].tone, "stress")
        self.assertAlmostEqual(by_id["semisquare"].angle, 45.0)
        self.assertAlmostEqual(by_id["conjunction"].default_orb, 10.0)
        self.assertEqual(result.imported_profiles, 1)

    def test_button_health_reports_visible_button_wiring(self) -> None:
        text = "\n".join(button_health_lines(DETAIL_PAGE_TABS))

        self.assertIn("Button Health", text)
        self.assertIn("All visible top, ribbon, and page-strip buttons have wired actions", text)
        self.assertIn("Validation", TOP_NAV_ITEMS)
        self.assertIn("Angles", VIEW_PAGE_TARGETS)
        self.assertIn("Aspect Strength", VIEW_PAGE_TARGETS)
        self.assertIn("Validation", VIEW_PAGE_TARGETS)
        self.assertIn("Reports", VIEW_PAGE_TARGETS)
        self.assertIn("Retrogrades", VIEW_PAGE_TARGETS)
        self.assertIn("Midpoints", VIEW_PAGE_TARGETS)
        self.assertIn("Live Sky", VIEW_PAGE_TARGETS)
        self.assertEqual(PAGE_MODE_LABELS["guide"], "Guide")
        self.assertEqual(PAGE_MODE_LABELS["retrogrades"], "Retrogrades")
        self.assertEqual(PAGE_MODE_LABELS["midpoints"], "Midpoints")
        self.assertEqual(PAGE_MODE_LABELS["live-sky"], "Live Sky")
        self.assertIn("Save Wheel", VIEW_PAGE_STRIP_ACTIONS)

    def test_view_page_quick_actions_stay_compact(self) -> None:
        self.assertLessEqual(len(VIEW_PAGE_QUICK_ACTIONS), 5)
        for label in VIEW_PAGE_QUICK_ACTIONS:
            self.assertIn(label, VIEW_PAGE_STRIP_ACTIONS)
        self.assertIn("Live Sky", VIEW_PAGE_QUICK_ACTIONS)

    def test_report_buttons_have_desktop_handlers(self) -> None:
        self.assertTrue(hasattr(ElectionalDesktopApp, "_show_current_report_dialog"))
        self.assertTrue(hasattr(ElectionalDesktopApp, "_show_daily_aspect_report_dialog"))
        self.assertTrue(hasattr(ElectionalDesktopApp, "_astrolabe_button"))

    def test_planet_abbreviation_uses_compact_labels(self) -> None:
        self.assertEqual(planet_abbreviation("Mercury"), "Me")
        self.assertEqual(planet_abbreviation("Pluto"), "Pl")
        self.assertEqual(star_abbreviation("Galactic Center"), "GC")

    def test_classic_glyph_helpers_and_theme_flag_support_reference_mode(self) -> None:
        self.assertEqual(planet_glyph("Sun"), "\u2609")
        self.assertEqual(sign_glyph("Sc"), "\u264f")
        self.assertEqual(planet_glyph("Unknown"), "Un")
        self.assertTrue(uses_classic_wheel_theme("Classic Natal"))
        self.assertFalse(uses_classic_wheel_theme("Astrolabe"))
        self.assertEqual(classic_planet_degree_text({"zodiac": {"degree": 14, "minute": 7}}), "14\u00b007")
        self.assertEqual(classic_planet_degree_text({}), "")
        self.assertEqual(classic_dignity_table_text({"dignity": {"label": "Unavailable"}}), "n/a")
        self.assertEqual(classic_dignity_table_text({"dignity": {"label": "Detriment"}}), "Detr.")
        self.assertEqual(classic_dignity_table_text({"dignity": {"label": "Rulership"}}), "Rulersh")
        self.assertEqual(WHEEL_VIEW_PRESET_LABELS["full-classic"], "Full Classic")

    def test_wheel_preset_help_and_overlay_summary_explain_display_state(self) -> None:
        self.assertIn("Clean reading", wheel_preset_help_text("clean"))
        self.assertIn("reference-style", wheel_preset_help_text("Full Classic"))
        self.assertIn("Diagnostic", wheel_preset_help_text("diagnostic"))
        self.assertEqual(
            wheel_overlay_summary(
                aspects=False,
                lots=False,
                nodes=False,
                fixed_stars=False,
                score=False,
                compact=False,
            ),
            "Overlays: none",
        )
        summary = wheel_overlay_summary(
            aspects=True,
            lots=True,
            nodes=False,
            fixed_stars=True,
            score=False,
            compact=True,
        )

        self.assertIn("aspects", summary)
        self.assertIn("lots", summary)
        self.assertIn("stars", summary)
        self.assertIn("compact labels", summary)
        self.assertNotIn("nodes", summary)

    def test_wheel_quality_helpers_separate_dpi_from_export_size(self) -> None:
        self.assertAlmostEqual(tk_scaling_for_dpi(96), 1.3333333333333333)
        self.assertAlmostEqual(tk_scaling_for_dpi(144), 2.0)
        self.assertEqual(tk_scaling_for_dpi("bad"), 96 / 72)
        self.assertEqual(wheel_export_scale_value("4x export"), 4.0)
        self.assertEqual(wheel_export_scale_value("0.5x export"), 1.0)
        self.assertEqual(wheel_export_scale_value("9x export"), 4.0)
        self.assertEqual(wheel_export_scale_label(3), "3x export")
        self.assertEqual(wheel_export_scale_label(2.5), "2.5x export")

    def test_wheel_export_postscript_options_scale_saved_art(self) -> None:
        options = wheel_export_postscript_options(900, 660, 3)

        self.assertEqual(options["width"], 900)
        self.assertEqual(options["height"], 660)
        self.assertEqual(options["pagewidth"], "2700p")
        self.assertEqual(options["pageheight"], "1980p")

    def test_manual_validation_parses_and_compares_reference_values(self) -> None:
        snapshot = {
            "zodiacSystem": type("Zodiac", (), {"id": "sidereal-lahiri", "name": "Sidereal Lahiri"})(),
            "houseSystem": type("House", (), {"name": "Topocentric"})(),
            "ayanamsha": 24.0,
            "engine": "Astronomy Engine",
            "positions": [
                {"name": "Sun", "longitude": 52.1334},
                {"name": "Moon", "longitude": 144.75},
            ],
            "angles": [{"id": "asc", "shortName": "ASC", "longitude": 120.0}],
            "houseCusps": [{"house": 1, "longitude": 120.0}],
            "accuracyAudit": {
                "label": "Swiss verified",
                "summary": "Swiss integration verified.",
                "maxPositionDeltaDegrees": 0.0,
                "maxAngleDeltaDegrees": 0.0,
                "maxHouseDeltaDegrees": 0.0,
            },
        }

        parsed = parse_manual_validation_values("Sun Taurus 22deg08\nASC Leo 00 00", zodiac_system_id="sidereal-lahiri")
        result = build_manual_validation_comparison(snapshot, "Sun Taurus 22deg08\nASC Leo 00 00", source="CapricornPROMETHEUS")
        lines = "\n".join(validation_workbench_lines(snapshot, None, result))
        quick_read = "\n".join(validation_quick_read_lines(snapshot, None, result))
        summary = manual_validation_result_summary(result)

        self.assertEqual(len([row for row in parsed if row.get("status") == "parsed"]), 2)
        self.assertEqual(result["status"], "Pass")
        self.assertEqual(summary["matchedCount"], 2)
        self.assertIn("Manual comparison passed", quick_read)
        self.assertIn("CapricornPROMETHEUS", lines)
        self.assertIn("Max delta", lines)

    def test_manual_validation_summary_counts_review_missing_and_unparsed_rows(self) -> None:
        snapshot = {
            "zodiacSystem": type("Zodiac", (), {"id": "sidereal-lahiri", "name": "Sidereal Lahiri"})(),
            "houseSystem": type("House", (), {"name": "Topocentric"})(),
            "ayanamsha": 24.0,
            "engine": "Astronomy Engine",
            "positions": [{"name": "Sun", "longitude": 52.1334}],
            "angles": [],
            "houseCusps": [],
            "accuracyAudit": {
                "label": "Swiss verified",
                "summary": "Swiss integration verified.",
                "maxPositionDeltaDegrees": 0.0,
                "maxAngleDeltaDegrees": 0.0,
                "maxHouseDeltaDegrees": 0.0,
            },
        }

        result = build_manual_validation_comparison(
            snapshot,
            "Sun Taurus 23deg08\nASC Leo 00 00\nnot a chart row",
            source="CapricornPROMETHEUS",
        )
        summary = manual_validation_result_summary(result)
        formatted = "\n".join(format_manual_validation_comparison(result))
        quick_read = "\n".join(validation_quick_read_lines(snapshot, None, result))

        self.assertEqual(result["status"], "Review")
        self.assertEqual(summary["reviewCount"], 1)
        self.assertEqual(summary["missingCount"], 1)
        self.assertEqual(summary["unparsedCount"], 1)
        self.assertIn("Rows: 0 match, 1 review, 1 missing, 1 unparsed", formatted)
        self.assertIn("Likely causes", formatted)
        self.assertIn("Review 2 row", quick_read)

    def test_manual_validation_uses_true_13_sign_constellation_starts(self) -> None:
        parsed = parse_manual_validation_values("Sun Tau 22 00", zodiac_system_id="true-13-sign")

        self.assertAlmostEqual(float(parsed[0]["referenceLongitude"]), 76.0)

    def test_wheel_degrees_places_ascendant_on_left_side(self) -> None:
        self.assertEqual(wheel_degrees(110.0, 110.0), 180)
        self.assertEqual(wheel_degrees(290.0, 110.0), 0)
        self.assertEqual(wheel_degrees_from_xy(100.0, 100.0, 200.0, 100.0), 0)
        self.assertEqual(wheel_degrees_from_xy(100.0, 100.0, 100.0, 0.0), 90)
        self.assertEqual(wheel_degrees_from_xy(100.0, 100.0, 0.0, 100.0), 180)
        self.assertEqual(wheel_degrees(20.0, 110.0), 90)
        self.assertEqual(wheel_degrees(200.0, 110.0), 270)

    def test_house_label_screen_angle_follows_rendered_sector_midpoint(self) -> None:
        self.assertEqual(house_label_screen_angle(90.0, 120.0, 90.0), 195.0)
        self.assertEqual(house_label_screen_angle(270.0, 300.0, 90.0), 15.0)
        self.assertEqual(house_label_screen_angle(330.0, 0.0, 90.0), 75.0)

    def test_house_geometry_summary_exposes_unequal_house_spans(self) -> None:
        snapshot = {
            "houseSystem": type("House", (), {"name": "Topocentric"})(),
            "houseCusps": [
                {"house": 1, "longitude": 10.0, "source": "Swiss Ephemeris"},
                {"house": 2, "longitude": 35.0, "source": "Swiss Ephemeris"},
                {"house": 3, "longitude": 70.0, "source": "Swiss Ephemeris"},
                {"house": 4, "longitude": 100.0, "source": "Swiss Ephemeris"},
                {"house": 5, "longitude": 130.0, "source": "Swiss Ephemeris"},
                {"house": 6, "longitude": 160.0, "source": "Swiss Ephemeris"},
                {"house": 7, "longitude": 190.0, "source": "Swiss Ephemeris"},
                {"house": 8, "longitude": 215.0, "source": "Swiss Ephemeris"},
                {"house": 9, "longitude": 250.0, "source": "Swiss Ephemeris"},
                {"house": 10, "longitude": 280.0, "source": "Swiss Ephemeris"},
                {"house": 11, "longitude": 310.0, "source": "Swiss Ephemeris"},
                {"house": 12, "longitude": 340.0, "source": "Swiss Ephemeris"},
            ],
        }

        rows = house_span_rows(snapshot)
        summary = house_geometry_summary(snapshot)
        lines = "\n".join(house_geometry_lines(snapshot))
        insight = "\n".join(house_geometry_insight_lines(snapshot))

        self.assertEqual(rows[0]["span"], 25.0)
        self.assertIn("Topocentric", summary)
        self.assertIn("unequal quadrant/accounted houses", summary)
        self.assertIn("Swiss Ephemeris", summary)
        self.assertIn("H01", lines)
        self.assertIn("25.00 deg", lines)
        self.assertIn("Widest", insight)
        self.assertIn("Narrowest", insight)
        self.assertIn("project the local sky onto the ecliptic", insight)
        self.assertEqual(house_span_label(rows[0]["span"]), "25.0deg")
        self.assertEqual(house_span_label(None), "")

    def test_retrograde_page_lines_surface_motion_status(self) -> None:
        snapshot = {
            "formattedTime": "Sat, Jun 6, 1:09 PM PDT",
            "positions": [
                {
                    "name": "Mercury",
                    "longitude": 70.0,
                    "zodiac": {"sign": "Ge", "degree": 10, "minute": 0},
                    "house": 3,
                    "isRetrograde": True,
                    "motion": {"label": "Retrograde", "dailyLongitudeChange": -0.72},
                },
                {
                    "name": "Saturn",
                    "longitude": 350.0,
                    "zodiac": {"sign": "Pi", "degree": 20, "minute": 0},
                    "house": 7,
                    "motion": {
                        "label": "Direct",
                        "dailyLongitudeChange": 0.01,
                        "station": {"isInStationWindow": True, "phase": "station direct"},
                    },
                },
                {
                    "name": "Venus",
                    "longitude": 90.0,
                    "zodiac": {"sign": "Ca", "degree": 0, "minute": 0},
                    "house": 4,
                    "motion": {"label": "Direct", "dailyLongitudeChange": 1.12},
                },
            ],
        }

        rows = retrograde_motion_rows(snapshot)
        text = "\n".join(retrograde_page_lines(snapshot))

        self.assertEqual(rows[0]["status"], "Retrograde")
        self.assertEqual(rows[1]["status"], "Station Direct")
        self.assertEqual(rows[2]["status"], "Direct")
        self.assertIn("Mercury", text)
        self.assertIn("Retrograde", text)
        self.assertIn("Station Direct", text)
        self.assertIn("-0.720 deg/day", text)

    def test_midpoint_page_lines_surface_exact_midpoint_contacts(self) -> None:
        snapshot = {
            "formattedTime": "Sat, Jun 6, 1:09 PM PDT",
            "positions": [
                {"name": "Sun", "longitude": 10.0},
                {"name": "Moon", "longitude": 110.0},
                {"name": "Mars", "longitude": 60.0},
                {"name": "Venus", "longitude": 240.75},
            ],
        }

        contacts = midpoint_contact_rows(snapshot, orb=0.2)
        pairs = midpoint_pair_rows(snapshot)
        text = "\n".join(midpoint_page_lines(snapshot))

        self.assertEqual(contacts[0]["body"], "Mars")
        self.assertEqual(contacts[0]["pair"], "Sun/Moon")
        self.assertAlmostEqual(float(contacts[0]["orb"]), 0.0)
        self.assertIn("Sun/Moon", [row["pair"] for row in pairs])
        self.assertIn("Mars = \u2609/\u263d Sun/Moon", text)
        self.assertIn("060.00 deg", text)

    def test_live_sky_rows_add_earth_and_timestamp_mode(self) -> None:
        location = LocationPreset("indio", "Indio, CA", 33.7206, -116.2156, "America/Los_Angeles")
        snapshot = {
            "formattedTime": "Tue, Jun 9, 8:55 AM PDT",
            "positions": [
                {
                    "name": "Sun",
                    "longitude": 70.0,
                    "tropicalLongitude": 80.0,
                    "zodiac": {"sign": "Gemini", "degree": 10, "minute": 0},
                },
                {
                    "name": "Mars",
                    "longitude": 10.0,
                    "tropicalLongitude": 20.0,
                    "distanceAu": 1.6,
                    "zodiac": {"sign": "Aries", "degree": 20, "minute": 0},
                },
            ],
        }

        rows = live_sky_body_rows(snapshot)
        by_name = {row["name"]: row for row in rows}

        self.assertEqual(by_name["Earth"]["longitude"], 260.0)
        self.assertEqual(by_name["Mars"]["radiusFactor"], 0.46)
        self.assertIn("Manual", live_sky_timestamp_line(snapshot, location, "manual"))
        self.assertIn("Live", live_sky_timestamp_line(snapshot, location, "live"))

    def test_real_chart_angles_render_in_expected_quadrants(self) -> None:
        snapshot = build_snapshot("2026-05-26", "09:00", get_location("los-angeles"), "traditional-lilly")
        ascendant = next(angle for angle in snapshot["angles"] if angle["id"] == "asc")
        asc_lon = float(ascendant["longitude"])
        screen_points = {
            angle["id"]: _polar(0.0, 0.0, 100.0, wheel_degrees(float(angle["longitude"]), asc_lon))
            for angle in snapshot["angles"]
        }

        self.assertLess(screen_points["asc"][0], 0)
        self.assertGreater(screen_points["dsc"][0], 0)
        self.assertLess(screen_points["mc"][1], 0)
        self.assertGreater(screen_points["ic"][1], 0)

    def test_constellation_arc_segments_keep_unequal_ecliptic_spans(self) -> None:
        segments = {str(segment["id"]): segment for segment in constellation_arc_segments()}

        self.assertEqual(len(segments), 13)
        self.assertAlmostEqual(float(segments["virgo"]["extent"]), 44.0)
        self.assertAlmostEqual(float(segments["scorpius"]["extent"]), 6.0)
        self.assertAlmostEqual(float(segments["ophiuchus"]["extent"]), 18.0)
        self.assertNotEqual(float(segments["virgo"]["extent"]), 30.0)

    def test_planet_marker_offsets_spread_close_cluster_symmetrically(self) -> None:
        offsets = planet_marker_offsets([10.0, 13.0, 16.0], compact=False)

        self.assertLess(offsets[0][0], offsets[1][0])
        self.assertLess(offsets[1][0], offsets[2][0])
        self.assertGreater(offsets[0][1], offsets[1][1])
        self.assertGreater(offsets[2][1], offsets[1][1])

    def test_planet_marker_offsets_merge_wraparound_cluster(self) -> None:
        offsets = planet_marker_offsets([358.0, 2.0, 6.0], compact=True)

        self.assertTrue(all(radial > 0 for _, radial in offsets))
        self.assertLess(offsets[0][0], offsets[1][0])
        self.assertLess(offsets[1][0], offsets[2][0])

    def test_body_marker_offsets_support_lots_and_nodes_too(self) -> None:
        offsets = body_marker_offsets([120.0, 123.0], compact=False, crowd_threshold=10.0, angle_step=4.5, radial_step=10.0)

        self.assertEqual(len(offsets), 2)
        self.assertLess(offsets[0][0], offsets[1][0])
        self.assertTrue(all(radial > 0 for _, radial in offsets))

    def test_aspect_curve_points_route_through_inner_control_point(self) -> None:
        points = aspect_curve_points(0.0, 0.0, 100.0, 20.0, 140.0, compact=False, lane_index=1)

        self.assertEqual(len(points), 6)
        control_x, control_y = points[2], points[3]
        control_radius = (control_x ** 2 + control_y ** 2) ** 0.5
        self.assertLess(control_radius, 100.0)

    def test_header_helpers_keep_timing_and_location_readable(self) -> None:
        snapshot = {"formattedTime": "Tue, May 26, 2026, 9:23 PM PDT"}
        location = LocationPreset("user-home", "Home Base", 33.12, -117.98, "America/Los_Angeles")

        self.assertIn("May 26 9:23 PM PDT", compact_time_label(snapshot))
        self.assertIn("Home Base", location_summary(location))
        self.assertIn("America/Los_Angeles", location_summary(location))
        self.assertNotIn("33.120", location_summary(location))
        self.assertIn("33.120", location_coordinate_summary(location))
        self.assertEqual(compact_place_name("Indio, California"), "Indio, CA")

    def test_left_status_chip_lines_surface_current_workflow_context(self) -> None:
        chips = left_status_chip_lines(
            "2026-06-05",
            "13:09",
            "Indio, California",
            "America/Los_Angeles",
            "True 13-Sign",
            "Topocentric",
            "Low Risk",
            "Validation: Swiss-backed",
        )

        self.assertEqual(chips[0], "Chart: 2026-06-05 13:09")
        self.assertEqual(chips[1], "Site: Indio, CA | America/Los_Angeles")
        self.assertEqual(chips[2], "Model: True 13-Sign / Topocentric")
        self.assertEqual(chips[3], "Search: Low Risk | Swiss-backed")

    def test_candidate_board_summary_reports_count_mode_and_selection(self) -> None:
        summary = candidate_board_summary(
            [{"score": 91}, {"score": 84}],
            evaluated_count=48,
            search_mode="low-risk",
            selected_index=1,
            displayed_source="selected candidate",
        )

        self.assertIn("2 candidates", summary)
        self.assertIn("48 evaluated", summary)
        self.assertIn("Low Risk", summary)
        self.assertIn("Selected #2", summary)

    def test_workspace_hub_cards_prioritize_what_user_should_see(self) -> None:
        location = LocationPreset("indio-ca", "Indio, California", 33.72, -116.22, "America/Los_Angeles")
        snapshot = {
            "formattedTime": "Mon, Jun 8, 2026, 4:12 PM PDT",
            "score": 91,
            "detectedAspects": [{"tone": "support"}, {"tone": "stress"}],
            "scoreBreakdown": {
                "diagnostics": {
                    "confidence": {"score": 88},
                    "cleanliness": {"score": 80},
                    "volatility": {"score": 18},
                }
            },
        }
        highlights = {
            "current": {
                "label": "Moon trine Jupiter",
                "tone": "support",
                "orbText": "0 deg 44 min",
                "phaseLabel": "Applying",
                "strength": 17.2,
            }
        }

        headline, detail, tone = compact_aspect_headline(highlights)
        cards = workspace_hub_cards(
            snapshot,
            snapshot,
            location,
            highlights,
            [{"score": 91}],
            selected_index=0,
            displayed_source="selected candidate",
            rejection_summary={},
        )
        by_title = {title: (head, body, card_tone) for title, head, body, card_tone in cards}

        self.assertEqual(headline, "Moon trine Jupiter")
        self.assertIn("Applying", detail)
        self.assertEqual(tone, "support")
        self.assertNotIn("Viewing", by_title)
        self.assertEqual(by_title["Strongest Now"][0], "Moon trine Jupiter")
        self.assertIn("Score 91 / Prime", by_title["Quality"][0])
        self.assertIn("Conf 88", by_title["Quality"][1])

    def test_displayed_chart_state_line_keeps_header_from_repeating_site_and_time(self) -> None:
        input_snapshot = {"date": datetime(2026, 6, 8, 18, 0), "formattedTime": "Mon, Jun 8, 6:00 PM PDT"}
        selected = {"date": datetime(2026, 6, 8, 20, 0), "formattedTime": "Mon, Jun 8, 8:00 PM PDT"}

        current = displayed_chart_state_line(input_snapshot, input_snapshot, displayed_source="input chart", selected_index=0)
        candidate = displayed_chart_state_line(input_snapshot, selected, displayed_source="selected candidate", selected_index=1)

        self.assertEqual(current, "Current Chart | Selected equals search start")
        self.assertEqual(candidate, "Candidate #2 | Selected +2h from start")

    def test_search_workbench_compact_lines_keep_console_short_and_actionable(self) -> None:
        title, summary, detail = search_workbench_compact_lines(
            profile_name="Major Five",
            action_note="Last action: Search Page #1",
            windows=[],
            selected_time="Mon, Jun 8, 6:24 PM PDT",
            search_mode="Low Risk",
            scan_hours="24",
            step_minutes="60",
            active_aspects=5,
            rejection_summary={"topReasons": [("major stress present", 12)]},
        )

        self.assertEqual(title, "Search Console | Major Five")
        self.assertIn("No matching candidates", summary)
        self.assertIn("Low Risk", detail)
        self.assertIn("major stress present", detail)

    def test_workflow_next_step_lines_guide_user_actions(self) -> None:
        self.assertIn(
            "Show current chart",
            workflow_next_step_lines(
                has_chart=False,
                candidate_count=0,
                selected_index=-1,
                displayed_source="input chart",
            )[0],
        )
        blocked = workflow_next_step_lines(
            has_chart=True,
            candidate_count=0,
            selected_index=-1,
            displayed_source="input chart",
            has_rejections=True,
        )
        self.assertIn("Loosen", blocked[0])
        self.assertIn("relax", blocked[1])
        pick = workflow_next_step_lines(
            has_chart=True,
            candidate_count=3,
            selected_index=-1,
            displayed_source="input chart",
        )
        self.assertIn("Pick a candidate", pick[0])
        decide = workflow_next_step_lines(
            has_chart=True,
            candidate_count=3,
            selected_index=1,
            displayed_source="selected candidate",
        )
        self.assertIn("window #2", decide[0])
        self.assertIn("shortlist", decide[1])

    def test_candidate_metric_badges_surface_quality_and_missing_data(self) -> None:
        window = {
            "scoreBreakdown": {
                "objectiveMatches": 2,
                "diagnostics": {
                    "confidence": {"score": 84},
                    "cleanliness": {"score": 79},
                    "volatility": {"score": 24},
                },
            },
            "detectedAspects": [
                {"tone": "support"},
                {"tone": "support"},
                {"tone": "stress"},
            ],
            "positions": [
                {"name": "Jupiter", "isAngular": True},
                {"name": "Mars", "isAngular": False},
            ],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
            "searchStage": "refined",
            "searchResolutionMinutes": 10,
        }

        labels = [label for label, _tone in candidate_metric_badges(window)]

        self.assertIn("Conf 84", labels)
        self.assertIn("Clean 79", labels)
        self.assertIn("Vol 24", labels)
        self.assertIn("Fit 2", labels)
        self.assertIn("+2 / !1", labels)
        self.assertIn("Moon OK", labels)
        self.assertIn("Ang+ Yes", labels)
        self.assertIn("10m refined", labels)
        self.assertIn("Conf --", [label for label, _tone in candidate_metric_badges({})])

    def test_aspect_dashboard_formatter_returns_three_highlight_sections(self) -> None:
        aspect = {
            "label": "Sun trine Moon",
            "tone": "support",
            "orbText": "0 deg 40 min",
            "phaseLabel": "Applying",
            "perfectsAtText": "Fri 2:20 PM",
            "strength": 12.4,
            "formattedTime": "Fri, Jun 5, 1:09 PM PDT",
        }

        text = format_aspect_highlight_dashboard({"current": aspect, "localDay": aspect, "rolling24Hours": aspect})

        self.assertIn("Current", text)
        self.assertIn("Local Day", text)
        self.assertIn("Next 24h", text)
        self.assertIn("Sun trine Moon", text)
        self.assertNotEqual(text, "None")

    def test_timeline_visual_rows_format_support_stress_and_missing_data(self) -> None:
        support = {
            "formattedTime": "Fri, Jun 5, 1:09 PM PDT",
            "label": "Sun trine Moon",
            "tone": "support",
            "orbText": "0 deg 40 min",
            "isApplying": True,
            "perfectsAtText": "Fri 2:20 PM",
            "strength": 14.2,
            "bodies": ["Sun", "Moon"],
        }
        stress = {"label": "Mars square Saturn", "tone": "stress", "bodies": ["Mars", "Saturn"]}

        rows = timeline_visual_rows({"timelineByTime": [support, stress]}, limit=4)
        empty_rows = timeline_visual_rows({}, limit=4)

        self.assertEqual(rows[0]["toneLabel"], "Support")
        self.assertEqual(rows[0]["phase"], "Applying")
        self.assertEqual(rows[0]["strength"], "14.2")
        self.assertEqual(rows[0]["bodies"], ["Sun", "Moon"])
        self.assertEqual(rows[1]["toneLabel"], "Stress")
        self.assertEqual(rows[1]["orb"], "orb n/a")
        self.assertEqual(timeline_item_display(stress)["peak"], "exact time n/a")
        self.assertEqual(empty_rows, [])

    def test_analysis_helpers_surface_diagnostics_validation_and_rejections(self) -> None:
        zodiac = type("Zodiac", (), {"name": "True 13-Sign"})()
        house = type("House", (), {"name": "Topocentric"})()
        snapshot = {
            "score": 88,
            "note": "Strong window.",
            "traditionalRulesEnabled": False,
            "zodiacSystem": zodiac,
            "houseSystem": house,
            "engine": "Astronomy Engine",
            "ayanamsha": 24.1,
            "detectedAspects": [{"tone": "support"}, {"tone": "stress"}],
            "positions": [{"name": "Jupiter", "isAngular": True}],
            "scoreBreakdown": {
                "diagnostics": {
                    "confidence": {"score": 82, "summary": "Signals agree."},
                    "cleanliness": {"score": 76, "summary": "Mostly clean."},
                    "volatility": {"score": 22, "summary": "Stable enough."},
                }
            },
            "accuracyAudit": {"label": "Swiss verified", "summary": "Tolerances pass."},
        }
        rejection_summary = {
            "topReasons": [("major stress present", 3)],
            "suggestedRelaxations": ["Relax stress temporarily."],
        }

        cards = analysis_metric_cards(snapshot, [{"score": 88}])
        notices = analysis_notice_lines(snapshot, rejection_summary)
        labels = [label for label, _value, _note, _tone in cards]

        self.assertIn("Confidence", labels)
        self.assertIn(("Support", "1", "Selected supportive aspects in orb.", "support"), cards)
        self.assertTrue(any("True 13-Sign mode" in line for line in notices))
        self.assertTrue(any("major stress present" in line for line in notices))
        self.assertTrue(any("Relax stress temporarily" in line for line in notices))

    def test_validation_accepts_am_pm_time_and_custom_location(self) -> None:
        errors = validate_election_inputs("2026-05-26", "09:00 AM", "34.0522", "-118.2437", "America/Los_Angeles")
        location = build_custom_location("Launch Site", "34.0522", "-118.2437", "America/Los_Angeles")

        self.assertEqual(errors, [])
        self.assertEqual(location.name, "Launch Site")
        self.assertEqual(location.timezone, "America/Los_Angeles")

    def test_validation_reports_bad_coordinate_and_timezone(self) -> None:
        errors = validate_election_inputs("05/26/2026", "morning", "120", "not-west", "Pacific Time")

        self.assertIn("Date must use YYYY-MM-DD.", errors)
        self.assertIn("Time must look like 09:00 or 09:00 AM.", errors)
        self.assertIn("Latitude must be between -90 and 90.", errors)
        self.assertIn("Longitude must be a number.", errors)
        self.assertIn("Time zone must be a valid IANA name like America/Los_Angeles.", errors)

    def test_search_config_parses_optional_desktop_controls(self) -> None:
        config = build_search_config_from_text("12", "30", "60", "8", "2", True)

        self.assertEqual(config.end_offset_minutes, 720)
        self.assertEqual(config.step_minutes, 30)
        self.assertEqual(config.minimum_score, 60)
        self.assertEqual(config.max_results, 8)
        self.assertEqual(config.minimum_fit, 2)
        self.assertTrue(config.avoid_major_stress)
        self.assertEqual(
            format_search_summary(config),
            "Scan 12h from start, every 30m; score >= 60, fit >= 2, no major stress, rank: Balanced, refine leaders to 10m, top 8.",
        )

    def test_search_config_parses_diagnostic_filters(self) -> None:
        config = build_search_config_from_text(
            "12",
            "30",
            "60",
            "8",
            "2",
            require_applying_support=True,
            require_angular_benefic=True,
            minimum_confidence_text="70",
            minimum_cleanliness_text="68",
            maximum_volatility_text="35",
        )

        self.assertEqual(config.minimum_confidence, 70)
        self.assertEqual(config.minimum_cleanliness, 68)
        self.assertEqual(config.maximum_volatility, 35)
        self.assertTrue(config.require_applying_support)
        self.assertTrue(config.require_angular_benefic)
        self.assertIn("confidence >= 70", format_search_summary(config))
        self.assertIn("cleanliness >= 68", format_search_summary(config))
        self.assertIn("volatility <= 35", format_search_summary(config))
        self.assertIn("needs angular benefic", format_search_summary(config))
        self.assertIn("rank: Balanced", format_search_summary(config))

    def test_search_config_supports_quality_modes_and_candidate_explanations(self) -> None:
        config = build_search_config_from_text("12", "60", search_quality_mode_text="Low Risk")
        window = {
            "score": 88,
            "note": "Strong support window.",
            "scoreBreakdown": {
                "rawScore": 91,
                "diagnostics": {
                    "confidence": {"score": 78},
                    "cleanliness": {"score": 82},
                    "readiness": {"score": 80},
                    "volatility": {"score": 22},
                },
            },
            "detectedAspects": [{"tone": "support", "isApplying": True}],
            "positions": [{"name": "Venus", "isAngular": True, "closestAngle": {"distance": 2.0}}],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }

        self.assertEqual(config.quality_mode, "low-risk")
        self.assertIn("Low Risk", SEARCH_QUALITY_MODE_NAMES)
        self.assertIn("rank: Low Risk", format_search_summary(config))
        self.assertIn("Rank mode: Low Risk", candidate_explanation_lines(window, {"score": 80}, config)[0])

    def test_candidate_refinement_offsets_fill_between_coarse_seed_times(self) -> None:
        base = datetime(2026, 5, 26, 16, 0)
        config = build_search_config_from_text("4", "60", max_results_text="3")
        windows = [
            {"date": base, "score": 70, "scoreBreakdown": {"rawScore": 70, "diagnostics": {}}},
            {"date": base.replace(hour=18), "score": 95, "scoreBreakdown": {"rawScore": 95, "diagnostics": {}}},
        ]

        offsets = candidate_refinement_offsets(windows, base, config)

        self.assertIn(110, offsets)
        self.assertIn(130, offsets)
        self.assertNotIn(120, offsets)

    def test_objective_search_presets_expose_expected_names_and_filters(self) -> None:
        self.assertIn("Strict Launch", SEARCH_PRESET_NAMES)
        launch = search_preset_values("Strict Launch")
        travel = search_preset_values("Safe Travel")

        self.assertTrue(launch["require_angular_benefic"])
        self.assertTrue(launch["avoid_objective_antipatterns"])
        self.assertTrue(travel["require_moon_non_void"])
        self.assertEqual(search_preset_values("Custom"), {})

    def test_search_validation_rejects_impossible_values(self) -> None:
        errors = validate_search_inputs("1", "90", "100", "0", "9")

        self.assertIn("Step minutes must fit inside the scan range.", errors)
        self.assertIn("Minimum score must be 99 or lower.", errors)
        self.assertIn("Max results must be at least 1.", errors)
        self.assertIn("Minimum fit must be 5 or lower.", errors)

    def test_search_validation_rejects_out_of_range_diagnostic_filters(self) -> None:
        errors = validate_search_inputs("12", "60", "50", "5", "2", "100", "101", "120")

        self.assertIn("Minimum confidence must be 99 or lower.", errors)
        self.assertIn("Minimum cleanliness must be 99 or lower.", errors)
        self.assertIn("Maximum volatility must be 99 or lower.", errors)

    def test_rank_search_windows_can_filter_for_fit_and_major_stress(self) -> None:
        clean_high_fit = {
            "score": 90,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.1, "isApplying": True}],
            "positions": [{"name": "Jupiter", "isAngular": True, "closestAngle": {"distance": 2.0}}],
        }
        stressed = {
            "score": 95,
            "scoreBreakdown": {"objectiveMatches": 3},
            "detectedAspects": [{"tone": "stress", "orb": 0.8, "isApplying": True}],
            "positions": [{"name": "Mars", "isAngular": True, "closestAngle": {"distance": 2.0}}],
        }
        low_fit = {
            "score": 92,
            "scoreBreakdown": {"objectiveMatches": 0},
            "detectedAspects": [],
            "positions": [],
        }

        ranked = rank_search_windows(
            [stressed, clean_high_fit, low_fit],
            build_search_config_from_text("12", "30", "60", "", "2", True),
        )

        self.assertEqual(ranked, [clean_high_fit])

    def test_rank_search_windows_can_require_support_avoid_angular_malefics_and_keep_moon_non_void(self) -> None:
        clean = {
            "score": 88,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.2, "isApplying": True}],
            "positions": [{"name": "Jupiter", "isAngular": True, "closestAngle": {"distance": 2.0}}],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }
        no_support = {
            "score": 90,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 2.8, "isApplying": False}],
            "positions": [],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }
        angular_malefic = {
            "score": 92,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [{"name": "Mars", "isAngular": True, "closestAngle": {"distance": 2.0}}],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }
        void_moon = {
            "score": 89,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [],
            "moonCondition": {"voidOfCourse": {"isVoid": True}},
        }

        ranked = rank_search_windows(
            [void_moon, angular_malefic, no_support, clean],
            build_search_config_from_text(
                "12",
                "30",
                "60",
                "",
                "2",
                require_applying_support=True,
                avoid_angular_malefics=True,
                require_moon_non_void=True,
            ),
        )

        self.assertEqual(ranked, [clean])

    def test_rank_search_windows_can_avoid_objective_antipatterns(self) -> None:
        clean = {
            "score": 87,
            "objective": "Meeting or negotiation",
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [{"name": "Jupiter", "isAngular": False, "isRetrograde": False}],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }
        bad_negotiation = {
            "score": 93,
            "objective": "Meeting or negotiation",
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "stress", "orb": 0.8, "isApplying": True}],
            "positions": [{"name": "Mercury", "isAngular": False, "isRetrograde": True}],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }

        ranked = rank_search_windows(
            [bad_negotiation, clean],
            build_search_config_from_text(
                "12",
                "30",
                "60",
                "",
                "1",
                avoid_objective_antipatterns=True,
            ),
        )

        self.assertTrue(fails_objective_antipattern(bad_negotiation, "Meeting or negotiation"))
        self.assertEqual(ranked, [clean])

    def test_rank_search_windows_can_filter_by_diagnostics_and_angular_benefic(self) -> None:
        strongest = {
            "score": 90,
            "scoreBreakdown": {
                "objectiveMatches": 2,
                "diagnostics": {
                    "confidence": {"score": 84},
                    "cleanliness": {"score": 79},
                    "volatility": {"score": 28},
                    "readiness": {"score": 81},
                },
            },
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [{"name": "Venus", "isAngular": True, "closestAngle": {"distance": 2.0}}],
        }
        noisy = {
            "score": 95,
            "scoreBreakdown": {
                "objectiveMatches": 3,
                "diagnostics": {
                    "confidence": {"score": 59},
                    "cleanliness": {"score": 52},
                    "volatility": {"score": 64},
                    "readiness": {"score": 75},
                },
            },
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [{"name": "Jupiter", "isAngular": False, "closestAngle": {"distance": 12.0}}],
        }

        ranked = rank_search_windows(
            [noisy, strongest],
            build_search_config_from_text(
                "12",
                "30",
                "60",
                "",
                "1",
                require_applying_support=True,
                require_angular_benefic=True,
                minimum_confidence_text="70",
                minimum_cleanliness_text="70",
                maximum_volatility_text="35",
            ),
        )

        self.assertTrue(has_angular_benefic(strongest))
        self.assertEqual(ranked, [strongest])

    def test_rejection_reasons_and_summary_explain_why_windows_failed(self) -> None:
        window = {
            "formattedTime": "Tue, May 26, 2026, 1:00 PM PDT",
            "score": 63,
            "objective": "Safe Travel",
            "scoreBreakdown": {
                "objectiveMatches": 0,
                "diagnostics": {
                    "confidence": {"score": 58},
                    "cleanliness": {"score": 60},
                    "volatility": {"score": 52},
                },
            },
            "detectedAspects": [{"tone": "stress", "orb": 0.8, "isApplying": True}],
            "positions": [{"name": "Mars", "isAngular": True, "closestAngle": {"distance": 2.0}}],
            "moonCondition": {"voidOfCourse": {"isVoid": True}},
        }
        config = build_search_config_from_text(
            "12",
            "30",
            "70",
            "",
            "1",
            avoid_major_stress=True,
            avoid_angular_malefics=True,
            require_moon_non_void=True,
            minimum_confidence_text="70",
            maximum_volatility_text="35",
        )

        reasons = rejection_reasons(window, config)
        kept, rejected = split_ranked_windows([window], config)
        summary = rejection_summary(rejected)

        self.assertEqual(kept, [])
        self.assertIn("score 63 below minimum 70", reasons)
        self.assertIn("confidence 58 below minimum 70", reasons)
        self.assertIn("major stress present", reasons)
        self.assertEqual(summary["count"], 1)
        self.assertTrue(any("major stress present" == reason for reason, _count in summary["topReasons"]))
        self.assertTrue(summary["suggestedRelaxations"])

    def test_has_major_stress_detects_tight_stress_or_angular_malefic(self) -> None:
        self.assertTrue(
            has_major_stress(
                {
                    "detectedAspects": [{"tone": "stress", "orb": 0.9, "isApplying": False}],
                    "positions": [],
                }
            )
        )

    def test_deeper_search_helpers_detect_support_malefics_and_void_moon(self) -> None:
        self.assertTrue(has_applying_support({"detectedAspects": [{"tone": "support", "isApplying": True}]}))
        self.assertTrue(
            has_angular_malefic({"positions": [{"name": "Saturn", "isAngular": True, "closestAngle": {"distance": 3.0}}]})
        )
        self.assertFalse(moon_is_non_void({"moonCondition": {"voidOfCourse": {"isVoid": True}}}))
        self.assertTrue(
            has_major_stress(
                {
                    "detectedAspects": [],
                    "positions": [{"name": "Saturn", "isAngular": True, "closestAngle": {"distance": 2.5}}],
                }
            )
        )

    def test_default_location_matches_local_timezone(self) -> None:
        location = default_location_for_timezone(DEFAULT_TIMEZONE)

        self.assertEqual(location.timezone, "America/Los_Angeles")
        self.assertEqual(location.name, "Los Angeles, CA")

    def test_shift_local_datetime_crosses_midnight(self) -> None:
        next_date, next_time = shift_local_datetime("2026-05-26", "11:30 PM", "America/Los_Angeles", 2)

        self.assertEqual(next_date, "2026-05-27")
        self.assertEqual(next_time, "01:30")

    def test_shift_local_datetime_minutes_supports_electional_fine_tuning(self) -> None:
        next_date, next_time = shift_local_datetime_minutes("2026-05-26", "23:58", "America/Los_Angeles", 5)

        self.assertEqual(next_date, "2026-05-27")
        self.assertEqual(next_time, "00:03")

    def test_window_label_summarizes_support_and_stress_counts(self) -> None:
        label = format_window_label(
            1,
            {
                "time": "9:00 AM PDT",
                "score": 77,
                "title": "High-priority election",
                "detectedAspects": [
                    {"tone": "support"},
                    {"tone": "support"},
                    {"tone": "stress"},
                ],
            },
        )

        self.assertIn("+2/!1", label)
        self.assertIn("Score 77", label)

    def test_window_label_handles_empty_aspects(self) -> None:
        label = format_window_label(2, {"time": "11:00 AM PDT", "score": 61, "title": "Workable election", "detectedAspects": []})

        self.assertIn("+0/!0", label)
        self.assertIn("Workable election", label)

    def test_window_score_color_groups_score_ranges(self) -> None:
        self.assertEqual(window_score_color(90), "#e6f6ef")
        self.assertEqual(window_score_color(82), "#eef7f5")
        self.assertEqual(window_score_color(65), "#fff5df")
        self.assertEqual(window_score_color(44), "#f9e7eb")
        self.assertEqual(score_band_label(90), "Prime")
        self.assertEqual(score_band_label(82), "Strong")
        self.assertEqual(score_band_label(65), "Workable")
        self.assertEqual(score_band_label(44), "Caution")

    def test_summary_chip_lines_surface_chart_context(self) -> None:
        snapshot = {
            "lunarPhase": {"name": "Waxing Gibbous"},
            "fixedStarContacts": [{"label": "Venus conjunct Spica"}],
            "planetaryHour": {"available": True, "hourRuler": "Jupiter"},
            "zodiacSystem": type("System", (), {"name": "Sidereal Lahiri"})(),
            "houseSystem": type("HouseSystem", (), {"name": "Koch"})(),
        }

        self.assertEqual(fixed_star_contact_count(snapshot), 1)
        chips = summary_chip_lines(snapshot, "Classical 7")

        self.assertIn("Moon: Waxing Gibbous", chips)
        self.assertIn("Hour: Jupiter", chips)
        self.assertIn("Points: Classical 7", chips)
        self.assertIn("Zodiac: Sidereal Lahiri", chips)
        self.assertIn("Houses: Koch", chips)

    def test_selection_offset_label_explains_current_vs_selected(self) -> None:
        start = {"date": datetime(2026, 5, 26, 16, 0)}
        same = {"date": datetime(2026, 5, 26, 16, 0)}
        later = {"date": datetime(2026, 5, 26, 18, 30)}
        earlier = {"date": datetime(2026, 5, 26, 15, 45)}

        self.assertEqual(selection_offset_label(start, same), "Selected equals search start")
        self.assertEqual(selection_offset_label(start, later), "Selected +2h 30m from start")
        self.assertEqual(selection_offset_label(start, earlier), "Selected -15m from start")

    def test_planet_focus_includes_dignity_and_contacts(self) -> None:
        planet = {
            "id": "venus",
            "name": "Venus",
            "zodiac": {"sign": "Cancer", "degree": 9, "minute": 23},
            "house": 10,
            "dignity": {"label": "Peregrine", "boundLord": "Venus", "isOwnBound": True},
            "closestAngle": {"shortName": "MC", "distance": 3.2},
            "isAngular": True,
            "motion": {"label": "Direct", "dailyLongitudeChange": 1.2},
        }
        focus = format_planet_focus(planet, [{"label": "Venus trine Moon", "orbText": "1 deg", "bodies": ["Venus", "Moon"]}])

        self.assertIn("Venus", focus)
        self.assertIn("Dignity: Peregrine", focus)
        self.assertIn("Egyptian bound: Venus", focus)
        self.assertIn("Motion: Direct", focus)
        self.assertIn("own Egyptian bound", focus)
        self.assertIn("Venus trine Moon", focus)

    def test_dignity_summary_includes_bound_context(self) -> None:
        summary = format_dignity_summary({"dignity": {"label": "Bound", "boundLord": "Mercury", "isOwnBound": True}})

        self.assertEqual(summary, "Bound / Bound Mercury own bound")

    def test_score_breakdown_summary_is_human_readable(self) -> None:
        summary = format_score_breakdown(
            {
                "score": 72,
                "scoreBreakdown": {
                    "base": 58,
                    "support": 1,
                    "mixed": 0,
                    "stress": 1,
                    "objectiveMatches": 1,
                    "closeContacts": 1,
                    "angularity": 4.5,
                    "dignity": 2,
                    "retrogradePressure": 3,
                    "accounting": {
                        "startingScore": 58,
                        "positiveTotal": 20,
                        "negativeTotal": -5,
                        "netAdjustment": 15,
                        "rawScore": 72.4,
                        "finalScore": 72,
                        "categoryTotals": {"Aspect quality": 7, "Risk pressure": -3},
                    },
                    "evaluation": {
                        "band": "Workable",
                        "grade": "C",
                        "summary": "Workable electional window with net +15.0 points.",
                        "strengths": ["Aspect quality +7.0"],
                        "risks": ["Risk pressure -3.0"],
                    },
                    "rawScore": 72.4,
                    "score": 72,
                },
            }
        )

        self.assertIn("support 1", summary)
        self.assertIn("retrograde pressure 3.0", summary)
        self.assertIn("raw 72.4 -> final 72", summary)

    def test_score_breakdown_applies_objective_specific_weighting(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = [
            {
                "name": "Mercury",
                "isAngular": False,
                "isRetrograde": True,
                "dignity": {"score": 0},
            },
            {
                "name": "Jupiter",
                "isAngular": True,
                "isRetrograde": False,
                "closestAngle": {"distance": 2.0},
                "dignity": {"score": 3},
            },
        ]
        aspects = [
            {"aspectId": "trine", "tone": "support", "orb": 1.0, "isApplying": True, "timingQuality": "soon"},
            {"aspectId": "square", "tone": "stress", "orb": 1.0, "isApplying": True, "timingQuality": "soon"},
        ]

        launch = score_breakdown(aspects, positions, preset, objective="Launch or publish")
        travel = score_breakdown(aspects, positions, preset, objective="Travel departure")

        self.assertNotEqual(launch["score"], travel["score"])
        reasons = travel["reasons"]
        self.assertTrue(any(reason.get("code") == "objective-weighting" for reason in reasons))

    def test_score_breakdown_includes_backend_diagnostics(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = [
            {
                "name": "Mercury",
                "isAngular": False,
                "isRetrograde": False,
                "dignity": {"score": 0},
            },
            {
                "name": "Jupiter",
                "isAngular": True,
                "isRetrograde": False,
                "closestAngle": {"distance": 2.0},
                "dignity": {"score": 3},
            },
        ]
        aspects = [
            {"aspectId": "trine", "tone": "support", "orb": 1.0, "isApplying": True, "timingQuality": "soon"},
        ]

        breakdown = score_breakdown(aspects, positions, preset, objective="Launch or publish")
        diagnostics = breakdown.get("diagnostics", {})

        self.assertIn("readiness", diagnostics)
        self.assertIn("volatility", diagnostics)
        self.assertIn("cleanliness", diagnostics)
        self.assertIn("confidence", diagnostics)
        self.assertIn("signals", diagnostics)
        self.assertIsInstance(diagnostics["confidence"]["score"], int)

    def test_score_accounting_and_evaluation_lines_are_human_readable(self) -> None:
        snapshot = {
            "scoreBreakdown": {
                "score": 72,
                "accounting": {
                    "startingScore": 58,
                    "positiveTotal": 18.5,
                    "negativeTotal": -4,
                    "netAdjustment": 14.5,
                    "rawScore": 72.5,
                    "finalScore": 72,
                    "categoryTotals": {"Aspect quality": 7, "Risk pressure": -4},
                },
                "evaluation": {
                    "band": "Workable",
                    "grade": "C",
                    "summary": "Workable electional window with net +14.5 points.",
                    "strengths": ["Aspect quality +7.0"],
                    "risks": ["Risk pressure -4.0"],
                },
            }
        }

        self.assertIn("positive +18.5", "\n".join(score_accounting_lines(snapshot)))
        self.assertIn("Aspect quality", "\n".join(score_accounting_lines(snapshot)))
        self.assertIn("Grade C", "\n".join(score_evaluation_lines(snapshot)))

    def test_score_diagnostic_lines_and_page_are_human_readable(self) -> None:
        snapshot = {
            "score": 78,
            "scoreBreakdown": {
                "evaluation": {"band": "Strong", "grade": "B"},
                "diagnostics": {
                    "readiness": {"score": 82, "band": "Strong", "summary": "Ready to act."},
                    "volatility": {"score": 36, "band": "Moderate", "summary": "Some motion remains."},
                    "cleanliness": {"score": 76, "band": "Usable", "summary": "Mostly coherent chart."},
                    "confidence": {"score": 71, "band": "Solid", "summary": "Signals agree well enough."},
                    "signals": {
                        "applyingSupport": True,
                        "angularBenefic": True,
                        "majorStress": False,
                        "angularMalefic": False,
                        "moonNonVoid": True,
                        "objectiveAntiPatterns": [],
                    },
                },
            },
            "accuracyAudit": {
                "label": "Swiss verified",
                "summary": "All full-chart values match Swiss verification tolerances.",
                "maxPositionDeltaDegrees": 0.0,
                "maxAngleDeltaDegrees": 0.0,
                "maxHouseDeltaDegrees": 0.0,
            },
        }

        diagnostic_text = "\n".join(score_diagnostic_lines(snapshot))
        page = build_diagnostics_page(snapshot)

        self.assertIn("Readiness: 82", diagnostic_text)
        self.assertIn("Signal: applying support is present.", diagnostic_text)
        self.assertIn("Signal: angular benefic emphasis is present.", diagnostic_text)
        self.assertIn("Window Diagnostics", page)
        self.assertIn("Confidence: 71", page)
        self.assertIn("Accuracy Audit", page)
        self.assertIn("Swiss verified", page)
        self.assertIn("Maximum planet delta: 0.000000 deg", page)

    def test_constellation_lines_explain_rising_size_and_speed(self) -> None:
        snapshot = {
            "constellationContext": {
                "sourceNote": "diagnostic note",
                "rising": {
                    "ascendantConstellation": {
                        "name": "Scorpius",
                        "spanDegrees": 6,
                        "spanRatioToSign": 0.2,
                        "percentThrough": 0.5,
                        "distanceToEndDegrees": 3,
                        "nextConstellation": {"name": "Ophiuchus"},
                    },
                    "ascendantSpeedDegPerHour": 25,
                    "tempo": {"label": "fast", "scoreImpact": 1},
                    "spanContext": {"label": "narrow", "scoreImpact": -0.5},
                    "currentConstellationRisingMinutes": 16,
                    "currentSignRisingMinutes": 110,
                    "minutesToNextConstellation": 7,
                },
                "positions": [
                    {"name": "Sun", "constellation": {"name": "Virgo", "spanDegrees": 44}},
                    {"name": "Moon", "constellation": {"name": "Libra", "spanDegrees": 24}},
                ],
            }
        }
        text = "\n".join(constellation_lines(snapshot))

        self.assertIn("Scorpius", text)
        self.assertIn("25.0 deg/hour", text)
        self.assertIn("current 30 deg sign", text)

    def test_judgment_and_factor_explorer_lines_are_human_readable(self) -> None:
        snapshot = {
            "score": 71,
            "significatorContext": {
                "summary": "Launch or publish: 3 primary significator(s) selected.",
                "scoreImpact": 1.5,
                "confidence": "solid",
                "factors": [
                    {
                        "title": "Mercury significator condition",
                        "detail": "Mercury serves as public launch natural significator.",
                        "scoreImpact": 1.5,
                        "severity": "support",
                    }
                ],
            },
            "moonCondition": {"summary": "Moon available.", "scoreImpact": 0, "confidence": "approximate", "factors": []},
            "houseRulerContext": {"summary": "House ruler available.", "scoreImpact": 0, "confidence": "solid", "factors": []},
            "receptionContext": {"summary": "No reception.", "scoreImpact": 0, "confidence": "solid", "factors": []},
            "planetConditionContext": {"summary": "No conditions.", "scoreImpact": 0, "confidence": "approximate", "factors": []},
            "declinationContext": {
                "summary": "Declination scan found 1 out-of-bounds body and 1 parallel contact.",
                "scoreImpact": -1,
                "confidence": "solid",
                "factors": [
                    {
                        "title": "Moon out of bounds",
                        "detail": "Moon has declination +24.1 deg, outside the solar bounds.",
                        "scoreImpact": -1,
                        "severity": "caution",
                    }
                ],
            },
            "advancedAspectContext": {"summary": "No patterns.", "scoreImpact": 0, "confidence": "experimental", "factors": []},
            "fixedStarContext": {
                "summary": "1 fixed-star contact found.",
                "scoreImpact": 2.0,
                "confidence": "approximate",
                "factors": [
                    {
                        "title": "Venus conjunct Spica",
                        "detail": "0 deg 12 min longitude orb; strength 0.90",
                        "scoreImpact": 2.0,
                        "severity": "support",
                    }
                ],
            },
        }

        self.assertIn("Mercury significator", "\n".join(judgment_context_lines(snapshot, "significatorContext")))
        self.assertIn("Moon out of bounds", "\n".join(judgment_context_lines(snapshot, "declinationContext")))
        self.assertIn("Significators", "\n".join(factor_explorer_lines(snapshot)))
        self.assertIn("Fixed Stars", "\n".join(factor_explorer_lines(snapshot)))

        baseline = {
            "score": 66,
            "significatorContext": {"scoreImpact": 0.5, "factors": []},
            "moonCondition": {"scoreImpact": 0, "factors": []},
            "houseRulerContext": {"scoreImpact": 0, "factors": []},
            "receptionContext": {"scoreImpact": 0, "factors": []},
            "planetConditionContext": {"scoreImpact": -0.5, "factors": []},
            "declinationContext": {"scoreImpact": 0, "factors": []},
            "advancedAspectContext": {"scoreImpact": 0, "factors": []},
            "fixedStarContext": {"scoreImpact": 0, "factors": []},
        }
        compared = "\n".join(factor_explorer_lines(snapshot, baseline))
        self.assertIn("Compared with search-start chart: +5 points.", compared)
        self.assertIn("improved +1.0 vs start", compared)
        self.assertIn("worsened -1.0 vs start", compared)

    def test_advisor_lines_surface_next_tools_from_factors(self) -> None:
        snapshot = {
            "score": 78,
            "title": "Launch or publish",
            "detectedAspects": [{"label": "Mars square Saturn", "tone": "stress"}],
            "scoreBreakdown": {
                "evaluation": {"band": "Strong", "grade": "B", "strengths": ["Objective fit +4.0"], "risks": ["Stress -3.0"]},
            },
            "moonCondition": {
                "summary": "Moon applies to Mars.",
                "scoreImpact": -1,
                "confidence": "solid",
                "factors": [
                    {"title": "Moon applies to Mars", "detail": "Next lunar contact is stressful.", "scoreImpact": -1.0, "severity": "caution"}
                ],
            },
            "receptionContext": {
                "summary": "Reception helps.",
                "scoreImpact": 1.5,
                "confidence": "solid",
                "factors": [
                    {"title": "Mutual reception", "detail": "Significators can cooperate.", "scoreImpact": 1.5, "severity": "support"}
                ],
            },
            "planetConditionContext": {"summary": "No conditions.", "scoreImpact": 0, "confidence": "approximate", "factors": []},
        }
        baseline = {"score": 72}

        text = "\n".join(advisor_lines(snapshot, baseline, "Launch or publish"))

        self.assertIn("Election Advisor", text)
        self.assertIn("Change from search start: +6 points", text)
        self.assertIn("Best Supports", text)
        self.assertIn("Mutual reception", text)
        self.assertIn("Needs Attention", text)
        self.assertIn("Moon applies to Mars", text)
        self.assertIn("Open Next", text)
        self.assertIn("Timing + Aspects", text)
        self.assertIn("Moon + Void Course", text)

    def test_angle_testimony_lines_explain_angular_scoring(self) -> None:
        snapshot = {
            "scoreBreakdown": {
                "diagnostics": {
                    "angles": {
                        "summary": "2 angular scoring planet(s); strongest testimony: Venus strengthens ASC.",
                        "scoreImpact": 4.5,
                        "beneficSupport": 6.0,
                        "maleficPressure": -1.5,
                        "luminarySupport": 0,
                        "neutralEmphasis": 0,
                        "factors": [
                            {
                                "title": "Venus strengthens ASC",
                                "angle": "ASC",
                                "distance": 1.2,
                                "scoreImpact": 6.0,
                            },
                            {
                                "title": "Saturn pressures MC",
                                "angle": "MC",
                                "distance": 3.4,
                                "scoreImpact": -1.5,
                            },
                        ],
                    }
                }
            }
        }

        text = "\n".join(angle_testimony_lines(snapshot))

        self.assertIn("Angle Testimony", text)
        self.assertIn("Score impact: +4.5", text)
        self.assertIn("Venus strengthens ASC", text)
        self.assertIn("Saturn pressures MC", text)

    def test_improvement_guide_turns_diagnostics_into_actions(self) -> None:
        snapshot = {
            "score": 63,
            "detectedAspects": [{"tone": "stress", "isApplying": True, "orb": 0.8}],
            "timingProfile": {
                "nextSupport": {"label": "Venus trine Jupiter", "timeToExactText": "3h"},
                "nextStress": {"label": "Mars square Saturn", "timeToExactText": "45m"},
            },
            "scoreBreakdown": {
                "diagnostics": {
                    "signals": {
                        "applyingSupport": False,
                        "majorStress": True,
                        "angularBenefic": False,
                        "angularMalefic": True,
                        "moonNonVoid": False,
                    }
                },
                "reasons": [
                    {"label": "Stress aspects", "value": -7.0},
                    {"label": "Angular malefic pressure", "value": -5.0},
                ],
            },
            "angleContext": {"factors": [{"body": "Mars", "angle": "ASC", "scoreImpact": -5.0}]},
            "moonCondition": {"factors": [{"title": "Moon void", "scoreImpact": -1.5}]},
        }

        text = "\n".join(improvement_guide_lines(snapshot, {"score": 66}))

        self.assertIn("Score Improvement Guide", text)
        self.assertIn("Change from search start: -3 points", text)
        self.assertIn("Search for the next window with an applying supportive aspect", text)
        self.assertIn("Move the minute away from tight applying stress", text)
        self.assertIn("Reduce Mars angular pressure near ASC", text)
        self.assertIn("Stress aspects: -7.0", text)
        self.assertIn("Protect support: Venus trine Jupiter exact in 3h", text)

    def test_lunar_and_motion_summaries_are_human_readable(self) -> None:
        phase = format_lunar_phase(
            {
                "lunarPhase": {
                    "name": "Waxing Gibbous",
                    "illumination": 0.82,
                    "ageDays": 10.5,
                    "isWaxing": True,
                }
            }
        )
        motion = format_motion_summary({"motion": {"label": "Retrograde", "dailyLongitudeChange": -0.42}})

        self.assertIn("Waxing Gibbous", phase)
        self.assertIn("82% lit", phase)
        self.assertEqual(motion, "Retrograde -0.42 deg/day")

        station_motion = format_motion_summary(
            {
                "motion": {
                    "label": "Direct",
                    "dailyLongitudeChange": 0.04,
                    "station": {"isInStationWindow": True, "phase": "approaching station", "daysFromStation": 1.5},
                }
            }
        )
        self.assertIn("approaching station", station_motion)

    def test_aspect_summary_includes_applying_phase(self) -> None:
        summary = format_aspect_summary(
            {
                "label": "Venus trine Jupiter",
                "orbText": "1 deg 30 min",
                "phase": "applying",
                "phaseLabel": "Applying",
                "orbChangePerDay": -0.75,
                "isApplying": True,
                "timeToExactText": "2d",
                "perfectsAtText": "Thu, May 28, 2026, 9:00 AM PDT",
            }
        )

        self.assertIn("applying", summary)
        self.assertIn("-0.75 deg/day", summary)
        self.assertIn("exact in 2d", summary)

    def test_condition_lines_collect_lunar_phase_and_retrogrades(self) -> None:
        lines = condition_lines(
            {
                "lunarPhase": {
                    "name": "Waning Gibbous",
                    "illumination": 0.73,
                    "ageDays": 18.2,
                    "isWaxing": False,
                },
                "positions": [
                    {
                        "name": "Mercury",
                        "isRetrograde": True,
                        "motion": {"label": "Retrograde", "dailyLongitudeChange": -0.35},
                    }
                ],
                "detectedAspects": [
                    {"label": "Venus trine Jupiter", "tone": "support", "isApplying": True},
                ],
            }
        )
        text = "\n".join(lines)

        self.assertIn("Waning Gibbous", text)
        self.assertIn("Retrograde: Mercury", text)
        self.assertIn("Election Flags", text)

    def test_election_flags_call_out_tightening_and_angular_conditions(self) -> None:
        flags = election_flag_lines(
            {
                "lunarPhase": {"name": "Waxing Crescent", "isWaxing": True},
                "detectedAspects": [
                    {"label": "Venus trine Jupiter", "tone": "support", "isApplying": True},
                    {"label": "Mars square Moon", "tone": "stress", "isApplying": True},
                ],
                "positions": [
                    {"name": "Jupiter", "isAngular": True},
                    {"name": "Mars", "isAngular": True},
                ],
            }
        )
        text = "\n".join(flags)

        self.assertIn("Tightening support", text)
        self.assertIn("Tightening stress", text)
        self.assertIn("Angular benefic", text)
        self.assertIn("Angular malefic", text)
        self.assertIn("favors building", text)

    def test_rule_lines_format_active_electional_rules(self) -> None:
        lines = rule_lines(
            {
                "ruleEvaluations": {
                    "rules": [
                        {
                            "title": "Mercury combust",
                            "detail": "Mercury is combust the Sun.",
                            "scoreImpact": -5,
                        }
                    ]
                }
            }
        )

        self.assertIn("Mercury combust", lines[0])
        self.assertIn("-5.0", lines[0])

    def test_dignity_table_includes_classical_rulerships(self) -> None:
        lines = dignity_table_lines()
        reference = "\n".join(lines)

        self.assertIn("Sign", lines[0])
        self.assertTrue(any("Aries" in line and "Mars" in line for line in lines))
        self.assertTrue(any("Libra" in line and "Venus" in line for line in lines))
        self.assertIn("Egyptian Bounds", reference)
        self.assertIn("0-6 Jupiter", reference)

    def test_system_reference_includes_sidereal_and_topocentric(self) -> None:
        reference = "\n".join(system_reference_lines())

        self.assertIn("Sidereal Lahiri", reference)
        self.assertIn("Sidereal Fagan-Bradley", reference)
        self.assertIn("Topocentric", reference)
        self.assertIn("Polich-Page", reference)
        self.assertIn("Koch", reference)
        self.assertIn("sefstars.txt", reference)

    def test_fixed_star_contact_summary_is_human_readable(self) -> None:
        summary = format_fixed_star_contact(
            {
                "label": "Venus conjunct Spica",
                "orbText": "0 deg 14 min",
                "tone": "support",
                "score": 4.0,
            }
        )

        self.assertIn("Venus conjunct Spica", summary)
        self.assertIn("+4.0", summary)

    def test_aspectarian_formats_detected_contacts(self) -> None:
        table = format_aspectarian(
            {
                "positions": [{"name": "Sun"}, {"name": "Moon"}, {"name": "Venus"}],
                "detectedAspects": [
                    {
                        "bodies": ["Sun", "Moon"],
                        "aspectName": "Trine",
                        "tone": "support",
                    },
                    {
                        "bodies": ["Moon", "Venus"],
                        "aspectName": "Square",
                        "tone": "stress",
                    },
                ],
            }
        )

        self.assertIn("Aspectarian", table)
        self.assertIn("+Tri", table)
        self.assertIn("!Sqr", table)

    def test_strongest_aspect_analysis_explains_lords_houses_and_dignity(self) -> None:
        snapshot = {
            "positions": [
                {
                    "name": "Venus",
                    "house": 10,
                    "dignity": {"label": "Exalted", "score": 4},
                    "closestAngle": {"shortName": "MC", "distance": 1.2},
                },
                {
                    "name": "Jupiter",
                    "house": 1,
                    "dignity": {"label": "Domicile", "score": 5},
                    "closestAngle": {"shortName": "ASC", "distance": 2.0},
                },
                {
                    "name": "Moon",
                    "house": 9,
                    "dignity": {"label": "Peregrine", "score": 0},
                },
                {
                    "name": "Mars",
                    "house": 7,
                    "dignity": {"label": "Fall", "score": -4},
                    "closestAngle": {"shortName": "DSC", "distance": 3.4},
                },
            ],
            "angles": [
                {"id": "asc", "zodiac": {"sign": "Cancer"}},
                {"id": "mc", "zodiac": {"sign": "Aries"}},
            ],
            "houseCusps": [{"house": 10, "zodiac": {"sign": "Aries"}}],
            "houseRulerContext": {"summary": "Launch/public: evaluated the 10th ruler."},
            "detectedAspects": [
                {
                    "bodies": ["Venus", "Jupiter"],
                    "aspectName": "Trine",
                    "label": "Venus trine Jupiter",
                    "tone": "support",
                    "orb": 0.4,
                    "orbText": "0 deg 24 min",
                    "isApplying": True,
                },
                {
                    "bodies": ["Moon", "Mars"],
                    "aspectName": "Square",
                    "label": "Moon square Mars",
                    "tone": "stress",
                    "orb": 3.0,
                    "isApplying": False,
                },
            ],
        }

        text = "\n".join(strongest_aspect_analysis_lines(snapshot))

        self.assertIn("Strongest Aspect", text)
        self.assertIn("Venus trine Jupiter", text)
        self.assertIn("House 10", text)
        self.assertIn("Exalted", text)
        self.assertIn("ASC lord Moon", text)
        self.assertIn("10th/MC: Aries", text)
        self.assertIn("10th lord Mars", text)
        self.assertIn("Fall", text)

    def test_compact_judgment_lines_feed_astrolabe_panel(self) -> None:
        snapshot = {
            "positions": [
                {"name": "Venus", "house": 10, "dignity": {"label": "Exalted", "score": 4}},
                {"name": "Jupiter", "house": 1, "dignity": {"label": "Domicile", "score": 5}},
                {"name": "Moon", "house": 9, "dignity": {"label": "Peregrine", "score": 0}},
                {"name": "Mars", "house": 7, "dignity": {"label": "Fall", "score": -4}},
            ],
            "angles": [
                {"id": "asc", "zodiac": {"sign": "Cancer"}},
                {"id": "mc", "zodiac": {"sign": "Aries"}},
            ],
            "detectedAspects": [
                {
                    "bodies": ["Venus", "Jupiter"],
                    "aspectName": "Trine",
                    "label": "Venus trine Jupiter",
                    "tone": "support",
                    "orb": 0.4,
                    "orbText": "0 deg 24 min",
                    "isApplying": True,
                }
            ],
            "scoreBreakdown": {"reasons": [{"label": "Preferred aspect types", "value": 4.0, "count": 1}]},
        }

        lines = compact_judgment_lines(snapshot)
        text = "\n".join(lines)

        self.assertIn("Strongest: Venus trine Jupiter", text)
        self.assertIn("applying", text)
        self.assertIn("ASC lord: Cancer / Moon", text)
        self.assertIn("10th lord: Aries / Mars", text)
        self.assertIn("Top reasons", text)

    def test_center_strongest_aspect_card_is_not_wired(self) -> None:
        self.assertFalse(hasattr(ElectionalDesktopApp, "_build_strongest_aspect_card"))
        self.assertFalse(hasattr(ElectionalDesktopApp, "_refresh_strongest_aspect_card"))

    def test_report_export_includes_aspect_strength_block(self) -> None:
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")
        snapshot = build_snapshot(
            "2026-05-30",
            "11:37",
            location,
            "traditional-lilly",
            ("trine", "sextile", "square", "opposition", "conjunction"),
            "tropical",
            "whole-sign",
            "Launch or publish",
        )
        snapshot.update({"time": "11:37 AM", "title": "Strong election", "note": "Readable report fixture."})

        text = build_report_text(snapshot, [snapshot], location)

        self.assertIn("Aspect strength:", text)
        self.assertIn("Strongest Aspect", text)

    def test_lot_reference_includes_new_hermetic_lots(self) -> None:
        reference = "\n".join(lot_reference_lines())

        self.assertIn("Seven Hermetic Lots", reference)
        self.assertIn("Part of Eros", reference)
        self.assertIn("Part of Nemesis", reference)

    def test_solar_elongation_summary_lists_inner_planets(self) -> None:
        snapshot = {
            "positions": [
                {"name": "Sun", "longitude": 10.0, "zodiac": {"sign": "Aries", "degree": 10, "minute": 0}},
                {"name": "Mercury", "longitude": 18.0, "zodiac": {"sign": "Aries", "degree": 18, "minute": 0}},
                {"name": "Venus", "longitude": 50.0, "zodiac": {"sign": "Taurus", "degree": 20, "minute": 0}},
            ]
        }
        summary = "\n".join(solar_elongation_summary(snapshot))

        self.assertIn("Mercury", summary)
        self.assertIn("Combust", summary)
        self.assertIn("evening", summary)
        self.assertIn("Venus", summary)

    def test_session_state_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "session.json"
            state = {
                "date": "2026-05-26",
                "time": "9:30 PM",
                "location_name": "Paris",
                "latitude": "48.8566",
                "longitude": "2.3522",
                "timezone": "Europe/Paris",
                "scan_hours": "24",
                "step_minutes": "30",
                "search_preset": "Safe Travel",
                "search_quality_mode": "Moon Safe",
                "minimum_score": "70",
                "minimum_confidence": "72",
                "minimum_cleanliness": "69",
                "maximum_volatility": "34",
                "max_results": "12",
                "require_angular_benefic": True,
                "avoid_objective_antipatterns": True,
                "display_options": {
                    "show_aspects": False,
                    "show_score_overlay": False,
                    "show_tools": True,
                    "compact_wheel": True,
                    "wheel_zoom": 0.94,
                    "wheel_export_scale": 4.0,
                    "right_panel_theme": "classic-natal",
                },
            }

            save_session_state(state, path)
            loaded = clean_session_state(load_session_state(path))

        self.assertEqual(loaded["date"], "2026-05-26")
        self.assertEqual(loaded["time"], "21:30")
        self.assertEqual(loaded["timezone"], "Europe/Paris")
        self.assertEqual(loaded["scan_hours"], "24")
        self.assertEqual(loaded["step_minutes"], "30")
        self.assertEqual(loaded["search_preset"], "Safe Travel")
        self.assertEqual(loaded["search_quality_mode"], "Moon Safe")
        self.assertEqual(loaded["minimum_score"], "70")
        self.assertEqual(loaded["minimum_confidence"], "72")
        self.assertEqual(loaded["minimum_cleanliness"], "69")
        self.assertEqual(loaded["maximum_volatility"], "34")
        self.assertEqual(loaded["max_results"], "12")
        self.assertTrue(loaded["require_angular_benefic"])
        self.assertTrue(loaded["avoid_objective_antipatterns"])
        self.assertFalse(loaded["display_options"]["show_aspects"])
        self.assertFalse(loaded["display_options"]["show_score_overlay"])
        self.assertTrue(loaded["display_options"]["show_tools"])
        self.assertTrue(loaded["display_options"]["compact_wheel"])
        self.assertTrue(loaded["display_options"]["show_fixed_stars"])
        self.assertEqual(loaded["display_options"]["wheel_zoom"], 0.94)
        self.assertEqual(loaded["display_options"]["wheel_export_scale"], 4.0)
        self.assertEqual(loaded["display_options"]["point_set"], "full-electional")
        self.assertEqual(loaded["display_options"]["page_mode"], "guide")
        self.assertEqual(loaded["display_options"]["right_panel_theme"], "classic-natal")
        self.assertEqual(loaded["display_options"]["wheel_view_preset"], "full-classic")
        self.assertEqual(loaded["manual_validation_comparison"]["source"], "CapricornPROMETHEUS")

    def test_user_locations_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "locations.json"
            location = LocationPreset("user-home", "Home Base", 33.12, -117.98, "America/Los_Angeles")

            save_user_locations([location], path)
            loaded = load_user_locations(path)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "Home Base")
        self.assertEqual(loaded[0].timezone, "America/Los_Angeles")

    def test_home_location_name_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "location-settings.json"

            save_home_location_name("Temple Office", path)
            loaded = load_home_location_name(path)
            save_home_location_name(None, path)
            cleared = load_home_location_name(path)

        self.assertEqual(loaded, "Temple Office")
        self.assertIsNone(cleared)

    def test_home_location_for_app_prefers_saved_home(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "location-settings.json"
            save_home_location_name("Temple Office", settings_path)
            location = home_location_for_app(
                user_locations=[LocationPreset("user-temple", "Temple Office", 35.0, -120.0, "America/Los_Angeles")],
                settings_path=settings_path,
            )

        self.assertEqual(location.name, "Temple Office")

    def test_city_location_search_finds_indio_and_saved_places(self) -> None:
        saved = [LocationPreset("user-temple", "Temple Office", 35.0, -120.0, "America/Los_Angeles")]
        recent = [LocationPreset("recent-la-quinta", "La Quinta, CA", 33.6634, -116.31, "America/Los_Angeles")]

        indio_results = search_city_locations("Indio", saved_locations=saved, recent_locations=recent)
        saved_results = search_city_locations("Temple", saved_locations=saved, recent_locations=recent)
        recent_results = search_city_locations("La Quinta", saved_locations=saved, recent_locations=recent)
        typo_results = search_city_locations("Indoi", saved_locations=saved, recent_locations=recent)

        self.assertEqual(indio_results[0].location.name, "Indio, CA")
        self.assertEqual(indio_results[0].location.timezone, "America/Los_Angeles")
        self.assertIn("Indio, CA", location_search_result_label(indio_results[0]))
        self.assertEqual(saved_results[0].source, "saved")
        self.assertEqual(recent_results[0].source, "recent")
        self.assertEqual(typo_results[0].location.name, "Indio, CA")

    def test_timezone_warning_flags_bad_place_zone_pairs(self) -> None:
        wrong = LocationPreset("bad-indio", "Indio, CA", 33.7206, -116.2156, "America/New_York")
        right = LocationPreset("good-indio", "Indio, CA", 33.7206, -116.2156, "America/Los_Angeles")

        self.assertEqual(expected_timezone_for_coordinates(33.7206, -116.2156, "Indio, CA"), "America/Los_Angeles")
        self.assertIn("looks closer", timezone_warning_for_location(wrong))
        self.assertIn("Timezone OK", timezone_warning_for_location(right))

    def test_recent_locations_round_trip_and_dedupe(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "location-settings.json"
            indio = LocationPreset("city-indio-ca", "Indio, CA", 33.7206, -116.2156, "America/Los_Angeles")
            paris = LocationPreset("city-paris-france", "Paris, France", 48.8566, 2.3522, "Europe/Paris")

            save_recent_locations([indio], path)
            remembered = remember_recent_location(paris, path)
            remembered = remember_recent_location(indio, path)
            loaded = load_recent_locations(path)

        self.assertEqual([location.name for location in remembered], ["Indio, CA", "Paris, France"])
        self.assertEqual([location.name for location in loaded], ["Indio, CA", "Paris, France"])

    def test_builtin_locations_can_be_hidden_and_reset_without_deleting_them(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "location-settings.json"

            save_hidden_builtin_location_ids({"sydney"}, settings_path)
            hidden = load_hidden_builtin_location_ids(settings_path)
            names = combined_visible_location_names([], hidden)
            resolved = get_location("sydney")
            reset_location_defaults(settings_path)
            reset_hidden = load_hidden_builtin_location_ids(settings_path)

        self.assertIn("sydney", hidden)
        self.assertNotIn("Sydney, Australia", names)
        self.assertEqual(resolved.name, "Sydney, Australia")
        self.assertEqual(reset_hidden, set())

    def test_session_state_infers_full_point_set_from_legacy_lot_display(self) -> None:
        loaded = clean_session_state({"display_options": {"show_lots": True}})

        self.assertEqual(loaded["display_options"]["point_set"], "full-electional")

    def test_session_state_preserves_current_wheel_zoom_range(self) -> None:
        high = clean_session_state({"display_options": {"wheel_zoom": 1.18}})
        low = clean_session_state({"display_options": {"wheel_zoom": 0.5}})
        default = clean_session_state({})

        self.assertEqual(high["display_options"]["wheel_zoom"], 1.18)
        self.assertEqual(low["display_options"]["wheel_zoom"], 0.82)
        self.assertEqual(default["display_options"]["wheel_zoom"], 0.98)
        self.assertEqual(default["display_options"]["right_panel_theme"], "classic-natal")
        self.assertEqual(default["display_options"]["wheel_view_preset"], "full-classic")
        self.assertEqual(default["display_options"]["wheel_export_scale"], 3.0)
        self.assertFalse(default["display_options"]["show_score_overlay"])
        self.assertFalse(default["display_options"]["show_tools"])
        self.assertEqual(default["display_options"]["page_mode"], "guide")

    def test_wheel_canvas_defaults_are_large_enough_for_crisp_desktop_rendering(self) -> None:
        self.assertGreaterEqual(WHEEL_CANVAS_DEFAULT_WIDTH, 1180)
        self.assertGreaterEqual(WHEEL_CANVAS_DEFAULT_HEIGHT, 860)

    def test_session_state_preserves_new_detail_page_modes(self) -> None:
        guide = clean_session_state({"display_options": {"page_mode": "guide"}})
        retrogrades = clean_session_state({"display_options": {"page_mode": "retrogrades"}})
        midpoints = clean_session_state({"display_options": {"page_mode": "midpoints"}})
        live_sky = clean_session_state({"display_options": {"page_mode": "live-sky"}})

        self.assertEqual(guide["display_options"]["page_mode"], "guide")
        self.assertEqual(retrogrades["display_options"]["page_mode"], "retrogrades")
        self.assertEqual(midpoints["display_options"]["page_mode"], "midpoints")
        self.assertEqual(live_sky["display_options"]["page_mode"], "live-sky")

    def test_user_location_upsert_replaces_same_name(self) -> None:
        original = LocationPreset("user-home", "Home Base", 33.0, -118.0, "America/Los_Angeles")
        updated = LocationPreset("user-home", "Home Base", 34.0, -119.0, "America/Los_Angeles")

        locations = upsert_user_location([original], updated)

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].latitude, 34.0)

    def test_medieval_data_page_summarizes_classical_context(self) -> None:
        snapshot = {
            "preset": type("Preset", (), {"name": "Traditional Lilly"})(),
            "zodiacSystem": type("System", (), {"name": "Sidereal Lahiri"})(),
            "houseSystem": type("HouseSystem", (), {"name": "Koch"})(),
            "ayanamsha": 24.1,
            "score": 92,
            "lunarPhase": {"name": "Waxing Gibbous", "illumination": 0.72, "ageDays": 10.2, "isWaxing": True},
            "judgmentContexts": {
                "significatorContext": {"summaryLines": ["- Jupiter signifies launch success."]},
                "moonCondition": {"summaryLines": ["- Moon applies to a benefic."]},
                "houseRulerContext": {"summaryLines": ["- 10th ruler is dignified."]},
                "receptionContext": {"summaryLines": ["- Venus receives Mercury by sign."]},
                "planetConditionContext": {"summaryLines": ["- Jupiter is angular."]},
            },
            "lots": [{"name": "Part of Fortune", "zodiac": {"sign": "Aries", "degree": 12, "minute": 0}, "house": 10, "formula": "ASC + Moon - Sun"}],
        }

        text = build_medieval_data_page(snapshot)

        self.assertIn("Medieval Data Page", text)
        self.assertIn("Traditional Lilly", text)
        self.assertIn("Part of Fortune", text)
        self.assertIn("Verdict", text)
        self.assertIn("Balance of Testimony", text)
        self.assertIn("Moon and Significators", text)

    def test_classical_point_data_page_summarizes_positions_lots_and_nodes(self) -> None:
        snapshot = {
            "preset": type("Preset", (), {"name": "Traditional Lilly"})(),
            "zodiacSystem": type("System", (), {"name": "Sidereal Lahiri"})(),
            "houseSystem": type("HouseSystem", (), {"name": "Koch"})(),
            "ayanamsha": 24.1,
            "score": 92,
            "positions": [
                {
                    "name": "Jupiter",
                    "house": 10,
                    "zodiac": {"sign": "Aries", "degree": 12, "minute": 0},
                    "dignity": {"label": "Domicile", "boundLord": "Jupiter", "isOwnBound": False},
                    "motion": {"label": "Direct", "dailyLongitudeChange": 0.23},
                    "closestAngle": {"shortName": "MC", "distance": 2.1},
                }
            ],
            "angles": [{"shortName": "ASC", "zodiac": {"sign": "Cancer", "degree": 20, "minute": 8}}],
            "houseCusps": [{"house": 10, "zodiac": {"sign": "Aries", "degree": 6, "minute": 32}}],
            "lots": [
                {
                    "name": "Part of Fortune",
                    "zodiac": {"sign": "Aries", "degree": 12, "minute": 0},
                    "house": 10,
                    "formula": "ASC + Moon - Sun",
                    "topic": "Prosperity",
                }
            ],
            "lunarNodes": [
                {
                    "name": "True North Node",
                    "zodiac": {"sign": "Pisces", "degree": 18, "minute": 30},
                    "house": 9,
                    "calculation": "true node",
                }
            ],
            "fixedStarContacts": [{"label": "Venus conjunct Spica", "orbText": "0 deg 14 min", "tone": "support", "score": 4.0}],
        }

        text = build_classical_point_data_page(snapshot)

        self.assertIn("Classical Point Data", text)
        self.assertIn("Jupiter", text)
        self.assertIn("House Cusps", text)
        self.assertIn("Part of Fortune", text)
        self.assertIn("True North Node", text)
        self.assertIn("Venus conjunct Spica", text)

    def test_transit_search_page_summarizes_ranked_windows(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0), "formattedTime": "Tue, May 26, 2026, 9:00 AM PDT"}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "title": "Launch or publish",
            "score": 94,
            "note": "Strong angular benefic support.",
            "detectedAspects": [{"label": "Sun trine Jupiter"}],
            "timingProfile": {"summary": "Next support perfects within the hour."},
            "preset": type("Preset", (), {"name": "Traditional Lilly"})(),
        }
        windows = [selected_window]
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")

        text = build_transit_search_page(input_snapshot, selected_window, windows, location, "Scan 12h from start, every 30m; score >= 70.")

        self.assertIn("Transit Search Page", text)
        self.assertIn("Best Aspect Patterns", text)
        self.assertIn("Difference: +2h", text)
        self.assertIn("Los Angeles, CA", text)
        self.assertIn("Sun trine Jupiter", text)

    def test_transit_search_page_can_include_rejection_reasons(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0), "formattedTime": "Tue, May 26, 2026, 9:00 AM PDT"}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "title": "Launch or publish",
            "score": 94,
            "note": "Strong angular benefic support.",
            "detectedAspects": [{"label": "Sun trine Jupiter"}],
            "timingProfile": {"summary": "Next support perfects within the hour."},
            "preset": type("Preset", (), {"name": "Traditional Lilly"})(),
            "scoreBreakdown": {"diagnostics": {"readiness": {"score": 80, "band": "Strong", "summary": "Ready."}}},
        }
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")
        summary = {
            "count": 2,
            "topReasons": [("major stress present", 2)],
            "suggestedRelaxations": ["Keep No major stress for final picks, but temporarily disable it to see nearby tradeoffs."],
            "samples": [{"formattedTime": "Tue, May 26, 2026, 1:00 PM PDT", "score": 71, "reasons": ["major stress present"]}],
        }

        text = build_transit_search_page(input_snapshot, selected_window, [selected_window], location, "Scan 12h from start.", summary)

        self.assertIn("Rejected Windows", text)
        self.assertIn("major stress present: 2", text)
        self.assertIn("Suggested Relaxations", text)
        self.assertIn("Rejected Samples", text)

    def test_decision_brief_page_translates_score_into_guidance(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0)}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "score": 94,
            "note": "Strong angular benefic support.",
            "detectedAspects": [
                {"label": "Sun trine Jupiter", "tone": "support"},
                {"label": "Mars square Pluto", "tone": "stress"},
            ],
            "timingProfile": {"summary": "Next support perfects within the hour."},
            "scoreBreakdown": {
                "objectiveMatches": 2,
                "evaluation": {
                    "band": "Prime",
                    "grade": "A",
                    "strengths": ["Objective fit +8.0"],
                    "risks": ["Risk pressure -2.0"],
                },
                "reasons": [{"label": "Preferred aspect types", "value": 8.0, "count": 2}],
            },
        }
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")

        text = build_decision_brief_page(input_snapshot, selected_window, "Launch or publish", location)

        self.assertIn("Decision Brief", text)
        self.assertIn("Objective fit: High fit", text)
        self.assertIn("Why It Matches", text)
        self.assertIn("Watchouts", text)
        self.assertIn("Sun trine Jupiter", text)

    def test_decision_brief_page_uses_objective_specific_guidance(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0)}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "score": 83,
            "note": "Strong angular benefic support.",
            "detectedAspects": [{"label": "Venus trine Jupiter", "tone": "support"}],
            "positions": [{"name": "Jupiter", "isAngular": True}],
            "timingProfile": {"summary": "Support perfects soon."},
            "scoreBreakdown": {
                "objectiveMatches": 1,
                "evaluation": {"band": "Strong", "grade": "B", "strengths": ["Objective fit +4.0"], "risks": []},
                "reasons": [{"label": "Preferred aspect types", "value": 4.0, "count": 1}],
            },
        }
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")

        launch_text = build_decision_brief_page(input_snapshot, selected_window, "Launch or publish", location)
        money_text = build_decision_brief_page(input_snapshot, selected_window, "Money or business", location)

        self.assertIn("visibility, momentum", launch_text)
        self.assertIn("steadier value, practical gains", money_text)

    def test_window_comparison_page_summarizes_top_candidates(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0)}
        windows = [
            {
                "date": datetime(2026, 5, 26, 11, 0),
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "score": 94,
                "title": "High-priority election",
                "note": "Strong angular benefic support.",
                "detectedAspects": [{"tone": "support"}],
                "positions": [{"isAngular": True}],
                "timingProfile": {"summary": "Next support perfects within the hour."},
                "scoreBreakdown": {
                    "objectiveMatches": 2,
                    "evaluation": {"band": "Prime", "strengths": ["Objective fit +8.0"], "risks": ["Risk pressure -2.0"]},
                },
            }
        ]

        text = build_window_comparison_page(input_snapshot, windows, "Launch or publish")

        self.assertIn("Candidate Comparison", text)
        self.assertIn("Fit 2", text)
        self.assertIn("Strength: Objective fit +8.0", text)
        self.assertIn("Risk: Risk pressure -2.0", text)

    def test_comparison_export_text_combines_brief_and_comparison(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0)}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "score": 94,
            "title": "High-priority election",
            "note": "Strong angular benefic support.",
            "detectedAspects": [{"label": "Sun trine Jupiter", "tone": "support"}],
            "positions": [{"name": "Jupiter", "isAngular": True}],
            "timingProfile": {"summary": "Next support perfects within the hour."},
            "scoreBreakdown": {
                "objectiveMatches": 2,
                "evaluation": {"band": "Prime", "grade": "A", "strengths": ["Objective fit +8.0"], "risks": []},
                "reasons": [{"label": "Preferred aspect types", "value": 8.0, "count": 2}],
            },
        }
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")
        text = build_comparison_export_text(input_snapshot, selected_window, [selected_window], "Launch or publish", location)

        self.assertIn("Electional Decision Sheet", text)
        self.assertIn("Decision Brief", text)
        self.assertIn("Candidate Comparison", text)

    def test_shortlist_entries_rank_by_quality_not_just_insertion_order(self) -> None:
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")
        stronger = build_shortlist_entry(
            {
                "date": datetime(2026, 5, 26, 11, 0),
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "score": 90,
                "title": "High-priority election",
                "note": "Strong angular benefic support.",
                "lunarPhase": {"name": "Waxing Gibbous", "illumination": 0.7, "ageDays": 10.0, "isWaxing": True},
                "detectedAspects": [],
                "scoreBreakdown": {
                    "diagnostics": {
                        "confidence": {"score": 84},
                        "cleanliness": {"score": 79},
                        "volatility": {"score": 24},
                        "readiness": {"score": 83},
                    }
                },
            },
            location,
            "Launch or publish",
        )
        weaker = build_shortlist_entry(
            {
                "date": datetime(2026, 5, 26, 12, 0),
                "formattedTime": "Tue, May 26, 2026, 12:00 PM PDT",
                "score": 90,
                "title": "High-priority election",
                "note": "More mixed support.",
                "lunarPhase": {"name": "Waxing Gibbous", "illumination": 0.7, "ageDays": 10.0, "isWaxing": True},
                "detectedAspects": [],
                "scoreBreakdown": {
                    "diagnostics": {
                        "confidence": {"score": 68},
                        "cleanliness": {"score": 61},
                        "volatility": {"score": 44},
                        "readiness": {"score": 72},
                    }
                },
            },
            location,
            "Launch or publish",
        )

        ranked = add_shortlist_entry([weaker], stronger)
        text = format_shortlist_entries(ranked)

        self.assertEqual(ranked[0]["formattedTime"], "Tue, May 26, 2026, 11:00 AM PDT")
        self.assertEqual(ranked[0]["latitude"], 34.0522)
        self.assertEqual(ranked[0]["longitude"], -118.2437)
        self.assertIn("Shortlist Diagnostics", text)
        self.assertIn("Best Overall", text)
        self.assertIn("Diagnostics: Conf 84  Clean 79  Read 83  Vol 24", text)

    def test_shortlist_batch_diagnostics_highlight_cleanest_confident_and_steadiest_windows(self) -> None:
        entries = [
            {
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "objective": "Launch or publish",
                "score": 90,
                "confidence": 82,
                "cleanliness": 74,
                "readiness": 79,
                "volatility": 28,
            },
            {
                "formattedTime": "Tue, May 26, 2026, 1:00 PM PDT",
                "objective": "Meeting or negotiation",
                "score": 88,
                "confidence": 91,
                "cleanliness": 86,
                "readiness": 84,
                "volatility": 18,
            },
            {
                "formattedTime": "Tue, May 26, 2026, 3:00 PM PDT",
                "objective": "Travel departure",
                "score": 87,
                "confidence": 73,
                "cleanliness": 80,
                "readiness": 76,
                "volatility": 12,
            },
        ]

        diagnostics = shortlist_batch_diagnostics(entries)
        text = format_shortlist_batch_diagnostics(entries)

        self.assertEqual(diagnostics["count"], 3)
        self.assertEqual(diagnostics["topCleanest"][0]["formattedTime"], "Tue, May 26, 2026, 1:00 PM PDT")
        self.assertEqual(diagnostics["topConfident"][0]["formattedTime"], "Tue, May 26, 2026, 1:00 PM PDT")
        self.assertEqual(diagnostics["topSteady"][0]["formattedTime"], "Tue, May 26, 2026, 3:00 PM PDT")
        self.assertIn("Cleanest Saved Windows", text)
        self.assertIn("Highest-Confidence Windows", text)
        self.assertIn("Steadiest Windows", text)
        self.assertIn("Objective mix:", text)

    def test_shortlist_tags_can_be_added_removed_and_normalized(self) -> None:
        entries = [
            {
                "id": "abc123",
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "score": 90,
                "confidence": 82,
                "cleanliness": 74,
                "readiness": 79,
                "volatility": 28,
                "tags": ["Backup"],
            }
        ]

        tagged = add_shortlist_tag(entries, "abc123", "Client-safe")
        tagged = add_shortlist_tag(tagged, "abc123", "backup")
        normalized = normalize_shortlist_tags([" Backup ", "backup", "", "Client-safe"])
        cleaned = shortlist_entry_by_id(tagged, "abc123")
        removed = remove_shortlist_tag(tagged, "abc123", "Backup")
        retagged = update_shortlist_tags(removed, "abc123", ["Best for launch"])

        self.assertIn("Client-safe", SHORTLIST_TAG_CHOICES)
        self.assertEqual(normalized, ["Backup", "Client-safe"])
        self.assertEqual(cleaned["tags"], ["Backup", "Client-safe"])
        self.assertEqual(shortlist_entry_by_id(removed, "abc123")["tags"], ["Client-safe"])
        self.assertEqual(shortlist_entry_by_id(retagged, "abc123")["tags"], ["Best for launch"])

    def test_shortlist_compare_text_summarizes_two_saved_windows(self) -> None:
        entries = [
            {
                "id": "a1",
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "objective": "Launch or publish",
                "score": 90,
                "confidence": 82,
                "cleanliness": 74,
                "readiness": 79,
                "volatility": 28,
                "note": "Faster launch momentum.",
                "tags": ["Best for launch"],
            },
            {
                "id": "b2",
                "formattedTime": "Tue, May 26, 2026, 1:00 PM PDT",
                "objective": "Meeting or negotiation",
                "score": 88,
                "confidence": 91,
                "cleanliness": 86,
                "readiness": 84,
                "volatility": 18,
                "note": "Cleaner client-facing option.",
                "tags": ["Client-safe"],
            },
        ]

        text = build_shortlist_compare_text(entries, "a1", "b2")

        self.assertIn("Shortlist Compare", text)
        self.assertIn("A: Tue, May 26, 2026, 11:00 AM PDT", text)
        self.assertIn("B: Tue, May 26, 2026, 1:00 PM PDT", text)
        self.assertIn("Metric Edge", text)
        self.assertIn("Volatility: B", text)
        self.assertIn("Tags: Best for launch", text)
        self.assertIn("Tags: Client-safe", text)

    def test_combined_location_names_include_custom_saved_places(self) -> None:
        names = combined_location_names([LocationPreset("user-temple", "Temple Office", 35.0, -120.0, "America/Los_Angeles")])

        self.assertIn("Los Angeles, CA", names)
        self.assertIn("Temple Office", names)


if __name__ == "__main__":
    unittest.main()
