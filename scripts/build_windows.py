"""Windows PyInstaller packaging script for LeagueLoop Nexus.

Produces a standalone Windows desktop executable.
Usage:
    python scripts/build_windows.py
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_pyinstaller() -> bool:
    """Check if PyInstaller is available in the current environment."""
    return importlib.util.find_spec("PyInstaller") is not None


def build() -> int:
    """Build the standalone Windows executable using PyInstaller.

    Returns:
        0 on success, non-zero on failure.
    """
    if not check_pyinstaller():
        print("ERROR: PyInstaller is not installed in the current environment.")
        print("Please install PyInstaller using: pip install pyinstaller")
        raise RuntimeError("PyInstaller module not found.")

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
        f"--add-data={assets_dir};assets",
        f"--paths={ROOT / 'src'}",
        str(entry_point),
    ]
    print(f"Executing PyInstaller build: {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(ROOT))


if __name__ == "__main__":
    try:
        sys.exit(build())
    except Exception as err:
        print(f"Build failed: {err}")
        sys.exit(1)
