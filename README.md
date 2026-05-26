# Electional Software

A private work-in-progress application for electional astrology: transits, aspects, timing windows, and eventually chart-based recommendations.

## Current Foundation

- Static browser app, no build step required yet.
- Electional workspace UI with date, location, objective, and aspect filters.
- Domain modules for aspect definitions and transit-window scaffolding.
- Starter ephemeris module for planet positions using mean daily motion.
- Aspect detection and ranked electional windows based on selected aspect types.

## Accuracy Note

The current calculation layer is intentionally a starter engine. It is useful for building the application flow, but it should be replaced with a professional ephemeris before relying on the app for final electional judgment.

## Open Locally

Open `index.html` in a browser from this folder.
