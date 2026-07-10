## Rule Supersession

Phase 9F adds controlled replacement of one certified active canonical rule with one promoted structured replacement proposal.

The supersession flow reuses the Phase 9D.1 canonical mutable rule repository plus the Phase 9D activation and Phase 9E certification records. It does not create a second rule repository, evaluator, or revalidation queue.

### Requirements

- The old rule must exist, be active, and still match its completed activation and certification receipts.
- The replacement proposal must be promoted, carry accepted citation evidence, and explicitly identify the old rule through `supersedes_rule_id`.
- The replacement candidate is built only from structured `rule_mapping` fields.
- The replacement receives a new canonical rule ID and does not inherit the old certification receipt.

### Compatibility

- Exact duplicates are blocked.
- Different rule family or target is blocked as incompatible.
- Scope expansion or contraction is allowed only after explicit acknowledgement during review.
- Approval saves review state only. It does not mutate active rules.

### Persistence

Supersession writes these records atomically with rollback:

- `data/source_documents/rule_supersession_reviews/`
- `data/source_documents/rule_supersession_chains/`
- `data/source_documents/rule_supersession_receipts/`
- `data/source_documents/rule_supersession_backups/`
- matching review, chain, and receipt indexes under `data/source_documents/indexes/`

Successful supersession:

- marks the old rule inactive,
- creates a new active canonical rule,
- enforces exactly one active version in the chain,
- creates one immutable supersession receipt,
- creates one pending `rule_supersession` revalidation item.

### Confirmations

- Supersession requires exact confirmation: `SUPERSEDE`
- Rollback requires exact confirmation: `ROLLBACK_SUPERSESSION`

### Rollback

Verified rollback restores the previous active rule from backup, marks the successor `rolled_back`, preserves the immutable supersession receipt, restores the active version pointer in the chain, and creates a pending rollback revalidation item.

Rollback is blocked after later certification or later supersession state.

### Public-safe reporting

The public-safe report omits:

- absolute paths,
- full proposal content,
- citation text,
- private reviewer notes,
- stack traces,
- secrets.

### Deferred

Still deferred:

- effectiveness analytics,
- historical backtesting,
- automatic supersession recommendation,
- automatic conflict resolution,
- in-place active-rule editing,
- rule merging or splitting,
- batch supersession,
- multi-reviewer approval,
- scoring, objective-pack, Fast Lane, and replay integration.
