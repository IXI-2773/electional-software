\# AGENTS.md



\## Mission

This project is an electional/aspect analysis app. Optimize for:

1\. Accurate calculations

2\. Clean data ingestion

3\. Strong finding/ranking logic

4\. Reproducible results

5\. Minimal, safe code changes



Do not waste time on cosmetic changes unless requested.



\---



\## Hard Rules

\- Make small, surgical patches.

\- Do not rewrite the whole project.

\- Do not change public behavior unless the task requires it.

\- Do not invent missing data.

\- Do not fake successful tests.

\- Do not silently ignore errors.

\- Do not add dependencies unless clearly justified.

\- Do not touch `.venv`, `.git`, `\_\_pycache\_\_`, old backups, or generated reports unless asked.

\- Preserve existing file names and user workflows.



\---



\## Project Map

Likely important areas:



\- `backend/` — core logic, calculations, analysis engine

\- `data/` — source data, lookup tables, configs

\- `docs/` — documentation

\- `reports/` — generated outputs

\- `legacy/` — old code; inspect only if needed

\- `desktop\_app.py` — desktop launcher/app entry

\- `index.html` / `styles.css` — UI layer

\- `requirements.txt` — Python dependencies

\- `README.md` — usage notes



Prioritize `backend/`, `data/`, and config files before UI.



\---



\## Preferred Workflow

Before editing:

1\. Inspect the relevant files.

2\. Identify the smallest safe fix.

3\. Explain the patch plan briefly.

4\. Then edit.



After editing:

1\. Run the smallest relevant test/check first.

2\. Run broader tests only if core logic changed.

3\. Report changed files.

4\. Report commands run and actual results.

5\. Mention anything not tested.



\---



## Commands

Use these when relevant:

### Fast Test Lanes

Use targeted tests before full tests:

```bash
scripts/test-fast.bat
scripts/test-full.bat
python -m pytest -q
python desktop_app.py
pip install -r requirements.txt
```


## Context Control

Ignore these unless explicitly asked:
- `.venv/`
- `.git/`
- `__pycache__/`
- `data/raw/`
- `data/cache/`
- `reports/`
- archives such as `.zip`, `.7z`, `.rar`
- generated files, logs, backups, and temp files

Use `data/samples/` for tests and parser work.

Do not scan large raw PDFs, CSVs, archives, or generated reports unless the task specifically requires it.
If raw data is needed, ask first and explain why.

