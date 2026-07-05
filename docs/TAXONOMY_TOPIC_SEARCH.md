# Taxonomy-Aware Topic Search

## Purpose

Phase 8T connects the controlled Phase 8S topic taxonomy to the existing cross-document topic-search index without rebuilding tags or indexes automatically.

The flow is:

1. resolve the query through the controlled taxonomy
2. build a controlled one-level expansion plan
3. execute one search per approved label
4. preserve match provenance
5. deduplicate structural references
6. rank direct matches before expanded matches
7. group results by document, chapter, and section
8. return a public-safe report

## Relationship Between Phase 8R and Phase 8S

- Phase 8S governs preferred labels, aliases, parents, children, related topics, and deprecated replacements.
- Phase 8R provides the stored cross-document topic-search surface.
- Phase 8T bridges them. It does not modify taxonomy records, topic-index records, content maps, or curation overlays.

## Controlled Query Resolution

- preferred labels resolve exactly
- explicit aliases resolve exactly
- unresolved labels stay unresolved
- no semantic guessing, fuzzy matching, or automatic topic creation occurs

## Expansion Options

The bridge can include:

- preferred label
- explicit aliases
- direct parent topics
- direct child topics
- direct related topics
- one replacement topic for a deprecated topic

Expansion is single-level only. Recursive traversal is prohibited in Phase 8T.

## Match Provenance

Every structural result keeps:

- matched search labels
- source type
- source topic ID
- expansion distance
- Phase 8R-style match reason
- Phase 8R-style match rank
- direct-versus-expanded classification

## Structural Deduplication

Results are deduplicated by structural identity, not by section title text alone. The identity uses:

- document ID
- chapter ID
- section ID
- page range
- sorted chunk IDs

Merged duplicates preserve combined provenance and labels.

## Deterministic Ranking

Results sort by:

1. direct preferred-label match class
2. minimum expansion distance
3. Phase 8R-style match rank
4. reader readiness
5. curated source before fallback
6. document and structural order

## Health and Blocking

Health checks report:

- taxonomy validation status
- topic-index availability
- stale topic-index warnings
- blocking critical taxonomy issues

The bridge does not rebuild the Phase 8R index automatically.

## Public-Safe Reporting

Public-safe reports omit:

- absolute paths
- source paths
- full source text
- full chunk text
- citations
- proposals
- private taxonomy notes
- tokens
- API keys
- stack traces

## Deferred

P1 deferred by timebox:

- saved search profiles
- search history
- topic usage analytics
- query analytics
- automatic taxonomy-index synchronization
- automatic retagging
- automatic deprecated-tag migration
- result export packages
- cross-topic comparison dashboards

P2 not attempted by policy:

- semantic similarity
- embeddings
- AI topic suggestions
- AI summaries
- fuzzy meaning inference
- PDF viewport integration

## Targeted Testing Policy

Run only:

```powershell
.\.venv\Scripts\python.exe scripts/run_targeted_tests.py --file backend/tests/test_taxonomy_topic_search.py
```

Do not run the broad project-wide test suite for this phase.
