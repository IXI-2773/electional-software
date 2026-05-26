"""Python backend core for Electional Software."""

from .aspects import ASPECTS, detect_aspects
from .presets import ELECTIONAL_PRESETS, get_preset
from .scoring import score_window

__all__ = [
    "ASPECTS",
    "ELECTIONAL_PRESETS",
    "detect_aspects",
    "get_preset",
    "score_window",
]
