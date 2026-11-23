"""Fixture pytest bersama."""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _preload_headless_qt() -> None:
    """Muat stub Qt bila sistem tidak punya libGL (container headless).

    Jalur ini tidak aktif di Linux desktop normal, Windows, atau macOS. Stub
    hanya cukup untuk platform ``offscreen``; lihat tools/headless_qt/README.md.
    """
    if not sys.platform.startswith("linux"):
        return
    try:
        ctypes.CDLL("libGL.so.1")
        return
    except OSError:
        pass
    root = Path(__file__).resolve().parents[2]
    try:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from tools.headless_qt.build import build_stubs

        stubs = build_stubs()
        for name in (
            "libGL.so.1",
            "libEGL.so.1",
            "libGLESv2.so.2",
            "libxkbcommon.so.0",
            "libdbus-1.so.3",
        ):
            ctypes.CDLL(str(stubs / name), mode=ctypes.RTLD_GLOBAL)
    except Exception as exc:  # jangan gagalkan collection tes
        print(f"jarvis-hands: stub Qt headless gagal: {exc}", file=sys.stderr)


_preload_headless_qt()

import pytest  # noqa: E402

from jarvis_hands.core.config import AppConfig  # noqa: E402


@pytest.fixture
def config() -> AppConfig:
    """Konfigurasi bawaan untuk tes UI."""
    return AppConfig.default()
