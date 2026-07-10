"""Right judgment, detail notebook, and candidate board methods."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tkinter import filedialog
from .corpus_execution_recovery import build_corpus_repair_plan, build_partial_write_recovery_plan, cancel_corpus_batch_plan, create_corpus_repair_backup, detect_partial_corpus_writes, detect_stale_executions, execute_corpus_repair_plan, format_corpus_execution_report_text, format_corpus_integrity_report_text, get_batch_recovery_state, get_corpus_execution_history, list_quarantined_corpus_records, pause_corpus_batch_plan, resume_corpus_batch_plan, rollback_corpus_repair, validate_batch_action_dependencies, validate_corpus_checkpoint, validate_corpus_index_integrity, verify_corpus_repair_backup
from .document_content_map import build_document_content_map, build_document_scoped_fingerprint, find_related_document_content, format_document_content_map_report, get_document_content_map_summary, get_reader_backend_readiness, validate_document_provenance_contract
from .document_content_curation import build_curated_document_content_map, build_document_content_curation_workspace, format_document_content_curation_report, get_document_content_curation_readiness, get_document_content_curation_summary, load_document_content_curation, normalize_manual_topic_tag, save_document_content_curation_change, validate_content_curation_change
from .document_content_history import compare_document_content_curation_revisions, format_document_content_curation_comparison_report, format_document_content_curation_history_report, format_document_content_curation_restore_report, list_document_content_curation_revisions, restore_document_content_curation_revision
from .document_content_rebase import abandon_document_content_rebase_workspace, apply_document_content_rebase_resolution, commit_document_content_rebase_workspace, create_rebase_workspace_from_current_stale_curation, create_rebase_workspace_from_historical_revision, format_document_content_rebase_report, get_document_content_rebase_readiness, list_document_content_rebase_workspaces, load_document_content_rebase_workspace, refresh_document_content_rebase_conflicts
from .document_content_bulk import add_document_content_bulk_operation, approve_document_content_bulk_plan, clear_document_content_bulk_operations, commit_document_content_bulk_plan, create_document_content_bulk_plan, format_document_content_bulk_report, list_document_content_bulk_review_queue, load_document_content_bulk_plan, preview_document_content_bulk_plan, reject_document_content_bulk_plan, remove_document_content_bulk_operation, replace_document_content_bulk_operation, validate_document_content_bulk_plan
from .document_content_integrity import abandon_document_content_transaction, apply_document_content_recovery_plan, create_document_content_recovery_plan, format_document_content_integrity_report, list_document_content_transactions, load_document_content_recovery_plan, rebuild_document_content_indexes, scan_document_content_integrity
from .backend_contract_validation import build_backend_contract_validation_plan, format_backend_contract_validation_report, get_backend_contract_validation_health, get_backend_contract_validation_summary, load_backend_contract_validation, run_backend_contract_validation
from .pdf_viewport import create_pdf_viewport_session, format_pdf_viewport_report, navigate_pdf_viewport, render_pdf_viewport_page, synchronize_pdf_viewport_to_locator
from .pdf_text_layer import build_pdf_highlight_overlay, extract_pdf_page_text_layer, format_pdf_text_layer_report, format_pdf_text_selection, select_pdf_text_in_rectangle
from .pdf_reader_workspace import build_pdf_reader_workspace_overlay, create_pdf_reader_workspace, draft_citation_from_pdf_selection, format_pdf_reader_workspace_report, load_pdf_reader_workspace, save_pdf_reader_annotation, save_pdf_reader_bookmark
from .citation_draft_review import build_citation_draft_review_workspace, create_citation_from_approved_draft, format_citation_draft_review_report, get_citation_draft_review_health, save_citation_draft_review_decision
from .evidence_handoff_review import build_evidence_handoff_review_workspace, create_proposal_draft_from_evidence_handoff, find_evidence_handoff_binder_candidates, format_evidence_handoff_review_report, insert_handoff_citation_into_binder, save_evidence_handoff_review_decision
from .proposal_promotion import build_proposal_promotion_workspace, format_proposal_promotion_report, get_proposal_promotion_health, promote_approved_proposal, save_proposal_promotion_decision
from .proposal_rule_activation import activate_rule_from_promoted_proposal, build_proposal_rule_activation_workspace, format_proposal_rule_activation_report, rollback_proposal_rule_activation, save_proposal_rule_activation_decision
from .rule_activation_revalidation import build_rule_activation_revalidation_workspace, complete_rule_activation_revalidation, format_rule_activation_revalidation_report, run_rule_runtime_contract_validation, save_rule_activation_revalidation_decision
from .rule_supersession import build_rule_supersession_workspace, format_rule_supersession_report, rollback_rule_supersession, save_rule_supersession_decision, supersede_certified_rule
from .rule_effectiveness_analysis import build_rule_effectiveness_backtest_plan, build_rule_effectiveness_workspace, format_rule_effectiveness_report, get_rule_effectiveness_health, run_rule_effectiveness_backtest
from .rule_effectiveness_recommendation import build_rule_effectiveness_recommendation_workspace, create_rule_action_candidate_from_recommendation, format_rule_effectiveness_recommendation_report, generate_rule_effectiveness_recommendation, save_rule_effectiveness_recommendation_decision
from .rule_batch_analysis import build_rule_batch_plan, build_rule_batch_workspace, cancel_rule_batch_run, format_rule_batch_report, run_rule_batch_analysis
from .autonomous_pdf_certification import build_autonomous_pdf_plan, build_autonomous_pdf_workspace, cancel_autonomous_pdf_pipeline, format_autonomous_pdf_report, get_autonomous_pdf_health, run_autonomous_pdf_pipeline
from .autonomous_pdf_benchmark import build_autonomous_pdf_benchmark_workspace, format_autonomous_pdf_benchmark_report, get_autonomous_pdf_benchmark_health, run_autonomous_pdf_benchmark, validate_autonomous_pdf_benchmark_manifest
from .autonomous_pdf_remediation import build_autonomous_pdf_remediation_workspace, format_autonomous_pdf_remediation_report, review_autonomous_pdf_remediation_case, run_autonomous_pdf_remediation_triage, verify_autonomous_pdf_remediation
from .autonomous_pdf_corrective_action import build_autonomous_pdf_corrective_action_plan, build_autonomous_pdf_corrective_action_workspace, close_autonomous_pdf_corrective_action, execute_autonomous_pdf_corrective_action, format_autonomous_pdf_corrective_action_report, verify_autonomous_pdf_corrective_action
from .certified_rule_replay_adapter import build_certified_rule_replay_plan, build_certified_rule_replay_workspace, format_certified_rule_replay_report, get_certified_rule_replay_health, run_certified_rule_replay, validate_certified_rule_replay_eligibility
from .certified_rule_objective_preview import build_certified_rule_objective_preview_plan, build_certified_rule_objective_preview_workspace, format_certified_rule_objective_preview_report, get_certified_rule_objective_preview_health, run_certified_rule_objective_preview, validate_certified_rule_objective_preview_eligibility
from .certified_rule_scoring_preview import build_certified_rule_scoring_preview_plan, build_certified_rule_scoring_preview_workspace, format_certified_rule_scoring_preview_report, get_certified_rule_scoring_preview_health, run_certified_rule_scoring_preview, validate_certified_rule_scoring_preview_eligibility
from .certified_rule_fast_lane_preview import build_certified_rule_fast_lane_preview_plan, build_certified_rule_fast_lane_preview_workspace, format_certified_rule_fast_lane_preview_report, get_certified_rule_fast_lane_preview_health, run_certified_rule_fast_lane_preview, validate_certified_rule_fast_lane_preview_eligibility
from .certified_rule_integration_authorization import build_certified_rule_integration_authorization_plan, build_certified_rule_integration_authorization_workspace, format_certified_rule_integration_authorization_report, save_certified_rule_integration_authorization_decision, validate_certified_rule_integration_authorization_eligibility
from .certified_rule_release_candidate import build_certified_rule_release_candidate_plan, build_certified_rule_release_candidate_workspace, format_certified_rule_release_candidate_report, qualify_certified_rule_release_candidate, validate_certified_rule_release_candidate_eligibility
from .certified_rule_controlled_integration import build_certified_rule_controlled_integration_plan, build_certified_rule_controlled_integration_workspace, execute_certified_rule_controlled_integration, format_certified_rule_controlled_integration_report, get_certified_rule_controlled_integration_health, validate_certified_rule_controlled_integration_eligibility
from .certified_rule_production_authorization import build_certified_rule_production_authorization_plan, build_certified_rule_production_authorization_workspace, format_certified_rule_production_authorization_report, get_certified_rule_production_authorization_health, save_certified_rule_production_authorization_decision, validate_certified_rule_production_authorization_eligibility
from .certified_rule_production_deployment import build_certified_rule_production_deployment_plan, build_certified_rule_production_deployment_workspace, execute_certified_rule_production_deployment, format_certified_rule_production_deployment_report, get_certified_rule_production_deployment_health, validate_certified_rule_production_deployment_eligibility
from .certified_rule_post_deployment_acceptance import build_certified_rule_post_deployment_acceptance_plan, build_certified_rule_post_deployment_acceptance_workspace, format_certified_rule_post_deployment_acceptance_report, get_certified_rule_post_deployment_acceptance_health, save_certified_rule_post_deployment_acceptance_decision, validate_certified_rule_post_deployment_acceptance_eligibility
from .api import build_deployed_rule_effectiveness_readiness_plan, build_deployed_rule_effectiveness_readiness_workspace, build_deployed_rule_operational_snapshot, build_deployed_rule_operational_telemetry_workspace, format_deployed_rule_effectiveness_readiness_report, format_deployed_rule_operational_telemetry_report, get_deployed_rule_effectiveness_readiness_health, get_deployed_rule_effectiveness_readiness_manifest, get_deployed_rule_operational_telemetry_health, list_deployed_rule_operational_events, load_deployed_rule_effectiveness_readiness_result, record_deployed_rule_effectiveness_readiness_result, validate_deployed_rule_effectiveness_readiness_eligibility, validate_deployed_rule_operational_telemetry_eligibility
from .topic_taxonomy import build_taxonomy_search_expansion, format_topic_taxonomy_report, load_controlled_topic, resolve_controlled_topic_label, save_controlled_topic, validate_topic_taxonomy
from .taxonomy_topic_search import build_taxonomy_topic_search_plan, format_taxonomy_topic_search_report, get_taxonomy_topic_search_health, resolve_taxonomy_search_query, search_taxonomy_aware_topic_content, get_taxonomy_topic_search_summary
from .locator_migration_planner import audit_document_locator_contracts, build_locator_migration_plan, format_locator_migration_report, get_locator_migration_health, load_locator_migration_plan, preview_locator_correction
from .locator_migration_execution import execute_locator_migration_proposal, format_locator_migration_execution_report, get_locator_migration_execution_health, load_locator_migration_execution_receipt, rollback_locator_migration_execution, validate_locator_migration_execution
from .document_manifest import build_document_manifest, format_document_manifest_report, get_document_backend_readiness, get_document_manifest_summary, reconcile_document_subsystems, validate_source_locator
from .source_workflow_coordinator import calculate_pipeline_state_fingerprint, create_source_workflow_plan, execute_source_workflow_stage, format_source_workflow_report, get_source_workflow_resume_state, load_source_workflow_plan, recommend_next_source_workflow_stage
from .source_impact_analysis import analyze_source_change_impact, create_source_revalidation_item, format_source_impact_report_text, list_source_revalidation_queue, update_source_revalidation_status
from .source_revalidation_review import build_revalidation_evidence_recheck, build_revalidation_review_workspace, finalize_source_revalidation_review, format_source_revalidation_resolution_report, load_source_revalidation_resolution
from .source_knowledge import chunk_extracted_text, get_source_knowledge_health
from .source_reliability_manager import detect_duplicate_source_identity, format_source_reliability_report_text, get_source_quality_dashboard, link_source_replacement, recalculate_source_reliability, update_source_metadata_for_reliability

from .source_corpus_manager import build_source_corpus_inventory, bulk_recalculate_source_reliability, bulk_refresh_evidence_binders, detect_corpus_missing_steps, format_source_corpus_report_text, get_source_corpus_health, list_duplicate_source_queue, list_failed_source_tasks, list_superseded_source_queue
from .source_document_reader import build_page_diagnostics, copy_snippet_from_selected_result, create_citation_from_selected_result, create_proposal_from_selected_result, get_document_chunk_text, get_document_page_text, get_document_reader_state, get_source_search_health, mark_selected_result_feedback, run_document_search_for_ui, select_search_result_for_ui
from .document_preflight import can_extract_after_preflight, format_preflight_report_text, get_document_preflight_summary, run_document_preflight
from .document_structure import analyze_chunk_quality, build_document_structure_map, get_document_structure_summary, recommend_rechunk_plan
from .evidence_binder import build_evidence_binder, format_evidence_binder_report_text, get_evidence_binder_summary
from .source_documents import extract_pdf_text, register_pdf_source
from .proposal_review import add_proposal_review_note, apply_proposal_review_ui_action, copy_proposal_review_summary, get_proposal_review_ui_state, select_proposal_for_review_ui


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
        self.pdf_intake_frame = self._more_frame_page("PDF Intake")
        self._build_pdf_intake_page(self.pdf_intake_frame)
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

    def _build_pdf_intake_page(self, parent: tk.Widget) -> None:
        self.pdf_intake_payload: dict[str, object] = {}
        self.pdf_intake_status_var = tk.StringVar(value=self._pdf_intake_status_text())
        tk.Label(
            parent,
            text="PDF Intake",
            bg=PALETTE["panel"],
            fg=PALETTE["accent_dark"],
            font=("Georgia", 11, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 5))
        tk.Label(
            parent,
            text=(
                "Register a source PDF, extract text when possible, and review the result before any future import. "
                "OCR and chart extraction are intentionally not automatic."
            ),
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            font=("Segoe UI", 8),
            wraplength=320,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))
        tk.Label(
            parent,
            textvariable=self.pdf_intake_status_var,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            font=("Segoe UI", 8),
            wraplength=320,
            justify=tk.LEFT,
            anchor="w",
            padx=8,
            pady=7,
        ).pack(fill=tk.X, pady=(0, 8))
        actions = ttk.Frame(parent, style="Panel.TFrame")
        actions.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(actions, text="Choose PDF", command=self._choose_pdf_intake_file, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Register Source", command=self._register_pdf_intake_source, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Run Preflight", command=self._run_pdf_intake_preflight, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Re-run Preflight", command=lambda: self._run_pdf_intake_preflight(regenerate=True), style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Copy Preflight Summary", command=self._copy_pdf_preflight_summary, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Extract Text", command=self._extract_pdf_intake_text, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Chunk Extracted Text", command=self._chunk_pdf_intake_text, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Knowledge Health", command=self._show_pdf_knowledge_health, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Build Page Diagnostics", command=self._build_pdf_page_diagnostics, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Build Structure Map", command=self._build_pdf_structure_map, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Structure Summary", command=self._show_pdf_structure_summary, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Analyze Chunk Quality", command=self._show_pdf_chunk_quality, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Recommend Re-Chunk Plan", command=self._show_pdf_rechunk_plan, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Search Health", command=self._show_pdf_search_health, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Proposal Review Queue", command=self._show_pdf_proposal_review_queue, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Open Extracted Text", command=self._open_pdf_intake_text, style="Compact.TButton").pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Clear PDF", command=self._clear_pdf_intake_file, style="Compact.TButton").pack(fill=tk.X)
        search_box = ttk.Frame(parent, style="Panel.TFrame")
        search_box.pack(fill=tk.X, pady=(0, 8))
        self.pdf_search_query_var = tk.StringVar(value="")
        self.pdf_search_mode_var = tk.StringVar(value="keyword")
        self.pdf_search_limit_var = tk.StringVar(value="20")
        self.pdf_search_proposal_var = tk.StringVar(value="")
        self.pdf_search_citation_var = tk.StringVar(value="")
        self.pdf_search_state: dict[str, object] = {}
        tk.Label(search_box, text="Document Reader / Search", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        tk.Entry(search_box, textvariable=self.pdf_search_query_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 4))
        mode_row = ttk.Frame(search_box, style="Panel.TFrame")
        mode_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Combobox(mode_row, textvariable=self.pdf_search_mode_var, values=("keyword", "exact_phrase", "all_terms", "any_terms"), state="readonly", width=14).pack(side=tk.LEFT, padx=(0, 5))
        tk.Entry(mode_row, textvariable=self.pdf_search_limit_var, width=5, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(side=tk.LEFT)
        ttk.Button(mode_row, text="Search", command=self._run_pdf_document_search, style="Compact.TButton").pack(side=tk.LEFT, padx=(5, 0))
        self.pdf_search_results_list = tk.Listbox(search_box, height=4, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT, exportselection=False)
        self.pdf_search_results_list.pack(fill=tk.X, pady=(0, 5))
        self.pdf_search_results_list.bind("<<ListboxSelect>>", self._on_pdf_search_result_selected)
        self.pdf_selected_result_var = tk.StringVar(value="Selected Result: None\nSelect a search result to review.")
        tk.Label(search_box, textvariable=self.pdf_selected_result_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        tk.Entry(search_box, textvariable=self.pdf_search_proposal_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 4))
        tk.Entry(search_box, textvariable=self.pdf_search_citation_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 4))
        action_row = ttk.Frame(search_box, style="Panel.TFrame")
        action_row.pack(fill=tk.X)
        for label, command in (
            ("Open Chunk", self._open_selected_pdf_chunk),
            ("Open Page", self._open_selected_pdf_page),
            ("Copy Snippet", self._copy_selected_pdf_snippet),
            ("Create Proposal", self._create_selected_pdf_proposal),
            ("Create Citation", self._create_selected_pdf_citation),
            ("Mark Useful", lambda: self._mark_selected_pdf_feedback("useful")),
            ("Bad Extraction", lambda: self._mark_selected_pdf_feedback("bad_extraction")),
        ):
            ttk.Button(action_row, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        reliability_box = ttk.Frame(parent, style="Panel.TFrame")
        reliability_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(reliability_box, text="Source Reliability Manager", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.source_reliability_type_var = tk.StringVar(value="unknown")
        self.source_reliability_authority_var = tk.StringVar(value="unknown")
        self.source_reliability_publication_var = tk.StringVar(value="")
        self.source_reliability_modified_var = tk.StringVar(value="")
        self.source_reliability_title_var = tk.StringVar(value="")
        self.source_reliability_version_var = tk.StringVar(value="")
        self.source_reliability_replacement_var = tk.StringVar(value="")
        ttk.Combobox(reliability_box, textvariable=self.source_reliability_type_var, values=("unknown", "official_policy", "internal_note", "manual_reference", "book", "paper", "web_export", "legal_source", "technical_doc", "user_supplied", "archived_source", "superseded_source"), state="readonly", width=22).pack(fill=tk.X, pady=(4, 3))
        ttk.Combobox(reliability_box, textvariable=self.source_reliability_authority_var, values=("unknown", "low", "medium", "high", "primary", "secondary", "tertiary"), state="readonly", width=22).pack(fill=tk.X, pady=(0, 3))
        for var, label in ((self.source_reliability_publication_var, "Publication Date YYYY-MM-DD"), (self.source_reliability_modified_var, "Modified Date YYYY-MM-DD"), (self.source_reliability_title_var, "Manual Title"), (self.source_reliability_version_var, "Version Label"), (self.source_reliability_replacement_var, "Replacement Source ID")):
            entry = tk.Entry(reliability_box, textvariable=var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT)
            entry.insert(0, "")
            entry.pack(fill=tk.X, pady=(0, 3))
        reliability_actions = ttk.Frame(reliability_box, style="Panel.TFrame")
        reliability_actions.pack(fill=tk.X)
        for label, command in (
            ("Load Reliability", self._load_source_reliability_summary),
            ("Update Metadata", self._update_source_reliability_metadata),
            ("Recalculate Reliability", self._recalculate_source_reliability),
            ("Detect Duplicate Source", self._detect_source_duplicate_identity),
            ("Source Quality Dashboard", self._show_source_quality_dashboard),
            ("Copy Reliability Report", self._copy_source_reliability_report),
            ("Link Replacement", self._link_source_replacement),
        ):
            ttk.Button(reliability_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        corpus_box = ttk.Frame(parent, style="Panel.TFrame")
        corpus_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(corpus_box, text="Source Corpus Manager", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.source_corpus_status_var = tk.StringVar(value="Corpus Health: Unknown\nSources: Unknown\nRecommended Action: Build corpus inventory.")
        tk.Label(corpus_box, textvariable=self.source_corpus_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 5))
        corpus_actions = ttk.Frame(corpus_box, style="Panel.TFrame")
        corpus_actions.pack(fill=tk.X)
        for label, command in (
            ("Build Corpus Inventory", self._build_source_corpus_inventory),
            ("Corpus Health", self._show_source_corpus_health),
            ("Detect Missing Steps", self._show_corpus_missing_steps),
            ("Failed Source Tasks", self._show_failed_source_tasks),
            ("Duplicate Source Queue", self._show_duplicate_source_queue),
            ("Superseded Source Queue", self._show_superseded_source_queue),
            ("Bulk Reliability Recheck", self._bulk_reliability_recheck),
            ("Bulk Evidence Refresh", self._bulk_evidence_refresh),
            ("Copy Corpus Report", self._copy_source_corpus_report),
        ):
            ttk.Button(corpus_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        impact_box = ttk.Frame(parent, style="Panel.TFrame")
        impact_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(impact_box, text="Source Impact Review", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.source_impact_status_var = tk.StringVar(value="Change Type: unknown\nImpact Severity: unknown\nAffected Citations: 0\nAffected Proposals: 0\nAffected Reviews: 0\nAffected Evidence Binders: 0\nRecommended Action: Analyze source impact.")
        self.source_impact_selected_queue_item_id = ""
        tk.Label(impact_box, textvariable=self.source_impact_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 5))
        impact_actions = ttk.Frame(impact_box, style="Panel.TFrame")
        impact_actions.pack(fill=tk.X)
        for label, command in (
            ("Analyze Source Impact", lambda: self._run_source_impact_action("analyze")),
            ("Add to Revalidation Queue", lambda: self._run_source_impact_action("queue")),
            ("View Revalidation Queue", lambda: self._run_source_impact_action("queue_view")),
            ("Mark Selected Reviewed", lambda: self._run_source_impact_action("reviewed")),
            ("Copy Impact Report", lambda: self._run_source_impact_action("copy")),
        ):
            ttk.Button(impact_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        review_box = ttk.Frame(parent, style="Panel.TFrame")
        review_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(review_box, text="Source Revalidation Review", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.source_revalidation_queue_item_var = tk.StringVar(value="")
        self.source_revalidation_decision_var = tk.StringVar(value="keep_open")
        self.source_revalidation_note_var = tk.StringVar(value="")
        self.source_revalidation_citation_disp_var = tk.StringVar(value="unknown")
        self.source_revalidation_proposal_disp_var = tk.StringVar(value="unknown")
        self.source_revalidation_review_disp_var = tk.StringVar(value="unknown")
        self.source_revalidation_binder_disp_var = tk.StringVar(value="unknown")
        self.source_revalidation_workspace_state: dict[str, object] = {}
        tk.Entry(review_box, textvariable=self.source_revalidation_queue_item_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 3))
        ttk.Combobox(review_box, textvariable=self.source_revalidation_decision_var, values=("keep_open", "resolved_no_change", "resolved_with_manual_followup", "replacement_source_required", "deferred", "dismissed"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        tk.Entry(review_box, textvariable=self.source_revalidation_note_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        for var in (
            self.source_revalidation_citation_disp_var,
            self.source_revalidation_proposal_disp_var,
            self.source_revalidation_review_disp_var,
            self.source_revalidation_binder_disp_var,
        ):
            ttk.Combobox(review_box, textvariable=var, values=("still_valid", "needs_review", "invalid_due_to_source", "replacement_source_required", "deferred", "not_applicable", "unknown"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        self.source_revalidation_status_var = tk.StringVar(value="Document ID: unknown\nChange Type: unknown\nImpact Severity: unknown\nQueue Status: unknown\nAffected citation count: 0\nAffected proposal count: 0\nAffected review count: 0\nAffected binder count: 0\nEvidence warnings: 0\nClosure: unknown\nResolution decision: keep_open\nRecommended action: Load a review workspace.")
        tk.Label(review_box, textvariable=self.source_revalidation_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        review_actions = ttk.Frame(review_box, style="Panel.TFrame")
        review_actions.pack(fill=tk.X)
        for label, command in (
            ("Load Review Workspace", lambda: self._run_source_revalidation_action("load")),
            ("Evidence Recheck", lambda: self._run_source_revalidation_action("evidence")),
            ("Finalize Review", lambda: self._run_source_revalidation_action("finalize")),
            ("Load Resolution", lambda: self._run_source_revalidation_action("resolution")),
            ("Copy Resolution Report", lambda: self._run_source_revalidation_action("copy")),
        ):
            ttk.Button(review_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        manifest_box = ttk.Frame(parent, style="Panel.TFrame")
        manifest_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(manifest_box, text="Document Backend Manifest", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.document_manifest_page_var = tk.StringVar(value="")
        self.document_manifest_chunk_var = tk.StringVar(value="")
        self.document_manifest_start_var = tk.StringVar(value="")
        self.document_manifest_end_var = tk.StringVar(value="")
        for var in (self.document_manifest_page_var, self.document_manifest_chunk_var, self.document_manifest_start_var, self.document_manifest_end_var):
            tk.Entry(manifest_box, textvariable=var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4 if var is self.document_manifest_page_var else 0, 3))
        self.document_manifest_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nLifecycle Status: unknown\nBackend Readiness: unknown\nPreflight Status: unknown\nExtraction Status: unknown\nChunk Status: unknown\nDiagnostics Status: unknown\nStructure Status: unknown\nReliability Status: unknown\nStale Component Count: 0\nConsistency Warning Count: 0\nConsistency Critical Count: 0\nRecommended Action: Build the manifest.")
        tk.Label(manifest_box, textvariable=self.document_manifest_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        manifest_actions = ttk.Frame(manifest_box, style="Panel.TFrame")
        manifest_actions.pack(fill=tk.X)
        for label, command in (
            ("Build Manifest", lambda: self._run_document_manifest_action("build")),
            ("Backend Readiness", lambda: self._run_document_manifest_action("readiness")),
            ("Reconcile Subsystems", lambda: self._run_document_manifest_action("reconcile")),
            ("Validate Locator", lambda: self._run_document_manifest_action("locator")),
            ("Copy Manifest Report", lambda: self._run_document_manifest_action("copy")),
        ):
            ttk.Button(manifest_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        workflow_box = ttk.Frame(parent, style="Panel.TFrame")
        workflow_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(workflow_box, text="Source Workflow Coordinator", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.source_workflow_stage_var = tk.StringVar(value="")
        self.source_workflow_dry_run_var = tk.BooleanVar(value=True)
        self.source_workflow_plan_id_var = tk.StringVar(value="")
        ttk.Combobox(workflow_box, textvariable=self.source_workflow_stage_var, values=("", "run_preflight", "extract_text", "chunk_text", "build_page_diagnostics", "build_structure_map", "recalculate_reliability", "refresh_existing_evidence_binders", "refresh_manifest"), state="readonly").pack(fill=tk.X, pady=(4, 3))
        ttk.Checkbutton(workflow_box, text="Dry Run", variable=self.source_workflow_dry_run_var).pack(anchor="w", pady=(0, 3))
        tk.Entry(workflow_box, textvariable=self.source_workflow_plan_id_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        self.source_workflow_status_var = tk.StringVar(value="Document ID: unknown\nPipeline Fingerprint Changed: unknown\nBackend Readiness: unknown\nRecommended Stage: unknown\nDependencies Satisfied: unknown\nSelected Stage: none\nDry Run: True\nPlan Status: unknown\nLast Execution Status: unknown\nNext Recommended Stage: unknown\nRecommended Action: Create a workflow plan.")
        tk.Label(workflow_box, textvariable=self.source_workflow_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        workflow_actions = ttk.Frame(workflow_box, style="Panel.TFrame")
        workflow_actions.pack(fill=tk.X)
        for label, command in (
            ("Pipeline Fingerprint", lambda: self._run_source_workflow_action("fingerprint")),
            ("Recommend Next Stage", lambda: self._run_source_workflow_action("recommend")),
            ("Create Workflow Plan", lambda: self._run_source_workflow_action("plan")),
            ("Execute One Stage", lambda: self._run_source_workflow_action("execute")),
            ("Resume State", lambda: self._run_source_workflow_action("resume")),
            ("Copy Workflow Report", lambda: self._run_source_workflow_action("copy")),
        ):
            ttk.Button(workflow_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        content_box = ttk.Frame(parent, style="Panel.TFrame")
        content_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(content_box, text="Document Content and Reader Readiness", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.document_content_topic_query_var = tk.StringVar(value="")
        self.document_content_topic_terms_var = tk.StringVar(value="")
        tk.Entry(content_box, textvariable=self.document_content_topic_query_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 3))
        tk.Entry(content_box, textvariable=self.document_content_topic_terms_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        self.document_content_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nStructure Status: unknown\nChapter Count: 0\nSection Count: 0\nAssigned Chunk Count: 0\nUnassigned Chunk Count: 0\nTopic Tag Count: 0\nRelated Match Count: 0\nProvenance Status: unknown\nCritical Provenance Count: 0\nReader Readiness: unknown\nRecommended Action: Build the content map.")
        tk.Label(content_box, textvariable=self.document_content_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        content_actions = ttk.Frame(content_box, style="Panel.TFrame")
        content_actions.pack(fill=tk.X)
        for label, command in (
            ("Build Content Map", lambda: self._run_document_content_action("build")),
            ("Find Related Content", lambda: self._run_document_content_action("related")),
            ("Validate Provenance", lambda: self._run_document_content_action("provenance")),
            ("Reader Readiness", lambda: self._run_document_content_action("readiness")),
            ("Document Fingerprint", lambda: self._run_document_content_action("fingerprint")),
            ("Copy Content Report", lambda: self._run_document_content_action("copy")),
        ):
            ttk.Button(content_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        curation_box = ttk.Frame(parent, style="Panel.TFrame")
        curation_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(curation_box, text="Document Content Curation", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.document_curation_target_type_var = tk.StringVar(value="section")
        self.document_curation_target_id_var = tk.StringVar(value="")
        self.document_curation_operation_var = tk.StringVar(value="rename")
        self.document_curation_title_var = tk.StringVar(value="")
        self.document_curation_start_page_var = tk.StringVar(value="")
        self.document_curation_end_page_var = tk.StringVar(value="")
        self.document_curation_start_chunk_var = tk.StringVar(value="")
        self.document_curation_end_chunk_var = tk.StringVar(value="")
        self.document_curation_chunk_id_var = tk.StringVar(value="")
        self.document_curation_topic_tag_var = tk.StringVar(value="")
        self.document_curation_note_var = tk.StringVar(value="")
        ttk.Combobox(curation_box, textvariable=self.document_curation_target_type_var, values=("chapter", "section", "chunk"), state="readonly").pack(fill=tk.X, pady=(4, 3))
        tk.Entry(curation_box, textvariable=self.document_curation_target_id_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        ttk.Combobox(curation_box, textvariable=self.document_curation_operation_var, values=("rename", "set_range", "assign_chunk", "unassign_chunk", "add_tag", "remove_tag"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        for variable in (
            self.document_curation_title_var,
            self.document_curation_start_page_var,
            self.document_curation_end_page_var,
            self.document_curation_start_chunk_var,
            self.document_curation_end_chunk_var,
            self.document_curation_chunk_id_var,
            self.document_curation_topic_tag_var,
            self.document_curation_note_var,
        ):
            tk.Entry(curation_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        self.document_curation_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nBase Fingerprint Current: unknown\nCuration Revision: 0\nCuration Status: not_started\nCuration Readiness: not_ready\nOverride Count: 0\nValid Change Count: 0\nInvalid Change Count: 0\nAssigned Chunk Count: 0\nUnassigned Chunk Count: 0\nManual Tag Count: 0\nRecommended Action: Build the detected content map first.")
        tk.Label(curation_box, textvariable=self.document_curation_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        curation_actions = ttk.Frame(curation_box, style="Panel.TFrame")
        curation_actions.pack(fill=tk.X)
        for label, command in (
            ("Load Curation Workspace", lambda: self._run_document_content_curation_action("workspace")),
            ("Validate Change", lambda: self._run_document_content_curation_action("validate")),
            ("Save Override", lambda: self._run_document_content_curation_action("save")),
            ("Build Curated Map", lambda: self._run_document_content_curation_action("build")),
            ("Curation Readiness", lambda: self._run_document_content_curation_action("readiness")),
            ("Copy Curation Report", lambda: self._run_document_content_curation_action("copy")),
        ):
            ttk.Button(curation_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        history_box = ttk.Frame(parent, style="Panel.TFrame")
        history_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(history_box, text="Curation History", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.document_curation_history_left_var = tk.StringVar(value="1")
        self.document_curation_history_right_var = tk.StringVar(value="1")
        self.document_curation_history_restore_var = tk.StringVar(value="1")
        tk.Entry(history_box, textvariable=self.document_curation_history_left_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 3))
        tk.Entry(history_box, textvariable=self.document_curation_history_right_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        tk.Entry(history_box, textvariable=self.document_curation_history_restore_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        self.document_curation_history_status_var = tk.StringVar(value="Revision Count: 0\nCurrent Revision: 0\nLatest Status: unknown\nLatest Warnings: 0")
        tk.Label(history_box, textvariable=self.document_curation_history_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        history_actions = ttk.Frame(history_box, style="Panel.TFrame")
        history_actions.pack(fill=tk.X)
        for label, command in (
            ("View Curation History", lambda: self._run_document_content_history_action("list")),
            ("Compare Revisions", lambda: self._run_document_content_history_action("compare")),
            ("Restore Revision", lambda: self._run_document_content_history_action("restore")),
            ("Copy Revision Report", lambda: self._run_document_content_history_action("copy")),
        ):
            ttk.Button(history_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        rebase_box = ttk.Frame(parent, style="Panel.TFrame")
        rebase_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(rebase_box, text="Stale Curation Rebase", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.document_curation_rebase_workspace_var = tk.StringVar(value="")
        self.document_curation_rebase_history_var = tk.StringVar(value="1")
        self.document_curation_rebase_conflict_var = tk.StringVar(value="")
        self.document_curation_rebase_action_var = tk.StringVar(value="drop")
        self.document_curation_rebase_target_var = tk.StringVar(value="")
        self.document_curation_rebase_start_page_var = tk.StringVar(value="")
        self.document_curation_rebase_end_page_var = tk.StringVar(value="")
        for variable in (
            self.document_curation_rebase_workspace_var,
            self.document_curation_rebase_history_var,
            self.document_curation_rebase_conflict_var,
            self.document_curation_rebase_target_var,
            self.document_curation_rebase_start_page_var,
            self.document_curation_rebase_end_page_var,
        ):
            tk.Entry(rebase_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4 if variable is self.document_curation_rebase_workspace_var else 0, 3))
        ttk.Combobox(rebase_box, textvariable=self.document_curation_rebase_action_var, values=("drop", "keep", "remap_chapter", "remap_section", "remap_chunk", "replace_chapter_range", "replace_section_range", "replace_assignment_target", "remove_assignment", "keep_manual_tag_override", "drop_manual_tag_override"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        self.document_curation_rebase_status_var = tk.StringVar(value="Workspace ID: unknown\nWorkspace Status: unknown\nSource Type: unknown\nConflict Count: 0\nUnresolved Blockers: 0\nReadiness: unknown")
        tk.Label(rebase_box, textvariable=self.document_curation_rebase_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        rebase_actions = ttk.Frame(rebase_box, style="Panel.TFrame")
        rebase_actions.pack(fill=tk.X)
        for label, command in (
            ("Create Rebase Workspace", lambda: self._run_document_content_rebase_action("create_current")),
            ("Load Rebase Workspace", lambda: self._run_document_content_rebase_action("load")),
            ("Detect Conflicts", lambda: self._run_document_content_rebase_action("refresh")),
            ("Resolve Conflict", lambda: self._run_document_content_rebase_action("resolve")),
            ("Rebase Readiness", lambda: self._run_document_content_rebase_action("readiness")),
            ("Commit Rebase", lambda: self._run_document_content_rebase_action("commit")),
            ("Abandon Rebase", lambda: self._run_document_content_rebase_action("abandon")),
            ("Copy Rebase Report", lambda: self._run_document_content_rebase_action("copy")),
        ):
            ttk.Button(rebase_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        bulk_box = ttk.Frame(parent, style="Panel.TFrame")
        bulk_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(bulk_box, text="Bulk Curation Review", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.document_curation_bulk_batch_var = tk.StringVar(value="")
        self.document_curation_bulk_operation_id_var = tk.StringVar(value="")
        self.document_curation_bulk_operation_var = tk.StringVar(value='{"operation_type":"add_tag_many","chunk_ids":[],"tag":""}')
        self.document_curation_bulk_reject_reason_var = tk.StringVar(value="")
        for variable in (
            self.document_curation_bulk_batch_var,
            self.document_curation_bulk_operation_id_var,
            self.document_curation_bulk_operation_var,
            self.document_curation_bulk_reject_reason_var,
        ):
            tk.Entry(bulk_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4 if variable is self.document_curation_bulk_batch_var else 0, 3))
        self.document_curation_bulk_status_var = tk.StringVar(value="Batch ID: unknown\nBatch Revision: 0\nStatus: unknown\nOperation Count: 0\nEffective Change Count: 0\nUnchanged Count: 0\nBlocker Count: 0\nWarning Count: 0\nApproved: False")
        tk.Label(bulk_box, textvariable=self.document_curation_bulk_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        bulk_actions = ttk.Frame(bulk_box, style="Panel.TFrame")
        bulk_actions.pack(fill=tk.X)
        for label, command in (
            ("Create Bulk Plan", lambda: self._run_document_content_bulk_action("create")),
            ("Load Bulk Plan", lambda: self._run_document_content_bulk_action("load")),
            ("Add Operation", lambda: self._run_document_content_bulk_action("add")),
            ("Remove Operation", lambda: self._run_document_content_bulk_action("remove")),
            ("Replace Operation", lambda: self._run_document_content_bulk_action("replace")),
            ("Clear Operations", lambda: self._run_document_content_bulk_action("clear")),
            ("Preview Bulk Plan", lambda: self._run_document_content_bulk_action("preview")),
            ("Validate Bulk Plan", lambda: self._run_document_content_bulk_action("validate")),
            ("Review Queue", lambda: self._run_document_content_bulk_action("queue")),
            ("Approve Bulk Plan", lambda: self._run_document_content_bulk_action("approve")),
            ("Reject Bulk Plan", lambda: self._run_document_content_bulk_action("reject")),
            ("Commit Bulk Plan", lambda: self._run_document_content_bulk_action("commit")),
            ("Copy Bulk Report", lambda: self._run_document_content_bulk_action("copy")),
        ):
            ttk.Button(bulk_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        integrity_box = ttk.Frame(parent, style="Panel.TFrame")
        integrity_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(integrity_box, text="Content Integrity and Recovery", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.document_curation_integrity_transaction_var = tk.StringVar(value="")
        self.document_curation_integrity_plan_var = tk.StringVar(value="")
        for variable in (self.document_curation_integrity_transaction_var, self.document_curation_integrity_plan_var):
            tk.Entry(integrity_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4 if variable is self.document_curation_integrity_transaction_var else 0, 3))
        self.document_curation_integrity_status_var = tk.StringVar(value="Critical: 0\nHigh: 0\nRecoverable: 0\nConflicts: 0\nPending Transactions: 0\nRecovery Status: unknown\nLast Reconciled Revision: 0")
        tk.Label(integrity_box, textvariable=self.document_curation_integrity_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        integrity_actions = ttk.Frame(integrity_box, style="Panel.TFrame")
        integrity_actions.pack(fill=tk.X)
        for label, command in (
            ("Scan Integrity", lambda: self._run_document_content_integrity_action("scan")),
            ("View Pending Transactions", lambda: self._run_document_content_integrity_action("transactions")),
            ("Build Recovery Plan", lambda: self._run_document_content_integrity_action("plan")),
            ("Load Recovery Plan", lambda: self._run_document_content_integrity_action("load_plan")),
            ("Apply Recovery Plan", lambda: self._run_document_content_integrity_action("apply")),
            ("Abandon Prepared Transaction", lambda: self._run_document_content_integrity_action("abandon")),
            ("Rebuild Indexes", lambda: self._run_document_content_integrity_action("rebuild")),
            ("Copy Integrity Report", lambda: self._run_document_content_integrity_action("copy")),
        ):
            ttk.Button(integrity_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        contract_box = ttk.Frame(parent, style="Panel.TFrame")
        contract_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(contract_box, text="Backend Contract Certification", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.backend_contract_validation_id_var = tk.StringVar(value="")
        self.backend_contract_regenerate_var = tk.BooleanVar(value=False)
        tk.Entry(contract_box, textvariable=self.backend_contract_validation_id_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 3))
        ttk.Checkbutton(contract_box, text="Regenerate", variable=self.backend_contract_regenerate_var).pack(anchor="w", pady=(0, 4))
        self.backend_contract_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nCertification Status: unknown\nValidation Current: unknown\nRequired Pass Count: 0\nWarning Count: 0\nFailure Count: 0\nBlocked Count: 0\nReader Backend Readiness: unknown\nCitation Count: 0\nEvidence Binder Count: 0\nPending Revalidation Count: 0\nRollback Failure Count: 0\nRecommended Action: Run contract validation for one registered document.")
        tk.Label(contract_box, textvariable=self.backend_contract_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        contract_actions = ttk.Frame(contract_box, style="Panel.TFrame")
        contract_actions.pack(fill=tk.X)
        for label, command in (
            ("Build Validation Plan", lambda: self._run_backend_contract_validation_action("plan")),
            ("Run Contract Validation", lambda: self._run_backend_contract_validation_action("run")),
            ("Load Validation", lambda: self._run_backend_contract_validation_action("load")),
            ("Validation Health", lambda: self._run_backend_contract_validation_action("health")),
            ("Copy Certification Report", lambda: self._run_backend_contract_validation_action("copy")),
        ):
            ttk.Button(contract_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        viewport_box = ttk.Frame(parent, style="Panel.TFrame")
        viewport_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(viewport_box, text="Certified PDF Viewport", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.pdf_viewport_id_var = tk.StringVar(value="")
        self.pdf_reader_workspace_id_var = tk.StringVar(value="")
        self.pdf_viewport_jump_page_var = tk.StringVar(value="1")
        self.pdf_viewport_zoom_var = tk.StringVar(value="100")
        self.pdf_viewport_locator_var = tk.StringVar(value='{"document_id":"","source_revision":0,"page":1}')
        self.pdf_viewport_selection_mode_var = tk.StringVar(value="intersect")
        self.pdf_reader_bookmark_label_var = tk.StringVar(value="")
        self.pdf_reader_annotation_type_var = tk.StringVar(value="highlight")
        self.pdf_reader_annotation_note_var = tk.StringVar(value="")
        self.pdf_reader_citation_note_var = tk.StringVar(value="")
        self.citation_review_workspace_id_var = tk.StringVar(value="")
        self.citation_review_draft_id_var = tk.StringVar(value="")
        self.citation_review_id_var = tk.StringVar(value="")
        self.citation_review_decision_var = tk.StringVar(value="approve")
        self.citation_review_note_var = tk.StringVar(value="")
        self.citation_review_confirmation_var = tk.StringVar(value="")
        self.citation_review_allow_near_duplicate_var = tk.BooleanVar(value=False)
        self.evidence_handoff_id_var = tk.StringVar(value="")
        self.evidence_handoff_review_id_var = tk.StringVar(value="")
        self.evidence_handoff_decision_var = tk.StringVar(value="approve_binder_insert")
        self.evidence_handoff_target_binder_var = tk.StringVar(value="")
        self.evidence_handoff_note_var = tk.StringVar(value="")
        self.evidence_handoff_confirmation_var = tk.StringVar(value="")
        self.proposal_promotion_proposal_id_var = tk.StringVar(value="")
        self.proposal_promotion_review_id_var = tk.StringVar(value="")
        self.proposal_promotion_decision_var = tk.StringVar(value="approve")
        self.proposal_promotion_note_var = tk.StringVar(value="")
        self.proposal_promotion_confirmation_var = tk.StringVar(value="")
        self.proposal_promotion_ack_near_duplicate_var = tk.BooleanVar(value=False)
        self.proposal_promotion_ack_conflict_var = tk.BooleanVar(value=False)
        self.rule_activation_proposal_id_var = tk.StringVar(value="")
        self.rule_activation_review_id_var = tk.StringVar(value="")
        self.rule_activation_decision_var = tk.StringVar(value="approve")
        self.rule_activation_note_var = tk.StringVar(value="")
        self.rule_activation_ack_inactive_var = tk.BooleanVar(value=False)
        self.rule_activation_ack_conflict_var = tk.BooleanVar(value=False)
        self.rule_activation_receipt_id_var = tk.StringVar(value="")
        self.rule_activation_confirmation_var = tk.StringVar(value="")
        self.rule_activation_rollback_confirmation_var = tk.StringVar(value="")
        self.rule_revalidation_id_var = tk.StringVar(value="")
        self.rule_revalidation_review_id_var = tk.StringVar(value="")
        self.rule_revalidation_decision_var = tk.StringVar(value="certify")
        self.rule_revalidation_note_var = tk.StringVar(value="")
        self.rule_revalidation_completion_confirmation_var = tk.StringVar(value="")
        self.rule_revalidation_receipt_id_var = tk.StringVar(value="")
        self.rule_supersession_old_rule_id_var = tk.StringVar(value="")
        self.rule_supersession_proposal_id_var = tk.StringVar(value="")
        self.rule_supersession_review_id_var = tk.StringVar(value="")
        self.rule_supersession_decision_var = tk.StringVar(value="approve")
        self.rule_supersession_note_var = tk.StringVar(value="")
        self.rule_supersession_receipt_id_var = tk.StringVar(value="")
        self.rule_supersession_confirmation_var = tk.StringVar(value="")
        self.rule_supersession_rollback_confirmation_var = tk.StringVar(value="")
        self.rule_supersession_ack_scope_var = tk.BooleanVar(value=False)
        self.rule_effectiveness_rule_id_var = tk.StringVar(value="")
        self.rule_effectiveness_dataset_id_var = tk.StringVar(value="")
        self.rule_effectiveness_comparison_rule_id_var = tk.StringVar(value="")
        self.rule_effectiveness_max_records_var = tk.StringVar(value="200")
        self.rule_effectiveness_regenerate_var = tk.BooleanVar(value=False)
        self.rule_effectiveness_recommendation_analysis_id_var = tk.StringVar(value="")
        self.rule_effectiveness_recommendation_policy_id_var = tk.StringVar(value="default_v1")
        self.rule_effectiveness_recommendation_id_var = tk.StringVar(value="")
        self.rule_effectiveness_recommendation_decision_var = tk.StringVar(value="accept")
        self.rule_effectiveness_recommendation_note_var = tk.StringVar(value="")
        self.rule_effectiveness_recommendation_review_id_var = tk.StringVar(value="")
        self.rule_effectiveness_recommendation_action_candidate_id_var = tk.StringVar(value="")
        self.rule_effectiveness_recommendation_queue_confirmation_var = tk.StringVar(value="")
        self.rule_batch_document_id_var = tk.StringVar(value="")
        self.rule_batch_source_revision_var = tk.StringVar(value="")
        self.rule_batch_dataset_id_var = tk.StringVar(value="")
        self.rule_batch_policy_id_var = tk.StringVar(value="default_v1")
        self.rule_batch_rule_ids_var = tk.StringVar(value="")
        self.rule_batch_include_active_var = tk.BooleanVar(value=True)
        self.rule_batch_max_rules_var = tk.StringVar(value="10")
        self.rule_batch_max_records_var = tk.StringVar(value="200")
        self.rule_batch_plan_id_var = tk.StringVar(value="")
        self.rule_batch_run_id_var = tk.StringVar(value="")
        self.rule_batch_stop_after_items_var = tk.StringVar(value="")
        self.rule_batch_cancellation_reason_var = tk.StringVar(value="")
        self.autonomous_pdf_document_id_var = tk.StringVar(value="")
        self.autonomous_pdf_source_revision_var = tk.StringVar(value="")
        self.autonomous_pdf_max_pages_var = tk.StringVar(value="300")
        self.autonomous_pdf_max_harvest_candidates_var = tk.StringVar(value="50")
        self.autonomous_pdf_max_proposal_candidates_var = tk.StringVar(value="20")
        self.autonomous_pdf_max_rule_candidates_var = tk.StringVar(value="10")
        self.autonomous_pdf_max_certified_rules_var = tk.StringVar(value="5")
        self.autonomous_pdf_plan_id_var = tk.StringVar(value="")
        self.autonomous_pdf_run_id_var = tk.StringVar(value="")
        self.autonomous_pdf_stop_after_stage_var = tk.StringVar(value="")
        self.autonomous_pdf_confirmation_var = tk.StringVar(value="AUTO_RUN")
        self.autonomous_pdf_cancellation_reason_var = tk.StringVar(value="")
        self.autonomous_pdf_benchmark_id_var = tk.StringVar(value="")
        self.autonomous_pdf_benchmark_run_id_var = tk.StringVar(value="")
        self.autonomous_pdf_benchmark_result_id_var = tk.StringVar(value="")
        self.autonomous_pdf_benchmark_receipt_id_var = tk.StringVar(value="")
        self.autonomous_pdf_benchmark_confirmation_var = tk.StringVar(value="BENCHMARK")
        self.autonomous_pdf_remediation_plan_id_var = tk.StringVar(value="")
        self.autonomous_pdf_remediation_case_id_var = tk.StringVar(value="")
        self.autonomous_pdf_remediation_new_result_id_var = tk.StringVar(value="")
        self.autonomous_pdf_remediation_review_decision_var = tk.StringVar(value="accept_for_targeted_fix")
        self.autonomous_pdf_remediation_review_note_var = tk.StringVar(value="")
        self.autonomous_pdf_remediation_confirmation_var = tk.StringVar(value="")
        self.autonomous_pdf_remediation_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nOriginal Release Classification: unknown\nPlan Status: unknown\nTotal Case Count: 0\nCritical Case Count: 0\nHigh Case Count: 0\nUnresolved Case Count: 0\nReviewed Case Count: 0\nResolved Case Count: 0\nPersisting Case Count: 0\nRegressed Case Count: 0\nRecommended Action: Load one benchmark result to start remediation.")
        self.autonomous_pdf_corrective_action_id_var = tk.StringVar(value="")
        self.autonomous_pdf_corrective_action_type_var = tk.StringVar(value="close_no_action")
        self.autonomous_pdf_corrective_action_payload_var = tk.StringVar(value="{}")
        self.autonomous_pdf_corrective_action_confirmation_var = tk.StringVar(value="")
        self.autonomous_pdf_corrective_action_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nReview Decision: unknown\nRoot-Cause Classification: unknown\nAction Type: unknown\nAction Status: unknown\nVerification Required: No\nVerification Outcome: none\nClosure Status: open\nRemaining Blockers: none\nRecommended Action: Load one remediation case to start corrective action.")
        self.certified_rule_replay_rule_id_var = tk.StringVar(value="")
        self.certified_rule_replay_dataset_id_var = tk.StringVar(value="")
        self.certified_rule_replay_max_records_var = tk.StringVar(value="10000")
        self.certified_rule_replay_plan_id_var = tk.StringVar(value="")
        self.certified_rule_replay_result_id_var = tk.StringVar(value="")
        self.certified_rule_replay_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_replay_confirmation_var = tk.StringVar(value="RUN_REPLAY")
        self.certified_rule_replay_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nRule Status: unknown\nCertification Status: unknown\nDataset Fingerprint Status: unknown\nReplay Status: unknown\nTotal Records: 0\nEvaluated Records: 0\nMatch Count: 0\nNo-Match Count: 0\nUnsupported Count: 0\nError Count: 0\nReplay Coverage: null\nCompatibility Rate: null\nRecommended Action: Load one rule workspace to start replay.")
        self.certified_rule_objective_preview_rule_id_var = tk.StringVar(value="")
        self.certified_rule_objective_preview_pack_id_var = tk.StringVar(value="")
        self.certified_rule_objective_preview_input_id_var = tk.StringVar(value="")
        self.certified_rule_objective_preview_max_records_var = tk.StringVar(value="10000")
        self.certified_rule_objective_preview_mapping_var = tk.StringVar(value='{"mapping_version":"rule_effect_mapping_v1","on_match":{"values":{"eligible_action":true}},"on_no_match":{"mode":"preserve_baseline"}}')
        self.certified_rule_objective_preview_plan_id_var = tk.StringVar(value="")
        self.certified_rule_objective_preview_result_id_var = tk.StringVar(value="")
        self.certified_rule_objective_preview_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_objective_preview_confirmation_var = tk.StringVar(value="RUN_OBJECTIVE_PREVIEW")
        self.certified_rule_objective_preview_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nRule Status: unknown\nCertification Status: unknown\nObjective Pack Status: unknown\nControlled Input Status: unknown\nPreview Status: unknown\nCompared Records: 0\nImproved Records: 0\nWorsened Records: 0\nUnsupported Records: 0\nPreview Coverage: null\nCompatibility Rate: null\nRecommended Action: Load one rule workspace to start objective preview.")
        self.certified_rule_scoring_preview_objective_result_id_var = tk.StringVar(value="")
        self.certified_rule_scoring_preview_config_id_var = tk.StringVar(value="")
        self.certified_rule_scoring_preview_plan_id_var = tk.StringVar(value="")
        self.certified_rule_scoring_preview_result_id_var = tk.StringVar(value="")
        self.certified_rule_scoring_preview_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_scoring_preview_confirmation_var = tk.StringVar(value="RUN_SCORING_PREVIEW")
        self.certified_rule_scoring_preview_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nCanonical Rule ID: unknown\nCertification Status: unknown\nObjective Preview Status: unknown\nPhase 9O Compatibility: unknown\nScoring Configuration Status: unknown\nCompatibility Status: unknown\nScoring Preview Status: unknown\nTotal Records: 0\nScoreable Records: 0\nCompared Records: 0\nIncreased Records: 0\nDecreased Records: 0\nUnchanged Records: 0\nMixed Records: 0\nUnsupported Records: 0\nError Count: 0\nBaseline Mean Score: null\nRule-Enabled Mean Score: null\nMean Score Delta: null\nScoring Coverage: null\nRecommended Action: Load one objective preview result to start scoring preview.")
        self.certified_rule_fast_lane_preview_rule_id_var = tk.StringVar(value="")
        self.certified_rule_fast_lane_preview_plan_id_var = tk.StringVar(value="")
        self.certified_rule_fast_lane_preview_result_id_var = tk.StringVar(value="")
        self.certified_rule_fast_lane_preview_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_fast_lane_preview_confirmation_var = tk.StringVar(value="RUN_FAST_LANE_COMPATIBILITY_PREVIEW")
        self.certified_rule_fast_lane_preview_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nCertification Status: unknown\nFast Lane Contract ID: unknown\nFast Lane Contract Version: unknown\nCapability Status: unknown\nPreview Status: unknown\nOverall Compatibility: unknown\nSemantic Loss: unknown\nCompatible Dimensions: 0\nWarning Dimensions: 0\nIncompatible Dimensions: 0\nBlocker Count: 0\nWarning Count: 0\nRecommended Action: Load one certified rule to start Fast Lane compatibility preview.")
        self.certified_rule_integration_authorization_rule_id_var = tk.StringVar(value="")
        self.certified_rule_integration_authorization_scoring_result_id_var = tk.StringVar(value="")
        self.certified_rule_integration_authorization_fast_lane_result_id_var = tk.StringVar(value="")
        self.certified_rule_integration_authorization_plan_id_var = tk.StringVar(value="")
        self.certified_rule_integration_authorization_result_id_var = tk.StringVar(value="")
        self.certified_rule_integration_authorization_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_integration_authorization_reviewer_var = tk.StringVar(value="")
        self.certified_rule_integration_authorization_decision_var = tk.StringVar(value="defer_integration")
        self.certified_rule_integration_authorization_rationale_var = tk.StringVar(value="")
        self.certified_rule_integration_authorization_ack_var = tk.StringVar(value="reviewed_scoring_preview, reviewed_fast_lane_preview")
        self.certified_rule_integration_authorization_confirmation_var = tk.StringVar(value="SAVE_INTEGRATION_AUTHORIZATION")
        self.certified_rule_integration_authorization_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nCanonical Rule ID: unknown\nCertification Status: unknown\nScoring Preview Status: unknown\nFast Lane Preview Status: unknown\nOverall Compatibility: unknown\nSemantic Loss: unknown\nDecision Status: unknown\nReviewer: none\nBlocker Count: 0\nWarning Count: 0\nRecommended Action: Load one certified rule and current preview evidence to start authorization review.")
        self.certified_rule_release_candidate_rule_id_var = tk.StringVar(value="")
        self.certified_rule_release_candidate_authorization_result_id_var = tk.StringVar(value="")
        self.certified_rule_release_candidate_plan_id_var = tk.StringVar(value="")
        self.certified_rule_release_candidate_result_id_var = tk.StringVar(value="")
        self.certified_rule_release_candidate_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_release_candidate_confirmation_var = tk.StringVar(value="QUALIFY_RELEASE_CANDIDATE")
        self.certified_rule_release_candidate_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nCanonical Rule ID: unknown\nAuthorization Status: unknown\nScoring Evidence Status: unknown\nCompatibility Evidence Status: unknown\nEligibility Status: unknown\nQualification Status: unknown\nBlocker Count: 0\nWarning Count: 0\nRecommended Action: Load one authorized integration result to start release-candidate qualification.")
        self.certified_rule_controlled_integration_rule_id_var = tk.StringVar(value="")
        self.certified_rule_controlled_integration_release_result_id_var = tk.StringVar(value="")
        self.certified_rule_controlled_integration_target_id_var = tk.StringVar(value="controlled_staging_primary")
        self.certified_rule_controlled_integration_plan_id_var = tk.StringVar(value="")
        self.certified_rule_controlled_integration_result_id_var = tk.StringVar(value="")
        self.certified_rule_controlled_integration_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_controlled_integration_confirmation_var = tk.StringVar(value="EXECUTE_CONTROLLED_INTEGRATION")
        self.certified_rule_controlled_integration_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nCertification Status: unknown\nRelease Candidate Status: unknown\nAuthorization Status: unknown\nTarget Status: unknown\nEnvironment Class: unknown\nAdapter Version: unknown\nNamespace ID: unknown\nTransaction ID: unknown\nExecution Status: unknown\nPending Verification: unknown\nCommitted Verification: unknown\nRollback Status: unknown\nProduction Safety: unknown\nStale Status: unknown\nBlocker Count: 0\nWarning Count: 0\nRecommended Action: Load one qualified release candidate and explicit target to start controlled integration.")
        self.certified_rule_production_authorization_rule_id_var = tk.StringVar(value="")
        self.certified_rule_production_authorization_integration_result_id_var = tk.StringVar(value="")
        self.certified_rule_production_authorization_target_id_var = tk.StringVar(value="production_target_primary")
        self.certified_rule_production_authorization_plan_id_var = tk.StringVar(value="")
        self.certified_rule_production_authorization_result_id_var = tk.StringVar(value="")
        self.certified_rule_production_authorization_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_production_authorization_decision_var = tk.StringVar(value="authorize_for_later_production_deployment")
        self.certified_rule_production_authorization_confirmation_var = tk.StringVar(value="SAVE_PRODUCTION_AUTHORIZATION")
        self.certified_rule_production_authorization_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nControlled Integration Status: unknown\nRelease Candidate Status: unknown\nAuthorization Status: unknown\nProduction Target Status: unknown\nDescriptor Access Mode: unknown\nNamespace ID: unknown\nTransaction ID: unknown\nDecision Status: unknown\nStale Status: unknown\nBlocker Count: 0\nWarning Count: 0\nRecommended Action: Load one completed controlled integration result and explicit production target descriptor to start production authorization.")
        self.certified_rule_production_deployment_rule_id_var = tk.StringVar(value="")
        self.certified_rule_production_deployment_authorization_result_id_var = tk.StringVar(value="")
        self.certified_rule_production_deployment_target_id_var = tk.StringVar(value="production_target_primary")
        self.certified_rule_production_deployment_plan_id_var = tk.StringVar(value="")
        self.certified_rule_production_deployment_result_id_var = tk.StringVar(value="")
        self.certified_rule_production_deployment_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_production_deployment_confirmation_var = tk.StringVar(value="EXECUTE_AUTHORIZED_PRODUCTION_DEPLOYMENT")
        self.certified_rule_production_deployment_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nCertification Status: unknown\nPhase 9U Authorization Status: unknown\nPhase 9T Verification Status: unknown\nProduction Target Status: unknown\nAdapter Version: unknown\nTransaction ID: unknown\nApply Status: unknown\nPending Verification: unknown\nCommit Status: unknown\nCommitted Verification: unknown\nRollback Status: unknown\nProduction Safety: unknown\nBlocker Count: 0\nWarning Count: 0\nRecommended Action: Load one authorized production authorization result and explicit target to start production deployment.")
        self.certified_rule_post_deployment_result_id_var = tk.StringVar(value="")
        self.certified_rule_post_deployment_plan_id_var = tk.StringVar(value="")
        self.certified_rule_post_deployment_decision_result_id_var = tk.StringVar(value="")
        self.certified_rule_post_deployment_receipt_id_var = tk.StringVar(value="")
        self.certified_rule_post_deployment_decision_var = tk.StringVar(value="continue_observation")
        self.certified_rule_post_deployment_confirmation_var = tk.StringVar(value="SAVE_POST_DEPLOYMENT_ACCEPTANCE_DECISION")
        self.certified_rule_post_deployment_status_var = tk.StringVar(value="Document ID: unknown\nSource Revision: unknown\nCanonical Rule ID: unknown\nDeployed Rule ID: unknown\nPhase 9V Status: unknown\nCurrent Transaction Status: unknown\nCurrent Verification Status: unknown\nCanonical Source Rule Status: unknown\nDeployed Rule Status: unknown\nOptional Telemetry Status: unknown\nDecision Status: unknown\nBlocker Count: 0\nWarning Count: 0\nRecommended Action: Load one completed Phase 9V deployment result to start post-deployment observation.")
        self.deployed_rule_operational_telemetry_rule_id_var = tk.StringVar(value="")
        self.deployed_rule_operational_telemetry_result_id_var = tk.StringVar(value="")
        self.deployed_rule_operational_telemetry_phase_9w_result_id_var = tk.StringVar(value="")
        self.deployed_rule_operational_telemetry_target_id_var = tk.StringVar(value="production_target_primary")
        self.deployed_rule_operational_telemetry_deployed_rule_id_var = tk.StringVar(value="")
        self.deployed_rule_operational_telemetry_start_var = tk.StringVar(value="")
        self.deployed_rule_operational_telemetry_end_var = tk.StringVar(value="")
        self.deployed_rule_operational_telemetry_event_type_var = tk.StringVar(value="")
        self.deployed_rule_operational_telemetry_producer_var = tk.StringVar(value="")
        self.deployed_rule_operational_telemetry_max_results_var = tk.StringVar(value="50")
        self.deployed_rule_operational_telemetry_status_var = tk.StringVar(value="Phase 9V Deployment Status: unknown\nCurrent Transaction Status: unknown\nDeployed Rule Status: unknown\nCanonical Source Rule Preservation: unknown\nState Telemetry Available: unknown\nExecution Telemetry Available: unknown\nProducer IDs: none\nObservation Window: none\nTotal Matching Event Count: 0\nReturned Event Count: 0\nValidated Event Count: 0\nInvalid Event Count: 0\nCorrupt Event Count: 0\nSnapshot Completeness: unknown\nSnapshot ID: none\nTelemetry Health: unknown\nMetric Availability: unknown\nEffectiveness Evaluation Status: not_performed\nBlocker Count: 0\nWarning Count: 0\nRecommended Action: Load one completed Phase 9V deployment result to inspect telemetry.")
        self._register_deployed_rule_operational_telemetry_traces()
        self.deployed_rule_effectiveness_readiness_rule_id_var = tk.StringVar(value="")
        self.deployed_rule_effectiveness_readiness_result_id_var = tk.StringVar(value="")
        self.deployed_rule_effectiveness_readiness_target_id_var = tk.StringVar(value="production_target_primary")
        self.deployed_rule_effectiveness_readiness_deployed_rule_id_var = tk.StringVar(value="")
        self.deployed_rule_effectiveness_readiness_snapshot_id_var = tk.StringVar(value="")
        self.deployed_rule_effectiveness_readiness_start_var = tk.StringVar(value="")
        self.deployed_rule_effectiveness_readiness_end_var = tk.StringVar(value="")
        self.deployed_rule_effectiveness_readiness_phase_9w_result_id_var = tk.StringVar(value="")
        self.deployed_rule_effectiveness_readiness_plan_id_var = tk.StringVar(value="")
        self.deployed_rule_effectiveness_readiness_loaded_result_id_var = tk.StringVar(value="")
        self.deployed_rule_effectiveness_readiness_confirmation_var = tk.StringVar(value="RECORD_EFFECTIVENESS_READINESS_RESULT")
        self.deployed_rule_effectiveness_readiness_status_var = tk.StringVar(value="Phase 9V Status: unknown\nDeployed Rule Status: unknown\nCanonical Source Rule Status: unknown\nTelemetry Snapshot Status: unknown\nExecution Producer Availability: unknown\nExecution Producer ID: unknown\nExecution Producer Fingerprint: unknown\nValid Execution Attempt Count: 0\nCompleted Event Count: 0\nFailed Event Count: 0\nMinimum Execution Attempts: 30\nSample Sufficiency Status: unknown\nDenominator Readiness: unknown\nObservation-Window Readiness: unknown\nReadiness Status: unknown\nReadiness Plan ID: none\nReadiness Result ID: none\nHealth Scope: repository-wide\nReadiness Health: unknown\nEffectiveness Evaluation Status: not_performed\nBlocker Count: 0\nWarning Count: 0\nRecommended Action: Load one explicit readiness workspace from a completed Phase 9V deployment and Phase 9X snapshot.")
        self._register_deployed_rule_effectiveness_readiness_traces()
        for variable in (
            self.pdf_viewport_id_var,
            self.pdf_reader_workspace_id_var,
            self.pdf_viewport_jump_page_var,
            self.pdf_viewport_zoom_var,
            self.pdf_viewport_locator_var,
            self.pdf_reader_bookmark_label_var,
            self.pdf_reader_annotation_note_var,
            self.pdf_reader_citation_note_var,
            self.citation_review_workspace_id_var,
            self.citation_review_draft_id_var,
            self.citation_review_id_var,
            self.citation_review_note_var,
            self.citation_review_confirmation_var,
            self.evidence_handoff_id_var,
            self.evidence_handoff_review_id_var,
            self.evidence_handoff_target_binder_var,
            self.evidence_handoff_note_var,
            self.evidence_handoff_confirmation_var,
            self.proposal_promotion_proposal_id_var,
            self.proposal_promotion_review_id_var,
            self.proposal_promotion_note_var,
            self.proposal_promotion_confirmation_var,
            self.rule_activation_proposal_id_var,
            self.rule_activation_review_id_var,
            self.rule_activation_note_var,
            self.rule_activation_receipt_id_var,
            self.rule_activation_confirmation_var,
            self.rule_activation_rollback_confirmation_var,
            self.rule_revalidation_id_var,
            self.rule_revalidation_review_id_var,
            self.rule_revalidation_note_var,
            self.rule_revalidation_completion_confirmation_var,
            self.rule_revalidation_receipt_id_var,
            self.rule_supersession_old_rule_id_var,
            self.rule_supersession_proposal_id_var,
            self.rule_supersession_review_id_var,
            self.rule_supersession_note_var,
            self.rule_supersession_receipt_id_var,
            self.rule_supersession_confirmation_var,
            self.rule_supersession_rollback_confirmation_var,
            self.rule_effectiveness_rule_id_var,
            self.rule_effectiveness_dataset_id_var,
            self.rule_effectiveness_comparison_rule_id_var,
            self.rule_effectiveness_max_records_var,
            self.rule_effectiveness_recommendation_analysis_id_var,
            self.rule_effectiveness_recommendation_policy_id_var,
            self.rule_effectiveness_recommendation_id_var,
            self.rule_effectiveness_recommendation_note_var,
            self.rule_effectiveness_recommendation_review_id_var,
            self.rule_effectiveness_recommendation_action_candidate_id_var,
            self.rule_effectiveness_recommendation_queue_confirmation_var,
            self.rule_batch_document_id_var,
            self.rule_batch_source_revision_var,
            self.rule_batch_dataset_id_var,
            self.rule_batch_policy_id_var,
            self.rule_batch_rule_ids_var,
            self.rule_batch_max_rules_var,
            self.rule_batch_max_records_var,
            self.rule_batch_plan_id_var,
            self.rule_batch_run_id_var,
            self.rule_batch_stop_after_items_var,
            self.rule_batch_cancellation_reason_var,
            self.autonomous_pdf_document_id_var,
            self.autonomous_pdf_source_revision_var,
            self.autonomous_pdf_max_pages_var,
            self.autonomous_pdf_max_harvest_candidates_var,
            self.autonomous_pdf_max_proposal_candidates_var,
            self.autonomous_pdf_max_rule_candidates_var,
            self.autonomous_pdf_max_certified_rules_var,
            self.autonomous_pdf_plan_id_var,
            self.autonomous_pdf_run_id_var,
            self.autonomous_pdf_stop_after_stage_var,
            self.autonomous_pdf_confirmation_var,
            self.autonomous_pdf_cancellation_reason_var,
            self.autonomous_pdf_benchmark_id_var,
            self.autonomous_pdf_benchmark_run_id_var,
            self.autonomous_pdf_benchmark_result_id_var,
            self.autonomous_pdf_benchmark_receipt_id_var,
            self.autonomous_pdf_benchmark_confirmation_var,
        ):
            tk.Entry(viewport_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4 if variable is self.pdf_viewport_id_var else 0, 3))
        ttk.Combobox(viewport_box, textvariable=self.pdf_viewport_selection_mode_var, values=("intersect", "contained"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        ttk.Combobox(viewport_box, textvariable=self.pdf_reader_annotation_type_var, values=("highlight", "underline", "note", "selection_reference"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        ttk.Combobox(viewport_box, textvariable=self.citation_review_decision_var, values=("approve", "reject", "request_changes"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        ttk.Combobox(viewport_box, textvariable=self.evidence_handoff_decision_var, values=("approve_binder_insert", "approve_proposal_draft", "defer", "reject"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        ttk.Combobox(viewport_box, textvariable=self.proposal_promotion_decision_var, values=("approve", "reject", "request_changes"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        ttk.Combobox(viewport_box, textvariable=self.rule_activation_decision_var, values=("approve", "reject", "request_changes"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        ttk.Combobox(viewport_box, textvariable=self.rule_revalidation_decision_var, values=("certify", "request_changes", "reject_and_rollback"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        ttk.Combobox(viewport_box, textvariable=self.rule_supersession_decision_var, values=("approve", "reject", "request_changes"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        ttk.Combobox(viewport_box, textvariable=self.rule_effectiveness_recommendation_decision_var, values=("accept", "reject", "defer", "request_more_evidence"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        ttk.Checkbutton(viewport_box, text="Allow Near Duplicate", variable=self.citation_review_allow_near_duplicate_var).pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(viewport_box, text="Acknowledge Near Duplicate", variable=self.proposal_promotion_ack_near_duplicate_var).pack(anchor="w", pady=(0, 2))
        ttk.Checkbutton(viewport_box, text="Acknowledge Conflict", variable=self.proposal_promotion_ack_conflict_var).pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(viewport_box, text="Acknowledge Inactive Equivalent", variable=self.rule_activation_ack_inactive_var).pack(anchor="w", pady=(0, 2))
        ttk.Checkbutton(viewport_box, text="Acknowledge Conflict (Rule)", variable=self.rule_activation_ack_conflict_var).pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(viewport_box, text="Acknowledge Scope Change", variable=self.rule_supersession_ack_scope_var).pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(viewport_box, text="Regenerate Effectiveness Analysis", variable=self.rule_effectiveness_regenerate_var).pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(viewport_box, text="Include Certified Rules from This PDF", variable=self.rule_batch_include_active_var).pack(anchor="w", pady=(0, 4))
        self.pdf_viewport_status_var = tk.StringVar(value="Certification Status: unknown\nRenderer Status: unknown\nCurrent Page / Page Count: unknown\nZoom: 100%\nRender Status: not_rendered\nCache Status: unknown\nLocator Status: not_selected\nText Layer Status: unknown\nOverlay Status: none\nWorkspace Status: none\nWorkspace Revision: 0\nBookmarks: 0\nAnnotations: 0\nCitation Drafts: 0\nSelected Text: none\nRecommended Action: Open a certified viewport session.")
        tk.Label(viewport_box, textvariable=self.pdf_viewport_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        viewport_actions = ttk.Frame(viewport_box, style="Panel.TFrame")
        viewport_actions.pack(fill=tk.X)
        for label, command in (
            ("Open Viewport", lambda: self._run_pdf_viewport_action("open")),
            ("First", lambda: self._run_pdf_viewport_action("first")),
            ("Previous", lambda: self._run_pdf_viewport_action("previous")),
            ("Next", lambda: self._run_pdf_viewport_action("next")),
            ("Last", lambda: self._run_pdf_viewport_action("last")),
            ("Jump", lambda: self._run_pdf_viewport_action("jump")),
            ("Zoom -", lambda: self._run_pdf_viewport_action("zoom_out")),
            ("Zoom +", lambda: self._run_pdf_viewport_action("zoom_in")),
            ("Sync Locator", lambda: self._run_pdf_viewport_action("sync")),
            ("Load Text Layer", lambda: self._run_pdf_viewport_action("load_text_layer")),
            ("Highlight Locator", lambda: self._run_pdf_viewport_action("highlight_locator")),
            ("Highlight Search Results", lambda: self._run_pdf_viewport_action("highlight_search")),
            ("Highlight Citations", lambda: self._run_pdf_viewport_action("highlight_citations")),
            ("Clear Highlights", lambda: self._run_pdf_viewport_action("clear_highlights")),
            ("Copy Selection", lambda: self._run_pdf_viewport_action("copy_selection")),
            ("Open Reader Workspace", lambda: self._run_pdf_viewport_action("open_workspace")),
            ("Add Bookmark", lambda: self._run_pdf_viewport_action("add_bookmark")),
            ("Save Highlight", lambda: self._run_pdf_viewport_action("save_annotation")),
            ("Save Note", lambda: self._run_pdf_viewport_action("save_note")),
            ("Draft Citation from Selection", lambda: self._run_pdf_viewport_action("draft_citation")),
            ("Reload Workspace Items", lambda: self._run_pdf_viewport_action("reload_workspace")),
            ("Copy Workspace Report", lambda: self._run_pdf_viewport_action("copy_workspace_report")),
            ("Copy Viewport Report", lambda: self._run_pdf_viewport_action("copy")),
            ("Load Draft Review", lambda: self._run_pdf_viewport_action("load_draft_review")),
            ("Approve Draft", lambda: self._run_pdf_viewport_action("approve_draft")),
            ("Reject Draft", lambda: self._run_pdf_viewport_action("reject_draft")),
            ("Request Changes", lambda: self._run_pdf_viewport_action("request_draft_changes")),
            ("Create Citation", lambda: self._run_pdf_viewport_action("create_citation")),
            ("Review Health", lambda: self._run_pdf_viewport_action("review_health")),
            ("Copy Review Report", lambda: self._run_pdf_viewport_action("copy_review_report")),
            ("Load Handoff", lambda: self._run_pdf_viewport_action("load_handoff_review")),
            ("Find Binder Candidates", lambda: self._run_pdf_viewport_action("find_handoff_binders")),
            ("Approve Binder Insert", lambda: self._run_pdf_viewport_action("approve_handoff_binder")),
            ("Approve Proposal Draft", lambda: self._run_pdf_viewport_action("approve_handoff_proposal")),
            ("Defer", lambda: self._run_pdf_viewport_action("defer_handoff")),
            ("Reject", lambda: self._run_pdf_viewport_action("reject_handoff")),
            ("Insert into Binder", lambda: self._run_pdf_viewport_action("insert_handoff_binder")),
            ("Create Proposal Draft", lambda: self._run_pdf_viewport_action("create_handoff_proposal")),
            ("Copy Handoff Report", lambda: self._run_pdf_viewport_action("copy_handoff_report")),
            ("Load Proposal Review", lambda: self._run_pdf_viewport_action("load_proposal_promotion")),
            ("Approve Promotion", lambda: self._run_pdf_viewport_action("approve_proposal_promotion")),
            ("Reject Proposal", lambda: self._run_pdf_viewport_action("reject_proposal_promotion")),
            ("Request Changes", lambda: self._run_pdf_viewport_action("request_changes_proposal_promotion")),
            ("Promote Proposal", lambda: self._run_pdf_viewport_action("promote_proposal")),
            ("Promotion Health", lambda: self._run_pdf_viewport_action("proposal_promotion_health")),
            ("Copy Promotion Report", lambda: self._run_pdf_viewport_action("copy_proposal_promotion_report")),
            ("Load Rule Candidate", lambda: self._run_pdf_viewport_action("load_rule_activation")),
            ("Approve Activation", lambda: self._run_pdf_viewport_action("approve_rule_activation")),
            ("Reject Candidate", lambda: self._run_pdf_viewport_action("reject_rule_activation")),
            ("Request Changes", lambda: self._run_pdf_viewport_action("request_changes_rule_activation")),
            ("Activate Rule", lambda: self._run_pdf_viewport_action("activate_rule")),
            ("Rollback Activation", lambda: self._run_pdf_viewport_action("rollback_rule_activation")),
            ("Copy Activation Report", lambda: self._run_pdf_viewport_action("copy_rule_activation_report")),
            ("Load Revalidation", lambda: self._run_pdf_viewport_action("load_rule_revalidation")),
            ("Run Runtime Contract", lambda: self._run_pdf_viewport_action("run_rule_revalidation_runtime")),
            ("Certify Rule", lambda: self._run_pdf_viewport_action("certify_rule_revalidation")),
            ("Request Changes", lambda: self._run_pdf_viewport_action("request_changes_rule_revalidation")),
            ("Reject and Roll Back", lambda: self._run_pdf_viewport_action("reject_rule_revalidation")),
            ("Complete Revalidation", lambda: self._run_pdf_viewport_action("complete_rule_revalidation")),
            ("Copy Revalidation Report", lambda: self._run_pdf_viewport_action("copy_rule_revalidation_report")),
            ("Load Supersession", lambda: self._run_pdf_viewport_action("load_rule_supersession")),
            ("Approve Replacement", lambda: self._run_pdf_viewport_action("approve_rule_supersession")),
            ("Reject Replacement", lambda: self._run_pdf_viewport_action("reject_rule_supersession")),
            ("Request Changes", lambda: self._run_pdf_viewport_action("request_changes_rule_supersession")),
            ("Supersede Rule", lambda: self._run_pdf_viewport_action("supersede_rule")),
            ("Rollback Supersession", lambda: self._run_pdf_viewport_action("rollback_rule_supersession")),
            ("Copy Supersession Report", lambda: self._run_pdf_viewport_action("copy_rule_supersession_report")),
            ("Load Effectiveness Workspace", lambda: self._run_pdf_viewport_action("load_rule_effectiveness_workspace")),
            ("Build Backtest Plan", lambda: self._run_pdf_viewport_action("build_rule_effectiveness_plan")),
            ("Run Focused Backtest", lambda: self._run_pdf_viewport_action("run_rule_effectiveness_backtest")),
            ("Effectiveness Health", lambda: self._run_pdf_viewport_action("rule_effectiveness_health")),
            ("Copy Effectiveness Report", lambda: self._run_pdf_viewport_action("copy_rule_effectiveness_report")),
            ("Load Recommendation Workspace", lambda: self._run_pdf_viewport_action("load_rule_effectiveness_recommendation_workspace")),
            ("Generate Recommendation", lambda: self._run_pdf_viewport_action("generate_rule_effectiveness_recommendation")),
            ("Accept Recommendation", lambda: self._run_pdf_viewport_action("accept_rule_effectiveness_recommendation")),
            ("Reject Recommendation", lambda: self._run_pdf_viewport_action("reject_rule_effectiveness_recommendation")),
            ("Defer Recommendation", lambda: self._run_pdf_viewport_action("defer_rule_effectiveness_recommendation")),
            ("Request More Evidence", lambda: self._run_pdf_viewport_action("more_evidence_rule_effectiveness_recommendation")),
            ("Queue Action Candidate", lambda: self._run_pdf_viewport_action("queue_rule_effectiveness_action_candidate")),
            ("Copy Recommendation Report", lambda: self._run_pdf_viewport_action("copy_rule_effectiveness_recommendation_report")),
            ("Load Batch Workspace", lambda: self._run_pdf_viewport_action("load_rule_batch_workspace")),
            ("Build Batch Plan", lambda: self._run_pdf_viewport_action("build_rule_batch_plan")),
            ("Run / Resume Batch", lambda: self._run_pdf_viewport_action("run_rule_batch_analysis")),
            ("Cancel Batch", lambda: self._run_pdf_viewport_action("cancel_rule_batch_run")),
            ("Batch Health", lambda: self._run_pdf_viewport_action("rule_batch_health")),
            ("Copy Batch Report", lambda: self._run_pdf_viewport_action("copy_rule_batch_report")),
            ("Load Autonomous Workspace", lambda: self._run_pdf_viewport_action("load_autonomous_pdf_workspace")),
            ("Build Autonomous Plan", lambda: self._run_pdf_viewport_action("build_autonomous_pdf_plan")),
            ("Run / Resume AUTO", lambda: self._run_pdf_viewport_action("run_autonomous_pdf_pipeline")),
            ("Cancel Autonomous Run", lambda: self._run_pdf_viewport_action("cancel_autonomous_pdf_pipeline")),
            ("Autonomous Health", lambda: self._run_pdf_viewport_action("autonomous_pdf_health")),
            ("Copy Autonomous Report", lambda: self._run_pdf_viewport_action("copy_autonomous_pdf_report")),
            ("Load Benchmark Workspace", lambda: self._run_pdf_viewport_action("load_autonomous_pdf_benchmark_workspace")),
            ("Validate Benchmark Manifest", lambda: self._run_pdf_viewport_action("validate_autonomous_pdf_benchmark_manifest")),
            ("Run Benchmark", lambda: self._run_pdf_viewport_action("run_autonomous_pdf_benchmark")),
            ("Benchmark Health", lambda: self._run_pdf_viewport_action("autonomous_pdf_benchmark_health")),
            ("Copy Benchmark Report", lambda: self._run_pdf_viewport_action("copy_autonomous_pdf_benchmark_report")),
            ("Load Remediation Workspace", lambda: self._run_pdf_viewport_action("load_autonomous_pdf_remediation_workspace")),
            ("Run Triage", lambda: self._run_pdf_viewport_action("run_autonomous_pdf_remediation_triage")),
            ("Review Case", lambda: self._run_pdf_viewport_action("review_autonomous_pdf_remediation_case")),
            ("Verify Re-Benchmark", lambda: self._run_pdf_viewport_action("verify_autonomous_pdf_remediation")),
            ("Copy Remediation Report", lambda: self._run_pdf_viewport_action("copy_autonomous_pdf_remediation_report")),
            ("Load Corrective Workspace", lambda: self._run_pdf_viewport_action("load_autonomous_pdf_corrective_action_workspace")),
            ("Build Action Plan", lambda: self._run_pdf_viewport_action("build_autonomous_pdf_corrective_action_plan")),
            ("Execute Action", lambda: self._run_pdf_viewport_action("execute_autonomous_pdf_corrective_action")),
            ("Verify Action", lambda: self._run_pdf_viewport_action("verify_autonomous_pdf_corrective_action")),
            ("Close Action", lambda: self._run_pdf_viewport_action("close_autonomous_pdf_corrective_action")),
            ("Copy Action Report", lambda: self._run_pdf_viewport_action("copy_autonomous_pdf_corrective_action_report")),
            ("Load Replay Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_replay_workspace")),
            ("Validate Replay Eligibility", lambda: self._run_pdf_viewport_action("validate_certified_rule_replay_eligibility")),
            ("Build Replay Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_replay_plan")),
            ("Run Shadow Replay", lambda: self._run_pdf_viewport_action("run_certified_rule_replay")),
            ("Replay Health", lambda: self._run_pdf_viewport_action("certified_rule_replay_health")),
            ("Copy Replay Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_replay_report")),
            ("Load Objective Preview Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_objective_preview_workspace")),
            ("Validate Objective Preview Eligibility", lambda: self._run_pdf_viewport_action("validate_certified_rule_objective_preview_eligibility")),
            ("Build Objective Preview Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_objective_preview_plan")),
            ("Run Read-Only Preview", lambda: self._run_pdf_viewport_action("run_certified_rule_objective_preview")),
            ("Objective Preview Health", lambda: self._run_pdf_viewport_action("certified_rule_objective_preview_health")),
            ("Copy Objective Preview Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_objective_preview_report")),
            ("Load Scoring Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_scoring_preview_workspace")),
            ("Validate Scoring Eligibility", lambda: self._run_pdf_viewport_action("validate_certified_rule_scoring_preview_eligibility")),
            ("Build Scoring Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_scoring_preview_plan")),
            ("Run Read-Only Scoring Preview", lambda: self._run_pdf_viewport_action("run_certified_rule_scoring_preview")),
            ("Scoring Preview Health", lambda: self._run_pdf_viewport_action("certified_rule_scoring_preview_health")),
            ("Copy Scoring Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_scoring_preview_report")),
            ("Load Fast Lane Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_fast_lane_preview_workspace")),
            ("Validate Fast Lane Eligibility", lambda: self._run_pdf_viewport_action("validate_certified_rule_fast_lane_preview_eligibility")),
            ("Build Compatibility Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_fast_lane_preview_plan")),
            ("Run Compatibility Preview", lambda: self._run_pdf_viewport_action("run_certified_rule_fast_lane_preview")),
            ("Fast Lane Preview Health", lambda: self._run_pdf_viewport_action("certified_rule_fast_lane_preview_health")),
            ("Copy Compatibility Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_fast_lane_preview_report")),
            ("Load Authorization Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_integration_authorization_workspace")),
            ("Validate Authorization Eligibility", lambda: self._run_pdf_viewport_action("validate_certified_rule_integration_authorization_eligibility")),
            ("Build Authorization Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_integration_authorization_plan")),
            ("Save Authorization Decision", lambda: self._run_pdf_viewport_action("save_certified_rule_integration_authorization_decision")),
            ("Copy Authorization Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_integration_authorization_report")),
            ("Load Release Candidate Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_release_candidate_workspace")),
            ("Validate Release Candidate", lambda: self._run_pdf_viewport_action("validate_certified_rule_release_candidate_eligibility")),
            ("Build Release Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_release_candidate_plan")),
            ("Qualify Release Candidate", lambda: self._run_pdf_viewport_action("qualify_certified_rule_release_candidate")),
            ("Copy Release Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_release_candidate_report")),
            ("Load Integration Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_controlled_integration_workspace")),
            ("Validate Integration Eligibility", lambda: self._run_pdf_viewport_action("validate_certified_rule_controlled_integration_eligibility")),
            ("Build Integration Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_controlled_integration_plan")),
            ("Execute Controlled Integration", lambda: self._run_pdf_viewport_action("execute_certified_rule_controlled_integration")),
            ("Controlled Integration Health", lambda: self._run_pdf_viewport_action("certified_rule_controlled_integration_health")),
            ("Copy Integration Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_controlled_integration_report")),
            ("Load Production Authorization Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_production_authorization_workspace")),
            ("Validate Production Authorization", lambda: self._run_pdf_viewport_action("validate_certified_rule_production_authorization_eligibility")),
            ("Build Production Authorization Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_production_authorization_plan")),
            ("Save Production Authorization", lambda: self._run_pdf_viewport_action("save_certified_rule_production_authorization_decision")),
            ("Production Authorization Health", lambda: self._run_pdf_viewport_action("certified_rule_production_authorization_health")),
            ("Copy Production Authorization Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_production_authorization_report")),
            ("Load Production Deployment Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_production_deployment_workspace")),
            ("Validate Production Deployment", lambda: self._run_pdf_viewport_action("validate_certified_rule_production_deployment_eligibility")),
            ("Build Production Deployment Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_production_deployment_plan")),
            ("Execute Authorized Deployment", lambda: self._run_pdf_viewport_action("execute_certified_rule_production_deployment")),
            ("Production Deployment Health", lambda: self._run_pdf_viewport_action("certified_rule_production_deployment_health")),
            ("Copy Production Deployment Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_production_deployment_report")),
            ("Load Post-Deployment Workspace", lambda: self._run_pdf_viewport_action("load_certified_rule_post_deployment_acceptance_workspace")),
            ("Validate Post-Deployment", lambda: self._run_pdf_viewport_action("validate_certified_rule_post_deployment_acceptance_eligibility")),
            ("Build Observation Plan", lambda: self._run_pdf_viewport_action("build_certified_rule_post_deployment_acceptance_plan")),
            ("Save Post-Deployment Decision", lambda: self._run_pdf_viewport_action("save_certified_rule_post_deployment_acceptance_decision")),
            ("Post-Deployment Health", lambda: self._run_pdf_viewport_action("certified_rule_post_deployment_acceptance_health")),
            ("Copy Post-Deployment Report", lambda: self._run_pdf_viewport_action("copy_certified_rule_post_deployment_acceptance_report")),
        ):
            ttk.Button(viewport_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        remediation_box = ttk.Frame(parent, style="Panel.TFrame")
        remediation_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(remediation_box, text="Autonomous PDF Remediation", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.autonomous_pdf_benchmark_result_id_var,
            self.autonomous_pdf_remediation_plan_id_var,
            self.autonomous_pdf_remediation_case_id_var,
            self.autonomous_pdf_remediation_new_result_id_var,
            self.autonomous_pdf_remediation_review_note_var,
            self.autonomous_pdf_remediation_confirmation_var,
        ):
            tk.Entry(remediation_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        ttk.Combobox(remediation_box, textvariable=self.autonomous_pdf_remediation_review_decision_var, values=("accept_for_targeted_fix", "benchmark_manifest_review", "source_document_review", "expected_conservative_behavior", "defer", "reject", "no_action"), state="readonly").pack(fill=tk.X, pady=(4, 0))
        tk.Label(remediation_box, textvariable=self.autonomous_pdf_remediation_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        corrective_box = ttk.Frame(parent, style="Panel.TFrame")
        corrective_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(corrective_box, text="Autonomous PDF Corrective Action", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.autonomous_pdf_remediation_case_id_var,
            self.autonomous_pdf_corrective_action_id_var,
            self.autonomous_pdf_corrective_action_payload_var,
            self.autonomous_pdf_remediation_new_result_id_var,
            self.autonomous_pdf_corrective_action_confirmation_var,
        ):
            tk.Entry(corrective_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        ttk.Combobox(corrective_box, textvariable=self.autonomous_pdf_corrective_action_type_var, values=("close_expected_behavior", "close_no_action", "apply_benchmark_manifest_amendment", "request_new_source_revision", "create_phase_9j_fix_package", "create_phase_9k_fix_package"), state="readonly").pack(fill=tk.X, pady=(4, 0))
        tk.Label(corrective_box, textvariable=self.autonomous_pdf_corrective_action_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        replay_box = ttk.Frame(parent, style="Panel.TFrame")
        replay_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(replay_box, text="Certified Rule Historical Replay", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_replay_rule_id_var,
            self.certified_rule_replay_dataset_id_var,
            self.certified_rule_replay_max_records_var,
            self.certified_rule_replay_plan_id_var,
            self.certified_rule_replay_result_id_var,
            self.certified_rule_replay_receipt_id_var,
            self.certified_rule_replay_confirmation_var,
        ):
            tk.Entry(replay_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        tk.Label(replay_box, textvariable=self.certified_rule_replay_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        objective_preview_box = ttk.Frame(parent, style="Panel.TFrame")
        objective_preview_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(objective_preview_box, text="Certified Rule Objective Preview", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_objective_preview_rule_id_var,
            self.certified_rule_objective_preview_pack_id_var,
            self.certified_rule_objective_preview_input_id_var,
            self.certified_rule_objective_preview_max_records_var,
            self.certified_rule_objective_preview_mapping_var,
            self.certified_rule_objective_preview_plan_id_var,
            self.certified_rule_objective_preview_result_id_var,
            self.certified_rule_objective_preview_receipt_id_var,
            self.certified_rule_objective_preview_confirmation_var,
        ):
            tk.Entry(objective_preview_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        tk.Label(objective_preview_box, textvariable=self.certified_rule_objective_preview_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        scoring_preview_box = ttk.Frame(parent, style="Panel.TFrame")
        scoring_preview_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(scoring_preview_box, text="Certified Rule Scoring Preview", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_scoring_preview_objective_result_id_var,
            self.certified_rule_scoring_preview_config_id_var,
            self.certified_rule_scoring_preview_plan_id_var,
            self.certified_rule_scoring_preview_result_id_var,
            self.certified_rule_scoring_preview_receipt_id_var,
            self.certified_rule_scoring_preview_confirmation_var,
        ):
            tk.Entry(scoring_preview_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        tk.Label(scoring_preview_box, textvariable=self.certified_rule_scoring_preview_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        fast_lane_preview_box = ttk.Frame(parent, style="Panel.TFrame")
        fast_lane_preview_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(fast_lane_preview_box, text="Certified Rule Fast Lane Preview", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_fast_lane_preview_rule_id_var,
            self.certified_rule_fast_lane_preview_plan_id_var,
            self.certified_rule_fast_lane_preview_result_id_var,
            self.certified_rule_fast_lane_preview_receipt_id_var,
            self.certified_rule_fast_lane_preview_confirmation_var,
        ):
            tk.Entry(fast_lane_preview_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        tk.Label(fast_lane_preview_box, textvariable=self.certified_rule_fast_lane_preview_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        authorization_box = ttk.Frame(parent, style="Panel.TFrame")
        authorization_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(authorization_box, text="Certified Rule Integration Authorization", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_integration_authorization_rule_id_var,
            self.certified_rule_integration_authorization_scoring_result_id_var,
            self.certified_rule_integration_authorization_fast_lane_result_id_var,
            self.certified_rule_integration_authorization_plan_id_var,
            self.certified_rule_integration_authorization_result_id_var,
            self.certified_rule_integration_authorization_receipt_id_var,
            self.certified_rule_integration_authorization_reviewer_var,
            self.certified_rule_integration_authorization_rationale_var,
            self.certified_rule_integration_authorization_ack_var,
            self.certified_rule_integration_authorization_confirmation_var,
        ):
            tk.Entry(authorization_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        ttk.Combobox(authorization_box, textvariable=self.certified_rule_integration_authorization_decision_var, values=("authorize_for_later_integration", "reject_integration", "defer_integration"), state="readonly").pack(fill=tk.X, pady=(4, 0))
        tk.Label(authorization_box, textvariable=self.certified_rule_integration_authorization_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        release_candidate_box = ttk.Frame(parent, style="Panel.TFrame")
        release_candidate_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(release_candidate_box, text="Certified Rule Release Candidate", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_release_candidate_rule_id_var,
            self.certified_rule_release_candidate_authorization_result_id_var,
            self.certified_rule_release_candidate_plan_id_var,
            self.certified_rule_release_candidate_result_id_var,
            self.certified_rule_release_candidate_receipt_id_var,
            self.certified_rule_release_candidate_confirmation_var,
        ):
            tk.Entry(release_candidate_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        tk.Label(release_candidate_box, textvariable=self.certified_rule_release_candidate_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        controlled_integration_box = ttk.Frame(parent, style="Panel.TFrame")
        controlled_integration_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(controlled_integration_box, text="Certified Rule Controlled Integration", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_controlled_integration_rule_id_var,
            self.certified_rule_controlled_integration_release_result_id_var,
            self.certified_rule_controlled_integration_target_id_var,
            self.certified_rule_controlled_integration_plan_id_var,
            self.certified_rule_controlled_integration_result_id_var,
            self.certified_rule_controlled_integration_receipt_id_var,
            self.certified_rule_controlled_integration_confirmation_var,
        ):
            tk.Entry(controlled_integration_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        tk.Label(controlled_integration_box, textvariable=self.certified_rule_controlled_integration_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        production_authorization_box = ttk.Frame(parent, style="Panel.TFrame")
        production_authorization_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(production_authorization_box, text="Certified Rule Production Authorization", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_production_authorization_rule_id_var,
            self.certified_rule_production_authorization_integration_result_id_var,
            self.certified_rule_production_authorization_target_id_var,
            self.certified_rule_production_authorization_plan_id_var,
            self.certified_rule_production_authorization_result_id_var,
            self.certified_rule_production_authorization_receipt_id_var,
            self.certified_rule_production_authorization_confirmation_var,
        ):
            tk.Entry(production_authorization_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        ttk.Combobox(
            production_authorization_box,
            textvariable=self.certified_rule_production_authorization_decision_var,
            values=("authorize_for_later_production_deployment", "defer_production_deployment", "reject_production_deployment"),
            state="readonly",
        ).pack(fill=tk.X, pady=(4, 0))
        tk.Label(production_authorization_box, textvariable=self.certified_rule_production_authorization_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        production_deployment_box = ttk.Frame(parent, style="Panel.TFrame")
        production_deployment_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(production_deployment_box, text="Certified Rule Production Deployment", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_production_deployment_rule_id_var,
            self.certified_rule_production_deployment_authorization_result_id_var,
            self.certified_rule_production_deployment_target_id_var,
            self.certified_rule_production_deployment_plan_id_var,
            self.certified_rule_production_deployment_result_id_var,
            self.certified_rule_production_deployment_receipt_id_var,
            self.certified_rule_production_deployment_confirmation_var,
        ):
            tk.Entry(production_deployment_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        tk.Label(production_deployment_box, textvariable=self.certified_rule_production_deployment_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        post_deployment_box = ttk.Frame(parent, style="Panel.TFrame")
        post_deployment_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(post_deployment_box, text="Certified Rule Post-Deployment Acceptance", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.certified_rule_post_deployment_result_id_var,
            self.certified_rule_post_deployment_plan_id_var,
            self.certified_rule_post_deployment_decision_result_id_var,
            self.certified_rule_post_deployment_receipt_id_var,
            self.certified_rule_post_deployment_confirmation_var,
        ):
            tk.Entry(post_deployment_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        ttk.Combobox(
            post_deployment_box,
            textvariable=self.certified_rule_post_deployment_decision_var,
            values=("accept", "reject", "continue_observation"),
            state="readonly",
        ).pack(fill=tk.X, pady=(4, 0))
        tk.Label(post_deployment_box, textvariable=self.certified_rule_post_deployment_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        telemetry_box = ttk.Frame(parent, style="Panel.TFrame")
        telemetry_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(telemetry_box, text="Deployed Rule Operational Telemetry", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for variable in (
            self.deployed_rule_operational_telemetry_rule_id_var,
            self.deployed_rule_operational_telemetry_result_id_var,
            self.deployed_rule_operational_telemetry_phase_9w_result_id_var,
            self.deployed_rule_operational_telemetry_target_id_var,
            self.deployed_rule_operational_telemetry_deployed_rule_id_var,
            self.deployed_rule_operational_telemetry_start_var,
            self.deployed_rule_operational_telemetry_end_var,
            self.deployed_rule_operational_telemetry_event_type_var,
            self.deployed_rule_operational_telemetry_producer_var,
            self.deployed_rule_operational_telemetry_max_results_var,
        ):
            tk.Entry(telemetry_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        tk.Label(telemetry_box, textvariable=self.deployed_rule_operational_telemetry_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        telemetry_actions = ttk.Frame(telemetry_box, style="Panel.TFrame")
        telemetry_actions.pack(fill=tk.X, pady=(4, 0))
        for label, command in (
            ("Load Telemetry Workspace", lambda: self._run_pdf_viewport_action("load_deployed_rule_operational_telemetry_workspace")),
            ("Validate Telemetry Eligibility", lambda: self._run_pdf_viewport_action("validate_deployed_rule_operational_telemetry_eligibility")),
            ("List Operational Events", lambda: self._run_pdf_viewport_action("list_deployed_rule_operational_events")),
            ("Build Telemetry Snapshot", lambda: self._run_pdf_viewport_action("build_deployed_rule_operational_snapshot")),
            ("Telemetry Health", lambda: self._run_pdf_viewport_action("deployed_rule_operational_telemetry_health")),
            ("Copy Telemetry Report", lambda: self._run_pdf_viewport_action("copy_deployed_rule_operational_telemetry_report")),
        ):
            ttk.Button(telemetry_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        readiness_box = ttk.Frame(parent, style="Panel.TFrame")
        readiness_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(readiness_box, text="Deployed Rule Effectiveness Readiness", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        for label_text, variable in (
            ("Canonical Rule ID", self.deployed_rule_effectiveness_readiness_rule_id_var),
            ("Phase 9V Deployment Result ID", self.deployed_rule_effectiveness_readiness_result_id_var),
            ("Production Target ID", self.deployed_rule_effectiveness_readiness_target_id_var),
            ("Deployed Rule ID", self.deployed_rule_effectiveness_readiness_deployed_rule_id_var),
            ("Telemetry Snapshot ID", self.deployed_rule_effectiveness_readiness_snapshot_id_var),
            ("Observation Start", self.deployed_rule_effectiveness_readiness_start_var),
            ("Observation End", self.deployed_rule_effectiveness_readiness_end_var),
            ("Optional Phase 9W Result ID", self.deployed_rule_effectiveness_readiness_phase_9w_result_id_var),
            ("Readiness Plan ID", self.deployed_rule_effectiveness_readiness_plan_id_var),
            ("Readiness Result ID", self.deployed_rule_effectiveness_readiness_loaded_result_id_var),
            ("Confirmation", self.deployed_rule_effectiveness_readiness_confirmation_var),
        ):
            tk.Label(readiness_box, text=label_text, bg=PALETTE["panel"], fg=PALETTE["muted"], font=("Segoe UI", 8), anchor="w").pack(fill=tk.X, pady=(4, 0))
            tk.Entry(readiness_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 0))
        tk.Label(readiness_box, textvariable=self.deployed_rule_effectiveness_readiness_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(4, 0))
        readiness_actions = ttk.Frame(readiness_box, style="Panel.TFrame")
        readiness_actions.pack(fill=tk.X, pady=(4, 0))
        for label, command in (
            ("Load Readiness Workspace", lambda: self._run_pdf_viewport_action("load_deployed_rule_effectiveness_readiness_workspace")),
            ("Validate Readiness Eligibility", lambda: self._run_pdf_viewport_action("validate_deployed_rule_effectiveness_readiness_eligibility")),
            ("Build Readiness Plan", lambda: self._run_pdf_viewport_action("build_deployed_rule_effectiveness_readiness_plan")),
            ("Load Readiness Result", lambda: self._run_pdf_viewport_action("load_deployed_rule_effectiveness_readiness_result")),
            ("Record Readiness Result", lambda: self._run_pdf_viewport_action("record_deployed_rule_effectiveness_readiness_result")),
            ("Readiness Health", lambda: self._run_pdf_viewport_action("deployed_rule_effectiveness_readiness_health")),
            ("Copy Readiness Report", lambda: self._run_pdf_viewport_action("copy_deployed_rule_effectiveness_readiness_report")),
        ):
            ttk.Button(readiness_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        taxonomy_box = ttk.Frame(parent, style="Panel.TFrame")
        taxonomy_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(taxonomy_box, text="Controlled Topic Taxonomy", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.topic_taxonomy_preferred_label_var = tk.StringVar(value="")
        self.topic_taxonomy_aliases_var = tk.StringVar(value="")
        self.topic_taxonomy_parent_ids_var = tk.StringVar(value="")
        self.topic_taxonomy_related_ids_var = tk.StringVar(value="")
        self.topic_taxonomy_status_field_var = tk.StringVar(value="active")
        self.topic_taxonomy_replacement_id_var = tk.StringVar(value="")
        self.topic_taxonomy_resolve_label_var = tk.StringVar(value="")
        self.topic_taxonomy_include_aliases_var = tk.BooleanVar(value=True)
        self.topic_taxonomy_include_parents_var = tk.BooleanVar(value=False)
        self.topic_taxonomy_include_children_var = tk.BooleanVar(value=False)
        self.topic_taxonomy_include_related_var = tk.BooleanVar(value=False)
        for variable in (
            self.topic_taxonomy_preferred_label_var,
            self.topic_taxonomy_aliases_var,
            self.topic_taxonomy_parent_ids_var,
            self.topic_taxonomy_related_ids_var,
            self.topic_taxonomy_replacement_id_var,
            self.topic_taxonomy_resolve_label_var,
        ):
            tk.Entry(taxonomy_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4 if variable is self.topic_taxonomy_preferred_label_var else 0, 3))
        ttk.Combobox(taxonomy_box, textvariable=self.topic_taxonomy_status_field_var, values=("active", "deprecated", "review_required", "disabled"), state="readonly").pack(fill=tk.X, pady=(0, 3))
        toggles = ttk.Frame(taxonomy_box, style="Panel.TFrame")
        toggles.pack(fill=tk.X, pady=(0, 4))
        for text, variable in (
            ("Include Aliases", self.topic_taxonomy_include_aliases_var),
            ("Include Parents", self.topic_taxonomy_include_parents_var),
            ("Include Children", self.topic_taxonomy_include_children_var),
            ("Include Related", self.topic_taxonomy_include_related_var),
        ):
            ttk.Checkbutton(toggles, text=text, variable=variable).pack(anchor="w")
        self.topic_taxonomy_status_var = tk.StringVar(value="Topic ID: unknown\nPreferred Label: unknown\nStatus: unknown\nAlias Count: 0\nParent Count: 0\nChild Count: 0\nRelated Count: 0\nResolved: unknown\nResolution Type: unknown\nExpansion Label Count: 0\nTaxonomy Status: unknown\nValidation Issue Count: 0\nRecommended Action: Save a controlled topic.")
        tk.Label(taxonomy_box, textvariable=self.topic_taxonomy_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        taxonomy_actions = ttk.Frame(taxonomy_box, style="Panel.TFrame")
        taxonomy_actions.pack(fill=tk.X)
        for label, command in (
            ("Save Topic", lambda: self._run_topic_taxonomy_action("save")),
            ("Resolve Label", lambda: self._run_topic_taxonomy_action("resolve")),
            ("Build Expansion", lambda: self._run_topic_taxonomy_action("expand")),
            ("Taxonomy Health", lambda: self._run_topic_taxonomy_action("health")),
            ("Copy Taxonomy Report", lambda: self._run_topic_taxonomy_action("copy")),
        ):
            ttk.Button(taxonomy_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        taxonomy_search_box = ttk.Frame(parent, style="Panel.TFrame")
        taxonomy_search_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(taxonomy_search_box, text="Taxonomy-Aware Topic Search", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.taxonomy_topic_search_query_var = tk.StringVar(value="")
        self.taxonomy_topic_search_limit_var = tk.StringVar(value="50")
        self.taxonomy_topic_search_include_aliases_var = tk.BooleanVar(value=True)
        self.taxonomy_topic_search_include_parents_var = tk.BooleanVar(value=False)
        self.taxonomy_topic_search_include_children_var = tk.BooleanVar(value=False)
        self.taxonomy_topic_search_include_related_var = tk.BooleanVar(value=False)
        self.taxonomy_topic_search_include_replacement_var = tk.BooleanVar(value=True)
        self.taxonomy_topic_search_include_warning_docs_var = tk.BooleanVar(value=True)
        tk.Entry(taxonomy_search_box, textvariable=self.taxonomy_topic_search_query_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 3))
        tk.Entry(taxonomy_search_box, textvariable=self.taxonomy_topic_search_limit_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        search_toggles = ttk.Frame(taxonomy_search_box, style="Panel.TFrame")
        search_toggles.pack(fill=tk.X, pady=(0, 4))
        for text, variable in (
            ("Include Aliases", self.taxonomy_topic_search_include_aliases_var),
            ("Include Parents", self.taxonomy_topic_search_include_parents_var),
            ("Include Children", self.taxonomy_topic_search_include_children_var),
            ("Include Related", self.taxonomy_topic_search_include_related_var),
            ("Include Replacement", self.taxonomy_topic_search_include_replacement_var),
            ("Include Warning Documents", self.taxonomy_topic_search_include_warning_docs_var),
        ):
            ttk.Checkbutton(search_toggles, text=text, variable=variable).pack(anchor="w")
        self.taxonomy_topic_search_status_var = tk.StringVar(value="Input Query: unknown\nResolved Topic ID: unknown\nPreferred Label: unknown\nResolution Type: unknown\nExpansion Label Count: 0\nDocuments Matched: 0\nStructural Match Count: 0\nDirect Match Count: 0\nExpanded Match Count: 0\nTopic Index Status: unknown\nTaxonomy Status: unknown\nSearch Health: unknown\nRecommended Action: Resolve a controlled topic query.")
        tk.Label(taxonomy_search_box, textvariable=self.taxonomy_topic_search_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        taxonomy_search_actions = ttk.Frame(taxonomy_search_box, style="Panel.TFrame")
        taxonomy_search_actions.pack(fill=tk.X)
        for label, command in (
            ("Resolve Query", lambda: self._run_taxonomy_topic_search_action("resolve")),
            ("Build Search Plan", lambda: self._run_taxonomy_topic_search_action("plan")),
            ("Search Controlled Topics", lambda: self._run_taxonomy_topic_search_action("search")),
            ("Search Health", lambda: self._run_taxonomy_topic_search_action("health")),
            ("Copy Search Report", lambda: self._run_taxonomy_topic_search_action("copy")),
        ):
            ttk.Button(taxonomy_search_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        locator_box = ttk.Frame(parent, style="Panel.TFrame")
        locator_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(locator_box, text="Locator Migration Planner", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.locator_migration_scope_var = tk.StringVar(value="all")
        self.locator_migration_plan_id_var = tk.StringVar(value="")
        self.locator_migration_proposal_id_var = tk.StringVar(value="")
        self.locator_migration_classification_var = tk.StringVar(value="")
        self.locator_migration_record_type_var = tk.StringVar(value="")
        ttk.Combobox(locator_box, textvariable=self.locator_migration_scope_var, values=("all", "citations", "proposals", "evidence_binders", "stale_only", "critical_only"), state="readonly").pack(fill=tk.X, pady=(4, 3))
        for variable in (
            self.locator_migration_plan_id_var,
            self.locator_migration_proposal_id_var,
            self.locator_migration_classification_var,
            self.locator_migration_record_type_var,
        ):
            tk.Entry(locator_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        self.locator_migration_status_var = tk.StringVar(value="Document ID: unknown\nCurrent Source Revision: unknown\nPlan Status: unknown\nRecords Checked: 0\nValid Locator Count: 0\nStale Locator Count: 0\nSafe Candidate Count: 0\nManual Review Count: 0\nBlocked Count: 0\nAffected Proposal Count: 0\nAffected Evidence Binder Count: 0\nSelected Proposal Classification: unknown\nPlan Fingerprint Current: unknown\nRecommended Action: Audit document locators.")
        tk.Label(locator_box, textvariable=self.locator_migration_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        locator_actions = ttk.Frame(locator_box, style="Panel.TFrame")
        locator_actions.pack(fill=tk.X)
        for label, command in (
            ("Audit Locators", lambda: self._run_locator_migration_action("audit")),
            ("Build Migration Plan", lambda: self._run_locator_migration_action("build")),
            ("Load Migration Plan", lambda: self._run_locator_migration_action("load")),
            ("Preview Proposal", lambda: self._run_locator_migration_action("preview")),
            ("Migration Health", lambda: self._run_locator_migration_action("health")),
            ("Copy Migration Report", lambda: self._run_locator_migration_action("copy")),
        ):
            ttk.Button(locator_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        locator_exec_box = ttk.Frame(parent, style="Panel.TFrame")
        locator_exec_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(locator_exec_box, text="Locator Migration Execution", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.locator_execution_plan_id_var = tk.StringVar(value="")
        self.locator_execution_proposal_id_var = tk.StringVar(value="")
        self.locator_execution_id_var = tk.StringVar(value="")
        self.locator_execution_confirmation_var = tk.StringVar(value="")
        self.locator_execution_dry_run_var = tk.BooleanVar(value=True)
        for variable in (
            self.locator_execution_plan_id_var,
            self.locator_execution_proposal_id_var,
            self.locator_execution_id_var,
            self.locator_execution_confirmation_var,
        ):
            tk.Entry(locator_exec_box, textvariable=variable, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4 if variable is self.locator_execution_plan_id_var else 0, 3))
        ttk.Checkbutton(locator_exec_box, text="Dry Run", variable=self.locator_execution_dry_run_var).pack(anchor="w", pady=(0, 4))
        self.locator_execution_status_var = tk.StringVar(value="Validation Status: unknown\nProposal Classification: unknown\nBefore-State Current: unknown\nTarget Current: unknown\nWrite-Set Record Count: 0\nExecution Status: unknown\nRecords Updated: 0\nRevalidation Records Created: 0\nPost-Write Provenance: unknown\nRollback Available: no\nRollback Verified: no\nRecommended Action: Validate one safe proposal before execution.")
        tk.Label(locator_exec_box, textvariable=self.locator_execution_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        locator_exec_actions = ttk.Frame(locator_exec_box, style="Panel.TFrame")
        locator_exec_actions.pack(fill=tk.X)
        for label, command in (
            ("Validate Execution", lambda: self._run_locator_migration_execution_action("validate")),
            ("Execute One Proposal", lambda: self._run_locator_migration_execution_action("execute")),
            ("Load Receipt", lambda: self._run_locator_migration_execution_action("load")),
            ("Rollback Execution", lambda: self._run_locator_migration_execution_action("rollback")),
            ("Execution Health", lambda: self._run_locator_migration_execution_action("health")),
            ("Copy Execution Report", lambda: self._run_locator_migration_execution_action("copy")),
        ):
            ttk.Button(locator_exec_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        execution_box = ttk.Frame(parent, style="Panel.TFrame")
        execution_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(execution_box, text="Corpus Execution and Recovery", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.corpus_execution_batch_id_var = tk.StringVar(value="")
        self.corpus_execution_repair_id_var = tk.StringVar(value="")
        self.corpus_execution_dry_run_var = tk.BooleanVar(value=True)
        self.corpus_execution_limit_var = tk.StringVar(value="25")
        self.corpus_execution_retry_failures_var = tk.BooleanVar(value=False)
        self.corpus_execution_force_var = tk.BooleanVar(value=False)
        tk.Entry(execution_box, textvariable=self.corpus_execution_batch_id_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(4, 3))
        options_row = ttk.Frame(execution_box, style="Panel.TFrame")
        options_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Checkbutton(options_row, text="Dry Run", variable=self.corpus_execution_dry_run_var).pack(side=tk.LEFT)
        ttk.Checkbutton(options_row, text="Retry Failures", variable=self.corpus_execution_retry_failures_var).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Checkbutton(options_row, text="Force Re-Execution", variable=self.corpus_execution_force_var).pack(side=tk.LEFT, padx=(6, 0))
        tk.Entry(execution_box, textvariable=self.corpus_execution_limit_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        tk.Entry(execution_box, textvariable=self.corpus_execution_repair_id_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 3))
        self.corpus_execution_status_var = tk.StringVar(value="Batch status: unknown\nLock status: unknown\nIndex status: unknown")
        tk.Label(execution_box, textvariable=self.corpus_execution_status_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        execution_actions = ttk.Frame(execution_box, style="Panel.TFrame")
        execution_actions.pack(fill=tk.X)
        for label, command in (
            ("Validate Dependencies", self._validate_corpus_execution_dependencies),
            ("Execute Batch", self._execute_corpus_batch),
            ("Pause Batch", self._pause_corpus_batch),
            ("Resume Batch", self._resume_corpus_batch),
            ("Cancel Batch", self._cancel_corpus_batch),
            ("Execution History", self._show_corpus_execution_history),
            ("Detect Stale Execution", self._detect_stale_corpus_execution),
            ("Index Integrity", self._show_corpus_index_integrity),
            ("Build Repair Plan", self._build_corpus_repair_plan_ui),
            ("Verify Repair Backup", self._verify_corpus_repair_backup_ui),
            ("Execute Repair", self._execute_corpus_repair_ui),
            ("Rollback Repair", self._rollback_corpus_repair_ui),
            ("Quarantine Summary", self._show_corpus_quarantine_summary),
            ("Partial-Write Check", self._show_partial_corpus_writes),
            ("Copy Execution Report", self._copy_corpus_execution_report),
        ):
            ttk.Button(execution_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        review_box = ttk.Frame(parent, style="Panel.TFrame")
        review_box.pack(fill=tk.X, pady=(0, 8))
        tk.Label(review_box, text="Proposal Review Dashboard", bg=PALETTE["panel"], fg=PALETTE["accent_dark"], font=("Georgia", 9, "bold"), anchor="w").pack(fill=tk.X)
        self.proposal_review_status_filter_var = tk.StringVar(value="any")
        self.proposal_review_readiness_filter_var = tk.StringVar(value="any")
        self.proposal_review_conflict_filter_var = tk.StringVar(value="any")
        self.proposal_review_duplicate_filter_var = tk.StringVar(value="any")
        self.proposal_review_note_var = tk.StringVar(value="")
        self.proposal_review_state: dict[str, object] = {}
        filter_row = ttk.Frame(review_box, style="Panel.TFrame")
        filter_row.pack(fill=tk.X, pady=(4, 4))
        ttk.Combobox(filter_row, textvariable=self.proposal_review_status_filter_var, values=("any", "pending_review", "in_review", "needs_more_source", "needs_better_citation", "rejected", "deferred", "duplicate", "conflict_review", "approved_for_later_promotion"), state="readonly", width=13).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Combobox(filter_row, textvariable=self.proposal_review_readiness_filter_var, values=("any", "ready", "review_ready", "not_ready", "weak", "blocked"), state="readonly", width=10).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Combobox(filter_row, textvariable=self.proposal_review_conflict_filter_var, values=("any", "none", "possible_conflict", "conflict_review", "unknown"), state="readonly", width=12).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Combobox(filter_row, textvariable=self.proposal_review_duplicate_filter_var, values=("any", "none", "possible_duplicate", "duplicate", "unknown"), state="readonly", width=12).pack(side=tk.LEFT)
        ttk.Button(review_box, text="Refresh Queue", command=self._refresh_proposal_review_queue, style="Compact.TButton").pack(fill=tk.X, pady=(0, 4))
        self.proposal_review_queue_list = tk.Listbox(review_box, height=4, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT, exportselection=False)
        self.proposal_review_queue_list.pack(fill=tk.X, pady=(0, 5))
        self.proposal_review_queue_list.bind("<<ListboxSelect>>", self._on_proposal_review_selected)
        self.proposal_review_selected_var = tk.StringVar(value="Selected Proposal: None\nSelect a proposal to review.")
        tk.Label(review_box, textvariable=self.proposal_review_selected_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT, anchor="w", padx=7, pady=6).pack(fill=tk.X, pady=(0, 5))
        tk.Entry(review_box, textvariable=self.proposal_review_note_var, bg=PALETTE["panel_alt"], fg=PALETTE["text"], relief=tk.FLAT).pack(fill=tk.X, pady=(0, 4))
        review_actions = ttk.Frame(review_box, style="Panel.TFrame")
        review_actions.pack(fill=tk.X)
        for label, command in (
            ("Add Note", self._add_selected_proposal_review_note),
            ("In Review", lambda: self._apply_selected_proposal_review_action("in_review")),
            ("Needs Source", lambda: self._apply_selected_proposal_review_action("needs_more_source")),
            ("Better Citation", lambda: self._apply_selected_proposal_review_action("needs_better_citation")),
            ("Reject", lambda: self._apply_selected_proposal_review_action("reject")),
            ("Defer", lambda: self._apply_selected_proposal_review_action("defer")),
            ("Duplicate", lambda: self._apply_selected_proposal_review_action("mark_duplicate")),
            ("Conflict Review", lambda: self._apply_selected_proposal_review_action("mark_conflict_review")),
            ("Approve Later", lambda: self._apply_selected_proposal_review_action("approve_for_later_promotion")),
            ("Copy Review Summary", self._copy_selected_proposal_review_summary),
            ("Build Evidence Binder", self._build_selected_evidence_binder),
            ("Evidence Summary", self._show_selected_evidence_binder_summary),
            ("Copy Evidence Report", self._copy_selected_evidence_binder_report),
        ):
            ttk.Button(review_actions, text=label, command=command, style="Compact.TButton").pack(fill=tk.X, pady=(0, 3))
        notes = tk.Text(
            parent,
            width=40,
            height=8,
            bg=PALETTE["panel_alt"],
            fg=PALETTE["text"],
            relief=tk.FLAT,
            wrap=tk.WORD,
            font=("Segoe UI", 8),
            padx=8,
            pady=7,
            highlightthickness=1,
            highlightbackground=PALETTE["panel_line"],
        )
        notes.pack(fill=tk.BOTH, expand=True)
        notes.insert(
            tk.END,
            "Processing stages\n"
            "1. Choose a PDF source file.\n"
            "2. Register it into controlled local source-document storage.\n"
            "3. Extract text only for text-based PDFs.\n"
            "4. Review extracted text manually before any later parsing/import phase.\n\n"
            "Current safety rule: PDF intake never changes chart data or imports election inputs automatically.",
        )
        notes.configure(state=tk.DISABLED)

    def _choose_pdf_intake_file(self) -> None:
        path_text = filedialog.askopenfilename(
            title="Choose source PDF",
            filetypes=(("PDF files", "*.pdf"), ("All files", "*.*")),
        )
        if not path_text:
            self.status_var.set("PDF Intake cancelled.")
            return
        path = Path(path_text)
        if path.suffix.lower() != ".pdf":
            self.status_var.set("PDF Intake expects a .pdf file.")
            return
        try:
            size_bytes = path.stat().st_size
        except OSError as exc:
            self.status_var.set(f"PDF Intake could not read file metadata: {exc}")
            return
        self.pdf_intake_payload = {
            "path": str(path),
            "name": path.name,
            "size_bytes": size_bytes,
            "status": "selected_metadata_only",
        }
        self.pdf_intake_status_var.set(self._pdf_intake_status_text())
        self._log_event(f"PDF selected for intake: {path.name} ({size_bytes} bytes)")
        self.status_var.set("PDF selected. Register Source to create a controlled source record.")

    def _register_pdf_intake_source(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        path_text = str(payload.get("path") or "") if isinstance(payload, dict) else ""
        if not path_text:
            self.status_var.set("Choose a PDF before registering a source record.")
            return
        try:
            record = register_pdf_source(path_text)
        except Exception as exc:
            self.status_var.set(f"PDF source registration failed: {exc}")
            return
        self.pdf_intake_payload = record.to_json()
        self.pdf_intake_status_var.set(self._pdf_intake_status_text())
        self._log_event(f"PDF source registered: {record.document_id}")
        self.status_var.set("PDF source registered. Text extraction is available for text-based PDFs.")

    def _run_pdf_intake_preflight(self, regenerate: bool = False) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register the PDF source before running preflight.")
            return
        report = run_document_preflight(document_id, regenerate=regenerate)
        self.pdf_intake_payload = dict(payload)
        self.pdf_intake_payload["preflight_summary"] = get_document_preflight_summary(document_id)
        self.pdf_intake_status_var.set(self._pdf_intake_status_text())
        self.status_var.set(f"PDF preflight {report.verdict}: {report.recommended_action}")
        self._log_event(f"PDF preflight for {document_id}: {report.verdict}")

    def _copy_pdf_preflight_summary(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register the PDF source before copying a preflight summary.")
            return
        text = format_preflight_report_text(document_id)
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception as exc:
            self.status_var.set(f"Could not copy preflight summary: {exc}")
            return
        self.status_var.set("Preflight summary copied without source paths or extracted text.")

    def _extract_pdf_intake_text(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register the PDF source before extracting text.")
            return
        gate = can_extract_after_preflight(document_id)
        if gate.get("verdict") == "NOT_RUN":
            self.pdf_intake_payload = dict(payload)
            self.pdf_intake_payload["preflight_summary"] = get_document_preflight_summary(document_id)
            self.pdf_intake_status_var.set(self._pdf_intake_status_text())
            self.status_var.set("Run preflight before extraction. Backend compatibility still allows extraction outside this UI.")
            return
        if not gate.get("allowed"):
            self.pdf_intake_payload = dict(payload)
            self.pdf_intake_payload["preflight_summary"] = get_document_preflight_summary(document_id)
            self.pdf_intake_status_var.set(self._pdf_intake_status_text())
            blockers = "; ".join(str(item) for item in gate.get("blockers", [])[:3]) or str(gate.get("reason"))
            self.status_var.set(f"PDF extraction blocked by preflight: {blockers}")
            return
        record = extract_pdf_text(document_id)
        self.pdf_intake_payload = record.to_json()
        self.pdf_intake_payload["preflight_summary"] = get_document_preflight_summary(document_id)
        self.pdf_intake_status_var.set(self._pdf_intake_status_text())
        if record.extraction_status == "extracted":
            caution = " Review preflight warnings and chunks before proposals." if gate.get("verdict") == "WARNING" else ""
            self.status_var.set("PDF text extracted. Review the text before any future parsing/import step." + caution)
        else:
            self.status_var.set(f"PDF extraction status: {record.extraction_status}.")
        self._log_event(f"PDF extraction status for {record.document_id}: {record.extraction_status}")
    def _chunk_pdf_intake_text(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register and extract the PDF before chunking text.")
            return
        chunks = chunk_extracted_text(document_id)
        if chunks:
            self.pdf_intake_payload = dict(payload)
            self.pdf_intake_payload["chunk_count"] = len(chunks)
            self.pdf_intake_status_var.set(self._pdf_intake_status_text())
            self.status_var.set(f"PDF knowledge chunks ready: {len(chunks)} chunk(s).")
            self._log_event(f"PDF chunks ready for {document_id}: {len(chunks)}")
        else:
            self.status_var.set("No chunks created. Confirm text extraction succeeded before chunking.")

    def _show_pdf_knowledge_health(self) -> None:
        health = get_source_knowledge_health()
        self.status_var.set(
            f"Source knowledge health: {health.status}; docs {health.documents}, chunks {health.chunks}, "
            f"pending proposals {health.proposals_pending}, citations {health.citations}."
        )
        self._log_event(f"Source knowledge health checked: {health.status}")

    def _build_pdf_page_diagnostics(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register and extract the PDF before building page diagnostics.")
            return
        diagnostics = build_page_diagnostics(document_id)
        self.pdf_intake_payload = dict(payload)
        self.pdf_intake_payload["reader_state"] = get_document_reader_state(document_id)
        self.pdf_intake_status_var.set(self._pdf_intake_status_text())
        self.status_var.set(f"Page diagnostics ready: {len(diagnostics)} page(s) diagnosed.")

    def _build_pdf_structure_map(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register and extract the PDF before building a structure map.")
            return
        try:
            structure = build_document_structure_map(document_id)
            summary = get_document_structure_summary(document_id)
        except Exception as exc:
            self.status_var.set(f"Structure map failed: {exc}")
            return
        self.pdf_intake_payload = dict(payload)
        self.pdf_intake_payload["structure_summary"] = summary
        self.pdf_intake_status_var.set(self._pdf_intake_status_text())
        self.status_var.set(
            f"Structure map built: {len(structure.get('headings', []))} heading(s), "
            f"{len(structure.get('sections', []))} section(s)."
        )

    def _show_pdf_structure_summary(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register a PDF before checking structure summary.")
            return
        summary = get_document_structure_summary(document_id)
        self.pdf_intake_payload = dict(payload)
        self.pdf_intake_payload["structure_summary"] = summary
        self.pdf_intake_status_var.set(self._pdf_intake_status_text())
        self.status_var.set(
            f"Structure: {summary.get('status')}; headings {summary.get('headings')}, sections {summary.get('sections')}, "
            f"tables {summary.get('tables')}, figures {summary.get('figures')}, re-chunk {summary.get('rechunk_strategy')}."
        )

    def _show_pdf_chunk_quality(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register and chunk the PDF before chunk quality analysis.")
            return
        quality = analyze_chunk_quality(document_id)
        self.status_var.set(
            f"Chunk quality: {quality.get('quality_status')}; chunks {quality.get('chunk_count')}, "
            f"short {quality.get('very_short_chunks', 0)}, long {quality.get('very_long_chunks', 0)}, "
            f"no page refs {quality.get('chunks_without_page_reference', 0)}."
        )

    def _show_pdf_rechunk_plan(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register and chunk the PDF before re-chunk recommendation.")
            return
        plan = recommend_rechunk_plan(document_id)
        self.status_var.set(
            f"Re-chunk recommendation: {plan.get('strategy')} (recommended: {plan.get('recommended')}). "
            f"Reason: {plan.get('reason')}. No chunks were changed."
        )
    def _show_pdf_search_health(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else None
        health = get_source_search_health(document_id or None)
        self.status_var.set(
            f"Source search health: {health.status}; chunks {health.chunks_indexed}, broken links {health.broken_chunk_links}, "
            f"docs without chunks {health.documents_without_chunks}."
        )
        self._log_event(f"Source search health checked: {health.status}")

    def _current_source_document_id(self) -> str:
        payload = getattr(self, "pdf_intake_payload", {})
        if isinstance(payload, dict):
            return str(payload.get("document_id") or "")
        return ""

    def _load_source_reliability_summary(self) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        try:
            rel = recalculate_source_reliability(document_id)
        except Exception as exc:
            self.status_var.set(f"Source reliability unavailable: {exc}")
            return
        self.status_var.set(f"Reliability: {rel.get('reliability_band')}; staleness {rel.get('staleness_status')}; authority {rel.get('authority_level')}; type {rel.get('source_type')}.")

    def _update_source_reliability_metadata(self) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        metadata = {
            "source_type": self.source_reliability_type_var.get(),
            "authority_level": self.source_reliability_authority_var.get(),
            "publication_date": self.source_reliability_publication_var.get().strip() or None,
            "modified_date": self.source_reliability_modified_var.get().strip() or None,
            "manual_title": self.source_reliability_title_var.get().strip() or None,
            "version_label": self.source_reliability_version_var.get().strip() or None,
        }
        try:
            result = update_source_metadata_for_reliability(document_id, metadata, note="Desktop metadata update")
        except Exception as exc:
            self.status_var.set(f"Could not update source metadata: {exc}")
            return
        self.status_var.set(f"Source metadata updated: {result.get('reliability_band')} / {result.get('staleness_status')}.")

    def _recalculate_source_reliability(self) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        rel = recalculate_source_reliability(document_id)
        self.status_var.set(f"Reliability recalculated: {rel.get('reliability_score')} - {rel.get('reliability_band')}; warnings {len(rel.get('warnings', []))}.")

    def _detect_source_duplicate_identity(self) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        duplicate = detect_duplicate_source_identity(document_id)
        self.status_var.set(f"Duplicate source identity: {duplicate.get('status')}; matches {len(duplicate.get('matches', []))}.")

    def _show_source_quality_dashboard(self) -> None:
        dashboard = get_source_quality_dashboard(limit=10)
        self.status_var.set(f"Source quality: total {dashboard.get('total_sources')}; strong {dashboard.get('strong_sources')}; usable {dashboard.get('usable_sources')}; unknown {dashboard.get('unknown_sources')}; duplicates {dashboard.get('possible_duplicates')}.")

    def _copy_source_reliability_report(self) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        text = format_source_reliability_report_text(document_id, public_safe=True)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("Public-safe source reliability report copied.")

    def _link_source_replacement(self) -> None:
        document_id = self._current_source_document_id()
        target = self.source_reliability_replacement_var.get().strip() if hasattr(self, "source_reliability_replacement_var") else ""
        if not document_id or not target:
            self.status_var.set("Select a source and enter a replacement source ID before linking.")
            return
        try:
            link_source_replacement(document_id, target, "replaced_by", "Desktop replacement link")
        except Exception as exc:
            self.status_var.set(f"Could not link replacement source: {exc}")
            return
        self.status_var.set("Replacement source linked. Existing citations and binders were not rewritten.")
    def _build_source_corpus_inventory(self) -> None:
        try:
            inventory = build_source_corpus_inventory(regenerate=True)
            health = get_source_corpus_health()
        except Exception as exc:
            self.status_var.set(f"Could not build source corpus inventory: {exc}")
            return
        self._set_source_corpus_status(health)
        self.status_var.set(f"Source corpus inventory built: {inventory.get('source_count', 0)} source(s).")

    def _show_source_corpus_health(self) -> None:
        try:
            health = get_source_corpus_health()
        except Exception as exc:
            self.status_var.set(f"Source corpus health unavailable: {exc}")
            return
        self._set_source_corpus_status(health)
        self.status_var.set(f"Corpus health: {health.get('status')}; sources {health.get('source_count')}; warnings {health.get('warning_sources')}; critical {health.get('critical_sources')}.")

    def _show_corpus_missing_steps(self) -> None:
        try:
            missing = detect_corpus_missing_steps()
        except Exception as exc:
            self.status_var.set(f"Missing-step review unavailable: {exc}")
            return
        self.status_var.set(
            f"Missing steps: preflight {missing.get('sources_missing_preflight')}, extraction {missing.get('sources_missing_extraction')}, "
            f"chunks {missing.get('sources_missing_chunks')}, structure {missing.get('sources_missing_structure')}, reliability {missing.get('sources_missing_reliability')}.")

    def _show_failed_source_tasks(self) -> None:
        failed = list_failed_source_tasks()
        self.status_var.set(f"Failed source tasks: {failed.get('failed_count', 0)}. Retry queue is not auto-run.")

    def _show_duplicate_source_queue(self) -> None:
        queue = list_duplicate_source_queue(limit=20)
        self.status_var.set(f"Duplicate source queue: {queue.get('duplicate_count', 0)} possible match(es). No sources were merged.")

    def _show_superseded_source_queue(self) -> None:
        queue = list_superseded_source_queue(limit=20)
        self.status_var.set(f"Superseded source queue: {queue.get('superseded_count', 0)} item(s). Citations were not rewritten.")

    def _bulk_reliability_recheck(self) -> None:
        result = bulk_recalculate_source_reliability(dry_run=True, limit=25)
        self.status_var.set(f"Bulk reliability recheck dry-run: {result.get('sources_planned', 0)} source(s) planned; none changed.")

    def _bulk_evidence_refresh(self) -> None:
        result = bulk_refresh_evidence_binders(dry_run=True, limit=25)
        self.status_var.set(f"Bulk evidence refresh dry-run: {result.get('binders_planned', 0)} binder(s) planned; none refreshed.")

    def _copy_source_corpus_report(self) -> None:
        try:
            text = format_source_corpus_report_text(public_safe=True)
        except Exception as exc:
            self.status_var.set(f"Could not copy source corpus report: {exc}")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("Public-safe source corpus report copied.")

    def _set_source_corpus_status(self, health: dict[str, object]) -> None:
        coverage = health.get("coverage", {}) if isinstance(health, dict) else {}
        risks = health.get("risks", {}) if isinstance(health, dict) else {}
        def pct(key: str) -> str:
            try:
                return f"{float(coverage.get(key, 0)) * 100:.0f}%"
            except Exception:
                return "Unknown"
        text = (
            f"Corpus Health: {health.get('status', 'unknown')}\n"
            f"Sources: {health.get('source_count', 0)} | Healthy: {health.get('healthy_sources', 0)} | Warning: {health.get('warning_sources', 0)} | Critical: {health.get('critical_sources', 0)}\n"
            f"Coverage: preflight {pct('preflight')}, extraction {pct('extraction')}, chunking {pct('chunks')}, structure {pct('structure')}, reliability {pct('reliability')}, evidence {pct('evidence_binders')}\n"
            f"Risks: duplicates {risks.get('duplicates', 0)}, superseded {risks.get('superseded_sources', 0)}, stale {risks.get('stale_sources', 0)}, failed {risks.get('failed_sources', 0)}, privacy {risks.get('privacy_warnings', 0)}\n"
            f"Recommended Action: {health.get('recommended_action', 'Unknown')}")
        if hasattr(self, "source_corpus_status_var"):
            self.source_corpus_status_var.set(text)

    def _run_source_impact_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        try:
            if action == "analyze":
                impact = analyze_source_change_impact(document_id)
                self._set_source_impact_status(impact)
                self.status_var.set(f"Source impact analyzed: {impact.get('impact_severity')} severity.")
            elif action == "queue":
                item = create_source_revalidation_item(document_id)
                self.source_impact_selected_queue_item_id = str(item.get("queue_item_id") or "")
                self._set_source_impact_status(analyze_source_change_impact(document_id))
                self.status_var.set(f"Revalidation queue item ready: {item.get('queue_item_id')}.")
            elif action == "queue_view":
                queue = list_source_revalidation_queue(limit=20)
                selected = next((item for item in queue.get("items", []) if item.get("document_id") == document_id), None)
                if selected is not None:
                    self.source_impact_selected_queue_item_id = str(selected.get("queue_item_id") or "")
                self._set_source_impact_status(analyze_source_change_impact(document_id))
                self.status_var.set(f"Revalidation queue items loaded: {queue.get('count', 0)}.")
            elif action == "reviewed":
                if not getattr(self, "source_impact_selected_queue_item_id", ""):
                    self.status_var.set("No revalidation queue item selected. View the queue first.")
                    return
                item = update_source_revalidation_status(self.source_impact_selected_queue_item_id, "reviewed", note="Desktop review")
                self.status_var.set(f"Revalidation item marked reviewed: {item.get('queue_item_id')}.")
            elif action == "copy":
                text = format_source_impact_report_text(document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self._set_source_impact_status(analyze_source_change_impact(document_id))
                self.status_var.set("Public-safe source impact report copied.")
        except Exception as exc:
            self.status_var.set(f"Source impact action failed: {exc}")

    def _set_source_impact_status(self, impact: dict[str, object]) -> None:
        text = (
            f"Change Type: {impact.get('change_type') or 'unknown'}\n"
            f"Impact Severity: {impact.get('impact_severity', 'unknown')}\n"
            f"Affected Citations: {impact.get('affected_counts', {}).get('citations')}\n"
            f"Affected Proposals: {impact.get('affected_counts', {}).get('proposals')}\n"
            f"Affected Reviews: {impact.get('affected_counts', {}).get('proposal_reviews')}\n"
            f"Affected Evidence Binders: {impact.get('affected_counts', {}).get('evidence_binders')}\n"
            f"Recommended Action: {impact.get('recommended_action', 'Unknown')}"
        )
        if hasattr(self, "source_impact_status_var"):
            self.source_impact_status_var.set(text)

    def _run_source_revalidation_action(self, action: str) -> None:
        queue_item_id = self.source_revalidation_queue_item_var.get().strip() if hasattr(self, "source_revalidation_queue_item_var") else ""
        if not queue_item_id:
            self.status_var.set("Enter a revalidation queue item ID first.")
            return
        try:
            if action == "load":
                workspace = build_revalidation_review_workspace(queue_item_id)
                self.source_revalidation_workspace_state = workspace
                self._set_source_revalidation_status(workspace, workspace.get("evidence_recheck", {}), None, None)
                self.status_var.set(f"Review workspace loaded: {queue_item_id}.")
            elif action == "evidence":
                workspace = self.source_revalidation_workspace_state or build_revalidation_review_workspace(queue_item_id)
                evidence = build_revalidation_evidence_recheck(queue_item_id)
                self.source_revalidation_workspace_state = workspace
                self._set_source_revalidation_status(workspace, evidence, None, None)
                self.status_var.set(f"Evidence recheck loaded: {queue_item_id}.")
            elif action == "finalize":
                dispositions = self._category_level_dispositions()
                result = finalize_source_revalidation_review(
                    queue_item_id,
                    self.source_revalidation_decision_var.get(),
                    dispositions,
                    review_note=self.source_revalidation_note_var.get().strip() or None,
                )
                workspace = build_revalidation_review_workspace(queue_item_id)
                self.source_revalidation_workspace_state = workspace
                self._set_source_revalidation_status(workspace, workspace.get("evidence_recheck", {}), result.get("closure"), result.get("resolution"))
                self.status_var.set(f"Revalidation review processed: {queue_item_id}.")
            elif action == "resolution":
                workspace = self.source_revalidation_workspace_state or build_revalidation_review_workspace(queue_item_id)
                resolution = load_source_revalidation_resolution(queue_item_id)
                self.source_revalidation_workspace_state = workspace
                self._set_source_revalidation_status(workspace, workspace.get("evidence_recheck", {}), None, resolution.get("resolution"))
                self.status_var.set(f"Resolution loaded: {queue_item_id}.")
            elif action == "copy":
                text = format_source_revalidation_resolution_report(queue_item_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe resolution report copied.")
        except Exception as exc:
            self.status_var.set(f"Source revalidation action failed: {exc}")

    def _category_level_dispositions(self) -> dict[str, object]:
        workspace = self.source_revalidation_workspace_state or {}
        affected = workspace.get("affected_record_ids", {}) if isinstance(workspace, dict) else {}
        mapping = {
            "citations": (affected.get("citation_ids", []), self.source_revalidation_citation_disp_var.get()),
            "proposals": (affected.get("proposal_ids", []), self.source_revalidation_proposal_disp_var.get()),
            "proposal_reviews": (affected.get("proposal_review_ids", []), self.source_revalidation_review_disp_var.get()),
            "evidence_binders": (affected.get("evidence_binder_ids", []), self.source_revalidation_binder_disp_var.get()),
        }
        return {
            category: {str(record_id): str(value) for record_id in record_ids}
            for category, (record_ids, value) in mapping.items()
            if record_ids
        }

    def _set_source_revalidation_status(
        self,
        workspace: dict[str, object],
        evidence: dict[str, object] | None,
        closure: dict[str, object] | None,
        resolution: dict[str, object] | None,
    ) -> None:
        evidence = evidence or {}
        resolution = resolution or {}
        closure_text = "allowed" if closure and closure.get("closure_allowed") else ("blocked" if closure else "unknown")
        text = (
            f"Document ID: {workspace.get('document_id', 'unknown')}\n"
            f"Change Type: {workspace.get('change_type') or 'unknown'}\n"
            f"Impact Severity: {workspace.get('impact_severity', 'unknown')}\n"
            f"Queue Status: {workspace.get('queue_status', 'unknown')}\n"
            f"Affected citation count: {workspace.get('affected_counts', {}).get('citations')}\n"
            f"Affected proposal count: {workspace.get('affected_counts', {}).get('proposals')}\n"
            f"Affected review count: {workspace.get('affected_counts', {}).get('proposal_reviews')}\n"
            f"Affected binder count: {workspace.get('affected_counts', {}).get('evidence_binders')}\n"
            f"Evidence warnings: {len(evidence.get('warnings', []))}\n"
            f"Closure: {closure_text}\n"
            f"Resolution decision: {resolution.get('resolution_decision') or self.source_revalidation_decision_var.get()}\n"
            f"Recommended action: {workspace.get('recommended_action', 'Unknown')}"
        )
        if hasattr(self, "source_revalidation_status_var"):
            self.source_revalidation_status_var.set(text)

    def _run_document_manifest_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        try:
            if action == "build":
                manifest = build_document_manifest(document_id, regenerate=True)
                self._set_document_manifest_status(get_document_manifest_summary(document_id), None)
                self.status_var.set(f"Document manifest built: revision {manifest.get('source_revision')}.")
            elif action == "readiness":
                build_document_manifest(document_id, regenerate=False)
                readiness = get_document_backend_readiness(document_id)
                self._set_document_manifest_status(get_document_manifest_summary(document_id), readiness)
                self.status_var.set(f"Backend readiness: {readiness.get('status')}.")
            elif action == "reconcile":
                build_document_manifest(document_id, regenerate=False)
                consistency = reconcile_document_subsystems(document_id)
                summary = get_document_manifest_summary(document_id)
                summary["consistency_warning_count"] = consistency.get("warning_checks", 0)
                summary["consistency_critical_count"] = consistency.get("critical_checks", 0)
                self._set_document_manifest_status(summary, None)
                self.status_var.set(f"Subsystem reconciliation: {consistency.get('status')}.")
            elif action == "locator":
                locator = {
                    "document_id": document_id,
                    "page_number": self.document_manifest_page_var.get().strip(),
                    "chunk_id": self.document_manifest_chunk_var.get().strip(),
                    "character_start": self.document_manifest_start_var.get().strip(),
                    "character_end": self.document_manifest_end_var.get().strip(),
                }
                result = validate_source_locator(locator)
                self._set_document_manifest_status(get_document_manifest_summary(document_id), result)
                self.status_var.set(f"Locator validation: valid={result.get('valid')}.")
            elif action == "copy":
                text = format_document_manifest_report(document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self._set_document_manifest_status(get_document_manifest_summary(document_id), None)
                self.status_var.set("Public-safe manifest report copied.")
        except Exception as exc:
            self.status_var.set(f"Document manifest action failed: {exc}")

    def _set_document_manifest_status(self, summary: dict[str, object], extra: dict[str, object] | None) -> None:
        extra = extra or {}
        text = (
            f"Document ID: {summary.get('document_id', 'unknown')}\n"
            f"Source Revision: {summary.get('source_revision', 'unknown')}\n"
            f"Lifecycle Status: {summary.get('lifecycle_status', 'unknown')}\n"
            f"Backend Readiness: {extra.get('status') or summary.get('backend_readiness', 'unknown')}\n"
            f"Preflight Status: {summary.get('preflight_status', 'unknown')}\n"
            f"Extraction Status: {summary.get('extraction_status', 'unknown')}\n"
            f"Chunk Status: {summary.get('chunk_status', 'unknown')}\n"
            f"Diagnostics Status: {summary.get('diagnostics_status', 'unknown')}\n"
            f"Structure Status: {summary.get('structure_status', 'unknown')}\n"
            f"Reliability Status: {summary.get('reliability_status', 'unknown')}\n"
            f"Stale Component Count: {summary.get('stale_component_count', 0)}\n"
            f"Consistency Warning Count: {summary.get('consistency_warning_count', 0)}\n"
            f"Consistency Critical Count: {summary.get('consistency_critical_count', 0)}\n"
            f"Recommended Action: {summary.get('recommended_action', extra.get('recommended_action', 'Unknown'))}"
        )
        if hasattr(self, "document_manifest_status_var"):
            self.document_manifest_status_var.set(text)

    def _run_source_workflow_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        stage = self.source_workflow_stage_var.get().strip() if hasattr(self, "source_workflow_stage_var") else ""
        plan_id = self.source_workflow_plan_id_var.get().strip() if hasattr(self, "source_workflow_plan_id_var") else ""
        try:
            if action == "fingerprint":
                fingerprint = calculate_pipeline_state_fingerprint(document_id)
                manifest = build_document_manifest(document_id, regenerate=False)
                recommendation = recommend_next_source_workflow_stage(document_id)
                self._set_source_workflow_status(manifest, recommendation, {"allowed": True}, None, None, fingerprint=fingerprint)
                self.status_var.set(f"Pipeline fingerprint calculated: {fingerprint.get('fingerprint')}.")
            elif action == "recommend":
                manifest = build_document_manifest(document_id, regenerate=False)
                recommendation = recommend_next_source_workflow_stage(document_id)
                self._set_source_workflow_status(manifest, recommendation, {"allowed": recommendation.get("dependencies_satisfied")}, None, None)
                self.status_var.set(f"Recommended stage: {recommendation.get('recommended_stage')}.")
            elif action == "plan":
                plan = create_source_workflow_plan(document_id, requested_stage=stage or None, dry_run=bool(self.source_workflow_dry_run_var.get()))
                self.source_workflow_plan_id_var.set(str(plan.get("workflow_plan_id") or ""))
                manifest = build_document_manifest(document_id, regenerate=False)
                recommendation = recommend_next_source_workflow_stage(document_id)
                deps = {"allowed": plan.get("dependencies", {}).get("allowed", False)}
                self._set_source_workflow_status(manifest, recommendation, deps, plan, None)
                self.status_var.set(f"Workflow plan created: {plan.get('workflow_plan_id')}.")
            elif action == "execute":
                if not plan_id:
                    self.status_var.set("Create or enter a workflow plan ID before execution.")
                    return
                result = execute_source_workflow_stage(plan_id, dry_run=bool(self.source_workflow_dry_run_var.get()))
                manifest = build_document_manifest(document_id, regenerate=False)
                recommendation = recommend_next_source_workflow_stage(document_id)
                plan = load_source_workflow_plan(plan_id)
                self._set_source_workflow_status(manifest, recommendation, {"allowed": True}, plan, result)
                self.status_var.set(f"Workflow stage result: {result.get('status')}.")
            elif action == "resume":
                manifest = build_document_manifest(document_id, regenerate=False)
                resume = get_source_workflow_resume_state(document_id)
                recommendation = recommend_next_source_workflow_stage(document_id)
                self._set_source_workflow_status(manifest, recommendation, {"allowed": resume.get("executable")}, None, {"status": "resume_ready", "next_recommended_stage": resume.get("recommended_stage")})
                self.status_var.set(f"Resume stage: {resume.get('recommended_stage')}.")
            elif action == "copy":
                text = format_source_workflow_report(document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                manifest = build_document_manifest(document_id, regenerate=False)
                recommendation = recommend_next_source_workflow_stage(document_id)
                self._set_source_workflow_status(manifest, recommendation, {"allowed": recommendation.get("dependencies_satisfied")}, None, None)
                self.status_var.set("Public-safe workflow report copied.")
        except Exception as exc:
            self.status_var.set(f"Source workflow action failed: {exc}")

    def _set_source_workflow_status(
        self,
        manifest: dict[str, object],
        recommendation: dict[str, object],
        dependencies: dict[str, object] | None,
        plan: dict[str, object] | None,
        execution: dict[str, object] | None,
        *,
        fingerprint: dict[str, object] | None = None,
    ) -> None:
        dependencies = dependencies or {}
        plan = plan or {}
        execution = execution or {}
        readiness = (manifest.get("backend_readiness") or {}).get("status")
        recommended_action = (
            f"Create a workflow plan for {recommendation.get('recommended_stage')}."
            if recommendation.get("recommended_stage") not in {None, 'none'}
            else (manifest.get("backend_readiness") or {}).get("recommended_action", "Unknown")
        )
        text = (
            f"Document ID: {manifest.get('document_id', 'unknown')}\n"
            f"Pipeline Fingerprint Changed: {manifest.get('fingerprint_changed', False)}\n"
            f"Backend Readiness: {readiness}\n"
            f"Recommended Stage: {recommendation.get('recommended_stage', 'unknown')}\n"
            f"Dependencies Satisfied: {dependencies.get('allowed', 'unknown')}\n"
            f"Selected Stage: {self.source_workflow_stage_var.get() or recommendation.get('recommended_stage') or 'none'}\n"
            f"Dry Run: {self.source_workflow_dry_run_var.get() if hasattr(self, 'source_workflow_dry_run_var') else True}\n"
            f"Plan Status: {plan.get('status', 'unknown')}\n"
            f"Last Execution Status: {execution.get('status', 'unknown')}\n"
            f"Next Recommended Stage: {execution.get('next_recommended_stage') or recommendation.get('recommended_stage') or 'none'}\n"
            f"Recommended Action: {recommended_action}"
        )
        if hasattr(self, "source_workflow_status_var"):
            self.source_workflow_status_var.set(text)

    def _run_document_content_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        topic = self.document_content_topic_query_var.get().strip() if hasattr(self, "document_content_topic_query_var") else ""
        raw_terms = self.document_content_topic_terms_var.get().strip() if hasattr(self, "document_content_topic_terms_var") else ""
        topic_terms = [item.strip() for item in raw_terms.split(",") if item.strip()]
        try:
            if action == "build":
                build_document_content_map(document_id, topic_terms=topic_terms or None, regenerate=True)
                summary = get_document_content_map_summary(document_id)
                self._set_document_content_status(summary, 0)
                self.status_var.set(f"Document content map built: {summary.get('section_count')} section(s).")
            elif action == "related":
                build_document_content_map(document_id, topic_terms=topic_terms or None, regenerate=False)
                related = find_related_document_content(document_id, topic, limit=50)
                summary = get_document_content_map_summary(document_id)
                self._set_document_content_status(summary, related.get("match_count", 0))
                self.status_var.set(f"Related content matches: {related.get('match_count', 0)}.")
            elif action == "provenance":
                build_document_content_map(document_id, topic_terms=topic_terms or None, regenerate=False)
                provenance = validate_document_provenance_contract(document_id)
                summary = get_document_content_map_summary(document_id)
                summary["provenance_status"] = provenance.get("status")
                summary["critical_provenance_count"] = provenance.get("critical_checks", 0)
                self._set_document_content_status(summary, 0)
                self.status_var.set(f"Provenance status: {provenance.get('status')}.")
            elif action == "readiness":
                build_document_content_map(document_id, topic_terms=topic_terms or None, regenerate=False)
                readiness = get_reader_backend_readiness(document_id)
                summary = get_document_content_map_summary(document_id)
                summary["reader_readiness"] = readiness.get("status")
                summary["recommended_action"] = readiness.get("recommended_action")
                self._set_document_content_status(summary, 0)
                self.status_var.set(f"Reader readiness: {readiness.get('status')}.")
            elif action == "fingerprint":
                fingerprint = build_document_scoped_fingerprint(document_id)
                summary = get_document_content_map_summary(document_id)
                self._set_document_content_status(summary, 0)
                self.status_var.set(f"Document-scoped fingerprint: {fingerprint.get('fingerprint')}.")
            elif action == "copy":
                text = format_document_content_map_report(document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                summary = get_document_content_map_summary(document_id)
                self._set_document_content_status(summary, 0)
                self.status_var.set("Public-safe content-map report copied.")
        except Exception as exc:
            self.status_var.set(f"Document content action failed: {exc}")

    def _set_document_content_status(self, summary: dict[str, object], related_match_count: int) -> None:
        text = (
            f"Document ID: {summary.get('document_id', 'unknown')}\n"
            f"Source Revision: {summary.get('source_revision', 'unknown')}\n"
            f"Structure Status: {summary.get('structure_status', 'unknown')}\n"
            f"Chapter Count: {summary.get('chapter_count', 0)}\n"
            f"Section Count: {summary.get('section_count', 0)}\n"
            f"Assigned Chunk Count: {summary.get('assigned_chunk_count', 0)}\n"
            f"Unassigned Chunk Count: {summary.get('unassigned_chunk_count', 0)}\n"
            f"Topic Tag Count: {summary.get('topic_tag_count', 0)}\n"
            f"Related Match Count: {related_match_count}\n"
            f"Provenance Status: {summary.get('provenance_status', 'unknown')}\n"
            f"Critical Provenance Count: {summary.get('critical_provenance_count', 0)}\n"
            f"Reader Readiness: {summary.get('reader_readiness', 'unknown')}\n"
            f"Recommended Action: {summary.get('recommended_action', 'Unknown')}"
        )
        if hasattr(self, "document_content_status_var"):
            self.document_content_status_var.set(text)

    def _document_curation_change_payload(self) -> dict[str, object]:
        operation = self.document_curation_operation_var.get().strip() if hasattr(self, "document_curation_operation_var") else ""
        value: dict[str, object] = {}
        if operation == "rename":
            value["title"] = self.document_curation_title_var.get().strip()
        elif operation == "set_range":
            value["start_page"] = self.document_curation_start_page_var.get().strip()
            value["end_page"] = self.document_curation_end_page_var.get().strip()
            value["start_chunk_id"] = self.document_curation_start_chunk_var.get().strip()
            value["end_chunk_id"] = self.document_curation_end_chunk_var.get().strip()
        elif operation in {"assign_chunk", "unassign_chunk"}:
            value["chunk_id"] = self.document_curation_chunk_id_var.get().strip()
        elif operation in {"add_tag", "remove_tag"}:
            value["tag"] = normalize_manual_topic_tag(self.document_curation_topic_tag_var.get())
        return {
            "target_type": self.document_curation_target_type_var.get().strip() if hasattr(self, "document_curation_target_type_var") else "",
            "target_id": self.document_curation_target_id_var.get().strip() if hasattr(self, "document_curation_target_id_var") else "",
            "operation": operation,
            "value": value,
            "note": self.document_curation_note_var.get().strip() if hasattr(self, "document_curation_note_var") else "",
        }

    def _run_document_content_curation_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        try:
            if action == "workspace":
                build_document_content_map(document_id, regenerate=False)
                build_document_content_curation_workspace(document_id)
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self.status_var.set("Content curation workspace loaded.")
            elif action == "validate":
                build_document_content_map(document_id, regenerate=False)
                result = validate_content_curation_change(document_id, self._document_curation_change_payload())
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self.status_var.set("Curation change is valid." if result.get("valid") else f"Curation change rejected: {', '.join(result.get('blockers', []))}.")
            elif action == "save":
                build_document_content_map(document_id, regenerate=False)
                result = save_document_content_curation_change(document_id, self._document_curation_change_payload())
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self.status_var.set(f"Curation override {result.get('status')}.")
            elif action == "build":
                build_document_content_map(document_id, regenerate=False)
                build_curated_document_content_map(document_id)
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self.status_var.set("Curated content map view built.")
            elif action == "readiness":
                build_document_content_map(document_id, regenerate=False)
                readiness = get_document_content_curation_readiness(document_id)
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self.status_var.set(f"Curation readiness: {readiness.get('status')}.")
            elif action == "copy":
                build_document_content_map(document_id, regenerate=False)
                text = format_document_content_curation_report(document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self.status_var.set("Public-safe curation report copied.")
        except Exception as exc:
            self.status_var.set(f"Document curation action failed: {exc}")

    def _set_document_curation_status(self, summary: dict[str, object]) -> None:
        text = (
            f"Document ID: {summary.get('document_id', 'unknown')}\n"
            f"Source Revision: {summary.get('source_revision', 'unknown')}\n"
            f"Base Fingerprint Current: {summary.get('base_fingerprint_current', False)}\n"
            f"Curation Revision: {summary.get('curation_revision', 0)}\n"
            f"Curation Status: {summary.get('curation_status', 'unknown')}\n"
            f"Curation Readiness: {summary.get('curation_readiness', 'unknown')}\n"
            f"Override Count: {summary.get('override_count', 0)}\n"
            f"Valid Change Count: {summary.get('valid_change_count', 0)}\n"
            f"Invalid Change Count: {summary.get('invalid_change_count', 0)}\n"
            f"Assigned Chunk Count: {summary.get('assigned_chunk_count', 0)}\n"
            f"Unassigned Chunk Count: {summary.get('unassigned_chunk_count', 0)}\n"
            f"Manual Tag Count: {summary.get('manual_tag_count', 0)}\n"
            f"Recommended Action: {summary.get('recommended_action', 'Unknown')}"
        )
        if hasattr(self, "document_curation_status_var"):
            self.document_curation_status_var.set(text)

    def _run_document_content_history_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        try:
            if action == "list":
                result = list_document_content_curation_revisions(document_id)
                self._set_document_curation_history_status(result)
                self.status_var.set(f"Curation history loaded: {result.get('count', 0)} revision(s).")
            elif action == "compare":
                left = int(self.document_curation_history_left_var.get().strip() or "0")
                right = int(self.document_curation_history_right_var.get().strip() or "0")
                result = compare_document_content_curation_revisions(document_id, left, right)
                self._set_document_curation_history_status({"count": 0, "items": [], "warnings": result.get("warnings", []), "latest_status": result.get("status"), "current_revision": max(left, right)})
                self.status_var.set(f"Curation comparison: {result.get('status')}.")
            elif action == "restore":
                revision = int(self.document_curation_history_restore_var.get().strip() or "0")
                result = restore_document_content_curation_revision(document_id, revision)
                self._set_document_curation_history_status(list_document_content_curation_revisions(document_id))
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self.status_var.set(f"Curation restore: {result.get('status')}.")
            elif action == "copy":
                left = int(self.document_curation_history_left_var.get().strip() or "0")
                right = int(self.document_curation_history_right_var.get().strip() or "0")
                if left and right and left != right:
                    text = format_document_content_curation_comparison_report(document_id, left, right, public_safe=True)
                else:
                    text = format_document_content_curation_history_report(document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self._set_document_curation_history_status(list_document_content_curation_revisions(document_id))
                self.status_var.set("Public-safe curation history report copied.")
        except Exception as exc:
            self.status_var.set(f"Document curation history action failed: {exc}")

    def _set_document_curation_history_status(self, listing: dict[str, object]) -> None:
        items = listing.get("items", []) if isinstance(listing.get("items"), list) else []
        current = next((item for item in items if isinstance(item, dict) and item.get("is_current")), None)
        latest_status = listing.get("latest_status") or ((current or {}).get("status")) or (items[-1].get("status") if items and isinstance(items[-1], dict) else "unknown")
        text = (
            f"Revision Count: {listing.get('count', len(items))}\n"
            f"Current Revision: {(current or {}).get('curation_revision', listing.get('current_revision', 0))}\n"
            f"Latest Status: {latest_status}\n"
            f"Latest Warnings: {len(listing.get('warnings', []))}"
        )
        if hasattr(self, "document_curation_history_status_var"):
            self.document_curation_history_status_var.set(text)

    def _document_curation_rebase_resolution_payload(self) -> dict[str, object]:
        action = self.document_curation_rebase_action_var.get().strip() if hasattr(self, "document_curation_rebase_action_var") else ""
        payload: dict[str, object] = {"action": action}
        target = self.document_curation_rebase_target_var.get().strip() if hasattr(self, "document_curation_rebase_target_var") else ""
        if action == "remap_chapter":
            payload["chapter_id"] = target
        elif action in {"remap_section", "replace_assignment_target"}:
            payload["section_id"] = target
        elif action == "remap_chunk":
            payload["chunk_id"] = target
        elif action == "replace_chapter_range":
            payload["chapter_id"] = target
            payload["start_page"] = self.document_curation_rebase_start_page_var.get().strip()
            payload["end_page"] = self.document_curation_rebase_end_page_var.get().strip()
        elif action == "replace_section_range":
            payload["section_id"] = target
            payload["start_page"] = self.document_curation_rebase_start_page_var.get().strip()
            payload["end_page"] = self.document_curation_rebase_end_page_var.get().strip()
        return payload

    def _run_document_content_rebase_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        workspace_id = self.document_curation_rebase_workspace_var.get().strip() if hasattr(self, "document_curation_rebase_workspace_var") else ""
        try:
            if action == "create_current":
                result = create_rebase_workspace_from_current_stale_curation(document_id)
                if result.get("workspace"):
                    self.document_curation_rebase_workspace_var.set(str(result["workspace"].get("workspace_id") or ""))
                    self._set_document_curation_rebase_status(result["workspace"])
                self.status_var.set(f"Rebase workspace: {result.get('status')}.")
            elif action == "load":
                result = load_document_content_rebase_workspace(document_id, workspace_id)
                if result.get("workspace"):
                    self._set_document_curation_rebase_status(result["workspace"])
                self.status_var.set(f"Rebase workspace load: {result.get('status')}.")
            elif action == "refresh":
                result = refresh_document_content_rebase_conflicts(document_id, workspace_id)
                if result.get("workspace"):
                    self._set_document_curation_rebase_status(result["workspace"])
                self.status_var.set(f"Rebase conflict refresh: {result.get('status')}.")
            elif action == "resolve":
                result = apply_document_content_rebase_resolution(document_id, workspace_id, self.document_curation_rebase_conflict_var.get().strip(), self._document_curation_rebase_resolution_payload())
                if result.get("workspace"):
                    self._set_document_curation_rebase_status(result["workspace"])
                self.status_var.set(f"Rebase resolution: {result.get('status')}.")
            elif action == "readiness":
                result = get_document_content_rebase_readiness(document_id, workspace_id)
                loaded = load_document_content_rebase_workspace(document_id, workspace_id)
                if loaded.get("workspace"):
                    self._set_document_curation_rebase_status(loaded["workspace"])
                self.status_var.set(f"Rebase readiness: {result.get('status')}.")
            elif action == "commit":
                result = commit_document_content_rebase_workspace(document_id, workspace_id)
                loaded = load_document_content_rebase_workspace(document_id, workspace_id)
                if loaded.get("workspace"):
                    self._set_document_curation_rebase_status(loaded["workspace"])
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self._set_document_curation_history_status(list_document_content_curation_revisions(document_id))
                self.status_var.set(f"Rebase commit: {result.get('status')}.")
            elif action == "abandon":
                result = abandon_document_content_rebase_workspace(document_id, workspace_id)
                if result.get("workspace"):
                    self._set_document_curation_rebase_status(result["workspace"])
                self.status_var.set(f"Rebase abandon: {result.get('status')}.")
            elif action == "copy":
                text = format_document_content_rebase_report(document_id, workspace_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                loaded = load_document_content_rebase_workspace(document_id, workspace_id)
                if loaded.get("workspace"):
                    self._set_document_curation_rebase_status(loaded["workspace"])
                self.status_var.set("Public-safe rebase report copied.")
        except Exception as exc:
            self.status_var.set(f"Document curation rebase action failed: {exc}")

    def _set_document_curation_rebase_status(self, workspace: dict[str, object]) -> None:
        conflicts = workspace.get("conflicts", []) if isinstance(workspace.get("conflicts"), list) else []
        text = (
            f"Workspace ID: {workspace.get('workspace_id', 'unknown')}\n"
            f"Workspace Status: {workspace.get('status', 'unknown')}\n"
            f"Source Type: {workspace.get('source_type', 'unknown')}\n"
            f"Conflict Count: {len(conflicts)}\n"
            f"Unresolved Blockers: {workspace.get('unresolved_conflict_count', 0)}\n"
            f"Readiness: {workspace.get('status', 'unknown')}"
        )
        if hasattr(self, "document_curation_rebase_status_var"):
            self.document_curation_rebase_status_var.set(text)

    def _document_curation_bulk_operation_payload(self) -> dict[str, object]:
        raw = self.document_curation_bulk_operation_var.get().strip() if hasattr(self, "document_curation_bulk_operation_var") else ""
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _parse_document_curation_bulk_operation_payload(self) -> tuple[dict[str, object] | None, str | None]:
        raw = self.document_curation_bulk_operation_var.get().strip() if hasattr(self, "document_curation_bulk_operation_var") else ""
        if not raw:
            return {}, None
        try:
            payload = json.loads(raw)
        except Exception:
            return None, "Bulk operation payload must be valid JSON."
        if not isinstance(payload, dict):
            return None, "Bulk operation payload must be a JSON object."
        return payload, None

    def _run_document_content_bulk_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        batch_id = self.document_curation_bulk_batch_var.get().strip() if hasattr(self, "document_curation_bulk_batch_var") else ""
        try:
            if action == "create":
                result = create_document_content_bulk_plan(document_id)
                if result.get("plan"):
                    self.document_curation_bulk_batch_var.set(str(result["plan"].get("batch_id") or ""))
                    self._set_document_curation_bulk_status(result["plan"])
                self.status_var.set(f"Bulk plan: {result.get('status')}.")
            elif action == "load":
                result = load_document_content_bulk_plan(document_id, batch_id)
                if result.get("plan"):
                    self._set_document_curation_bulk_status(result["plan"])
                self.status_var.set(f"Bulk plan load: {result.get('status')}.")
            elif action == "add":
                payload, error = self._parse_document_curation_bulk_operation_payload()
                if error:
                    self.status_var.set(error)
                    return
                result = add_document_content_bulk_operation(document_id, batch_id, payload or {})
                if result.get("plan"):
                    self._set_document_curation_bulk_status(result["plan"])
                self.status_var.set(f"Bulk operation add: {result.get('status')}.")
            elif action == "remove":
                result = remove_document_content_bulk_operation(document_id, batch_id, self.document_curation_bulk_operation_id_var.get().strip())
                if result.get("plan"):
                    self._set_document_curation_bulk_status(result["plan"])
                self.status_var.set(f"Bulk operation remove: {result.get('status')}.")
            elif action == "replace":
                payload, error = self._parse_document_curation_bulk_operation_payload()
                if error:
                    self.status_var.set(error)
                    return
                result = replace_document_content_bulk_operation(document_id, batch_id, self.document_curation_bulk_operation_id_var.get().strip(), payload or {})
                if result.get("plan"):
                    self._set_document_curation_bulk_status(result["plan"])
                self.status_var.set(f"Bulk operation replace: {result.get('status')}.")
            elif action == "clear":
                result = clear_document_content_bulk_operations(document_id, batch_id)
                if result.get("plan"):
                    self._set_document_curation_bulk_status(result["plan"])
                self.status_var.set(f"Bulk operation clear: {result.get('status')}.")
            elif action == "preview":
                result = preview_document_content_bulk_plan(document_id, batch_id)
                if result.get("plan"):
                    self._set_document_curation_bulk_status(result["plan"])
                self.status_var.set(f"Bulk preview: {result.get('status')}.")
            elif action == "validate":
                result = validate_document_content_bulk_plan(document_id, batch_id)
                loaded = load_document_content_bulk_plan(document_id, batch_id)
                if loaded.get("plan"):
                    self._set_document_curation_bulk_status(loaded["plan"])
                self.status_var.set(f"Bulk validation: {result.get('status')}.")
            elif action == "queue":
                result = list_document_content_bulk_review_queue(document_id)
                if result.get("items"):
                    first = result["items"][0]
                    loaded = load_document_content_bulk_plan(document_id, str(first.get("batch_id") or ""))
                    if loaded.get("plan"):
                        self.document_curation_bulk_batch_var.set(str(loaded["plan"].get("batch_id") or ""))
                        self._set_document_curation_bulk_status(loaded["plan"])
                self.status_var.set(f"Bulk queue: {result.get('count', 0)} batch(es).")
            elif action == "approve":
                result = approve_document_content_bulk_plan(document_id, batch_id)
                if result.get("plan"):
                    self._set_document_curation_bulk_status(result["plan"])
                self.status_var.set(f"Bulk approval: {result.get('status')}.")
            elif action == "reject":
                result = reject_document_content_bulk_plan(document_id, batch_id, self.document_curation_bulk_reject_reason_var.get().strip())
                if result.get("plan"):
                    self._set_document_curation_bulk_status(result["plan"])
                self.status_var.set(f"Bulk rejection: {result.get('status')}.")
            elif action == "commit":
                result = commit_document_content_bulk_plan(document_id, batch_id)
                loaded = load_document_content_bulk_plan(document_id, batch_id)
                if loaded.get("plan"):
                    self._set_document_curation_bulk_status(loaded["plan"])
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self._set_document_curation_history_status(list_document_content_curation_revisions(document_id))
                self.status_var.set(f"Bulk commit: {result.get('status')}.")
            elif action == "copy":
                text = format_document_content_bulk_report(document_id, batch_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                loaded = load_document_content_bulk_plan(document_id, batch_id)
                if loaded.get("plan"):
                    self._set_document_curation_bulk_status(loaded["plan"])
                self.status_var.set("Public-safe bulk report copied.")
        except Exception as exc:
            self.status_var.set(f"Document content bulk action failed: {exc}")

    def _set_document_curation_bulk_status(self, plan: dict[str, object]) -> None:
        text = (
            f"Batch ID: {plan.get('batch_id', 'unknown')}\n"
            f"Batch Revision: {plan.get('batch_revision', 0)}\n"
            f"Status: {plan.get('status', 'unknown')}\n"
            f"Operation Count: {plan.get('operation_count', 0)}\n"
            f"Effective Change Count: {plan.get('effective_change_count', 0)}\n"
            f"Unchanged Count: {plan.get('unchanged_operation_count', 0)}\n"
            f"Blocker Count: {len(plan.get('blockers', [])) if isinstance(plan.get('blockers'), list) else 0}\n"
            f"Warning Count: {len(plan.get('warnings', [])) if isinstance(plan.get('warnings'), list) else 0}\n"
            f"Approved: {bool(plan.get('approval_metadata'))}"
        )
        if hasattr(self, "document_curation_bulk_status_var"):
            self.document_curation_bulk_status_var.set(text)

    def _run_document_content_integrity_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        plan_id = self.document_curation_integrity_plan_var.get().strip() if hasattr(self, "document_curation_integrity_plan_var") else ""
        try:
            if action == "scan":
                result = scan_document_content_integrity(document_id)
                self._set_document_curation_integrity_status(result)
                self.status_var.set(f"Integrity scan: {result.get('issue_count', 0)} issue(s).")
            elif action == "transactions":
                result = list_document_content_transactions(document_id)
                if result.get("items"):
                    self.document_curation_integrity_transaction_var.set(str(result["items"][0].get("transaction_id") or ""))
                self._set_document_curation_integrity_status(scan_document_content_integrity(document_id))
                self.status_var.set(f"Pending transactions: {result.get('count', 0)}.")
            elif action == "plan":
                result = create_document_content_recovery_plan(document_id)
                if result.get("plan"):
                    self.document_curation_integrity_plan_var.set(str(result["plan"].get("plan_id") or ""))
                self._set_document_curation_integrity_status(scan_document_content_integrity(document_id))
                self.status_var.set(f"Recovery plan: {result.get('status')}.")
            elif action == "load_plan":
                result = load_document_content_recovery_plan(document_id, plan_id)
                if result.get("plan"):
                    self.document_curation_integrity_plan_var.set(str(result["plan"].get("plan_id") or ""))
                    self.status_var.set(
                        "Recovery plan loaded: "
                        f"{result['plan'].get('status')} | issues={len(result['plan'].get('issue_ids', []))} | "
                        f"actions={len(result['plan'].get('planned_actions', []))} | "
                        f"blockers={len(result['plan'].get('blockers', []))} | "
                        f"warnings={len(result['plan'].get('warnings', []))} | "
                        f"stale={result['plan'].get('status') == 'stale'}"
                    )
                else:
                    self.status_var.set(f"Recovery plan load: {result.get('status')}.")
                self._set_document_curation_integrity_status(scan_document_content_integrity(document_id))
            elif action == "apply":
                result = apply_document_content_recovery_plan(document_id, plan_id)
                self._set_document_curation_integrity_status(scan_document_content_integrity(document_id))
                self._set_document_curation_status(get_document_content_curation_summary(document_id))
                self._set_document_curation_history_status(list_document_content_curation_revisions(document_id))
                self.status_var.set(f"Recovery apply: {result.get('status')}.")
            elif action == "abandon":
                transaction_id = self.document_curation_integrity_transaction_var.get().strip() if hasattr(self, "document_curation_integrity_transaction_var") else ""
                result = abandon_document_content_transaction(document_id, transaction_id)
                self._set_document_curation_integrity_status(scan_document_content_integrity(document_id))
                self.status_var.set(f"Transaction abandon: {result.get('status')}.")
            elif action == "rebuild":
                result = rebuild_document_content_indexes(document_id)
                self._set_document_curation_integrity_status(scan_document_content_integrity(document_id))
                self.status_var.set(f"Index rebuild: {result.get('status')}.")
            elif action == "copy":
                text = format_document_content_integrity_report(document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self._set_document_curation_integrity_status(scan_document_content_integrity(document_id))
                self.status_var.set("Public-safe integrity report copied.")
        except Exception as exc:
            self.status_var.set(f"Document content integrity action failed: {exc}")

    def _run_backend_contract_validation_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        validation_id = self.backend_contract_validation_id_var.get().strip() if hasattr(self, "backend_contract_validation_id_var") else ""
        regenerate = bool(self.backend_contract_regenerate_var.get()) if hasattr(self, "backend_contract_regenerate_var") else False
        try:
            if action == "plan":
                result = build_backend_contract_validation_plan(document_id)
                self._set_backend_contract_validation_status(get_backend_contract_validation_summary(document_id))
                self.status_var.set(f"Backend contract plan: {len(result.get('checks', []))} check(s).")
            elif action == "run":
                result = run_backend_contract_validation(document_id, regenerate=regenerate)
                if result.get("validation"):
                    self.backend_contract_validation_id_var.set(str(result["validation"].get("validation_id") or ""))
                self._set_backend_contract_validation_status(get_backend_contract_validation_summary(document_id))
                self.status_var.set(f"Backend contract validation: {result.get('status')}.")
            elif action == "load":
                result = load_backend_contract_validation(validation_id)
                if result.get("validation"):
                    self.backend_contract_validation_id_var.set(str(result["validation"].get("validation_id") or validation_id))
                    self._set_backend_contract_validation_status(get_backend_contract_validation_summary(document_id))
                self.status_var.set(f"Backend contract load: {result.get('status')}.")
            elif action == "health":
                result = get_backend_contract_validation_health(document_id)
                self._set_backend_contract_validation_status(get_backend_contract_validation_summary(document_id))
                self.status_var.set(f"Backend contract health: {result.get('status')}.")
            elif action == "copy":
                text = format_backend_contract_validation_report(validation_id=validation_id or None, document_id=None if validation_id else document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self._set_backend_contract_validation_status(get_backend_contract_validation_summary(document_id))
                self.status_var.set("Public-safe backend contract report copied.")
        except Exception as exc:
            self.status_var.set(f"Backend contract validation failed: {exc}")

    def _set_backend_contract_validation_status(self, summary: dict[str, object]) -> None:
        text = (
            f"Document ID: {summary.get('document_id', 'unknown')}\n"
            f"Source Revision: {summary.get('source_revision', 'unknown')}\n"
            f"Certification Status: {summary.get('certification_status', 'unknown')}\n"
            f"Validation Current: {summary.get('validation_current', 'unknown')}\n"
            f"Required Pass Count: {summary.get('required_pass_count', 0)}\n"
            f"Warning Count: {summary.get('warning_count', 0)}\n"
            f"Failure Count: {summary.get('failure_count', 0)}\n"
            f"Blocked Count: {summary.get('blocked_count', 0)}\n"
            f"Reader Backend Readiness: {summary.get('reader_backend_readiness', 'unknown')}\n"
            f"Citation Count: {summary.get('citation_count', 0)}\n"
            f"Evidence Binder Count: {summary.get('evidence_binder_count', 0)}\n"
            f"Pending Revalidation Count: {summary.get('pending_revalidation_count', 0)}\n"
            f"Rollback Failure Count: {summary.get('rollback_failure_count', 0)}\n"
            f"Recommended Action: {summary.get('recommended_action', 'Unknown')}"
        )
        if hasattr(self, "backend_contract_status_var"):
            self.backend_contract_status_var.set(text)

    def _run_pdf_viewport_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        viewport_id = self.pdf_viewport_id_var.get().strip() if hasattr(self, "pdf_viewport_id_var") else ""
        try:
            if action == "open":
                jump_page = self._parse_int_text(self.pdf_viewport_jump_page_var.get(), 1) if hasattr(self, "pdf_viewport_jump_page_var") else 1
                zoom = self._parse_int_text(self.pdf_viewport_zoom_var.get(), 100) if hasattr(self, "pdf_viewport_zoom_var") else 100
                result = create_pdf_viewport_session(document_id, initial_page=jump_page, zoom_percent=zoom)
                if result.get("viewport"):
                    viewport = result["viewport"]
                    viewport_id = str(viewport.get("viewport_id") or "")
                    self.pdf_viewport_id_var.set(viewport_id)
                    render = render_pdf_viewport_page(viewport_id, page_number=int(viewport.get("current_page") or 1), zoom_percent=int(viewport.get("zoom_percent") or 100))
                    self._clear_pdf_viewport_overlay_state()
                    self._set_pdf_viewport_status(viewport=viewport, render=render)
                    self._show_pdf_viewport_image(render)
                self.status_var.set(f"PDF viewport: {result.get('status')}.")
            elif action in {"first", "previous", "next", "last", "jump", "zoom_in", "zoom_out"}:
                page_number = None
                nav_action = action
                if action == "jump":
                    page_number = self._parse_int_text(self.pdf_viewport_jump_page_var.get(), 1) if hasattr(self, "pdf_viewport_jump_page_var") else 1
                result = navigate_pdf_viewport(viewport_id, nav_action, page_number=page_number)
                if result.get("status") == "ready":
                    render = render_pdf_viewport_page(viewport_id, page_number=int(result.get("current_page") or 1), zoom_percent=int(result.get("zoom_percent") or 100))
                    self._clear_pdf_viewport_overlay_state()
                    self._set_pdf_viewport_status(viewport=result, render=render)
                    self._show_pdf_viewport_image(render)
                self.status_var.set(f"PDF viewport navigation: {result.get('status')}.")
            elif action == "sync":
                raw = self.pdf_viewport_locator_var.get().strip() if hasattr(self, "pdf_viewport_locator_var") else ""
                try:
                    locator = json.loads(raw) if raw else {}
                except Exception:
                    self.status_var.set("Locator JSON must be valid.")
                    return
                if not isinstance(locator, dict):
                    self.status_var.set("Locator JSON must be an object.")
                    return
                result = synchronize_pdf_viewport_to_locator(viewport_id, locator)
                if result.get("locator_status") == "synchronized":
                    render = render_pdf_viewport_page(viewport_id, page_number=int(result.get("current_page") or 1))
                    self._set_pdf_viewport_status(viewport=result, render=render)
                    self._show_pdf_viewport_image(render)
                self.status_var.set(f"PDF viewport locator sync: {result.get('locator_status', result.get('status'))}.")
            elif action == "load_text_layer":
                result = extract_pdf_page_text_layer(viewport_id)
                self._pdf_viewport_text_layer = result
                self._set_pdf_viewport_status(viewport=result.get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"PDF text layer: {result.get('status', 'unknown')}.")
            elif action in {"highlight_locator", "highlight_search", "highlight_citations"}:
                raw = self.pdf_viewport_locator_var.get().strip() if hasattr(self, "pdf_viewport_locator_var") else ""
                try:
                    payload = json.loads(raw) if raw else {}
                except Exception:
                    self.status_var.set("Highlight JSON must be valid.")
                    return
                if action == "highlight_locator":
                    locators = [payload] if isinstance(payload, dict) else []
                    overlay_type = "selected_locator"
                else:
                    locators = payload if isinstance(payload, list) else []
                    overlay_type = "search" if action == "highlight_search" else "citation"
                result = build_pdf_highlight_overlay(viewport_id, locators, overlay_type=overlay_type)
                self._pdf_viewport_overlay = result
                self._draw_pdf_viewport_overlay(result)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"PDF overlay: mapped {result.get('mapped_locator_count', 0)}, unmapped {result.get('unmapped_locator_count', 0)}.")
            elif action == "clear_highlights":
                self._clear_pdf_viewport_overlay_state()
                self._draw_pdf_viewport_overlay(None)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set("PDF overlays cleared.")
            elif action == "copy_selection":
                selection = getattr(self, "_pdf_viewport_selection", None)
                if not isinstance(selection, dict) or selection.get("selection_status") != "selected":
                    self.status_var.set("No native text selection is available to copy.")
                    return
                text = format_pdf_text_selection(selection, include_locator=False, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Selected native text copied.")
            elif action == "open_workspace":
                result = create_pdf_reader_workspace(document_id, viewport_id=viewport_id or None)
                if result.get("workspace"):
                    self._pdf_reader_workspace = result["workspace"]
                    self.pdf_reader_workspace_id_var.set(str(result["workspace"].get("workspace_id") or ""))
                    self._reload_pdf_reader_workspace_overlay(viewport_id)
                    self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"PDF reader workspace: {result.get('status')}.")
            elif action == "add_bookmark":
                workspace_id = self.pdf_reader_workspace_id_var.get().strip() if hasattr(self, "pdf_reader_workspace_id_var") else ""
                page_number = int((getattr(self, "_pdf_viewport_last_render", {}) or {}).get("page_number") or 0)
                locator = None
                raw = self.pdf_viewport_locator_var.get().strip() if hasattr(self, "pdf_viewport_locator_var") else ""
                if raw:
                    try:
                        parsed = json.loads(raw)
                        locator = parsed if isinstance(parsed, dict) else None
                    except Exception:
                        locator = None
                result = save_pdf_reader_bookmark(workspace_id, page_number, label=self.pdf_reader_bookmark_label_var.get().strip() or None, locator=locator)
                if result.get("workspace"):
                    self._pdf_reader_workspace = result["workspace"]
                    self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"PDF bookmark: {result.get('status')}.")
            elif action in {"save_annotation", "save_note"}:
                workspace_id = self.pdf_reader_workspace_id_var.get().strip() if hasattr(self, "pdf_reader_workspace_id_var") else ""
                selection = getattr(self, "_pdf_viewport_selection", None)
                page_number = int((selection or {}).get("page_number") or (getattr(self, "_pdf_viewport_last_render", {}) or {}).get("page_number") or 0)
                rectangles_pdf = [selection.get("pdf_bbox")] if action == "save_annotation" and isinstance(selection, dict) and isinstance(selection.get("pdf_bbox"), list) else []
                if action == "save_note" and not rectangles_pdf:
                    rectangles_pdf = [[1.0, 1.0, 20.0, 20.0]]
                annotation_type = self.pdf_reader_annotation_type_var.get().strip() or ("note" if action == "save_note" else "highlight")
                note = self.pdf_reader_annotation_note_var.get().strip() or None
                locator = None
                raw = self.pdf_viewport_locator_var.get().strip() if hasattr(self, "pdf_viewport_locator_var") else ""
                if raw:
                    try:
                        parsed = json.loads(raw)
                        locator = parsed if isinstance(parsed, dict) else None
                    except Exception:
                        locator = None
                result = save_pdf_reader_annotation(workspace_id, page_number, annotation_type, rectangles_pdf, note=note, locator=locator, selected_text_hash=(selection or {}).get("selected_text_hash"))
                if result.get("workspace"):
                    self._pdf_reader_workspace = result["workspace"]
                    self._reload_pdf_reader_workspace_overlay(viewport_id)
                    self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"PDF annotation: {result.get('status')}.")
            elif action == "draft_citation":
                workspace_id = self.pdf_reader_workspace_id_var.get().strip() if hasattr(self, "pdf_reader_workspace_id_var") else ""
                selection = getattr(self, "_pdf_viewport_selection", None)
                result = draft_citation_from_pdf_selection(workspace_id, selection or {}, note=self.pdf_reader_citation_note_var.get().strip() or None)
                if result.get("workspace"):
                    self._pdf_reader_workspace = result["workspace"]
                    self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"PDF citation draft: {result.get('status')}.")
            elif action == "reload_workspace":
                self._reload_pdf_reader_workspace_overlay(viewport_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set("PDF workspace items reloaded.")
            elif action == "copy_workspace_report":
                workspace_id = self.pdf_reader_workspace_id_var.get().strip() if hasattr(self, "pdf_reader_workspace_id_var") else ""
                text = format_pdf_reader_workspace_report(workspace_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe reader workspace report copied.")
            elif action == "load_draft_review":
                workspace_id = self.citation_review_workspace_id_var.get().strip() or (self.pdf_reader_workspace_id_var.get().strip() if hasattr(self, "pdf_reader_workspace_id_var") else "")
                draft_id = self.citation_review_draft_id_var.get().strip()
                result = build_citation_draft_review_workspace(workspace_id, draft_id)
                self._citation_draft_review = result
                if hasattr(self, "citation_review_workspace_id_var"):
                    self.citation_review_workspace_id_var.set(workspace_id)
                self.status_var.set(f"Citation draft review: {result.get('review_status', result.get('status', 'pending'))}.")
            elif action in {"approve_draft", "reject_draft", "request_draft_changes"}:
                workspace_id = self.citation_review_workspace_id_var.get().strip() or (self.pdf_reader_workspace_id_var.get().strip() if hasattr(self, "pdf_reader_workspace_id_var") else "")
                draft_id = self.citation_review_draft_id_var.get().strip()
                decision = "approve" if action == "approve_draft" else "reject" if action == "reject_draft" else "request_changes"
                result = save_citation_draft_review_decision(
                    workspace_id,
                    draft_id,
                    decision,
                    reviewer_note=self.citation_review_note_var.get().strip() or None,
                    allow_near_duplicate=bool(self.citation_review_allow_near_duplicate_var.get()) if hasattr(self, "citation_review_allow_near_duplicate_var") else False,
                )
                if result.get("review"):
                    self._citation_draft_review_record = result["review"]
                    if hasattr(self, "citation_review_id_var"):
                        self.citation_review_id_var.set(str(result["review"].get("review_id") or ""))
                self.status_var.set(f"Citation review decision: {result.get('status')}.")
            elif action == "create_citation":
                review_id = self.citation_review_id_var.get().strip()
                result = create_citation_from_approved_draft(review_id, confirmation=self.citation_review_confirmation_var.get().strip() or None)
                self._citation_draft_creation = result
                self.status_var.set(f"Citation creation: {result.get('status')}.")
            elif action == "review_health":
                workspace_id = self.citation_review_workspace_id_var.get().strip() or None
                result = get_citation_draft_review_health(workspace_id=workspace_id)
                self._citation_draft_review_health = result
                self.status_var.set(f"Citation review health: {result.get('status', 'unknown')}.")
            elif action == "copy_review_report":
                review_id = self.citation_review_id_var.get().strip() or None
                workspace_id = self.citation_review_workspace_id_var.get().strip() or None
                text = format_citation_draft_review_report(review_id=review_id, workspace_id=workspace_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe citation draft review report copied.")
            elif action == "load_handoff_review":
                handoff_id = self.evidence_handoff_id_var.get().strip()
                result = build_evidence_handoff_review_workspace(handoff_id)
                self._evidence_handoff_review = result
                review_id = str(result.get("review_id") or "")
                if hasattr(self, "evidence_handoff_review_id_var"):
                    self.evidence_handoff_review_id_var.set(review_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Evidence handoff review: {result.get('handoff_status', result.get('status', 'unknown'))}.")
            elif action == "find_handoff_binders":
                handoff_id = self.evidence_handoff_id_var.get().strip()
                result = find_evidence_handoff_binder_candidates(handoff_id)
                self._evidence_handoff_candidates = result
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Evidence handoff candidates: {result.get('candidate_count', 0)}.")
            elif action in {"approve_handoff_binder", "approve_handoff_proposal", "defer_handoff", "reject_handoff"}:
                handoff_id = self.evidence_handoff_id_var.get().strip()
                decision = (
                    "approve_binder_insert" if action == "approve_handoff_binder"
                    else "approve_proposal_draft" if action == "approve_handoff_proposal"
                    else "defer" if action == "defer_handoff"
                    else "reject"
                )
                result = save_evidence_handoff_review_decision(
                    handoff_id,
                    decision,
                    target_binder_id=self.evidence_handoff_target_binder_var.get().strip() or None,
                    reviewer_note=self.evidence_handoff_note_var.get().strip() or None,
                )
                if result.get("review"):
                    self._evidence_handoff_review_record = result["review"]
                    self.evidence_handoff_review_id_var.set(str(result["review"].get("review_id") or ""))
                refreshed = build_evidence_handoff_review_workspace(handoff_id)
                self._evidence_handoff_review = refreshed
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Evidence handoff decision: {result.get('status')}.")
            elif action == "insert_handoff_binder":
                review_id = self.evidence_handoff_review_id_var.get().strip()
                result = insert_handoff_citation_into_binder(review_id, confirmation=self.evidence_handoff_confirmation_var.get().strip() or None)
                self._evidence_handoff_action = result
                handoff_id = str(result.get("evidence_handoff_id") or self.evidence_handoff_id_var.get().strip())
                if handoff_id:
                    self._evidence_handoff_review = build_evidence_handoff_review_workspace(handoff_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Evidence handoff binder insert: {result.get('status')}.")
            elif action == "create_handoff_proposal":
                review_id = self.evidence_handoff_review_id_var.get().strip()
                result = create_proposal_draft_from_evidence_handoff(review_id, confirmation=self.evidence_handoff_confirmation_var.get().strip() or None)
                self._evidence_handoff_action = result
                handoff_id = str(result.get("evidence_handoff_id") or self.evidence_handoff_id_var.get().strip())
                if handoff_id:
                    self._evidence_handoff_review = build_evidence_handoff_review_workspace(handoff_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Evidence handoff proposal: {result.get('status')}.")
            elif action == "copy_handoff_report":
                handoff_id = self.evidence_handoff_id_var.get().strip() or None
                review_id = self.evidence_handoff_review_id_var.get().strip() or None
                text = format_evidence_handoff_review_report(evidence_handoff_id=handoff_id, review_id=review_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe evidence handoff report copied.")
            elif action == "load_proposal_promotion":
                proposal_id = self.proposal_promotion_proposal_id_var.get().strip()
                result = build_proposal_promotion_workspace(proposal_id)
                self._proposal_promotion_workspace = result
                if hasattr(self, "proposal_promotion_review_id_var"):
                    self.proposal_promotion_review_id_var.set(str(result.get("promotion_review_id") or ""))
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Proposal promotion review: {result.get('proposal_status', result.get('status', 'unknown'))}.")
            elif action in {"approve_proposal_promotion", "reject_proposal_promotion", "request_changes_proposal_promotion"}:
                proposal_id = self.proposal_promotion_proposal_id_var.get().strip()
                decision = "approve" if action == "approve_proposal_promotion" else "reject" if action == "reject_proposal_promotion" else "request_changes"
                result = save_proposal_promotion_decision(
                    proposal_id,
                    decision,
                    reviewer_note=self.proposal_promotion_note_var.get().strip() or None,
                    acknowledge_near_duplicate=bool(self.proposal_promotion_ack_near_duplicate_var.get()) if hasattr(self, "proposal_promotion_ack_near_duplicate_var") else False,
                    acknowledge_conflict=bool(self.proposal_promotion_ack_conflict_var.get()) if hasattr(self, "proposal_promotion_ack_conflict_var") else False,
                )
                if result.get("review"):
                    self._proposal_promotion_review = result["review"]
                    self.proposal_promotion_review_id_var.set(str(result["review"].get("promotion_review_id") or ""))
                refreshed = build_proposal_promotion_workspace(proposal_id)
                self._proposal_promotion_workspace = refreshed
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Proposal promotion decision: {result.get('status')}.")
            elif action == "promote_proposal":
                promotion_review_id = self.proposal_promotion_review_id_var.get().strip()
                result = promote_approved_proposal(promotion_review_id, confirmation=self.proposal_promotion_confirmation_var.get().strip() or None)
                self._proposal_promotion_action = result
                proposal_id = str(result.get("proposal_id") or self.proposal_promotion_proposal_id_var.get().strip())
                if proposal_id:
                    self._proposal_promotion_workspace = build_proposal_promotion_workspace(proposal_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Proposal promotion: {result.get('status')}.")
            elif action == "proposal_promotion_health":
                result = get_proposal_promotion_health(document_id=None)
                self._proposal_promotion_health = result
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Proposal promotion health: {result.get('status', 'unknown')}.")
            elif action == "copy_proposal_promotion_report":
                proposal_id = self.proposal_promotion_proposal_id_var.get().strip() or None
                promotion_review_id = self.proposal_promotion_review_id_var.get().strip() or None
                text = format_proposal_promotion_report(proposal_id=proposal_id, promotion_review_id=promotion_review_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe proposal promotion report copied.")
            elif action == "load_rule_activation":
                proposal_id = self.rule_activation_proposal_id_var.get().strip()
                result = build_proposal_rule_activation_workspace(proposal_id)
                self._rule_activation_workspace = result
                self.rule_activation_review_id_var.set(str(result.get("rule_activation_review_status") and "" or result.get("rule_activation_review_id") or ""))
                self.rule_activation_receipt_id_var.set(str(result.get("activation_receipt_id") or ""))
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule activation workspace: {result.get('rule_candidate_status', result.get('status', 'unknown'))}.")
            elif action in {"approve_rule_activation", "reject_rule_activation", "request_changes_rule_activation"}:
                proposal_id = self.rule_activation_proposal_id_var.get().strip()
                decision = "approve" if action == "approve_rule_activation" else "reject" if action == "reject_rule_activation" else "request_changes"
                result = save_proposal_rule_activation_decision(
                    proposal_id,
                    decision,
                    reviewer_note=self.rule_activation_note_var.get().strip() or None,
                    acknowledge_inactive_equivalent=bool(self.rule_activation_ack_inactive_var.get()) if hasattr(self, "rule_activation_ack_inactive_var") else False,
                    acknowledge_conflict=bool(self.rule_activation_ack_conflict_var.get()) if hasattr(self, "rule_activation_ack_conflict_var") else False,
                )
                if result.get("review"):
                    self._rule_activation_review = result["review"]
                    self.rule_activation_review_id_var.set(str(result["review"].get("rule_activation_review_id") or ""))
                self._rule_activation_workspace = build_proposal_rule_activation_workspace(proposal_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule activation review: {result.get('status')}.")
            elif action == "activate_rule":
                review_id = self.rule_activation_review_id_var.get().strip()
                result = activate_rule_from_promoted_proposal(review_id, confirmation=self.rule_activation_confirmation_var.get().strip() or None)
                self._rule_activation_action = result
                proposal_id = str(result.get("proposal_id") or self.rule_activation_proposal_id_var.get().strip())
                if proposal_id:
                    self._rule_activation_workspace = build_proposal_rule_activation_workspace(proposal_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule activation: {result.get('status')}.")
            elif action == "rollback_rule_activation":
                receipt_id = self.rule_activation_receipt_id_var.get().strip()
                result = rollback_proposal_rule_activation(receipt_id, confirmation=self.rule_activation_rollback_confirmation_var.get().strip() or None)
                self._rule_activation_action = result
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule activation rollback: {result.get('status')}.")
            elif action == "copy_rule_activation_report":
                proposal_id = self.rule_activation_proposal_id_var.get().strip() or None
                review_id = self.rule_activation_review_id_var.get().strip() or None
                receipt_id = self.rule_activation_receipt_id_var.get().strip() or None
                text = format_proposal_rule_activation_report(proposal_id=proposal_id, rule_activation_review_id=review_id, activation_receipt_id=receipt_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe proposal rule activation report copied.")
            elif action == "load_rule_revalidation":
                revalidation_id = self.rule_revalidation_id_var.get().strip()
                result = build_rule_activation_revalidation_workspace(revalidation_id)
                self._rule_activation_revalidation_workspace = result
                self.rule_revalidation_review_id_var.set(str(result.get("revalidation_review_id") or ""))
                self.rule_revalidation_receipt_id_var.set(str(result.get("certification_receipt_id") or ""))
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule activation revalidation workspace: {result.get('runtime_validation_status', result.get('status', 'unknown'))}.")
            elif action == "run_rule_revalidation_runtime":
                revalidation_id = self.rule_revalidation_id_var.get().strip()
                result = run_rule_runtime_contract_validation(revalidation_id)
                self._rule_activation_revalidation_runtime = result
                self._rule_activation_revalidation_workspace = build_rule_activation_revalidation_workspace(revalidation_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule runtime validation: {result.get('status')}.")
            elif action in {"certify_rule_revalidation", "request_changes_rule_revalidation", "reject_rule_revalidation"}:
                revalidation_id = self.rule_revalidation_id_var.get().strip()
                decision = "certify" if action == "certify_rule_revalidation" else "request_changes" if action == "request_changes_rule_revalidation" else "reject_and_rollback"
                result = save_rule_activation_revalidation_decision(
                    revalidation_id,
                    decision,
                    reviewer_note=self.rule_revalidation_note_var.get().strip() or None,
                )
                if result.get("review"):
                    self._rule_activation_revalidation_review = result["review"]
                    self.rule_revalidation_review_id_var.set(str(result["review"].get("revalidation_review_id") or ""))
                self._rule_activation_revalidation_workspace = build_rule_activation_revalidation_workspace(revalidation_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule activation revalidation review: {result.get('status')}.")
            elif action == "complete_rule_revalidation":
                review_id = self.rule_revalidation_review_id_var.get().strip()
                result = complete_rule_activation_revalidation(review_id, confirmation=self.rule_revalidation_completion_confirmation_var.get().strip() or None)
                self._rule_activation_revalidation_action = result
                revalidation_id = str(result.get("revalidation_id") or self.rule_revalidation_id_var.get().strip())
                if revalidation_id:
                    self._rule_activation_revalidation_workspace = build_rule_activation_revalidation_workspace(revalidation_id)
                self.rule_revalidation_receipt_id_var.set(str(result.get("certification_receipt_id") or self.rule_revalidation_receipt_id_var.get().strip() or ""))
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule activation revalidation completion: {result.get('status')}.")
            elif action == "copy_rule_revalidation_report":
                revalidation_id = self.rule_revalidation_id_var.get().strip() or None
                review_id = self.rule_revalidation_review_id_var.get().strip() or None
                receipt_id = self.rule_revalidation_receipt_id_var.get().strip() or None
                text = format_rule_activation_revalidation_report(revalidation_id=revalidation_id, revalidation_review_id=review_id, certification_receipt_id=receipt_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe rule activation revalidation report copied.")
            elif action == "load_rule_supersession":
                old_rule_id = self.rule_supersession_old_rule_id_var.get().strip()
                proposal_id = self.rule_supersession_proposal_id_var.get().strip()
                result = build_rule_supersession_workspace(old_rule_id, proposal_id)
                self._rule_supersession_workspace = result
                self.rule_supersession_review_id_var.set(str(result.get("review_status") == "pending" and "" or getattr(self, "_rule_supersession_review", {}).get("supersession_review_id", "") or ""))
                self.rule_supersession_receipt_id_var.set(str(result.get("supersession_receipt_id") or ""))
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule supersession workspace: {result.get('supersession_compatibility', result.get('status', 'unknown'))}.")
            elif action in {"approve_rule_supersession", "reject_rule_supersession", "request_changes_rule_supersession"}:
                old_rule_id = self.rule_supersession_old_rule_id_var.get().strip()
                proposal_id = self.rule_supersession_proposal_id_var.get().strip()
                decision = "approve" if action == "approve_rule_supersession" else "reject" if action == "reject_rule_supersession" else "request_changes"
                result = save_rule_supersession_decision(
                    old_rule_id,
                    proposal_id,
                    decision,
                    reviewer_note=self.rule_supersession_note_var.get().strip() or None,
                    acknowledge_scope_change=bool(self.rule_supersession_ack_scope_var.get()),
                )
                if result.get("review"):
                    self._rule_supersession_review = result["review"]
                    self.rule_supersession_review_id_var.set(str(result["review"].get("supersession_review_id") or ""))
                self._rule_supersession_workspace = build_rule_supersession_workspace(old_rule_id, proposal_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule supersession review: {result.get('status')}.")
            elif action == "supersede_rule":
                review_id = self.rule_supersession_review_id_var.get().strip()
                result = supersede_certified_rule(review_id, confirmation=self.rule_supersession_confirmation_var.get().strip() or None)
                self._rule_supersession_action = result
                receipt_id = str(result.get("supersession_receipt_id") or "")
                if receipt_id:
                    self.rule_supersession_receipt_id_var.set(receipt_id)
                old_rule_id = str(result.get("old_rule_id") or self.rule_supersession_old_rule_id_var.get().strip())
                proposal_id = self.rule_supersession_proposal_id_var.get().strip()
                if old_rule_id and proposal_id:
                    self._rule_supersession_workspace = build_rule_supersession_workspace(old_rule_id, proposal_id)
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule supersession: {result.get('status')}.")
            elif action == "rollback_rule_supersession":
                receipt_id = self.rule_supersession_receipt_id_var.get().strip()
                result = rollback_rule_supersession(receipt_id, confirmation=self.rule_supersession_rollback_confirmation_var.get().strip() or None)
                self._rule_supersession_action = result
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
                self.status_var.set(f"Rule supersession rollback: {result.get('status')}.")
            elif action == "copy_rule_supersession_report":
                review_id = self.rule_supersession_review_id_var.get().strip() or None
                receipt_id = self.rule_supersession_receipt_id_var.get().strip() or None
                text = format_rule_supersession_report(supersession_review_id=review_id, supersession_receipt_id=receipt_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe rule supersession report copied.")
            elif action == "load_rule_effectiveness_workspace":
                result = build_rule_effectiveness_workspace(
                    self.rule_effectiveness_rule_id_var.get().strip(),
                    self.rule_effectiveness_dataset_id_var.get().strip(),
                    comparison_rule_id=self.rule_effectiveness_comparison_rule_id_var.get().strip() or None,
                )
                self._rule_effectiveness_workspace = result
                self.status_var.set(f"Rule effectiveness workspace: {result.get('analysis_status', result.get('status', 'unknown'))}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "build_rule_effectiveness_plan":
                result = build_rule_effectiveness_backtest_plan(
                    self.rule_effectiveness_rule_id_var.get().strip(),
                    self.rule_effectiveness_dataset_id_var.get().strip(),
                    comparison_rule_id=self.rule_effectiveness_comparison_rule_id_var.get().strip() or None,
                    max_records=int(self.rule_effectiveness_max_records_var.get().strip() or "200"),
                )
                self._rule_effectiveness_plan = result
                self.status_var.set(f"Rule effectiveness plan: {result.get('record_count', 0)} records.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "run_rule_effectiveness_backtest":
                result = run_rule_effectiveness_backtest(
                    self.rule_effectiveness_rule_id_var.get().strip(),
                    self.rule_effectiveness_dataset_id_var.get().strip(),
                    comparison_rule_id=self.rule_effectiveness_comparison_rule_id_var.get().strip() or None,
                    max_records=int(self.rule_effectiveness_max_records_var.get().strip() or "200"),
                    regenerate=bool(self.rule_effectiveness_regenerate_var.get()),
                )
                self._rule_effectiveness_analysis = result
                self.status_var.set(f"Rule effectiveness backtest: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "rule_effectiveness_health":
                result = get_rule_effectiveness_health(
                    rule_id=self.rule_effectiveness_rule_id_var.get().strip() or None,
                    dataset_id=self.rule_effectiveness_dataset_id_var.get().strip() or None,
                )
                self._rule_effectiveness_health = result
                self.status_var.set(f"Rule effectiveness health: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "copy_rule_effectiveness_report":
                analysis_id = str((getattr(self, "_rule_effectiveness_analysis", {}) or {}).get("analysis_id") or "")
                text = format_rule_effectiveness_report(analysis_id=analysis_id or None, rule_id=self.rule_effectiveness_rule_id_var.get().strip() or None, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe rule effectiveness report copied.")
            elif action == "load_rule_effectiveness_recommendation_workspace":
                result = build_rule_effectiveness_recommendation_workspace(
                    self.rule_effectiveness_recommendation_analysis_id_var.get().strip(),
                    policy_id=self.rule_effectiveness_recommendation_policy_id_var.get().strip() or "default_v1",
                )
                self._rule_effectiveness_recommendation_workspace = result
                if result.get("recommendation_id"):
                    self.rule_effectiveness_recommendation_id_var.set(str(result.get("recommendation_id") or ""))
                if result.get("recommendation_review_id"):
                    self.rule_effectiveness_recommendation_review_id_var.set(str(result.get("recommendation_review_id") or ""))
                if result.get("action_candidate_id"):
                    self.rule_effectiveness_recommendation_action_candidate_id_var.set(str(result.get("action_candidate_id") or ""))
                self.status_var.set(f"Rule effectiveness recommendation workspace: {result.get('recommendation_status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "generate_rule_effectiveness_recommendation":
                result = generate_rule_effectiveness_recommendation(
                    self.rule_effectiveness_recommendation_analysis_id_var.get().strip(),
                    policy_id=self.rule_effectiveness_recommendation_policy_id_var.get().strip() or "default_v1",
                )
                self._rule_effectiveness_recommendation = result
                if result.get("recommendation_id"):
                    self.rule_effectiveness_recommendation_id_var.set(str(result.get("recommendation_id") or ""))
                self.status_var.set(f"Rule effectiveness recommendation: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action in {"accept_rule_effectiveness_recommendation", "reject_rule_effectiveness_recommendation", "defer_rule_effectiveness_recommendation", "more_evidence_rule_effectiveness_recommendation"}:
                decision = {
                    "accept_rule_effectiveness_recommendation": "accept",
                    "reject_rule_effectiveness_recommendation": "reject",
                    "defer_rule_effectiveness_recommendation": "defer",
                    "more_evidence_rule_effectiveness_recommendation": "request_more_evidence",
                }[action]
                self.rule_effectiveness_recommendation_decision_var.set(decision)
                result = save_rule_effectiveness_recommendation_decision(
                    self.rule_effectiveness_recommendation_id_var.get().strip(),
                    decision,
                    reviewer_note=self.rule_effectiveness_recommendation_note_var.get().strip() or None,
                )
                self._rule_effectiveness_recommendation_review = result
                if result.get("recommendation_review_id"):
                    self.rule_effectiveness_recommendation_review_id_var.set(str(result.get("recommendation_review_id") or ""))
                self.status_var.set(f"Rule effectiveness review: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "queue_rule_effectiveness_action_candidate":
                result = create_rule_action_candidate_from_recommendation(
                    self.rule_effectiveness_recommendation_review_id_var.get().strip(),
                    confirmation=self.rule_effectiveness_recommendation_queue_confirmation_var.get().strip() or None,
                )
                self._rule_effectiveness_recommendation_action = result
                if result.get("action_candidate_id"):
                    self.rule_effectiveness_recommendation_action_candidate_id_var.set(str(result.get("action_candidate_id") or ""))
                self.status_var.set(f"Rule effectiveness action candidate: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "copy_rule_effectiveness_recommendation_report":
                text = format_rule_effectiveness_recommendation_report(
                    recommendation_id=self.rule_effectiveness_recommendation_id_var.get().strip() or None,
                    action_candidate_id=self.rule_effectiveness_recommendation_action_candidate_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe rule effectiveness recommendation report copied.")
            elif action == "load_rule_batch_workspace":
                rule_ids = [item.strip() for item in self.rule_batch_rule_ids_var.get().split(",") if item.strip()]
                result = build_rule_batch_workspace(
                    self.rule_batch_document_id_var.get().strip(),
                    int(self.rule_batch_source_revision_var.get().strip() or "0"),
                    self.rule_batch_dataset_id_var.get().strip(),
                    policy_id=self.rule_batch_policy_id_var.get().strip() or "default_v1",
                    rule_ids=rule_ids or None,
                    include_document_certified_rules=bool(self.rule_batch_include_active_var.get()),
                )
                self._rule_batch_workspace = result
                self.status_var.set(f"Rule batch workspace: eligible {result.get('eligible_rule_count', 0)} of {result.get('selected_rule_count', 0)}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "build_rule_batch_plan":
                rule_ids = [item.strip() for item in self.rule_batch_rule_ids_var.get().split(",") if item.strip()]
                result = build_rule_batch_plan(
                    self.rule_batch_document_id_var.get().strip(),
                    int(self.rule_batch_source_revision_var.get().strip() or "0"),
                    self.rule_batch_dataset_id_var.get().strip(),
                    policy_id=self.rule_batch_policy_id_var.get().strip() or "default_v1",
                    rule_ids=rule_ids or None,
                    include_document_certified_rules=bool(self.rule_batch_include_active_var.get()),
                    max_rules=int(self.rule_batch_max_rules_var.get().strip() or "10"),
                    max_records_per_rule=int(self.rule_batch_max_records_var.get().strip() or "200"),
                )
                self._rule_batch_plan = result
                if result.get("batch_plan_id"):
                    self.rule_batch_plan_id_var.set(str(result.get("batch_plan_id") or ""))
                self.status_var.set(f"Rule batch plan: {result.get('rule_count', 0)} rules.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "run_rule_batch_analysis":
                result = run_rule_batch_analysis(
                    self.rule_batch_plan_id_var.get().strip(),
                    stop_after_items=(int(self.rule_batch_stop_after_items_var.get().strip()) if self.rule_batch_stop_after_items_var.get().strip() else None),
                )
                self._rule_batch_run = result
                if result.get("batch_run_id"):
                    self.rule_batch_run_id_var.set(str(result.get("batch_run_id") or ""))
                self.status_var.set(f"Rule batch run: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "cancel_rule_batch_run":
                result = cancel_rule_batch_run(
                    self.rule_batch_run_id_var.get().strip(),
                    self.rule_batch_cancellation_reason_var.get().strip(),
                )
                self._rule_batch_run = result
                self.status_var.set(f"Rule batch cancellation: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "rule_batch_health":
                from .rule_batch_analysis import get_rule_batch_health
                result = get_rule_batch_health(self.rule_batch_run_id_var.get().strip() or None)
                self._rule_batch_health = result
                self.status_var.set(f"Rule batch health: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "copy_rule_batch_report":
                text = format_rule_batch_report(
                    batch_run_id=self.rule_batch_run_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe rule batch report copied.")
            elif action == "load_autonomous_pdf_workspace":
                result = build_autonomous_pdf_workspace(
                    self.autonomous_pdf_document_id_var.get().strip() or document_id,
                    int(self.autonomous_pdf_source_revision_var.get().strip() or "0"),
                )
                self._autonomous_pdf_workspace = result
                self.status_var.set(f"Autonomous PDF workspace: {result.get('autonomous_readiness', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "build_autonomous_pdf_plan":
                result = build_autonomous_pdf_plan(
                    self.autonomous_pdf_document_id_var.get().strip() or document_id,
                    int(self.autonomous_pdf_source_revision_var.get().strip() or "0"),
                    max_pages=int(self.autonomous_pdf_max_pages_var.get().strip() or "300"),
                    max_harvest_candidates=int(self.autonomous_pdf_max_harvest_candidates_var.get().strip() or "50"),
                    max_proposal_candidates=int(self.autonomous_pdf_max_proposal_candidates_var.get().strip() or "20"),
                    max_rule_candidates=int(self.autonomous_pdf_max_rule_candidates_var.get().strip() or "10"),
                    max_certified_rules=int(self.autonomous_pdf_max_certified_rules_var.get().strip() or "5"),
                )
                self._autonomous_pdf_plan = result
                if result.get("autonomous_plan_id"):
                    self.autonomous_pdf_plan_id_var.set(str(result.get("autonomous_plan_id") or ""))
                self.status_var.set(f"Autonomous PDF plan: {result.get('autonomous_plan_id', 'blocked')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "run_autonomous_pdf_pipeline":
                result = run_autonomous_pdf_pipeline(
                    self.autonomous_pdf_plan_id_var.get().strip(),
                    confirmation=self.autonomous_pdf_confirmation_var.get().strip() or None,
                    stop_after_stage=self.autonomous_pdf_stop_after_stage_var.get().strip() or None,
                )
                self._autonomous_pdf_run = result
                if result.get("autonomous_run_id"):
                    self.autonomous_pdf_run_id_var.set(str(result.get("autonomous_run_id") or ""))
                self.status_var.set(f"Autonomous PDF run: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "cancel_autonomous_pdf_pipeline":
                result = cancel_autonomous_pdf_pipeline(
                    self.autonomous_pdf_run_id_var.get().strip(),
                    self.autonomous_pdf_cancellation_reason_var.get().strip(),
                )
                self._autonomous_pdf_run = result
                self.status_var.set(f"Autonomous PDF cancellation: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "autonomous_pdf_health":
                result = get_autonomous_pdf_health(self.autonomous_pdf_document_id_var.get().strip() or document_id or None)
                self._autonomous_pdf_health = result
                self.status_var.set(f"Autonomous PDF health: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "copy_autonomous_pdf_report":
                text = format_autonomous_pdf_report(
                    autonomous_run_id=self.autonomous_pdf_run_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe autonomous PDF report copied.")
            elif action == "load_autonomous_pdf_benchmark_workspace":
                result = build_autonomous_pdf_benchmark_workspace(
                    self.autonomous_pdf_benchmark_id_var.get().strip(),
                    autonomous_run_id=self.autonomous_pdf_benchmark_run_id_var.get().strip() or None,
                )
                self._autonomous_pdf_benchmark_workspace = result
                if result.get("autonomous_run_id"):
                    self.autonomous_pdf_benchmark_run_id_var.set(str(result.get("autonomous_run_id") or ""))
                self.status_var.set(f"Autonomous PDF benchmark workspace: {result.get('benchmark_status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "validate_autonomous_pdf_benchmark_manifest":
                result = validate_autonomous_pdf_benchmark_manifest(self.autonomous_pdf_benchmark_id_var.get().strip())
                self._autonomous_pdf_benchmark_manifest_validation = result
                self.status_var.set(f"Autonomous PDF benchmark manifest: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "run_autonomous_pdf_benchmark":
                result = run_autonomous_pdf_benchmark(
                    self.autonomous_pdf_benchmark_id_var.get().strip(),
                    self.autonomous_pdf_benchmark_run_id_var.get().strip(),
                    confirmation=self.autonomous_pdf_benchmark_confirmation_var.get().strip() or None,
                )
                self._autonomous_pdf_benchmark_result = result
                if result.get("benchmark_result_id"):
                    self.autonomous_pdf_benchmark_result_id_var.set(str(result.get("benchmark_result_id") or ""))
                if result.get("benchmark_receipt_id"):
                    self.autonomous_pdf_benchmark_receipt_id_var.set(str(result.get("benchmark_receipt_id") or ""))
                self.status_var.set(f"Autonomous PDF benchmark: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "autonomous_pdf_benchmark_health":
                result = get_autonomous_pdf_benchmark_health(self.autonomous_pdf_benchmark_id_var.get().strip() or None)
                self._autonomous_pdf_benchmark_health = result
                self.status_var.set(f"Autonomous PDF benchmark health: {result.get('status', 'unknown')}.")
                self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
            elif action == "copy_autonomous_pdf_benchmark_report":
                text = format_autonomous_pdf_benchmark_report(
                    benchmark_result_id=self.autonomous_pdf_benchmark_result_id_var.get().strip() or None,
                    benchmark_receipt_id=self.autonomous_pdf_benchmark_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe autonomous PDF benchmark report copied.")
            elif action == "load_autonomous_pdf_remediation_workspace":
                result = build_autonomous_pdf_remediation_workspace(self.autonomous_pdf_benchmark_result_id_var.get().strip())
                self._set_autonomous_pdf_remediation_status(result)
                if result.get("remediation_plan_id"):
                    self.autonomous_pdf_remediation_plan_id_var.set(str(result.get("remediation_plan_id") or ""))
                self.status_var.set(f"Autonomous PDF remediation workspace: {result.get('status', 'unknown')}.")
            elif action == "run_autonomous_pdf_remediation_triage":
                result = run_autonomous_pdf_remediation_triage(
                    self.autonomous_pdf_benchmark_result_id_var.get().strip(),
                    confirmation=self.autonomous_pdf_remediation_confirmation_var.get().strip() or None,
                )
                self._set_autonomous_pdf_remediation_status(result)
                if result.get("remediation_plan_id"):
                    self.autonomous_pdf_remediation_plan_id_var.set(str(result.get("remediation_plan_id") or ""))
                self.status_var.set(f"Autonomous PDF remediation triage: {result.get('status', 'unknown')}.")
            elif action == "review_autonomous_pdf_remediation_case":
                result = review_autonomous_pdf_remediation_case(
                    self.autonomous_pdf_remediation_case_id_var.get().strip(),
                    self.autonomous_pdf_remediation_review_decision_var.get().strip(),
                    note=self.autonomous_pdf_remediation_review_note_var.get().strip() or None,
                    confirmation=self.autonomous_pdf_remediation_confirmation_var.get().strip() or None,
                )
                self._set_autonomous_pdf_remediation_status(result)
                self.status_var.set(f"Autonomous PDF remediation review: {result.get('status', 'unknown')}.")
            elif action == "verify_autonomous_pdf_remediation":
                result = verify_autonomous_pdf_remediation(
                    self.autonomous_pdf_remediation_plan_id_var.get().strip(),
                    self.autonomous_pdf_remediation_new_result_id_var.get().strip(),
                    confirmation=self.autonomous_pdf_remediation_confirmation_var.get().strip() or None,
                )
                self._set_autonomous_pdf_remediation_status(result)
                self.status_var.set(f"Autonomous PDF remediation verification: {result.get('status', 'unknown')}.")
            elif action == "copy_autonomous_pdf_remediation_report":
                text = format_autonomous_pdf_remediation_report(
                    self.autonomous_pdf_remediation_plan_id_var.get().strip(),
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe autonomous PDF remediation report copied.")
            elif action == "load_autonomous_pdf_corrective_action_workspace":
                result = build_autonomous_pdf_corrective_action_workspace(self.autonomous_pdf_remediation_case_id_var.get().strip())
                self._set_autonomous_pdf_corrective_action_status(result)
                if result.get("corrective_action_id"):
                    self.autonomous_pdf_corrective_action_id_var.set(str(result.get("corrective_action_id") or ""))
                self.status_var.set(f"Autonomous PDF corrective workspace: {result.get('status', 'unknown')}.")
            elif action == "build_autonomous_pdf_corrective_action_plan":
                payload = json.loads(self.autonomous_pdf_corrective_action_payload_var.get().strip() or "{}")
                result = build_autonomous_pdf_corrective_action_plan(
                    self.autonomous_pdf_remediation_case_id_var.get().strip(),
                    self.autonomous_pdf_corrective_action_type_var.get().strip(),
                    payload,
                )
                self._set_autonomous_pdf_corrective_action_status(result)
                if result.get("corrective_action_id"):
                    self.autonomous_pdf_corrective_action_id_var.set(str(result.get("corrective_action_id") or ""))
                self.status_var.set(f"Autonomous PDF corrective plan: {result.get('status', 'unknown')}.")
            elif action == "execute_autonomous_pdf_corrective_action":
                result = execute_autonomous_pdf_corrective_action(
                    self.autonomous_pdf_corrective_action_id_var.get().strip(),
                    confirmation=self.autonomous_pdf_corrective_action_confirmation_var.get().strip() or None,
                )
                self._set_autonomous_pdf_corrective_action_status(result)
                self.status_var.set(f"Autonomous PDF corrective execution: {result.get('status', 'unknown')}.")
            elif action == "verify_autonomous_pdf_corrective_action":
                result = verify_autonomous_pdf_corrective_action(
                    self.autonomous_pdf_corrective_action_id_var.get().strip(),
                    self.autonomous_pdf_remediation_new_result_id_var.get().strip(),
                    confirmation=self.autonomous_pdf_corrective_action_confirmation_var.get().strip() or None,
                )
                self._set_autonomous_pdf_corrective_action_status(result)
                self.status_var.set(f"Autonomous PDF corrective verification: {result.get('status', 'unknown')}.")
            elif action == "close_autonomous_pdf_corrective_action":
                result = close_autonomous_pdf_corrective_action(
                    self.autonomous_pdf_corrective_action_id_var.get().strip(),
                    confirmation=self.autonomous_pdf_corrective_action_confirmation_var.get().strip() or None,
                )
                self._set_autonomous_pdf_corrective_action_status(result)
                self.status_var.set(f"Autonomous PDF corrective closure: {result.get('status', 'unknown')}.")
            elif action == "copy_autonomous_pdf_corrective_action_report":
                text = format_autonomous_pdf_corrective_action_report(
                    self.autonomous_pdf_corrective_action_id_var.get().strip(),
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe autonomous PDF corrective-action report copied.")
            elif action == "load_certified_rule_replay_workspace":
                result = build_certified_rule_replay_workspace(
                    self.certified_rule_replay_rule_id_var.get().strip(),
                    self.certified_rule_replay_dataset_id_var.get().strip() or None,
                )
                self._set_certified_rule_replay_status(result)
                if result.get("replay_plan_id"):
                    self.certified_rule_replay_plan_id_var.set(str(result.get("replay_plan_id") or ""))
                if result.get("replay_result_id"):
                    self.certified_rule_replay_result_id_var.set(str(result.get("replay_result_id") or ""))
                if result.get("replay_receipt_id"):
                    self.certified_rule_replay_receipt_id_var.set(str(result.get("replay_receipt_id") or ""))
                self.status_var.set(f"Certified rule replay workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_replay_eligibility":
                result = validate_certified_rule_replay_eligibility(
                    self.certified_rule_replay_rule_id_var.get().strip(),
                    dataset_id=self.certified_rule_replay_dataset_id_var.get().strip() or None,
                )
                self._set_certified_rule_replay_status(result)
                self.status_var.set(f"Certified rule replay eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_replay_plan":
                result = build_certified_rule_replay_plan(
                    self.certified_rule_replay_rule_id_var.get().strip(),
                    self.certified_rule_replay_dataset_id_var.get().strip(),
                    max_records=int(self.certified_rule_replay_max_records_var.get().strip() or "10000"),
                )
                self._set_certified_rule_replay_status(result)
                if result.get("replay_plan_id"):
                    self.certified_rule_replay_plan_id_var.set(str(result.get("replay_plan_id") or ""))
                self.status_var.set(f"Certified rule replay plan: {result.get('status', 'unknown')}.")
            elif action == "run_certified_rule_replay":
                result = run_certified_rule_replay(
                    self.certified_rule_replay_plan_id_var.get().strip(),
                    confirmation=self.certified_rule_replay_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_replay_status(result)
                if result.get("replay_result_id"):
                    self.certified_rule_replay_result_id_var.set(str(result.get("replay_result_id") or ""))
                if result.get("replay_receipt_id"):
                    self.certified_rule_replay_receipt_id_var.set(str(result.get("replay_receipt_id") or ""))
                self.status_var.set(f"Certified rule replay run: {result.get('status', 'unknown')}.")
            elif action == "certified_rule_replay_health":
                result = get_certified_rule_replay_health(self.certified_rule_replay_plan_id_var.get().strip() or None)
                self._set_certified_rule_replay_status(result)
                self.status_var.set(f"Certified rule replay health: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_replay_report":
                text = format_certified_rule_replay_report(
                    replay_result_id=self.certified_rule_replay_result_id_var.get().strip() or None,
                    replay_receipt_id=self.certified_rule_replay_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule replay report copied.")
            elif action == "load_certified_rule_objective_preview_workspace":
                result = build_certified_rule_objective_preview_workspace(
                    self.certified_rule_objective_preview_rule_id_var.get().strip(),
                    self.certified_rule_objective_preview_pack_id_var.get().strip(),
                    self.certified_rule_objective_preview_input_id_var.get().strip() or None,
                )
                self._set_certified_rule_objective_preview_status(result)
                if result.get("objective_preview_plan_id"):
                    self.certified_rule_objective_preview_plan_id_var.set(str(result.get("objective_preview_plan_id") or ""))
                if result.get("objective_preview_result_id"):
                    self.certified_rule_objective_preview_result_id_var.set(str(result.get("objective_preview_result_id") or ""))
                if result.get("objective_preview_receipt_id"):
                    self.certified_rule_objective_preview_receipt_id_var.set(str(result.get("objective_preview_receipt_id") or ""))
                self.status_var.set(f"Certified rule objective preview workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_objective_preview_eligibility":
                result = validate_certified_rule_objective_preview_eligibility(
                    self.certified_rule_objective_preview_rule_id_var.get().strip(),
                    self.certified_rule_objective_preview_pack_id_var.get().strip(),
                    controlled_input_id=self.certified_rule_objective_preview_input_id_var.get().strip() or None,
                    effect_mapping=json.loads(self.certified_rule_objective_preview_mapping_var.get().strip() or "{}"),
                )
                self._set_certified_rule_objective_preview_status(result)
                self.status_var.set(f"Certified rule objective preview eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_objective_preview_plan":
                result = build_certified_rule_objective_preview_plan(
                    self.certified_rule_objective_preview_rule_id_var.get().strip(),
                    self.certified_rule_objective_preview_pack_id_var.get().strip(),
                    self.certified_rule_objective_preview_input_id_var.get().strip(),
                    json.loads(self.certified_rule_objective_preview_mapping_var.get().strip() or "{}"),
                    max_records=int(self.certified_rule_objective_preview_max_records_var.get().strip() or "10000"),
                )
                self._set_certified_rule_objective_preview_status(result)
                if result.get("objective_preview_plan_id"):
                    self.certified_rule_objective_preview_plan_id_var.set(str(result.get("objective_preview_plan_id") or ""))
                self.status_var.set(f"Certified rule objective preview plan: {result.get('status', 'unknown')}.")
            elif action == "run_certified_rule_objective_preview":
                result = run_certified_rule_objective_preview(
                    self.certified_rule_objective_preview_plan_id_var.get().strip(),
                    confirmation=self.certified_rule_objective_preview_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_objective_preview_status(result)
                if result.get("objective_preview_result_id"):
                    self.certified_rule_objective_preview_result_id_var.set(str(result.get("objective_preview_result_id") or ""))
                if result.get("objective_preview_receipt_id"):
                    self.certified_rule_objective_preview_receipt_id_var.set(str(result.get("objective_preview_receipt_id") or ""))
                self.status_var.set(f"Certified rule objective preview run: {result.get('status', 'unknown')}.")
            elif action == "certified_rule_objective_preview_health":
                result = get_certified_rule_objective_preview_health(self.certified_rule_objective_preview_plan_id_var.get().strip() or None)
                self._set_certified_rule_objective_preview_status(result)
                self.status_var.set(f"Certified rule objective preview health: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_objective_preview_report":
                text = format_certified_rule_objective_preview_report(
                    objective_preview_result_id=self.certified_rule_objective_preview_result_id_var.get().strip() or None,
                    objective_preview_receipt_id=self.certified_rule_objective_preview_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule objective preview report copied.")
            elif action == "load_certified_rule_scoring_preview_workspace":
                result = build_certified_rule_scoring_preview_workspace(
                    self.certified_rule_scoring_preview_objective_result_id_var.get().strip(),
                    self.certified_rule_scoring_preview_config_id_var.get().strip() or None,
                )
                self._set_certified_rule_scoring_preview_status(result)
                if result.get("scoring_preview_plan_id"):
                    self.certified_rule_scoring_preview_plan_id_var.set(str(result.get("scoring_preview_plan_id") or ""))
                if result.get("scoring_preview_result_id"):
                    self.certified_rule_scoring_preview_result_id_var.set(str(result.get("scoring_preview_result_id") or ""))
                if result.get("scoring_preview_receipt_id"):
                    self.certified_rule_scoring_preview_receipt_id_var.set(str(result.get("scoring_preview_receipt_id") or ""))
                self.status_var.set(f"Certified rule scoring preview workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_scoring_preview_eligibility":
                result = validate_certified_rule_scoring_preview_eligibility(
                    self.certified_rule_scoring_preview_objective_result_id_var.get().strip(),
                    self.certified_rule_scoring_preview_config_id_var.get().strip(),
                )
                self._set_certified_rule_scoring_preview_status(result)
                self.status_var.set(f"Certified rule scoring preview eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_scoring_preview_plan":
                result = build_certified_rule_scoring_preview_plan(
                    self.certified_rule_scoring_preview_objective_result_id_var.get().strip(),
                    self.certified_rule_scoring_preview_config_id_var.get().strip(),
                )
                self._set_certified_rule_scoring_preview_status(result)
                if result.get("scoring_preview_plan_id"):
                    self.certified_rule_scoring_preview_plan_id_var.set(str(result.get("scoring_preview_plan_id") or ""))
                self.status_var.set(f"Certified rule scoring preview plan: {result.get('status', 'unknown')}.")
            elif action == "run_certified_rule_scoring_preview":
                result = run_certified_rule_scoring_preview(
                    self.certified_rule_scoring_preview_plan_id_var.get().strip(),
                    confirmation=self.certified_rule_scoring_preview_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_scoring_preview_status(result)
                if result.get("scoring_preview_result_id"):
                    self.certified_rule_scoring_preview_result_id_var.set(str(result.get("scoring_preview_result_id") or ""))
                if result.get("scoring_preview_receipt_id"):
                    self.certified_rule_scoring_preview_receipt_id_var.set(str(result.get("scoring_preview_receipt_id") or ""))
                self.status_var.set(f"Certified rule scoring preview run: {result.get('status', 'unknown')}.")
            elif action == "certified_rule_scoring_preview_health":
                result = get_certified_rule_scoring_preview_health(self.certified_rule_scoring_preview_plan_id_var.get().strip() or None)
                self._set_certified_rule_scoring_preview_status(result)
                self.status_var.set(f"Certified rule scoring preview health: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_scoring_preview_report":
                text = format_certified_rule_scoring_preview_report(
                    scoring_preview_result_id=self.certified_rule_scoring_preview_result_id_var.get().strip() or None,
                    scoring_preview_receipt_id=self.certified_rule_scoring_preview_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule scoring preview report copied.")
            elif action == "load_certified_rule_fast_lane_preview_workspace":
                result = build_certified_rule_fast_lane_preview_workspace(
                    self.certified_rule_fast_lane_preview_rule_id_var.get().strip(),
                )
                self._set_certified_rule_fast_lane_preview_status(result)
                if result.get("fast_lane_preview_plan_id"):
                    self.certified_rule_fast_lane_preview_plan_id_var.set(str(result.get("fast_lane_preview_plan_id") or ""))
                if result.get("fast_lane_preview_result_id"):
                    self.certified_rule_fast_lane_preview_result_id_var.set(str(result.get("fast_lane_preview_result_id") or ""))
                if result.get("fast_lane_preview_receipt_id"):
                    self.certified_rule_fast_lane_preview_receipt_id_var.set(str(result.get("fast_lane_preview_receipt_id") or ""))
                self.status_var.set(f"Certified rule Fast Lane preview workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_fast_lane_preview_eligibility":
                result = validate_certified_rule_fast_lane_preview_eligibility(
                    self.certified_rule_fast_lane_preview_rule_id_var.get().strip(),
                )
                self._set_certified_rule_fast_lane_preview_status(result)
                self.status_var.set(f"Certified rule Fast Lane preview eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_fast_lane_preview_plan":
                result = build_certified_rule_fast_lane_preview_plan(
                    self.certified_rule_fast_lane_preview_rule_id_var.get().strip(),
                )
                self._set_certified_rule_fast_lane_preview_status(result)
                if result.get("fast_lane_preview_plan_id"):
                    self.certified_rule_fast_lane_preview_plan_id_var.set(str(result.get("fast_lane_preview_plan_id") or ""))
                self.status_var.set(f"Certified rule Fast Lane preview plan: {result.get('status', 'unknown')}.")
            elif action == "run_certified_rule_fast_lane_preview":
                result = run_certified_rule_fast_lane_preview(
                    self.certified_rule_fast_lane_preview_plan_id_var.get().strip(),
                    confirmation=self.certified_rule_fast_lane_preview_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_fast_lane_preview_status(result)
                if result.get("fast_lane_preview_result_id"):
                    self.certified_rule_fast_lane_preview_result_id_var.set(str(result.get("fast_lane_preview_result_id") or ""))
                if result.get("fast_lane_preview_receipt_id"):
                    self.certified_rule_fast_lane_preview_receipt_id_var.set(str(result.get("fast_lane_preview_receipt_id") or ""))
                self.status_var.set(f"Certified rule Fast Lane preview run: {result.get('status', 'unknown')}.")
            elif action == "certified_rule_fast_lane_preview_health":
                result = get_certified_rule_fast_lane_preview_health(self.certified_rule_fast_lane_preview_plan_id_var.get().strip() or None)
                self._set_certified_rule_fast_lane_preview_status(result)
                self.status_var.set(f"Certified rule Fast Lane preview health: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_fast_lane_preview_report":
                text = format_certified_rule_fast_lane_preview_report(
                    fast_lane_preview_result_id=self.certified_rule_fast_lane_preview_result_id_var.get().strip() or None,
                    fast_lane_preview_receipt_id=self.certified_rule_fast_lane_preview_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule Fast Lane preview report copied.")
            elif action == "load_certified_rule_integration_authorization_workspace":
                result = build_certified_rule_integration_authorization_workspace(
                    self.certified_rule_integration_authorization_rule_id_var.get().strip(),
                    self.certified_rule_integration_authorization_scoring_result_id_var.get().strip() or None,
                    self.certified_rule_integration_authorization_fast_lane_result_id_var.get().strip() or None,
                )
                self._set_certified_rule_integration_authorization_status(result)
                if result.get("scoring_preview_result_id"):
                    self.certified_rule_integration_authorization_scoring_result_id_var.set(str(result.get("scoring_preview_result_id") or ""))
                if result.get("fast_lane_preview_result_id"):
                    self.certified_rule_integration_authorization_fast_lane_result_id_var.set(str(result.get("fast_lane_preview_result_id") or ""))
                if result.get("integration_authorization_plan_id"):
                    self.certified_rule_integration_authorization_plan_id_var.set(str(result.get("integration_authorization_plan_id") or ""))
                if result.get("integration_authorization_result_id"):
                    self.certified_rule_integration_authorization_result_id_var.set(str(result.get("integration_authorization_result_id") or ""))
                if result.get("integration_authorization_receipt_id"):
                    self.certified_rule_integration_authorization_receipt_id_var.set(str(result.get("integration_authorization_receipt_id") or ""))
                self.status_var.set(f"Certified rule integration authorization workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_integration_authorization_eligibility":
                result = validate_certified_rule_integration_authorization_eligibility(
                    self.certified_rule_integration_authorization_rule_id_var.get().strip(),
                    self.certified_rule_integration_authorization_scoring_result_id_var.get().strip(),
                    self.certified_rule_integration_authorization_fast_lane_result_id_var.get().strip(),
                )
                self._set_certified_rule_integration_authorization_status(result)
                self.status_var.set(f"Certified rule integration authorization eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_integration_authorization_plan":
                result = build_certified_rule_integration_authorization_plan(
                    self.certified_rule_integration_authorization_rule_id_var.get().strip(),
                    self.certified_rule_integration_authorization_scoring_result_id_var.get().strip(),
                    self.certified_rule_integration_authorization_fast_lane_result_id_var.get().strip(),
                )
                self._set_certified_rule_integration_authorization_status(result)
                if result.get("integration_authorization_plan_id"):
                    self.certified_rule_integration_authorization_plan_id_var.set(str(result.get("integration_authorization_plan_id") or ""))
                self.status_var.set(f"Certified rule integration authorization plan: {result.get('status', 'unknown')}.")
            elif action == "save_certified_rule_integration_authorization_decision":
                acknowledgements = [item.strip() for item in self.certified_rule_integration_authorization_ack_var.get().split(",") if item.strip()]
                result = save_certified_rule_integration_authorization_decision(
                    self.certified_rule_integration_authorization_plan_id_var.get().strip(),
                    self.certified_rule_integration_authorization_reviewer_var.get().strip(),
                    self.certified_rule_integration_authorization_decision_var.get().strip(),
                    self.certified_rule_integration_authorization_rationale_var.get().strip(),
                    acknowledgements,
                    confirmation=self.certified_rule_integration_authorization_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_integration_authorization_status(result)
                if result.get("integration_authorization_result_id"):
                    self.certified_rule_integration_authorization_result_id_var.set(str(result.get("integration_authorization_result_id") or ""))
                if result.get("integration_authorization_receipt_id"):
                    self.certified_rule_integration_authorization_receipt_id_var.set(str(result.get("integration_authorization_receipt_id") or ""))
                self.status_var.set(f"Certified rule integration authorization decision: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_integration_authorization_report":
                text = format_certified_rule_integration_authorization_report(
                    integration_authorization_result_id=self.certified_rule_integration_authorization_result_id_var.get().strip() or None,
                    integration_authorization_receipt_id=self.certified_rule_integration_authorization_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule integration authorization report copied.")
            elif action == "load_certified_rule_release_candidate_workspace":
                result = build_certified_rule_release_candidate_workspace(
                    self.certified_rule_release_candidate_rule_id_var.get().strip(),
                    self.certified_rule_release_candidate_authorization_result_id_var.get().strip(),
                )
                self._set_certified_rule_release_candidate_status(result)
                if result.get("release_candidate_plan_id"):
                    self.certified_rule_release_candidate_plan_id_var.set(str(result.get("release_candidate_plan_id") or ""))
                if result.get("release_candidate_result_id"):
                    self.certified_rule_release_candidate_result_id_var.set(str(result.get("release_candidate_result_id") or ""))
                if result.get("release_candidate_receipt_id"):
                    self.certified_rule_release_candidate_receipt_id_var.set(str(result.get("release_candidate_receipt_id") or ""))
                self.status_var.set(f"Certified rule release candidate workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_release_candidate_eligibility":
                result = validate_certified_rule_release_candidate_eligibility(
                    self.certified_rule_release_candidate_rule_id_var.get().strip(),
                    self.certified_rule_release_candidate_authorization_result_id_var.get().strip(),
                )
                self._set_certified_rule_release_candidate_status(result)
                self.status_var.set(f"Certified rule release candidate eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_release_candidate_plan":
                result = build_certified_rule_release_candidate_plan(
                    self.certified_rule_release_candidate_rule_id_var.get().strip(),
                    self.certified_rule_release_candidate_authorization_result_id_var.get().strip(),
                )
                self._set_certified_rule_release_candidate_status(result)
                if result.get("release_candidate_plan_id"):
                    self.certified_rule_release_candidate_plan_id_var.set(str(result.get("release_candidate_plan_id") or ""))
                self.status_var.set(f"Certified rule release candidate plan: {result.get('status', 'unknown')}.")
            elif action == "qualify_certified_rule_release_candidate":
                result = qualify_certified_rule_release_candidate(
                    self.certified_rule_release_candidate_plan_id_var.get().strip(),
                    confirmation=self.certified_rule_release_candidate_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_release_candidate_status(result)
                if result.get("release_candidate_result_id"):
                    self.certified_rule_release_candidate_result_id_var.set(str(result.get("release_candidate_result_id") or ""))
                if result.get("release_candidate_receipt_id"):
                    self.certified_rule_release_candidate_receipt_id_var.set(str(result.get("release_candidate_receipt_id") or ""))
                self.status_var.set(f"Certified rule release candidate qualification: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_release_candidate_report":
                text = format_certified_rule_release_candidate_report(
                    release_candidate_result_id=self.certified_rule_release_candidate_result_id_var.get().strip() or None,
                    release_candidate_receipt_id=self.certified_rule_release_candidate_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule release candidate report copied.")
            elif action == "load_certified_rule_controlled_integration_workspace":
                result = build_certified_rule_controlled_integration_workspace(
                    self.certified_rule_controlled_integration_rule_id_var.get().strip(),
                    self.certified_rule_controlled_integration_release_result_id_var.get().strip(),
                    self.certified_rule_controlled_integration_target_id_var.get().strip(),
                )
                self._set_certified_rule_controlled_integration_status(result)
                if result.get("controlled_integration_plan_id"):
                    self.certified_rule_controlled_integration_plan_id_var.set(str(result.get("controlled_integration_plan_id") or ""))
                if result.get("controlled_integration_result_id"):
                    self.certified_rule_controlled_integration_result_id_var.set(str(result.get("controlled_integration_result_id") or ""))
                if result.get("controlled_integration_receipt_id"):
                    self.certified_rule_controlled_integration_receipt_id_var.set(str(result.get("controlled_integration_receipt_id") or ""))
                self.status_var.set(f"Certified rule controlled integration workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_controlled_integration_eligibility":
                result = validate_certified_rule_controlled_integration_eligibility(
                    self.certified_rule_controlled_integration_rule_id_var.get().strip(),
                    self.certified_rule_controlled_integration_release_result_id_var.get().strip(),
                    self.certified_rule_controlled_integration_target_id_var.get().strip(),
                )
                self._set_certified_rule_controlled_integration_status(result)
                self.status_var.set(f"Certified rule controlled integration eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_controlled_integration_plan":
                result = build_certified_rule_controlled_integration_plan(
                    self.certified_rule_controlled_integration_rule_id_var.get().strip(),
                    self.certified_rule_controlled_integration_release_result_id_var.get().strip(),
                    self.certified_rule_controlled_integration_target_id_var.get().strip(),
                )
                self._set_certified_rule_controlled_integration_status(result)
                if result.get("controlled_integration_plan_id"):
                    self.certified_rule_controlled_integration_plan_id_var.set(str(result.get("controlled_integration_plan_id") or ""))
                self.status_var.set(f"Certified rule controlled integration plan: {result.get('status', 'unknown')}.")
            elif action == "execute_certified_rule_controlled_integration":
                result = execute_certified_rule_controlled_integration(
                    self.certified_rule_controlled_integration_plan_id_var.get().strip(),
                    confirmation=self.certified_rule_controlled_integration_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_controlled_integration_status(result)
                if result.get("controlled_integration_result_id"):
                    self.certified_rule_controlled_integration_result_id_var.set(str(result.get("controlled_integration_result_id") or ""))
                if result.get("controlled_integration_receipt_id"):
                    self.certified_rule_controlled_integration_receipt_id_var.set(str(result.get("controlled_integration_receipt_id") or ""))
                self.status_var.set(f"Certified rule controlled integration execution: {result.get('status', 'unknown')}.")
            elif action == "certified_rule_controlled_integration_health":
                result = get_certified_rule_controlled_integration_health(self.certified_rule_controlled_integration_plan_id_var.get().strip() or None)
                self._set_certified_rule_controlled_integration_status(result)
                self.status_var.set(f"Certified rule controlled integration health: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_controlled_integration_report":
                text = format_certified_rule_controlled_integration_report(
                    controlled_integration_result_id=self.certified_rule_controlled_integration_result_id_var.get().strip() or None,
                    controlled_integration_receipt_id=self.certified_rule_controlled_integration_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule controlled integration report copied.")
            elif action == "load_certified_rule_production_authorization_workspace":
                result = build_certified_rule_production_authorization_workspace(
                    self.certified_rule_production_authorization_rule_id_var.get().strip(),
                    self.certified_rule_production_authorization_integration_result_id_var.get().strip(),
                    self.certified_rule_production_authorization_target_id_var.get().strip(),
                )
                self._set_certified_rule_production_authorization_status(result)
                if result.get("production_authorization_plan_id"):
                    self.certified_rule_production_authorization_plan_id_var.set(str(result.get("production_authorization_plan_id") or ""))
                if result.get("production_authorization_result_id"):
                    self.certified_rule_production_authorization_result_id_var.set(str(result.get("production_authorization_result_id") or ""))
                if result.get("production_authorization_receipt_id"):
                    self.certified_rule_production_authorization_receipt_id_var.set(str(result.get("production_authorization_receipt_id") or ""))
                self.status_var.set(f"Certified rule production authorization workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_production_authorization_eligibility":
                result = validate_certified_rule_production_authorization_eligibility(
                    self.certified_rule_production_authorization_rule_id_var.get().strip(),
                    self.certified_rule_production_authorization_integration_result_id_var.get().strip(),
                    self.certified_rule_production_authorization_target_id_var.get().strip(),
                )
                self._set_certified_rule_production_authorization_status(result)
                self.status_var.set(f"Certified rule production authorization eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_production_authorization_plan":
                result = build_certified_rule_production_authorization_plan(
                    self.certified_rule_production_authorization_rule_id_var.get().strip(),
                    self.certified_rule_production_authorization_integration_result_id_var.get().strip(),
                    self.certified_rule_production_authorization_target_id_var.get().strip(),
                )
                self._set_certified_rule_production_authorization_status(result)
                if result.get("production_authorization_plan_id"):
                    self.certified_rule_production_authorization_plan_id_var.set(str(result.get("production_authorization_plan_id") or ""))
                self.status_var.set(f"Certified rule production authorization plan: {result.get('status', 'unknown')}.")
            elif action == "save_certified_rule_production_authorization_decision":
                result = save_certified_rule_production_authorization_decision(
                    self.certified_rule_production_authorization_plan_id_var.get().strip(),
                    decision=self.certified_rule_production_authorization_decision_var.get().strip() or None,
                    confirmation=self.certified_rule_production_authorization_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_production_authorization_status(result)
                if result.get("production_authorization_result_id"):
                    self.certified_rule_production_authorization_result_id_var.set(str(result.get("production_authorization_result_id") or ""))
                if result.get("production_authorization_receipt_id"):
                    self.certified_rule_production_authorization_receipt_id_var.set(str(result.get("production_authorization_receipt_id") or ""))
                self.status_var.set(f"Certified rule production authorization save: {result.get('status', 'unknown')}.")
            elif action == "certified_rule_production_authorization_health":
                result = get_certified_rule_production_authorization_health(self.certified_rule_production_authorization_plan_id_var.get().strip() or None)
                self._set_certified_rule_production_authorization_status(result)
                self.status_var.set(f"Certified rule production authorization health: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_production_authorization_report":
                text = format_certified_rule_production_authorization_report(
                    production_authorization_result_id=self.certified_rule_production_authorization_result_id_var.get().strip() or None,
                    production_authorization_receipt_id=self.certified_rule_production_authorization_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule production authorization report copied.")
            elif action == "load_certified_rule_production_deployment_workspace":
                result = build_certified_rule_production_deployment_workspace(
                    self.certified_rule_production_deployment_rule_id_var.get().strip(),
                    self.certified_rule_production_deployment_authorization_result_id_var.get().strip(),
                    self.certified_rule_production_deployment_target_id_var.get().strip(),
                )
                self._set_certified_rule_production_deployment_status(result)
                if result.get("production_deployment_plan_id"):
                    self.certified_rule_production_deployment_plan_id_var.set(str(result.get("production_deployment_plan_id") or ""))
                if result.get("production_deployment_result_id"):
                    self.certified_rule_production_deployment_result_id_var.set(str(result.get("production_deployment_result_id") or ""))
                if result.get("production_deployment_receipt_id"):
                    self.certified_rule_production_deployment_receipt_id_var.set(str(result.get("production_deployment_receipt_id") or ""))
                self.status_var.set(f"Certified rule production deployment workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_production_deployment_eligibility":
                result = validate_certified_rule_production_deployment_eligibility(
                    self.certified_rule_production_deployment_rule_id_var.get().strip(),
                    self.certified_rule_production_deployment_authorization_result_id_var.get().strip(),
                    self.certified_rule_production_deployment_target_id_var.get().strip(),
                )
                self._set_certified_rule_production_deployment_status(result)
                self.status_var.set(f"Certified rule production deployment eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_production_deployment_plan":
                result = build_certified_rule_production_deployment_plan(
                    self.certified_rule_production_deployment_rule_id_var.get().strip(),
                    self.certified_rule_production_deployment_authorization_result_id_var.get().strip(),
                    self.certified_rule_production_deployment_target_id_var.get().strip(),
                )
                self._set_certified_rule_production_deployment_status(result)
                if result.get("production_deployment_plan_id"):
                    self.certified_rule_production_deployment_plan_id_var.set(str(result.get("production_deployment_plan_id") or ""))
                self.status_var.set(f"Certified rule production deployment plan: {result.get('status', 'unknown')}.")
            elif action == "execute_certified_rule_production_deployment":
                result = execute_certified_rule_production_deployment(
                    self.certified_rule_production_deployment_plan_id_var.get().strip(),
                    confirmation=self.certified_rule_production_deployment_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_production_deployment_status(result)
                if result.get("production_deployment_result_id"):
                    self.certified_rule_production_deployment_result_id_var.set(str(result.get("production_deployment_result_id") or ""))
                if result.get("production_deployment_receipt_id"):
                    self.certified_rule_production_deployment_receipt_id_var.set(str(result.get("production_deployment_receipt_id") or ""))
                self.status_var.set(f"Certified rule production deployment execution: {result.get('status', 'unknown')}.")
            elif action == "certified_rule_production_deployment_health":
                result = get_certified_rule_production_deployment_health(self.certified_rule_production_deployment_plan_id_var.get().strip() or None)
                self._set_certified_rule_production_deployment_status(result)
                self.status_var.set(f"Certified rule production deployment health: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_production_deployment_report":
                text = format_certified_rule_production_deployment_report(
                    production_deployment_result_id=self.certified_rule_production_deployment_result_id_var.get().strip() or None,
                    production_deployment_receipt_id=self.certified_rule_production_deployment_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule production deployment report copied.")
            elif action == "load_certified_rule_post_deployment_acceptance_workspace":
                result = build_certified_rule_post_deployment_acceptance_workspace(
                    self.certified_rule_post_deployment_result_id_var.get().strip(),
                )
                self._set_certified_rule_post_deployment_acceptance_status(result)
                if result.get("post_deployment_acceptance_plan_id"):
                    self.certified_rule_post_deployment_plan_id_var.set(str(result.get("post_deployment_acceptance_plan_id") or ""))
                if result.get("post_deployment_acceptance_result_id"):
                    self.certified_rule_post_deployment_decision_result_id_var.set(str(result.get("post_deployment_acceptance_result_id") or ""))
                if result.get("post_deployment_acceptance_receipt_id"):
                    self.certified_rule_post_deployment_receipt_id_var.set(str(result.get("post_deployment_acceptance_receipt_id") or ""))
                self.status_var.set(f"Certified rule post-deployment workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_certified_rule_post_deployment_acceptance_eligibility":
                result = validate_certified_rule_post_deployment_acceptance_eligibility(
                    self.certified_rule_post_deployment_result_id_var.get().strip(),
                )
                self._set_certified_rule_post_deployment_acceptance_status(result)
                self.status_var.set(f"Certified rule post-deployment eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_certified_rule_post_deployment_acceptance_plan":
                result = build_certified_rule_post_deployment_acceptance_plan(
                    self.certified_rule_post_deployment_result_id_var.get().strip(),
                )
                self._set_certified_rule_post_deployment_acceptance_status(result)
                if result.get("post_deployment_acceptance_plan_id"):
                    self.certified_rule_post_deployment_plan_id_var.set(str(result.get("post_deployment_acceptance_plan_id") or ""))
                self.status_var.set(f"Certified rule post-deployment plan: {result.get('status', 'unknown')}.")
            elif action == "save_certified_rule_post_deployment_acceptance_decision":
                result = save_certified_rule_post_deployment_acceptance_decision(
                    self.certified_rule_post_deployment_plan_id_var.get().strip(),
                    self.certified_rule_post_deployment_decision_var.get().strip() or "",
                    confirmation=self.certified_rule_post_deployment_confirmation_var.get().strip() or None,
                )
                self._set_certified_rule_post_deployment_acceptance_status(result)
                if result.get("post_deployment_acceptance_result_id"):
                    self.certified_rule_post_deployment_decision_result_id_var.set(str(result.get("post_deployment_acceptance_result_id") or ""))
                if result.get("post_deployment_acceptance_receipt_id"):
                    self.certified_rule_post_deployment_receipt_id_var.set(str(result.get("post_deployment_acceptance_receipt_id") or ""))
                self.status_var.set(f"Certified rule post-deployment decision: {result.get('status', 'unknown')}.")
            elif action == "certified_rule_post_deployment_acceptance_health":
                result = get_certified_rule_post_deployment_acceptance_health(self.certified_rule_post_deployment_plan_id_var.get().strip() or None)
                self._set_certified_rule_post_deployment_acceptance_status(result)
                self.status_var.set(f"Certified rule post-deployment health: {result.get('status', 'unknown')}.")
            elif action == "copy_certified_rule_post_deployment_acceptance_report":
                text = format_certified_rule_post_deployment_acceptance_report(
                    post_deployment_acceptance_result_id=self.certified_rule_post_deployment_decision_result_id_var.get().strip() or None,
                    post_deployment_acceptance_receipt_id=self.certified_rule_post_deployment_receipt_id_var.get().strip() or None,
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe certified rule post-deployment report copied.")
            elif action == "load_deployed_rule_operational_telemetry_workspace":
                if not self._validate_deployed_rule_operational_telemetry_inputs(action):
                    return
                result = build_deployed_rule_operational_telemetry_workspace(**self._deployed_rule_operational_telemetry_common_kwargs())
                self._set_deployed_rule_operational_telemetry_status(result)
                self.status_var.set(f"Deployed rule operational telemetry workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_deployed_rule_operational_telemetry_eligibility":
                if not self._validate_deployed_rule_operational_telemetry_inputs(action):
                    return
                result = validate_deployed_rule_operational_telemetry_eligibility(**self._deployed_rule_operational_telemetry_common_kwargs())
                self._set_deployed_rule_operational_telemetry_status(result)
                self.status_var.set(f"Deployed rule operational telemetry eligibility: {result.get('status', 'unknown')}.")
            elif action == "list_deployed_rule_operational_events":
                if not self._validate_deployed_rule_operational_telemetry_inputs(action):
                    return
                result = list_deployed_rule_operational_events(**self._deployed_rule_operational_telemetry_list_kwargs())
                self._set_deployed_rule_operational_telemetry_status(result)
                self.status_var.set(f"Deployed rule operational telemetry events: {result.get('status', 'unknown')}.")
            elif action == "build_deployed_rule_operational_snapshot":
                if not self._validate_deployed_rule_operational_telemetry_inputs(action):
                    return
                result = build_deployed_rule_operational_snapshot(**self._deployed_rule_operational_telemetry_snapshot_kwargs())
                self._set_deployed_rule_operational_telemetry_status(result)
                self.status_var.set(f"Deployed rule operational telemetry snapshot: {result.get('status', 'unknown')}.")
            elif action == "deployed_rule_operational_telemetry_health":
                if not self._validate_deployed_rule_operational_telemetry_inputs(action):
                    return
                result = get_deployed_rule_operational_telemetry_health(**self._deployed_rule_operational_telemetry_common_kwargs())
                result = dict(result)
                result["telemetry_health"] = result.get("status", "unknown")
                self._set_deployed_rule_operational_telemetry_status(result)
                self.status_var.set(f"Deployed rule operational telemetry health: {result.get('telemetry_health', result.get('status', 'unknown'))}.")
            elif action == "copy_deployed_rule_operational_telemetry_report":
                if not self._validate_deployed_rule_operational_telemetry_inputs(action):
                    return
                text = format_deployed_rule_operational_telemetry_report(
                    **self._deployed_rule_operational_telemetry_common_kwargs(),
                    start_timestamp=self.deployed_rule_operational_telemetry_start_var.get().strip() or None,
                    end_timestamp=self.deployed_rule_operational_telemetry_end_var.get().strip() or None,
                    event_type=self.deployed_rule_operational_telemetry_event_type_var.get().strip() or None,
                    producer_id=self.deployed_rule_operational_telemetry_producer_var.get().strip() or None,
                    max_results=self._deployed_rule_operational_telemetry_max_results(),
                    public_safe=True,
                )
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe deployed-rule operational telemetry report copied.")
            elif action == "load_deployed_rule_effectiveness_readiness_workspace":
                if not self._validate_deployed_rule_effectiveness_readiness_inputs(action):
                    return
                result = build_deployed_rule_effectiveness_readiness_workspace(**self._deployed_rule_effectiveness_readiness_common_kwargs())
                self._set_deployed_rule_effectiveness_readiness_status(result)
                self.status_var.set(f"Deployed rule effectiveness readiness workspace: {result.get('status', 'unknown')}.")
            elif action == "validate_deployed_rule_effectiveness_readiness_eligibility":
                if not self._validate_deployed_rule_effectiveness_readiness_inputs(action):
                    return
                result = validate_deployed_rule_effectiveness_readiness_eligibility(**self._deployed_rule_effectiveness_readiness_common_kwargs())
                self._set_deployed_rule_effectiveness_readiness_status(result)
                self.status_var.set(f"Deployed rule effectiveness readiness eligibility: {result.get('status', 'unknown')}.")
            elif action == "build_deployed_rule_effectiveness_readiness_plan":
                if not self._validate_deployed_rule_effectiveness_readiness_inputs(action):
                    return
                result = build_deployed_rule_effectiveness_readiness_plan(**self._deployed_rule_effectiveness_readiness_common_kwargs())
                if isinstance(result, dict) and result.get("effectiveness_readiness_plan_id"):
                    self.deployed_rule_effectiveness_readiness_plan_id_var.set(str(result.get("effectiveness_readiness_plan_id") or ""))
                self._set_deployed_rule_effectiveness_readiness_status(result)
                self.status_var.set(f"Deployed rule effectiveness readiness plan: {result.get('status', 'unknown')}.")
            elif action == "load_deployed_rule_effectiveness_readiness_result":
                if not self._validate_deployed_rule_effectiveness_readiness_inputs(action):
                    return
                loaded = load_deployed_rule_effectiveness_readiness_result(
                    self.deployed_rule_effectiveness_readiness_loaded_result_id_var.get().strip(),
                )
                if isinstance(loaded, dict) and isinstance(loaded.get("effectiveness_readiness_result"), dict):
                    self._set_deployed_rule_effectiveness_readiness_status(loaded["effectiveness_readiness_result"])
                else:
                    self._set_deployed_rule_effectiveness_readiness_status(loaded)
                self.status_var.set(f"Deployed rule effectiveness readiness result load: {loaded.get('status', 'unknown')}.")
            elif action == "record_deployed_rule_effectiveness_readiness_result":
                if not self._validate_deployed_rule_effectiveness_readiness_inputs(action):
                    return
                result = record_deployed_rule_effectiveness_readiness_result(
                    self.deployed_rule_effectiveness_readiness_plan_id_var.get().strip(),
                    confirmation=self.deployed_rule_effectiveness_readiness_confirmation_var.get().strip(),
                )
                if isinstance(result, dict) and result.get("effectiveness_readiness_result_id"):
                    self.deployed_rule_effectiveness_readiness_loaded_result_id_var.set(str(result.get("effectiveness_readiness_result_id") or ""))
                    loaded = load_deployed_rule_effectiveness_readiness_result(str(result.get("effectiveness_readiness_result_id") or ""))
                    if isinstance(loaded, dict) and isinstance(loaded.get("effectiveness_readiness_result"), dict):
                        self._set_deployed_rule_effectiveness_readiness_status(loaded["effectiveness_readiness_result"])
                    else:
                        self._set_deployed_rule_effectiveness_readiness_status(result)
                else:
                    self._set_deployed_rule_effectiveness_readiness_status(result)
                self.status_var.set(f"Deployed rule effectiveness readiness result: {result.get('status', 'unknown')}.")
            elif action == "deployed_rule_effectiveness_readiness_health":
                result = get_deployed_rule_effectiveness_readiness_health()
                result = dict(result)
                result["readiness_health"] = result.get("status", "unknown")
                result["health_scope"] = "repository-wide"
                self._set_deployed_rule_effectiveness_readiness_status(result)
                self.status_var.set(f"Deployed rule effectiveness readiness health: {result.get('readiness_health', result.get('status', 'unknown'))}.")
            elif action == "copy_deployed_rule_effectiveness_readiness_report":
                if not self._validate_deployed_rule_effectiveness_readiness_inputs(action):
                    return
                text = format_deployed_rule_effectiveness_readiness_report(**self._deployed_rule_effectiveness_readiness_common_kwargs())
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe deployed-rule effectiveness readiness report copied.")
            elif action == "copy":
                text = format_pdf_text_layer_report(viewport_id=viewport_id or None, document_id=None if viewport_id else document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self.status_var.set("Public-safe PDF text-layer report copied.")
        except Exception as exc:
            self.status_var.set(f"PDF viewport action failed: {exc}")

    def _set_autonomous_pdf_remediation_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        total_cases = int(payload.get("case_count", payload.get("total_case_count", 0)) or 0)
        reviewed = int(payload.get("reviewed_case_count", 0) or 0)
        self.autonomous_pdf_remediation_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Original Release Classification: {payload.get('release_classification', 'unknown')}\n"
            f"Plan Status: {payload.get('status', 'unknown')}\n"
            f"Total Case Count: {total_cases}\n"
            f"Critical Case Count: {int(payload.get('critical_case_count', 0) or 0)}\n"
            f"High Case Count: {int(payload.get('high_case_count', 0) or 0)}\n"
            f"Unresolved Case Count: {max(total_cases - reviewed, 0)}\n"
            f"Reviewed Case Count: {reviewed}\n"
            f"Resolved Case Count: {int(payload.get('resolved_count', 0) or 0)}\n"
            f"Persisting Case Count: {int(payload.get('persisting_count', 0) or 0)}\n"
            f"Regressed Case Count: {int(payload.get('regressed_count', 0) or 0)}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue remediation review.')}"
        )

    def _set_autonomous_pdf_corrective_action_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        blockers = payload.get("blockers", [])
        blocker_text = ", ".join(str(item) for item in blockers) if isinstance(blockers, list) and blockers else "none"
        self.autonomous_pdf_corrective_action_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Review Decision: {payload.get('review_decision', 'unknown')}\n"
            f"Root-Cause Classification: {payload.get('root_cause_classification', 'unknown')}\n"
            f"Action Type: {payload.get('action_type', 'unknown')}\n"
            f"Action Status: {payload.get('status', 'unknown')}\n"
            f"Verification Required: {'Yes' if payload.get('verification_required') else 'No'}\n"
            f"Verification Outcome: {payload.get('verification_outcome', 'none')}\n"
            f"Closure Status: {payload.get('closure_status', 'open')}\n"
            f"Remaining Blockers: {blocker_text}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue corrective action processing.')}"
        )

    def _set_certified_rule_replay_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        self.certified_rule_replay_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Rule Status: {payload.get('rule_status', payload.get('status', 'unknown'))}\n"
            f"Certification Status: {payload.get('certification_status', 'unknown')}\n"
            f"Dataset Fingerprint Status: {payload.get('dataset_fingerprint_status', 'unknown')}\n"
            f"Replay Status: {payload.get('status', 'unknown')}\n"
            f"Total Records: {payload.get('total_records', payload.get('bounded_record_count', 0))}\n"
            f"Evaluated Records: {payload.get('evaluated_records', 0)}\n"
            f"Match Count: {payload.get('match_count', 0)}\n"
            f"No-Match Count: {payload.get('no_match_count', 0)}\n"
            f"Unsupported Count: {payload.get('unsupported_count', 0)}\n"
            f"Error Count: {payload.get('evaluator_error_count', 0)}\n"
            f"Replay Coverage: {payload.get('replay_coverage', 'null')}\n"
            f"Compatibility Rate: {payload.get('compatibility_rate', 'null')}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue replay workflow.')}"
        )

    def _set_certified_rule_objective_preview_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
        self.certified_rule_objective_preview_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Rule Status: {payload.get('rule_status', payload.get('status', 'unknown'))}\n"
            f"Certification Status: {payload.get('certification_status', 'unknown')}\n"
            f"Objective Pack Status: {payload.get('objective_pack_status', 'unknown')}\n"
            f"Controlled Input Status: {payload.get('controlled_input_status', 'unknown')}\n"
            f"Preview Status: {payload.get('status', 'unknown')}\n"
            f"Compared Records: {metrics.get('compared_records', payload.get('compared_records', 0))}\n"
            f"Improved Records: {metrics.get('improved_records', payload.get('improved_records', 0))}\n"
            f"Worsened Records: {metrics.get('worsened_records', payload.get('worsened_records', 0))}\n"
            f"Unsupported Records: {metrics.get('unsupported_records', payload.get('unsupported_records', 0))}\n"
            f"Preview Coverage: {metrics.get('preview_coverage', 'null')}\n"
            f"Compatibility Rate: {metrics.get('compatibility_rate', 'null')}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue objective preview workflow.')}"
        )

    def _set_certified_rule_scoring_preview_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
        self.certified_rule_scoring_preview_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Canonical Rule ID: {payload.get('canonical_rule_id', 'unknown')}\n"
            f"Certification Status: {payload.get('certification_status', 'unknown')}\n"
            f"Objective Preview Status: {payload.get('objective_preview_status', payload.get('status', 'unknown'))}\n"
            f"Phase 9O Compatibility: {payload.get('phase_9o_compatibility', payload.get('compatibility_status', 'unknown'))}\n"
            f"Scoring Configuration Status: {payload.get('scoring_config_status', 'unknown')}\n"
            f"Compatibility Status: {payload.get('compatibility_status', payload.get('status', 'unknown'))}\n"
            f"Scoring Preview Status: {payload.get('status', 'unknown')}\n"
            f"Total Records: {metrics.get('total_phase_9o_records', payload.get('total_record_count', 0))}\n"
            f"Scoreable Records: {metrics.get('scoreable_records', payload.get('scoreable_record_count', payload.get('scoreable_records', 0)))}\n"
            f"Compared Records: {metrics.get('compared_records', 0)}\n"
            f"Increased Records: {metrics.get('increased_score_records', 0)}\n"
            f"Decreased Records: {metrics.get('decreased_score_records', 0)}\n"
            f"Unchanged Records: {metrics.get('unchanged_score_records', 0)}\n"
            f"Mixed Records: {metrics.get('mixed_component_records', 0)}\n"
            f"Unsupported Records: {metrics.get('unsupported_records', 0)}\n"
            f"Error Count: {metrics.get('scoring_error_records', 0)}\n"
            f"Baseline Mean Score: {metrics.get('baseline_mean_bounded_score', metrics.get('baseline_mean_raw_score', 'null'))}\n"
            f"Rule-Enabled Mean Score: {metrics.get('rule_enabled_mean_bounded_score', metrics.get('rule_enabled_mean_raw_score', 'null'))}\n"
            f"Mean Score Delta: {metrics.get('mean_bounded_score_delta', metrics.get('mean_raw_score_delta', 'null'))}\n"
            f"Scoring Coverage: {metrics.get('scoring_coverage', 'null')}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue scoring preview workflow.')}"
        )

    def _set_certified_rule_fast_lane_preview_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        self.certified_rule_fast_lane_preview_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Certification Status: {payload.get('certification_status', 'unknown')}\n"
            f"Fast Lane Contract ID: {payload.get('fast_lane_contract_id', 'unknown')}\n"
            f"Fast Lane Contract Version: {payload.get('fast_lane_contract_version', 'unknown')}\n"
            f"Capability Status: {payload.get('capability_status', payload.get('compatibility_foundation_status', 'unknown'))}\n"
            f"Preview Status: {payload.get('preview_status', payload.get('status', 'unknown'))}\n"
            f"Overall Compatibility: {payload.get('overall_compatibility', 'unknown')}\n"
            f"Semantic Loss: {payload.get('semantic_loss', 'unknown')}\n"
            f"Compatible Dimensions: {payload.get('compatible_dimension_count', 0)}\n"
            f"Warning Dimensions: {payload.get('warning_dimension_count', 0)}\n"
            f"Incompatible Dimensions: {payload.get('incompatible_dimension_count', 0)}\n"
            f"Blocker Count: {payload.get('blocker_count', len(payload.get('blockers', []) if isinstance(payload.get('blockers'), list) else []))}\n"
            f"Warning Count: {payload.get('warning_count', len(payload.get('warnings', []) if isinstance(payload.get('warnings'), list) else []))}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue Fast Lane compatibility preview workflow.')}"
        )

    def _set_certified_rule_integration_authorization_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        self.certified_rule_integration_authorization_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Canonical Rule ID: {payload.get('canonical_rule_id', 'unknown')}\n"
            f"Certification Status: {payload.get('certification_status', 'unknown')}\n"
            f"Scoring Preview Status: {payload.get('scoring_preview_status', payload.get('status', 'unknown'))}\n"
            f"Fast Lane Preview Status: {payload.get('fast_lane_preview_status', payload.get('status', 'unknown'))}\n"
            f"Overall Compatibility: {payload.get('overall_compatibility', 'unknown')}\n"
            f"Semantic Loss: {payload.get('semantic_loss', 'unknown')}\n"
            f"Decision Status: {payload.get('status', 'unknown')}\n"
            f"Reviewer: {payload.get('reviewer_identity', 'none')}\n"
            f"Blocker Count: {len(payload.get('blockers', []) if isinstance(payload.get('blockers'), list) else [])}\n"
            f"Warning Count: {len(payload.get('warnings', []) if isinstance(payload.get('warnings'), list) else [])}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue integration authorization review.')}"
        )

    def _set_certified_rule_release_candidate_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        self.certified_rule_release_candidate_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Canonical Rule ID: {payload.get('canonical_rule_id', 'unknown')}\n"
            f"Authorization Status: {payload.get('authorization_status', payload.get('status', 'unknown'))}\n"
            f"Scoring Evidence Status: {payload.get('scoring_evidence_status', 'unknown')}\n"
            f"Compatibility Evidence Status: {payload.get('compatibility_evidence_status', 'unknown')}\n"
            f"Eligibility Status: {payload.get('health_status', payload.get('status', 'unknown'))}\n"
            f"Qualification Status: {payload.get('status', 'unknown')}\n"
            f"Blocker Count: {len(payload.get('blockers', []) if isinstance(payload.get('blockers'), list) else [])}\n"
            f"Warning Count: {len(payload.get('warnings', []) if isinstance(payload.get('warnings'), list) else [])}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue release-candidate qualification.')}"
        )

    def _set_certified_rule_controlled_integration_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        self.certified_rule_controlled_integration_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Certification Status: {payload.get('certification_status', 'unknown')}\n"
            f"Release Candidate Status: {payload.get('release_candidate_status', payload.get('status', 'unknown'))}\n"
            f"Authorization Status: {payload.get('authorization_status', 'unknown')}\n"
            f"Target Status: {payload.get('target_status', payload.get('integration_target_id', 'unknown'))}\n"
            f"Environment Class: {payload.get('environment_class', 'unknown')}\n"
            f"Adapter Version: {payload.get('adapter_version', 'unknown')}\n"
            f"Namespace ID: {payload.get('isolated_namespace_id', payload.get('namespace_id', 'unknown'))}\n"
            f"Transaction ID: {payload.get('transaction_id', 'unknown')}\n"
            f"Execution Status: {payload.get('final_status', payload.get('status', 'unknown'))}\n"
            f"Pending Verification: {payload.get('pending_verification_status', payload.get('verification_status', 'unknown'))}\n"
            f"Committed Verification: {payload.get('committed_verification_status', payload.get('verification_capability_status', 'unknown'))}\n"
            f"Rollback Status: {payload.get('rollback_status', payload.get('rollback_capability_status', 'unknown'))}\n"
            f"Production Safety: {payload.get('production_safety_status', 'unknown')}\n"
            f"Stale Status: {'yes' if payload.get('stale') else 'no'}\n"
            f"Blocker Count: {len(payload.get('blockers', []) if isinstance(payload.get('blockers'), list) else [])}\n"
            f"Warning Count: {len(payload.get('warnings', []) if isinstance(payload.get('warnings'), list) else [])}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue controlled integration review.')}"
        )

    def _set_certified_rule_production_authorization_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        self.certified_rule_production_authorization_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Controlled Integration Status: {payload.get('controlled_integration_status', 'unknown')}\n"
            f"Release Candidate Status: {payload.get('release_candidate_status', 'unknown')}\n"
            f"Authorization Status: {payload.get('authorization_status', 'unknown')}\n"
            f"Production Target Status: {payload.get('production_target_status', payload.get('status', 'unknown'))}\n"
            f"Descriptor Access Mode: {payload.get('descriptor_access_mode', 'unknown')}\n"
            f"Namespace ID: {payload.get('namespace_id', 'unknown')}\n"
            f"Transaction ID: {payload.get('transaction_id', 'unknown')}\n"
            f"Decision Status: {payload.get('status', 'unknown')}\n"
            f"Stale Status: {'yes' if payload.get('stale') else 'no'}\n"
            f"Blocker Count: {len(payload.get('blockers', []) if isinstance(payload.get('blockers'), list) else [])}\n"
            f"Warning Count: {len(payload.get('warnings', []) if isinstance(payload.get('warnings'), list) else [])}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue production authorization review.')}"
        )

    def _set_certified_rule_production_deployment_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        self.certified_rule_production_deployment_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Certification Status: {payload.get('certification_status', 'unknown')}\n"
            f"Phase 9U Authorization Status: {payload.get('production_authorization_status', payload.get('authorization_status', 'unknown'))}\n"
            f"Phase 9T Verification Status: {payload.get('phase_9t_verification_status', 'unknown')}\n"
            f"Production Target Status: {payload.get('production_target_status', payload.get('status', 'unknown'))}\n"
            f"Adapter Version: {payload.get('adapter_version', 'unknown')}\n"
            f"Transaction ID: {payload.get('production_transaction_id', payload.get('transaction_id', 'unknown'))}\n"
            f"Apply Status: {payload.get('apply_status', 'unknown')}\n"
            f"Pending Verification: {payload.get('pending_verification_status', 'unknown')}\n"
            f"Commit Status: {payload.get('commit_status', 'unknown')}\n"
            f"Committed Verification: {payload.get('committed_verification_status', 'unknown')}\n"
            f"Rollback Status: {payload.get('rollback_status', 'unknown')}\n"
            f"Production Safety: {payload.get('production_safety_status', 'unknown')}\n"
            f"Blocker Count: {len(payload.get('blockers', []) if isinstance(payload.get('blockers'), list) else [])}\n"
            f"Warning Count: {len(payload.get('warnings', []) if isinstance(payload.get('warnings'), list) else [])}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue authorized production deployment review.')}"
        )

    def _set_certified_rule_post_deployment_acceptance_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        self.certified_rule_post_deployment_status_var.set(
            f"Document ID: {payload.get('document_id', 'unknown')}\n"
            f"Source Revision: {payload.get('source_revision', 'unknown')}\n"
            f"Canonical Rule ID: {payload.get('canonical_rule_id', 'unknown')}\n"
            f"Deployed Rule ID: {payload.get('deployed_rule_id', 'unknown')}\n"
            f"Phase 9V Status: {payload.get('phase_9v_result_status', payload.get('status', 'unknown'))}\n"
            f"Current Transaction Status: {payload.get('current_transaction_status', 'unknown')}\n"
            f"Current Verification Status: {payload.get('current_verification_status', 'unknown')}\n"
            f"Canonical Source Rule Status: {payload.get('canonical_source_rule_status', 'unknown')}\n"
            f"Deployed Rule Status: {payload.get('current_deployed_rule_status', 'unknown')}\n"
            f"Optional Telemetry Status: {payload.get('optional_telemetry_status', 'unknown')}\n"
            f"Decision Status: {payload.get('decision_status', payload.get('status', 'unknown'))}\n"
            f"Blocker Count: {len(payload.get('blockers', []) if isinstance(payload.get('blockers'), list) else [])}\n"
            f"Warning Count: {len(payload.get('warnings', []) if isinstance(payload.get('warnings'), list) else [])}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue post-deployment integrity review.')}"
        )

    def _deployed_rule_operational_telemetry_common_kwargs(self) -> dict[str, object]:
        return {
            "canonical_rule_id": self.deployed_rule_operational_telemetry_rule_id_var.get().strip(),
            "production_deployment_result_id": self.deployed_rule_operational_telemetry_result_id_var.get().strip(),
            "phase_9w_result_id": self.deployed_rule_operational_telemetry_phase_9w_result_id_var.get().strip() or None,
            "production_target_id": self.deployed_rule_operational_telemetry_target_id_var.get().strip() or None,
            "deployed_rule_id": self.deployed_rule_operational_telemetry_deployed_rule_id_var.get().strip() or None,
        }

    def _deployed_rule_operational_telemetry_max_results(self) -> int:
        text = self.deployed_rule_operational_telemetry_max_results_var.get().strip()
        try:
            value = int(text or "50")
        except ValueError:
            return 50
        return 50 if value <= 0 else value

    def _deployed_rule_operational_telemetry_list_kwargs(self) -> dict[str, object]:
        return {
            "deployed_rule_id": self.deployed_rule_operational_telemetry_deployed_rule_id_var.get().strip(),
            "production_deployment_result_id": self.deployed_rule_operational_telemetry_result_id_var.get().strip(),
            "event_type": self.deployed_rule_operational_telemetry_event_type_var.get().strip() or None,
            "producer_id": self.deployed_rule_operational_telemetry_producer_var.get().strip() or None,
            "start_timestamp": self.deployed_rule_operational_telemetry_start_var.get().strip() or None,
            "end_timestamp": self.deployed_rule_operational_telemetry_end_var.get().strip() or None,
            "max_results": self._deployed_rule_operational_telemetry_max_results(),
        }

    def _deployed_rule_operational_telemetry_snapshot_kwargs(self) -> dict[str, object]:
        return {
            "deployed_rule_id": self.deployed_rule_operational_telemetry_deployed_rule_id_var.get().strip(),
            "production_deployment_result_id": self.deployed_rule_operational_telemetry_result_id_var.get().strip(),
            "start_timestamp": self.deployed_rule_operational_telemetry_start_var.get().strip() or None,
            "end_timestamp": self.deployed_rule_operational_telemetry_end_var.get().strip() or None,
            "phase_9w_result_id": self.deployed_rule_operational_telemetry_phase_9w_result_id_var.get().strip() or None,
            "max_events": self._deployed_rule_operational_telemetry_max_results(),
        }

    def _register_deployed_rule_operational_telemetry_traces(self) -> None:
        if getattr(self, "_deployed_rule_operational_telemetry_traces_registered", False):
            return
        self._deployed_rule_operational_telemetry_traces_registered = True
        for variable in (
            self.deployed_rule_operational_telemetry_rule_id_var,
            self.deployed_rule_operational_telemetry_result_id_var,
            self.deployed_rule_operational_telemetry_phase_9w_result_id_var,
            self.deployed_rule_operational_telemetry_target_id_var,
            self.deployed_rule_operational_telemetry_deployed_rule_id_var,
            self.deployed_rule_operational_telemetry_start_var,
            self.deployed_rule_operational_telemetry_end_var,
            self.deployed_rule_operational_telemetry_event_type_var,
            self.deployed_rule_operational_telemetry_producer_var,
            self.deployed_rule_operational_telemetry_max_results_var,
        ):
            trace_add = getattr(variable, "trace_add", None)
            if callable(trace_add):
                trace_add("write", self._on_deployed_rule_operational_telemetry_input_changed)

    def _on_deployed_rule_operational_telemetry_input_changed(self, *_args: object) -> None:
        self._mark_deployed_rule_operational_telemetry_stale()

    def _mark_deployed_rule_operational_telemetry_stale(self) -> None:
        self.deployed_rule_operational_telemetry_status_var.set(
            "Phase 9V Deployment Status: stale\n"
            "Current Transaction Status: stale\n"
            "Deployed Rule Status: stale\n"
            "Canonical Source Rule Preservation: stale\n"
            "State Telemetry Available: unknown\n"
            "Execution Telemetry Available: unknown\n"
            "Producer IDs: none\n"
            "Observation Window: stale_due_to_input_change\n"
            "Total Matching Event Count: 0\n"
            "Returned Event Count: 0\n"
            "Validated Event Count: 0\n"
            "Invalid Event Count: 0\n"
            "Corrupt Event Count: 0\n"
            "Snapshot Completeness: stale\n"
            "Snapshot ID: none\n"
            "Telemetry Health: stale\n"
            "Metric Availability: unknown\n"
            "Effectiveness Evaluation Status: not_performed\n"
            "Blocker Count: 0\n"
            "Warning Count: 1\n"
            "Recommended Action: Refresh telemetry workspace, eligibility, events, snapshot, health, or report after changing inputs."
        )

    def _validate_deployed_rule_operational_telemetry_inputs(self, action: str) -> bool:
        required_fields = {
            "load_deployed_rule_operational_telemetry_workspace": (
                ("canonical_rule_id", self.deployed_rule_operational_telemetry_rule_id_var.get().strip()),
                ("production_deployment_result_id", self.deployed_rule_operational_telemetry_result_id_var.get().strip()),
            ),
            "validate_deployed_rule_operational_telemetry_eligibility": (
                ("canonical_rule_id", self.deployed_rule_operational_telemetry_rule_id_var.get().strip()),
                ("production_deployment_result_id", self.deployed_rule_operational_telemetry_result_id_var.get().strip()),
            ),
            "deployed_rule_operational_telemetry_health": (
                ("canonical_rule_id", self.deployed_rule_operational_telemetry_rule_id_var.get().strip()),
                ("production_deployment_result_id", self.deployed_rule_operational_telemetry_result_id_var.get().strip()),
            ),
            "copy_deployed_rule_operational_telemetry_report": (
                ("canonical_rule_id", self.deployed_rule_operational_telemetry_rule_id_var.get().strip()),
                ("production_deployment_result_id", self.deployed_rule_operational_telemetry_result_id_var.get().strip()),
            ),
            "list_deployed_rule_operational_events": (
                ("deployed_rule_id", self.deployed_rule_operational_telemetry_deployed_rule_id_var.get().strip()),
                ("production_deployment_result_id", self.deployed_rule_operational_telemetry_result_id_var.get().strip()),
            ),
            "build_deployed_rule_operational_snapshot": (
                ("deployed_rule_id", self.deployed_rule_operational_telemetry_deployed_rule_id_var.get().strip()),
                ("production_deployment_result_id", self.deployed_rule_operational_telemetry_result_id_var.get().strip()),
            ),
        }
        required = required_fields.get(action, ())
        missing = [name for name, value in required if not value]
        if not missing:
            return True
        self.deployed_rule_operational_telemetry_status_var.set(
            "Phase 9V Deployment Status: blocked\n"
            "Current Transaction Status: blocked\n"
            "Deployed Rule Status: blocked\n"
            "Canonical Source Rule Preservation: unknown\n"
            "State Telemetry Available: unknown\n"
            "Execution Telemetry Available: unknown\n"
            "Producer IDs: none\n"
            f"Observation Window: {self.deployed_rule_operational_telemetry_start_var.get().strip() or 'none'} -> {self.deployed_rule_operational_telemetry_end_var.get().strip() or 'none'}\n"
            "Total Matching Event Count: 0\n"
            "Returned Event Count: 0\n"
            "Validated Event Count: 0\n"
            "Invalid Event Count: 0\n"
            "Corrupt Event Count: 0\n"
            "Snapshot Completeness: unknown\n"
            "Snapshot ID: none\n"
            "Telemetry Health: blocked\n"
            "Metric Availability: unknown\n"
            "Effectiveness Evaluation Status: not_performed\n"
            f"Blocker Count: {len(missing)}\n"
            "Warning Count: 0\n"
            f"Recommended Action: Enter required telemetry identifiers before {action}: {', '.join(missing)}."
        )
        self.status_var.set(f"Deployed rule operational telemetry action blocked: missing {', '.join(missing)}.")
        return False

    def _set_deployed_rule_operational_telemetry_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        metric_availability = payload.get("metric_availability")
        if isinstance(metric_availability, dict):
            metric_summary = ", ".join(f"{key}={value}" for key, value in sorted(metric_availability.items()))
        else:
            metric_summary = "unknown"
        phase_9v_status = payload.get("phase_9v_result_status", payload.get("status", "unknown"))
        current_verification = payload.get("current_verification_status", "unknown")
        canonical_preservation = "preserved" if str(payload.get("canonical_rule_id", "") or "").strip() else "unknown"
        observation_start = payload.get("observation_start", self.deployed_rule_operational_telemetry_start_var.get().strip() or None)
        observation_end = payload.get("observation_end", self.deployed_rule_operational_telemetry_end_var.get().strip() or None)
        observation_window = f"{observation_start or 'none'} -> {observation_end or 'none'}"
        self.deployed_rule_operational_telemetry_status_var.set(
            f"Phase 9V Deployment Status: {phase_9v_status}\n"
            f"Current Transaction Status: {payload.get('current_transaction_status', 'unknown')}\n"
            f"Deployed Rule Status: {payload.get('deployed_rule_status', current_verification)}\n"
            f"Canonical Source Rule Preservation: {canonical_preservation}\n"
            f"State Telemetry Available: {payload.get('state_telemetry_available', 'unknown')}\n"
            f"Execution Telemetry Available: {payload.get('execution_telemetry_available', 'unknown')}\n"
            f"Producer IDs: {', '.join(payload.get('producer_ids', [])) if isinstance(payload.get('producer_ids'), list) and payload.get('producer_ids') else 'none'}\n"
            f"Observation Window: {observation_window}\n"
            f"Total Matching Event Count: {payload.get('total_matching_event_count', 0)}\n"
            f"Returned Event Count: {payload.get('returned_event_count', 0)}\n"
            f"Validated Event Count: {payload.get('validated_event_count', 0)}\n"
            f"Invalid Event Count: {payload.get('invalid_event_count', 0)}\n"
            f"Corrupt Event Count: {payload.get('corrupt_event_count', 0)}\n"
            f"Snapshot Completeness: {payload.get('snapshot_completeness_status', 'unknown')}\n"
            f"Snapshot ID: {payload.get('snapshot_id', 'none')}\n"
            f"Telemetry Health: {payload.get('telemetry_health', payload.get('status', 'unknown'))}\n"
            f"Metric Availability: {metric_summary}\n"
            f"Effectiveness Evaluation Status: {payload.get('effectiveness_evaluation_status', 'not_performed')}\n"
            f"Blocker Count: {len(payload.get('blockers', []) if isinstance(payload.get('blockers'), list) else [])}\n"
            f"Warning Count: {len(payload.get('warnings', []) if isinstance(payload.get('warnings'), list) else [])}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Review read-only deployed-rule telemetry state.')}"
        )

    def _deployed_rule_effectiveness_readiness_common_kwargs(self) -> dict[str, object]:
        return {
            "canonical_rule_id": self.deployed_rule_effectiveness_readiness_rule_id_var.get().strip(),
            "production_deployment_result_id": self.deployed_rule_effectiveness_readiness_result_id_var.get().strip(),
            "production_target_id": self.deployed_rule_effectiveness_readiness_target_id_var.get().strip(),
            "deployed_rule_id": self.deployed_rule_effectiveness_readiness_deployed_rule_id_var.get().strip(),
            "telemetry_snapshot_id": self.deployed_rule_effectiveness_readiness_snapshot_id_var.get().strip(),
            "observation_window_start": self.deployed_rule_effectiveness_readiness_start_var.get().strip(),
            "observation_window_end": self.deployed_rule_effectiveness_readiness_end_var.get().strip(),
            "post_deployment_result_id": self.deployed_rule_effectiveness_readiness_phase_9w_result_id_var.get().strip() or None,
        }

    def _register_deployed_rule_effectiveness_readiness_traces(self) -> None:
        if getattr(self, "_deployed_rule_effectiveness_readiness_traces_registered", False):
            return
        self._deployed_rule_effectiveness_readiness_traces_registered = True
        for variable in (
            self.deployed_rule_effectiveness_readiness_rule_id_var,
            self.deployed_rule_effectiveness_readiness_result_id_var,
            self.deployed_rule_effectiveness_readiness_target_id_var,
            self.deployed_rule_effectiveness_readiness_deployed_rule_id_var,
            self.deployed_rule_effectiveness_readiness_snapshot_id_var,
            self.deployed_rule_effectiveness_readiness_start_var,
            self.deployed_rule_effectiveness_readiness_end_var,
            self.deployed_rule_effectiveness_readiness_phase_9w_result_id_var,
            self.deployed_rule_effectiveness_readiness_plan_id_var,
            self.deployed_rule_effectiveness_readiness_loaded_result_id_var,
            self.deployed_rule_effectiveness_readiness_confirmation_var,
        ):
            trace_add = getattr(variable, "trace_add", None)
            if callable(trace_add):
                trace_add("write", self._on_deployed_rule_effectiveness_readiness_input_changed)

    def _on_deployed_rule_effectiveness_readiness_input_changed(self, *_args: object) -> None:
        self._mark_deployed_rule_effectiveness_readiness_stale()

    def _mark_deployed_rule_effectiveness_readiness_stale(self) -> None:
        self.deployed_rule_effectiveness_readiness_status_var.set(
            "Phase 9V Status: stale\n"
            "Deployed Rule Status: stale\n"
            "Canonical Source Rule Status: stale\n"
            "Telemetry Snapshot Status: stale\n"
            "Execution Producer Availability: unknown\n"
            "Execution Producer ID: unknown\n"
            "Execution Producer Fingerprint: unknown\n"
            "Valid Execution Attempt Count: 0\n"
            "Completed Event Count: 0\n"
            "Failed Event Count: 0\n"
            "Minimum Execution Attempts: 30\n"
            "Sample Sufficiency Status: stale_due_to_input_change\n"
            "Denominator Readiness: stale_due_to_input_change\n"
            "Observation-Window Readiness: stale_due_to_input_change\n"
            "Readiness Status: stale_due_to_input_change\n"
            "Readiness Plan ID: none\n"
            "Readiness Result ID: none\n"
            "Health Scope: repository-wide\n"
            "Readiness Health: stale\n"
            "Effectiveness Evaluation Status: not_performed\n"
            "Blocker Count: 0\n"
            "Warning Count: 1\n"
            "Recommended Action: Refresh readiness workspace, eligibility, plan, result, health, or report after changing inputs."
        )

    def _validate_deployed_rule_effectiveness_readiness_inputs(self, action: str) -> bool:
        shared = (
            ("canonical_rule_id", self.deployed_rule_effectiveness_readiness_rule_id_var.get().strip()),
            ("production_deployment_result_id", self.deployed_rule_effectiveness_readiness_result_id_var.get().strip()),
            ("production_target_id", self.deployed_rule_effectiveness_readiness_target_id_var.get().strip()),
            ("deployed_rule_id", self.deployed_rule_effectiveness_readiness_deployed_rule_id_var.get().strip()),
            ("telemetry_snapshot_id", self.deployed_rule_effectiveness_readiness_snapshot_id_var.get().strip()),
            ("observation_window_start", self.deployed_rule_effectiveness_readiness_start_var.get().strip()),
            ("observation_window_end", self.deployed_rule_effectiveness_readiness_end_var.get().strip()),
        )
        required_fields = {
            "load_deployed_rule_effectiveness_readiness_workspace": shared,
            "validate_deployed_rule_effectiveness_readiness_eligibility": shared,
            "build_deployed_rule_effectiveness_readiness_plan": shared,
            "copy_deployed_rule_effectiveness_readiness_report": shared,
            "load_deployed_rule_effectiveness_readiness_result": (
                ("effectiveness_readiness_result_id", self.deployed_rule_effectiveness_readiness_loaded_result_id_var.get().strip()),
            ),
            "record_deployed_rule_effectiveness_readiness_result": (
                ("effectiveness_readiness_plan_id", self.deployed_rule_effectiveness_readiness_plan_id_var.get().strip()),
                ("confirmation", self.deployed_rule_effectiveness_readiness_confirmation_var.get().strip()),
            ),
        }
        required = required_fields.get(action, ())
        missing = [name for name, value in required if not value]
        confirmation = self.deployed_rule_effectiveness_readiness_confirmation_var.get().strip()
        if action == "record_deployed_rule_effectiveness_readiness_result" and confirmation and confirmation != "RECORD_EFFECTIVENESS_READINESS_RESULT":
            missing.append("confirmation_exact_match_required")
        if not missing:
            return True
        self.deployed_rule_effectiveness_readiness_status_var.set(
            "Phase 9V Status: blocked\n"
            "Deployed Rule Status: blocked\n"
            "Canonical Source Rule Status: unknown\n"
            "Telemetry Snapshot Status: blocked\n"
            "Execution Producer Availability: unknown\n"
            "Execution Producer ID: unknown\n"
            "Execution Producer Fingerprint: unknown\n"
            "Valid Execution Attempt Count: 0\n"
            "Completed Event Count: 0\n"
            "Failed Event Count: 0\n"
            "Minimum Execution Attempts: 30\n"
            "Sample Sufficiency Status: blocked\n"
            "Denominator Readiness: blocked\n"
            f"Observation-Window Readiness: {self.deployed_rule_effectiveness_readiness_start_var.get().strip() or 'none'} -> {self.deployed_rule_effectiveness_readiness_end_var.get().strip() or 'none'}\n"
            "Readiness Status: blocked\n"
            f"Readiness Plan ID: {self.deployed_rule_effectiveness_readiness_plan_id_var.get().strip() or 'none'}\n"
            f"Readiness Result ID: {self.deployed_rule_effectiveness_readiness_loaded_result_id_var.get().strip() or 'none'}\n"
            "Health Scope: repository-wide\n"
            "Readiness Health: blocked\n"
            "Effectiveness Evaluation Status: not_performed\n"
            f"Blocker Count: {len(missing)}\n"
            "Warning Count: 0\n"
            f"Recommended Action: Enter required readiness identifiers before {action}: {', '.join(missing)}."
        )
        self.status_var.set(f"Deployed rule effectiveness readiness action blocked: missing {', '.join(missing)}.")
        return False

    def _set_deployed_rule_effectiveness_readiness_status(self, payload: dict[str, object] | None) -> None:
        if not isinstance(payload, dict):
            return
        criteria = payload.get("criteria")
        if isinstance(criteria, dict):
            phase_9v_status = "completed" if criteria.get("phase_9v_deployment_completed") else payload.get("status", "unknown")
            deployed_status = "bound" if criteria.get("deployed_instance_bound_to_phase_9v_result") else "unknown"
            canonical_status = "unchanged" if criteria.get("canonical_source_rule_unchanged") else "unknown"
            snapshot_status = "bound" if criteria.get("telemetry_snapshot_exists") else "unknown"
        else:
            phase_9v_status = payload.get("phase_9v_result_status", payload.get("status", "unknown"))
            deployed_status = payload.get("deployed_rule_status", payload.get("status", "unknown"))
            canonical_status = payload.get("canonical_source_rule_status", "unknown")
            snapshot_status = payload.get("snapshot_completeness_status", payload.get("status", "unknown"))
        self.deployed_rule_effectiveness_readiness_status_var.set(
            f"Phase 9V Status: {phase_9v_status}\n"
            f"Deployed Rule Status: {deployed_status}\n"
            f"Canonical Source Rule Status: {canonical_status}\n"
            f"Telemetry Snapshot Status: {snapshot_status}\n"
            f"Execution Producer Availability: {payload.get('execution_producer_available', payload.get('execution_producer_status', 'unknown'))}\n"
            f"Execution Producer ID: {payload.get('execution_producer_id', 'unknown')}\n"
            f"Execution Producer Fingerprint: {payload.get('execution_producer_fingerprint', 'unknown')}\n"
            f"Valid Execution Attempt Count: {payload.get('valid_execution_attempt_count', 0)}\n"
            f"Completed Event Count: {payload.get('execution_completion_count', 0)}\n"
            f"Failed Event Count: {payload.get('execution_failure_count', 0)}\n"
            f"Minimum Execution Attempts: {payload.get('minimum_execution_attempt_count', 30)}\n"
            f"Sample Sufficiency Status: {payload.get('sample_sufficiency_status', 'unknown')}\n"
            f"Denominator Readiness: {payload.get('denominator_readiness', 'unknown')}\n"
            f"Observation-Window Readiness: {payload.get('observation_window_readiness', 'unknown')}\n"
            f"Readiness Status: {payload.get('readiness_status', payload.get('status', 'unknown'))}\n"
            f"Readiness Plan ID: {payload.get('effectiveness_readiness_plan_id', self.deployed_rule_effectiveness_readiness_plan_id_var.get().strip() or 'none')}\n"
            f"Readiness Result ID: {payload.get('effectiveness_readiness_result_id', self.deployed_rule_effectiveness_readiness_loaded_result_id_var.get().strip() or 'none')}\n"
            f"Health Scope: {payload.get('health_scope', 'repository-wide')}\n"
            f"Readiness Health: {payload.get('readiness_health', payload.get('status', 'unknown'))}\n"
            f"Effectiveness Evaluation Status: {payload.get('effectiveness_evaluation_status', 'not_performed')}\n"
            f"Blocker Count: {len(payload.get('blockers', []) if isinstance(payload.get('blockers'), list) else [])}\n"
            f"Warning Count: {len(payload.get('warnings', []) if isinstance(payload.get('warnings'), list) else [])}\n"
            f"Recommended Action: {payload.get('recommended_action', 'Continue deployed-rule effectiveness-readiness review.')}"
        )

    def _set_pdf_viewport_status(self, *, viewport: dict[str, object] | None, render: dict[str, object] | None) -> None:
        certification = "unknown"
        current_page = "unknown"
        page_count = "unknown"
        zoom = "unknown"
        render_status = "unknown"
        cache_status = "unknown"
        locator_status = "not_selected"
        text_layer_status = "unknown"
        overlay_status = "none"
        workspace_status = "none"
        workspace_revision = 0
        bookmark_count = 0
        annotation_count = 0
        citation_draft_count = 0
        review_status = "none"
        duplicate_status = "none"
        duplicate_count = 0
        real_citation_id = "none"
        handoff_status = "none"
        handoff_review_status = "none"
        handoff_candidate_count = 0
        handoff_selected_binder = "none"
        handoff_existing_proposals = 0
        handoff_completed_action = "none"
        handoff_binder_id = "none"
        handoff_proposal_id = "none"
        handoff_revalidation_id = "none"
        promotion_proposal_status = "none"
        promotion_citation_id = "none"
        promotion_citation_provenance = "unknown"
        promotion_handoff_status = "none"
        promotion_duplicate_status = "none"
        promotion_conflict_status = "none"
        promotion_review_status = "none"
        promotion_receipt_id = "none"
        promotion_revalidation_status = "none"
        rule_activation_proposal_status = "none"
        rule_activation_promotion_receipt_status = "none"
        rule_activation_mapping_status = "none"
        rule_activation_schema_status = "none"
        rule_activation_duplicate_status = "none"
        rule_activation_conflict_status = "none"
        rule_activation_review_status = "none"
        rule_activation_active_rule_id = "none"
        rule_activation_receipt_id = "none"
        rule_activation_revalidation_status = "none"
        rule_activation_rollback_available = "No"
        rule_revalidation_rule_id = "none"
        rule_revalidation_rule_status = "none"
        rule_revalidation_provenance = "unknown"
        rule_revalidation_evaluator_status = "unknown"
        rule_revalidation_contract_case_count = 0
        rule_revalidation_passed_case_count = 0
        rule_revalidation_failed_case_count = 0
        rule_revalidation_mutation_detected = "No"
        rule_revalidation_review_status = "none"
        rule_revalidation_receipt_id = "none"
        rule_revalidation_status = "none"
        rule_revalidation_rollback_verified = "No"
        rule_supersession_old_rule_status = "none"
        rule_supersession_old_rule_certification = "none"
        rule_supersession_proposal_status = "none"
        rule_supersession_mapping_status = "none"
        rule_supersession_compatibility = "none"
        rule_supersession_scope_change = "none"
        rule_supersession_review_status = "none"
        rule_supersession_new_rule_id = "none"
        rule_supersession_version_chain_id = "none"
        rule_supersession_receipt_id = "none"
        rule_supersession_revalidation_status = "none"
        rule_supersession_rollback_available = "No"
        rule_effectiveness_certification = "none"
        rule_effectiveness_dataset_status = "none"
        rule_effectiveness_records_planned = 0
        rule_effectiveness_records_evaluated = 0
        rule_effectiveness_matched = 0
        rule_effectiveness_not_matched = 0
        rule_effectiveness_errors = 0
        rule_effectiveness_match_coverage = "null"
        rule_effectiveness_labels = "No"
        rule_effectiveness_precision = "null"
        rule_effectiveness_recall = "null"
        rule_effectiveness_specificity = "null"
        rule_effectiveness_balanced_accuracy = "null"
        rule_effectiveness_comparison = "none"
        rule_effectiveness_disagreement = "null"
        rule_effectiveness_mutation = "No"
        rule_effectiveness_recommendation_rule_id = "none"
        rule_effectiveness_recommendation_analysis_status = "none"
        rule_effectiveness_recommendation_policy_status = "none"
        rule_effectiveness_recommendation_type = "none"
        rule_effectiveness_recommendation_status = "not_generated"
        rule_effectiveness_recommendation_triggered = 0
        rule_effectiveness_recommendation_outcome_metrics = "No"
        rule_effectiveness_recommendation_comparison_available = "No"
        rule_effectiveness_recommendation_review_status = "pending"
        rule_effectiveness_recommendation_action_type = "none"
        rule_effectiveness_recommendation_action_status = "not_queued"
        rule_batch_dataset_status = "none"
        rule_batch_policy_status = "none"
        rule_batch_document_status = "unknown"
        rule_batch_revision_lock_status = "unknown"
        rule_batch_selected_rule_count = 0
        rule_batch_eligible_rule_count = 0
        rule_batch_blocked_rule_count = 0
        rule_batch_rules_omitted_by_limit = 0
        rule_batch_foreign_document_rule_count = 0
        rule_batch_foreign_revision_rule_count = 0
        rule_batch_total_planned_evaluations = 0
        rule_batch_status = "not_run"
        rule_batch_processed_count = 0
        rule_batch_successful_count = 0
        rule_batch_failed_count = 0
        rule_batch_blocked_count = 0
        rule_batch_next_item_index = 0
        rule_batch_continue_count = 0
        rule_batch_monitor_count = 0
        rule_batch_rollback_count = 0
        rule_batch_supersession_count = 0
        rule_batch_insufficient_count = 0
        autonomous_pdf_document_status = "unknown"
        autonomous_pdf_native_text_status = "unknown"
        autonomous_pdf_class = "unknown"
        autonomous_pdf_readiness = "unknown"
        autonomous_pdf_plan_status = "none"
        autonomous_pdf_run_status = "not_run"
        autonomous_pdf_certified_rule_count = 0
        autonomous_pdf_blocked_item_count = 0
        autonomous_pdf_receipt_id = "none"
        autonomous_pdf_benchmark_manifest_status = "unknown"
        autonomous_pdf_benchmark_run_status = "unknown"
        autonomous_pdf_benchmark_release_classification = "not_run"
        autonomous_pdf_benchmark_native_text_coverage = "null"
        autonomous_pdf_benchmark_anchor_recall = "null"
        autonomous_pdf_benchmark_citation_precision = "null"
        autonomous_pdf_benchmark_citation_recall = "null"
        autonomous_pdf_benchmark_proposal_precision = "null"
        autonomous_pdf_benchmark_proposal_recall = "null"
        autonomous_pdf_benchmark_rule_precision = "null"
        autonomous_pdf_benchmark_certification_correctness = "null"
        autonomous_pdf_benchmark_safety_count = 0
        autonomous_pdf_benchmark_mismatch_count = 0
        selected_text = "none"
        recommended = "Open a certified viewport session."
        renderer_status = "unavailable"
        if isinstance(viewport, dict):
            certification = str(viewport.get("certification_status", viewport.get("certification", "unknown")))
            current_page = viewport.get("current_page", viewport.get("page_number", "unknown"))
            page_count = viewport.get("page_count", "unknown")
            zoom = viewport.get("zoom_percent", "unknown")
            if viewport.get("selected_locator"):
                locator_status = "synchronized"
            if viewport.get("words") is not None:
                text_layer_status = "available"
        if isinstance(render, dict):
            render_status = str(render.get("render_status", render.get("status", "unknown")))
            cache_status = str(render.get("cache_status", "unknown"))
            renderer_status = "available" if render.get("status") != "renderer_unavailable" else "unavailable"
            if render.get("status") == "renderer_unavailable":
                recommended = "Enable a supported PDF renderer before page rendering."
        overlay = getattr(self, "_pdf_viewport_overlay", None)
        if isinstance(overlay, dict):
            overlay_status = f"{overlay.get('overlay_type', 'overlay')} ({overlay.get('mapped_locator_count', 0)}/{overlay.get('requested_locator_count', 0)})"
        workspace = getattr(self, "_pdf_reader_workspace", None)
        if isinstance(workspace, dict):
            loaded = load_pdf_reader_workspace(str(workspace.get("workspace_id") or ""))
            workspace_status = str(loaded.get("status", "current"))
            current_workspace = loaded.get("workspace") if isinstance(loaded.get("workspace"), dict) else workspace
            workspace_revision = int((current_workspace or {}).get("workspace_revision") or 0)
            bookmark_count = int((current_workspace or {}).get("bookmark_count") or 0)
            annotation_count = int((current_workspace or {}).get("annotation_count") or 0)
            citation_draft_count = int((current_workspace or {}).get("citation_draft_count") or 0)
        review = getattr(self, "_citation_draft_review", None)
        if isinstance(review, dict):
            review_status = str(review.get("review_status", review.get("status", "pending")))
            duplicate_status = str(review.get("duplicate_status", "none"))
            duplicate_count = int(review.get("duplicate_count", 0) or 0)
            real_citation_id = str(review.get("real_citation_id") or "none")
        creation = getattr(self, "_citation_draft_creation", None)
        if isinstance(creation, dict):
            real_citation_id = str(creation.get("citation_id") or real_citation_id)
            handoff_status = "pending_evidence_review" if creation.get("evidence_handoff_id") else handoff_status
            if creation.get("evidence_handoff_id") and hasattr(self, "evidence_handoff_id_var"):
                self.evidence_handoff_id_var.set(str(creation.get("evidence_handoff_id") or ""))
        handoff = getattr(self, "_evidence_handoff_review", None)
        if isinstance(handoff, dict):
            handoff_status = str(handoff.get("handoff_status", handoff.get("status", handoff_status)))
            handoff_review_status = str(handoff.get("review_status", "pending"))
            handoff_candidate_count = int(handoff.get("binder_candidate_count", 0) or 0)
            handoff_selected_binder = str(handoff.get("selected_binder_id") or "none")
            handoff_existing_proposals = int(handoff.get("existing_proposal_count", 0) or 0)
            handoff_completed_action = str(handoff.get("completed_action") or "none")
            handoff_binder_id = str(handoff.get("binder_id") or "none")
            handoff_proposal_id = str(handoff.get("proposal_id") or "none")
            handoff_revalidation_id = str(handoff.get("revalidation_id") or "none")
            recommended = str(handoff.get("recommended_action") or recommended)
        handoff_action = getattr(self, "_evidence_handoff_action", None)
        if isinstance(handoff_action, dict):
            handoff_binder_id = str(handoff_action.get("binder_id") or handoff_binder_id)
            handoff_proposal_id = str(handoff_action.get("proposal_id") or handoff_proposal_id)
            handoff_revalidation_id = str(handoff_action.get("revalidation_id") or handoff_revalidation_id)
            if handoff_action.get("proposal_id") and hasattr(self, "proposal_promotion_proposal_id_var"):
                self.proposal_promotion_proposal_id_var.set(str(handoff_action.get("proposal_id") or ""))
        promotion_workspace = getattr(self, "_proposal_promotion_workspace", None)
        if isinstance(promotion_workspace, dict):
            promotion_proposal_status = str(promotion_workspace.get("proposal_status") or "none")
            promotion_citation_id = str(promotion_workspace.get("citation_id") or "none")
            promotion_citation_provenance = str(promotion_workspace.get("citation_provenance_status") or "unknown")
            promotion_handoff_status = str(promotion_workspace.get("handoff_status") or "none")
            promotion_duplicate_status = str(promotion_workspace.get("duplicate_status") or "none")
            promotion_conflict_status = str(promotion_workspace.get("conflict_status") or "none")
            promotion_review_status = str(promotion_workspace.get("promotion_review_status") or "pending")
            promotion_receipt_id = str(promotion_workspace.get("promotion_receipt_id") or "none")
            promotion_revalidation_status = str(promotion_workspace.get("revalidation_status") or "none")
            recommended = str(promotion_workspace.get("recommended_action") or recommended)
        promotion_action = getattr(self, "_proposal_promotion_action", None)
        if isinstance(promotion_action, dict):
            promotion_receipt_id = str(promotion_action.get("promotion_receipt_id") or promotion_receipt_id)
            if promotion_action.get("proposal_id") and hasattr(self, "proposal_promotion_proposal_id_var"):
                self.proposal_promotion_proposal_id_var.set(str(promotion_action.get("proposal_id") or ""))
        rule_activation = getattr(self, "_rule_activation_workspace", None)
        if isinstance(rule_activation, dict):
            rule_activation_proposal_status = str(rule_activation.get("proposal_status") or "none")
            rule_activation_promotion_receipt_status = "completed" if rule_activation.get("promotion_receipt_id") else "missing"
            rule_activation_mapping_status = str(rule_activation.get("rule_mapping_status") or "none")
            rule_activation_schema_status = "valid" if rule_activation.get("rule_mapping_status") == "valid" else "invalid"
            rule_activation_duplicate_status = str(rule_activation.get("duplicate_status") or "none")
            rule_activation_conflict_status = str(rule_activation.get("conflict_status") or "none")
            rule_activation_review_status = str(rule_activation.get("rule_activation_review_status") or "pending")
            rule_activation_active_rule_id = str(rule_activation.get("active_rule_id") or "none")
            rule_activation_receipt_id = str(rule_activation.get("activation_receipt_id") or "none")
            rule_activation_revalidation_status = "pending_review" if rule_activation.get("activation_receipt_id") else "none"
            rule_activation_rollback_available = "Yes" if rule_activation.get("activation_receipt_id") else "No"
            recommended = str(rule_activation.get("recommended_action") or recommended)
        rule_activation_action = getattr(self, "_rule_activation_action", None)
        if isinstance(rule_activation_action, dict):
            rule_activation_active_rule_id = str(rule_activation_action.get("rule_id") or rule_activation_active_rule_id)
            rule_activation_receipt_id = str(rule_activation_action.get("activation_receipt_id") or rule_activation_receipt_id)
        rule_revalidation = getattr(self, "_rule_activation_revalidation_workspace", None)
        if isinstance(rule_revalidation, dict):
            rule_revalidation_rule_id = str(rule_revalidation.get("rule_id") or "none")
            rule_revalidation_rule_status = str(rule_revalidation.get("rule_status") or "none")
            rule_revalidation_provenance = str(rule_revalidation.get("activation_provenance_status") or "unknown")
            rule_revalidation_evaluator_status = str(rule_revalidation.get("runtime_evaluator_status") or "unknown")
            rule_revalidation_review_status = str(rule_revalidation.get("review_status") or "pending")
            rule_revalidation_receipt_id = str(rule_revalidation.get("certification_receipt_id") or "none")
            rule_revalidation_status = str(rule_revalidation.get("revalidation_status") or "none")
            recommended = str(rule_revalidation.get("recommended_action") or recommended)
        rule_revalidation_runtime = getattr(self, "_rule_activation_revalidation_runtime", None)
        if isinstance(rule_revalidation_runtime, dict):
            rule_revalidation_contract_case_count = int(rule_revalidation_runtime.get("required_case_count", 0) or 0)
            rule_revalidation_passed_case_count = int(rule_revalidation_runtime.get("passed_case_count", 0) or 0)
            rule_revalidation_failed_case_count = int(rule_revalidation_runtime.get("failed_case_count", 0) or 0)
            rule_revalidation_mutation_detected = "Yes" if rule_revalidation_runtime.get("persistent_state_mutated") else "No"
        rule_revalidation_action = getattr(self, "_rule_activation_revalidation_action", None)
        if isinstance(rule_revalidation_action, dict):
            rule_revalidation_receipt_id = str(rule_revalidation_action.get("certification_receipt_id") or rule_revalidation_receipt_id)
            rule_revalidation_status = str(rule_revalidation_action.get("revalidation_status") or rule_revalidation_status)
            rule_revalidation_rollback_verified = "Yes" if rule_revalidation_action.get("rollback_verified") else rule_revalidation_rollback_verified
        rule_supersession = getattr(self, "_rule_supersession_workspace", None)
        if isinstance(rule_supersession, dict):
            rule_supersession_old_rule_status = str(rule_supersession.get("old_rule_status") or "none")
            rule_supersession_old_rule_certification = str(rule_supersession.get("old_rule_certification_status") or "none")
            rule_supersession_proposal_status = str(rule_supersession.get("replacement_proposal_status") or "none")
            rule_supersession_mapping_status = str(rule_supersession.get("replacement_mapping_status") or "none")
            rule_supersession_compatibility = str(rule_supersession.get("supersession_compatibility") or "none")
            rule_supersession_scope_change = "required" if "replacement_scope_is_broader" in set(rule_supersession.get("warnings", [])) or "replacement_scope_is_narrower" in set(rule_supersession.get("warnings", [])) else "not_required"
            rule_supersession_review_status = str(rule_supersession.get("review_status") or "pending")
            rule_supersession_new_rule_id = str(rule_supersession.get("candidate_rule_id") or "none")
            rule_supersession_version_chain_id = str(rule_supersession.get("version_chain_id") or "none")
            rule_supersession_receipt_id = str(rule_supersession.get("supersession_receipt_id") or "none")
            rule_supersession_revalidation_status = str(rule_supersession.get("replacement_revalidation_status") or "none")
            rule_supersession_rollback_available = "Yes" if rule_supersession.get("rollback_available") else "No"
            recommended = str(rule_supersession.get("recommended_action") or recommended)
        rule_supersession_action = getattr(self, "_rule_supersession_action", None)
        if isinstance(rule_supersession_action, dict):
            rule_supersession_new_rule_id = str(rule_supersession_action.get("new_rule_id") or rule_supersession_new_rule_id)
            rule_supersession_version_chain_id = str(rule_supersession_action.get("version_chain_id") or rule_supersession_version_chain_id)
            rule_supersession_receipt_id = str(rule_supersession_action.get("supersession_receipt_id") or rule_supersession_receipt_id)
            rule_supersession_revalidation_status = str(rule_supersession_action.get("revalidation_status") or rule_supersession_revalidation_status)
            if rule_supersession_action.get("status") == "rollback_completed":
                rule_supersession_rollback_available = "No"
        rule_effectiveness_workspace = getattr(self, "_rule_effectiveness_workspace", None)
        if isinstance(rule_effectiveness_workspace, dict):
            rule_effectiveness_certification = str(rule_effectiveness_workspace.get("rule_certification_status") or "none")
            rule_effectiveness_dataset_status = str(rule_effectiveness_workspace.get("dataset_status") or "none")
            rule_effectiveness_comparison = str(rule_effectiveness_workspace.get("comparison_rule_id") or "none")
            recommended = str(rule_effectiveness_workspace.get("recommended_action") or recommended)
        rule_effectiveness_analysis = getattr(self, "_rule_effectiveness_analysis", None)
        if isinstance(rule_effectiveness_analysis, dict):
            rule_effectiveness_records_planned = int(rule_effectiveness_analysis.get("records_planned", 0) or 0)
            rule_effectiveness_records_evaluated = int(rule_effectiveness_analysis.get("records_evaluated", 0) or 0)
            rule_effectiveness_matched = int(rule_effectiveness_analysis.get("matched_count", 0) or 0)
            rule_effectiveness_not_matched = int(rule_effectiveness_analysis.get("not_matched_count", 0) or 0)
            rule_effectiveness_errors = int(rule_effectiveness_analysis.get("evaluation_error_count", 0) or 0)
            rule_effectiveness_match_coverage = f"{float(rule_effectiveness_analysis.get('match_coverage')) * 100:.2f}%" if isinstance(rule_effectiveness_analysis.get("match_coverage"), (int, float)) else "null"
            outcome_metrics = rule_effectiveness_analysis.get("outcome_metrics", {}) or {}
            rule_effectiveness_labels = "Yes" if outcome_metrics.get("outcome_metrics_status") != "unavailable" else "No"
            rule_effectiveness_precision = f"{float(outcome_metrics.get('precision')) * 100:.2f}%" if isinstance(outcome_metrics.get("precision"), (int, float)) else "null"
            rule_effectiveness_recall = f"{float(outcome_metrics.get('recall')) * 100:.2f}%" if isinstance(outcome_metrics.get("recall"), (int, float)) else "null"
            rule_effectiveness_specificity = f"{float(outcome_metrics.get('specificity')) * 100:.2f}%" if isinstance(outcome_metrics.get("specificity"), (int, float)) else "null"
            rule_effectiveness_balanced_accuracy = f"{float(outcome_metrics.get('balanced_accuracy')) * 100:.2f}%" if isinstance(outcome_metrics.get("balanced_accuracy"), (int, float)) else "null"
            comparison_metrics = rule_effectiveness_analysis.get("comparison", {}) or {}
            rule_effectiveness_comparison = str(comparison_metrics.get("comparison_rule_id") or rule_effectiveness_comparison)
            rule_effectiveness_disagreement = f"{float(comparison_metrics.get('match_disagreement_rate')) * 100:.2f}%" if isinstance(comparison_metrics.get("match_disagreement_rate"), (int, float)) else "null"
            rule_effectiveness_mutation = "Yes" if rule_effectiveness_analysis.get("persistent_state_mutated") else "No"
        recommendation_workspace = getattr(self, "_rule_effectiveness_recommendation_workspace", None)
        if isinstance(recommendation_workspace, dict):
            rule_effectiveness_recommendation_rule_id = str(recommendation_workspace.get("rule_id") or "none")
            rule_effectiveness_recommendation_analysis_status = str(recommendation_workspace.get("analysis_status") or "none")
            rule_effectiveness_recommendation_policy_status = str(recommendation_workspace.get("policy_status") or "none")
            rule_effectiveness_recommendation_type = str(recommendation_workspace.get("recommendation_type") or rule_effectiveness_recommendation_type)
            rule_effectiveness_recommendation_status = str(recommendation_workspace.get("recommendation_status") or rule_effectiveness_recommendation_status)
            rule_effectiveness_recommendation_triggered = int(recommendation_workspace.get("triggered_condition_count", 0) or 0)
            rule_effectiveness_recommendation_outcome_metrics = "Yes" if recommendation_workspace.get("outcome_metrics_available") else "No"
            rule_effectiveness_recommendation_comparison_available = "Yes" if recommendation_workspace.get("version_comparison_available") else "No"
            rule_effectiveness_recommendation_review_status = str(recommendation_workspace.get("review_status") or rule_effectiveness_recommendation_review_status)
            rule_effectiveness_recommendation_action_type = str(recommendation_workspace.get("action_candidate_type") or rule_effectiveness_recommendation_action_type)
            rule_effectiveness_recommendation_action_status = str(recommendation_workspace.get("action_candidate_status") or rule_effectiveness_recommendation_action_status)
            recommended = str(recommendation_workspace.get("recommended_action") or recommended)
        recommendation = getattr(self, "_rule_effectiveness_recommendation", None)
        if isinstance(recommendation, dict):
            rule_effectiveness_recommendation_rule_id = str(recommendation.get("rule_id") or rule_effectiveness_recommendation_rule_id)
            rule_effectiveness_recommendation_type = str(recommendation.get("recommendation_type") or rule_effectiveness_recommendation_type)
            rule_effectiveness_recommendation_status = str(recommendation.get("status") or recommendation.get("recommendation_status") or rule_effectiveness_recommendation_status)
            rule_effectiveness_recommendation_triggered = len(list(recommendation.get("triggered_conditions", []) or []))
            metrics = recommendation.get("supporting_metrics", {}) or {}
            rule_effectiveness_recommendation_outcome_metrics = "Yes" if metrics.get("outcome_metrics_status") == "available" else rule_effectiveness_recommendation_outcome_metrics
            rule_effectiveness_recommendation_comparison_available = "Yes" if metrics.get("comparison_rule_id") else rule_effectiveness_recommendation_comparison_available
        recommendation_review = getattr(self, "_rule_effectiveness_recommendation_review", None)
        if isinstance(recommendation_review, dict):
            rule_effectiveness_recommendation_review_status = str(recommendation_review.get("review_status") or rule_effectiveness_recommendation_review_status)
        recommendation_action = getattr(self, "_rule_effectiveness_recommendation_action", None)
        if isinstance(recommendation_action, dict):
            rule_effectiveness_recommendation_action_type = str(recommendation_action.get("action_type") or rule_effectiveness_recommendation_action_type)
            rule_effectiveness_recommendation_action_status = str(recommendation_action.get("status") or rule_effectiveness_recommendation_action_status)
        rule_batch_workspace = getattr(self, "_rule_batch_workspace", None)
        if isinstance(rule_batch_workspace, dict):
            rule_batch_document_status = str(rule_batch_workspace.get("document_status") or rule_batch_document_status)
            rule_batch_revision_lock_status = str(rule_batch_workspace.get("revision_lock_status") or rule_batch_revision_lock_status)
            rule_batch_dataset_status = str(rule_batch_workspace.get("dataset_status") or "none")
            rule_batch_policy_status = str(rule_batch_workspace.get("policy_status") or "none")
            rule_batch_selected_rule_count = int(rule_batch_workspace.get("selected_rule_count", 0) or 0)
            rule_batch_eligible_rule_count = int(rule_batch_workspace.get("eligible_rule_count", 0) or 0)
            rule_batch_blocked_rule_count = int(rule_batch_workspace.get("blocked_rule_count", 0) or 0)
            rule_batch_foreign_document_rule_count = int(rule_batch_workspace.get("foreign_document_rule_count", 0) or 0)
            rule_batch_foreign_revision_rule_count = int(rule_batch_workspace.get("foreign_revision_rule_count", 0) or 0)
            recommended = str(rule_batch_workspace.get("recommended_action") or recommended)
        rule_batch_plan = getattr(self, "_rule_batch_plan", None)
        if isinstance(rule_batch_plan, dict):
            rule_batch_total_planned_evaluations = int(rule_batch_plan.get("total_planned_evaluations", 0) or 0)
            rule_batch_blocked_rule_count = sum(1 for item in rule_batch_plan.get("items", []) if item.get("blockers"))
            rule_batch_rules_omitted_by_limit = int(rule_batch_plan.get("rules_omitted_by_limit", 0) or 0)
            rule_batch_foreign_document_rule_count = int(rule_batch_plan.get("foreign_document_rule_count", rule_batch_foreign_document_rule_count) or 0)
            rule_batch_foreign_revision_rule_count = int(rule_batch_plan.get("foreign_revision_rule_count", rule_batch_foreign_revision_rule_count) or 0)
        rule_batch_run = getattr(self, "_rule_batch_run", None)
        if isinstance(rule_batch_run, dict):
            rule_batch_status = str(rule_batch_run.get("status") or rule_batch_status)
            rule_batch_processed_count = int(rule_batch_run.get("processed_count", 0) or 0)
            rule_batch_successful_count = int(rule_batch_run.get("successful_count", 0) or 0)
            rule_batch_failed_count = int(rule_batch_run.get("failed_count", 0) or 0)
            rule_batch_blocked_count = int(rule_batch_run.get("blocked_count", 0) or 0)
            rule_batch_next_item_index = int(rule_batch_run.get("next_item_index", 0) or 0)
            for batch_item in rule_batch_run.get("items", []):
                recommendation_type = str(batch_item.get("recommendation_type") or "")
                if recommendation_type == "continue":
                    rule_batch_continue_count += 1
                elif recommendation_type == "monitor":
                    rule_batch_monitor_count += 1
                elif recommendation_type == "rollback_candidate":
                    rule_batch_rollback_count += 1
                elif recommendation_type == "supersession_review_candidate":
                    rule_batch_supersession_count += 1
                elif recommendation_type == "insufficient_evidence":
                    rule_batch_insufficient_count += 1
        rule_batch_health = getattr(self, "_rule_batch_health", None)
        if isinstance(rule_batch_health, dict) and rule_batch_status == "not_run":
            rule_batch_status = str(rule_batch_health.get("status") or rule_batch_status)
        autonomous_pdf_workspace = getattr(self, "_autonomous_pdf_workspace", None)
        if isinstance(autonomous_pdf_workspace, dict):
            autonomous_pdf_document_status = str(autonomous_pdf_workspace.get("document_status") or autonomous_pdf_document_status)
            autonomous_pdf_native_text_status = str(autonomous_pdf_workspace.get("native_text_status") or autonomous_pdf_native_text_status)
            autonomous_pdf_class = str(autonomous_pdf_workspace.get("document_class") or autonomous_pdf_class)
            autonomous_pdf_readiness = str(autonomous_pdf_workspace.get("autonomous_readiness") or autonomous_pdf_readiness)
            recommended = str(autonomous_pdf_workspace.get("recommended_action") or recommended)
        autonomous_pdf_plan = getattr(self, "_autonomous_pdf_plan", None)
        if isinstance(autonomous_pdf_plan, dict):
            autonomous_pdf_plan_status = "blocked" if autonomous_pdf_plan.get("blockers") else "planned"
        autonomous_pdf_run = getattr(self, "_autonomous_pdf_run", None)
        if isinstance(autonomous_pdf_run, dict):
            autonomous_pdf_run_status = str(autonomous_pdf_run.get("status") or autonomous_pdf_run_status)
            autonomous_pdf_class = str(autonomous_pdf_run.get("document_class") or autonomous_pdf_class)
            autonomous_pdf_native_text_status = str(autonomous_pdf_run.get("native_text_status") or autonomous_pdf_native_text_status)
            autonomous_pdf_certified_rule_count = int(autonomous_pdf_run.get("certified_rule_count", 0) or 0)
            autonomous_pdf_blocked_item_count = int(autonomous_pdf_run.get("blocked_item_count", 0) or 0)
            autonomous_pdf_receipt_id = str(autonomous_pdf_run.get("autonomous_receipt_id") or autonomous_pdf_receipt_id)
        autonomous_pdf_health = getattr(self, "_autonomous_pdf_health", None)
        if isinstance(autonomous_pdf_health, dict) and autonomous_pdf_plan_status == "none":
            autonomous_pdf_plan_status = str(autonomous_pdf_health.get("status") or autonomous_pdf_plan_status)
            recommended = str(autonomous_pdf_health.get("recommended_action") or recommended)
        autonomous_pdf_benchmark_workspace = getattr(self, "_autonomous_pdf_benchmark_workspace", None)
        if isinstance(autonomous_pdf_benchmark_workspace, dict):
            autonomous_pdf_benchmark_manifest_status = str(autonomous_pdf_benchmark_workspace.get("benchmark_manifest_status") or autonomous_pdf_benchmark_manifest_status)
            autonomous_pdf_benchmark_run_status = str(autonomous_pdf_benchmark_workspace.get("autonomous_run_status") or autonomous_pdf_benchmark_run_status)
            autonomous_pdf_benchmark_release_classification = str(autonomous_pdf_benchmark_workspace.get("benchmark_status") or autonomous_pdf_benchmark_release_classification)
            recommended = str(autonomous_pdf_benchmark_workspace.get("recommended_action") or recommended)
        autonomous_pdf_benchmark_validation = getattr(self, "_autonomous_pdf_benchmark_manifest_validation", None)
        if isinstance(autonomous_pdf_benchmark_validation, dict):
            autonomous_pdf_benchmark_manifest_status = str(autonomous_pdf_benchmark_validation.get("status") or autonomous_pdf_benchmark_manifest_status)
        autonomous_pdf_benchmark_result = getattr(self, "_autonomous_pdf_benchmark_result", None)
        if isinstance(autonomous_pdf_benchmark_result, dict):
            autonomous_pdf_benchmark_release_classification = str(autonomous_pdf_benchmark_result.get("release_classification") or autonomous_pdf_benchmark_release_classification)
        benchmark_loaded = None
        if hasattr(self, "autonomous_pdf_benchmark_result_id_var"):
            benchmark_loaded = self.autonomous_pdf_benchmark_result_id_var.get().strip() or None
        from .autonomous_pdf_benchmark import load_autonomous_pdf_benchmark_result
        if benchmark_loaded:
            loaded_benchmark = load_autonomous_pdf_benchmark_result(benchmark_loaded)
            benchmark_payload = loaded_benchmark.get("benchmark_result") if isinstance(loaded_benchmark, dict) else None
            if isinstance(benchmark_payload, dict):
                metrics = benchmark_payload.get("stage_metrics") or {}
                autonomous_pdf_benchmark_release_classification = str(benchmark_payload.get("release_classification") or autonomous_pdf_benchmark_release_classification)
                autonomous_pdf_benchmark_native_text_coverage = f"{(((metrics.get('native_text_page_coverage') or {}).get('value')) or 0) * 100:.2f}%" if ((metrics.get("native_text_page_coverage") or {}).get("value")) is not None else "null"
                autonomous_pdf_benchmark_anchor_recall = f"{(((metrics.get('section_anchor_recall') or {}).get('value')) or 0) * 100:.2f}%" if ((metrics.get("section_anchor_recall") or {}).get("value")) is not None else "null"
                autonomous_pdf_benchmark_citation_precision = f"{(((metrics.get('citation_precision') or {}).get('value')) or 0) * 100:.2f}%" if ((metrics.get("citation_precision") or {}).get("value")) is not None else "null"
                autonomous_pdf_benchmark_citation_recall = f"{(((metrics.get('citation_recall') or {}).get('value')) or 0) * 100:.2f}%" if ((metrics.get("citation_recall") or {}).get("value")) is not None else "null"
                autonomous_pdf_benchmark_proposal_precision = f"{(((metrics.get('proposal_precision') or {}).get('value')) or 0) * 100:.2f}%" if ((metrics.get("proposal_precision") or {}).get("value")) is not None else "null"
                autonomous_pdf_benchmark_proposal_recall = f"{(((metrics.get('proposal_recall') or {}).get('value')) or 0) * 100:.2f}%" if ((metrics.get("proposal_recall") or {}).get("value")) is not None else "null"
                autonomous_pdf_benchmark_rule_precision = f"{(((metrics.get('rule_activation_precision') or {}).get('value')) or 0) * 100:.2f}%" if ((metrics.get("rule_activation_precision") or {}).get("value")) is not None else "null"
                autonomous_pdf_benchmark_certification_correctness = f"{(((metrics.get('certification_correctness') or {}).get('value')) or 0) * 100:.2f}%" if ((metrics.get("certification_correctness") or {}).get("value")) is not None else "null"
                autonomous_pdf_benchmark_safety_count = len(benchmark_payload.get("critical_safety_violations", []) or [])
                autonomous_pdf_benchmark_mismatch_count = len(benchmark_payload.get("mismatches", []) or [])
        autonomous_pdf_benchmark_health = getattr(self, "_autonomous_pdf_benchmark_health", None)
        if isinstance(autonomous_pdf_benchmark_health, dict):
            autonomous_pdf_benchmark_run_status = str(autonomous_pdf_benchmark_health.get("status") or autonomous_pdf_benchmark_run_status)
        selection = getattr(self, "_pdf_viewport_selection", None)
        if isinstance(selection, dict) and selection.get("selection_status") == "selected":
            selected_text = str(selection.get("selected_text") or "")[:80] or "selected"
        text = (
            f"Certification Status: {certification}\n"
            f"Renderer Status: {renderer_status}\n"
            f"Current Page / Page Count: {current_page} / {page_count}\n"
            f"Zoom: {zoom}%\n"
            f"Render Status: {render_status}\n"
            f"Cache Status: {cache_status}\n"
            f"Locator Status: {locator_status}\n"
            f"Text Layer Status: {text_layer_status}\n"
            f"Overlay Status: {overlay_status}\n"
            f"Workspace Status: {workspace_status}\n"
            f"Workspace Revision: {workspace_revision}\n"
            f"Bookmarks: {bookmark_count}\n"
            f"Annotations: {annotation_count}\n"
            f"Citation Drafts: {citation_draft_count}\n"
            f"Review Status: {review_status}\n"
            f"Duplicate Status: {duplicate_status} ({duplicate_count})\n"
            f"Real Citation ID: {real_citation_id}\n"
            f"Handoff Status: {handoff_status}\n"
            f"Handoff Review Status: {handoff_review_status}\n"
            f"Binder Candidate Count: {handoff_candidate_count}\n"
            f"Selected Binder ID: {handoff_selected_binder}\n"
            f"Existing Proposal Count: {handoff_existing_proposals}\n"
            f"Completed Action: {handoff_completed_action}\n"
            f"Binder ID: {handoff_binder_id}\n"
            f"Proposal ID: {handoff_proposal_id}\n"
            f"Revalidation ID: {handoff_revalidation_id}\n"
            f"Promotion Proposal Status: {promotion_proposal_status}\n"
            f"Promotion Citation ID: {promotion_citation_id}\n"
            f"Promotion Citation Provenance: {promotion_citation_provenance}\n"
            f"Promotion Handoff Status: {promotion_handoff_status}\n"
            f"Promotion Duplicate Status: {promotion_duplicate_status}\n"
            f"Promotion Conflict Status: {promotion_conflict_status}\n"
            f"Promotion Review Status: {promotion_review_status}\n"
            f"Promotion Receipt ID: {promotion_receipt_id}\n"
            f"Promotion Revalidation Status: {promotion_revalidation_status}\n"
            f"Rule Activation Proposal Status: {rule_activation_proposal_status}\n"
            f"Rule Activation Promotion Receipt Status: {rule_activation_promotion_receipt_status}\n"
            f"Rule Mapping Status: {rule_activation_mapping_status}\n"
            f"Rule Schema Status: {rule_activation_schema_status}\n"
            f"Rule Duplicate Status: {rule_activation_duplicate_status}\n"
            f"Rule Conflict Status: {rule_activation_conflict_status}\n"
            f"Rule Activation Review Status: {rule_activation_review_status}\n"
            f"Active Rule ID: {rule_activation_active_rule_id}\n"
            f"Rule Activation Receipt ID: {rule_activation_receipt_id}\n"
            f"Rule Activation Revalidation Status: {rule_activation_revalidation_status}\n"
            f"Rollback Available: {rule_activation_rollback_available}\n"
            f"Rule Revalidation Rule ID: {rule_revalidation_rule_id}\n"
            f"Rule Revalidation Rule Status: {rule_revalidation_rule_status}\n"
            f"Rule Revalidation Provenance: {rule_revalidation_provenance}\n"
            f"Rule Revalidation Evaluator Status: {rule_revalidation_evaluator_status}\n"
            f"Rule Revalidation Contract Case Count: {rule_revalidation_contract_case_count}\n"
            f"Rule Revalidation Passed Case Count: {rule_revalidation_passed_case_count}\n"
            f"Rule Revalidation Failed Case Count: {rule_revalidation_failed_case_count}\n"
            f"Rule Revalidation Persistent Mutation Detected: {rule_revalidation_mutation_detected}\n"
            f"Rule Revalidation Review Status: {rule_revalidation_review_status}\n"
            f"Rule Revalidation Certification Receipt ID: {rule_revalidation_receipt_id}\n"
            f"Rule Revalidation Status: {rule_revalidation_status}\n"
            f"Rule Revalidation Rollback Verified: {rule_revalidation_rollback_verified}\n"
            f"Rule Supersession Old Rule Status: {rule_supersession_old_rule_status}\n"
            f"Rule Supersession Old Rule Certification: {rule_supersession_old_rule_certification}\n"
            f"Rule Supersession Proposal Status: {rule_supersession_proposal_status}\n"
            f"Rule Supersession Mapping Status: {rule_supersession_mapping_status}\n"
            f"Rule Supersession Compatibility: {rule_supersession_compatibility}\n"
            f"Rule Supersession Scope Change: {rule_supersession_scope_change}\n"
            f"Rule Supersession Review Status: {rule_supersession_review_status}\n"
            f"Rule Supersession New Rule ID: {rule_supersession_new_rule_id}\n"
            f"Rule Supersession Version Chain ID: {rule_supersession_version_chain_id}\n"
            f"Rule Supersession Receipt ID: {rule_supersession_receipt_id}\n"
            f"Rule Supersession Revalidation Status: {rule_supersession_revalidation_status}\n"
            f"Rule Supersession Rollback Available: {rule_supersession_rollback_available}\n"
            f"Rule Effectiveness Certification Status: {rule_effectiveness_certification}\n"
            f"Rule Effectiveness Dataset Status: {rule_effectiveness_dataset_status}\n"
            f"Rule Effectiveness Records Planned: {rule_effectiveness_records_planned}\n"
            f"Rule Effectiveness Records Evaluated: {rule_effectiveness_records_evaluated}\n"
            f"Rule Effectiveness Matched Count: {rule_effectiveness_matched}\n"
            f"Rule Effectiveness Not-Matched Count: {rule_effectiveness_not_matched}\n"
            f"Rule Effectiveness Error Count: {rule_effectiveness_errors}\n"
            f"Rule Effectiveness Match Coverage: {rule_effectiveness_match_coverage}\n"
            f"Rule Effectiveness Outcome Labels Available: {rule_effectiveness_labels}\n"
            f"Rule Effectiveness Precision: {rule_effectiveness_precision}\n"
            f"Rule Effectiveness Recall: {rule_effectiveness_recall}\n"
            f"Rule Effectiveness Specificity: {rule_effectiveness_specificity}\n"
            f"Rule Effectiveness Balanced Accuracy: {rule_effectiveness_balanced_accuracy}\n"
            f"Rule Effectiveness Comparison Rule ID: {rule_effectiveness_comparison}\n"
            f"Rule Effectiveness Disagreement Rate: {rule_effectiveness_disagreement}\n"
            f"Rule Effectiveness Persistent Mutation Detected: {rule_effectiveness_mutation}\n"
            f"Rule Effectiveness Recommendation Rule ID: {rule_effectiveness_recommendation_rule_id}\n"
            f"Rule Effectiveness Recommendation Analysis Status: {rule_effectiveness_recommendation_analysis_status}\n"
            f"Rule Effectiveness Recommendation Policy Status: {rule_effectiveness_recommendation_policy_status}\n"
            f"Rule Effectiveness Recommendation Type: {rule_effectiveness_recommendation_type}\n"
            f"Rule Effectiveness Recommendation Status: {rule_effectiveness_recommendation_status}\n"
            f"Rule Effectiveness Recommendation Triggered Condition Count: {rule_effectiveness_recommendation_triggered}\n"
            f"Rule Effectiveness Recommendation Outcome Metrics Available: {rule_effectiveness_recommendation_outcome_metrics}\n"
            f"Rule Effectiveness Recommendation Version Comparison Available: {rule_effectiveness_recommendation_comparison_available}\n"
            f"Rule Effectiveness Recommendation Review Status: {rule_effectiveness_recommendation_review_status}\n"
            f"Rule Effectiveness Recommendation Action Candidate Type: {rule_effectiveness_recommendation_action_type}\n"
            f"Rule Effectiveness Recommendation Action Candidate Status: {rule_effectiveness_recommendation_action_status}\n"
            f"Rule Effectiveness Recommendation Automatic Action Performed: No\n"
            f"Rule Batch Dataset Status: {rule_batch_dataset_status}\n"
            f"Rule Batch Policy Status: {rule_batch_policy_status}\n"
            f"Rule Batch Document Status: {rule_batch_document_status}\n"
            f"Rule Batch Revision Lock Status: {rule_batch_revision_lock_status}\n"
            f"Rule Batch Selected Rule Count: {rule_batch_selected_rule_count}\n"
            f"Rule Batch Eligible Rule Count: {rule_batch_eligible_rule_count}\n"
            f"Rule Batch Blocked Rule Count: {rule_batch_blocked_rule_count}\n"
            f"Rule Batch Rules Omitted by Limit: {rule_batch_rules_omitted_by_limit}\n"
            f"Rule Batch Foreign-Document Rule Count: {rule_batch_foreign_document_rule_count}\n"
            f"Rule Batch Foreign-Revision Rule Count: {rule_batch_foreign_revision_rule_count}\n"
            f"Rule Batch Total Planned Evaluations: {rule_batch_total_planned_evaluations}\n"
            f"Rule Batch Status: {rule_batch_status}\n"
            f"Rule Batch Processed Count: {rule_batch_processed_count}\n"
            f"Rule Batch Successful Count: {rule_batch_successful_count}\n"
            f"Rule Batch Failed Count: {rule_batch_failed_count}\n"
            f"Rule Batch Blocked Count: {rule_batch_blocked_count}\n"
            f"Rule Batch Next Item Index: {rule_batch_next_item_index}\n"
            f"Rule Batch Continue Recommendation Count: {rule_batch_continue_count}\n"
            f"Rule Batch Monitor Recommendation Count: {rule_batch_monitor_count}\n"
            f"Rule Batch Rollback-Candidate Count: {rule_batch_rollback_count}\n"
            f"Rule Batch Supersession-Candidate Count: {rule_batch_supersession_count}\n"
            f"Rule Batch Insufficient-Evidence Count: {rule_batch_insufficient_count}\n"
            f"Autonomous PDF Document Status: {autonomous_pdf_document_status}\n"
            f"Autonomous PDF Native Text Status: {autonomous_pdf_native_text_status}\n"
            f"Autonomous PDF Class: {autonomous_pdf_class}\n"
            f"Autonomous PDF Readiness: {autonomous_pdf_readiness}\n"
            f"Autonomous PDF Plan Status: {autonomous_pdf_plan_status}\n"
            f"Autonomous PDF Run Status: {autonomous_pdf_run_status}\n"
            f"Autonomous PDF Certified Rule Count: {autonomous_pdf_certified_rule_count}\n"
            f"Autonomous PDF Blocked Item Count: {autonomous_pdf_blocked_item_count}\n"
            f"Autonomous PDF Receipt ID: {autonomous_pdf_receipt_id}\n"
            f"Autonomous PDF Benchmark Manifest Status: {autonomous_pdf_benchmark_manifest_status}\n"
            f"Autonomous PDF Benchmark Run Status: {autonomous_pdf_benchmark_run_status}\n"
            f"Autonomous PDF Benchmark Release Classification: {autonomous_pdf_benchmark_release_classification}\n"
            f"Autonomous PDF Benchmark Native-Text Coverage: {autonomous_pdf_benchmark_native_text_coverage}\n"
            f"Autonomous PDF Benchmark Section-Anchor Recall: {autonomous_pdf_benchmark_anchor_recall}\n"
            f"Autonomous PDF Benchmark Citation Precision: {autonomous_pdf_benchmark_citation_precision}\n"
            f"Autonomous PDF Benchmark Citation Recall: {autonomous_pdf_benchmark_citation_recall}\n"
            f"Autonomous PDF Benchmark Proposal Precision: {autonomous_pdf_benchmark_proposal_precision}\n"
            f"Autonomous PDF Benchmark Proposal Recall: {autonomous_pdf_benchmark_proposal_recall}\n"
            f"Autonomous PDF Benchmark Rule-Activation Precision: {autonomous_pdf_benchmark_rule_precision}\n"
            f"Autonomous PDF Benchmark Certification Correctness: {autonomous_pdf_benchmark_certification_correctness}\n"
            f"Autonomous PDF Benchmark Critical Safety Violation Count: {autonomous_pdf_benchmark_safety_count}\n"
            f"Autonomous PDF Benchmark Mismatch Count: {autonomous_pdf_benchmark_mismatch_count}\n"
            f"Selected Text: {selected_text}\n"
            f"Recommended Action: {recommended}"
        )
        if hasattr(self, "pdf_viewport_status_var"):
            self.pdf_viewport_status_var.set(text)

    def _show_pdf_viewport_image(self, render: dict[str, object] | None) -> None:
        if not isinstance(render, dict):
            return
        cache_path = str(render.get("cache_path") or "")
        if not cache_path or not os.path.exists(cache_path):
            return
        self._pdf_viewport_last_render = render
        if not hasattr(self, "_pdf_viewport_window") or self._pdf_viewport_window is None or not self._pdf_viewport_window.winfo_exists():
            self._pdf_viewport_window = tk.Toplevel(self)
            self._pdf_viewport_window.title("Controlled PDF Viewport")
            self._pdf_viewport_canvas = tk.Canvas(self._pdf_viewport_window, bg=PALETTE["panel_alt"], highlightthickness=0)
            self._pdf_viewport_canvas.pack(fill=tk.BOTH, expand=True)
            self._pdf_viewport_canvas.bind("<ButtonPress-1>", self._on_pdf_viewport_selection_press)
            self._pdf_viewport_canvas.bind("<B1-Motion>", self._on_pdf_viewport_selection_drag)
            self._pdf_viewport_canvas.bind("<ButtonRelease-1>", self._on_pdf_viewport_selection_release)
        image = tk.PhotoImage(file=cache_path)
        self._pdf_viewport_photo = image
        if hasattr(self, "pdf_viewport_id_var"):
            self._reload_pdf_reader_workspace_overlay(self.pdf_viewport_id_var.get().strip())
        self._pdf_viewport_canvas.delete("all")
        self._pdf_viewport_canvas.configure(width=image.width(), height=image.height(), scrollregion=(0, 0, image.width(), image.height()))
        self._pdf_viewport_canvas.create_image(0, 0, image=image, anchor="nw", tags=("viewport_image",))
        self._draw_pdf_viewport_overlay(getattr(self, "_pdf_viewport_overlay", None))
        self._draw_pdf_reader_workspace_overlay(getattr(self, "_pdf_reader_workspace_overlay", None))

    def _clear_pdf_viewport_overlay_state(self) -> None:
        self._pdf_viewport_overlay = None
        self._pdf_viewport_selection = None
        self._pdf_viewport_text_layer = None
        self._pdf_viewport_selection_start = None

    def _draw_pdf_viewport_overlay(self, overlay: dict[str, object] | None) -> None:
        canvas = getattr(self, "_pdf_viewport_canvas", None)
        if canvas is None:
            return
        canvas.delete("viewport_overlay")
        if not isinstance(overlay, dict):
            return
        colors = {"search": "#f6d743", "citation": "#4fb0c6", "selected_locator": "#ff7a59"}
        color = colors.get(str(overlay.get("overlay_type") or ""), "#f6d743")
        for rectangle in overlay.get("rectangles", []):
            if not isinstance(rectangle, dict):
                continue
            bbox = rectangle.get("image_bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            canvas.create_rectangle(bbox[0], bbox[1], bbox[2], bbox[3], outline=color, width=2, tags=("viewport_overlay",))

    def _draw_pdf_reader_workspace_overlay(self, overlay: dict[str, object] | None) -> None:
        canvas = getattr(self, "_pdf_viewport_canvas", None)
        if canvas is None:
            return
        canvas.delete("workspace_overlay")
        if not isinstance(overlay, dict):
            return
        for rectangle in overlay.get("rectangles", []):
            if not isinstance(rectangle, dict):
                continue
            bbox = rectangle.get("image_bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                continue
            canvas.create_rectangle(bbox[0], bbox[1], bbox[2], bbox[3], outline="#7dd3fc", width=2, tags=("workspace_overlay",))

    def _reload_pdf_reader_workspace_overlay(self, viewport_id: str) -> None:
        workspace_id = self.pdf_reader_workspace_id_var.get().strip() if hasattr(self, "pdf_reader_workspace_id_var") else ""
        if not workspace_id or not viewport_id:
            self._pdf_reader_workspace_overlay = None
            return
        loaded = load_pdf_reader_workspace(workspace_id)
        if isinstance(loaded.get("workspace"), dict):
            self._pdf_reader_workspace = loaded["workspace"]
        overlay = build_pdf_reader_workspace_overlay(workspace_id, viewport_id)
        self._pdf_reader_workspace_overlay = overlay if isinstance(overlay, dict) else None
        self._draw_pdf_reader_workspace_overlay(self._pdf_reader_workspace_overlay)

    def _on_pdf_viewport_selection_press(self, event: tk.Event) -> None:
        canvas = getattr(self, "_pdf_viewport_canvas", None)
        if canvas is None:
            return
        self._pdf_viewport_selection_start = (float(event.x), float(event.y))
        canvas.delete("viewport_selection")

    def _on_pdf_viewport_selection_drag(self, event: tk.Event) -> None:
        canvas = getattr(self, "_pdf_viewport_canvas", None)
        start = getattr(self, "_pdf_viewport_selection_start", None)
        if canvas is None or start is None:
            return
        canvas.delete("viewport_selection")
        canvas.create_rectangle(start[0], start[1], event.x, event.y, outline="#ffffff", dash=(4, 2), width=2, tags=("viewport_selection",))

    def _on_pdf_viewport_selection_release(self, event: tk.Event) -> None:
        canvas = getattr(self, "_pdf_viewport_canvas", None)
        start = getattr(self, "_pdf_viewport_selection_start", None)
        viewport_id = self.pdf_viewport_id_var.get().strip() if hasattr(self, "pdf_viewport_id_var") else ""
        if canvas is None or start is None or not viewport_id:
            return
        bbox = [start[0], start[1], float(event.x), float(event.y)]
        left, top, right, bottom = min(bbox[0], bbox[2]), min(bbox[1], bbox[3]), max(bbox[0], bbox[2]), max(bbox[1], bbox[3])
        result = select_pdf_text_in_rectangle(viewport_id, [left, top, right, bottom], selection_mode=self.pdf_viewport_selection_mode_var.get().strip() or "intersect")
        self._pdf_viewport_selection = result
        self._set_pdf_viewport_status(viewport=getattr(self, "_pdf_viewport_text_layer", {}).get("text_layer"), render=getattr(self, "_pdf_viewport_last_render", None))
        self.status_var.set(f"PDF selection: {result.get('selection_status', 'unknown')}.")

    def _run_topic_taxonomy_action(self, action: str) -> None:
        try:
            if action == "save":
                result = save_controlled_topic(
                    self.topic_taxonomy_preferred_label_var.get().strip(),
                    aliases=self._split_csv_values(self.topic_taxonomy_aliases_var.get()),
                    parent_topic_ids=self._split_csv_values(self.topic_taxonomy_parent_ids_var.get()),
                    related_topic_ids=self._split_csv_values(self.topic_taxonomy_related_ids_var.get()),
                    status=self.topic_taxonomy_status_field_var.get().strip() or "active",
                    replacement_topic_id=self.topic_taxonomy_replacement_id_var.get().strip() or None,
                )
                if result.get("topic"):
                    self._set_topic_taxonomy_status(result["topic"], validation=validate_topic_taxonomy(), resolution=None, expansion=None)
                self.status_var.set(f"Topic taxonomy save: {result.get('status')}.")
            elif action == "resolve":
                resolution = resolve_controlled_topic_label(self.topic_taxonomy_resolve_label_var.get().strip())
                validation = validate_topic_taxonomy()
                topic = load_controlled_topic(str(resolution.get("topic_id") or "")).get("topic") if resolution.get("topic_id") else None
                self._set_topic_taxonomy_status(topic if isinstance(topic, dict) else None, validation=validation, resolution=resolution, expansion=None)
                self.status_var.set(f"Topic resolution: {resolution.get('resolution_type')}.")
            elif action == "expand":
                expansion = build_taxonomy_search_expansion(
                    self.topic_taxonomy_resolve_label_var.get().strip(),
                    include_aliases=bool(self.topic_taxonomy_include_aliases_var.get()),
                    include_parents=bool(self.topic_taxonomy_include_parents_var.get()),
                    include_children=bool(self.topic_taxonomy_include_children_var.get()),
                    include_related=bool(self.topic_taxonomy_include_related_var.get()),
                )
                resolution = resolve_controlled_topic_label(self.topic_taxonomy_resolve_label_var.get().strip(), include_deprecated=True)
                topic = load_controlled_topic(str(resolution.get("topic_id") or "")).get("topic") if resolution.get("topic_id") else None
                self._set_topic_taxonomy_status(topic if isinstance(topic, dict) else None, validation=validate_topic_taxonomy(), resolution=resolution, expansion=expansion)
                self.status_var.set(f"Topic expansion labels: {len(expansion.get('search_labels', []))}.")
            elif action == "health":
                validation = validate_topic_taxonomy()
                self._set_topic_taxonomy_status(None, validation=validation, resolution=None, expansion=None)
                self.status_var.set(f"Topic taxonomy health: {validation.get('status')}.")
            elif action == "copy":
                text = format_topic_taxonomy_report(public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                self._set_topic_taxonomy_status(None, validation=validate_topic_taxonomy(), resolution=None, expansion=None)
                self.status_var.set("Public-safe taxonomy report copied.")
        except Exception as exc:
            self.status_var.set(f"Topic taxonomy action failed: {exc}")

    def _set_topic_taxonomy_status(
        self,
        topic: dict[str, object] | None,
        *,
        validation: dict[str, object] | None,
        resolution: dict[str, object] | None,
        expansion: dict[str, object] | None,
    ) -> None:
        issue_count = len(validation.get("issues", [])) if isinstance((validation or {}).get("issues"), list) else 0
        recommended = "No action required."
        if isinstance(validation, dict) and validation.get("issues"):
            recommended = str(validation["issues"][0].get("recommended_action") or recommended)
        text = (
            f"Topic ID: {(topic or {}).get('topic_id', 'unknown')}\n"
            f"Preferred Label: {(topic or {}).get('preferred_label', 'unknown')}\n"
            f"Status: {(topic or {}).get('status', 'unknown')}\n"
            f"Alias Count: {len((topic or {}).get('aliases', [])) if isinstance((topic or {}).get('aliases'), list) else 0}\n"
            f"Parent Count: {len((topic or {}).get('parent_topic_ids', [])) if isinstance((topic or {}).get('parent_topic_ids'), list) else 0}\n"
            f"Child Count: {len((topic or {}).get('child_topic_ids', [])) if isinstance((topic or {}).get('child_topic_ids'), list) else 0}\n"
            f"Related Count: {len((topic or {}).get('related_topic_ids', [])) if isinstance((topic or {}).get('related_topic_ids'), list) else 0}\n"
            f"Resolved: {resolution.get('resolved', 'unknown') if isinstance(resolution, dict) else 'unknown'}\n"
            f"Resolution Type: {resolution.get('resolution_type', 'unknown') if isinstance(resolution, dict) else 'unknown'}\n"
            f"Expansion Label Count: {len(expansion.get('search_labels', [])) if isinstance((expansion or {}).get('search_labels'), list) else 0}\n"
            f"Taxonomy Status: {(validation or {}).get('status', 'unknown')}\n"
            f"Validation Issue Count: {issue_count}\n"
            f"Recommended Action: {recommended}"
        )
        if hasattr(self, "topic_taxonomy_status_var"):
            self.topic_taxonomy_status_var.set(text)

    def _split_csv_values(self, raw: str) -> list[str]:
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _run_taxonomy_topic_search_action(self, action: str) -> None:
        query = self.taxonomy_topic_search_query_var.get().strip() if hasattr(self, "taxonomy_topic_search_query_var") else ""
        options = {
            "limit": self._parse_int_text(self.taxonomy_topic_search_limit_var.get(), 50) if hasattr(self, "taxonomy_topic_search_limit_var") else 50,
            "include_aliases": bool(self.taxonomy_topic_search_include_aliases_var.get()) if hasattr(self, "taxonomy_topic_search_include_aliases_var") else True,
            "include_parents": bool(self.taxonomy_topic_search_include_parents_var.get()) if hasattr(self, "taxonomy_topic_search_include_parents_var") else False,
            "include_children": bool(self.taxonomy_topic_search_include_children_var.get()) if hasattr(self, "taxonomy_topic_search_include_children_var") else False,
            "include_related": bool(self.taxonomy_topic_search_include_related_var.get()) if hasattr(self, "taxonomy_topic_search_include_related_var") else False,
            "include_replacement": bool(self.taxonomy_topic_search_include_replacement_var.get()) if hasattr(self, "taxonomy_topic_search_include_replacement_var") else True,
            "include_warning_documents": bool(self.taxonomy_topic_search_include_warning_docs_var.get()) if hasattr(self, "taxonomy_topic_search_include_warning_docs_var") else True,
        }
        try:
            if action == "resolve":
                resolution = resolve_taxonomy_search_query(query)
                self._set_taxonomy_topic_search_status(get_taxonomy_topic_search_summary(query, **options))
                self.status_var.set(f"Taxonomy search resolution: {resolution.get('resolution_type')}.")
            elif action == "plan":
                plan = build_taxonomy_topic_search_plan(query, **{key: value for key, value in options.items() if key != "limit" and key != "include_warning_documents"})
                self._set_taxonomy_topic_search_status(get_taxonomy_topic_search_summary(query, **options))
                self.status_var.set(f"Taxonomy search plan labels: {len(plan.get('search_labels', []))}.")
            elif action == "search":
                result = search_taxonomy_aware_topic_content(query, **options)
                self._set_taxonomy_topic_search_status(get_taxonomy_topic_search_summary(query, **options))
                self.status_var.set(f"Taxonomy search: {result.get('status')}.")
            elif action == "health":
                health = get_taxonomy_topic_search_health()
                self._set_taxonomy_topic_search_status(get_taxonomy_topic_search_summary(query, **options) if query else {
                    "input_query": query or "unknown",
                    "resolved_topic_id": "unknown",
                    "preferred_label": "unknown",
                    "resolution_type": "unknown",
                    "expansion_label_count": 0,
                    "documents_matched": 0,
                    "structural_match_count": 0,
                    "direct_match_count": 0,
                    "expanded_match_count": 0,
                    "topic_index_status": health.get("topic_index_status", "unknown"),
                    "taxonomy_status": health.get("taxonomy_status", "unknown"),
                    "search_health": health.get("status", "unknown"),
                    "recommended_action": health.get("recommended_action"),
                    "status": health.get("status"),
                })
                self.status_var.set(f"Taxonomy search health: {health.get('status')}.")
            elif action == "copy":
                text = format_taxonomy_topic_search_report(query, public_safe=True, **options)
                self.clipboard_clear()
                self.clipboard_append(text)
                self._set_taxonomy_topic_search_status(get_taxonomy_topic_search_summary(query, **options))
                self.status_var.set("Public-safe taxonomy-aware search report copied.")
        except Exception as exc:
            self.status_var.set(f"Taxonomy-aware topic search failed: {exc}")

    def _set_taxonomy_topic_search_status(self, summary: dict[str, object]) -> None:
        text = (
            f"Input Query: {summary.get('input_query', 'unknown')}\n"
            f"Resolved Topic ID: {summary.get('resolved_topic_id', 'unknown')}\n"
            f"Preferred Label: {summary.get('preferred_label', 'unknown')}\n"
            f"Resolution Type: {summary.get('resolution_type', 'unknown')}\n"
            f"Expansion Label Count: {summary.get('expansion_label_count', 0)}\n"
            f"Documents Matched: {summary.get('documents_matched', 0)}\n"
            f"Structural Match Count: {summary.get('structural_match_count', 0)}\n"
            f"Direct Match Count: {summary.get('direct_match_count', 0)}\n"
            f"Expanded Match Count: {summary.get('expanded_match_count', 0)}\n"
            f"Topic Index Status: {summary.get('topic_index_status', 'unknown')}\n"
            f"Taxonomy Status: {summary.get('taxonomy_status', 'unknown')}\n"
            f"Search Health: {summary.get('search_health', 'unknown')}\n"
            f"Recommended Action: {summary.get('recommended_action', 'Unknown')}"
        )
        if hasattr(self, "taxonomy_topic_search_status_var"):
            self.taxonomy_topic_search_status_var.set(text)

    def _run_locator_migration_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        plan_id = self.locator_migration_plan_id_var.get().strip() if hasattr(self, "locator_migration_plan_id_var") else ""
        proposal_id = self.locator_migration_proposal_id_var.get().strip() if hasattr(self, "locator_migration_proposal_id_var") else ""
        try:
            if action == "audit":
                audit = audit_document_locator_contracts(document_id)
                self._set_locator_migration_status(document_id, audit=audit, plan=None, preview=None, health=None)
                self.status_var.set(f"Locator audit: {audit.get('records_checked', 0)} record(s).")
            elif action == "build":
                result = build_locator_migration_plan(document_id, scope=self.locator_migration_scope_var.get().strip() or "all")
                if result.get("migration_plan_id"):
                    self.locator_migration_plan_id_var.set(str(result.get("migration_plan_id") or ""))
                self._set_locator_migration_status(document_id, audit=(result.get("plan") or {}).get("audit"), plan=result.get("plan"), preview=None, health=None)
                self.status_var.set(f"Locator migration plan: {result.get('status')}.")
            elif action == "load":
                loaded = load_locator_migration_plan(plan_id)
                self._set_locator_migration_status(document_id, audit=(loaded.get("plan") or {}).get("audit"), plan=loaded.get("plan"), preview=None, health=None)
                self.status_var.set(f"Locator migration plan load: {loaded.get('status')}.")
            elif action == "preview":
                preview = preview_locator_correction(plan_id, proposal_id)
                loaded = load_locator_migration_plan(plan_id)
                self._set_locator_migration_status(document_id, audit=(loaded.get("plan") or {}).get("audit"), plan=loaded.get("plan"), preview=preview, health=None)
                self.status_var.set(f"Locator proposal preview: {preview.get('classification', preview.get('status', 'unknown'))}.")
            elif action == "health":
                health = get_locator_migration_health(document_id)
                latest = load_locator_migration_plan(plan_id) if plan_id else {"plan": None}
                self._set_locator_migration_status(document_id, audit=(latest.get("plan") or {}).get("audit"), plan=latest.get("plan"), preview=None, health=health)
                self.status_var.set(f"Locator migration health: {health.get('status')}.")
            elif action == "copy":
                text = format_locator_migration_report(document_id=document_id, migration_plan_id=plan_id or None, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                latest = load_locator_migration_plan(plan_id) if plan_id else {"plan": None}
                self._set_locator_migration_status(document_id, audit=(latest.get("plan") or {}).get("audit"), plan=latest.get("plan"), preview=None, health=get_locator_migration_health(document_id))
                self.status_var.set("Public-safe locator migration report copied.")
        except Exception as exc:
            self.status_var.set(f"Locator migration action failed: {exc}")

    def _set_locator_migration_status(
        self,
        document_id: str,
        *,
        audit: dict[str, object] | None,
        plan: dict[str, object] | None,
        preview: dict[str, object] | None,
        health: dict[str, object] | None,
    ) -> None:
        dependency = (plan or {}).get("dependency_summary", {}) if isinstance((plan or {}).get("dependency_summary"), dict) else {}
        stale = "yes" if isinstance(plan, dict) and load_locator_migration_plan(str(plan.get("migration_plan_id") or "")).get("status") == "stale" else "no"
        text = (
            f"Document ID: {document_id}\n"
            f"Current Source Revision: {(plan or {}).get('source_revision', (audit or {}).get('current_source_revision', 'unknown'))}\n"
            f"Plan Status: {(health or {}).get('status', (plan or {}).get('status', 'unknown'))}\n"
            f"Records Checked: {(audit or {}).get('records_checked', 0)}\n"
            f"Valid Locator Count: {(audit or {}).get('valid_count', 0)}\n"
            f"Stale Locator Count: {(audit or {}).get('stale_count', 0)}\n"
            f"Safe Candidate Count: {(plan or {}).get('safe_candidate_count', 0)}\n"
            f"Manual Review Count: {(plan or {}).get('manual_review_count', 0)}\n"
            f"Blocked Count: {(plan or {}).get('blocked_count', 0)}\n"
            f"Affected Proposal Count: {dependency.get('proposal_count', 0)}\n"
            f"Affected Evidence Binder Count: {dependency.get('evidence_binder_count', 0)}\n"
            f"Selected Proposal Classification: {(preview or {}).get('classification', self.locator_migration_classification_var.get().strip() if hasattr(self, 'locator_migration_classification_var') else 'unknown') or 'unknown'}\n"
            f"Plan Fingerprint Current: {stale}\n"
            f"Recommended Action: {(health or {}).get('recommended_action', 'Review the migration plan.')}"
        )
        if hasattr(self, "locator_migration_status_var"):
            self.locator_migration_status_var.set(text)

    def _run_locator_migration_execution_action(self, action: str) -> None:
        document_id = self._current_source_document_id()
        if not document_id:
            self.status_var.set("No source selected. Register a PDF source first.")
            return
        plan_id = self.locator_execution_plan_id_var.get().strip() if hasattr(self, "locator_execution_plan_id_var") else ""
        proposal_id = self.locator_execution_proposal_id_var.get().strip() if hasattr(self, "locator_execution_proposal_id_var") else ""
        execution_id = self.locator_execution_id_var.get().strip() if hasattr(self, "locator_execution_id_var") else ""
        dry_run = bool(self.locator_execution_dry_run_var.get()) if hasattr(self, "locator_execution_dry_run_var") else True
        confirmation = self.locator_execution_confirmation_var.get().strip() if hasattr(self, "locator_execution_confirmation_var") else ""
        try:
            if action == "validate":
                validation = validate_locator_migration_execution(plan_id, proposal_id, dry_run=dry_run, confirmation=confirmation)
                result = execute_locator_migration_proposal(plan_id, proposal_id, dry_run=True)
                if result.get("execution_id"):
                    self.locator_execution_id_var.set(str(result.get("execution_id") or ""))
                self._set_locator_migration_execution_status(validation=validation, result=result, health=None, receipt=None)
                self.status_var.set(f"Locator execution validation: {'valid' if validation.get('valid') else 'blocked'}.")
            elif action == "execute":
                result = execute_locator_migration_proposal(plan_id, proposal_id, dry_run=dry_run, confirmation=confirmation)
                if result.get("execution_id"):
                    self.locator_execution_id_var.set(str(result.get("execution_id") or ""))
                receipt = load_locator_migration_execution_receipt(str(result.get("execution_id") or "")) if result.get("execution_id") else {"receipt": None}
                self._set_locator_migration_execution_status(validation=None, result=result, health=None, receipt=receipt.get("receipt"))
                self.status_var.set(f"Locator execution: {result.get('status')}.")
            elif action == "load":
                loaded = load_locator_migration_execution_receipt(execution_id)
                self._set_locator_migration_execution_status(validation=None, result=None, health=None, receipt=loaded.get("receipt"))
                self.status_var.set(f"Locator receipt load: {loaded.get('status')}.")
            elif action == "rollback":
                result = rollback_locator_migration_execution(execution_id, confirmation=confirmation)
                loaded = load_locator_migration_execution_receipt(execution_id)
                self._set_locator_migration_execution_status(validation=None, result=result, health=None, receipt=loaded.get("receipt"))
                self.status_var.set(f"Locator rollback: {result.get('status')}.")
            elif action == "health":
                health = get_locator_migration_execution_health(document_id)
                self._set_locator_migration_execution_status(validation=None, result=None, health=health, receipt=None)
                self.status_var.set(f"Locator execution health: {health.get('status')}.")
            elif action == "copy":
                text = format_locator_migration_execution_report(execution_id=execution_id or None, document_id=document_id, public_safe=True)
                self.clipboard_clear()
                self.clipboard_append(text)
                health = get_locator_migration_execution_health(document_id)
                loaded = load_locator_migration_execution_receipt(execution_id) if execution_id else {"receipt": None}
                self._set_locator_migration_execution_status(validation=None, result=None, health=health, receipt=loaded.get("receipt"))
                self.status_var.set("Public-safe locator execution report copied.")
        except Exception as exc:
            self.status_var.set(f"Locator execution action failed: {exc}")

    def _set_locator_migration_execution_status(
        self,
        *,
        validation: dict[str, object] | None,
        result: dict[str, object] | None,
        health: dict[str, object] | None,
        receipt: dict[str, object] | None,
    ) -> None:
        write_set_count = 0
        if isinstance(result, dict) and isinstance(result.get("write_set"), dict):
            write_set_count = len(result["write_set"].get("record_updates", []))
        recommended = "Validate one safe proposal before execution."
        if isinstance(health, dict):
            recommended = str(health.get("recommended_action") or recommended)
        elif isinstance(result, dict) and result.get("status") == "completed":
            recommended = "Review the pending revalidation item."
        text = (
            f"Validation Status: {('valid' if validation and validation.get('valid') else 'unknown') if validation is not None else 'unknown'}\n"
            f"Proposal Classification: {(validation or {}).get('proposal_classification', (receipt or {}).get('proposal_classification', 'unknown'))}\n"
            f"Before-State Current: {(validation or {}).get('before_state_current', 'unknown')}\n"
            f"Target Current: {(validation or {}).get('target_current', 'unknown')}\n"
            f"Write-Set Record Count: {write_set_count}\n"
            f"Execution Status: {(result or {}).get('status', (receipt or {}).get('status', (health or {}).get('status', 'unknown')))}\n"
            f"Records Updated: {(result or {}).get('records_updated', len((receipt or {}).get('updated_record_ids', [])) if isinstance((receipt or {}).get('updated_record_ids'), list) else 0)}\n"
            f"Revalidation Records Created: {(result or {}).get('revalidation_records_created', 1 if (receipt or {}).get('revalidation_queue_item_id') else 0)}\n"
            f"Post-Write Provenance: {(result or {}).get('post_write_provenance_status', (receipt or {}).get('post_write_provenance_status', 'unknown'))}\n"
            f"Rollback Available: {'yes' if ((result or {}).get('rollback_available') or (receipt or {}).get('rollback_available')) else 'no'}\n"
            f"Rollback Verified: {'yes' if ((result or {}).get('rollback_verified') or (receipt or {}).get('rollback_verified')) else 'no'}\n"
            f"Recommended Action: {recommended}"
        )
        if hasattr(self, "locator_execution_status_var"):
            self.locator_execution_status_var.set(text)

    def _set_document_curation_integrity_status(self, scan: dict[str, object]) -> None:
        counts = scan.get("severity_counts", {}) if isinstance(scan.get("severity_counts"), dict) else {}
        issues = scan.get("issues", []) if isinstance(scan.get("issues"), list) else []
        recoverable = len([item for item in issues if isinstance(item, dict) and item.get("recoverability") == "recoverable"])
        manual_review = len([item for item in issues if isinstance(item, dict) and item.get("recoverability") == "manual_review_required"])
        conflicts = len([item for item in issues if isinstance(item, dict) and item.get("severity") == "critical"])
        summary = get_document_content_curation_summary(scan.get("document_id")) if scan.get("document_id") else {}
        revision = summary.get("curation_revision", 0)
        text = (
            f"Critical: {counts.get('critical', 0)}\n"
            f"High: {counts.get('high', 0)}\n"
            f"Recoverable: {recoverable}\n"
            f"Manual Review: {manual_review}\n"
            f"Conflicts: {conflicts}\n"
            f"Pending Transactions: {len([item for item in issues if isinstance(item, dict) and str(item.get('issue_type') or '').startswith('transaction_')])}\n"
            f"Recovery Status: {scan.get('status', 'unknown')}\n"
            f"Last Reconciled Revision: {revision}"
        )
        if hasattr(self, "document_curation_integrity_status_var"):
            self.document_curation_integrity_status_var.set(text)

    def _corpus_batch_id(self) -> str:
        return str(self.corpus_execution_batch_id_var.get()).strip() if hasattr(self, "corpus_execution_batch_id_var") else ""

    def _corpus_repair_id(self) -> str:
        return str(self.corpus_execution_repair_id_var.get()).strip() if hasattr(self, "corpus_execution_repair_id_var") else ""

    def _corpus_execution_limit(self) -> int:
        try:
            return max(1, int(self.corpus_execution_limit_var.get()))
        except Exception:
            return 25

    def _set_corpus_execution_status(self, batch_id: str | None = None, repair_id: str | None = None) -> None:
        batch = batch_id or self._corpus_batch_id()
        repair = repair_id or self._corpus_repair_id()
        recovery = get_batch_recovery_state(batch) if batch else {}
        history = get_corpus_execution_history(batch_id=batch, limit=500) if batch else {}
        checkpoint = validate_corpus_checkpoint(batch) if batch else {}
        integrity = validate_corpus_index_integrity()
        quarantine = list_quarantined_corpus_records(limit=500)
        partial = detect_partial_corpus_writes()
        counts = history.get("classification_counts", {}) if isinstance(history, dict) else {}
        text = (
            f"Batch status: {recovery.get('status', 'unknown')} | Lock status: {recovery.get('lock_status', 'unknown')} | Dry-run status: {self.corpus_execution_dry_run_var.get() if hasattr(self, 'corpus_execution_dry_run_var') else True}\n"
            f"Completed count: {counts.get('unknown', 0)} | Already-completed count: {counts.get('already_completed', 0)} | Blocked count: {counts.get('blocked', 0)} | Failed count: {counts.get('processing_failure', 0)}\n"
            f"Interrupted count: {counts.get('interrupted', 0)} | Pending count: {len(recovery.get('pending_document_ids', []))} | Checkpoint validity: {checkpoint.get('valid', False)} | Resume availability: {recovery.get('resume_available', False)}\n"
            f"Retry budget state: manual | Index status: healthy {integrity.get('healthy_index_count', 0)}, warning {integrity.get('warning_index_count', 0)}, critical {integrity.get('critical_index_count', 0)}\n"
            f"Repair plan status: {repair or 'none'} | Backup status: pending | Rollback status: manual | Quarantine count: {quarantine.get('count', 0)} | Partial-write count: {partial.get('count', 0)}"
        )
        if hasattr(self, "corpus_execution_status_var"):
            self.corpus_execution_status_var.set(text)

    def _validate_corpus_execution_dependencies(self) -> None:
        batch_id = self._corpus_batch_id()
        if not batch_id:
            self.status_var.set("Enter a batch ID before validating dependencies.")
            return
        try:
            plan = load_corpus_batch_plan(batch_id)
            doc = str((plan.get("document_ids") or [""])[0])
            result = validate_batch_action_dependencies(doc, str(plan.get("action")))
        except Exception as exc:
            self.status_var.set(f"Dependency validation unavailable: {exc}")
            return
        self._set_corpus_execution_status(batch_id=batch_id)
        self.status_var.set(f"Dependency validation for {result.get('document_id')}: allowed={result.get('allowed')} missing={result.get('missing_dependencies')}.")

    def _execute_corpus_batch(self) -> None:
        batch_id = self._corpus_batch_id()
        if not batch_id:
            self.status_var.set("Enter a batch ID before execution.")
            return
        try:
            result = execute_corpus_batch_plan(
                batch_id,
                dry_run=bool(self.corpus_execution_dry_run_var.get()),
                limit=self._corpus_execution_limit(),
                force=bool(self.corpus_execution_force_var.get()),
                retry_failures=bool(self.corpus_execution_retry_failures_var.get()),
            )
        except Exception as exc:
            self.status_var.set(f"Corpus execution failed: {exc}")
            return
        self._set_corpus_execution_status(batch_id=batch_id)
        self.status_var.set(f"Batch {batch_id}: status {result.get('status')} attempted {result.get('attempted')} completed {result.get('completed')} pending {result.get('pending')}.")

    def _pause_corpus_batch(self) -> None:
        batch_id = self._corpus_batch_id()
        if not batch_id:
            self.status_var.set("Enter a batch ID before pausing.")
            return
        pause_corpus_batch_plan(batch_id, note="Desktop pause")
        self._set_corpus_execution_status(batch_id=batch_id)
        self.status_var.set(f"Batch {batch_id} paused.")

    def _resume_corpus_batch(self) -> None:
        batch_id = self._corpus_batch_id()
        if not batch_id:
            self.status_var.set("Enter a batch ID before resume.")
            return
        try:
            result = resume_corpus_batch_plan(
                batch_id,
                dry_run=bool(self.corpus_execution_dry_run_var.get()),
                limit=self._corpus_execution_limit(),
                retry_failures=bool(self.corpus_execution_retry_failures_var.get()),
            )
        except Exception as exc:
            self.status_var.set(f"Resume failed: {exc}")
            return
        self._set_corpus_execution_status(batch_id=batch_id)
        self.status_var.set(f"Batch {batch_id} resumed: status {result.get('status')} pending {result.get('pending')}.")

    def _cancel_corpus_batch(self) -> None:
        batch_id = self._corpus_batch_id()
        if not batch_id:
            self.status_var.set("Enter a batch ID before cancel.")
            return
        cancel_corpus_batch_plan(batch_id, note="Desktop cancel")
        self._set_corpus_execution_status(batch_id=batch_id)
        self.status_var.set(f"Batch {batch_id} cancelled.")

    def _show_corpus_execution_history(self) -> None:
        batch_id = self._corpus_batch_id()
        if not batch_id:
            self.status_var.set("Enter a batch ID before loading history.")
            return
        history = get_corpus_execution_history(batch_id=batch_id, limit=100)
        self._set_corpus_execution_status(batch_id=batch_id)
        self.status_var.set(f"Execution history for {batch_id}: {history.get('receipt_count', 0)} receipt(s).")

    def _detect_stale_corpus_execution(self) -> None:
        batch_id = self._corpus_batch_id() or None
        stale = detect_stale_executions(batch_id=batch_id)
        self._set_corpus_execution_status(batch_id=batch_id)
        self.status_var.set(f"Stale executions: {stale.get('stale_count', 0)}.")

    def _show_corpus_index_integrity(self) -> None:
        integrity = validate_corpus_index_integrity()
        self._set_corpus_execution_status(batch_id=self._corpus_batch_id())
        self.status_var.set(f"Index integrity: healthy {integrity.get('healthy_index_count', 0)}, warning {integrity.get('warning_index_count', 0)}, critical {integrity.get('critical_index_count', 0)}.")

    def _build_corpus_repair_plan_ui(self) -> None:
        plan = build_corpus_repair_plan(dry_run=True)
        if hasattr(self, "corpus_execution_repair_id_var"):
            self.corpus_execution_repair_id_var.set(str(plan.get("repair_id", "")))
        self._set_corpus_execution_status(batch_id=self._corpus_batch_id(), repair_id=str(plan.get("repair_id", "")))
        self.status_var.set(f"Repair plan built: {plan.get('repair_id')}. Dry-run preview only.")

    def _verify_corpus_repair_backup_ui(self) -> None:
        repair_id = self._corpus_repair_id()
        if not repair_id:
            self.status_var.set("Build a repair plan first.")
            return
        try:
            plan = build_corpus_repair_plan(dry_run=True) if False else None
            if plan:
                pass
        except Exception:
            pass
        try:
            from .corpus_execution_recovery import _load_repair_plan

            repair = _load_repair_plan(repair_id, Path(__file__).resolve().parents[2] / "data" / "source_documents")
            backup_id = str(repair.get("backup_id") or "")
            if not backup_id:
                backup = create_corpus_repair_backup(repair_id)
                backup_id = str(backup.get("backup_id"))
            verified = verify_corpus_repair_backup(backup_id)
        except Exception as exc:
            self.status_var.set(f"Backup verification failed: {exc}")
            return
        self._set_corpus_execution_status(batch_id=self._corpus_batch_id(), repair_id=repair_id)
        self.status_var.set(f"Backup verification for {repair_id}: verified={verified.get('verified')}.")

    def _execute_corpus_repair_ui(self) -> None:
        repair_id = self._corpus_repair_id()
        if not repair_id:
            self.status_var.set("Enter or build a repair ID before execution.")
            return
        result = execute_corpus_repair_plan(repair_id, dry_run=bool(self.corpus_execution_dry_run_var.get()))
        self._set_corpus_execution_status(batch_id=self._corpus_batch_id(), repair_id=repair_id)
        self.status_var.set(f"Repair {repair_id}: {result.get('status')}.")

    def _rollback_corpus_repair_ui(self) -> None:
        repair_id = self._corpus_repair_id()
        if not repair_id:
            self.status_var.set("Enter a repair ID before rollback.")
            return
        result = rollback_corpus_repair(repair_id, explicit=True)
        self._set_corpus_execution_status(batch_id=self._corpus_batch_id(), repair_id=repair_id)
        self.status_var.set(f"Rollback {repair_id}: {result.get('status')}.")

    def _show_corpus_quarantine_summary(self) -> None:
        result = list_quarantined_corpus_records(limit=100)
        self._set_corpus_execution_status(batch_id=self._corpus_batch_id(), repair_id=self._corpus_repair_id())
        self.status_var.set(f"Quarantine records: {result.get('count', 0)}.")

    def _show_partial_corpus_writes(self) -> None:
        result = detect_partial_corpus_writes()
        build_partial_write_recovery_plan(dry_run=True)
        self._set_corpus_execution_status(batch_id=self._corpus_batch_id(), repair_id=self._corpus_repair_id())
        self.status_var.set(f"Partial-write records: {result.get('count', 0)}.")

    def _copy_corpus_execution_report(self) -> None:
        batch_id = self._corpus_batch_id()
        if not batch_id:
            self.status_var.set("Enter a batch ID before copying the execution report.")
            return
        text = format_corpus_execution_report_text(batch_id, public_safe=True)
        integrity = format_corpus_integrity_report_text(public_safe=True)
        self.clipboard_clear()
        self.clipboard_append(text + "\n\n" + integrity)
        self._set_corpus_execution_status(batch_id=batch_id, repair_id=self._corpus_repair_id())
        self.status_var.set(f"Public-safe execution report copied for {batch_id}.")

    def _show_pdf_proposal_review_queue(self) -> None:
        self._refresh_proposal_review_queue()

    def _filter_value(self, attr_name: str) -> str | None:
        var = getattr(self, attr_name, None)
        value = var.get() if var is not None else "any"
        return None if not value or str(value).lower() == "any" else str(value)

    def _refresh_proposal_review_queue(self) -> None:
        try:
            state = get_proposal_review_ui_state(
                status=self._filter_value("proposal_review_status_filter_var"),
                readiness_band=self._filter_value("proposal_review_readiness_filter_var"),
                conflict_status=self._filter_value("proposal_review_conflict_filter_var"),
                duplicate_status=self._filter_value("proposal_review_duplicate_filter_var"),
                limit=50,
            )
        except Exception as exc:
            self.status_var.set(f"Proposal review queue unavailable: {exc}")
            return
        self.proposal_review_state = state
        if hasattr(self, "proposal_review_queue_list"):
            self.proposal_review_queue_list.delete(0, tk.END)
            items = state.get("items", []) if isinstance(state, dict) else []
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    row = (
                        f"{item.get('proposal_id')} | {item.get('review_status')} | "
                        f"cite {item.get('citation_strength_band')} | dup {item.get('duplicate_status')} | "
                        f"conf {item.get('conflict_status')} | ready {item.get('promotion_readiness_band')}"
                    )
                    self.proposal_review_queue_list.insert(tk.END, row)
        if hasattr(self, "proposal_review_selected_var"):
            warnings = state.get("warnings", []) if isinstance(state, dict) else []
            if warnings:
                self.proposal_review_selected_var.set("Selected Proposal: None\nNo proposals match current filters.")
            else:
                self.proposal_review_selected_var.set("Selected Proposal: None\nSelect a proposal to review.")
        self.status_var.set(f"Proposal review queue: {state.get('queue_count', 0)} item(s).")

    def _on_proposal_review_selected(self, _event: object | None = None) -> None:
        if not hasattr(self, "proposal_review_queue_list"):
            return
        selection = self.proposal_review_queue_list.curselection()
        if not selection:
            self.proposal_review_selected_var.set("Selected Proposal: None\nSelect a proposal to review.")
            return
        items = self.proposal_review_state.get("items", []) if isinstance(getattr(self, "proposal_review_state", {}), dict) else []
        if not isinstance(items, list) or selection[0] >= len(items):
            self.proposal_review_selected_var.set("Selected Proposal: None\nSelection is no longer valid.")
            return
        proposal_id = str(items[selection[0]].get("proposal_id") or "")
        selected = select_proposal_for_review_ui(proposal_id)
        self.proposal_review_state["selected_proposal"] = selected
        self._refresh_proposal_review_selected_detail()

    def _selected_proposal_review_state(self) -> dict[str, object] | None:
        state = getattr(self, "proposal_review_state", {})
        selected = state.get("selected_proposal") if isinstance(state, dict) else None
        if not isinstance(selected, dict) or not selected.get("selected"):
            self.status_var.set("No proposal selected. Select a proposal from the review queue first.")
            return None
        return selected

    def _refresh_proposal_review_selected_detail(self) -> None:
        selected = self._selected_proposal_review_state()
        if selected is None:
            if hasattr(self, "proposal_review_selected_var"):
                self.proposal_review_selected_var.set("Selected Proposal: None\nSelect a proposal to review.")
            return
        citation = selected.get("citation_strength") if isinstance(selected.get("citation_strength"), dict) else {}
        duplicate = selected.get("duplicate_check") if isinstance(selected.get("duplicate_check"), dict) else {}
        conflict = selected.get("conflict_check") if isinstance(selected.get("conflict_check"), dict) else {}
        readiness = selected.get("promotion_readiness") if isinstance(selected.get("promotion_readiness"), dict) else {}
        warnings = selected.get("warnings") if isinstance(selected.get("warnings"), list) else []
        blockers = selected.get("blockers") if isinstance(selected.get("blockers"), list) else []
        notes = selected.get("review_notes") if isinstance(selected.get("review_notes"), list) else []
        self.proposal_review_selected_var.set(
            "Selected Proposal\n"
            f"Proposal: {selected.get('proposal_id')}\n"
            f"Status: {selected.get('review_status')}\n"
            f"Claim: {selected.get('claim_preview')}\n"
            f"Citation: {citation.get('band', 'unknown')} ({citation.get('score', 'unknown')})\n"
            f"Duplicate: {duplicate.get('status', 'unknown')}\n"
            f"Conflict: {conflict.get('status', 'unknown')}\n"
            f"Readiness: {readiness.get('band', 'unknown')} ({readiness.get('score', 'unknown')})\n"
            f"Recommended Action: {selected.get('recommended_action')}\n"
            f"Warnings: {', '.join(str(item) for item in warnings) if warnings else 'None'}\n"
            f"Blockers: {', '.join(str(item) for item in blockers) if blockers else 'None'}\n"
            f"Notes: {len(notes)}"
        )

    def _add_selected_proposal_review_note(self) -> None:
        selected = self._selected_proposal_review_state()
        if selected is None:
            return
        note = self.proposal_review_note_var.get().strip() if hasattr(self, "proposal_review_note_var") else ""
        if not note:
            self.status_var.set("Enter a review note before adding it.")
            return
        try:
            add_proposal_review_note(str(selected.get("proposal_id")), note, "manual")
            self.proposal_review_note_var.set("")
            self.proposal_review_state["selected_proposal"] = select_proposal_for_review_ui(str(selected.get("proposal_id")))
            self._refresh_proposal_review_selected_detail()
        except Exception as exc:
            self.status_var.set(f"Could not add review note: {exc}")
            return
        self.status_var.set("Review note added.")

    def _apply_selected_proposal_review_action(self, action: str) -> None:
        selected = self._selected_proposal_review_state()
        if selected is None:
            return
        note = self.proposal_review_note_var.get().strip() if hasattr(self, "proposal_review_note_var") else ""
        try:
            refreshed = apply_proposal_review_ui_action(str(selected.get("proposal_id")), action, note or None)
            self.proposal_review_note_var.set("")
            self.proposal_review_state["selected_proposal"] = refreshed
            self._refresh_proposal_review_selected_detail()
            self._refresh_proposal_review_queue()
            self.proposal_review_state["selected_proposal"] = refreshed
            self._refresh_proposal_review_selected_detail()
        except Exception as exc:
            self.status_var.set(f"Could not update review decision: {exc}")
            return
        self.status_var.set("Review decision updated. No rules were promoted or changed.")

    def _copy_selected_proposal_review_summary(self) -> None:
        selected = self._selected_proposal_review_state()
        if selected is None:
            return
        try:
            text = copy_proposal_review_summary(str(selected.get("proposal_id")))
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception as exc:
            self.status_var.set(f"Could not copy review summary: {exc}")
            return
        self.status_var.set("Public-safe proposal review summary copied.")
    def _build_selected_evidence_binder(self) -> None:
        selected = self._selected_proposal_review_state()
        if selected is None:
            return
        proposal_id = str(selected.get("proposal_id") or "")
        try:
            build_evidence_binder(proposal_id, regenerate=True)
            summary = get_evidence_binder_summary(proposal_id)
        except Exception as exc:
            self.status_var.set(f"Could not build evidence binder: {exc}")
            return
        self.status_var.set(
            f"Evidence binder: {summary.get('binder_status')}; citations {summary.get('citation_count')}, "
            f"bundle {summary.get('bundle_strength_band')}, coverage {summary.get('coverage_band')}, "
            f"conflict {summary.get('conflict_status')}."
        )

    def _show_selected_evidence_binder_summary(self) -> None:
        selected = self._selected_proposal_review_state()
        if selected is None:
            return
        proposal_id = str(selected.get("proposal_id") or "")
        try:
            summary = get_evidence_binder_summary(proposal_id)
        except Exception as exc:
            self.status_var.set(f"Evidence binder summary unavailable: {exc}")
            return
        self.status_var.set(
            f"Evidence Binder: {summary.get('binder_status')}; citations {summary.get('citation_count')}; "
            f"documents {summary.get('unique_documents')}; support {summary.get('support_status')}; "
            f"conflict {summary.get('conflict_status')}; action: {summary.get('recommended_action')}"
        )

    def _copy_selected_evidence_binder_report(self) -> None:
        selected = self._selected_proposal_review_state()
        if selected is None:
            return
        proposal_id = str(selected.get("proposal_id") or "")
        try:
            text = format_evidence_binder_report_text(proposal_id, public_safe=True)
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception as exc:
            self.status_var.set(f"Could not copy evidence binder report: {exc}")
            return
        self.status_var.set("Public-safe evidence binder report copied. No rules were changed.")
    def _run_pdf_document_search(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        document_id = str(payload.get("document_id") or "") if isinstance(payload, dict) else ""
        if not document_id:
            self.status_var.set("Register and chunk a PDF before searching.")
            return
        query = self.pdf_search_query_var.get().strip() if hasattr(self, "pdf_search_query_var") else ""
        if not query:
            self.status_var.set("Enter a search query before searching document chunks.")
            return
        try:
            limit = max(1, min(50, int(self.pdf_search_limit_var.get() or "20")))
        except ValueError:
            limit = 20
        try:
            state = run_document_search_for_ui(document_id, query, mode=self.pdf_search_mode_var.get() or "keyword", limit=limit)
        except Exception as exc:
            self.status_var.set(f"Document search failed: {exc}")
            return
        self.pdf_search_state = state
        self._refresh_pdf_search_results()
        count = len(state.get("results", [])) if isinstance(state.get("results"), list) else 0
        self.status_var.set(f"Document search {state.get('status', 'unknown')}: {count} result(s).")

    def _refresh_pdf_search_results(self) -> None:
        if not hasattr(self, "pdf_search_results_list"):
            return
        self.pdf_search_results_list.delete(0, tk.END)
        state = getattr(self, "pdf_search_state", {})
        results = state.get("results", []) if isinstance(state, dict) else []
        if not isinstance(results, list) or not results:
            self.pdf_selected_result_var.set("Selected Result: None\nNo search results available.")
            return
        for item in results:
            if not isinstance(item, dict):
                continue
            page = item.get("page_start") if item.get("page_start") is not None else "?"
            snippet = str(item.get("snippet") or "").replace("\n", " ")[:80]
            self.pdf_search_results_list.insert(tk.END, f"Page {page} | {item.get('chunk_id')} | {item.get('match_count')} match(es) | {snippet}")
        self.pdf_selected_result_var.set("Selected Result: None\nSelect a search result to review.")

    def _on_pdf_search_result_selected(self, _event: object | None = None) -> None:
        if not hasattr(self, "pdf_search_results_list"):
            return
        selection = self.pdf_search_results_list.curselection()
        if not selection:
            self.pdf_selected_result_var.set("Selected Result: None\nSelect a search result to review.")
            return
        state = getattr(self, "pdf_search_state", {})
        results = state.get("results", []) if isinstance(state, dict) else []
        if not isinstance(results, list) or selection[0] >= len(results):
            self.pdf_selected_result_var.set("Selected Result: None\nSelection is no longer valid.")
            return
        result = results[selection[0]]
        try:
            self.pdf_search_state = select_search_result_for_ui(state, str(result.get("result_id") or ""))
        except Exception as exc:
            self.status_var.set(f"Could not select search result: {exc}")
            return
        self._refresh_pdf_selected_result_detail()

    def _refresh_pdf_selected_result_detail(self) -> None:
        state = getattr(self, "pdf_search_state", {})
        selected = state.get("selected_result") if isinstance(state, dict) else None
        if not isinstance(selected, dict):
            self.pdf_selected_result_var.set("Selected Result: None\nSelect a search result to review.")
            return
        page_start = selected.get("selected_page_start")
        page_end = selected.get("selected_page_end")
        page = "Unavailable" if page_start is None else f"{page_start}-{page_end}" if page_end and page_end != page_start else str(page_start)
        warnings = selected.get("selected_warnings") or []
        warning_text = "; ".join(str(item) for item in warnings) if warnings else "None"
        self.pdf_selected_result_var.set(
            "Selected Result\n"
            f"Document: {selected.get('selected_document_id')}\n"
            f"Chunk: {selected.get('selected_chunk_id')}\n"
            f"Page: {page}\n"
            f"Matches: {selected.get('selected_match_count')}\n"
            f"Snippet: {selected.get('selected_snippet')}\n"
            f"Warnings: {warning_text}"
        )

    def _selected_pdf_result_state(self) -> dict[str, object] | None:
        state = getattr(self, "pdf_search_state", {})
        if not isinstance(state, dict) or not isinstance(state.get("selected_result"), dict):
            self.status_var.set("No result selected. Select a search result first.")
            return None
        return state

    def _open_selected_pdf_chunk(self) -> None:
        state = self._selected_pdf_result_state()
        if state is None:
            return
        selected = state["selected_result"]
        try:
            chunk = get_document_chunk_text(str(selected.get("selected_chunk_id")))
        except Exception as exc:
            self.status_var.set(f"Chunk unavailable: {exc}")
            return
        self.pdf_selected_result_var.set(f"Chunk {chunk.get('chunk_id')}\n\n{str(chunk.get('text') or '')[:1200]}")
        self.status_var.set("Selected chunk opened in the review panel.")

    def _open_selected_pdf_page(self) -> None:
        state = self._selected_pdf_result_state()
        if state is None:
            return
        selected = state["selected_result"]
        page = selected.get("selected_page_start")
        if page is None:
            self.status_var.set("Page text unavailable for this result.")
            return
        try:
            page_text = get_document_page_text(str(selected.get("selected_document_id")), int(page))
        except Exception as exc:
            self.status_var.set(f"Page unavailable: {exc}")
            return
        if not page_text.get("text"):
            self.status_var.set("Page text unavailable for this result.")
            return
        self.pdf_selected_result_var.set(f"Page {page}\n\n{str(page_text.get('text') or '')[:1200]}")
        self.status_var.set("Selected page opened in the review panel.")

    def _copy_selected_pdf_snippet(self) -> None:
        state = self._selected_pdf_result_state()
        if state is None:
            return
        try:
            snippet = copy_snippet_from_selected_result(state)
            self.clipboard_clear()
            self.clipboard_append(snippet)
        except Exception as exc:
            self.status_var.set(f"Could not copy snippet: {exc}")
            return
        self.status_var.set("Selected redaction-safe snippet copied.")

    def _create_selected_pdf_proposal(self) -> None:
        state = self._selected_pdf_result_state()
        if state is None:
            return
        claim = self.pdf_search_proposal_var.get().strip() if hasattr(self, "pdf_search_proposal_var") else ""
        if not claim:
            self.status_var.set("Enter a proposal claim/note before creating a proposal.")
            return
        try:
            proposal = create_proposal_from_selected_result(state, claim)
        except Exception as exc:
            self.status_var.set(f"Could not create proposal: {exc}")
            return
        self.status_var.set(f"Proposal created for review: {proposal.proposal_id}.")

    def _create_selected_pdf_citation(self) -> None:
        state = self._selected_pdf_result_state()
        if state is None:
            return
        note = self.pdf_search_citation_var.get().strip() if hasattr(self, "pdf_search_citation_var") else ""
        if not note:
            self.status_var.set("Enter a citation note before creating a citation.")
            return
        try:
            citation = create_citation_from_selected_result(state, note)
        except Exception as exc:
            self.status_var.set(f"Could not create citation: {exc}")
            return
        self.status_var.set(f"Citation created: {citation.citation_id}.")

    def _mark_selected_pdf_feedback(self, feedback: str) -> None:
        state = self._selected_pdf_result_state()
        if state is None:
            return
        try:
            record = mark_selected_result_feedback(state, feedback)
        except Exception as exc:
            self.status_var.set(f"Could not save feedback: {exc}")
            return
        self.status_var.set(f"Search result feedback saved: {record.get('feedback_id')}.")
    def _open_pdf_intake_text(self) -> None:
        payload = getattr(self, "pdf_intake_payload", {})
        text_path = Path(str(payload.get("extracted_text_path") or "")) if isinstance(payload, dict) else Path("")
        if not text_path.exists():
            self.status_var.set("No extracted text file is available for this PDF.")
            return
        try:
            os.startfile(text_path)  # type: ignore[attr-defined]
        except OSError as exc:
            self.status_var.set(f"Could not open extracted text: {exc}")

    def _clear_pdf_intake_file(self) -> None:
        self.pdf_intake_payload = {}
        if hasattr(self, "pdf_intake_status_var"):
            self.pdf_intake_status_var.set(self._pdf_intake_status_text())
        self.status_var.set("PDF Intake cleared.")

    def _pdf_intake_status_text(self) -> str:
        payload = getattr(self, "pdf_intake_payload", {})
        if not isinstance(payload, dict) or not payload:
            return "No PDF selected. Choose a PDF to stage it for controlled source-document processing."
        size_bytes = int(payload.get("size_bytes", 0) or 0)
        size_kb = size_bytes / 1024 if size_bytes else 0
        document_id = str(payload.get("document_id") or "")
        summary = payload.get("preflight_summary")
        if document_id and not isinstance(summary, dict):
            try:
                summary = get_document_preflight_summary(document_id)
            except Exception:
                summary = None
        lines = [
            f"File: {payload.get('original_filename') or payload.get('name', 'unknown')}",
            f"Size: {size_kb:.1f} KB",
            f"Status: {payload.get('extraction_status') or payload.get('status', 'selected')}",
        ]
        if document_id:
            lines.append(f"Document ID: {document_id}")
        if isinstance(summary, dict):
            lines.extend(
                [
                    "",
                    "Document Preflight",
                    f"Verdict: {summary.get('verdict', 'Unknown')}",
                    f"Status: {summary.get('status', 'Unknown')}",
                    f"Format: {summary.get('format', 'Unknown')}",
                    f"OCR needed: {self._pdf_intake_yes_no_unknown(summary.get('ocr_needed'))}",
                    f"Pages: {self._pdf_intake_unknown(summary.get('page_count'))}",
                    f"Text pages: {self._pdf_intake_unknown(summary.get('text_pages'))}",
                    f"Empty pages: {self._pdf_intake_unknown(summary.get('empty_pages'))}",
                    f"Extraction quality: {self._pdf_intake_score(summary.get('extraction_quality_score'), summary.get('extraction_quality_band'))}",
                    f"Chunk readiness: {self._pdf_intake_score(summary.get('chunk_readiness_score'), summary.get('chunk_readiness_band'))}",
                    f"Citation readiness: {self._pdf_intake_score(summary.get('citation_readiness_score'), summary.get('citation_readiness_band'))}",
                    f"Privacy: {summary.get('privacy_status', 'Unknown')}",
                    f"Public export safe: {self._pdf_intake_yes_no_unknown(summary.get('public_export_safe'))}",
                ]
            )
            blockers = summary.get("top_blockers") or []
            warnings = summary.get("top_warnings") or []
            keywords = summary.get("keyword_matches") or []
            findings = summary.get("privacy_findings") or []
            if blockers:
                lines.append("Blockers: " + "; ".join(str(item) for item in blockers[:4]))
            if warnings:
                lines.append("Warnings: " + "; ".join(str(item) for item in warnings[:4]))
            if keywords:
                lines.append("Key terms: " + "; ".join(f"{item.get('term')}: {item.get('count')}" for item in keywords[:4] if isinstance(item, dict)))
            if findings:
                lines.append("Privacy findings: " + "; ".join(str(item).replace("_", " ") for item in findings[:4]))
            if summary.get("recommended_action"):
                lines.append("Recommended Action: " + str(summary.get("recommended_action")))
        elif payload.get("page_count") is not None:
            lines.append(f"Pages: {payload.get('page_count')}")
        reader_state = payload.get("reader_state")
        if isinstance(reader_state, dict):
            lines.append(
                f"Document Reader: extracted {self._pdf_intake_yes_no_unknown(reader_state.get('has_extracted_text'))}; "
                f"chunks {reader_state.get('chunk_count', 0)}; diagnostics {self._pdf_intake_yes_no_unknown(reader_state.get('has_page_diagnostics'))}"
            )
            structure_summary = reader_state.get("structure_summary")
            if isinstance(structure_summary, dict):
                lines.append(
                    f"Structure: {structure_summary.get('status')}; headings {structure_summary.get('headings', 0)}; "
                    f"sections {structure_summary.get('sections', 0)}; re-chunk {structure_summary.get('rechunk_strategy', 'unknown')}"
                )
        structure_summary = payload.get("structure_summary")
        if isinstance(structure_summary, dict):
            lines.append(
                f"Structure: {structure_summary.get('status')}; headings {structure_summary.get('headings', 0)}; "
                f"sections {structure_summary.get('sections', 0)}; chunk quality {structure_summary.get('chunk_quality_status', 'unknown')}"
            )
        if payload.get("extracted_char_count"):
            lines.append(f"Extracted text: {payload.get('extracted_char_count')} characters")
        if payload.get("chunk_count"):
            lines.append(f"Chunks: {payload.get('chunk_count')}")
        if payload.get("sha256"):
            lines.append(f"Hash: {payload.get('sha256')}")
        warnings = payload.get("warnings")
        if isinstance(warnings, list) and warnings:
            lines.append("Record warnings: " + "; ".join(str(item) for item in warnings[:3]))
        lines.append("Safety: no OCR, parsing, chart import, or election data mutation runs automatically.")
        return "\n".join(lines)

    @staticmethod
    def _pdf_intake_unknown(value: object) -> str:
        return "Unknown" if value is None else str(value)

    @staticmethod
    def _pdf_intake_yes_no_unknown(value: object) -> str:
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        return "Unknown"

    @staticmethod
    def _pdf_intake_score(score: object, band: object) -> str:
        if score is None:
            return "Unknown"
        return f"{score}/100 - {band or 'Unknown'}"
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
            "PDF Intake": "Load a source PDF for future chart/source processing without running OCR or parsing yet.",
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
            samples = summary.get("samples", [])
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
            repair_lines: list[str] = []
            if isinstance(samples, list):
                for sample in samples:
                    if not isinstance(sample, dict):
                        continue
                    repairs = sample.get("repairs", [])
                    if isinstance(repairs, list):
                        for repair in repairs:
                            text = str(repair).strip()
                            if text and text not in repair_lines:
                                repair_lines.append(text)
                            if len(repair_lines) >= 2:
                                break
                    if len(repair_lines) >= 2:
                        break
            if repair_lines:
                tk.Label(
                    empty_card,
                    text="Try this repair",
                    bg=PALETTE["panel_alt"],
                    fg=PALETTE["accent_dark"],
                    font=("Georgia", 8, "bold"),
                    anchor="w",
                ).pack(fill=tk.X, pady=(8, 2))
                for repair in repair_lines:
                    tk.Label(
                        empty_card,
                        text=f"- {repair}",
                        bg=PALETTE["panel_alt"],
                        fg=PALETTE["astrolabe_ink"],
                        font=("Segoe UI", 8),
                        wraplength=300,
                        justify=tk.LEFT,
                        anchor="w",
                    ).pack(fill=tk.X, pady=(0, 3))
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
