PDF Viewport

Purpose

Phase 8X adds the first controlled PDF-reader foundation. It is limited to certified document gating, controlled source resolution, lightweight viewport sessions, one-page PNG rendering, page navigation, validated zoom, revision-aware render caching, and canonical locator-to-page synchronization.

Certification prerequisite

Viewport access is allowed only when the latest current backend contract validation is:

- `certified`
- `certified_with_warnings`

All other certification states block viewport creation. Phase 8X does not run backend contract validation automatically.

Controlled source resolution

The viewport accepts only a `document_id`. It resolves the PDF internally through the controlled source registry and requires the resolved file to remain inside controlled `pdf_sources` storage. Arbitrary paths, file URLs, and caller-supplied filesystem targets are not accepted.

Renderer capability

Renderer capability is checked through `get_pdf_renderer_capability()`. The current implementation uses PyMuPDF only when it is already installed and callable. If no supported renderer is available, the system reports `pdf_renderer_unavailable` honestly and does not claim that rendering succeeded.

Viewport sessions

Sessions are stored in:

- `data/source_documents/pdf_viewport_sessions/`
- `data/source_documents/indexes/pdf_viewport_session_index.json`

Each session binds to:

- document ID
- source revision
- source hash
- certification validation ID
- certification status
- page count
- current page
- zoom

Sessions are revision-aware and become stale when source revision, source hash, page count, or certification currentness changes.

One-based page numbering

All user-facing page numbers are 1-based. Session creation, navigation, jump handling, and locator synchronization use the 1..page_count range.

Page rendering

`render_pdf_viewport_page()` renders exactly one selected page to PNG, or reuses a valid cache entry when allowed. Rendering is blocked when page numbers are invalid, zoom is unsupported, certification is stale, the renderer is unavailable, or the estimated output would exceed the render safety limit.

Navigation actions

Supported navigation actions:

- `first`
- `previous`
- `next`
- `last`
- `jump`
- `zoom_in`
- `zoom_out`

Boundary navigation never creates an invalid page number. Instead, it preserves the current valid page and returns a warning.

Zoom steps and limits

Allowed zoom steps:

- `25`
- `50`
- `75`
- `100`
- `125`
- `150`
- `175`
- `200`
- `250`
- `300`
- `400`

Only integer zoom steps are accepted.

Render-pixel safety limit

Before rendering, the viewport estimates the output size and blocks oversized allocations above the private safety limit:

- `40,000,000` pixels

This is a guard against unreasonable raster allocations.

Revision-aware cache identity

Render cache identity includes:

- document ID
- source revision
- source hash
- page number
- zoom percent
- renderer name
- renderer version
- render schema version

Cache files are stored in:

- `data/source_documents/pdf_viewport_cache/`

The cache is never reused across source revisions or hash changes.

Cache invalidation

A cache entry is reused only when both the PNG file and matching cache metadata are present and consistent with the current session and renderer identity. Invalid or stale cache state is not trusted silently.

Locator synchronization

`synchronize_pdf_viewport_to_locator()` supports locator fields:

- `document_id`
- `source_revision`
- `page`
- `chunk_id`
- `start_offset`
- `end_offset`

Phase 8X validates the locator, moves the viewport to the correct page, and records the selected locator in session state. It does not highlight the chunk or text range.

Stale locator behavior

If a locator source revision no longer matches the active controlled revision, the viewport returns:

- `locator_status = stale_revision`

Phase 8X does not run locator migration automatically.

Public-safe reporting

Public viewport reports omit:

- absolute PDF paths
- cache paths
- source text
- chunk text
- citation text
- private notes
- stack traces
- secrets

Deferred behavior

Deferred by design:

- visible highlighting
- text selection
- citation overlays
- annotations
- bookmarks
- thumbnail navigation
- continuous scrolling
- rotation
- printing
- OCR

Targeted testing policy

Phase 8X uses one focused file:

- `backend/tests/test_pdf_viewport.py`

The focused tests cover certification gating, controlled source enforcement, one-based session creation, cache reuse, navigation boundaries, zoom and pixel guards, locator synchronization, and the public-safe API/report flow.
