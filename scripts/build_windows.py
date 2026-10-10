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
        print("Error: PyInstaller is required for packaging. Install with: pip install pyinstaller")
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
    try:
        subprocess.check_call(cmd, cwd=str(ROOT))
    except subprocess.CalledProcessError as exc:
        print(f"PyInstaller build failed with exit code {exc.returncode}")
        sys.exit(exc.returncode)


if __name__ == "__main__":
    build()
