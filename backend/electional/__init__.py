"""Python backend core for Electional Software."""

from .aspects import ASPECTS, detect_aspects
from .lots import calculate_lots
from .presets import ELECTIONAL_PRESETS, get_preset
from .reporting import build_report_text
from .scoring import score_window
from .search import SearchConfig
from .systems import HOUSE_SYSTEMS, ZODIAC_SYSTEMS

__all__ = [
    "ASPECTS",
    "ELECTIONAL_PRESETS",
    "HOUSE_SYSTEMS",
    "ZODIAC_SYSTEMS",
    "SearchConfig",
    "build_report_text",
    "calculate_lots",
    "detect_aspects",
    "get_preset",
    "score_window",
]
