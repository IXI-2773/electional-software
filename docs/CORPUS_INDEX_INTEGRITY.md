# Corpus Index Integrity

Phase 8K validates corpus indexes from an explicit registry. It does not discover indexes by crawling arbitrary folders.

## Allowlisted Indexes

The registry covers controlled corpus indexes such as:

- `source_document_index`
- `chunk_index`
- `proposal_index`
- `citation_index`
- `page_diagnostics_index`
- `structure_map_index`
- execution, receipt, lock, checkpoint, repair, backup, and quarantine indexes

Each registry entry declares:

- the index file path
- the controlled record directory
- the record ID field
- the document ID field when applicable
- supported schema versions
- whether the index is optional

## Integrity Checks

Validation is read-only. It checks for:

- missing index files
- invalid JSON
- unsupported top-level shapes
- duplicate index entries
- missing referenced records
- corrupt record files
- record ID mismatches
- document ID mismatches
- unindexed valid records
- unsupported schema versions
- stale temporary files

Severity is reported as `info`, `warning`, or `critical`.

## Repair Planning

Repair planning defaults to dry-run and produces a before/after preview for each affected index:

- `before_entries`
- `planned_after_entries`
- `records_to_add`
- `references_to_omit`
- `records_to_quarantine`

Planned actions are explicit. Unknown issues are left unchanged.

## Repair Safety Rules

Non-dry-run repair requires:

1. a saved repair plan
2. a verified backup manifest
3. hash verification for backup files
4. staged index reconstruction
5. staged validation before replacement
6. live validation after replacement

If live validation fails after replacement begins, rollback restores only the files listed in the backup manifest.

## Quarantine

Corrupt or unsupported controlled records can be quarantined for review. Phase 8K preserves bytes and tracks:

- record type
- record ID
- reason
- hash
- size
- repair linkage when applicable

Quarantine is reviewable and is not auto-deleted.
