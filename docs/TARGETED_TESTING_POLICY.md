# Targeted Testing Policy

Broad project-wide test suites are disabled during normal development.

Allowed:

```powershell
python scripts/run_targeted_tests.py --file backend/tests/test_project_governance_roadmap.py
python scripts/run_targeted_tests.py --case backend/tests/test_project_governance_roadmap.py::RoadmapRegistryTest.test_roadmap_registry_summary
```

Forbidden unless explicitly requested:

```text
pytest
pytest backend/tests
python -m pytest
python -m unittest discover
tox
nox
coverage run -m pytest
```

Release gates may run smoke checks but must not run broad discovery.

