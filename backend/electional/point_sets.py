"""Display point configurations for the desktop chart wheel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .presets import ALL_MAJOR_PLANETS, CLASSICAL_PLANETS

DEFAULT_POINT_SET_ID = "ten-planets"


@dataclass(frozen=True)
class PointSet:
    id: str
    name: str
    description: str
    planet_names: tuple[str, ...]
    show_nodes: bool = False
    show_lots: bool = False
    lot_names: tuple[str, ...] = ()
    show_fixed_stars: bool = False


POINT_SETS: tuple[PointSet, ...] = (
    PointSet(
        id="classical-7",
        name="Classical 7",
        description="Traditional visible planets only: Sun through Saturn.",
        planet_names=CLASSICAL_PLANETS,
    ),
    PointSet(
        id="ten-planets",
        name="10 Planets",
        description="Modern planet display from Sun through Pluto.",
        planet_names=ALL_MAJOR_PLANETS,
    ),
    PointSet(
        id="planets-nodes",
        name="Planets + Nodes",
        description="Planets plus mean and true lunar nodes.",
        planet_names=ALL_MAJOR_PLANETS,
        show_nodes=True,
    ),
    PointSet(
        id="planets-fortune",
        name="Planets + Fortune",
        description="Planets plus the Part of Fortune.",
        planet_names=ALL_MAJOR_PLANETS,
        show_lots=True,
        lot_names=("Part of Fortune",),
    ),
    PointSet(
        id="full-electional",
        name="Full Electional",
        description="Planets, nodes, hermetic lots, and fixed-star rim markers.",
        planet_names=ALL_MAJOR_PLANETS,
        show_nodes=True,
        show_lots=True,
        show_fixed_stars=True,
    ),
)

POINT_SET_BY_ID = {point_set.id: point_set for point_set in POINT_SETS}
POINT_SET_BY_NAME = {point_set.name: point_set for point_set in POINT_SETS}
POINT_SET_NAMES = tuple(point_set.name for point_set in POINT_SETS)


def get_point_set(point_set_id_or_name: object | None) -> PointSet:
    value = str(point_set_id_or_name or DEFAULT_POINT_SET_ID)
    return POINT_SET_BY_ID.get(value) or POINT_SET_BY_NAME.get(value) or POINT_SET_BY_ID[DEFAULT_POINT_SET_ID]


def visible_planets_for_point_set(positions: Sequence[Mapping[str, object]], point_set: PointSet) -> list[Mapping[str, object]]:
    allowed = set(point_set.planet_names)
    return [position for position in positions if str(position.get("name")) in allowed]


def visible_lots_for_point_set(lots: Sequence[Mapping[str, object]], point_set: PointSet) -> list[Mapping[str, object]]:
    if not point_set.show_lots:
        return []
    if not point_set.lot_names:
        return list(lots)
    allowed = set(point_set.lot_names)
    return [lot for lot in lots if str(lot.get("name")) in allowed]
