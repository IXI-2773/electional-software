# Source Revalidation Review

Phase 8M adds a controlled review workspace for existing Phase 8L source-impact queue items.

## Review Workspace Purpose

The workspace loads one queue item, its source impact summary, affected dependency IDs, an evidence recheck summary, and the current resolution record if one already exists.

## Dependency Dispositions

Disposition values are advisory only:

- `still_valid`
- `needs_review`
- `invalid_due_to_source`
- `replacement_source_required`
- `deferred`
- `not_applicable`
- `unknown`

They do not edit citations, proposals, reviews, or evidence binders.

## Evidence Recheck Behavior

Evidence recheck reads existing binder records only. It summarizes:

- available vs missing binders
- weak/stale source warnings already present in binder records
- existing conflict flags
- existing evidence coverage bands

It does not rebuild binders or infer new evidence.

## Resolution Decisions

- `keep_open`
- `resolved_no_change`
- `resolved_with_manual_followup`
- `replacement_source_required`
- `deferred`
- `dismissed`

`reviewed` means the queue review is complete. It does not mean downstream records were rewritten or corrected automatically.

## Queue Closure Rules

Closure validates:

- allowed disposition values
- allowed dependency IDs only
- required dispositions for high/critical items
- safe-only dispositions for `resolved_no_change`
- replacement-required dispositions for `replacement_source_required`

## What This Workflow Does Not Modify

- citation content
- proposal content
- proposal review decisions
- evidence binder content
- rules
- scores
- production behavior

## Public-Safe Reports

Resolution reports omit local paths, source text, citation text, proposal text, and private notes when `public_safe=True`.

## Deferred

- P1 deferred by timebox: per-record editors, binder rebuilding, batch resolution, notifications, timelines, graph views
- P2 not attempted by policy: AI review advice, semantic analysis, automatic replacements or rewrites

## Targeted Testing Policy

Run only:

```powershell
.\.venv\Scripts\python.exe scripts\run_targeted_tests.py --file backend/tests/test_source_revalidation_review.py
```
