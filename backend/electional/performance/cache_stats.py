from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CacheStats:
    cache_hits: int = 0
    cache_misses: int = 0

    def hit(self) -> None:
        self.cache_hits += 1

    def miss(self) -> None:
        self.cache_misses += 1

    def to_json(self) -> dict[str, object]:
        total = self.cache_hits + self.cache_misses
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": round(self.cache_hits / total, 2) if total else 0.0,
        }
