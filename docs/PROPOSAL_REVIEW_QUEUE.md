# Proposal Review Queue

Phase 8E adds manual governance for source-backed proposals and citations.

## Workflow

```text
Manual proposal -> Citation review -> Duplicate/conflict checks -> Promotion readiness -> Human review decision
```

Approval means `approved_for_later_promotion`; it does not promote a rule, mutate scoring, change Fast Lane, or modify objective packs.

## Citation Strength

Citation strength measures source quality only. It checks whether a citation links to a source document, chunk, page reference when available, excerpt, source hash, preflight quality, and existing chunk/document records.

Bands:

- `strong`
- `usable`
- `weak`
- `poor`
- `unusable`

Weak or missing citations block promotion readiness but do not delete proposals.

## Duplicate and Conflict Checks

Duplicate detection uses deterministic claim/source matching only. Conflict detection uses simple opposite decision-word checks. These are review warnings, not final truth judgments.

## Review Statuses

Supported statuses include:

- `pending_review`
- `in_review`
- `approved_for_later_promotion`
- `rejected`
- `deferred`
- `needs_more_source`
- `needs_better_citation`
- `duplicate`
- `conflict_review`

Review notes are stored in the proposal review record. Public-safe summaries should expose note counts or categories, not full private notes.

## Promotion Readiness

Promotion readiness is advisory only. It can say a proposal is ready for human promotion review, but it never creates, edits, or activates production rules.

## Desktop UI

The PDF Intake page exposes a compact Proposal Review Queue action that reports the top queue item and recommended action. It is intentionally not a rule-promotion dashboard.

## Targeted Testing

Use targeted tests only:

```powershell
.\.venv\Scripts\python.exe scripts/run_targeted_tests.py --file backend/tests/test_proposal_review_queue.py
```

Broad project-wide test discovery is skipped by policy unless explicitly requested.
## Phase 8F Proposal Review Dashboard

The desktop PDF Intake area now includes a compact Proposal Review Dashboard. It is a manual governance surface only: it does not promote rules, mutate scoring, change Fast Lane, or activate citations.

Dashboard controls:
- Filter by review status, promotion readiness, duplicate status, and conflict status.
- Refresh the real proposal review queue from controlled source-document storage.
- Select a proposal to inspect citation strength, duplicate checks, possible conflict checks, promotion readiness, warnings, blockers, and note count.
- Add a review note.
- Set manual review decisions: In Review, Needs More Source, Needs Better Citation, Reject, Defer, Duplicate, Conflict Review, or Approve for Later Promotion.
- Copy a public-safe review summary that omits source text, local paths, private note text, and exact sensitive values.

Approval is deliberately named Approve for Later Promotion. It marks the proposal as reviewed for a future human promotion workflow, but does not create or edit production rules.

Targeted testing only: use the specific proposal review dashboard test file or specific cases. Do not run broad project-wide test discovery during document governance work.
## Phase 8H Evidence Binder

Evidence binders group proposal-linked citations across documents, summarize source reliability, score citation bundle strength, flag deterministic support/conflict evidence, report weak or stale sources, and produce public-safe binder summaries. Evidence binders are review aids only: they do not create citations, create proposals, promote rules, mutate scoring, or touch Fast Lane.
## Phase 8I Source Reliability Manager

Source reliability records can now be edited, recalculated, versioned through history events, linked to replacement sources, checked for duplicate source identities, summarized in a quality dashboard, and used to refresh evidence binders. Reliability remains advisory only and does not mutate rules, scoring, Fast Lane, proposals, or citations.
