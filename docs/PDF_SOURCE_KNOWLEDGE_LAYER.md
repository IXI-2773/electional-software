# PDF Source Knowledge Layer

Phase 6B builds on controlled PDF intake. It turns extracted text into searchable source chunks and lets a human attach proposals and citations to those chunks.

## Workflow

1. Register a PDF with `register_pdf_source`.
2. Extract text with `extract_pdf_text`.
3. Chunk the extracted text with `chunk_source_document`.
4. Search chunks with `search_source_chunks`.
5. Create a manual proposal from a chunk with `create_manual_source_proposal`.
6. Create a citation from a chunk with `create_source_citation`.
7. Check storage and review status with `get_source_knowledge_health`.

## Storage

Everything stays under:

```text
data/source_documents/
  chunks/
  proposals/
  citations/
  indexes/
  quarantine/
```

Indexes:

```text
data/source_documents/indexes/chunk_index.json
data/source_documents/indexes/proposal_index.json
data/source_documents/indexes/citation_index.json
```

## Safety Rules

- Chunks are made only from already extracted text.
- Search reads stored chunk records, not raw PDFs.
- Proposals do not become rules.
- Citations do not become rules.
- Nothing changes scoring, Fast Lane, objective packs, or production rule behavior.
- Public-safe output must not include local paths, full chunk text, private notes, or extracted text paths.

## Not Supported Yet

- OCR.
- AI extraction.
- Semantic search.
- Embeddings.
- Automatic proposal generation.
- Automatic citation generation.
- Rule promotion.
- Source-backed production rules.

## Targeted Tests

Use targeted tests only:

```powershell
python scripts/run_targeted_tests.py --file backend/tests/test_pdf_source_knowledge_layer.py
```

Broad project-wide test discovery is skipped by policy unless explicitly requested.
