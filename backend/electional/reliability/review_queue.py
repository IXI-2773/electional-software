"""Review queue item generation for coverage and replay drift."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ReviewQueueItem:
    item_type: str
    severity: str
    title: str
    description: str
    recommendation: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def build_review_queue(
    *,
    replay_drift: Iterable[Mapping[str, object]] | None = None,
    coverage_audit: Mapping[str, object] | None = None,
) -> list[ReviewQueueItem]:
    items: list[ReviewQueueItem] = []
    for drift in replay_drift or []:
        category = str(drift.get("category") or drift.get("drift_type") or "replay_drift")
        severity = str(drift.get("severity") or "warning")
        title = str(drift.get("title") or category.replace("_", " ").title())
        description = str(drift.get("description") or "Replay output changed.")
        recommendation = str(drift.get("recommendation") or "Review changed output before trusting this rule update.")
        items.append(ReviewQueueItem(category, severity, title, description, recommendation))
    if coverage_audit:
        for key, item_type in (
            ("missing_features", "phase_coverage_missing_feature"),
            ("export_gaps", "phase_coverage_missing_export"),
            ("test_gaps", "phase_coverage_missing_test"),
        ):
            values = coverage_audit.get(key, [])
            if isinstance(values, list):
                for value in values:
                    if not isinstance(value, Mapping):
                        continue
                    items.append(
                        ReviewQueueItem(
                            item_type,
                            "major",
                            f"Coverage gap: {value.get('feature_id', 'feature')}",
                            f"{value.get('name', 'Feature')} has {key.replace('_', ' ')}.",
                            "Fill the missing integration before claiming reliability coverage.",
                        )
                    )
    return items
