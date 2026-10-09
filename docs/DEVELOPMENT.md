# Development

Python 3.10+.

PowerShell (Windows):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest -q
league-loop-nexus
```

Bash (Linux / macOS):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
league-loop-nexus
```

Without League Client (Simulation Mode):
```bash
NEXUS_SIMULATE=1 league-loop-nexus
```

## Packaging for Windows

To build a standalone Windows executable (`dist/LeagueLoopNexus.exe`):

```powershell
pip install -e ".[dev]"
python scripts/build_windows_exe.py
```

This uses PyInstaller and `league_loop_nexus.spec` to bundle the application and `assets/champions.json`.
*(Note: Executing PyInstaller on a non-Windows platform generates and validates the spec file; a Windows host or CI runner is required to emit a native `.exe` binary.)*
