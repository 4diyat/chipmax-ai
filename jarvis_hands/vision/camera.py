"""Kamera + pelacakan tangan di QThread terpisah.

UI hanya menerima landmark (:class:`TrackingResult`) lewat signal; frame piksel
hanya diteruskan bila mode Cermin membutuhkannya. Tidak ada frame yang pernah
ditulis ke disk atau dikirim keluar proses.
"""

from __future__ import annotations

import contextlib
import statistics
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
from numpy import typing as npt
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from jarvis_hands.core.config import CameraConfig
from jarvis_hands.vision.tracker import (
    HandTracker,
    TrackerError,
)

__all__ = [
    "CameraController",
    "CameraError",
    "CameraWorker",
    "Frame",
    "FrameSource",
    "OpenCVSource",
]


class CameraError(RuntimeError):
    """Kamera tidak dapat dibuka atau berhenti menghasilkan frame."""


@dataclass(frozen=True)
class Frame:
    """Satu frame RGB siap analisis (uint8 HxWx3)."""

    rgb: npt.NDArray[np.uint8]
    width: int
    height: int
    timestamp_ms: int


class FrameSource(Protocol):
    """Sumber frame yang bisa dibuka/dibaca/dilepas di thread kamera."""

    def open(self) -> None: ...

    def read(self) -> Frame | None: ...

    def release(self) -> None: ...

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...


class OpenCVSource:
    """Sumber kamera OpenCV. ``CAP_DSHOW`` dipakai di Windows bila diizinkan."""

    def __init__(self, config: CameraConfig) -> None:
        self._config = config
        self._capture: Any | None = None
        self._width = max(1, int(config.width))
        self._height = max(1, int(config.height))

    @property
    def width(self) -> int:
        """Lebar frame yang diminta."""
        return self._width

    @property
    def height(self) -> int:
        """Tinggi frame yang diminta."""
        return self._height

    def open(self) -> None:
        """Buka perangkat; raise :class:`CameraError` bila gagal."""
        import cv2

        api = cv2.CAP_ANY
        if sys.platform == "win32" and self._config.use_dshow:
            api = cv2.CAP_DSHOW
        capture = cv2.VideoCapture(int(self._config.index), api)
        if not capture.isOpened():
            capture.release()
            raise CameraError(f"kamera index {self._config.index} tidak dapat dibuka")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(self._config.width))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self._config.height))
        capture.set(cv2.CAP_PROP_FPS, float(self._config.fps))
        self._capture = capture

    def read(self) -> Frame | None:
        """Baca satu frame; None bila kamera berhenti."""
        import cv2

        capture = self._capture
        if capture is None:
            return None
        ok, bgr = capture.read()
        if not ok or bgr is None:
            return None
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        scale = float(self._config.analysis_scale)
        if 0.0 < scale < 1.0:
            width = max(1, int(rgb.shape[1] * scale))
            height = max(1, int(rgb.shape[0] * scale))
            rgb = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_AREA)
        if self._config.mirror:
            rgb = rgb[:, ::-1]
        return Frame(
            rgb=np.ascontiguousarray(rgb),
            width=int(rgb.shape[1]),
            height=int(rgb.shape[0]),
            timestamp_ms=time.monotonic_ns() // 1_000_000,
        )

    def release(self) -> None:
        """Lepas perangkat."""
        capture = self._capture
        self._capture = None
        if capture is not None:
            with contextlib.suppress(Exception):
                capture.release()


class CameraWorker(QObject):
    """Loop kamera yang berjalan di QThread terpisah."""

    #: Frame RGB untuk mode Cermin (payload: :class:`Frame`).
    frame_ready = Signal(object)
    #: Landmark terdeteksi (payload: :class:`TrackingResult`).
    landmarks_ready = Signal(object)
    #: Estimasi FPS analisis (dihitung tiap ~0.5 s).
    fps_changed = Signal(float)
    #: Kamera berhenti bekerja; payload pesan aman untuk pengguna.
    failed = Signal(str)
    #: Loop mulai/benar-benar berhenti.
    running_changed = Signal(bool)
    #: Loop selesai (dipakai untuk menghentikan QThread).
    finished_run = Signal()

    def __init__(
        self,
        config: CameraConfig,
        *,
        source_factory: Callable[[], FrameSource] | None = None,
        tracker_factory: Callable[[], HandTracker] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._source_factory = source_factory or (lambda: OpenCVSource(config))
        self._tracker_factory = tracker_factory or HandTracker
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._active = False

    @property
    def is_active(self) -> bool:
        """True bila loop kamera sedang berjalan."""
        return self._active

    @property
    def is_paused(self) -> bool:
        """True bila loop berjalan tetapi sengaja tidak membaca frame."""
        return self._pause.is_set()

    def stop(self) -> None:
        """Minta loop berhenti secepatnya (aman dipanggil dari thread lain)."""
        self._stop.set()

    def set_paused(self, paused: bool) -> None:
        """Jeda/lanjut pembacaan frame tanpa menutup kamera."""
        if paused:
            self._pause.set()
        else:
            self._pause.clear()

    @Slot()
    def run(self) -> None:
        """Buka kamera, jalankan pelacakan, lalu keluar saat diminta."""
        source = self._source_factory()
        tracker: HandTracker | None = None
        try:
            source.open()
            self._active = True
            self.running_changed.emit(True)
            tracker = self._tracker_factory()
            self._loop(source, tracker)
        except (CameraError, TrackerError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(f"kamera berhenti: {exc}")
        finally:
            if tracker is not None:
                tracker.close()
            source.release()
            self._active = False
            self.running_changed.emit(False)
            self.finished_run.emit()

    def _loop(self, source: FrameSource, tracker: HandTracker) -> None:
        capture_interval = 1.0 / max(1.0, float(self._config.fps))
        analysis_interval = 1.0 / max(1.0, float(self._config.analysis_fps))
        budget_ms = 1000.0 * min(100.0, max(1.0, float(self._config.max_cpu_percent))) / 100.0
        next_tick = time.monotonic()
        next_analysis = 0.0
        stats_started = next_tick
        stats_frames = 0
        infer_times: deque[float] = deque(maxlen=8)
        while not self._stop.is_set():
            if self._pause.is_set():
                time.sleep(0.02)
                next_tick = time.monotonic()
                next_analysis = 0.0
                continue
            frame = source.read()
            if frame is None:
                raise CameraError("kamera berhenti menghasilkan frame")
            self.frame_ready.emit(frame)
            now = time.monotonic()
            if now >= next_analysis:
                started = time.perf_counter()
                result = tracker.detect(frame.rgb, frame.timestamp_ms)
                infer_ms = (time.perf_counter() - started) * 1000.0
                self.landmarks_ready.emit(result)
                stats_frames += 1
                infer_times.append(infer_ms)
                representative = statistics.median(infer_times) if infer_times else 0.0
                throttle = representative / budget_ms if representative > 0.0 else 0.0
                # Median mengabaikan biaya start dingin (ratusan ms) supaya loop
                # tidak tertahan beberapa detik pada frame pertama.
                next_analysis = now + min(0.5, max(analysis_interval, throttle))
            if now - stats_started >= 0.5:
                elapsed = max(1e-6, now - stats_started)
                self.fps_changed.emit(stats_frames / elapsed)
                stats_started = now
                stats_frames = 0
            next_tick += capture_interval
            delay = next_tick - now
            if delay > 0:
                time.sleep(delay)
            else:
                next_tick = now


class CameraController(QObject):
    """Pemilik QThread kamera; API yang dipakai UI."""

    #: Frame RGB untuk mode Cermin.
    frame_ready = Signal(object)
    #: Landmark tangan.
    landmarks_ready = Signal(object)
    #: Kamera menyala/mati (bukan jeda sementara).
    active_changed = Signal(bool)
    #: Kesalahan kamera/tracker.
    error = Signal(str)
    #: FPS analisis.
    fps_changed = Signal(float)

    def __init__(
        self,
        config: CameraConfig,
        *,
        source_factory: Callable[[], FrameSource] | None = None,
        tracker_factory: Callable[[], HandTracker] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._source_factory = source_factory
        self._tracker_factory = tracker_factory
        self._thread: QThread | None = None
        self._worker: CameraWorker | None = None
        self._active = False
        self._last_error = ""

    @property
    def is_active(self) -> bool:
        """True bila thread kamera sedang berjalan."""
        return self._active

    @property
    def is_paused(self) -> bool:
        """True bila loop dijeda."""
        worker = self._worker
        return worker is not None and worker.is_paused

    @property
    def last_error(self) -> str:
        """Pesan kesalahan terakhir (kosong bila tidak ada)."""
        return self._last_error

    @property
    def config(self) -> CameraConfig:
        """Konfigurasi yang dipakai pada penyalaan berikutnya."""
        return self._config

    def set_config(self, config: CameraConfig) -> None:
        """Simpan konfigurasi untuk penyalaan kamera berikutnya.

        Worker yang sedang berjalan memakai salinan konfigurasi saat ``start``;
        perubahan tidak mengganggu sesi aktif dan diterapkan saat kamera
        dinyalakan lagi.
        """
        self._config = config

    def start(self) -> bool:
        """Nyalakan kamera. Return False bila sudah menyala."""
        if self._thread is not None:
            if not self._thread.isFinished():
                return False
            self._thread = None
            self._worker = None
        self._last_error = ""
        thread = QThread()
        thread.setObjectName("jarvis-camera")
        worker = CameraWorker(
            self._config,
            source_factory=self._source_factory,
            tracker_factory=self._tracker_factory,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished_run.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.finished_run.connect(worker.deleteLater)
        worker.running_changed.connect(self._on_running_changed)
        worker.frame_ready.connect(self.frame_ready)
        worker.landmarks_ready.connect(self.landmarks_ready)
        worker.fps_changed.connect(self.fps_changed)
        worker.failed.connect(self._on_failed)
        self._thread = thread
        self._worker = worker
        thread.start()
        return True

    def stop(self, timeout_ms: int = 3000) -> bool:
        """Matikan kamera dan tunggu thread keluar."""
        thread = self._thread
        worker = self._worker
        if thread is None or worker is None:
            return True
        if not thread.isFinished():
            worker.stop()
            worker.set_paused(False)
            thread.quit()
        finished = thread.wait(timeout_ms)
        if finished:
            self._thread = None
            self._worker = None
        if finished and self._active:
            self._active = False
            self.active_changed.emit(False)
        return finished

    def set_enabled(self, enabled: bool) -> bool:
        """Nyalakan/matikan sesuai Mode Gestur."""
        if enabled:
            return self.start()
        return self.stop()

    def toggle(self) -> bool:
        """Balik status kamera; return status aktif setelahnya."""
        if self._active:
            self.stop()
            return False
        self.start()
        return True

    def set_paused(self, paused: bool) -> None:
        """Jeda pembacaan frame (kamera tetap terbuka)."""
        worker = self._worker
        if worker is not None:
            worker.set_paused(paused)

    @Slot(bool)
    def _on_running_changed(self, running: bool) -> None:
        if running and (self._thread is None or self._thread.isFinished()):
            return
        if running == self._active:
            return
        self._active = running
        self.active_changed.emit(running)

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        self._last_error = message
        self.error.emit(message)
