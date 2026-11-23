"""Sesi kamera: mengikat kamera, hotkey jeda, dan indikator.

Satu objek ini yang dipakai UI pada fase berikutnya: menyalakan kamera hanya
saat Mode Gestur aktif, meneruskan landmark ke kursor, dan menjaga indikator
kamera tetap akurat (aktif / jeda / mati / error).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from jarvis_hands.core.config import CameraConfig
from jarvis_hands.core.hotkey import PauseHotkey
from jarvis_hands.ui.camera import CameraIndicator, CameraState
from jarvis_hands.vision.camera import CameraController

__all__ = ["CameraSession"]


class CameraSession(QObject):
    """Kamera + hotkey Ctrl+Alt+G + indikator dalam satu API."""

    #: Kamera menyala/mati.
    active_changed = Signal(bool)
    #: Mode Gestur dijeda/dilanjutkan.
    paused_changed = Signal(bool)
    #: Kesalahan kamera/tracker.
    error = Signal(str)
    #: FPS analisis.
    fps_changed = Signal(float)
    #: Landmark tangan.
    landmarks_ready = Signal(object)
    #: Frame RGB untuk mode Cermin.
    frame_ready = Signal(object)

    def __init__(
        self,
        config: CameraConfig | None = None,
        *,
        controller: CameraController | None = None,
        hotkey: PauseHotkey | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config or CameraConfig()
        self._controller = controller or CameraController(self._config)
        self._hotkey = hotkey or PauseHotkey()
        self._indicators: list[CameraIndicator] = []
        self._active = False
        self._paused = False

        self._controller.active_changed.connect(self._on_active_changed)
        self._controller.error.connect(self._on_error)
        self._controller.fps_changed.connect(self.fps_changed)
        self._controller.landmarks_ready.connect(self.landmarks_ready)
        self._controller.frame_ready.connect(self.frame_ready)
        self._hotkey.toggled.connect(self.set_paused)

    # ------------------------------------------------------------------ state

    @property
    def controller(self) -> CameraController:
        """Kontroler kamera."""
        return self._controller

    @property
    def hotkey(self) -> PauseHotkey:
        """Hotkey jeda."""
        return self._hotkey

    @property
    def is_active(self) -> bool:
        """True bila kamera menyala."""
        return self._active

    @property
    def is_paused(self) -> bool:
        """True bila Mode Gestur dijeda."""
        return self._paused

    @property
    def state(self) -> CameraState:
        """State untuk indikator kamera."""
        if self._active and self._paused:
            return CameraState.PAUSED
        if self._active:
            return CameraState.ACTIVE
        return CameraState.OFF

    @property
    def hotkey_listening(self) -> bool:
        """True bila backend hotkey global aktif."""
        return self._hotkey.is_listening

    # ------------------------------------------------------------------ control

    def attach_indicator(self, indicator: CameraIndicator) -> None:
        """Tambah indikator yang selalu mengikuti state sesi."""
        if indicator not in self._indicators:
            self._indicators.append(indicator)
        indicator.set_state(self.state)

    def start(self) -> bool:
        """Nyalakan kamera dan hotkey. Return False bila kamera gagal menyala."""
        started = self._controller.start()
        if started:
            self._hotkey.start()
        return started

    def stop(self) -> bool:
        """Matikan kamera dan hotkey."""
        stopped = self._controller.stop()
        if self._hotkey.is_listening:
            self._hotkey.stop()
        if self._paused:
            self._paused = False
            self.paused_changed.emit(False)
        self._hotkey.set_paused(False)
        return stopped

    def set_paused(self, paused: bool) -> None:
        """Jeda/lanjut pembacaan frame tanpa menutup kamera."""
        paused = bool(paused)
        if not self._active or paused == self._paused:
            return
        self._paused = paused
        self._hotkey.set_paused(paused)
        self._controller.set_paused(paused)
        self._sync_indicators()
        self.paused_changed.emit(paused)

    def toggle(self) -> bool:
        """Balik status jeda; return status baru."""
        self.set_paused(not self._paused)
        return self._paused

    def set_enabled(self, enabled: bool) -> bool:
        """Nyalakan/matikan sesuai Mode Gestur."""
        return self.start() if enabled else self.stop()

    # ------------------------------------------------------------------ slots

    def _on_active_changed(self, active: bool) -> None:
        self._active = bool(active)
        if not active and self._hotkey.is_listening:
            self._hotkey.stop()
        if not active and self._paused:
            self._paused = False
            self.paused_changed.emit(False)
        if not active:
            self._hotkey.set_paused(False)
        self._sync_indicators()
        self.active_changed.emit(self._active)

    def _on_error(self, message: str) -> None:
        if self._hotkey.is_listening:
            self._hotkey.stop()
        for indicator in self._indicators:
            indicator.set_error()
        self.error.emit(message)

    def _sync_indicators(self) -> None:
        state = self.state
        for indicator in self._indicators:
            indicator.set_state(state)
