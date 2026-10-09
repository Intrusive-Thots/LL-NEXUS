# -*- mode: python ; coding: utf-8 -*-

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
