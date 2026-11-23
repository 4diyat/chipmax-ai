"""Kursor 2D dari landmark tangan (murni Python, tanpa Qt).

Alur: landmark -> One-Euro -> koordinat layar -> cubit dengan histeresis.
Modul ini tidak tahu gestur (tap/drag/hold); :mod:`jarvis_hands.gestures.engine`
nantinya membangun gestur di atas :class:`CursorSample`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from jarvis_hands.core.config import CursorConfig, GestureThresholds
from jarvis_hands.vision.filters import OneEuroFilter2D
from jarvis_hands.vision.tracker import HandObservation, TrackingResult

__all__ = ["CursorSample", "CursorTracker"]


@dataclass(frozen=True)
class CursorSample:
    """Satu sampel kursor layar."""

    x: int
    y: int
    #: 0..1, seberapa rapat jempol-telunjuk (0 = terbuka).
    pinch: float
    #: Status cubit setelah histeresis.
    pinching: bool
    #: False bila tidak ada tangan yang cukup dekat.
    visible: bool
    timestamp_ms: int
    #: Rasio jarak jempol-telunjuk terhadap lebar telapak (diagnostik).
    ratio: float = 0.0
    hand_size: float = 0.0

    @property
    def point(self) -> tuple[int, int]:
        """Posisi layar sebagai tuple."""
        return self.x, self.y


class CursorTracker:
    """Ubah :class:`TrackingResult` menjadi :class:`CursorSample` layar."""

    def __init__(
        self,
        *,
        cursor_config: CursorConfig | None = None,
        thresholds: GestureThresholds | None = None,
        screen_width: int = 1920,
        screen_height: int = 1080,
        origin_x: int = 0,
        origin_y: int = 0,
        min_hand_size: float = 0.035,
    ) -> None:
        self._config = cursor_config or CursorConfig()
        self._thresholds = thresholds or GestureThresholds()
        self._screen = (max(1, int(screen_width)), max(1, int(screen_height)))
        self._origin = (int(origin_x), int(origin_y))
        self._min_hand_size = float(min_hand_size)
        self._filter = OneEuroFilter2D()
        self._pinching = False
        self._last: CursorSample | None = None

    @property
    def pinching(self) -> bool:
        """Status cubit saat ini."""
        return self._pinching

    @property
    def screen_size(self) -> tuple[int, int]:
        """Ukuran area kursor (lebar, tinggi)."""
        return self._screen

    @property
    def last(self) -> CursorSample | None:
        """Sampel terakhir; None sebelum ada tangan."""
        return self._last

    def set_screen(
        self,
        width: int,
        height: int,
        *,
        origin_x: int = 0,
        origin_y: int = 0,
    ) -> None:
        """Ganti area layar (misal pindah monitor)."""
        self._screen = (max(1, int(width)), max(1, int(height)))
        self._origin = (int(origin_x), int(origin_y))

    def reset(self) -> None:
        """Hapus status filter dan cubit (saat kamera mati/jeda)."""
        self._filter.reset()
        self._pinching = False
        self._last = None

    def update(self, result: TrackingResult) -> CursorSample:
        """Hitung sampel kursor dari satu hasil pelacakan."""
        hand = result.primary
        if hand is None or len(hand.landmarks) < 21:
            return self._no_hand(result.timestamp_ms)

        size = self._hand_size(hand, result.width, result.height)
        if size < self._min_hand_size:
            return self._no_hand(result.timestamp_ms)

        tip = hand.index_tip
        width, height = self._screen
        origin_x, origin_y = self._origin
        gain = max(0.1, float(self._config.gain))
        raw_x = origin_x + width * 0.5 + (tip.x - 0.5) * width * gain
        raw_y = origin_y + height * 0.5 + (tip.y - 0.5) * height * gain
        smooth_x, smooth_y = self._filter.filter(
            raw_x,
            raw_y,
            t=result.timestamp_ms / 1000.0,
        )
        x = round(min(max(smooth_x, origin_x), origin_x + width - 1))
        y = round(min(max(smooth_y, origin_y), origin_y + height - 1))

        ratio = self._pinch_ratio(hand, result.width, result.height)
        pinch = self._pinch_amount(ratio)
        if self._pinching:
            if ratio >= self._thresholds.pinch_open:
                self._pinching = False
        elif ratio <= self._thresholds.pinch_close:
            self._pinching = True

        sample = CursorSample(
            x=x,
            y=y,
            pinch=pinch,
            pinching=self._pinching,
            visible=True,
            timestamp_ms=result.timestamp_ms,
            ratio=ratio,
            hand_size=size,
        )
        self._last = sample
        return sample

    def _no_hand(self, timestamp_ms: int) -> CursorSample:
        previous = self._last
        x = previous.x if previous is not None else self._origin[0] + self._screen[0] // 2
        y = previous.y if previous is not None else self._origin[1] + self._screen[1] // 2
        self._pinching = False
        sample = CursorSample(
            x=x,
            y=y,
            pinch=0.0,
            pinching=False,
            visible=False,
            timestamp_ms=timestamp_ms,
            ratio=previous.ratio if previous is not None else 0.0,
            hand_size=0.0,
        )
        self._last = sample
        return sample

    def _pinch_amount(self, ratio: float) -> float:
        close = self._thresholds.pinch_close
        open_ = self._thresholds.pinch_open
        if open_ <= close:
            return 1.0 if ratio <= close else 0.0
        return min(1.0, max(0.0, (open_ - ratio) / (open_ - close)))

    @staticmethod
    def _hand_size(hand: HandObservation, width: int, height: int) -> float:
        aspect = (width / height) if height else 1.0
        wrist = hand.landmarks[0]
        middle = hand.landmarks[9]
        return math.hypot((middle.x - wrist.x) * aspect, middle.y - wrist.y)

    @staticmethod
    def _pinch_ratio(hand: HandObservation, width: int, height: int) -> float:
        aspect = (width / height) if height else 1.0
        thumb = hand.thumb_tip
        index = hand.index_tip
        distance = math.hypot((thumb.x - index.x) * aspect, thumb.y - index.y)
        size = CursorTracker._hand_size(hand, width, height)
        if size <= 1e-6:
            return 1.0
        return distance / size
