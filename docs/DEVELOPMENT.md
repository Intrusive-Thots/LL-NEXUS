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

`scripts/build_windows.py` is the packaging entry point. See `docs/PACKAGING.md`.

`scripts/build_windows_exe.py` and `league_loop_nexus.spec` build a standalone executable that bundles `assets/champions.json`:

```powershell
pip install -e ".[dev]"
python scripts/build_windows_exe.py
```

Executing PyInstaller on a non-Windows platform generates and validates the spec file. A Windows host or CI runner is required to emit a native `.exe`.

