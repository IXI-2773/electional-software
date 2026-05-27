# Electional Python Backend

This is the Python-owned application backend for Electional Software.

The current Python slice includes:

- Aspect definitions and detection.
- Electional presets inspired by the Capricorn Prometheus reference inventory.
- Classical essential dignity scoring.
- Electional window scoring.
- IANA timezone conversion.
- Astronomy Engine Python ephemeris.
- ASC, MC, DSC, IC, Whole Sign houses, and angularity.
- Seven Hermetic Lots / Parts.
- Moon phase, daily planetary motion, and retrograde scoring pressure.
- Applying/separating aspect phase for reports, APIs, and scoring explanations.
- Election condition flags for tightening aspect and angular planet context.
- Structured score accounting with category totals, net point adjustments, grades, strengths, and risks.
- Unequal ecliptic constellation span diagnostics, ASC rising speed, and small constellation/rising score factors.
- Layered judgment contexts for significators, Moon condition, house rulers, reception, planet condition, advanced aspects, and factor exploration.
- A small standard-library JSON API.
- A native Python desktop interface.
- Persistent shortlisted candidate windows for comparing promising electional picks.
- iCalendar export for selected windows and saved shortlists.
- Fit/zoom wheel controls and applying/separating aspect line styling.
- A server-rendered diagnostic interface at `/`.

The legacy browser UI has been retired to `legacy/static-js-ui` for reference only. New features should target the Python backend and native desktop interface.

## Run Tests

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover backend\tests
```

## Run Desktop App

```powershell
& ".\.venv\Scripts\python.exe" desktop_app.py
```

## Run Diagnostic API

```powershell
& ".\.venv\Scripts\python.exe" -m backend.electional.server
```

Endpoints:

- `GET /`
- `GET /api/health`
- `GET /api/presets`
- `POST /api/score`
- `POST /api/chart`
- `POST /api/search`
- `POST /api/report`

`POST /api/score` still accepts already-calculated positions for bridge compatibility. The Python-rendered app route now calculates timezone conversion, ephemeris, house angles, aspects, dignity, scoring, and candidate windows server-side.

`POST /api/chart`, `/api/search`, and `/api/report` accept chart inputs such as `date`, `time`, `locationId`, `presetId`, `aspects`, `zodiacSystemId`, and `houseSystemId`. Search/report calls also accept `startOffsetMinutes`, `endOffsetMinutes`, `stepMinutes`, `maxResults`, and `minimumScore`.

The desktop app exposes the same search controls through the Election Model panel.
