# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


datas = []
binaries = []
hiddenimports = []

legacy_logo = Path("assets/logo.png")
if legacy_logo.exists():
    datas.append((str(legacy_logo), "assets"))

logo_extensions = {".png", ".jpg", ".jpeg", ".webp"}
logo_dir = Path("assets/logos")
if logo_dir.exists():
    for logo_path in sorted(logo_dir.iterdir(), key=lambda item: item.name.lower()):
        if logo_path.is_file() and logo_path.suffix.lower() in logo_extensions:
            datas.append((str(logo_path), "assets/logos"))

qfluent_datas, qfluent_binaries, qfluent_hiddenimports = collect_all("qfluentwidgets")
datas += qfluent_datas
binaries += qfluent_binaries
hiddenimports += qfluent_hiddenimports


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="图片处理工具",
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
