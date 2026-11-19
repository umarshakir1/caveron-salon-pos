# -*- mode: python ; coding: utf-8 -*-
import os

from PyInstaller.utils.hooks import collect_submodules

datas = []
if os.path.isdir("assets"):
    datas.append(("assets", "assets"))
if os.path.isdir("fonts"):
    datas.append(("fonts", "fonts"))

hidden = collect_submodules("escpos")
hidden += [
    "win32print",
    "PySide6.QtCharts",
    "PySide6.QtPrintSupport",
    "openpyxl",
    "reportlab",
    "PIL",
]

icon = "assets/caveron.ico" if os.path.exists("assets/caveron.ico") else None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CAVERON",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=icon,
)
