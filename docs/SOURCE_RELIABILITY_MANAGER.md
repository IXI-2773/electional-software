# Source Reliability Manager

Phase 8I adds source reliability management for controlled source documents.

Reliability metadata is advisory only. It does not promote proposals, mutate rules, change scoring, touch Fast Lane, create citations, or create proposals.

## Managed Metadata

Editable fields include:

- source type
- authority level
- publication date
- modified date
- manual title
- author / publisher
- version label
- jurisdiction
- source URL label
- reliability notes

Dates must be explicit ISO dates. The system does not fabricate publication dates, modified dates, titles, authors, or authority levels.

## History

Reliability updates append compact history events under:

```text
data/source_documents/source_reliability_history/
data/source_documents/indexes/source_reliability_history_index.json
```

History stores changed-field summaries, not full source text or local file paths.

## Relationships

Sources can be related with controlled relationship records:

- replaced_by
- supersedes
- newer_version_of
- older_version_of
- duplicate_of
- related_source

Relationships do not delete old sources, rewrite citations, or mutate evidence binders automatically.

## Dashboard

The source quality dashboard summarizes strong, usable, weak, unknown, stale, duplicate, and superseded sources. It omits local paths and full source text.

## Binder Refresh

Evidence binders using a source can be listed and refreshed after metadata changes. Refresh recalculates binder summaries only. It does not create citations, proposals, rules, or promotions.

## Unsupported

OCR, AI extraction, semantic matching, automatic trust decisions, automatic source deletion, automatic duplicate merge, automatic proposal/citation creation, rule promotion, Fast Lane changes, and scoring changes are unsupported.

## Targeted Testing

Use:

```text
scripts/run_targeted_tests.py --file backend/tests/test_source_reliability_manager.py
```

Do not run broad project-wide discovery for source reliability manager work.

## Corpus Manager Link

Phase 8J adds corpus-level reliability control. The corpus manager can dry-run bulk reliability rechecks, list stale/duplicate/superseded source queues, and include reliability coverage in public-safe corpus reports. It does not auto-trust, auto-delete, auto-merge, promote proposals, mutate rules, touch Fast Lane, or change scoring.
