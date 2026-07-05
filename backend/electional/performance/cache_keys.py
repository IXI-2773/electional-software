from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Mapping

PHASE4_CACHE_VERSION = "phase4_cache_v1"


def build_cache_key(namespace: str, payload: Mapping[str, object]) -> str:
    normalized = {"namespace": namespace, "cache_version": PHASE4_CACHE_VERSION, **dict(payload)}
    if isinstance(normalized.get("datetime_utc"), datetime):
        moment = normalized["datetime_utc"]
        normalized["datetime_utc"] = moment.astimezone(UTC).isoformat() if moment.tzinfo else moment.isoformat()
    text = json.dumps(normalized, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
