# AGENTS.md

LeagueLoop Nexus (LL-NEXUS) is an independent League Client companion. Do not modify the old LeagueLoop.DEV repo. Work only in this repository.

## Stack

- Python 3.10+
- Package: `src/nexus` (setuptools, src layout)
- UI: PySide6. Entry point: `league-loop-nexus` -> `nexus.app.bootstrap:main`
- Tests: pytest, `pytest -q` from repo root. UI tests use the `ui` marker and must stay offscreen.
- Simulation: `NEXUS_SIMULATE=1` must keep the app usable without a live League Client.

## Boundaries

- LCU access stays behind the existing service/port layer. Do not scatter lockfile parsing or raw HTTP through UI code.
- Automation must keep the emergency stop / kill switch. Never remove verification before an action.
- Recommendations stay deterministic and explainable. Do not add a black-box model call on the pick path.
- Do not commit `__pycache__`, `.venv`, or local `nexus_data` runtime files.

## Done means

- `pytest -q` passes.
- Public behavior changes are covered by a test.
- Open a pull request against `main`. Do not force-push `main`.
