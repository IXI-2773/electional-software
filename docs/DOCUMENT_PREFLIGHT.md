# Document Preflight

Phase 8 adds a preflight scan before trusting PDF extraction quality.

## Verdicts

- `PASS`: text-based PDF, no blockers, extraction quality is usable.
- `WARNING`: extraction can proceed, but review is required.
- `BLOCK`: extraction should not proceed unless explicitly overridden.
- `UNKNOWN`: the scanner could not determine enough, usually because the extractor is unavailable.

## Checks

Preflight checks:

- file existence, extension, size, readability, and SHA-256 hash
- corrupt or encrypted PDFs
- text-based, scanned-like, or mixed PDF classification
- page count and text density
- likely font or encoding problems
- metadata and title detection
- project keyword counts
- extraction, chunk, and citation readiness scores
- privacy patterns such as emails, local paths, token-like strings, and phone-like values

## Not Supported

- OCR
- AI extraction
- semantic search
- automatic proposals
- automatic citations
- rule promotion

## Privacy

Public-safe preflight output may include verdicts, scores, warning categories, hashes, and counts. It must not include full text, local paths, private notes, or exact sensitive values.

## Testing

Use targeted tests only:

```powershell
python scripts/run_targeted_tests.py --file backend/tests/test_document_preflight.py
```

Broad project-wide test discovery is skipped by policy unless explicitly requested.

## Phase 8B Intake Controls

The PDF Intake page now treats preflight as the normal gate before extraction:

```text
Choose PDF -> Register Source -> Run Preflight -> Review Summary -> Extract Text -> Chunk Text
```

The compact summary is safe for UI display. It shows verdict, status, format, OCR need, page counts, quality bands, warning/blocker categories, top keyword counts, privacy categories, public-export safety, and a recommended action. If preflight has not run, scores are shown as `Unknown`, not zero or pass.

Extraction gate behavior:

- `NOT_RUN`: backend extraction remains backward-compatible with a warning, but the desktop intake page asks the user to run preflight first.
- `PASS`: extraction is allowed normally.
- `WARNING`: extraction is allowed with visible caution; chunks must be reviewed before proposals or citations.
- `BLOCK`: extraction is refused unless an explicit backend override is used.
- `UNKNOWN`: extraction should not be trusted without review or override.

Privacy summaries list categories only, such as `email_like_pattern_detected` or `local_path_detected`. They do not show exact emails, paths, tokens, or extracted text.

Keyword counts are review aids only. They do not create proposals, citations, rules, scoring changes, objective-pack changes, or Fast Lane changes.

## Phase 8C Rich Report Detail

The plain-text preflight report now includes low-density page counts plus explicit `Unavailable` labels for scanned-like and image-heavy page counts when those diagnostics are not available. Keyword output is labeled as `Top Keywords` and remains a review aid only.
## Phase 8G Structure Analysis

Document structure analysis can now build a deterministic map from controlled extracted text. It marks headings, sections, TOC candidates, repeated header/footer noise, possible tables, possible figures, footnotes, references, chunk quality, and re-chunk recommendations. It does not apply re-chunking automatically and does not create proposals, citations, rules, Fast Lane changes, or scoring changes.
