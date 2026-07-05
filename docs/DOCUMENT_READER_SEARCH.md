# Document Reader and Search

Phase 8C adds a controlled local reader/search layer for already-registered source PDFs.

## Flow

```text
Register PDF -> Run Preflight -> Extract Text -> Chunk Text -> Build Page Diagnostics -> Search -> Create Manual Proposal or Citation
```

The reader uses controlled extracted text and chunk JSON. It does not search raw PDFs, run OCR, use AI, create embeddings, promote rules, alter scoring, or change Fast Lane.

## Page Diagnostics

Page diagnostics are built only when extracted text contains page markers such as `--- Page 1 ---`. If page markers are missing, diagnostics return `page_text_unavailable`; page numbers are not fabricated.

Diagnostics include page status, character count, word count, line count, quality score, flags, top keyword counts, and warnings.

## Search Modes

Supported modes:

- `keyword`: any keyword count scoring.
- `exact_phrase`: exact phrase matching.
- `all_terms`: every term must appear.
- `any_terms`: at least one term must appear.

Search works on controlled chunk records and returns short snippets only. Results are sorted deterministically by score, page, and chunk ID.

## Search Result Actions

A user action can create a manual proposal or citation from a search result. These actions still do not activate rules or change scoring. Proposals remain `pending_review`; citations remain source records only.

## Citation Snippets

Citation snippets are short excerpts linked to `document_id` and `chunk_id`. If the preflight privacy scan found sensitive patterns, snippets redact email-like values, token-like values, and local paths.

## Privacy

Public-safe output may include counts, statuses, IDs, warning categories, and health status. It must not include full extracted text, chunk text, exact emails, exact tokens, exact local paths, private notes, source paths, or extracted text paths.

## Targeted Testing

Use targeted tests only:

```powershell
.\.venv\Scripts\python.exe scripts/run_targeted_tests.py --file backend/tests/test_document_reader_search.py
```

Broad project-wide test discovery is skipped by policy unless explicitly requested.

## Phase 8D Desktop Review Workflow

The desktop PDF Intake panel now supports a selected-result review flow:

```text
Search Chunks -> Select Result -> Inspect Snippet -> Open Chunk/Page -> Copy Snippet -> Create Proposal/Citation -> Mark Feedback
```

Search controls use the same backend `search_document` modes: `keyword`, `exact_phrase`, `all_terms`, and `any_terms`. Results are real chunk search results and are never fabricated. Selecting a new query clears the old selected result.

Selected-result actions are manual only:

- `Open Chunk` shows controlled chunk text in the local review panel.
- `Open Page` shows page text only when page markers are available.
- `Copy Snippet` copies the redaction-safe selected snippet.
- `Create Proposal` requires a user-entered claim and creates a `pending_review` proposal.
- `Create Citation` requires a user-entered note and creates a source citation only.
- `Mark Useful` and `Bad Extraction` store review feedback under controlled source-document storage.

These actions do not create production rules, change scoring, alter Fast Lane, touch objective packs, or search raw PDFs.

## Phase 8E Proposal Governance

Search-result proposals now flow into a proposal review queue. Citation strength, duplicate checks, possible conflict checks, review notes, and promotion readiness are stored separately from production rules. No proposal or citation is promoted automatically.
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
