# Autonomous PDF Benchmark

Phase 9K adds a controlled benchmark layer for the Phase 9J single-PDF autonomous pipeline.

Scope:

- one benchmark manifest
- one `document_id`
- one `source_revision`
- one final Phase 9J autonomous run
- one immutable benchmark result
- one immutable benchmark receipt

This phase measures quality. It does not repair, tune, or rerun the pipeline automatically.

## Relationship to Phase 9J

Phase 9J executes:

- document readiness
- harvesting
- citations
- proposals
- rule activation
- runtime validation
- certification

Phase 9K evaluates that completed run against an independent controlled benchmark manifest.

## Independent ground truth

Benchmark manifests must be independently authored.

Rejected cases include:

- autonomous-output-derived manifests
- stale source revision manifests
- source hash mismatch
- duplicate expected identities
- unsupported schema

## Supported benchmark types

- `clean_digital_pdf`
- `complex_digital_pdf`
- unsupported rejection benchmarks for image-only or otherwise non-autonomous PDFs

Focused fixtures do not prove production accuracy. They only verify deterministic comparison behavior.

## Stable expected identities

- section anchor: page number + normalized heading + locator
- citation: document + revision + page/chunk locator + selected-text hash
- proposal: citation support + target/scope/condition/operator/value fingerprint
- rule: canonical rule behavior fingerprint
- blocker: candidate id + blocker code + blocked stage

Generated record ids are not the primary match key.

## Stage comparisons

The benchmark compares:

- native-text page coverage
- section-anchor recall and locator validity
- citation precision and recall
- proposal precision and recall
- rule activation precision
- certification correctness
- blocker accuracy
- contamination and uncertified-active-rule safety checks

Zero denominators produce `null`, not zero.

## Release gates

Policy id:

- `native_pdf_benchmark_policy_v1`

Clean PDFs and complex PDFs use separate recall thresholds, but safety stays strict for both:

- rule activation precision must remain `1.00`
- certification correctness must remain `1.00`
- cross-document contamination must remain zero
- cross-revision contamination must remain zero
- uncertified active rules must remain zero

Critical safety violations override average metrics and force a safety failure.

## Results and receipts

Storage:

- `data/source_documents/autonomous_pdf_benchmark_manifests/`
- `data/source_documents/autonomous_pdf_benchmark_results/`
- `data/source_documents/autonomous_pdf_benchmark_receipts/`
- `data/source_documents/indexes/autonomous_pdf_benchmark_manifest_index.json`
- `data/source_documents/indexes/autonomous_pdf_benchmark_result_index.json`
- `data/source_documents/indexes/autonomous_pdf_benchmark_receipt_index.json`

Results store deterministic metrics and mismatch localization.

Receipts are append-only summaries without private source payloads.

## Idempotency and staleness

An identical benchmark manifest and identical final autonomous run return:

- `already_benchmarked`

Results become stale when the benchmark manifest fingerprint, autonomous run fingerprint, release policy, or comparison schema changes.

## Health checks

Health checks verify:

- manifest, result, and receipt index readability
- duplicate ids
- stale benchmark results
- critical safety violation counts
- impossible metric values

Health checks do not run Phase 9J and do not mutate pipeline records.

## Public-safe reporting

Reports omit:

- absolute paths
- full PDF text
- private citation text
- proposal content
- rule payloads
- stack traces
- secrets

## Targeted testing policy

Phase 9K uses focused temporary fixtures only.

Allowed test command:

```powershell
.\.venv\Scripts\python.exe scripts/run_targeted_tests.py --file backend/tests/test_autonomous_pdf_benchmark.py
```

Broad project-wide suites remain out of scope for this phase.
