# Electional Software

A private work-in-progress application for electional astrology: transits, aspects, timing windows, and chart-based recommendations.

## Current Foundation

- Python is now the primary application runtime.
- The primary interface is a native Python desktop application.
- The desktop UI requires no browser and no browser JavaScript.
- The desktop UI supports preset cities, custom latitude/longitude/timezone entries, and built-in validation.
- Custom locations can be saved, reused from the Location preset dropdown, and forgotten later.
- Ranked candidate windows are selectable in the desktop UI and can be applied back to the input time.
- Ribbon buttons now perform useful actions: reset chart, calculate, save reports, or clearly mark queued features.
- The chart workspace includes degree ticks and a bottom interpretation panel for the selected window.
- Quick time controls and support/stress counts make candidate-window scanning faster.
- The desktop app remembers the last working session and saved reports include ranked candidate windows.
- Scoreboard cards, report copy/view/save actions, and double-click window selection support a faster working session.
- Chart planets are selectable and update the point-interpretation panel with dignity, angle, and aspect context.
- The wheel center now masks aspect lines and clearly distinguishes search start time from selected ranked-window time.
- The desktop layout now uses cleaner workflow sections, a calmer blue/ivory palette, and card-based candidate windows instead of a plain listbox.
- Report details now live in right-panel tabs, with more polished score cards and a deeper chart-wheel rendering.
- Ribbon utilities now open real calculated tools for chart data, void-of-course Moon scanning, essential dignity reference, and solar elongation screening.
- Sidereal is now first-class: the desktop defaults to Sidereal Lahiri, stores ayanamsha in chart snapshots, and supports Whole Sign, Equal House, Topocentric, or Koch selection.
- House cusps have their own detail tab and drive the wheel divisions for quadrant-style systems.
- Arabic Lots now calculate Fortune and Spirit for each chart, with a Lots tab and wheel markers.
- System references are available from the ribbon so zodiac/house modes can be reviewed inside the app.
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
