"""Tes bus signal internal."""

from __future__ import annotations

from jarvis_hands.core.bus import Bus
from jarvis_hands.core.state import Status


def test_status_signal(qtbot) -> None:  # type: ignore[no-untyped-def]
    bus = Bus()
    seen: list[object] = []
    bus.status_changed.connect(seen.append)
    with qtbot.waitSignal(bus.status_changed):
        bus.set_status(Status.THINKING)
    assert seen == [Status.THINKING]


def test_level_is_clamped(qtbot) -> None:  # type: ignore[no-untyped-def]
    bus = Bus()
    levels: list[float] = []
    bus.level_changed.connect(levels.append)
    bus.set_level(1.7)
    bus.set_level(-0.2)
    bus.set_level(0.4)
    assert levels == [1.0, 0.0, 0.4]


def test_toast_signal(qtbot) -> None:  # type: ignore[no-untyped-def]
    bus = Bus()
    seen: list[str] = []
    bus.toast.connect(seen.append)
    with qtbot.waitSignal(bus.toast):
        bus.show_toast("Mode gestur aktif")
    assert seen == ["Mode gestur aktif"]
