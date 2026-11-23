"""Tes fixture landmark: setiap gestur harus terdeteksi dari urutan frame."""

from __future__ import annotations

import json

import pytest

from jarvis_hands.gestures.engine import GestureEngine
from jarvis_hands.gestures.types import GestureEvent
from jarvis_hands.tests.support import FIXTURE_DIR, load_fixture, make_hand, make_result

FIXTURES = (
    "tap",
    "tap_short",
    "tap_long",
    "drag",
    "hold",
    "two_hand",
    "clap",
    "scrub_explode",
    "idle",
)


def _events(name: str) -> list[GestureEvent]:
    engine = GestureEngine()
    events: list[GestureEvent] = []
    for result in load_fixture(name):
        events.extend(engine.process(result))
    return events


def _signature(events: list[GestureEvent]) -> list[tuple[str, str, str]]:
    return [(event.kind.value, event.phase.value, event.action) for event in events]


@pytest.mark.parametrize("name", FIXTURES)
def test_fixture_loads_monotonic_frames(name: str) -> None:
    frames = load_fixture(name)
    assert frames
    timestamps = [frame.timestamp_ms for frame in frames]
    assert timestamps == sorted(timestamps)
    assert len(set(timestamps)) == len(timestamps)
    assert all(frame.width == 1920 and frame.height == 1080 for frame in frames)


def test_fixture_tap() -> None:
    events = _events("tap")
    assert _signature(events) == [("tap", "one_shot", "")]


def test_fixture_tap_short_has_no_event() -> None:
    assert _events("tap_short") == []


def test_fixture_tap_long_has_no_event() -> None:
    assert _events("tap_long") == []


def test_fixture_drag() -> None:
    signature = _signature(_events("drag"))
    assert signature[0] == ("drag", "begin", "")
    assert signature[-1] == ("drag", "end", "")
    assert ("tap", "one_shot", "") not in signature


def test_fixture_hold() -> None:
    signature = _signature(_events("hold"))
    assert signature[0] == ("hold", "begin", "")
    assert signature[-1] == ("hold", "end", "")
    assert ("tap", "one_shot", "") not in signature


def test_fixture_two_hand() -> None:
    signature = _signature(_events("two_hand"))
    assert signature[0] == ("two_hand", "begin", "")
    assert signature[-1] == ("two_hand", "end", "")
    assert ("clap", "one_shot", "") not in signature
    assert ("scrub_explode", "one_shot", "explode") not in signature


def test_fixture_clap() -> None:
    signature = _signature(_events("clap"))
    assert ("clap", "one_shot", "") in signature
    assert ("scrub_explode", "one_shot", "explode") not in signature


def test_fixture_scrub_explode() -> None:
    signature = _signature(_events("scrub_explode"))
    assert ("scrub_explode", "one_shot", "scrub") in signature
    assert ("scrub_explode", "one_shot", "explode") in signature


def test_fixture_idle() -> None:
    assert _events("idle") == []


def test_all_fixtures_are_listed_and_valid() -> None:
    files = sorted(path.stem for path in FIXTURE_DIR.glob("*.json"))
    assert files == sorted(FIXTURES)
    for name in FIXTURES:
        payload = json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))
        assert payload["width"] == 1920
        assert payload["height"] == 1080
        assert payload["fps"] == 30
        for frame in payload["frames"]:
            assert len(frame["hands"]) <= 2
            for hand in frame["hands"]:
                assert len(hand["landmarks"]) == 21


def test_engine_handles_direct_hand_observation() -> None:
    engine = GestureEngine()
    events = engine.process(make_result(make_hand(), timestamp_ms=0))
    assert events == []
    assert engine.last_sample is not None
