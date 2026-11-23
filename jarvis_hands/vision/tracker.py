"""Pembungkus MediaPipe Hand Landmarker.

Import mediapipe dilakukan malas di dalam thread kamera supaya start aplikasi
tetap ringan. Model resmi ``hand_landmarker.task`` dibundel di
``jarvis_hands/assets/models`` (Apache-2.0, lihat README di folder tersebut).
"""

from __future__ import annotations

import contextlib
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy import typing as npt

__all__ = [
    "HandObservation",
    "HandTracker",
    "Landmark",
    "TrackerError",
    "TrackingResult",
    "default_model_path",
]


class TrackerError(RuntimeError):
    """Tracker tidak dapat dibuat atau dijalankan."""


@dataclass(frozen=True)
class Landmark:
    """Satu landmark tangan dalam koordinat normalisasi 0..1."""

    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


@dataclass(frozen=True)
class HandObservation:
    """21 landmark satu tangan + handedness dan skor."""

    landmarks: tuple[Landmark, ...]
    handedness: str = "Unknown"
    score: float = 0.0

    @property
    def index_tip(self) -> Landmark:
        """Ujung telunjuk (landmark 8)."""
        return self.landmarks[8]

    @property
    def thumb_tip(self) -> Landmark:
        """Ujung jempol (landmark 4)."""
        return self.landmarks[4]

    @property
    def palm_center(self) -> Landmark:
        """Perkiraan pusat telapak (rata-rata landmark 0, 5, 9, 13, 17)."""
        points = [self.landmarks[i] for i in (0, 5, 9, 13, 17)]
        return Landmark(
            x=sum(point.x for point in points) / len(points),
            y=sum(point.y for point in points) / len(points),
            z=sum(point.z for point in points) / len(points),
        )

    @property
    def hand_size(self) -> float:
        """Jarak pergelangan (0) ke pangkal jari tengah (9), sebagai skala tangan."""
        wrist = self.landmarks[0]
        middle = self.landmarks[9]
        return math.hypot(middle.x - wrist.x, middle.y - wrist.y)


@dataclass(frozen=True)
class TrackingResult:
    """Hasil satu frame: nol atau lebih tangan."""

    hands: tuple[HandObservation, ...]
    timestamp_ms: int
    width: int
    height: int

    @property
    def primary(self) -> HandObservation | None:
        """Tangan pertama (paling relevan) bila ada."""
        return self.hands[0] if self.hands else None


def default_model_path() -> Path:
    """Lokasi model Hand Landmarker yang dibundel."""
    return Path(__file__).resolve().parents[1] / "assets" / "models" / "hand_landmarker.task"


class HandTracker:
    """Pembungkus MediaPipe Hand Landmarker mode VIDEO."""

    def __init__(
        self,
        *,
        model_path: Path | None = None,
        num_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self._model_path = Path(model_path) if model_path is not None else default_model_path()
        self._num_hands = max(1, min(2, int(num_hands)))
        self._min_detection = min_detection_confidence
        self._min_presence = min_presence_confidence
        self._min_tracking = min_tracking_confidence
        self._landmarker: Any = None
        self._mp: Any = None

    @property
    def model_path(self) -> Path:
        """Path model yang dipakai."""
        return self._model_path

    @property
    def is_loaded(self) -> bool:
        """True bila model sudah dimuat."""
        return self._landmarker is not None

    def _ensure_loaded(self) -> None:
        if self._landmarker is not None:
            return
        if not self._model_path.is_file():
            raise TrackerError(f"model hand_landmarker tidak ditemukan: {self._model_path}")
        os.environ.setdefault("GLOG_minloglevel", "2")
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions
            from mediapipe.tasks.python.vision import (
                HandLandmarker,
                HandLandmarkerOptions,
            )
            from mediapipe.tasks.python.vision.core import vision_task_running_mode
        except Exception as exc:  # pragma: no cover - tergantung instalasi
            raise TrackerError(f"mediapipe tidak tersedia: {exc}") from exc

        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self._model_path)),
            running_mode=vision_task_running_mode.VisionTaskRunningMode.VIDEO,
            num_hands=self._num_hands,
            min_hand_detection_confidence=self._min_detection,
            min_hand_presence_confidence=self._min_presence,
            min_tracking_confidence=self._min_tracking,
        )
        try:
            self._landmarker = HandLandmarker.create_from_options(options)
        except Exception as exc:
            raise TrackerError(f"gagal memuat model hand landmarker: {exc}") from exc
        self._mp = mp

    def detect(self, rgb: npt.NDArray[np.uint8], timestamp_ms: int) -> TrackingResult:
        """Deteksi landmark dari frame RGB uint8 (H, W, 3)."""
        self._ensure_loaded()
        if rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("frame harus array (H, W, 3)")
        height, width = int(rgb.shape[0]), int(rgb.shape[1])
        if height == 0 or width == 0:
            raise ValueError("frame tidak boleh kosong")
        assert self._mp is not None
        image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=np.ascontiguousarray(rgb),
        )
        result = self._landmarker.detect_for_video(image, int(timestamp_ms))
        hands: list[HandObservation] = []
        landmark_lists = list(result.hand_landmarks)
        handedness_lists = list(result.handedness)
        for index, points in enumerate(landmark_lists):
            landmarks = tuple(
                Landmark(
                    x=float(point.x),
                    y=float(point.y),
                    z=float(point.z),
                    visibility=float(point.visibility),
                )
                for point in points
            )
            handedness = "Unknown"
            score = 0.0
            if index < len(handedness_lists) and handedness_lists[index]:
                category = handedness_lists[index][0]
                handedness = str(getattr(category, "category_name", "Unknown"))
                score = float(getattr(category, "score", 0.0))
            hands.append(HandObservation(landmarks=landmarks, handedness=handedness, score=score))
        return TrackingResult(
            hands=tuple(hands),
            timestamp_ms=int(timestamp_ms),
            width=width,
            height=height,
        )

    def close(self) -> None:
        """Tutup landmarker dan bebaskan model."""
        if self._landmarker is not None:
            with contextlib.suppress(Exception):
                self._landmarker.close()
            self._landmarker = None
            self._mp = None
