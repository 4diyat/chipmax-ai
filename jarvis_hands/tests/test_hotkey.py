"""Tes hotkey jeda: parsing, toggle, backend tiruan, dan fallback Qt."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from jarvis_hands.core.hotkey import (
    HotkeySpec,
    PauseHotkey,
    QtFallbackBackend,
    parse_hotkey,
)


class FakeBackend:
    """Backend hotkey yang mencatat start/stop dan bisa dipicu manual."""

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


def test_parse_hotkey_defaults() -> None:
    spec = parse_hotkey("ctrl+alt+g")
    assert spec == HotkeySpec(key="g", ctrl=True, alt=True)
    assert spec.label == "Ctrl+Alt+G"


def test_parse_hotkey_alternatives() -> None:
    assert parse_hotkey("Control+Shift+G").key == "g"
    assert parse_hotkey("alt+g").alt is True
    assert parse_hotkey("g").ctrl is False


@pytest.mark.parametrize("value", ["", "ctrl", "ctrl+alt+g+x", "ctrl+", "ctrl+$$"])
def test_parse_hotkey_rejects_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        parse_hotkey(value)


def test_toggle_and_signals() -> None:
    backend = FakeBackend()
    hotkey = PauseHotkey(backend=backend)
    states: list[bool] = []
    hotkey.toggled.connect(states.append)
    assert hotkey.start() is True
    assert backend.started == 1
    assert hotkey.is_listening
    assert hotkey.toggle() is True
    assert hotkey.paused
    assert hotkey.set_paused(True) is True
    assert len(states) == 1
    assert hotkey.set_paused(False) is False
    assert states == [True, False]
    hotkey.stop()
    assert backend.stopped == 1
    assert not hotkey.is_listening


def test_backend_activation_toggles(qapp: object) -> None:
    backend = FakeBackend()
    hotkey = PauseHotkey(backend=backend)
    hotkey.start()
    assert not bool(hotkey.paused)
    backend.activate()
    assert bool(hotkey.paused)
    backend.activate()
    assert not bool(hotkey.paused)


def test_qt_fallback_backend_matches_shortcut(qapp: object, qtbot: object) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    widget.show()
    spec = parse_hotkey("ctrl+alt+g")
    backend = QtFallbackBackend(spec)
    hotkey = PauseHotkey(backend=backend)
    states: list[bool] = []
    hotkey.toggled.connect(states.append)
    assert hotkey.start() is True

    QTest.keyClick(
        widget, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
    )
    assert states == [True]
    assert hotkey.paused

    QTest.keyClick(widget, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
    assert states == [True]
    backend.stop()
