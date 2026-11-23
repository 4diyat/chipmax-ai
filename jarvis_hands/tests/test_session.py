"""Tes CameraSession: pengikatan kamera, hotkey, dan indikator."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from jarvis_hands.core.hotkey import PauseHotkey
from jarvis_hands.ui.camera import CameraIndicator, CameraState
from jarvis_hands.vision.session import CameraSession


class StubController(QObject):
    """Pengganti CameraController yang memancarkan sinyal yang sama."""

    active_changed = Signal(bool)
    error = Signal(str)
    fps_changed = Signal(float)
    landmarks_ready = Signal(object)
    frame_ready = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.started = 0
        self.stopped = 0
        self.paused = False
        self.active = False

    def start(self) -> bool:
        self.started += 1
        self.active = True
        self.active_changed.emit(True)
        return True

    def stop(self, timeout_ms: int = 3000) -> bool:
        del timeout_ms
        self.stopped += 1
        self.active = False
        self.active_changed.emit(False)
        return True

    def set_paused(self, paused: bool) -> None:
        self.paused = paused


class StubBackend:
    """Backend hotkey yang bisa dipicu manual."""

    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.callback: Callable[[], None] | None = None

    def start(self, on_activate: Callable[[], None]) -> bool:
        self.started += 1
        self.callback = on_activate
        return True

    def stop(self) -> None:
        self.stopped += 1
        self.callback = None

    def activate(self) -> None:
        assert self.callback is not None
        self.callback()


def make_session() -> tuple[CameraSession, StubController, StubBackend, CameraIndicator]:
    controller = StubController()
    backend = StubBackend()
    hotkey = PauseHotkey(backend=backend)
    session = CameraSession(controller=controller, hotkey=hotkey)  # type: ignore[arg-type]
    indicator = CameraIndicator()
    session.attach_indicator(indicator)
    return session, controller, backend, indicator


def test_start_activates_camera_and_hotkey(qapp: object) -> None:
    session, controller, backend, indicator = make_session()
    assert session.start() is True
    assert bool(session.is_active)
    assert controller.started == 1
    assert backend.started == 1
    assert bool(session.hotkey_listening)
    active_state: CameraState = indicator.state
    assert active_state == CameraState.ACTIVE
    session.stop()
    indicator.close()


def test_hotkey_pauses_and_resumes(qapp: object) -> None:
    session, controller, backend, indicator = make_session()
    states: list[bool] = []
    session.paused_changed.connect(states.append)
    session.start()

    backend.activate()
    assert bool(session.is_paused)
    assert bool(controller.paused)
    paused_state: CameraState = indicator.state
    assert paused_state == CameraState.PAUSED
    assert states == [True]

    backend.activate()
    assert not bool(session.is_paused)
    assert not bool(controller.paused)
    active_state: CameraState = indicator.state
    assert active_state == CameraState.ACTIVE
    assert states == [True, False]
    session.stop()
    indicator.close()


def test_stop_clears_pause_and_hotkey(qapp: object) -> None:
    session, controller, backend, indicator = make_session()
    session.start()
    session.set_paused(True)
    assert bool(session.is_paused)

    assert session.stop() is True
    assert controller.stopped == 1
    assert not bool(session.is_active)
    assert not bool(session.is_paused)
    assert not bool(session.hotkey_listening)
    assert backend.stopped == 1
    off_state: CameraState = indicator.state
    assert off_state == CameraState.OFF
    indicator.close()


def test_error_marks_indicator(qapp: object) -> None:
    session, controller, _backend, indicator = make_session()
    errors: list[str] = []
    session.error.connect(errors.append)
    session.start()
    controller.error.emit("kamera tidak dapat dibuka")
    assert errors == ["kamera tidak dapat dibuka"]
    error_state: CameraState = indicator.state
    assert error_state == CameraState.ERROR
    session.stop()
    indicator.close()


def test_pause_ignored_when_inactive(qapp: object) -> None:
    session, controller, _backend, _indicator = make_session()
    session.set_paused(True)
    assert not bool(session.is_paused)
    assert not bool(controller.paused)


def test_landmarks_and_frames_forwarded(qapp: object) -> None:
    session, controller, _backend, _indicator = make_session()
    landmarks: list[object] = []
    frames: list[object] = []
    session.landmarks_ready.connect(landmarks.append)
    session.frame_ready.connect(frames.append)
    payload = object()
    controller.landmarks_ready.emit(payload)
    controller.frame_ready.emit(payload)
    assert landmarks == [payload]
    assert frames == [payload]
