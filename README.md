# LL-NEXUS

LeagueLoop Nexus is an independent League Client companion focused on Champ Select, explainable recommendations, safe automation, and session history.

## Included

- PySide6 executable desktop shell with Champ Select as the primary surface
- Authoritative state machine with confidence and staleness
- LCU service and event ingestion boundaries
- Champion catalog and persistent priority system
- Deterministic explainable recommendation engine
- Automation controller, verification, and global emergency stop
- Session recording and persistence
- Developer diagnostics and simulation mode
- Responsive champion-grid/component foundation
- Regression tests and GitHub Actions CI

## Run

```bash
python -m venv .venv
# On Windows: .\.venv\Scripts\Activate.ps1
# On Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
league-loop-nexus
```

Simulation without League Client:

```bash
NEXUS_SIMULATE=1 league-loop-nexus
```

## Packaging

To generate a standalone Windows executable bundle:

```bash
python scripts/build_windows_exe.py
```

The original LeagueLoop project is not modified or required by Nexus.
