# Source Workflow Coordinator

Phase 8O adds a read-controlled coordinator over the existing source pipeline helpers. It does not replace those helpers and it does not run the full pipeline automatically.

## Purpose

The coordinator answers:

- what controlled pipeline state exists now
- whether the manifest can be reused safely
- which stage should run next
- whether a selected stage is executable
- what changes after one explicitly approved stage runs

## Pipeline Fingerprint Components

The workflow fingerprint is deterministic and uses controlled state only:

- `source_hash`
- `preflight_record_hash`
- `extraction_record_hash`
- `chunk_index_hash`
- `page_diagnostics_hash`
- `structure_map_hash`
- `reliability_record_hash`
- `citation_index_hash`
- `proposal_index_hash`
- `evidence_binder_index_hash`
- `impact_queue_index_hash`
- `revalidation_resolution_index_hash`

## Manifest Invalidation Rules

Manifest reuse is allowed only when:

- the source hash is unchanged
- the stored pipeline fingerprint matches the current fingerprint
- the stored manifest schema is supported
- the manifest is readable

Downstream-only changes can therefore invalidate manifest reuse without changing the source revision.

## Allowlisted Workflow Stages

Only these stages are supported:

- `run_preflight`
- `extract_text`
- `chunk_text`
- `build_page_diagnostics`
- `build_structure_map`
- `recalculate_reliability`
- `refresh_existing_evidence_binders`
- `refresh_manifest`

No arbitrary helper names or paths are allowed.

## Recommendation Order

The next-step recommendation is deterministic:

1. `run_preflight`
2. `extract_text`
3. `chunk_text`
4. `build_page_diagnostics`
5. `build_structure_map`
6. `recalculate_reliability`
7. `refresh_existing_evidence_binders`
8. `refresh_manifest`
9. `none`

## Dry-Run Planning

Workflow plans default to `dry_run=True`.

Plan creation:

- validates the requested or recommended stage
- captures current manifest fingerprint and readiness
- records dependency state
- does not execute anything
- does not run prerequisites

## Single-Stage Execution Rule

Execution runs exactly one selected stage. It does not:

- run subsequent stages
- run until ready
- silently execute prerequisites
- retry automatically

## Dependency Validation

Dependencies are validated before plan creation and again before execution. Missing prerequisites block execution and are reported explicitly.

## Manifest and Readiness Refresh

After one stage executes, the coordinator refreshes:

- pipeline fingerprint
- canonical manifest
- consistency state
- backend readiness

## Resume State

Resume state is planning only. It identifies the first missing or stale stage and the remaining stages still needed. It does not build a batch or run the remaining work.

## Public-Safe Workflow Report

Public-safe workflow reports omit:

- absolute paths
- source or chunk text
- citation or proposal text
- private notes
- stack traces
- secrets or tokens

## Deferred Work

- P1 deferred by timebox: multi-stage execution, run-until-ready, batch workflows, automatic retries, automatic stale rebuilds, workflow history/timelines, workflow graphs
- P2 not attempted by policy: PDF rendering, page navigation, OCR, semantic search, AI interpretation

## Targeted Testing Policy

Only the focused Phase 8O test file is intended for this pass:

- `scripts/run_targeted_tests.py --file backend/tests/test_source_workflow_coordinator.py`

Broad project-wide test execution is intentionally skipped in this phase.
