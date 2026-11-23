"""Tes HandTracker: model resmi, frame kosong, dan jalur kesalahan."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from jarvis_hands.vision.tracker import (
    HandTracker,
    TrackerError,
    TrackingResult,
    default_model_path,
)

MODEL_SHA256 = "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1"


def test_bundled_model_matches_official_hash() -> None:
    path = default_model_path()
    assert path.is_file()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == MODEL_SHA256
    assert path.stat().st_size == 7_819_105


def test_detect_blank_frame_returns_no_hands() -> None:
    tracker = HandTracker()
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    result = tracker.detect(frame, timestamp_ms=0)
    assert isinstance(result, TrackingResult)
    assert result.hands == ()
    assert (result.width, result.height) == (640, 360)
    assert result.timestamp_ms == 0
    assert result.primary is None
    tracker.close()
    assert not tracker.is_loaded


def test_missing_model_raises_tracker_error(tmp_path: Path) -> None:
    tracker = HandTracker(model_path=tmp_path / "absent.task")
    with pytest.raises(TrackerError):
        tracker.detect(np.zeros((32, 32, 3), dtype=np.uint8), 0)


def test_invalid_frame_raises_value_error() -> None:
    tracker = HandTracker()
    with pytest.raises(ValueError):
        tracker.detect(np.zeros((4, 4), dtype=np.uint8), 0)
    with pytest.raises(ValueError):
        tracker.detect(np.zeros((0, 0, 3), dtype=np.uint8), 0)
    tracker.close()


def test_model_path_property() -> None:
    tracker = HandTracker(model_path=Path("x.task"))
    assert tracker.model_path == Path("x.task")
    assert not tracker.is_loaded
