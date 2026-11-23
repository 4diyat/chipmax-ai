"""Tipe event gestur (murni Python, tanpa Qt).

Mesin gestur mengembalikan daftar :class:`GestureEvent` per frame. Pemanggil
(Qt bridge, UI) yang menerjemahkan event menjadi aksi; modul ini tidak tahu
widget maupun signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique

__all__ = ["GestureEvent", "GestureKind", "GesturePhase"]


@unique
class GestureKind(StrEnum):
    """Enam gestur yang didukung."""

    TAP = "tap"
    DRAG = "drag"
    HOLD = "hold"
    TWO_HAND = "two_hand"
    CLAP = "clap"
    SCRUB_EXPLODE = "scrub_explode"


@unique
class GesturePhase(StrEnum):
    """Fasa event: mulai, berjalan, selesai, atau satu tembakan."""

    BEGIN = "begin"
    UPDATE = "update"
    END = "end"
    ONE_SHOT = "one_shot"


@dataclass(frozen=True)
class GestureEvent:
    """Satu event gestur dengan posisi layar dan metrik.

    ``magnitude`` bersatuan milidetik untuk HOLD, piksel untuk gestur lain.
    ``action`` membedakan ``scrub`` dan ``explode`` pada ``SCRUB_EXPLODE``.
    """

    kind: GestureKind
    phase: GesturePhase
    timestamp_ms: int
    x: int
    y: int
    dx: float = 0.0
    dy: float = 0.0
    magnitude: float = 0.0
    action: str = ""
    cancelled: bool = False
    hands: int = 1

    @property
    def position(self) -> tuple[int, int]:
        """Posisi layar (x, y)."""
        return self.x, self.y

    @property
    def is_begin(self) -> bool:
        """True bila event adalah awal gestur."""
        return self.phase is GesturePhase.BEGIN

    @property
    def is_end(self) -> bool:
        """True bila event adalah akhir gestur."""
        return self.phase is GesturePhase.END
