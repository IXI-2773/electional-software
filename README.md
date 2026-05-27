# Electional Software

A private work-in-progress application for electional astrology: transits, aspects, timing windows, and chart-based recommendations.

## Current Foundation

- Python is now the primary application runtime.
- The primary interface is a native Python desktop application.
- The desktop UI requires no browser and no browser JavaScript.
- The desktop UI supports preset cities, custom latitude/longitude/timezone entries, and built-in validation.
- Custom locations can be saved, reused from the Location preset dropdown, and forgotten later.
- Ranked candidate windows are selectable in the desktop UI and can be applied back to the input time.
- Promising candidate windows can be shortlisted, compared in a dedicated tab, copied, cleared, or saved as a shortlist report.
- Selected windows and shortlists can be exported as `.ics` calendar files from the desktop UI.
- Ribbon buttons now perform useful actions: reset chart, calculate, save reports, inspect chart data, review systems, and run screening tools.
- The chart workspace includes degree ticks and a bottom interpretation panel for the selected window.
- Quick time controls and support/stress counts make candidate-window scanning faster.
- The chart workspace now keeps Search Start, Selected Window, and Difference visible so ranked windows do not get confused with the input chart.
- Preferences can apply zodiac, house, objective, model, and search defaults from one dialog.
- Wheel view controls can toggle aspects, Lots, nodes, fixed-star markers, and compact mode without recalculating.
- Clean/Full wheel presets make it faster to switch between a readable working chart and a dense inspection chart.
- Fit and zoom controls improve wheel framing, while applying aspects draw solid and separating aspects draw dashed.
- Timing and location context is now shown above the wheel with compact search/selected-window cards.
- Focus Wheel mode hides the side panels for chart inspection and can be toggled with `F11`.
- A reference-style View Page strip below the chart opens Interpretation, Aspects, Aspectarian, Conditions, Chart Data, and wheel export.
- Timing controls now support fine adjustments with `-15m`, `-5m`, `+5m`, and `+15m` buttons.
- A Timing detail tab summarizes next exact contact, next support, and next stress from the backend timing profile.
- A Log detail tab records calculations, selected windows, saved reports/wheels, location changes, and focused chart points.
- The desktop app remembers the last working session and saved reports include ranked candidate windows.
- Scoreboard cards, report copy/view/save actions, and double-click window selection support a faster working session.
- Chart planets are selectable and update the point-interpretation panel with dignity, angle, and aspect context.
- The wheel center now masks aspect lines and clearly distinguishes search start time from selected ranked-window time.
- The desktop layout now uses cleaner workflow sections, a calmer blue/ivory palette, and card-based candidate windows instead of a plain listbox.
- Report details now live in right-panel tabs, with more polished score cards and a deeper chart-wheel rendering.
- Ribbon utilities now open real calculated tools for chart data, void-of-course Moon scanning, essential dignity reference, and solar elongation screening.
- Sidereal is now first-class: the desktop defaults to Sidereal Lahiri, stores ayanamsha in chart snapshots, and supports Whole Sign, Equal House, Topocentric, or Koch selection.
- Calculation diagnostics now detect the local `ast78win64\ephem` Swiss Ephemeris files and report whether Swiss Python bindings or Astronomy Engine fallback are active.
- Placidus, Porphyry, Campanus, Regiomontanus, Alcabitius, and Sripati are available as Phase 2 house-system groundwork; professional Swiss routing is used when bindings are available, with safe fallback cusps otherwise.
- House cusps have their own detail tab and drive the wheel divisions for quadrant-style systems.
- Arabic Lots now calculate the seven Hermetic Lots for each chart, with a Lots tab, wheel markers, focus support, and an in-app reference.
- Lunar nodes now calculate as chart points, appear on the wheel, can be focused, and have their own detail tab.
- Fixed stars now appear on the wheel rim and can be clicked/focused like other chart points.
- Moon phase, planetary motion, retrograde state, and electional condition notes now appear in snapshots, reports, and desktop detail tabs.
- Pure-Python electional rules now add sidereal nakshatra/tithi context plus solar-condition screening for cazimi, combustion, and under-beams.
- Planetary day/hour is calculated in Python from local sunrise and sunset, appears in reports/UI, and contributes a small electional rule score.
- Unequal ecliptic constellation spans and ASC rising-speed diagnostics now appear in reports/UI and contribute small, transparent rule-score adjustments.
- Judgment-engine contexts now add objective-specific significators, Moon condition, house rulers, reception, planet-condition diagnostics, advanced aspect patterns, and a Factor Explorer tab.
- Aspect contacts now show applying/separating phase and feed the score explanation when supportive or stressful contacts are tightening.
- Applying aspects now include approximate perfection timing, exact-time estimates, and a backend timing profile for next support/stress contacts.
- The desktop now includes an aspectarian tab and Chart Data aspectarian output for faster visual review of active contacts.
- The Health ribbon action opens calculation diagnostics for active engine, local Astrolog/Swiss resources, cusp sources, planetary hour status, and warning notes.
- Conditions now include election flags for tightening support/stress, angular benefics/malefics, and lunar phase context.
- System references are available from the ribbon so zodiac/house modes can be reviewed inside the app.
- Score breakdowns and reason lines explain the final window score.
- Score accounting now separates category totals, positive/negative adjustments, net points, grade, strengths, and risks.
- Desktop search controls can scan custom hour ranges, step sizes, score thresholds, and result limits.
- The backend exposes chart, configurable search, and report API endpoints.
- Python calculates timezone conversion, ephemeris, ASC/MC/DSC/IC, houses, aspects, lunar phase, planetary motion, dignity, scoring, and ranked windows server-side.
- The previous static JavaScript UI has been retired into `legacy/static-js-ui` for reference only.

## Run Locally

Create a local virtual environment and install dependencies:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

Run the native desktop application:

```powershell
& ".\.venv\Scripts\python.exe" desktop_app.py
```

Or double-click:

`Run Desktop App.bat`

Open the project Python runner:

`Open Python Runner.bat`

Runner notes are in `docs/python-runner.md`.

Optional diagnostic server:

```powershell
& ".\.venv\Scripts\python.exe" -m backend.electional.server
```

## Tests

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover backend\tests
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

## Professional Calculation Bridge

The app currently detects this local Astrolog/Swiss Ephemeris reference path:

`C:\Users\Drago\Downloads\ast78win64\ephem`

If Python Swiss Ephemeris bindings are available in the runtime, the professional bridge can route supported planetary and house calculations through Swiss Ephemeris. On this machine, `pyswisseph` currently requires Windows C++ Build Tools for Python 3.12, so the app keeps using Astronomy Engine fallback while surfacing clear calculation notes in reports and Chart Data.

## Legacy UI

The retired browser-only JavaScript implementation is archived at:

`legacy/static-js-ui`

It remains useful for comparison during migration, but new work should target the Python backend and native desktop application.
