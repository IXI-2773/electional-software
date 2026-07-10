# Autonomous PDF Remediation

Phase 9L converts one failing Phase 9K benchmark result for one PDF revision into bounded remediation work.

Scope:

- one `benchmark_result_id`
- one `document_id`
- one `source_revision`
- deterministic triage into remediation cases
- human review decisions
- verification against one later Phase 9K result for the same revision

Phase 9L does not automatically repair code, source documents, manifests, rules, or thresholds.

## Storage

- `data/source_documents/autonomous_pdf_remediation_plans/`
- `data/source_documents/autonomous_pdf_remediation_cases/`
- `data/source_documents/autonomous_pdf_remediation_receipts/`
- `data/source_documents/indexes/autonomous_pdf_remediation_plan_index.json`
- `data/source_documents/indexes/autonomous_pdf_remediation_case_index.json`
- `data/source_documents/indexes/autonomous_pdf_remediation_receipt_index.json`

## Triage rules

- Triage requires confirmation `TRIAGE`.
- Triage blocks on missing, stale, or provenance-mismatched benchmark results.
- Cases are grouped within one document and one revision only.
- Rule-candidate mismatches remain separate from activation and certification.
- Critical safety evidence is prioritized ahead of quality failures.

## Root-cause discipline

- Root causes are limited to the documented controlled classifications.
- When benchmark evidence is insufficient, the case remains `unresolved`.
- Phase 9L records recommended corrective routes only. It does not execute them.

## Review and verification

- Review requires confirmation `REVIEW`.
- Review creates an immutable receipt and does not mutate pipeline records.
- Verification requires confirmation `VERIFY`.
- Verification compares reviewed cases against one later benchmark result for the same PDF revision.
- Case outcomes are `resolved`, `partially_resolved`, `persists`, `regressed`, `unavailable`, or `stale`.
- Resolution depends on mismatch identities and safety evidence, not aggregate metric improvement alone.

## Idempotency and staleness

- Identical triage returns `already_triaged` with zero writes.
- Identical verification returns `already_verified` with zero writes.
- Plans become stale when the underlying benchmark provenance or revision changes.

## Health and reporting

- Health checks inspect indexes, relationships, duplicate IDs, stale plans, and unresolved critical cases.
- Public-safe reports include document/revision scope, case counts, status summaries, and metric deltas.
- Reports omit paths, PDF text, citation text, proposal content, rule payloads, stack traces, and secrets.
