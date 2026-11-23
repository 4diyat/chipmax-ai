"""Tes RingWidget Fase 1: lima status, animasi jam dinding, dan render visual."""

from __future__ import annotations

import hashlib

from PySide6.QtCore import QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from jarvis_hands.core.state import Status
from jarvis_hands.ui.ring import RingWidget
from jarvis_hands.ui.tokens import METRICS, build_theme


class FakeClock:
    """Jam yang bisa dimajukan manual untuk tes deterministik."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


STAGE = QColor("#070D0F")


def _render(ring: RingWidget, background: QColor | None = STAGE) -> QPixmap:
    pixmap = QPixmap(ring.size())
    if background is None:
        pixmap.fill(Qt.GlobalColor.transparent)
    else:
        pixmap.fill(background)
    ring.render(
        pixmap,
        QPoint(0, 0),
        QRegion(ring.rect()),
        QWidget.RenderFlag.DrawChildren,
    )
    return pixmap


def _digest(pixmap: QPixmap) -> str:
    return hashlib.sha256(bytes(pixmap.toImage().constBits())).hexdigest()


def test_geometry_ticks_and_timer() -> None:
    ring = RingWidget(build_theme(), clock=FakeClock())
    assert ring.size() == QSize(METRICS.ring_size, METRICS.ring_size)
    assert ring.sizeHint() == QSize(METRICS.ring_size, METRICS.ring_size)
    assert ring.tick_count == METRICS.ring_ticks == 48
    assert ring.timer_interval_ms <= 17  # 60 fps
    assert len(ring.findChildren(QTimer)) == 1


def test_ring_never_takes_focus() -> None:
    ring = RingWidget(build_theme(), clock=FakeClock())
    assert ring.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert ring.autoFillBackground() is False


def test_status_signal_and_accessible_name(qtbot) -> None:  # type: ignore[no-untyped-def]
    ring = RingWidget(build_theme(), clock=FakeClock())
    seen: list[object] = []
    ring.status_changed.connect(seen.append)
    with qtbot.waitSignal(ring.status_changed):
        ring.set_status(Status.THINKING)
    assert seen == [Status.THINKING]
    assert ring.status is Status.THINKING
    assert ring.accessibleDescription() == "Status BERPIKIR"


def test_level_is_clamped() -> None:
    ring = RingWidget(build_theme(), clock=FakeClock())
    ring.set_level(2.0)
    assert ring.level == 1.0
    ring.set_level(-3.0)
    assert ring.level == 0.0


def test_idle_breathing_uses_wall_clock() -> None:
    clock = FakeClock(0.0)
    ring = RingWidget(build_theme(), clock=clock)
    first = _digest(_render(ring))
    clock.now = 1.125
    second = _digest(_render(ring))
    clock.now = 1.6875
    third = _digest(_render(ring))
    assert len({first, second, third}) == 3


def test_senyap_is_static_and_dim() -> None:
    clock = FakeClock(0.0)
    ring = RingWidget(build_theme(), clock=clock)
    ring.set_status(Status.SENYAP)
    first = _render(ring)
    clock.now = 5.0
    second = _render(ring)
    assert _digest(first) == _digest(second)

    idle = RingWidget(build_theme(), clock=FakeClock(0.0))
    idle_pixel = _render(idle, background=None).toImage().pixelColor(220, 32)
    senyap_pixel = _render(ring, background=None).toImage().pixelColor(220, 32)
    assert senyap_pixel.alpha() < idle_pixel.alpha()


def test_thinking_radar_rotates() -> None:
    clock = FakeClock(0.0)
    ring = RingWidget(build_theme(), clock=clock)
    ring.set_status(Status.THINKING)
    first = _digest(_render(ring))
    clock.now = 0.4
    second = _digest(_render(ring))
    assert first != second


def test_listening_pulse_is_time_based() -> None:
    clock = FakeClock(0.0)
    ring = RingWidget(build_theme(), clock=clock)
    ring.set_status(Status.LISTENING)
    first = _digest(_render(ring))
    clock.now = 0.275  # seperempat periode 1.1 detik
    second = _digest(_render(ring))
    assert first != second


def test_speaking_follows_level() -> None:
    clock = FakeClock(0.0)
    ring = RingWidget(build_theme(), clock=clock)
    ring.set_status(Status.SPEAKING)
    ring.set_level(0.0)
    quiet = _digest(_render(ring))
    clock.now = 0.2
    ring.set_level(1.0)
    loud = _digest(_render(ring))
    assert quiet != loud
    assert ring.normalized_level() == 1.0


def test_auto_gain_keeps_quiet_voice_visible() -> None:
    clock = FakeClock(0.0)
    ring = RingWidget(build_theme(), clock=clock)
    ring.set_status(Status.SPEAKING)
    ring.set_level(0.8)
    clock.now = 3.0
    ring.set_level(0.0)
    assert ring.normalized_level() < 0.2
    ring.set_level(0.05)
    assert ring.normalized_level() > 0.2


def test_status_change_resets_animation_clock() -> None:
    clock = FakeClock(10.0)
    ring = RingWidget(build_theme(), clock=clock)
    ring.set_status(Status.LISTENING)
    assert ring.elapsed == 0.0
    clock.now = 12.0
    assert ring.elapsed == 2.0


def test_all_statuses_render_distinctly() -> None:
    clock = FakeClock(0.0)
    ring = RingWidget(build_theme(), clock=clock)
    digests: set[str] = set()
    for status in Status:
        clock.now = 0.0
        ring.set_status(status)
        if status is Status.SPEAKING:
            ring.set_level(0.8)
        digests.add(_digest(_render(ring)))
    assert len(digests) == len(Status) == 5


def test_ring_is_transparent_outside_the_band() -> None:
    ring = RingWidget(build_theme(), clock=FakeClock())
    pixmap = _render(ring, background=None)
    image = pixmap.toImage()
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(5, 5).alpha() == 0
    assert image.pixelColor(220, 220).alpha() > 0


def test_high_contrast_theme_renders() -> None:
    ring = RingWidget(build_theme(high_contrast=True), clock=FakeClock())
    ring.set_status(Status.SPEAKING)
    ring.set_level(0.9)
    image = _render(ring).toImage()
    assert not image.isNull()
    assert image.pixelColor(220, 32).alpha() > 0


def test_timer_follows_visibility_and_status(qtbot) -> None:  # type: ignore[no-untyped-def]
    ring = RingWidget(build_theme(), clock=FakeClock())
    qtbot.addWidget(ring)
    assert not ring.is_animating()

    ring.show()
    qtbot.wait(20)
    assert ring.is_animating()

    ring.hide()
    qtbot.wait(20)
    assert not ring.is_animating()

    ring.show()
    qtbot.wait(20)
    assert ring.is_animating()

    ring.set_status(Status.SENYAP)
    qtbot.wait(20)
    assert not ring.is_animating()

    ring.set_status(Status.IDLE)
    qtbot.wait(20)
    assert ring.is_animating()
