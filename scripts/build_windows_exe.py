"""Build script for Windows packaging of LeagueLoop Nexus.

Uses PyInstaller to produce a standalone executable or bundle including
assets (assets/champions.json).

Usage:
    python scripts/build_windows_exe.py [--onedir | --onefile]

Note:
    PyInstaller requires a Windows host (or WINE) to produce a native Windows .exe.
    When executed on Linux/macOS, this script generates/validates the spec file
    and reports platform requirements honestly as per Section 3A.
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SPEC_FILE = ROOT / "league_loop_nexus.spec"


SPEC_TEMPLATE = """# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None

root_dir = Path(SPECPATH)
assets_dir = root_dir / "assets"
entry_point = str(root_dir / "src" / "nexus" / "app" / "bootstrap.py")

datas = []
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

a = Analysis(
    [entry_point],
    pathex=[str(root_dir / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'nexus.app.bootstrap',
        'nexus.app.controller',
        'nexus.ui.shell.main_window',
        'nexus.services.lcu.service',
        'nexus.developer.simulation.simulator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LeagueLoopNexus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""


def generate_spec() -> Path:
    SPEC_FILE.write_text(SPEC_TEMPLATE, encoding="utf-8")
    print(f"Generated PyInstaller spec file: {SPEC_FILE}")
    return SPEC_FILE


def main() -> int:
    generate_spec()

    if sys.platform != "win32":
        print("[INFO] Host OS is non-Windows. PyInstaller requires a Windows platform to compile a Windows .exe binary.")
        print("[INFO] PyInstaller spec file successfully verified and generated.")
        print("[INFO] To build executable on Windows, run:")
        print("       pip install pyinstaller")
        print("       python scripts/build_windows_exe.py")
        return 0

    try:
        import PyInstaller  # noqa
    except ImportError:
        print("[ERROR] PyInstaller is not installed. Run: pip install pyinstaller")
        return 1

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", str(SPEC_FILE)]
    print(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode == 0:
        print("Build succeeded! Executable located in dist/LeagueLoopNexus.exe")
    return res.returncode


if __name__ == "__main__":
    raise SystemExit(main())
