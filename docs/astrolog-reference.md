# Astrolog 7.80 Reference Notes

Local reference folder: `C:\Users\Drago\Downloads\ast78win64`

This folder is useful as a design and calculation reference for the Python desktop app. It is not copied into the repo wholesale, but the app can mirror its concepts piece by piece.

## Key Defaults

Astrolog's `astrolog.as` default file shows a sidereal-first configuration:

- `=s`: sidereal zodiac enabled.
- `:s Lahi`: Lahiri ayanamsha selected.
- `=b`: ephemeris files enabled.
- `-A 5`: five major aspects selected.
- `-c Plac`: Placidus default house system.

## Ayanamsha Choices

Astrolog documents named sidereal offsets relative to its Fagan-Bradley baseline:

- Fagan-Bradley: `0.0`.
- Lahiri: `0.883208`.
- Krishnamurti: `0.98006`.
- B.V. Raman: `2.329509`.

The Python app now keeps Lahiri as the default and exposes these additional sidereal choices in the Zodiac System dropdown.

## House Systems

Astrolog documents house-system indexes including:

- `1`: Koch.
- `2`: Equal.
- `8`: Topocentric / Polich-Page.
- `14`: Whole.
- `15`: Vedic.

The Python app currently supports Whole Sign, Equal House, Topocentric, and Koch.

Phase 2 groundwork adds Placidus, Porphyry, Campanus, Regiomontanus, Alcabitius, and Sripati to the app's selectable house systems. Systems supported by Swiss Ephemeris are routed through the professional bridge when Python bindings are available; otherwise the desktop keeps running and labels fallback cusp sources in Chart Data and reports.

## Fixed Stars

Astrolog ships `sefstars.txt`, a Swiss Ephemeris fixed-star data file. The Python app now includes a curated electional subset:

- Aldebaran.
- Algol.
- Regulus.
- Sirius.
- Spica.
- Antares.
- Galactic Center.

Contacts are screened as conjunctions within a diagnostic star-specific orb: bright stars can use a slightly wider allowance, dim or special points are tighter, and contacts with known ecliptic latitude carry a strength adjustment.

## Python-Only Rule Direction

The project stays Python-native. Astrolog and Swiss Ephemeris remain reference material unless a clean Python-compatible runtime path is chosen later. Current pure-Python rule work includes:

- Sidereal lunar context: nakshatra and tithi.
- Solar condition screening: cazimi, combust, under beams, clear of beams.
- Rule score impacts surfaced in reports, score reasons, and the desktop Rules tab.
