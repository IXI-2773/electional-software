# Electional Software

A private work-in-progress application for electional astrology: transits, aspects, timing windows, and chart-based recommendations.

## Current Foundation

- Python is now the primary application runtime.
- The primary interface is a native Python desktop application.
- The desktop UI requires no browser and no browser JavaScript.
- The desktop UI supports preset cities, custom latitude/longitude/timezone entries, and built-in validation.
- Ranked candidate windows are selectable in the desktop UI and can be applied back to the input time.
- Ribbon buttons now perform useful actions: reset chart, calculate, save reports, or clearly mark queued features.
- The chart workspace includes degree ticks and a bottom interpretation panel for the selected window.
- Python calculates timezone conversion, ephemeris, ASC/MC/DSC/IC, Whole Sign houses, aspects, dignity, scoring, and ranked windows server-side.
- The previous static JavaScript UI has been retired into `legacy/static-js-ui` for reference only.

## Run Locally

Install dependencies:

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pip install -r requirements.txt
```

Run the native desktop application:

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" desktop_app.py
```

Or double-click:

`Run Desktop App.bat`

Open the project Python runner:

`Open Python Runner.bat`

Runner notes are in `docs/python-runner.md`.

Optional diagnostic server:

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m backend.electional.server
```

## Tests

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover backend\tests
```

## Accuracy Fixtures

Ephemeris fixture:

- Chart: May 26, 2026 at 9:00 AM, Los Angeles, CA
- UTC: May 26, 2026 at 16:00
- Source reference: NASA/JPL Horizons observer ecliptic longitude output
- Current Python Astronomy Engine checks include Sun, Moon, and Mercury within `0.01` degrees.

Angle fixture:

- Source reference: `sweph-wasm` 2.6.9 using Swiss Ephemeris `swe_houses(..., "W")`
- ASC: `110.13511832023705` degrees / `20 Cancer 08`
- MC: `6.5293592412573105` degrees / `6 Aries 32`
- Python tests enforce both within `0.05` degrees.

## Legacy UI

The retired browser-only JavaScript implementation is archived at:

`legacy/static-js-ui`

It remains useful for comparison during migration, but new work should target the Python backend and native desktop application.
