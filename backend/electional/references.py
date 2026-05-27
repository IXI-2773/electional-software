"""Human-readable reference tables for desktop and reports."""

from __future__ import annotations

from .lots import LOT_NAMES, LOT_TOPICS
from .presets import DETRIMENTS, EGYPTIAN_BOUNDS, EXALTATIONS, FALLS, RULERS
from .systems import HOUSE_SYSTEMS, ZODIAC_SYSTEMS


def dignity_table_lines() -> list[str]:
    lines = ["Sign         Ruler      Exalted    Detriment  Fall"]
    for sign, ruler in RULERS.items():
        lines.append(
            f"{sign:<12} {ruler:<10} {EXALTATIONS.get(sign, '-'):<10} {DETRIMENTS.get(sign, '-'):<10} {FALLS.get(sign, '-'):<10}"
        )
    lines.extend(["", "Egyptian Bounds", "Sign         Degrees"])
    for sign, bounds in EGYPTIAN_BOUNDS.items():
        start = 0
        entries = []
        for end, lord in bounds:
            entries.append(f"{start}-{end} {lord}")
            start = end
        lines.append(f"{sign:<12} {', '.join(entries)}")
    return lines


def system_reference_lines() -> list[str]:
    lines = ["Zodiac Systems", ""]
    for system in ZODIAC_SYSTEMS:
        lines.append(f"{system.name}")
        lines.append(f"  Mode: {system.mode}")
        lines.append(f"  {system.description}")
        lines.append("")
    lines.extend(["House Systems", ""])
    for system in HOUSE_SYSTEMS:
        lines.append(f"{system.name}")
        lines.append(f"  {system.description}")
        lines.append("")
    lines.extend(
        [
            "Current implementation notes:",
            "- Sidereal Lahiri is the default electional mode.",
            "- Topocentric is implemented as a Polich-Page cusp option using local latitude-derived pole divisions.",
            "- Koch is implemented as a birthplace/time-division house option based on MC and IC arc trisections.",
            "- Future Swiss Ephemeris integration can tighten ayanamsha and house cusp precision further.",
        ]
    )
    return lines


def lot_reference_lines() -> list[str]:
    lines = [
        "Seven Hermetic Lots",
        "",
        "Lots are calculated from the Ascendant and planetary relationships. Fortune and Spirit anchor the set; the other lots derive from those anchors and the classical planets.",
        "",
    ]
    for lot_id in ("fortune", "spirit", "eros", "necessity", "courage", "victory", "nemesis"):
        lines.append(LOT_NAMES[lot_id])
        lines.append(f"  Topic: {LOT_TOPICS[lot_id]}")
        lines.append("")
    lines.extend(
        [
            "Formula notes:",
            "- Day and night charts reverse the relevant formula direction.",
            "- The Lots tab shows the exact formula used for the selected chart.",
        ]
    )
    return lines
