# Document Content Curation

Phase 8Q adds a manual, non-destructive curation overlay on top of the detected document content map.

## Purpose

- keep the detected content map intact
- allow controlled chapter and section corrections
- allow chunk assignment fixes in the curated view
- allow per-chunk manual topic-tag overrides
- track curation revisions against the detected base fingerprint

## Why The Detected Map Stays Unchanged

The detected map remains the authoritative automatic output from Phase 8P. Phase 8Q stores overrides separately and applies them only when building a curated view.

## Supported Corrections

- chapter rename
- chapter range correction
- section rename
- section range correction
- assign existing chunk to existing section
- unassign chunk from section in the curated view
- add manual topic tag to chunk
- remove manual topic tag from chunk

Unsupported in this pass:

- new chapter creation
- new section creation
- permanent delete
- bulk editing
- drag-and-drop ordering

## Curation Revision Behavior

- curation revision increments only for effective new changes
- exact duplicate changes are idempotent
- stored changes preserve the original detected map
- base content-map fingerprint and source revision are recorded with the overlay

## Base-Fingerprint Staleness

Curation becomes stale when:

- the detected content-map fingerprint changes
- the source revision changes
- a referenced chapter, section, or chunk no longer exists
- a stored manual range is no longer valid

Stale overrides are preserved, but they are not migrated or reapplied silently.

## Readiness Statuses

- `ready`
- `ready_with_warnings`
- `not_ready`
- `stale`
- `invalid`
- `unknown`

`unknown` is reserved for curation records that are recognized but cannot be safely classified under the current schema, such as a legacy overlay record that requires manual review before reuse.

## Curated-Map Fallback

If curation is `stale` or `invalid`, the detected content map remains available and the curated state is not silently applied.

## Public-Safe Reports

Public-safe curation reports omit:

- absolute paths
- source paths
- full source text
- full chunk text
- citation text
- proposal text
- private notes
- tokens, keys, and stack traces

## Phase 8R History, Comparison, and Restore

History snapshots are stored separately from the current overlay:

```text
data/source_documents/document_content_curation_history/<document_id>/<revision>.json
data/source_documents/indexes/document_content_curation_history_index.json
```

Actual Phase 8R behavior:

- each effective saved curation revision writes one immutable history snapshot
- duplicate snapshot writes are idempotent when content matches exactly
- conflicting writes for the same document and revision are rejected
- revision listing is per-document and deterministic
- revision comparison reports added, removed, and changed override categories
- restore creates a new current revision; it never rewinds the revision counter
- restore records `restored_from_revision`, `restored_at_utc`, and `previous_current_revision`
- stale or invalid historical revisions can be inspected and compared, but are not restored automatically

Compact desktop controls now expose:

- `View Curation History`
- `Compare Revisions`
- `Restore Revision`
- `Copy Revision Report`

## Phase 8S Manual Stale-Curation Rebase

Rebase workspaces are stored separately from current overlays and immutable history:

```text
data/source_documents/document_content_curation_rebase/<document_id>/<workspace_id>.json
data/source_documents/indexes/document_content_curation_rebase_index.json
```

Actual Phase 8S behavior:

- a rebase workspace can be created from the current stale overlay or one historical revision
- a newly created workspace starts in `draft`; `Detect Conflicts` or the equivalent refresh step performs analysis and transitions it deterministically to `unresolved`, `ready`, `ready_with_warnings`, `invalid`, `stale_again`, or `unknown`
- conflict analysis is deterministic and preserves the source overlay unchanged
- valid unaffected overrides are retained in the proposed rebased state
- blocking conflicts require explicit manual resolution
- supported manual actions are limited to keep/drop/remap/replace operations implemented in the backend
- `document_mismatch` is a distinct blocking conflict when a stale overlay or history record belongs to a different document; it is inspectable but not remappable in this phase
- `malformed_override` is a distinct blocking conflict when one stored override item can still be isolated safely but its structure is unusable; it may be dropped, but it cannot be kept or auto-repaired
- `invalid_chunk_assignment` is a distinct blocking conflict for contradictory or malformed assignment overrides that are not simply missing a chunk or missing a target section
- workspace readiness can be `draft`, `unresolved`, `ready`, `ready_with_warnings`, `stale_again`, `invalid`, `committed`, `abandoned`, or `unknown`
- committing a ready workspace creates a new current curation revision and one immutable history snapshot
- rebase provenance is recorded on the committed overlay and history snapshot
- commit remains blocked while any blocking conflict is unresolved, including `document_mismatch`, `malformed_override`, and `invalid_chunk_assignment`

Compact desktop controls now also expose:

- `Create Rebase Workspace`
- `Load Rebase Workspace`
- `Detect Conflicts`
- `Resolve Conflict`
- `Rebase Readiness`
- `Commit Rebase`
- `Abandon Rebase`
- `Copy Rebase Report`

## Phase 8T Bulk Curation Review

Bulk plans are stored separately from current overlays, history snapshots, and rebase workspaces:

```text
data/source_documents/document_content_bulk/<document_id>/<batch_id>.json
data/source_documents/indexes/document_content_bulk_index.json
```

Actual Phase 8T behavior:

- a new bulk plan starts in `draft`
- plan edits store normalized bulk operations separately from the current curation overlay
- editing an approved plan invalidates prior approval and returns the batch to `draft`
- committed and rejected plans are preserved and cannot be edited through replace or clear operations
- dry-run preview rebuilds a proposed overlay without mutating current curation or history
- supported bulk operations cover manual tag add/remove, chunk assignment/unassignment, chapter and section renames, and chapter and section range corrections
- duplicate equivalent operations are idempotent, while conflicting duplicate operations block review
- whole-plan validation runs after per-operation validation and can mark the batch `ready_for_review`, `unchanged`, `invalid`, or `stale`
- approval is explicit and binds to one batch revision and one preview fingerprint
- rejection preserves the plan and blocks commit
- clear operations resets stored plan operations, preview, validation, counts, warnings, blockers, and approval metadata without touching current curation or history
- commit is all-or-nothing and creates exactly one new curation revision and one immutable history snapshot
- bulk provenance is recorded on the committed curation overlay

Compact desktop controls now also expose:

- `Create Bulk Plan`
- `Load Bulk Plan`
- `Add Operation`
- `Remove Operation`
- `Replace Operation`
- `Clear Operations`
- `Preview Bulk Plan`
- `Validate Bulk Plan`
- `Review Queue`
- `Approve Bulk Plan`
- `Reject Bulk Plan`
- `Commit Bulk Plan`
- `Copy Bulk Report`

## Phase 8U Transactional Commit and Recovery

Transaction journals are stored separately from overlays, history, rebase workspaces, and bulk plans:

```text
data/source_documents/document_content_transactions/<document_id>/<transaction_id>.json
data/source_documents/indexes/document_content_transaction_index.json
data/source_documents/document_content_recovery_plans/<document_id>/<plan_id>.json
```

Actual Phase 8U behavior:

- direct curation saves, history restores, rebase commits, and bulk commits create a journal before authoritative overlay mutation
- journals record expected prior and new revision, safe overlay state, commit fingerprint, workflow linkage where applicable, and checkpoint progress
- write checkpoints are tracked across `prepared`, `overlay_written`, `history_written`, `source_status_written`, `indexes_reconciled`, `committed`, `recovering`, `recovered`, `conflict`, `failed`, `abandoned`, and `unknown`
- a prepared journal may be explicitly abandoned only while no authoritative mutation has been verified; abandonment preserves the journal and records `abandoned_at_utc`
- integrity scans detect incomplete or unfinalized transactions, missing derived-index entries, `overlay_revision_behind_history`, `duplicate_conflicting_history_revision`, and `transaction_missing_workflow_record`
- `overlay_revision_behind_history` is scan-only and blocks automatic repair; the scan does not promote older or newer overlay state automatically
- `duplicate_conflicting_history_revision` is a critical manual-review condition; automatic recovery is prohibited while competing authoritative records exist
- `transaction_missing_workflow_record` distinguishes prepared journals that may be abandoned from mutated commits that require manual review because the originating bulk plan or rebase workspace is missing
- recovery plans are dry-run-first and apply only deterministic reconciliation steps such as writing a missing matching history snapshot, completing missing workflow committed status, and rebuilding derived indexes
- unrecoverable integrity conditions persist `manual_review_required` on the recovery plan rather than collapsing into a generic success or failure state
- recovery is idempotent and does not rewrite detected maps or historical snapshots
- journaled recovery provides recoverable multi-file consistency; it does not claim single-file atomicity across all records

Compact desktop controls now also expose:

- `Scan Integrity`
- `View Pending Transactions`
- `Build Recovery Plan`
- `Load Recovery Plan`
- `Apply Recovery Plan`
- `Abandon Prepared Transaction`
- `Rebuild Indexes`
- `Copy Integrity Report`

## Deferred

P1 deferred by timebox:

- drag-and-drop ordering
- bulk edits
- curation history timeline
- cross-document taxonomy

P2 not attempted by policy:

- AI correction
- semantic grouping
- embeddings
- PDF viewport work

## Targeted Testing Policy

Only the focused curation test file is run in this phase. Broad project-wide test runs are intentionally skipped.
