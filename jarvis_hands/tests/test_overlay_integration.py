"""Uji sinyal thread kamera hingga UI dan penghentian bersih."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from PySide6.QtWidgets import QApplication

from jarvis_hands.core.config import AppConfig, CameraConfig, DisplayMode
from jarvis_hands.core.hotkey import HotkeySpec, PynputBackend
from jarvis_hands.tests.test_camera import FakeSource, FakeTracker
from jarvis_hands.ui.overlay import OverlayWindow
from jarvis_hands.vision.camera import CameraController
from jarvis_hands.vision.session import CameraSession


def test_camera_thread_to_overlay(qtbot: Any, qapp: QApplication) -> None:
    source = FakeSource(frames=100000)
    config = CameraConfig(fps=60)
    controller = CameraController(
        config, source_factory=lambda: source, tracker_factory=FakeTracker
    )
    session = CameraSession(config, controller=controller)
    overlay = OverlayWindow(AppConfig.default(), session, qapp.primaryScreen())
    qtbot.addWidget(overlay)
    overlay.set_mode(DisplayMode.MIRROR)
    overlay.show()
    assert session.start()
    qtbot.waitUntil(lambda: not overlay._image.isNull(), timeout=5000)
    assert session.is_active
    session.set_paused(True)
    assert overlay._image.isNull()
    assert session.stop()
    assert source.released == 1
    assert not bool(session.is_active)
    overlay.close()


def test_pynput_uses_global_hotkeys(monkeypatch: Any) -> None:
    class Listener:
        def __init__(self, mapping: Any) -> None:
            self.mapping = mapping
            self.daemon = False
            self.started = False

        def start(self) -> None:
            self.started = True

        def stop(self) -> None:
            self.started = False

    module = ModuleType("pynput")
    module.keyboard = type("Keyboard", (), {"GlobalHotKeys": Listener})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pynput", module)
    backend = PynputBackend(HotkeySpec("g", ctrl=True, alt=True))
    assert backend.start(lambda: None)
    listener = backend._listener
    assert listener is not None
    assert listener.started
    assert "<ctrl>+<alt>+g" in listener.mapping
    backend.stop()
