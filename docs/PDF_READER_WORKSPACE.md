## Phase 8Z

Phase 8Z adds a revision-bound reader workspace on top of the certified PDF viewport and native text-layer selection flow. The workspace stores bookmarks, overlay-only annotations, selection-derived citation drafts, and the active controlled reading context without modifying the PDF or creating real citation records.

## Workspace Purpose

The reader workspace preserves controlled PDF reading state for one registered document revision at a time. Each workspace belongs to one document ID, one source revision, one source hash, and one current certification validation.

## Revision-Bound Behavior

Workspaces are stored in:

- `data/source_documents/pdf_reader_workspaces/`
- `data/source_documents/indexes/pdf_reader_workspace_index.json`

Workspace IDs are revision-bound by document and source revision. If a matching current workspace already exists for the same document revision, it is returned instead of duplicated. A newer source revision does not overwrite an older workspace.

## Bookmarks

Bookmarks are validated against the workspace document and revision. A bookmark may optionally carry a locator, but that locator must match document, revision, and page. Exact duplicate bookmarks are idempotent and do not increment workspace revision.

## Annotation Types

Allowed annotation types are:

- `highlight`
- `underline`
- `note`
- `selection_reference`

Annotations are overlay-only records. They store validated PDF rectangles and optional notes or locator metadata. They do not alter PNG caches or PDF bytes.

## Selection Provenance

Phase 8Y selections can be used to create citation drafts only when the selection document, revision, page, offsets, text hash, and bounding box remain valid for the current workspace.

## Citation Draft Behavior

Citation drafts remain reader-workspace items with status `draft`. They do not create real citation records, do not touch evidence binders, and do not create proposal records.

## Workspace Revisions

`workspace_revision` increments only for effective persistent changes:

- new bookmark
- new annotation
- new citation draft

Load, listing, reports, overlay reconstruction, and exact duplicate bookmark saves do not increment workspace revision.

## Overlay Reconstruction

The workspace overlay builder filters saved items to the current page only, converts saved PDF rectangles through the existing Phase 8Y geometry transform, and returns geometry for viewer redraw. Temporary search/citation overlays remain separate from persistent workspace overlays.

## Page and Zoom Behavior

Saved workspace overlays are page-scoped. Page changes reload current-page saved items only. Zoom changes re-render the page and recompute image-space geometry from the saved PDF rectangles.

## Staleness

Workspaces become stale when the current source revision, source hash, or certification currentness no longer matches the stored workspace state. Stale workspaces are reported explicitly and are not migrated automatically.

## Public-Safe Reporting

Workspace reports exclude private paths, cache paths, full selected citation text, stack traces, and citation repository contents. Reports summarize counts and current status only.

## Deferred

Deferred by timebox:

- real citation creation or submission
- proposal creation from selection
- cross-page annotations
- multi-page selection
- annotation history
- workspace sharing

Not attempted by policy:

- OCR
- PDF modification
- collaboration workflows

## Targeted Testing Policy

Phase 8Z uses one focused test file:

- `backend/tests/test_pdf_reader_workspace.py`

The focused tests verify revision binding, bookmark idempotency, annotation validation, selection-to-draft behavior, current-page overlay filtering, and the guarantee that no real citation repository record is created.
