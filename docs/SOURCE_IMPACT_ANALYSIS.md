# Source Impact Analysis

Phase 8L adds read-only traceability for source changes.

## Purpose

When a controlled source becomes stale, superseded, replaced, downgraded, quarantined, corrupt, or missing, the system can trace affected downstream records without changing them automatically.

## Dependency Categories Checked

- citations linked to the source document or its controlled chunks
- proposals linked to the same controlled source chunks
- proposal review records for affected proposals
- evidence binders for affected proposals when the binder links the source

## Deterministic Severity Rules

- `none`: no downstream dependencies found
- `low`: only one or two citations affected
- `medium`: multiple citations or any proposal/review affected
- `high`: any evidence binder affected or approved-for-later-promotion review affected
- `critical`: corrupt, quarantined, or missing source with downstream dependencies
- `unknown`: required controlled indexes could not be read safely

## Manual Revalidation Queue

Queue items are stored under `data/source_documents/source_impact_queue/` and indexed in `data/source_documents/indexes/source_impact_queue_index.json`.

Queue status is manual only:

- `pending_review`
- `in_review`
- `reviewed`
- `deferred`
- `dismissed`

Duplicate pending items for the same source/change state are prevented with a stable deduplication key.

## Public-Safe Reports

Impact reports include counts, source state, severity, and recommended action. They omit absolute paths, source text, chunk text, citation excerpts, proposal text, private notes, and secrets.

For controlled review and closure of existing queue items, see `docs/SOURCE_REVALIDATION_REVIEW.md`.

## What Phase 8L Does Not Change Automatically

- no citation replacement
- no citation invalidation
- no proposal rewriting
- no proposal review status mutation
- no evidence binder rebuild
- no batch revalidation execution

## Deferred

- P1 deferred by timebox: graph views, automatic refresh execution, batch revalidation execution, notifications, timelines
- P2 not attempted by policy: AI interpretation, semantic inference, automatic replacements or rewrites

## Targeted Testing Policy

Run only:

```powershell
.\.venv\Scripts\python.exe scripts\run_targeted_tests.py --file backend/tests/test_source_impact_analysis.py
```
