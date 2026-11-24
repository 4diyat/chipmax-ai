"""Auto-hide chrome overlay setelah idle.

Modul ini hanya menghitung waktu idle dan memancarkan ``hidden_changed``;
pemilik (overlay) yang memutuskan widget mana yang disembunyikan. Indikator
kamera tidak pernah ikut disembunyikan karena merupakan janji privasi produk.
Jam bisa disuntik supaya perilaku deterministik di tes.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal

__all__ = ["AutoHideController"]


class AutoHideController(QObject):
    """Sembunyikan chrome setelah ``delay_s`` detik tanpa aktivitas."""

    #: Chrome seharusnya disembunyikan/ditampilkan lagi.
    hidden_changed = Signal(bool)

    def __init__(
        self,
        delay_s: int = 10,
        *,
        enabled: bool = True,
        parent: QObject | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self._clock = clock
        self._delay_s = max(1, int(delay_s))
        self._enabled = bool(enabled)
        self._hold = False
        self._hidden = False
        self._last_activity = float(clock())
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_timeout)
        self._arm()

    # ------------------------------------------------------------------ state

    @property
    def delay_s(self) -> int:
        """Jeda idle sebelum chrome disembunyikan (detik)."""
        return self._delay_s

    @property
    def enabled(self) -> bool:
        """True bila auto-hide aktif."""
        return self._enabled

    @property
    def is_hidden(self) -> bool:
        """True bila chrome sedang disembunyikan."""
        return self._hidden

    @property
    def idle_ms(self) -> float:
        """Milidetik sejak aktivitas terakhir."""
        return max(0.0, (float(self._clock()) - self._last_activity) * 1000.0)

    # ------------------------------------------------------------------ input

    def poke(self) -> None:
        """Catat aktivitas; tampilkan lagi chrome bila sedang disembunyikan."""
        self._last_activity = float(self._clock())
        if self._hidden:
            self._set_hidden(False)
        self._arm()

    def set_delay_s(self, delay_s: int) -> None:
        """Ganti jeda idle (1..600 detik)."""
        self._delay_s = max(1, min(600, int(delay_s)))
        self._arm()

    def set_enabled(self, enabled: bool) -> None:
        """Nyalakan/matikan auto-hide tanpa kehilangan status lain."""
        enabled = bool(enabled)
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            self._last_activity = float(self._clock())
            self._arm()
        else:
            self._timer.stop()
            if self._hidden:
                self._set_hidden(False)

    def set_hold(self, hold: bool) -> None:
        """Tahan chrome tetap terlihat (misal saat agen sedang BERPIKIR)."""
        hold = bool(hold)
        if hold == self._hold:
            return
        self._hold = hold
        if hold:
            self._timer.stop()
        else:
            self._last_activity = float(self._clock())
            self._arm()

    # ------------------------------------------------------------------ clock

    def tick(self) -> bool:
        """Evaluasi idle sekarang; return status ``is_hidden`` setelahnya.

        Dipanggil oleh QTimer, tetapi juga bisa dipanggil langsung di tes dengan
        jam suntik. Bila jeda belum tercapai, timer dijadwalkan ulang.
        """
        if not self._enabled or self._hold:
            return self._hidden
        if self._hidden:
            return True
        if self.idle_ms >= self._delay_s * 1000.0:
            self._set_hidden(True)
            return True
        self._arm()
        return False

    # ------------------------------------------------------------------ private

    def _arm(self) -> None:
        self._timer.stop()
        if not self._enabled or self._hold or self._hidden:
            return
        self._timer.start(self._delay_s * 1000)

    def _on_timeout(self) -> None:
        self.tick()

    def _set_hidden(self, hidden: bool) -> None:
        hidden = bool(hidden)
        if hidden == self._hidden:
            return
        self._hidden = hidden
        if hidden:
            self._timer.stop()
        self.hidden_changed.emit(hidden)
