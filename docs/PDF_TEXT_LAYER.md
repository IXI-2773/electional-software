## Phase 8Y

Phase 8Y adds native PDF text-layer extraction on top of the certified Phase 8X viewport. It extracts exactly one current viewport page at a time, preserves native PDF coordinates, maps canonical locators to native rectangles when deterministic evidence exists, and supports one-page visible text selection plus copy-safe text extraction.

## Native Text Layer Requirement

The implementation depends on the PDF's existing native text layer. If the renderer cannot expose native word geometry, the result is `text_layer_unavailable`. OCR, image analysis, and semantic guessing are deferred.

## Renderer Capability

`get_pdf_text_layer_capability()` reports renderer availability, renderer identity, word/span support, and warnings. Character-box extraction is not implemented in this phase.

## Storage

Text-layer records and overlay geometry use controlled storage only:

- `data/source_documents/pdf_text_layers/`
- `data/source_documents/pdf_overlay_cache/`
- `data/source_documents/indexes/pdf_text_layer_index.json`

Writes use atomic JSON replacement. Cache identity includes document ID, source revision, source hash, page number, renderer name, renderer version, and text-layer schema version. Cache identity does not include zoom.

## Page Text-Layer Records

`extract_pdf_page_text_layer()` loads the current certified viewport session, resolves the controlled PDF internally, extracts exactly one page, normalizes deterministic word order, and stores half-open character ranges `[start_char, end_char)`.

## Coordinate System

The text layer preserves native PDF point coordinates. Overlay building converts:

1. PDF point rectangles
2. rendered image pixel rectangles
3. visible canvas rectangles in the viewer

The transform uses current page dimensions and rendered image dimensions. It does not hardcode DPI.

## Locator Mapping Priority

`map_pdf_locator_to_rectangles()` uses this deterministic order:

1. exact page character offsets
2. exact selected text hash with one unique match
3. exact selected text with one unique match
4. unmappable

Ambiguous matches are reported as `ambiguous`. Cross-document and stale locators are blocked explicitly. No fuzzy matching is used.

## Highlight Overlays

`build_pdf_highlight_overlay()` creates geometry-only overlays for `search`, `citation`, or `selected_locator`. It deduplicates identical rectangles, reports unmappable locators, and does not modify the PDF or source records.

## Visible Selection

`select_pdf_text_in_rectangle()` converts one visible selection rectangle back into PDF coordinates, selects intersecting or fully contained native words in deterministic order, and returns selected text plus stable offset metadata. Selection is limited to one current page.

## Copy-Safe Extraction

`format_pdf_text_selection()` returns only the selected native text by default. Optional locator output includes document ID, revision, page, and offsets. Public-safe output omits paths, cache details, stack traces, and unselected page text.

## Zoom and Page Changes

Text-layer cache is revision-aware and zoom-independent. Page changes require a different text-layer record. Viewer overlays are cleared on page navigation and can be rebuilt for the current page. Zoom changes use the same PDF rectangles and recalculate image-space overlay geometry.

## Health and Reporting

`get_pdf_text_layer_health()` checks renderer capability, cache readability, malformed word boxes, invalid character ranges, and duplicate text-layer IDs without rebuilding caches automatically. `format_pdf_text_layer_report()` is public-safe and omits private paths and full page text.

## Deferred

Deferred by timebox:

- multi-page selection
- cross-page highlights
- persistent annotations
- PDF modification

Not attempted by policy:

- OCR
- semantic matching
- guessed rectangles
