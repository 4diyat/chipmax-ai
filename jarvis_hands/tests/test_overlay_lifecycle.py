"""Regresi siklus hidup kamera dan sinkronisasi hotkey."""

from __future__ import annotations

from typing import Any

from jarvis_hands.core.config import CameraConfig
from jarvis_hands.tests.test_camera import FakeSource, FakeTracker
from jarvis_hands.tests.test_session import make_session
from jarvis_hands.vision.camera import CameraController


def test_manual_pause_and_hotkey_remain_in_sync(qapp: Any) -> None:
    session, _, backend, indicator = make_session()
    session.start()
    session.set_paused(True)
    backend.activate()
    assert not bool(session.is_paused)
    session.set_paused(True)
    session.stop()
    session.start()
    backend.activate()
    assert session.is_paused
    session.stop()
    indicator.close()


def test_hotkey_stops_after_camera_error(qapp: Any) -> None:
    session, controller, backend, indicator = make_session()
    session.start()
    controller.error.emit("kamera gagal")
    assert backend.callback is None
    session.stop()
    indicator.close()


def test_failed_open_can_restart(qtbot: Any, qapp: Any) -> None:
    sources = [FakeSource(fail_open=True), FakeSource(frames=100000)]
    controller = CameraController(
        CameraConfig(fps=120), source_factory=lambda: sources.pop(0), tracker_factory=FakeTracker
    )
    states: list[bool] = []
    controller.active_changed.connect(states.append)
    assert controller.start()
    qtbot.waitUntil(lambda: bool(controller.last_error), timeout=5000)
    assert True not in states
    qtbot.waitUntil(
        lambda: controller._thread is not None and controller._thread.isFinished(), timeout=5000
    )
    assert controller.start()
    qtbot.waitUntil(lambda: controller.is_active, timeout=5000)
    assert controller.stop()
