# Electional Python Backend

This is the beginning of the migration from browser-only JavaScript toward a Python calculation backend.

The current Python slice includes:

- Aspect definitions and detection.
- Electional presets inspired by the Capricorn Prometheus reference inventory.
- Classical essential dignity scoring.
- Electional window scoring.
- A small standard-library JSON API.

The browser UI is still JavaScript for now. The migration path is to move the calculation engine into Python first, then have the existing UI call the Python API.

## Run Tests

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover backend\tests
```

## Run API

```powershell
& "C:\Users\Drago\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m backend.electional.server
```

Endpoints:

- `GET /api/health`
- `GET /api/presets`
- `POST /api/score`

`POST /api/score` currently expects already-calculated positions. Ephemeris and house calculation are still running in the browser and should be moved into Python in a later migration slice.
