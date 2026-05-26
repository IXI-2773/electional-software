# Electional Software

A private work-in-progress application for electional astrology: transits, aspects, timing windows, and eventually chart-based recommendations.

## Current Foundation

- Static browser app, no build step required yet.
- Python backend migration has started under `backend/electional`.
- Python now serves a no-JavaScript interface at `http://127.0.0.1:8765/`.
- The Python interface calculates timezone conversion, ephemeris, angles, houses, aspects, dignity, and ranked windows server-side.
- Electional workspace UI with date, location, objective, and aspect filters.
- Domain modules for aspect definitions and transit-window scaffolding.
- Professional ephemeris module powered by Astronomy Engine.
- Location presets with latitude, longitude, and IANA timezone handling.
- Aspect detection and ranked electional windows based on selected aspect types.
- Ascendant, Midheaven, Descendant, IC, Whole Sign house placement, and angularity scoring.

## Accuracy Note

Planetary positions now use Astronomy Engine's browser library for geocentric true ecliptic coordinates. Angles are calculated from sidereal time, true obliquity, latitude, and longitude. The next accuracy step is cross-checking the house angles against a second astrology-specific calculator before relying on final electional judgment.

## Validation

The app includes a validation panel that compares a fixed chart against NASA/JPL Horizons observer ecliptic longitude/latitude output. Current fixture:

- Chart: May 26, 2026 at 9:00 AM, Los Angeles, CA
- UTC: May 26, 2026 at 16:00
- Source: NASA/JPL Horizons API, observer quantity 31
- Current max longitude delta: 0.0032 degrees

The same panel also runs an angle sanity check for the Los Angeles morning chart to guard against flipped ASC/DSC orientation.

Angle validation fixture:

- Source: `sweph-wasm` 2.6.9 using Swiss Ephemeris `swe_houses(..., "W")`
- ASC: 110.13511832023705 degrees / 20 Cancer 08
- MC: 6.5293592412573105 degrees / 6 Aries 32
- Current ASC delta: 0.0000 degrees
- Current MC delta: 0.0000 degrees

## Open Locally

Open `index.html` in a browser from this folder.

## Python Backend Migration

The first Python slice now mirrors core electional logic:

- Aspect definitions and detection.
- Electional presets: Transit 1 Degree, Traditional Lilly, Medieval Electional.
- Classical essential dignity scoring.
- Electional window scoring.
- Standard-library JSON API skeleton.
- The browser app now calls the Python API for preset scoring when it is running, and falls back to JavaScript if it is not.

Run tests:

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover backend\tests
```

Run the Python API:

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m backend.electional.server
```

The next migration step is retiring the legacy static JavaScript UI once the Python interface has feature parity.
