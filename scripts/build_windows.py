"""Windows PyInstaller packaging script for LeagueLoop Nexus.

Produces a standalone Windows desktop executable.
Usage:
    python scripts/build_windows.py
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Error: PyInstaller is not installed. Install with: pip install pyinstaller>=6.0")
        sys.exit(1)

    entry_point = ROOT / "src" / "nexus" / "app" / "bootstrap.py"
    assets_dir = ROOT / "assets"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name=league-loop-nexus",
        "--windowed",
        f"--add-data={assets_dir}{os.pathsep}assets",
        f"--paths={ROOT / 'src'}",
        str(entry_point),
    ]
    print(f"Executing PyInstaller build: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    build()
