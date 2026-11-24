"""Toggle chrome overlay ``Ctrl+Alt+C``: pilih apa yang tampil di layar.

Tiga status, berputar tiap kali hotkey ditekan:

1. **ON** — cincin, orb, dan kartu selalu terlihat.
2. **OFF** — chrome disembunyikan, hanya indikator kamera yang tetap (janji
   privasi) dan sebuah titik 16 px di bawah layar sebagai petunjuk.
3. **SENYAP** — auto-hide normal: chrome menghilang setelah idle, titik yang sama
   muncul sebagai gantinya.

Kelas ini hanya menyimpan status dan memancarkan sinyal; overlay yang memutuskan
widget mana yang disembunyikan, sehingga perilakunya mudah dites tanpa Qt.
"""

from __future__ import annotations

from enum import StrEnum, unique

from PySide6.QtCore import QObject, Signal

__all__ = ["ChromeMode", "ChromeToggle"]


@unique
class ChromeMode(StrEnum):
    """Status tampilan chrome."""

    ON = "on"
    OFF = "off"
    SENYAP = "senyap"

    def next(self) -> ChromeMode:
        """Status berikutnya saat hotkey ditekan."""
        order = (ChromeMode.ON, ChromeMode.OFF, ChromeMode.SENYAP)
        return order[(order.index(self) + 1) % len(order)]

    @property
    def label(self) -> str:
        """Label pendek untuk UI."""
        return {
            ChromeMode.ON: "Chrome tampil",
            ChromeMode.OFF: "Chrome disembunyikan",
            ChromeMode.SENYAP: "Auto-hide aktif",
        }[self]


class ChromeToggle(QObject):
    """Status chrome + sinyal perubahan."""

    #: Status berubah (payload: :class:`ChromeMode`).
    mode_changed = Signal(object)

    def __init__(self, mode: ChromeMode = ChromeMode.ON, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._mode = ChromeMode(mode)

    @property
    def mode(self) -> ChromeMode:
        """Status saat ini."""
        return self._mode

    def cycle(self) -> ChromeMode:
        """Pindah ke status berikutnya; return status baru."""
        self.set_mode(self._mode.next())
        return self._mode

    def set_mode(self, mode: ChromeMode) -> None:
        """Set status; sinyal hanya dipancarkan bila berubah."""
        mode = ChromeMode(mode)
        if mode is self._mode:
            return
        self._mode = mode
        self.mode_changed.emit(mode)
