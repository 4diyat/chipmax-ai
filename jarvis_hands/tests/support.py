"""Pembantu tes: tangan dan hasil pelacakan sintetis."""

from __future__ import annotations

from jarvis_hands.vision.tracker import HandObservation, Landmark, TrackingResult

__all__ = ["make_hand", "make_result"]


def make_hand(
    *,
    index: tuple[float, float] = (0.5, 0.5),
    pinch_ratio: float = 0.6,
    hand_size: float = 0.15,
    wrist: tuple[float, float] = (0.5, 0.9),
    handedness: str = "Right",
    score: float = 0.92,
    width: int = 640,
    height: int = 360,
) -> HandObservation:
    """Bangun 21 landmark sintetis dengan rasio cubit dan ukuran telapak terkontrol."""
    aspect = width / height if height else 1.0
    points = [Landmark(wrist[0], wrist[1]) for _ in range(21)]
    points[0] = Landmark(wrist[0], wrist[1])
    points[9] = Landmark(wrist[0], wrist[1] - hand_size)
    points[8] = Landmark(index[0], index[1])
    distance = pinch_ratio * hand_size
    dx = distance / aspect
    points[4] = Landmark(index[0] + dx, index[1])
    for i in (5, 13, 17):
        points[i] = Landmark(wrist[0], wrist[1] - hand_size * 0.8)
    return HandObservation(
        landmarks=tuple(points),
        handedness=handedness,
        score=score,
    )


def make_result(
    hand: HandObservation | None = None,
    *,
    width: int = 640,
    height: int = 360,
    timestamp_ms: int = 0,
) -> TrackingResult:
    """Bangun hasil pelacakan berisi nol atau satu tangan."""
    return TrackingResult(
        hands=() if hand is None else (hand,),
        timestamp_ms=timestamp_ms,
        width=width,
        height=height,
    )
