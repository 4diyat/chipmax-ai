"""Tes auto-hide chrome overlay: jeda idle, poke, hold, dan nonaktif."""

from __future__ import annotations

from typing import Any

from jarvis_hands.ui.autohide import AutoHideController


class FakeClock:
    """Jam suntik yang deterministik."""

    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_hides_after_idle_and_poke_restores(qapp: Any) -> None:
    clock = FakeClock()
    controller = AutoHideController(2, clock=clock)
    changes: list[bool] = []
    controller.hidden_changed.connect(changes.append)

    assert controller.enabled
    assert bool(controller.is_hidden) is False
    clock.now += 1.0
    assert controller.tick() is False
    clock.now += 1.0
    assert controller.tick() is True
    assert changes == [True]
    assert bool(controller.is_hidden) is True

    controller.poke()
    assert bool(controller.is_hidden) is False
    assert changes == [True, False]
    assert controller.idle_ms == 0.0


def test_disabled_never_hides(qapp: Any) -> None:
    clock = FakeClock()
    controller = AutoHideController(1, enabled=False, clock=clock)
    clock.now += 60.0
    assert controller.tick() is False
    assert bool(controller.is_hidden) is False


def test_hold_blocks_hide_and_release_rearms(qapp: Any) -> None:
    clock = FakeClock()
    controller = AutoHideController(1, clock=clock)
    controller.set_hold(True)
    clock.now += 10.0
    assert controller.tick() is False
    controller.set_hold(False)
    clock.now += 0.5
    assert controller.tick() is False
    clock.now += 0.6
    assert controller.tick() is True


def test_set_delay_and_disable_restore(qapp: Any) -> None:
    clock = FakeClock()
    controller = AutoHideController(1, clock=clock)
    clock.now += 5.0
    assert controller.tick() is True
    controller.set_enabled(False)
    assert bool(controller.is_hidden) is False
    controller.set_delay_s(3)
    assert controller.delay_s == 3
    controller.set_enabled(True)
    clock.now += 2.0
    assert controller.tick() is False
    clock.now += 1.1
    assert controller.tick() is True
