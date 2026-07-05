# Topic Taxonomy

Phase 8S adds a controlled topic-taxonomy layer above normalized topic labels.

## Purpose

- Store one controlled topic record per preferred normalized label.
- Attach explicit aliases, parent links, child links, related-topic links, and deprecated replacement links.
- Resolve labels deterministically without semantic inference.
- Build a taxonomy-aware search-expansion plan without executing search.

## Storage

- Records: `data/source_documents/topic_taxonomy/<topic_id>.json`
- Index: `data/source_documents/indexes/topic_taxonomy_index.json`

Each record uses `controlled_topic_v1` and stores:

- `topic_id`
- `preferred_label`
- `normalized_preferred_label`
- `aliases`
- `parent_topic_ids`
- `child_topic_ids`
- `related_topic_ids`
- `status`
- `replacement_topic_id`
- `note`
- `created_at_utc`
- `updated_at_utc`
- `warnings`

## Normalization

- Lowercase
- Trim surrounding whitespace
- Collapse repeated whitespace
- Normalize dash variants through the existing topic normalizer
- Remove simple punctuation noise
- Preserve meaningful numbers and internal hyphen structure where the shared normalizer keeps them

The preferred label normalizes to the stable topic ID shape `topic_<normalized_slug>`.

## Validation

The taxonomy validator is read-only. It detects:

- duplicate preferred labels
- alias collisions with another preferred label
- duplicate aliases across active topics
- self-parent, self-child, and self-related references
- missing parent, child, related, or replacement targets
- parent or replacement cycles
- invalid status values
- unsupported schema versions

Relationships are explicit only. The system does not infer aliases, broader topics, narrower topics, or related topics.

## Resolution

Resolution order:

1. exact normalized preferred label
2. exact normalized alias
3. deprecated preferred label when deprecated resolution is explicitly allowed
4. deprecated alias when deprecated resolution is explicitly allowed
5. unresolved

Unresolved labels stay unresolved. The system does not guess.

## Expansion Planning

`build_taxonomy_search_expansion(...)` creates a controlled plan only. It can include:

- the resolved preferred label
- explicit aliases
- explicit parent topics
- explicit child topics
- explicit related topics
- explicit replacement topics for deprecated topics

It does not execute cross-document search automatically.

## Reporting

Public-safe reports omit:

- private notes
- absolute paths
- source text
- chunk text
- citations
- proposals
- tokens
- API keys
- stack traces

## Deferred

P1 deferred by timebox:

- preferred-label rename workflow
- automatic retagging or tag migration
- taxonomy-aware Phase 8R index rebuilding
- automatic topic merge or split
- bulk import/export
- history timeline
- usage analytics
- tree visualization

P2 not attempted by policy:

- AI alias suggestions
- semantic similarity
- embeddings
- automatic hierarchy generation
- model-based topic classification
- PDF viewport work

## Targeted Testing Policy

Run only:

```powershell
.\.venv\Scripts\python.exe scripts/run_targeted_tests.py --file backend/tests/test_topic_taxonomy.py
```

Do not run the broad project-wide test suite for this phase.
