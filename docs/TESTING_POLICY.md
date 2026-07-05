# Targeted Testing Policy

Broad project-wide test suites are disabled by default during development.

Use targeted tests only:

```bash
python scripts/run_targeted_tests.py --file backend/tests/test_cache.py
python scripts/run_targeted_tests.py --case backend/tests/test_cache.py::test_cache_hit
```

Rejected by default:

```bash
python scripts/run_targeted_tests.py
python scripts/run_targeted_tests.py --all
python scripts/run_targeted_tests.py --file .
python scripts/run_targeted_tests.py --file backend/tests
python -m unittest discover
python -m pytest
pytest backend/tests
```

Default limits:

- Maximum targeted files: 3
- Maximum targeted cases: 10
- Broad suite requires an explicit user request.

Final development reports should list targeted tests, smoke tests, and integration tests only. Broad project-wide testing is skipped by policy unless the user explicitly asks for it.
