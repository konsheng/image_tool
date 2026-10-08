# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


if os.name == "nt":
    # Qt uses Windows ICU. An unrelated tool's ICU on the inherited PATH can
    # have the same DLL name with incompatible exports and break QtCore import.
    # Resolve native dependencies from this Python install and Windows only;
    # PyInstaller's package hooks add PySide6's own library directories.
    windows_directory = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    os.environ["PATH"] = os.pathsep.join(
        str(path)
        for path in (
            Path(sys.executable).resolve().parent,
            Path(sys.base_prefix),
            Path(sys.base_prefix) / "DLLs",
            windows_directory / "System32",
            windows_directory,
        )
    )


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

font_dir = Path("assets/fonts")
if font_dir.exists():
    datas.append((str(font_dir), "assets/fonts"))

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
    excludes=[
        "pytest",
        "_pytest",
        "blind_watermark_service",
        "blind_watermark",
        "cv2",
        "numpy",
        "pywt",
    ],
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
