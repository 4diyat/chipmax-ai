# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller untuk JARVIS Ring & Hands (Windows x64, one-folder).

Model Hand Landmarker dan lisensinya dibundel sebagai data aplikasi, bukan
diunduhan saat runtime. Hasil build ada di ``dist/jarvis-hands/``.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent
MODEL_DIR = ROOT / "jarvis_hands" / "assets" / "models"
ICON_DIR = ROOT / "jarvis_hands" / "assets" / "icons"

# MediaPipe membawa binary dan data internal; PyInstaller tidak punya hook
# lengkap untuk semua modulnya, jadi seluruh paket ikut dikumpulkan.
mediapipe_datas, mediapipe_binaries, mediapipe_hiddenimports = collect_all("mediapipe")

a = Analysis(
    [str(ROOT / "jarvis_hands" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=mediapipe_binaries,
    datas=[
        (str(MODEL_DIR / "hand_landmarker.task"), "jarvis_hands/assets/models"),
        (str(MODEL_DIR / "LICENSE"), "jarvis_hands/assets/models"),
        (str(MODEL_DIR / "README.md"), "jarvis_hands/assets/models"),
        (str(ICON_DIR / "chevron-down.svg"), "jarvis_hands/assets/icons"),
        (str(ICON_DIR / "chevron-up.svg"), "jarvis_hands/assets/icons"),
        (str(ICON_DIR / "check.svg"), "jarvis_hands/assets/icons"),
    ]
    + mediapipe_datas,
    hiddenimports=mediapipe_hiddenimports
    + [
        "mediapipe.tasks.python.vision.hand_landmarker",
        "mediapipe.tasks.python.vision.core",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6.QtNetwork", "tkinter", "test", "unittest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="jarvis-hands",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="jarvis-hands",
)
