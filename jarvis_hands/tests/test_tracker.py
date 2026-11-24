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


def test_delegate_defaults_to_auto() -> None:
    tracker = HandTracker()
    assert tracker.delegate == "auto"
    assert tracker.delegate_used is None


@pytest.mark.parametrize("delegate", ("auto", "gpu", "cpu"))
def test_delegate_property(delegate: str) -> None:
    tracker = HandTracker(delegate=delegate)
    assert tracker.delegate == delegate


def test_invalid_delegate_defaults_to_auto() -> None:
    tracker = HandTracker(delegate="cuda")
    assert tracker.delegate == "auto"


class _Point:
    """Tiruan ``NormalizedLandmark`` MediaPipe (atribut bisa ``None``)."""

    def __init__(self, x: float, y: float, z: float | None, visibility: float | None) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility


class _Category:
    def __init__(self, name: str, score: float | None) -> None:
        self.category_name = name
        self.score = score


class _Result:
    def __init__(self, landmarks: list[list[_Point]], handedness: list[list[_Category]]) -> None:
        self.hand_landmarks = landmarks
        self.handedness = handedness


class _FakeLandmarker:
    """Landmarker palsu: hasil ``detect_for_video`` sudah disiapkan tes."""

    def __init__(self, result: _Result) -> None:
        self.result = result

    def detect_for_video(self, image: object, timestamp_ms: int) -> _Result:
        del image, timestamp_ms
        return self.result

    def close(self) -> None:
        return None


class _FakeMp:
    """Tiruan modul mediapipe untuk membungkus frame menjadi "image"."""

    class ImageFormat:
        SRGB = 1

    class Image:
        def __init__(self, *, image_format: int, data: object) -> None:
            self.image_format = image_format
            self.data = data


def _tracker_with(result: _Result) -> HandTracker:
    """Tracker dengan model palsu; tidak memuat mediapipe sama sekali."""
    tracker = HandTracker()
    tracker._landmarker = _FakeLandmarker(result)
    tracker._mp = _FakeMp()
    return tracker


def test_landmark_with_none_visibility_does_not_crash() -> None:
    """Bug lapangan: MediaPipe mengisi visibility/z dengan None untuk hand landmark.

    Sebelumnya ``float(point.visibility)`` melempar TypeError, loop kamera mati,
    dan panduan menampilkan "kamera berhenti: float() argument must be a string
    or a real number, not 'NoneType'".
    """
    points = [_Point(0.4, 0.5, None, None) for _ in range(21)]
    tracker = _tracker_with(_Result([points], [[_Category("Right", None)]]))
    frame = np.zeros((360, 640, 3), dtype=np.uint8)

    result = tracker.detect(frame, timestamp_ms=0)

    assert len(result.hands) == 1
    hand = result.hands[0]
    assert len(hand.landmarks) == 21
    assert hand.landmarks[0].x == pytest.approx(0.4)
    assert hand.landmarks[0].z == 0.0
    assert hand.landmarks[0].visibility == 1.0  # default aman, bukan None
    assert hand.handedness == "Right"
    assert hand.score == 0.0
    tracker.close()


def test_landmark_with_nan_and_infinite_values_is_normalised() -> None:
    points = [_Point(0.1, 0.2, float("nan"), float("inf")) for _ in range(21)]
    tracker = _tracker_with(_Result([points], [[_Category("Left", 0.8)]]))
    result = tracker.detect(np.zeros((8, 8, 3), dtype=np.uint8), timestamp_ms=1)
    hand = result.hands[0]
    assert hand.landmarks[0].z == 0.0
    assert hand.landmarks[0].visibility == 1.0
    assert hand.score == pytest.approx(0.8)
    tracker.close()


def test_missing_handedness_falls_back_to_unknown() -> None:
    points = [_Point(0.5, 0.5, 0.0, 1.0) for _ in range(21)]
    tracker = _tracker_with(_Result([points], []))
    result = tracker.detect(np.zeros((8, 8, 3), dtype=np.uint8), timestamp_ms=2)
    assert result.hands[0].handedness == "Unknown"
    assert result.hands[0].score == 0.0
    tracker.close()
