# Corpus Execution Recovery

Phase 8K extends the existing controlled corpus manager with crash-safe execution, bounded retry, checkpoint/resume, and public-safe audit records.

## Execution Storage

Controlled execution records live under `data/source_documents/`:

- `corpus_execution/`
- `corpus_execution_receipts/`
- `corpus_execution_locks/`
- `corpus_checkpoints/`
- `corpus_execution_history/`
- `corpus_audits/`

Repair and recovery records live under:

- `corpus_repairs/`
- `corpus_repair_backups/`
- `corpus_repair_staging/`
- `corpus_quarantine/`

Indexes for those records are stored under `indexes/` with explicit allowlisted filenames.

## Safe Defaults

Execution configuration is fixed to safe defaults:

- `default_dry_run = true`
- `default_limit = 25`
- `maximum_limit = 100`
- `maximum_retries = 2`
- `stale_lock_seconds = 600`
- `require_backup_before_repair = true`
- `verify_backup_hashes = true`
- `verify_rebuilt_index = true`

Unsafe overrides are rejected.

## Batch Execution

Execution follows a deterministic sequence:

1. load and validate a saved batch plan
2. validate controlled document IDs
3. validate per-item dependencies
4. acquire a batch lock
5. build an idempotency key from document state and action options
6. write a started receipt before calling the action
7. finalize the receipt after completion, blocking, skip, or failure
8. atomically update the checkpoint after every final receipt
9. release the lock in cleanup

The executor does not:

- auto-run prerequisites
- mark work complete without a final receipt
- silently rerun matching completed work
- trust only in-memory counters

## Failure Taxonomy

Phase 8K uses these classifications:

- `missing_step`
- `dependency_missing`
- `processing_failure`
- `blocked`
- `unsupported`
- `corrupt_record`
- `interrupted`
- `cancelled`
- `already_completed`
- `skipped_by_policy`
- `stale_execution`
- `rollback_required`
- `unknown`

Missing steps are tracked separately from attempted failures.

## Resume and Retry

- completed idempotency keys are skipped on resume
- interrupted items can be retried explicitly
- blocked dependency items do not consume retry budget
- processing retries stop after the configured maximum
- pause and cancel preserve receipts and checkpoints

## Public-Safe Reporting

Execution reports summarize:

- batch status
- lock status
- receipt counts
- checkpoint validity
- resume availability
- failure counts
- recommended next action

Reports sanitize local paths and do not expose source text.
