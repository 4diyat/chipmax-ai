"""Tes CursorTracker: pemetaan layar, One-Euro, dan histeresis cubit."""

from __future__ import annotations

import pytest

from jarvis_hands.core.config import CursorConfig, GestureThresholds
from jarvis_hands.tests.support import make_hand, make_result
from jarvis_hands.vision.cursor import CursorTracker


def test_center_maps_to_screen_center() -> None:
    tracker = CursorTracker(screen_width=1920, screen_height=1080)
    sample = tracker.update(make_result(make_hand(index=(0.5, 0.5))))
    assert sample.visible
    assert sample.point == (960, 540)


def test_gain_amplifies_movement() -> None:
    tracker = CursorTracker(
        screen_width=1000, screen_height=1000, cursor_config=CursorConfig(gain=2.0)
    )
    sample = tracker.update(make_result(make_hand(index=(0.6, 0.5))))
    assert sample.x == pytest.approx(700)


def test_clamps_to_screen_bounds() -> None:
    tracker = CursorTracker(
        screen_width=800, screen_height=600, cursor_config=CursorConfig(gain=4.0)
    )
    sample = tracker.update(make_result(make_hand(index=(0.0, 0.0))))
    assert sample.x == 0
    assert sample.y == 0
    sample = tracker.update(make_result(make_hand(index=(1.0, 1.0)), timestamp_ms=16))
    assert sample.x == 799
    assert sample.y == 599


def test_pinch_hysteresis() -> None:
    tracker = CursorTracker(screen_width=800, screen_height=600)
    thresholds = GestureThresholds(pinch_close=0.30, pinch_open=0.45)
    tracker = CursorTracker(screen_width=800, screen_height=600, thresholds=thresholds)
    assert tracker.update(make_result(make_hand(pinch_ratio=0.6), timestamp_ms=0)).pinching is False
    closed = tracker.update(make_result(make_hand(pinch_ratio=0.25), timestamp_ms=16))
    assert closed.pinching is True
    assert closed.pinch == pytest.approx(1.0)
    between = tracker.update(make_result(make_hand(pinch_ratio=0.35), timestamp_ms=32))
    assert between.pinching is True
    opened = tracker.update(make_result(make_hand(pinch_ratio=0.5), timestamp_ms=48))
    assert opened.pinching is False
    assert opened.pinch == pytest.approx(0.0, abs=1e-6)


def test_hand_loss_hides_cursor_and_releases_pinch() -> None:
    tracker = CursorTracker(screen_width=800, screen_height=600)
    tracker.update(make_result(make_hand(pinch_ratio=0.2)))
    lost = tracker.update(make_result(None, timestamp_ms=100))
    assert lost.visible is False
    assert lost.pinching is False
    assert tracker.pinching is False


def test_small_hand_is_hidden() -> None:
    tracker = CursorTracker(screen_width=800, screen_height=600)
    sample = tracker.update(make_result(make_hand(hand_size=0.01)))
    assert sample.visible is False


def test_set_screen_changes_mapping() -> None:
    tracker = CursorTracker(screen_width=1000, screen_height=1000)
    tracker.set_screen(500, 400, origin_x=100, origin_y=50)
    sample = tracker.update(make_result(make_hand(index=(0.5, 0.5))))
    assert sample.point == (350, 250)


def test_one_euro_smooths_jitter() -> None:
    tracker = CursorTracker(screen_width=1000, screen_height=1000)
    xs: list[float] = []
    raw: list[float] = []
    for i in range(40):
        nx = 0.5 + (0.02 if i % 2 else -0.02)
        raw.append(nx)
        xs.append(tracker.update(make_result(make_hand(index=(nx, 0.5)), timestamp_ms=i * 33)).x)
    raw_span = (max(raw) - min(raw)) * 1000 * 1.6
    assert max(xs) - min(xs) < raw_span


def test_reset_clears_state() -> None:
    tracker = CursorTracker(screen_width=800, screen_height=600)
    tracker.update(make_result(make_hand(pinch_ratio=0.2)))
    assert bool(tracker.pinching)
    tracker.reset()
    assert not bool(tracker.pinching)
    assert tracker.last is None
