# Electional Python Backend

This is the beginning of the migration from browser-only JavaScript toward a Python-owned application.

The current Python slice includes:

- Aspect definitions and detection.
- Electional presets inspired by the Capricorn Prometheus reference inventory.
- Classical essential dignity scoring.
- Electional window scoring.
- A small standard-library JSON API.
- A server-rendered Python interface at `/`.

The legacy browser UI still exists as a fallback while the Python interface grows. The migration path is to move calculation and display into Python in layers until the JavaScript interface can be retired.

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

`POST /api/score` currently expects already-calculated positions. Ephemeris and house calculation are still running in the browser and should be moved into Python in a later migration slice.
