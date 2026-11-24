"""Benchmark mikro untuk jalur panas JARVIS (Fase 8).

Modul ini bebas Qt dan jaringan: mengukur filter One-Euro, kursor 2D, dan mesin
gestur dengan landmark sintetis. Hasil dipakai untuk memastikan perubahan tidak
memperlambat jalur interaksi, dan dapat dijalankan lewat ``--profile``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Final

from jarvis_hands.core.config import CursorConfig, GestureThresholds
from jarvis_hands.gestures.engine import GestureEngine
from jarvis_hands.vision.cursor import CursorTracker
from jarvis_hands.vision.filters import OneEuroFilter2D
from jarvis_hands.vision.tracker import HandObservation, Landmark, TrackingResult

__all__ = [
    "ProfileReport",
    "ProfileResult",
    "benchmark_cursor",
    "benchmark_gestures",
    "benchmark_one_euro",
    "run_profile",
]

#: Iterasi default; cukup untuk angka stabil tanpa membuat CLI terasa lambat.
DEFAULT_ITERATIONS: Final = 2000


@dataclass(frozen=True)
class ProfileResult:
    """Satu hasil benchmark."""

    name: str
    iterations: int
    total_ms: float
    per_call_us: float
    note: str = ""


@dataclass(frozen=True)
class ProfileReport:
    """Kumpulan hasil benchmark siap cetak atau serialisasi."""

    results: tuple[ProfileResult, ...]

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        """Serialisasi ke dict siap-JSON."""
        return {
            "results": [
                {
                    "name": result.name,
                    "iterations": result.iterations,
                    "total_ms": round(result.total_ms, 3),
                    "per_call_us": round(result.per_call_us, 3),
                    "note": result.note,
                }
                for result in self.results
            ]
        }

    def to_markdown(self) -> str:
        """Tabel Markdown sederhana untuk terminal atau dokumentasi."""
        lines = [
            "| Benchmark | Iterasi | Total (ms) | Per panggilan (µs) |",
            "| --- | ---: | ---: | ---: |",
        ]
        lines.extend(
            f"| {result.name} | {result.iterations} | {result.total_ms:.2f} | "
            f"{result.per_call_us:.2f} |"
            for result in self.results
        )
        return "\n".join(lines)

    def slowest(self) -> ProfileResult | None:
        """Benchmark dengan waktu per panggilan terbesar."""
        if not self.results:
            return None
        return max(self.results, key=lambda result: result.per_call_us)


def _hand(x: float, y: float, pinch_ratio: float = 0.6) -> HandObservation:
    """Tangan sintetis 21 landmark; cukup untuk jalur kursor dan mesin gestur."""
    points = [Landmark(0.5, 0.9) for _ in range(21)]
    points[0] = Landmark(0.5, 0.9)
    points[9] = Landmark(0.5, 0.75)
    points[8] = Landmark(x, y)
    points[4] = Landmark(x + pinch_ratio * 0.15, y)
    for index in (5, 13, 17):
        points[index] = Landmark(0.5, 0.78)
    return HandObservation(landmarks=tuple(points), handedness="Right", score=0.95)


def _result(timestamp_ms: int, x: float = 0.5, y: float = 0.5) -> TrackingResult:
    return TrackingResult(
        hands=(_hand(x, y),),
        timestamp_ms=timestamp_ms,
        width=640,
        height=360,
    )


def _timed(
    name: str, iterations: int, step: Callable[[int], None], *, note: str = ""
) -> ProfileResult:
    iterations = max(1, int(iterations))
    # Pemanasan singkat agar alokasi awal tidak mendominasi.
    for index in range(min(16, iterations)):
        step(index)
    started = perf_counter()
    for index in range(iterations):
        step(index)
    total_ms = (perf_counter() - started) * 1000.0
    return ProfileResult(
        name=name,
        iterations=iterations,
        total_ms=total_ms,
        per_call_us=(total_ms * 1000.0) / iterations,
        note=note,
    )


def benchmark_one_euro(iterations: int = DEFAULT_ITERATIONS) -> ProfileResult:
    """Ukur One-Euro 2D pada laju 30 fps."""
    flt = OneEuroFilter2D()

    def step(index: int) -> None:
        t = index / 30.0
        flt.filter(0.5 + 0.01 * (index % 7), 0.5 - 0.01 * (index % 5), t=t)

    return _timed("One-Euro 2D", iterations, step, note="30 fps, gerak kecil")


def benchmark_cursor(iterations: int = DEFAULT_ITERATIONS) -> ProfileResult:
    """Ukur konversi landmark -> sampel kursor (termasuk One-Euro dan cubit)."""
    tracker = CursorTracker(
        cursor_config=CursorConfig(),
        thresholds=GestureThresholds(),
        screen_width=1920,
        screen_height=1080,
    )

    def step(index: int) -> None:
        tracker.update(_result(index * 33, 0.5 + 0.01 * (index % 9), 0.5))

    return _timed("Kursor 2D", iterations, step, note="1920x1080, 30 fps")


def benchmark_gestures(iterations: int = DEFAULT_ITERATIONS) -> ProfileResult:
    """Ukur mesin gestur lengkap (pinch, dua tangan, scrub, explode)."""
    engine = GestureEngine(screen_width=1920, screen_height=1080)

    def step(index: int) -> None:
        engine.process(_result(index * 33, 0.5 + 0.02 * (index % 11), 0.5))

    return _timed("Mesin gestur", iterations, step, note="satu tangan, tanpa event")


def run_profile(iterations: int = DEFAULT_ITERATIONS) -> ProfileReport:
    """Jalankan seluruh benchmark dan kembalikan laporan."""
    iterations = max(1, int(iterations))
    return ProfileReport(
        results=(
            benchmark_one_euro(iterations),
            benchmark_cursor(iterations),
            benchmark_gestures(iterations),
        )
    )
