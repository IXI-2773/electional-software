# Electional Software

A private work-in-progress application for electional astrology: transits, aspects, timing windows, and eventually chart-based recommendations.

## Current Foundation

- Static browser app, no build step required yet.
- Electional workspace UI with date, location, objective, and aspect filters.
- Domain modules for aspect definitions and transit-window scaffolding.
- Professional ephemeris module powered by Astronomy Engine.
- Location presets with latitude, longitude, and IANA timezone handling.
- Aspect detection and ranked electional windows based on selected aspect types.
- Ascendant, Midheaven, Descendant, IC, Whole Sign house placement, and angularity scoring.

## Accuracy Note

Planetary positions now use Astronomy Engine's browser library for geocentric true ecliptic coordinates. Angles are calculated from sidereal time, true obliquity, latitude, and longitude. The next accuracy step is validating app outputs against an external astrology reference before relying on final electional judgment.

## Open Locally

Open `index.html` in a browser from this folder.
