"""Tes mesin gestur: tap, drag, hold, two-hand, clap, scrub-explode."""

from __future__ import annotations

import pytest

from jarvis_hands.core.config import GestureThresholds
from jarvis_hands.gestures.engine import GestureEngine
from jarvis_hands.gestures.types import GestureEvent, GestureKind, GesturePhase
from jarvis_hands.tests.support import make_hand, make_result, make_result_multi
from jarvis_hands.vision.tracker import TrackingResult

CENTER = (0.5, 0.5)


def _run(
    frames: list[TrackingResult],
    *,
    thresholds: GestureThresholds | None = None,
) -> list[GestureEvent]:
    engine = GestureEngine(thresholds=thresholds)
    events: list[GestureEvent] = []
    for frame in frames:
        events.extend(engine.process(frame))
    return events


def _open(ts: int, index: tuple[float, float] = CENTER) -> TrackingResult:
    return make_result(make_hand(index=index), timestamp_ms=ts)


def _closed(ts: int, index: tuple[float, float] = CENTER) -> TrackingResult:
    return make_result(make_hand(index=index, pinch_ratio=0.15), timestamp_ms=ts)


def test_tap_emits_one_shot() -> None:
    frames = [_open(i * 33) for i in range(5)]
    frames += [_closed(165 + i * 33) for i in range(4)]
    frames += [_open(297 + i * 33) for i in range(3)]
    events = _run(frames)
    taps = [e for e in events if e.kind is GestureKind.TAP]
    assert len(taps) == 1
    tap = taps[0]
    assert tap.phase is GesturePhase.ONE_SHOT
    assert tap.timestamp_ms == 297
    assert tap.magnitude == pytest.approx(132.0)
    assert tap.position == (960, 540)
    assert len(events) == 1


def test_short_pinch_is_not_tap() -> None:
    frames = [_open(i * 33) for i in range(4)]
    frames += [_closed(132)]
    frames += [_open(165 + i * 33) for i in range(3)]
    assert _run(frames) == []


def test_long_pinch_is_not_tap_or_hold() -> None:
    frames = [_open(i * 33) for i in range(4)]
    frames += [_closed(132 + i * 33) for i in range(12)]
    frames += [_open(528 + i * 33) for i in range(3)]
    assert _run(frames) == []


def test_hold_emits_begin_update_end() -> None:
    frames = [_open(i * 33) for i in range(4)]
    frames += [_closed(132 + i * 33) for i in range(40)]
    frames += [_open(1452 + i * 33) for i in range(3)]
    events = _run(frames)
    holds = [e for e in events if e.kind is GestureKind.HOLD]
    assert holds[0].phase is GesturePhase.BEGIN
    assert holds[0].magnitude == pytest.approx(1023.0)
    assert holds[-1].phase is GesturePhase.END
    assert holds[-1].magnitude == pytest.approx(1320.0)
    assert all(e.kind is GestureKind.HOLD for e in events)
    assert sum(1 for e in holds if e.phase is GesturePhase.UPDATE) >= 5


def test_drag_emits_begin_updates_end() -> None:
    frames = [_open(i * 33) for i in range(4)]
    frames += [_closed(132 + i * 33) for i in range(2)]
    for step in range(10):
        frames.append(
            make_result(
                make_hand(index=(0.5 + step * 0.005, 0.5), pinch_ratio=0.15),
                timestamp_ms=198 + step * 33,
            )
        )
    frames += [_open(528 + i * 33, (0.55, 0.5)) for i in range(3)]
    events = _run(frames)
    drags = [e for e in events if e.kind is GestureKind.DRAG]
    assert drags[0].phase is GesturePhase.BEGIN
    assert drags[-1].phase is GesturePhase.END
    assert sum(1 for e in drags if e.phase is GesturePhase.UPDATE) >= 5
    assert all(e.kind is GestureKind.DRAG for e in events)
    assert drags[-1].cancelled is False


def test_hand_loss_cancels_drag() -> None:
    frames = [_open(i * 33) for i in range(3)]
    frames += [_closed(99)]
    frames += [
        make_result(
            make_hand(index=(0.55, 0.5), pinch_ratio=0.15),
            timestamp_ms=132,
        )
    ]
    frames += [make_result(None, timestamp_ms=165)]
    events = _run(frames)
    drags = [e for e in events if e.kind is GestureKind.DRAG]
    assert len(drags) == 3
    assert drags[-1].phase is GesturePhase.END
    assert drags[-1].cancelled is True


def test_two_hand_begin_and_end() -> None:
    frames = []
    ts = 0
    for step in range(30):
        offset = 0.1 - step * 0.0032
        frames.append(
            make_result_multi(
                (
                    make_hand(index=(0.5 - offset, 0.5), handedness="Left"),
                    make_hand(index=(0.5 + offset, 0.5), handedness="Right"),
                ),
                timestamp_ms=ts,
            )
        )
        ts += 33
    for _ in range(5):
        frames.append(
            make_result_multi(
                (
                    make_hand(index=(0.5 - 0.01, 0.5), handedness="Left"),
                    make_hand(index=(0.5 + 0.01, 0.5), handedness="Right"),
                ),
                timestamp_ms=ts,
            )
        )
        ts += 33
    for step in range(25):
        offset = 0.01 + step * 0.0032
        frames.append(
            make_result_multi(
                (
                    make_hand(index=(0.5 - offset, 0.5), handedness="Left"),
                    make_hand(index=(0.5 + offset, 0.5), handedness="Right"),
                ),
                timestamp_ms=ts,
            )
        )
        ts += 33
    events = _run(frames)
    two = [e for e in events if e.kind is GestureKind.TWO_HAND]
    assert two[0].phase is GesturePhase.BEGIN
    assert two[-1].phase is GesturePhase.END
    assert two[0].hands == 2
    assert not [e for e in events if e.kind is GestureKind.CLAP]


def test_clap_requires_fast_approach() -> None:
    frames = []
    ts = 0
    for step in range(4):
        offset = 0.12 - step * 0.03
        frames.append(
            make_result_multi(
                (
                    make_hand(index=(0.5 - offset, 0.5), handedness="Left"),
                    make_hand(index=(0.5 + offset, 0.5), handedness="Right"),
                ),
                timestamp_ms=ts,
            )
        )
        ts += 33
    for _ in range(3):
        frames.append(
            make_result_multi(
                (
                    make_hand(index=(0.49, 0.5), handedness="Left"),
                    make_hand(index=(0.51, 0.5), handedness="Right"),
                ),
                timestamp_ms=ts,
            )
        )
        ts += 33
    events = _run(frames)
    claps = [e for e in events if e.kind is GestureKind.CLAP]
    assert len(claps) == 1
    assert claps[0].hands == 2
    assert claps[0].magnitude >= 40.0


def test_explode_requires_fast_separation() -> None:
    frames = []
    ts = 0
    for _ in range(4):
        frames.append(
            make_result_multi(
                (
                    make_hand(index=(0.49, 0.5), handedness="Left"),
                    make_hand(index=(0.51, 0.5), handedness="Right"),
                ),
                timestamp_ms=ts,
            )
        )
        ts += 33
    for step in range(5):
        offset = 0.01 + step * 0.03
        frames.append(
            make_result_multi(
                (
                    make_hand(index=(0.5 - offset, 0.5), handedness="Left"),
                    make_hand(index=(0.5 + offset, 0.5), handedness="Right"),
                ),
                timestamp_ms=ts,
            )
        )
        ts += 33
    events = _run(frames)
    explodes = [e for e in events if e.kind is GestureKind.SCRUB_EXPLODE and e.action == "explode"]
    assert len(explodes) == 1
    assert explodes[0].hands == 2
    assert explodes[0].magnitude >= 140.0


def test_scrub_detects_reversals() -> None:
    frames = []
    ts = 0
    for index in range(24):
        offset = -0.04 if index % 2 == 0 else 0.04
        frames.append(_open(ts, (0.5 + offset, 0.5)))
        ts += 33
    events = _run(frames)
    scrubs = [e for e in events if e.kind is GestureKind.SCRUB_EXPLODE and e.action == "scrub"]
    assert len(scrubs) >= 1
    assert scrubs[0].magnitude >= 140.0


def test_idle_hand_emits_nothing() -> None:
    frames = [_open(i * 33, (0.5 + i * 0.002, 0.5)) for i in range(30)]
    assert _run(frames) == []


def test_thresholds_can_disable_tap_and_drag() -> None:
    frames = [_open(i * 33) for i in range(4)]
    frames += [_closed(132 + i * 33) for i in range(4)]
    frames += [_open(264 + i * 33) for i in range(3)]
    assert _run(frames, thresholds=GestureThresholds(tap_min_ms=300)) == []

    frames = [_open(i * 33) for i in range(3)]
    frames += [_closed(99)]
    frames += [
        make_result(
            make_hand(index=(0.55, 0.5), pinch_ratio=0.15),
            timestamp_ms=132,
        )
    ]
    frames += [_open(165, (0.55, 0.5))]
    assert (
        _run(
            frames,
            thresholds=GestureThresholds(drag_start_px=5000.0, tap_min_ms=300),
        )
        == []
    )


def test_reset_clears_active_gesture() -> None:
    engine = GestureEngine()
    engine.process(_open(0))
    engine.process(_closed(33))
    engine.process(make_result(None, timestamp_ms=66))
    engine.reset()
    assert engine.last_sample is None
    assert not engine.is_dragging
    assert not engine.is_holding
    assert not engine.two_hand_active
