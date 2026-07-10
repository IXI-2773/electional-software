# Autonomous PDF Certification

Phase 9J adds a guarded single-PDF orchestrator in [backend/electional/autonomous_pdf_certification.py](/C:/Users/Drago/Documents/Codex/2026-05-26/need-to-connectt-my-github-to/backend/electional/autonomous_pdf_certification.py).

Supported scope:

- one `document_id`
- one current `source_revision`
- native-text `clean_digital_pdf`
- native-text `complex_digital_pdf`

Blocked scope:

- OCR
- image-only PDFs
- cross-PDF processing
- cross-revision mixing
- automatic supersession
- scoring, objective-pack, Fast Lane, or replay execution

Storage:

- plans and runs: `data/source_documents/autonomous_pdf_runs/`
- receipts: `data/source_documents/autonomous_pdf_receipts/`
- indexes: `data/source_documents/indexes/autonomous_pdf_run_index.json`
- indexes: `data/source_documents/indexes/autonomous_pdf_receipt_index.json`

Implemented backend flow:

1. `build_autonomous_pdf_workspace`
2. `build_autonomous_pdf_plan`
3. `run_autonomous_pdf_pipeline`
4. `cancel_autonomous_pdf_pipeline`
5. `format_autonomous_pdf_report`

Runtime behavior:

- readiness is derived from source record, manifest, extracted native text, page diagnostics, structure summary, and chunk availability
- unsupported native-text states return explicit blockers
- plans are stale when the current source revision or manifest fingerprint changes
- candidate discovery is bounded by stored plan limits
- ambiguous or near-duplicate items are preserved as blocked items
- non-rule proposal outcomes are preserved without forced activation
- runtime contract failure triggers the existing activation rollback path and records the blocked item
- a completed run writes one immutable autonomous receipt
- rerunning a completed plan returns `already_completed` instead of duplicating the run result

Desktop controls added in the PDF intake / viewport area:

- `Load Autonomous Workspace`
- `Build Autonomous Plan`
- `Run / Resume AUTO`
- `Cancel Autonomous Run`
- `Autonomous Health`
- `Copy Autonomous Report`

Deferred in this pass:

- OCR
- automatic evidence guessing
- cross-document autonomous harvest
- broad repository rule processing
- automatic supersession
