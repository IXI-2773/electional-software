"""Annual profection and time-lord boundary for future engine work.

The application does not yet implement full profections. Keeping this module
explicit prevents UI code from inventing ad-hoc time-lord logic in the desktop layer.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfectionResult:
    age: int
    house: int
    note: str


def profection_house_for_age(age: int) -> int:
    """Return the annual profection house using the standard 12-year cycle."""

    if age < 0:
        raise ValueError("Age must be non-negative for profection calculation.")
    return (age % 12) + 1


def annual_profection(age: int) -> ProfectionResult:
    house = profection_house_for_age(age)
    return ProfectionResult(age=age, house=house, note=f"Age {age} profects to house {house}.")


__all__ = ["ProfectionResult", "annual_profection", "profection_house_for_age"]
