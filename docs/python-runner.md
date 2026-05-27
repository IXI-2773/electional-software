# Python Runner

This project includes two Windows launchers:

- `Open Python Runner.bat` opens a lightweight Python IDE using IDLE, the editor included with Python.
- `Run Desktop App.bat` launches the native Electional Software desktop application.

## Open The Runner

Double-click:

```text
Open Python Runner.bat
```

This opens:

- A single Python shell for running project code.
- A startup tip showing the project path and a useful chart-engine import.

It no longer opens multiple source editor windows by default.

## Run The App

Double-click:

```text
Run Desktop App.bat
```

Or run from PowerShell:

```powershell
& ".\.venv\Scripts\python.exe" desktop_app.py
```

## Spyder Later

IDLE is the immediate built-in runner. If we want the heavier Spyder-style workflow later, the next clean step is to install Spyder through Conda or Windows Package Manager and point it at this repository.
