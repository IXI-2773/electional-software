# Document Structure Analysis

Phase 8G adds deterministic structure analysis for controlled source documents after text extraction.

It reads only controlled extracted text and existing chunk records under `data/source_documents/`. It does not search raw PDFs, run OCR, use AI, create proposals, create citations, promote rules, change Fast Lane, or change scoring.

## What It Builds

Storage is kept under:

```text
data/source_documents/structure_maps/
data/source_documents/cleaned_text/
data/source_documents/rechunk_plans/
data/source_documents/indexes/structure_map_index.json
data/source_documents/indexes/cleaned_text_index.json
data/source_documents/indexes/rechunk_plan_index.json
```

## Cleanup

`normalize_extracted_page_text` saves cleaned page text separately. It preserves page boundaries and original extraction output. Cleanup is conservative:

- collapsed repeated whitespace
- normalized line breaks
- repaired hyphenated line breaks
- preserved page-level text for citation lookup

## Structure Map

`build_document_structure_map` runs heuristic detectors for:

- repeated headers and footers
- headings and sections
- table-of-contents candidates
- possible tables
- possible figures
- possible footnotes
- references or bibliography sections
- chunk quality

All layout detections are labeled heuristic and include low, medium, or high confidence where relevant. The analyzer does not claim exact PDF layout parsing.

## Chunk Quality

`analyze_chunk_quality` reports short/long chunks, missing page references, header/footer noise, low-quality chunks, and duplicate chunks. It does not delete or overwrite chunks.

## Re-Chunk Recommendations

`recommend_rechunk_plan` returns advisory strategies only:

- `keep_existing`
- `section_aware_chunking`
- `page_aware_chunking`
- `paragraph_aware_chunking`
- `manual_review_required`

Recommendations are not applied automatically. Old chunk records are never deleted by this layer.

## Unsupported

OCR, AI extraction, semantic search, table row parsing, figure extraction, automatic citation creation, automatic proposal creation, and rule promotion are not supported in this phase.

## Testing Policy

Use targeted tests only:

```text
scripts/run_targeted_tests.py --file backend/tests/test_document_structure_analysis.py
```

Do not run broad project-wide test discovery for this work.
