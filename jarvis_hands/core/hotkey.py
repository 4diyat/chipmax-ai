"""Hotkey global Ctrl+Alt+G untuk menjeda/ melanjutkan Mode Gestur.

``pynput`` hanya dipasang di platform non-Linux (lihat ``pyproject.toml``);
di Linux/Wayland tanpa pynput dipakai fallback Qt yang bekerja saat aplikasi
memegang fokus. Karena overlay memang dirancang tanpa fokus, fallback ini
bukan jalan utama di Linux: pengguna tetap punya tombol UI dan pemanggilan
programatik :meth:`PauseHotkey.toggle`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent

__all__ = [
    "HotkeySpec",
    "PauseHotkey",
    "PynputBackend",
    "QtFallbackBackend",
    "parse_hotkey",
]


class HotkeyBackend(Protocol):
    """Kontrak backend hotkey; bisa dipalsukan di tes."""

    def start(self, on_activate: Callable[[], None]) -> bool: ...

    def stop(self) -> None: ...


@dataclass(frozen=True)
class HotkeySpec:
    """Kombinasi tombol: modifier terurut + satu tombol utama."""

    key: str
    ctrl: bool = False
    alt: bool = False
    shift: bool = False

    @property
    def label(self) -> str:
        """Label human-readable, mis. ``Ctrl+Alt+G``."""
        parts: list[str] = []
        if self.ctrl:
            parts.append("Ctrl")
        if self.alt:
            parts.append("Alt")
        if self.shift:
            parts.append("Shift")
        parts.append(self.key.upper())
        return "+".join(parts)


def parse_hotkey(value: str) -> HotkeySpec:
    """Parse ``ctrl+alt+g``; hanya satu tombol utama yang diizinkan."""
    parts = [part.strip().lower() for part in value.split("+") if part.strip()]
    if not parts:
        raise ValueError("kombinasi hotkey tidak boleh kosong")
    ctrl = alt = shift = False
    keys: list[str] = []
    for part in parts:
        if part in {"ctrl", "control"}:
            ctrl = True
        elif part == "alt":
            alt = True
        elif part == "shift":
            shift = True
        else:
            keys.append(part)
    if len(keys) != 1:
        raise ValueError(f"hotkey membutuhkan tepat satu tombol utama: {value!r}")
    key = keys[0]
    if not key.isalnum() or len(key) != 1:
        raise ValueError(f"tombol utama hotkey tidak valid: {key!r}")
    return HotkeySpec(key=key, ctrl=ctrl, alt=alt, shift=shift)


class PynputBackend:
    """Hotkey global via pynput (bila terpasang)."""

    def __init__(self, spec: HotkeySpec) -> None:
        self._spec = spec
        self._listener: Any | None = None

    @staticmethod
    def is_available() -> bool:
        """True bila pynput dapat diimpor di platform ini."""
        try:
            import pynput  # noqa: F401
        except Exception:
            return False
        return True

    def start(self, on_activate: Callable[[], None]) -> bool:
        """Mulai listener; return False bila pynput tidak tersedia."""
        try:
            from pynput import keyboard
        except Exception:
            return False
        combo = ""
        if self._spec.ctrl:
            combo += "<ctrl>+"
        if self._spec.alt:
            combo += "<alt>+"
        if self._spec.shift:
            combo += "<shift>+"
        combo += self._spec.key
        listener = keyboard.GlobalHotKeys({combo: on_activate})
        listener.daemon = True
        listener.start()
        self._listener = listener
        return True

    def stop(self) -> None:
        """Hentikan listener."""
        listener = self._listener
        self._listener = None
        if listener is not None:
            with contextlib.suppress(Exception):
                listener.stop()


class QtFallbackBackend(QObject):
    """Fallback: tangkap Ctrl+Alt+G saat aplikasi memegang fokus."""

    def __init__(self, spec: HotkeySpec, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._spec = spec
        self._on_activate: Callable[[], None] | None = None

    def start(self, on_activate: Callable[[], None]) -> bool:
        """Pasang event filter aplikasi."""
        app = QGuiApplication.instance()
        if app is None:
            return False
        self._on_activate = on_activate
        app.installEventFilter(self)
        return True

    def stop(self) -> None:
        """Lepas event filter."""
        app = QGuiApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._on_activate = None

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Cocokkan KeyPress dengan kombinasi hotkey."""
        if event.type() != QEvent.Type.KeyPress or self._on_activate is None:
            return super().eventFilter(watched, event)
        assert isinstance(event, QKeyEvent)
        key = chr(event.key()).lower() if 0x20 < event.key() < 0x7F else ""
        modifiers = event.modifiers()
        mask = (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.ShiftModifier
        )
        expected = Qt.KeyboardModifier.NoModifier
        if self._spec.ctrl:
            expected |= Qt.KeyboardModifier.ControlModifier
        if self._spec.alt:
            expected |= Qt.KeyboardModifier.AltModifier
        if self._spec.shift:
            expected |= Qt.KeyboardModifier.ShiftModifier
        if key == self._spec.key and (modifiers & mask) == expected:
            self._on_activate()
            return True
        return super().eventFilter(watched, event)


class PauseHotkey(QObject):
    """Jeda/lanjut Mode Gestur, lewat hotkey global atau pemanggilan langsung."""

    #: Status jeda baru (True = gestur dijeda, kamera tidak membaca frame).
    toggled = Signal(bool)

    def __init__(
        self,
        combination: str = "ctrl+alt+g",
        *,
        backend: HotkeyBackend | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._spec = parse_hotkey(combination)
        self._backend: HotkeyBackend = backend or self._default_backend()
        self._paused = False
        self._listening = False

    @property
    def spec(self) -> HotkeySpec:
        """Kombinasi tombol aktif."""
        return self._spec

    @property
    def paused(self) -> bool:
        """True bila Mode Gestur sedang dijeda."""
        return self._paused

    @property
    def is_listening(self) -> bool:
        """True bila backend hotkey aktif."""
        return self._listening

    def start(self) -> bool:
        """Mulai mendengarkan hotkey."""
        if self._listening:
            return True
        self._listening = bool(self._backend.start(self._activate))
        return self._listening

    def stop(self) -> None:
        """Hentikan backend."""
        self._backend.stop()
        self._listening = False

    def _activate(self) -> None:
        """Callback backend hotkey; abaikan nilai kembalian toggle."""
        self.toggle()

    def toggle(self) -> bool:
        """Balik status jeda; return status baru."""
        self._paused = not self._paused
        self.toggled.emit(self._paused)
        return self._paused

    def set_paused(self, paused: bool) -> bool:
        """Atur status jeda; hanya memancarkan signal bila berubah."""
        if paused == self._paused:
            return self._paused
        return self.toggle()

    def _default_backend(self) -> HotkeyBackend:
        if PynputBackend.is_available():
            return PynputBackend(self._spec)
        return QtFallbackBackend(self._spec, self)
