from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Mapping

from .cache_keys import build_cache_key
from .cache_stats import CacheStats


class DeterministicCache:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._items: dict[str, object] = {}
        self._lock = RLock()
        self.stats = CacheStats()

    def key(self, namespace: str, payload: Mapping[str, object]) -> str:
        return build_cache_key(namespace, payload)

    def get(self, namespace: str, payload: Mapping[str, object]) -> object | None:
        if not self.enabled:
            self.stats.miss()
            return None
        key = self.key(namespace, payload)
        with self._lock:
            if key in self._items:
                self.stats.hit()
                return deepcopy(self._items[key])
        self.stats.miss()
        return None

    def set(self, namespace: str, payload: Mapping[str, object], value: object) -> str:
        key = self.key(namespace, payload)
        if self.enabled:
            with self._lock:
                self._items[key] = deepcopy(value)
        return key

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
        self.stats = CacheStats()

    def stats_payload(self) -> dict[str, object]:
        return self.stats.to_json()
