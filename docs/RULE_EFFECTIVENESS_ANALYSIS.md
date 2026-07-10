## Rule Effectiveness Analysis

Phase 9G adds bounded, read-only effectiveness analysis for one certified canonical rule against one controlled historical dataset or replay-style artifact.

### Prerequisites

- The rule must exist in the canonical rule repository.
- A completed certification receipt must exist.
- The certification receipt hash must still match the current preserved rule record.
- A controlled historical dataset or replay artifact must exist locally.

### Why production replay is not executed

This phase measures one rule in isolation through the canonical single-rule evaluator. It does not execute the production historical replay workflow, scoring logic, objective packs, or Fast Lane.

### Dataset contract

The analysis module accepts one controlled dataset record with:

- supported dataset schema,
- deterministic ordered record IDs,
- mapping-based evaluation contexts,
- optional explicit outcome-label field,
- optional explicit baseline field.

If no controlled dataset is available, analysis returns `historical_rule_dataset_unavailable`.

### Plans and fingerprints

Backtest plans are bounded:

- default limit: 200
- hard limit: 500

Stable plan fingerprints include rule fingerprint, dataset fingerprint, ordered record IDs, comparison rule fingerprint when present, declared label fields, and record limit. Timestamps are excluded from plan-fingerprint inputs.

### Metrics

Always calculated:

- records planned
- records evaluated
- matched count
- not-matched count
- blocked / unsupported / error counts
- match coverage
- evaluation completion rate
- evaluation error rate
- persistent mutation detection

Outcome metrics are calculated only when explicit labels exist:

- precision
- recall
- specificity
- negative predictive value
- accuracy
- balanced accuracy
- prevalence

No positive class is inferred.

### Comparison

Optional version comparison is limited to certified rules from the same version chain and the identical ordered record set. The report shows differences only. It does not recommend one version.

### Persistence

Analysis records:

- `data/source_documents/rule_effectiveness_analyses/`
- `data/source_documents/rule_effectiveness_receipts/`
- matching indexes under `data/source_documents/indexes/`

Receipts are immutable and append-only.

### Safety rules

- no rule mutation
- no scoring mutation
- no objective-pack mutation
- no Fast Lane mutation
- no automatic recommendation
- no production replay execution

### Staleness and idempotency

Identical reruns return `already_analyzed`.

Existing analysis is reusable only when rule, certification, dataset, ordered records, comparison rule, and bounded plan options are unchanged. Otherwise the prior result is stale and must not be presented as current.

### Public-safe reporting

Public-safe reports exclude:

- absolute paths
- full historical contexts
- raw private payloads
- full sensitive rule payload values
- stack traces
- secrets

### Deferred

- automatic recommendations
- rollback recommendations
- supersession recommendations
- scoring integration
- objective-pack integration
- Fast Lane integration
- production replay integration
- batch analysis
- rule tuning
