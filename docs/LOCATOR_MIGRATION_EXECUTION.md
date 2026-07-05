## Locator Migration Execution

Phase 8V adds controlled execution on top of the non-destructive locator migration planner.

### Scope

- Executes one `safe_candidate` proposal at a time.
- Requires a current migration plan, a current proposal before-state, and explicit `APPLY` for live writes.
- Supports dry-run validation and write-set preview without mutating source records.
- Writes one locator-bearing primary record update, updates cached binder `linked_citations` snapshots when they embed the migrated citation locator, and creates one pending source-impact/revalidation queue item.
- Creates an execution receipt and verified backup set for live execution.
- Supports verified rollback with explicit `ROLLBACK`, including reversal linkage for the original revalidation item.

### Storage

- Receipts: `data/source_documents/locator_migration_execution_receipts/`
- Backups: `data/source_documents/locator_migration_backups/`
- Index: `data/source_documents/indexes/locator_migration_execution_index.json`

### Public Functions

- `validate_locator_migration_execution(...)`
- `build_locator_migration_write_set(...)`
- `execute_locator_migration_proposal(...)`
- `load_locator_migration_execution_receipt(...)`
- `list_locator_migration_execution_receipts(...)`
- `rollback_locator_migration_execution(...)`
- `get_locator_migration_execution_health(...)`
- `format_locator_migration_execution_report(...)`

### API Wrappers

- `validate_locator_migration_execution(...)`
- `execute_locator_migration_proposal(...)`
- `load_locator_migration_execution_receipt(...)`
- `rollback_locator_migration_execution(...)`
- `format_locator_migration_execution_report(...)`

### Desktop UI

The PDF intake panel includes a compact `Locator Migration Execution` section with:

- `Validate Execution`
- `Execute One Proposal`
- `Load Receipt`
- `Rollback Execution`
- `Execution Health`
- `Copy Execution Report`

Live execution requires `APPLY`. Rollback requires `ROLLBACK`. Dry run defaults on.
