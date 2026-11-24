"""Mesin gestur murni Python.

Alur sesuai spesifikasi: landmark -> One-Euro -> kursor 2D -> cubit dengan
histeresis -> mesin status. Tidak ada Qt di sini supaya bisa diuji cepat dan
dipakai ulang oleh bridge agen/overlay.

Gestur:
- ``TAP``: cubit singkat (``tap_min_ms``..``tap_max_ms``) tanpa pergeseran.
- ``DRAG``: cubit lalu kursor bergerak melewati ``drag_start_px``.
- ``HOLD``: cubit ditahan >= ``hold_ms`` tanpa pergeseran.
- ``TWO_HAND``: dua tangan masuk radius ``two_hand_min_px``.
- ``CLAP``: dua tangan saling mendekat cepat di jendela ``clap_window_ms``.
- ``SCRUB_EXPLODE``: goyang horizontal berulang (``scrub``) atau dua tangan
  menjauh cepat (``explode``).
"""

from __future__ import annotations

import math
from collections import deque
from itertools import pairwise

from jarvis_hands.core.config import CursorConfig, GestureThresholds
from jarvis_hands.gestures.types import GestureEvent, GestureKind, GesturePhase
from jarvis_hands.vision.cursor import CursorSample, CursorTracker
from jarvis_hands.vision.tracker import HandObservation, Landmark, TrackingResult

__all__ = ["GestureEngine"]


class GestureEngine:
    """Ubah :class:`TrackingResult` menjadi daftar :class:`GestureEvent`."""

    def __init__(
        self,
        *,
        thresholds: GestureThresholds | None = None,
        cursor_config: CursorConfig | None = None,
        screen_width: int = 1920,
        screen_height: int = 1080,
        origin_x: int = 0,
        origin_y: int = 0,
    ) -> None:
        self._thresholds = thresholds or GestureThresholds()
        self._cursor_config = cursor_config or CursorConfig()
        self._screen = (max(1, int(screen_width)), max(1, int(screen_height)))
        self._origin = (int(origin_x), int(origin_y))
        self._cursor = CursorTracker(
            cursor_config=self._cursor_config,
            thresholds=self._thresholds,
            screen_width=self._screen[0],
            screen_height=self._screen[1],
            origin_x=self._origin[0],
            origin_y=self._origin[1],
        )

        self._pinch_start: tuple[int, int, int] | None = None
        self._pinch_last: tuple[int, int] | None = None
        self._pinch_max = 0.0
        self._dragging = False
        self._holding = False

        self._two_hand_active = False
        self._two_history: deque[tuple[int, float]] = deque(maxlen=64)
        self._two_last_mid: tuple[int, int] | None = None

        self._scrub_history: deque[tuple[int, int]] = deque(maxlen=64)
        self._last_scrub_ts = -(10**9)
        self._last_explode_ts = -(10**9)
        self._last_clap_ts = -(10**9)

        # SWIPE: gerakan tangan terbuka (tidak mencubit) dalam arah satu.
        self._swipe_start: tuple[int, int, int] | None = None
        self._swipe_max_dist = 0.0
        self._swipe_end: tuple[int, int] = (0, 0)

        # FIST: semua jari lipat ke telapak, tahan sesuai ambang.
        self._fist_start: int | None = None

    # ------------------------------------------------------------------ state

    @property
    def last_sample(self) -> CursorSample | None:
        """Sampel kursor terakhir."""
        return self._cursor.last

    @property
    def is_dragging(self) -> bool:
        """True bila drag sedang berjalan."""
        return self._dragging

    @property
    def is_holding(self) -> bool:
        """True bila hold sedang berjalan."""
        return self._holding

    @property
    def two_hand_active(self) -> bool:
        """True bila dua tangan sedang berdekatan."""
        return self._two_hand_active

    @property
    def is_swiping(self) -> bool:
        """True bila gerakan swipe sedang ditrack."""
        return self._swipe_start is not None

    @property
    def is_fist(self) -> bool:
        """True bila gestur genggam (fist) sedang aktif."""
        return self._fist_start is not None

    @property
    def screen_size(self) -> tuple[int, int]:
        """Ukuran area gestur."""
        return self._screen

    def set_screen(
        self,
        width: int,
        height: int,
        *,
        origin_x: int = 0,
        origin_y: int = 0,
    ) -> None:
        """Ganti area layar (pindah monitor)."""
        self._screen = (max(1, int(width)), max(1, int(height)))
        self._origin = (int(origin_x), int(origin_y))
        self._cursor.set_screen(width, height, origin_x=origin_x, origin_y=origin_y)

    def reset(self) -> None:
        """Batalkan seluruh gestur yang sedang berjalan."""
        self._cursor.reset()
        self._pinch_start = None
        self._pinch_last = None
        self._pinch_max = 0.0
        self._dragging = False
        self._holding = False
        self._two_hand_active = False
        self._two_history.clear()
        self._two_last_mid = None
        self._scrub_history.clear()
        self._last_scrub_ts = -(10**9)
        self._last_explode_ts = -(10**9)
        self._last_clap_ts = -(10**9)
        self._swipe_start = None
        self._swipe_max_dist = 0.0
        self._swipe_end = (0, 0)
        self._fist_start = None

    def set_thresholds(self, thresholds: GestureThresholds) -> None:
        """Ganti ambang gestur saat aplikasi berjalan (tanpa membatalkan gestur)."""
        self._thresholds = thresholds
        self._cursor.set_thresholds(thresholds)

    def set_cursor_config(self, cursor_config: CursorConfig) -> None:
        """Ganti parameter filter kursor saat aplikasi berjalan."""
        self._cursor_config = cursor_config
        self._cursor.set_cursor_config(cursor_config)

    # ------------------------------------------------------------------ input

    def process(self, result: TrackingResult) -> list[GestureEvent]:
        """Proses satu frame landmark; kembalikan event yang terjadi."""
        sample = self._cursor.update(result)
        events: list[GestureEvent] = []
        events.extend(self._update_pinch(sample))
        events.extend(self._update_two_hand(result))
        events.extend(self._update_scrub(sample, result))
        events.extend(self._update_swipe(sample))
        events.extend(self._update_fist(result))
        return events

    # ------------------------------------------------------------ pinch state

    def _update_pinch(self, sample: CursorSample) -> list[GestureEvent]:
        if sample.visible and sample.pinching:
            if self._pinch_start is None:
                self._pinch_start = (sample.x, sample.y, sample.timestamp_ms)
                self._pinch_last = (sample.x, sample.y)
                self._pinch_max = 0.0
                self._dragging = False
                self._holding = False
                return []
            return self._update_pinch_active(sample)

        if self._pinch_start is None:
            return []
        return self._end_pinch(sample)

    def _update_pinch_active(self, sample: CursorSample) -> list[GestureEvent]:
        assert self._pinch_start is not None
        start_x, start_y, start_ts = self._pinch_start
        assert self._pinch_last is not None
        last_x, last_y = self._pinch_last
        ts = sample.timestamp_ms
        distance = math.hypot(sample.x - start_x, sample.y - start_y)
        self._pinch_max = max(self._pinch_max, distance)
        events: list[GestureEvent] = []

        if not self._dragging and distance >= self._thresholds.drag_start_px:
            if self._holding:
                self._holding = False
                events.append(
                    GestureEvent(
                        kind=GestureKind.HOLD,
                        phase=GesturePhase.END,
                        timestamp_ms=ts,
                        x=start_x,
                        y=start_y,
                        magnitude=float(ts - start_ts),
                        cancelled=True,
                    )
                )
            self._dragging = True
            events.append(
                GestureEvent(
                    kind=GestureKind.DRAG,
                    phase=GesturePhase.BEGIN,
                    timestamp_ms=ts,
                    x=sample.x,
                    y=sample.y,
                    magnitude=distance,
                )
            )
        if self._dragging:
            events.append(
                GestureEvent(
                    kind=GestureKind.DRAG,
                    phase=GesturePhase.UPDATE,
                    timestamp_ms=ts,
                    x=sample.x,
                    y=sample.y,
                    dx=float(sample.x - last_x),
                    dy=float(sample.y - last_y),
                    magnitude=distance,
                )
            )
        elif not self._holding and ts - start_ts >= self._thresholds.hold_ms:
            self._holding = True
            events.append(
                GestureEvent(
                    kind=GestureKind.HOLD,
                    phase=GesturePhase.BEGIN,
                    timestamp_ms=ts,
                    x=start_x,
                    y=start_y,
                    magnitude=float(ts - start_ts),
                )
            )
        elif self._holding:
            events.append(
                GestureEvent(
                    kind=GestureKind.HOLD,
                    phase=GesturePhase.UPDATE,
                    timestamp_ms=ts,
                    x=start_x,
                    y=start_y,
                    magnitude=float(ts - start_ts),
                )
            )

        self._pinch_last = (sample.x, sample.y)
        return events

    def _end_pinch(self, sample: CursorSample) -> list[GestureEvent]:
        assert self._pinch_start is not None
        start_x, start_y, start_ts = self._pinch_start
        assert self._pinch_last is not None
        last_x, last_y = self._pinch_last
        ts = sample.timestamp_ms
        duration = max(0, ts - start_ts)
        cancelled = not sample.visible
        events: list[GestureEvent] = []
        if self._dragging:
            events.append(
                GestureEvent(
                    kind=GestureKind.DRAG,
                    phase=GesturePhase.END,
                    timestamp_ms=ts,
                    x=last_x,
                    y=last_y,
                    magnitude=self._pinch_max,
                    cancelled=cancelled,
                )
            )
        elif self._holding:
            events.append(
                GestureEvent(
                    kind=GestureKind.HOLD,
                    phase=GesturePhase.END,
                    timestamp_ms=ts,
                    x=start_x,
                    y=start_y,
                    magnitude=float(duration),
                    cancelled=cancelled,
                )
            )
        elif (
            not cancelled
            and self._thresholds.tap_min_ms <= duration <= self._thresholds.tap_max_ms
            and self._pinch_max < self._thresholds.drag_start_px
        ):
            events.append(
                GestureEvent(
                    kind=GestureKind.TAP,
                    phase=GesturePhase.ONE_SHOT,
                    timestamp_ms=ts,
                    x=start_x,
                    y=start_y,
                    magnitude=float(duration),
                )
            )
        self._clear_pinch()
        return events

    def _clear_pinch(self) -> None:
        self._pinch_start = None
        self._pinch_last = None
        self._pinch_max = 0.0
        self._dragging = False
        self._holding = False

    # ----------------------------------------------------------- two-hand state

    def _update_two_hand(self, result: TrackingResult) -> list[GestureEvent]:
        ts = result.timestamp_ms
        hands = result.hands
        if len(hands) < 2:
            self._two_history.clear()
            if not self._two_hand_active:
                return []
            self._two_hand_active = False
            mid = self._two_last_mid or (0, 0)
            return [
                GestureEvent(
                    kind=GestureKind.TWO_HAND,
                    phase=GesturePhase.END,
                    timestamp_ms=ts,
                    x=mid[0],
                    y=mid[1],
                    cancelled=True,
                    hands=2,
                )
            ]

        first = self._map_to_screen(hands[0], result)
        second = self._map_to_screen(hands[1], result)
        distance = math.hypot(first[0] - second[0], first[1] - second[1])
        mid = ((first[0] + second[0]) // 2, (first[1] + second[1]) // 2)
        self._two_last_mid = mid
        prior = [(t, d) for t, d in self._two_history if ts - t <= self._thresholds.clap_window_ms]
        explode_prior = [
            (t, d) for t, d in self._two_history if ts - t <= self._thresholds.scrub_window_ms
        ]
        self._two_history.append((ts, distance))
        events: list[GestureEvent] = []

        if not self._two_hand_active and distance <= self._thresholds.two_hand_min_px:
            self._two_hand_active = True
            events.append(
                GestureEvent(
                    kind=GestureKind.TWO_HAND,
                    phase=GesturePhase.BEGIN,
                    timestamp_ms=ts,
                    x=mid[0],
                    y=mid[1],
                    magnitude=distance,
                    hands=2,
                )
            )
            if prior:
                peak_t, peak_distance = max(prior, key=lambda item: item[1])
                approach = peak_distance - distance
                elapsed_s = max(1e-6, (ts - peak_t) / 1000.0)
                speed = approach / elapsed_s
                if (
                    approach >= self._thresholds.clap_approach_px
                    and speed >= self._thresholds.clap_min_speed_px_s
                ):
                    self._last_clap_ts = ts
                    events.append(
                        GestureEvent(
                            kind=GestureKind.CLAP,
                            phase=GesturePhase.ONE_SHOT,
                            timestamp_ms=ts,
                            x=mid[0],
                            y=mid[1],
                            magnitude=approach,
                            hands=2,
                        )
                    )

        if self._two_hand_active and distance > self._thresholds.two_hand_min_px * 1.5:
            self._two_hand_active = False
            events.append(
                GestureEvent(
                    kind=GestureKind.TWO_HAND,
                    phase=GesturePhase.END,
                    timestamp_ms=ts,
                    x=mid[0],
                    y=mid[1],
                    magnitude=distance,
                    hands=2,
                )
            )

        if explode_prior:
            min_t, min_distance = min(explode_prior, key=lambda item: item[1])
            rise = distance - min_distance
            elapsed_s = max(1e-6, (ts - min_t) / 1000.0)
            speed = rise / elapsed_s
            if (
                rise >= self._thresholds.scrub_explode_px
                and speed >= self._thresholds.explode_min_speed_px_s
                and ts - self._last_explode_ts >= self._thresholds.gesture_cooldown_ms
                and ts - self._last_clap_ts >= self._thresholds.gesture_cooldown_ms
            ):
                self._last_explode_ts = ts
                events.append(
                    GestureEvent(
                        kind=GestureKind.SCRUB_EXPLODE,
                        phase=GesturePhase.ONE_SHOT,
                        timestamp_ms=ts,
                        x=mid[0],
                        y=mid[1],
                        magnitude=rise,
                        action="explode",
                        hands=2,
                    )
                )
        return events

    # ------------------------------------------------------------ scrub state

    def _update_scrub(
        self,
        sample: CursorSample,
        result: TrackingResult,
    ) -> list[GestureEvent]:
        ts = sample.timestamp_ms
        if (
            not sample.visible
            or sample.pinching
            or self._dragging
            or self._holding
            or len(result.hands) >= 2
        ):
            self._scrub_history.clear()
            return []
        self._scrub_history.append((ts, sample.x))
        window = self._thresholds.scrub_window_ms
        points = [(t, x) for t, x in self._scrub_history if ts - t <= window]
        self._scrub_history.clear()
        self._scrub_history.extend(points)
        if len(points) < 4:
            return []

        reversals = 0
        last_sign = 0
        for (_, x0), (_, x1) in pairwise(points):
            delta = x1 - x0
            if abs(delta) < 3:
                continue
            sign = 1 if delta > 0 else -1
            if last_sign and sign != last_sign:
                reversals += 1
            last_sign = sign
        xs = [x for _, x in points]
        span = max(xs) - min(xs)
        if (
            reversals >= self._thresholds.scrub_reversals
            and span >= self._thresholds.scrub_explode_px
            and ts - self._last_scrub_ts >= self._thresholds.gesture_cooldown_ms
        ):
            self._last_scrub_ts = ts
            return [
                GestureEvent(
                    kind=GestureKind.SCRUB_EXPLODE,
                    phase=GesturePhase.ONE_SHOT,
                    timestamp_ms=ts,
                    x=sample.x,
                    y=sample.y,
                    dx=float(last_sign),
                    magnitude=float(span),
                    action="scrub",
                )
            ]
        return []

    # ------------------------------------------------------------ swipe state

    def _update_swipe(self, sample: CursorSample) -> list[GestureEvent]:
        """Deteksi gerakan layang (swipe) tangan terbuka dalam satu arah.

        Di-track saat tangan terlihat dan tidak mencubit. Jika perpindahan
        total dari titik awal mencapai ``swipe_min_px`` dalam
        ``swipe_max_ms`` sebelum tangan mencubit atau hilang, event SWIPE
        one_shot di-emits dengan arah dominan.
        """
        ts = sample.timestamp_ms
        events: list[GestureEvent] = []

        if sample.visible and not sample.pinching:
            if self._swipe_start is None:
                self._swipe_start = (sample.x, sample.y, ts)
                self._swipe_max_dist = 0.0
                self._swipe_end = (sample.x, sample.y)
            else:
                start_x, start_y, _ = self._swipe_start
                dist = math.hypot(sample.x - start_x, sample.y - start_y)
                self._swipe_max_dist = max(self._swipe_max_dist, dist)
                self._swipe_end = (sample.x, sample.y)
            return events

        # Tangan mulai mencubit atau hilang: akhiri tracking swipe.
        if self._swipe_start is None:
            return events
        start_x, start_y, start_ts = self._swipe_start
        end_x, end_y = self._swipe_end
        max_dist = self._swipe_max_dist
        self._swipe_start = None
        self._swipe_max_dist = 0.0
        self._swipe_end = (0, 0)

        elapsed = max(0, ts - start_ts)
        if elapsed <= self._thresholds.swipe_max_ms and max_dist >= self._thresholds.swipe_min_px:
            dx = end_x - start_x
            dy = end_y - start_y
            events.append(
                GestureEvent(
                    kind=GestureKind.SWIPE,
                    phase=GesturePhase.ONE_SHOT,
                    timestamp_ms=ts,
                    x=start_x,
                    y=start_y,
                    dx=dx,
                    dy=dy,
                    magnitude=max_dist,
                    direction=self._swipe_direction(dx, dy),
                )
            )
        return events

    @staticmethod
    def _swipe_direction(dx: float, dy: float) -> str:
        """Tentukan arah dominan dari displacement (dx, dy)."""
        if abs(dx) >= abs(dy):
            return "kanan" if dx > 0 else "kiri"
        return "bawah" if dy > 0 else "atas"

    # ------------------------------------------------------------ fist state

    def _update_fist(self, result: TrackingResult) -> list[GestureEvent]:
        """Deteksi genggam (fist): semua ujung jari dekat telapak/pulsa.

        Jika tangan dalam posisi genggam terus-menerus >= ``fist_hold_ms``,
        event FIST one_shot di-emits.
        """
        ts = result.timestamp_ms
        events: list[GestureEvent] = []

        hands = result.hands
        if not hands:
            self._fist_start = None
            return events

        hand = hands[0]
        if self._is_fist(hand, result.width, result.height):
            if self._fist_start is None:
                self._fist_start = ts
            elif ts - self._fist_start >= self._thresholds.fist_hold_ms:
                events.append(
                    GestureEvent(
                        kind=GestureKind.FIST,
                        phase=GesturePhase.ONE_SHOT,
                        timestamp_ms=ts,
                        x=int(hand.index_tip.x),
                        y=int(hand.index_tip.y),
                        magnitude=float(ts - self._fist_start),
                        hands=1,
                    )
                )
                self._fist_start = None
        else:
            self._fist_start = None

        return events

    def _is_fist(self, hand: HandObservation, width: int, height: int) -> bool:
        """True bila semua ujung jari dekat telapak (posisi genggam)."""
        landmarks = hand.landmarks
        if len(landmarks) < 21:
            return False

        wrist = landmarks[0]
        # Ukuran telapak dari pergelangan ke jempol tengah (landmark 9).
        aspect = (width / height) if height else 1.0
        palm_size = math.hypot((landmarks[9].x - wrist.x) * aspect, landmarks[9].y - wrist.y)
        if palm_size <= 1e-6:
            return False

        # Ujung jari: telunjuk(8), tengah(12), manis(16), kelingking(20).
        # Semua harus dekat pergelangan (dalam fraksi ukuran telapak).
        tip_indices = (8, 12, 16, 20)
        for tip_idx in tip_indices:
            tip = landmarks[tip_idx]
            dist = math.hypot((tip.x - wrist.x) * aspect, tip.y - wrist.y)
            if dist > palm_size * 0.55:
                return False
        return True

    # --------------------------------------------------------------- helpers

    def _map_to_screen(
        self,
        hand: HandObservation,
        result: TrackingResult,
    ) -> tuple[int, int]:
        width, height = self._screen
        origin_x, origin_y = self._origin
        gain = max(0.1, float(self._cursor_config.gain))
        tip: Landmark = hand.index_tip
        raw_x = origin_x + width * 0.5 + (tip.x - 0.5) * width * gain
        raw_y = origin_y + height * 0.5 + (tip.y - 0.5) * height * gain
        x = round(min(max(raw_x, origin_x), origin_x + width - 1))
        y = round(min(max(raw_y, origin_y), origin_y + height - 1))
        return x, y
