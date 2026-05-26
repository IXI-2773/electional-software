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
- A small standard-library JSON API.
- A server-rendered Python interface at `/`.

The legacy browser UI has been retired to `legacy/static-js-ui` for reference only. New features should target the Python backend and Python-rendered interface.

## Run Tests

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover backend\tests
```

## Run API

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m backend.electional.server
```

Endpoints:

- `GET /`
- `GET /api/health`
- `GET /api/presets`
- `POST /api/score`

`POST /api/score` still accepts already-calculated positions for bridge compatibility. The Python-rendered app route now calculates timezone conversion, ephemeris, house angles, aspects, dignity, scoring, and candidate windows server-side.
