# Document Content Map

Phase 8P adds a deterministic content-organization layer for one registered document at a time. It does not render PDF pages and it does not infer semantic meaning with AI.

## Purpose

The document content map provides:

- document-scoped fingerprinting
- chapter and section resolution from existing controlled structure data
- page and chunk range assignment
- deterministic topic tags
- related-content lookup within the selected document
- provenance validation for citations, proposals, binders, and content-map ranges
- reader-backend readiness status

## Document-Scoped Fingerprinting

The content-map layer hashes only records belonging to or referencing the selected document, including:

- source record
- preflight record
- extraction record
- chunks for the document
- page diagnostics
- structure map
- reliability record
- citations for the document
- proposals and proposal reviews linked to those chunks or citations
- evidence binders referencing the document, citations, or proposals
- impact queue items and their resolutions
- the existing content map, when present

Unrelated document records are excluded.

## Chapter and Section Resolution

Resolution uses only existing controlled structure records:

- structure-map headings
- structure-map sections
- TOC candidates already present in the structure map
- chunk page metadata

If chapters cannot be resolved safely, the result falls back to `section_only` or `unknown`. It does not invent chapter titles or ranges.

## Page and Chunk Range Assignment

Sections receive chunk assignments only when chunk page metadata falls inside the known section page range. Chunks outside resolved ranges remain unassigned and are reported explicitly.

## Controlled Topic Tagging

Topic tags are deterministic and come only from:

- caller-supplied topic terms
- normalized chapter titles
- normalized section titles

Matching uses exact normalized phrases and whole-word title terms. No semantic similarity, embeddings, or AI-generated labels are used.

## Related-Content Matching

Related-content lookup is document-scoped and matches only:

- exact topic tags
- exact section titles
- exact chapter titles
- whole-word title keywords

Results are sorted deterministically by match type, chapter order, section order, and page order.

## Provenance Contract

Provenance validation checks:

- citation to chunk linkage
- optional citation revision fields against current source revision
- proposal and review linkage when present
- evidence binder proposal/citation linkage
- content-map section chunk IDs and page ranges
- content-map revision and fingerprint against the current manifest and document-scoped fingerprint

Validation is read-only and does not repair records automatically.

## Reader-Backend Readiness

The final backend gate reports whether the selected document is structurally ready for future PDF-reader integration. Readiness requires current manifest state, extraction, chunks, page diagnostics, structure, content map, current fingerprint, and no critical provenance issues.

## Public-Safe Reports

Public-safe content-map reports omit:

- absolute paths
- source file paths
- source text
- chunk text
- citation text
- proposal text
- private notes
- stack traces
- tokens or keys

## Deferred Work

- P1 deferred by timebox: manual chapter editing, per-chunk tag editing, cross-document topic grouping, batch content-map building, automatic locator migration
- P2 not attempted by policy: PDF viewport, OCR, semantic search, embeddings, AI topic classification

## Targeted Testing Policy

Only the focused Phase 8P test file is intended for this pass:

- `scripts/run_targeted_tests.py --file backend/tests/test_document_content_map.py`

Broad project-wide testing is intentionally skipped in this phase.
