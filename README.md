# Electional Software

A private work-in-progress application for electional astrology: transits, aspects, timing windows, and chart-based recommendations.

## Current Foundation

- Python is now the primary application runtime.
- The primary interface is a native Python desktop application.
- The desktop UI requires no browser and no browser JavaScript.
- The desktop UI supports preset cities, custom latitude/longitude/timezone entries, and built-in validation.
- Custom locations can be saved, reused from the Location preset dropdown, marked as Home, and forgotten later.
- Ranked candidate windows are selectable in the desktop UI and can be applied back to the input time.
- Promising candidate windows can be shortlisted, compared in a dedicated tab, copied, cleared, or saved as a shortlist report.
- Selected windows and shortlists can be exported as `.ics` calendar files from the desktop UI.
- Ribbon buttons now perform useful actions: reset chart, calculate, save reports, inspect chart data, review systems, and run screening tools.
- The chart workspace includes degree ticks and a bottom interpretation panel for the selected window.
- Quick time controls and support/stress counts make candidate-window scanning faster.
- The chart workspace now keeps Search Start, Selected Window, and Difference visible so ranked windows do not get confused with the input chart.
- Preferences can apply zodiac, house, objective, model, page mode, point configuration, home location, and search defaults from one dialog.
- Wheel view controls can toggle aspects, Lots, nodes, fixed-star markers, and compact mode without recalculating.
- Point configuration presets now switch the visible wheel set between Classical 7, 10 Planets, Planets + Nodes, Planets + Fortune, and Full Electional modes.
- Page modes now separate `Wheel`, `Wheel + Aspectarian`, `Classical Point Data`, `Medieval Data`, and `Transit Search` workflows in the View Page strip.
- Transit Search now has its own detail page with search profile, search-start vs selected-window timing, and ranked-window summaries.
- A new Decision Brief page translates the selected window into recommendation, fit, timing, and watchout language for faster choosing.
- A new Compare page summarizes the leading candidate windows side by side with fit, timing offset, strengths, and risks.
- Search filters now support minimum fit and an `avoid major stress` mode in addition to score and result limits.
- Search filters now also support `require applying support`, `avoid angular malefics`, and `keep Moon non-void`.
- Search filters now also support `avoid objective anti-patterns`, so launch, negotiation, travel, and money scans can reject windows that are specifically wrong for that goal.
- Search filters now also support `minimum confidence`, `minimum cleanliness`, `maximum volatility`, and `require angular benefic` for stronger quality control during scans.
- Search now uses a snapshot calculation cache plus a fast/deep path for large limited scans, ranking cheaply first and deep-building only buffered top candidates.
- Desktop cache tools now include both cache stats and a Clear Cache action for fresh search comparisons.
- Left-panel timing, location, and search shortcut buttons now use cleaner equal-width rows for a steadier layout.
- Top navigation and tighter wrapped ribbon groups now use clearer task labels, including Advisor, Decision, Compare, Factors, Day Report, Copy, Search Page, and Map.
- The Advisor tab turns score factors into a compact verdict, supports, cautions, and recommended next tools to inspect.
- The Improve tab turns weak score signals into concrete adjustment moves, including angle, Moon, aspect timing, and support/stress fixes.
- Button Health checks visible top nav, ribbon, and page-strip controls for missing action wiring or missing detail-page targets.
- Desktop polish now includes a calmer workbench palette, clearer header hierarchy, active top-nav page state, and softer ribbon tiles.
- The wheel is larger and cleaner, with sharper planet markers, stronger angle lines, angle constellation labels, and an outer unequal constellation band.
- The constellation band uses approximate IAU ecliptic-crossing spans, including Ophiuchus and narrow Scorpius, instead of treating constellations as equal zodiac signs.
- Election scoring now splits angular testimony into benefic support, malefic pressure, luminary support, and other angular emphasis.
- Angle explanations now name the planet, nearest angle, distance, and point impact in diagnostics, reports, Factor Explorer, and the desktop Angles tab.
- Search presets now include `Strict Launch`, `Clean Negotiation`, `Safe Travel`, and `Conservative Money` to fill those filters quickly.
- Compare tools can now export a saved decision sheet with the selected brief plus top-window comparison.
- Decision guidance is now more objective-aware for launch/publish, negotiation, travel, and money/business work.
- Objective-specific backend ranking weights now make those workflows score differently, not just read differently.
- Backend scoring now includes readiness, volatility, cleanliness, and confidence diagnostics for each ranked window.
- The desktop scoreboard now includes confidence, and a Diagnostics page summarizes backend trust signals and anti-pattern warnings.
- Search ranking now breaks ties with diagnostics too, preferring stronger confidence, cleanliness, and readiness over noisier windows with the same headline score.
- Transit Search now reports why windows were rejected, including top rejection reasons and rejected sample windows.
- Shortlists now store and display confidence, cleanliness, readiness, and volatility, and rank saved picks by quality instead of insertion order.
- Shortlists now open with batch diagnostics so the cleanest, highest-confidence, and steadiest saved candidates stand out at a glance.
- The desktop shortlist board now uses color-banded diagnostics cards, direct two-pick compare controls, and persistent custom tags like `Best for launch`, `Backup`, or `Client-safe`.
- Classical Point Data now gives planets, angles, cusps, lots, nodes, and fixed-star contacts their own dense reference-style workspace.
- Medieval Data now summarizes verdict, balance of testimony, score reasons, election flags, and classical judgment sections in one working page.
- Clean/Full wheel presets make it faster to switch between a readable working chart and a dense inspection chart.
- Fit and zoom controls improve wheel framing, while applying aspects draw solid and separating aspects draw dashed.
- The chart wheel now uses a cleaner canvas, subtler rings, visible degree ticks, polished angle badges, and better marker depth.
- Timing and location context is now shown above the wheel with compact search/selected-window cards.
- Focus Wheel mode hides the side panels for chart inspection and can be toggled with `F11`.
- A compact View Page selector below the chart opens the full interpretation/detail pages while keeping Search, Aspect Strength, Chart Data, and wheel export close at hand.
- Timing controls now support fine adjustments with `-15m`, `-5m`, `+5m`, and `+15m` buttons.
- A Timing detail tab summarizes next exact contact, next support, and next stress from the backend timing profile.
- A Log detail tab records calculations, selected windows, saved reports/wheels, location changes, and focused chart points.
- The desktop app remembers the last working session and saved reports include ranked candidate windows.
- The astrolabe-style judgment panel, report copy/view/save actions, and double-click window selection support a faster working session.
- The judgment panel now surfaces objective fit alongside score, support, stress, angularity, stars, rules, strongest aspect, ASC lord, and 10th lord.
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
- Fixed-star contacts now use star-specific diagnostic orbs, magnitude sensitivity, and latitude-aware contact strength when both coordinates are available.
- Moon phase, planetary motion, retrograde state, and electional condition notes now appear in snapshots, reports, and desktop detail tabs.
- Planet condition diagnostics now estimate station windows, very slow/fast motion, and primary-vs-background scoring pressure.
- Visibility diagnostics now label morning/evening solar side, cazimi/combust/under-beams/emerging phases, and diagnostic confidence.
- Visibility pressure now contributes light relevance-weighted planet-condition factors without overpowering classical solar-condition rules.
- Pure-Python electional rules now add sidereal nakshatra/tithi context plus solar-condition screening for cazimi, combustion, and under-beams.
- Planetary day/hour is calculated in Python from local sunrise and sunset, appears in reports/UI, and contributes a small electional rule score.
- Unequal ecliptic constellation spans and ASC rising-speed diagnostics now appear in reports/UI and contribute small, transparent rule-score adjustments.
- Judgment-engine contexts now add objective-specific significators, Moon condition, house rulers, reception, planet-condition diagnostics, advanced aspect patterns, and a Factor Explorer tab.
- Factor Explorer now compares selected-window judgment layers against the search-start chart and labels which layers improved or worsened.
- Advanced aspect diagnostics now flag basic prohibition and frustration patterns when a significator contact is interrupted by a sooner perfection.
- Advanced aspect diagnostics now explain objective-specific aspect importance, so launch, negotiation, travel, money, relationship, and health work weight contact meaning differently.
- Declination is now calculated for chart bodies, with out-of-bounds and parallel/contra-parallel diagnostics included in judgment factors.
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
