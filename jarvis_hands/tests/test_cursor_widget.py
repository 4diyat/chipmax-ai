"""Tes widget kursor 28 px dan CursorPresenter."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt

from jarvis_hands.tests.support import make_hand, make_result
from jarvis_hands.ui.cursor import CursorPresenter, CursorWidget
from jarvis_hands.ui.tokens import METRICS
from jarvis_hands.vision.cursor import CursorTracker


def test_widget_size_and_flags(qapp: object) -> None:
    widget = CursorWidget()
    assert widget.size_px == METRICS.cursor_size == 28
    assert widget.width() == 28 and widget.height() == 28
    assert widget.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert widget.windowFlags() & Qt.WindowType.Tool
    assert widget.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert widget.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert widget.focusPolicy() == Qt.FocusPolicy.NoFocus
    widget.close()


def test_pinch_and_dwell_paint(qapp: object, qtbot: object) -> None:
    widget = CursorWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    widget.show()
    qtbot.waitExposed(widget)  # type: ignore[attr-defined]
    image = widget.grab().toImage()
    assert image.pixelColor(14, 14).alpha() > 0

    widget.set_pinch(1.0, True)
    assert widget.pinch == pytest.approx(1.0)
    assert bool(widget.pinching)
    filled = widget.grab().toImage()
    assert filled.pixelColor(14, 14).alpha() > 0

    widget.set_dwell(0.5)
    assert widget.dwell == pytest.approx(0.5)
    assert widget.grab().toImage().pixelColor(14, 14).alpha() > 0


def test_move_to_centers_on_point(qapp: object) -> None:
    widget = CursorWidget()
    moves: list[QPoint] = []
    widget.moved.connect(moves.append)
    widget.move_to(QPoint(100, 120))
    assert widget.center == QPoint(100, 120)
    assert widget.pos() == QPoint(86, 106)
    assert moves == [QPoint(100, 120)]
    widget.close()


def test_hand_visible_changes_ring(qapp: object, qtbot: object) -> None:
    widget = CursorWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    widget.show()
    qtbot.waitExposed(widget)  # type: ignore[attr-defined]
    widget.set_hand_visible(True)
    assert widget.grab().toImage().pixelColor(14, 14).alpha() > 0
    widget.close()


def test_presenter_updates_widget_and_signals(qapp: object) -> None:
    widget = CursorWidget()
    tracker = CursorTracker(screen_width=1920, screen_height=1080)
    presenter = CursorPresenter(tracker=tracker, widget=widget)
    pinches: list[bool] = []
    visible: list[bool] = []
    samples: list[object] = []
    presenter.pinch_changed.connect(pinches.append)
    presenter.visibility_changed.connect(visible.append)
    presenter.sample_ready.connect(samples.append)

    first = presenter.process(make_result(make_hand(pinch_ratio=0.2), timestamp_ms=0))
    assert first.visible and first.pinching
    assert widget.center == QPoint(960, 540)
    assert bool(widget.pinching)
    assert pinches == [True]
    assert visible == [True]
    assert len(samples) == 1
    assert presenter.hand_visible

    lost = presenter.process(make_result(None, timestamp_ms=50))
    assert not lost.visible
    assert pinches == [True, False]
    assert visible == [True, False]
    assert not bool(widget.pinching)

    presenter.reset()
    assert presenter.last_sample is None
    assert widget.dwell == pytest.approx(0.0)
    widget.close()


def test_presenter_emits_pinch_only_on_change(qapp: object) -> None:
    presenter = CursorPresenter(tracker=CursorTracker(screen_width=800, screen_height=600))
    pinches: list[bool] = []
    presenter.pinch_changed.connect(pinches.append)
    for i in range(3):
        presenter.process(make_result(make_hand(pinch_ratio=0.2), timestamp_ms=i * 33))
    assert pinches == [True]
    for i in range(3, 6):
        presenter.process(make_result(make_hand(pinch_ratio=0.6), timestamp_ms=i * 33))
    assert pinches == [True, False]


def test_presenter_without_widget(qapp: object) -> None:
    presenter = CursorPresenter(tracker=CursorTracker(screen_width=800, screen_height=600))
    sample = presenter.process(make_result(make_hand(index=(0.5, 0.5))))
    assert sample.point == (400, 300)


def test_widget_is_top_level_tool_window(qapp: object) -> None:
    widget = CursorWidget()
    assert widget.isWindow()
    widget.close()
