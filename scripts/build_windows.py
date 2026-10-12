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


def get_build_command() -> list[str]:
    entry_point = ROOT / "src" / "nexus" / "app" / "bootstrap.py"
    assets_dir = ROOT / "assets"
    return [
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


def build():
    cmd = get_build_command()
    print(f"Executing PyInstaller build: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    build()
