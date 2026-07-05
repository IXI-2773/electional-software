# Phase 4 Performance

Phase 4 adds deterministic cache keys, optional in-memory cache storage, resumable search checkpoints, and deterministic parallel worker helpers.

Cache keys must include location, objective, zodiac/house settings, and version fields so cached results do not cross incompatible contexts.
