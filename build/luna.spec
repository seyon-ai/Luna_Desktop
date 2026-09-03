# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LUNA Desktop.

Produces a one-folder Windows build (portable, no installer) with the app
icon. Large AI/Kokoro models and voice binaries are never bundled — users
import them through the LUNA Models/Voice managers.
"""

from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "luna" / "assets"), "luna/assets"),
]

hiddenimports = [
    "luna.config",
    "luna.core",
    "luna.storage",
    "luna.ai",
    "luna.voice",
    "luna.automation",
    "luna.ui",
    "luna.__main__",
]

a = Analysis(
    [str(ROOT / "run_luna.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / "build" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LUNA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "luna" / "assets" / "luna.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LUNA",
)
