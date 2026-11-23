"""Tes kamera: loop worker di thread, sinyal, jeda, dan kegagalan perangkat."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from numpy import typing as npt
from PySide6.QtCore import QCoreApplication

from jarvis_hands.core.config import CameraConfig
from jarvis_hands.tests.support import make_hand, make_result
from jarvis_hands.vision.camera import CameraController, CameraError, CameraWorker, Frame
from jarvis_hands.vision.tracker import HandTracker, TrackingResult


class FakeSource:
    """Sumber frame sintetis yang menghitung bacaan."""

    def __init__(self, frames: int = 100, *, fail_open: bool = False) -> None:
        self._frames = frames
        self._fail_open = fail_open
        self.reads = 0
        self.released = 0
        self.width = 640
        self.height = 360

    def open(self) -> None:
        if self._fail_open:
            raise CameraError("perangkat uji sengaja gagal")

    def read(self) -> Frame | None:
        if self.reads >= self._frames:
            return None
        self.reads += 1
        return Frame(
            rgb=np.zeros((360, 640, 3), dtype=np.uint8),
            width=640,
            height=360,
            timestamp_ms=int(time.monotonic() * 1000),
        )

    def release(self) -> None:
        self.released += 1


class FakeTracker(HandTracker):
    """Tracker yang mengembalikan tangan tetap."""

    def __init__(self) -> None:
        self.calls = 0
        self.closed = 0

    def detect(self, rgb: npt.NDArray[np.uint8], timestamp_ms: int) -> TrackingResult:
        self.calls += 1
        return make_result(make_hand(), timestamp_ms=timestamp_ms)

    def close(self) -> None:
        self.closed += 1


def test_worker_processes_frames_and_stops() -> None:
    source = FakeSource(frames=50)
    tracker = FakeTracker()
    worker = CameraWorker(
        CameraConfig(fps=120),
        source_factory=lambda: source,
        tracker_factory=lambda: tracker,
    )
    results: list[TrackingResult] = []
    frames: list[Frame] = []

    def on_result(result: TrackingResult) -> None:
        results.append(result)
        if len(results) >= 3:
            worker.stop()

    worker.landmarks_ready.connect(on_result)
    worker.frame_ready.connect(frames.append)
    worker.run()

    assert len(results) == 3
    assert len(frames) >= 3
    assert tracker.calls == 3
    assert tracker.closed == 1
    assert source.released == 1
    assert not worker.is_active


def test_worker_reports_camera_open_failure() -> None:
    source = FakeSource(fail_open=True)
    worker = CameraWorker(
        CameraConfig(),
        source_factory=lambda: source,
        tracker_factory=FakeTracker,
    )
    failures: list[str] = []
    finished: list[bool] = []
    worker.failed.connect(failures.append)
    worker.finished_run.connect(lambda: finished.append(True))
    worker.run()
    assert failures == ["perangkat uji sengaja gagal"]
    assert finished == [True]
    assert not worker.is_active


def test_worker_reports_missing_frames() -> None:
    source = FakeSource(frames=0)
    worker = CameraWorker(
        CameraConfig(),
        source_factory=lambda: source,
        tracker_factory=FakeTracker,
    )
    failures: list[str] = []
    worker.failed.connect(failures.append)
    worker.run()
    assert failures and "frame" in failures[0]


def test_worker_pause_skips_reads() -> None:
    source = FakeSource(frames=1000)
    tracker = FakeTracker()
    worker = CameraWorker(
        CameraConfig(fps=240),
        source_factory=lambda: source,
        tracker_factory=lambda: tracker,
    )

    def stop_after_two(result: TrackingResult) -> None:
        if tracker.calls >= 2:
            worker.set_paused(True)
            QCoreApplication.processEvents()
            reads = source.reads
            time.sleep(0.08)
            assert source.reads == reads
            worker.set_paused(False)

    def stop_soon(result: TrackingResult) -> None:
        if tracker.calls >= 4:
            worker.stop()

    worker.landmarks_ready.connect(stop_after_two)
    worker.landmarks_ready.connect(stop_soon)
    worker.run()
    assert tracker.calls == 4
    assert not worker.is_paused


def test_controller_start_stop_emits_active_changed(qapp: Any, qtbot: Any) -> None:
    source = FakeSource(frames=100_000)
    tracker = FakeTracker()
    config = CameraConfig(fps=120)
    controller = CameraController(
        config,
        source_factory=lambda: source,
        tracker_factory=lambda: tracker,
    )
    states: list[bool] = []
    results: list[TrackingResult] = []
    controller.active_changed.connect(states.append)
    controller.landmarks_ready.connect(results.append)

    assert controller.start() is True
    qtbot.waitUntil(lambda: controller.is_active, timeout=5000)
    assert states == [True]
    assert controller.start() is False
    qtbot.waitUntil(lambda: len(results) >= 2, timeout=5000)

    assert controller.stop() is True
    assert not controller.is_active
    assert states[-1] is False
    assert tracker.closed == 1
    assert source.released == 1


def test_controller_survives_camera_error(qapp: Any, qtbot: Any) -> None:
    source = FakeSource(fail_open=True)
    controller = CameraController(
        CameraConfig(),
        source_factory=lambda: source,
        tracker_factory=FakeTracker,
    )
    errors: list[str] = []
    controller.error.connect(errors.append)
    controller.start()
    qtbot.waitUntil(lambda: bool(controller.last_error), timeout=5000)
    assert errors == ["perangkat uji sengaja gagal"]
    assert controller.stop() is True
    assert not controller.is_active


def test_controller_pause_and_toggle(qapp: Any, qtbot: Any) -> None:
    source = FakeSource(frames=100_000)
    controller = CameraController(
        CameraConfig(fps=120),
        source_factory=lambda: source,
        tracker_factory=FakeTracker,
    )
    controller.start()
    qtbot.waitUntil(lambda: controller.is_active, timeout=5000)
    controller.set_paused(True)
    assert controller.is_paused is True
    controller.set_paused(False)
    assert not bool(controller.is_paused)
    assert controller.toggle() is False
    assert not controller.is_active
    assert controller.toggle() is True
    qtbot.waitUntil(lambda: controller.is_active, timeout=5000)
    controller.stop()


def test_real_tracker_runs_inside_qthread(qapp: Any, qtbot: Any) -> None:
    """Integrasi: model resmi + QThread + sinyal lintas thread."""
    source = FakeSource(frames=100_000)
    controller = CameraController(
        CameraConfig(fps=30, analysis_fps=30),
        source_factory=lambda: source,
        tracker_factory=HandTracker,
    )
    results: list[TrackingResult] = []
    controller.landmarks_ready.connect(results.append)
    assert controller.start() is True
    qtbot.waitUntil(lambda: controller.is_active, timeout=10_000)
    qtbot.waitUntil(lambda: len(results) >= 2, timeout=20_000)
    assert results[0].hands == ()
    assert (results[0].width, results[0].height) == (640, 360)
    assert controller.stop() is True
    assert not controller.is_active
