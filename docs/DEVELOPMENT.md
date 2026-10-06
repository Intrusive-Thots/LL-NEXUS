# Development

Python 3.10+.

PowerShell:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest -q
league-loop-nexus

Without League Client:
$env:NEXUS_SIMULATE="1"
league-loop-nexus
