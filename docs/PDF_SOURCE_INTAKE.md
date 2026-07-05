# PDF Source Intake

Phase 6 adds controlled PDF source-document intake for local, text-based PDFs.

## What It Does

- Registers a selected `.pdf` as a private local source document.
- Computes deterministic metadata: document ID, SHA-256 hash, file size, timestamps, and extraction status.
- Copies PDFs into controlled storage by default.
- Extracts text from text-based PDFs when `pypdf` is installed.
- Saves extracted text for manual review.

## What It Does Not Do

- No OCR.
- No Tesseract or image processing.
- No automatic chart import.
- No automatic parsing into election inputs.
- No mutation of existing chart, search, or reliability records.

## Storage

Controlled files live under:

```text
data/source_documents/
  pdf_sources/
  extracted_text/
  indexes/
  quarantine/
```

The index file is:

```text
data/source_documents/indexes/source_document_index.json
```

PDF source records are private by default. Public-safe exports omit original paths, stored PDF paths, and extracted text paths.

## Status Values

```text
registered
extracted
needs_ocr_not_supported
extractor_unavailable
invalid_pdf
read_error
```

`needs_ocr_not_supported` means the PDF likely contains scanned/image content or otherwise has no extractable text. OCR is intentionally deferred.

## Targeted Testing

Use targeted tests only:

```powershell
python scripts/run_targeted_tests.py --file backend/tests/test_pdf_source_intake.py
python scripts/run_targeted_tests.py --file backend/tests/test_desktop_ui.py
```

Broad project-wide test discovery is skipped by policy unless explicitly requested.

## Phase 6B Knowledge Layer

After text extraction, the controlled knowledge layer can chunk extracted text, search stored chunks, and create manual proposals or citations for review. See `docs/PDF_SOURCE_KNOWLEDGE_LAYER.md`.

The knowledge layer still does not perform OCR, AI extraction, automatic parsing, rule promotion, scoring changes, or Fast Lane changes.

## Document Preflight

Before trusting extraction quality, run document preflight. Preflight checks file safety, text-vs-scanned format, metadata/title quality, keyword counts, quality scores, and privacy warnings. See `docs/DOCUMENT_PREFLIGHT.md`.

A `BLOCK` preflight refuses extraction unless an explicit override is used. `WARNING` allows extraction with review.

## Phase 8B PDF Intake UI Flow

The intake page now shows a richer `Document Preflight` panel after registration. It includes:

- verdict and status
- source format and OCR-needed indicator
- page, text-page, and empty-page counts
- extraction quality, chunk readiness, and citation readiness
- warning and blocker categories
- top keyword counts
- privacy category summary and public-export safety
- recommended action

Before preflight runs, the page shows `NOT RUN` and `Unknown` scores. The desktop Extract Text action is intentionally stricter than the backend compatibility path: it asks for preflight first, blocks `BLOCK` verdicts, and allows `WARNING` only with visible caution.

`Copy Preflight Summary` copies a plain-text report that omits local paths, full extracted text, chunk text, exact emails, exact tokens, and exact private values.

## Phase 8C Reader and Search

After extraction and chunking, use the document reader/search layer to build page diagnostics, inspect reader state, search chunks, and create manual proposal or citation records from selected search results. The search layer uses controlled extracted text and chunk indexes; it does not search raw PDFs or create rules automatically. See `docs/DOCUMENT_READER_SEARCH.md`.

## Phase 8D Search Result Review

The PDF Intake page includes a compact Document Reader / Search section. Use it after extraction and chunking. Search results must be selected before any review action can run. Proposal and citation buttons require a selected result plus a manual user note; they never run automatically.

## Phase 8E Proposal Review Queue

The PDF Intake page includes a compact Proposal Review Queue action. It summarizes pending review items and recommended action. Approval in this queue means approved for later human promotion review only; it does not create production rules.
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
## Phase 8G Structure Analysis

Document structure analysis can now build a deterministic map from controlled extracted text. It marks headings, sections, TOC candidates, repeated header/footer noise, possible tables, possible figures, footnotes, references, chunk quality, and re-chunk recommendations. It does not apply re-chunking automatically and does not create proposals, citations, rules, Fast Lane changes, or scoring changes.
## Phase 8H Evidence Binder

Evidence binders group proposal-linked citations across documents, summarize source reliability, score citation bundle strength, flag deterministic support/conflict evidence, report weak or stale sources, and produce public-safe binder summaries. Evidence binders are review aids only: they do not create citations, create proposals, promote rules, mutate scoring, or touch Fast Lane.
## Phase 8I Source Reliability Manager

Source reliability records can now be edited, recalculated, versioned through history events, linked to replacement sources, checked for duplicate source identities, summarized in a quality dashboard, and used to refresh evidence binders. Reliability remains advisory only and does not mutate rules, scoring, Fast Lane, proposals, or citations.

## Source Corpus Manager

Phase 8J adds a Source Corpus Manager for registered documents. It inventories controlled sources, detects missing pipeline steps, reports corpus health, builds dry-run batch plans, lists failed/duplicate/superseded source queues, and creates public-safe corpus reports. It does not crawl folders, run OCR/AI/semantic search, or mutate rules/Fast Lane/scoring.
