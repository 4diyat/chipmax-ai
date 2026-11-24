"""Pembantu tes: tangan dan hasil pelacakan sintetis."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from jarvis_hands.vision.tracker import HandObservation, Landmark, TrackingResult

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "landmarks"

__all__ = ["FIXTURE_DIR", "load_fixture", "make_hand", "make_result", "make_result_multi"]


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
    fist: bool = False,
) -> HandObservation:
    """Bangun 21 landmark sintetis dengan rasio cubit dan ukuran telapak terkontrol.

    Saat ``fist=True``, semua ujung jari diposisikan di dekat pergelangan
    (posisi genggam) untuk pengujian deteksi FIST.
    """
    aspect = width / height if height else 1.0
    points = [Landmark(wrist[0], wrist[1]) for _ in range(21)]
    points[0] = Landmark(wrist[0], wrist[1])
    points[9] = Landmark(wrist[0], wrist[1] - hand_size)

    if fist:
        # Semua ujung jari dekat pergelangan (posisi genggam).
        for tip_idx in (4, 8, 12, 16, 20):
            points[tip_idx] = Landmark(wrist[0], wrist[1])
    else:
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


def make_result_multi(
    hands: Sequence[HandObservation],
    *,
    width: int = 640,
    height: int = 360,
    timestamp_ms: int = 0,
) -> TrackingResult:
    """Bangun hasil pelacakan berisi beberapa tangan."""
    return TrackingResult(
        hands=tuple(hands),
        timestamp_ms=timestamp_ms,
        width=width,
        height=height,
    )


def load_fixture(name: str) -> list[TrackingResult]:
    """Muat fixture landmark JSON menjadi urutan TrackingResult."""
    path = FIXTURE_DIR / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"fixture landmark tidak ditemukan: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    width = int(data["width"])
    height = int(data["height"])
    results: list[TrackingResult] = []
    for frame in data["frames"]:
        hands: list[HandObservation] = []
        for raw in frame["hands"]:
            points = tuple(
                Landmark(
                    x=float(point[0]),
                    y=float(point[1]),
                    z=float(point[2]) if len(point) > 2 else 0.0,
                )
                for point in raw["landmarks"]
            )
            hands.append(
                HandObservation(
                    landmarks=points,
                    handedness=str(raw.get("handedness", "Right")),
                    score=float(raw.get("score", 0.9)),
                )
            )
        results.append(
            TrackingResult(
                hands=tuple(hands),
                timestamp_ms=int(frame["t"]),
                width=width,
                height=height,
            )
        )
    return results
