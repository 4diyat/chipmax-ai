"""Tes tipe event gestur."""

from __future__ import annotations

import dataclasses

import pytest

from jarvis_hands.gestures.types import GestureEvent, GestureKind, GesturePhase


def test_kind_values() -> None:
    assert [kind.value for kind in GestureKind] == [
        "tap",
        "drag",
        "hold",
        "two_hand",
        "clap",
        "scrub_explode",
        "swipe",
        "fist",
    ]


def test_phase_values() -> None:
    assert [phase.value for phase in GesturePhase] == [
        "begin",
        "update",
        "end",
        "one_shot",
    ]


def test_event_position_and_flags() -> None:
    event = GestureEvent(
        kind=GestureKind.DRAG,
        phase=GesturePhase.BEGIN,
        timestamp_ms=100,
        x=10,
        y=20,
        magnitude=30.0,
    )
    assert event.position == (10, 20)
    assert event.is_begin
    assert not event.is_end
    assert event.hands == 1
    assert event.cancelled is False
    assert event.direction == ""


def test_event_is_frozen() -> None:
    event = GestureEvent(
        kind=GestureKind.TAP,
        phase=GesturePhase.ONE_SHOT,
        timestamp_ms=0,
        x=0,
        y=0,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.x = 5  # type: ignore[misc]


def test_end_event_flag() -> None:
    event = GestureEvent(
        kind=GestureKind.DRAG,
        phase=GesturePhase.END,
        timestamp_ms=0,
        x=0,
        y=0,
        cancelled=True,
    )
    assert event.is_end
    assert event.cancelled
