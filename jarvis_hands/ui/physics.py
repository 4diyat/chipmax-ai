"""Fisika sederhana untuk kartu: pegas + redaman, murni Python.

Dipakai saat kartu dilepas dari seretan supaya kembali ke posisi istirahat
tanpa memakai QPropertyAnimation. Modelnya osilator teredam klasik yang
diintegrasi semi-implisit dengan sub-langkah tetap (1/240 s) supaya hasilnya
tidak bergantung pada laju frame:

    a = (target - x) * stiffness - 2 * damping * sqrt(stiffness) * v
    v += a * dt ;  x += v * dt

Dengan ``stiffness`` 620 dan rasio redaman ``damping`` 0.82, kartu yang
dilepas 200 px dari rumahnya sampai di target pada ±180 ms, melewati target
kurang dari 1 px, dan berhenti pada ±350 ms. ``damping`` 1 berarti redaman
kritis, 0 berarti tanpa redaman. Batas layar opsional menjepit posisi dan
menghapus kecepatan pada sisi yang tertabrak.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import ClassVar

__all__ = ["SpringConfig", "SpringMotion"]


@dataclass(frozen=True)
class SpringConfig:
    """Parameter pegas.

    ``stiffness`` bersatuan 1/s^2 per piksel jarak; ``damping`` adalah rasio
    redaman 0..1 (1 = kritis); ``rest_threshold`` jarak diam dalam piksel;
    ``max_speed`` batas kecepatan dalam piksel per detik.
    """

    stiffness: float = 620.0
    damping: float = 0.82
    max_speed: float = 4000.0
    rest_threshold: float = 0.5

    #: Sub-langkah integrasi tetap (detik) agar tidak bergantung laju frame.
    SUBSTEP: ClassVar[float] = 1.0 / 240.0

    def __post_init__(self) -> None:
        if self.stiffness <= 0:
            raise ValueError("stiffness harus > 0")
        if not 0.0 <= self.damping <= 1.0:
            raise ValueError("damping harus 0..1")
        if self.max_speed <= 0:
            raise ValueError("max_speed harus > 0")
        if self.rest_threshold <= 0:
            raise ValueError("rest_threshold harus > 0")


class SpringMotion:
    """Titik dua dimensi dengan pegas menuju target dan batas layar opsional."""

    def __init__(
        self,
        config: SpringConfig | None = None,
        *,
        x: float = 0.0,
        y: float = 0.0,
    ) -> None:
        self._config = config or SpringConfig()
        self._x = float(x)
        self._y = float(y)
        self._vx = 0.0
        self._vy = 0.0
        self._tx = self._x
        self._ty = self._y
        self._bounds: tuple[float, float, float, float] | None = None

    @property
    def config(self) -> SpringConfig:
        """Parameter pegas."""
        return self._config

    @property
    def x(self) -> float:
        """Posisi X saat ini."""
        return self._x

    @property
    def y(self) -> float:
        """Posisi Y saat ini."""
        return self._y

    @property
    def vx(self) -> float:
        """Kecepatan X (piksel per detik)."""
        return self._vx

    @property
    def vy(self) -> float:
        """Kecepatan Y (piksel per detik)."""
        return self._vy

    @property
    def target(self) -> tuple[float, float]:
        """Target pegas."""
        return self._tx, self._ty

    @property
    def position(self) -> tuple[float, float]:
        """Posisi saat ini."""
        return self._x, self._y

    @property
    def bounds(self) -> tuple[float, float, float, float] | None:
        """Batas ``(kiri, atas, kanan, bawah)`` bila ada."""
        return self._bounds

    @property
    def settled(self) -> bool:
        """True bila sudah dekat target dan hampir berhenti."""
        return (
            math.hypot(self._x - self._tx, self._y - self._ty) < self._config.rest_threshold
            and math.hypot(self._vx, self._vy) < self._config.rest_threshold * 10.0
        )

    def set_target(self, x: float, y: float) -> None:
        """Ubah target tanpa mengubah posisi."""
        self._tx = float(x)
        self._ty = float(y)
        self._clamp_target()

    def set_bounds(
        self,
        left: float | None = None,
        top: float | None = None,
        right: float | None = None,
        bottom: float | None = None,
    ) -> None:
        """Atur batas layar; ``None`` pada keempat sisi menghapus batas."""
        if left is None and top is None and right is None and bottom is None:
            self._bounds = None
            self._clamp_to_bounds()
            return
        if left is None or top is None or right is None or bottom is None:
            raise ValueError("semua sisi batas harus diisi")
        if right < left or bottom < top:
            raise ValueError("batas kanan/bawah harus >= kiri/atas")
        self._bounds = (float(left), float(top), float(right), float(bottom))
        self._clamp_target()
        self._clamp_to_bounds()

    def set_position(self, x: float, y: float, *, keep_velocity: bool = False) -> None:
        """Ubah posisi langsung (misalnya saat diseret)."""
        self._x = float(x)
        self._y = float(y)
        if not keep_velocity:
            self._vx = 0.0
            self._vy = 0.0
        self._clamp_to_bounds()

    def fling(self, vx: float, vy: float) -> None:
        """Berikan kecepatan awal, dibatasi ``max_speed``."""
        limit = self._config.max_speed
        speed = math.hypot(vx, vy)
        if speed > limit:
            scale = limit / speed
            vx *= scale
            vy *= scale
        self._vx = float(vx)
        self._vy = float(vy)

    def step(self, dt: float) -> tuple[float, float]:
        """Maju ``dt`` detik (maksimum 1/30 s) lewat sub-langkah tetap."""
        total = min(1.0 / 30.0, max(0.0, float(dt)))
        if total <= 0.0:
            return self._x, self._y
        cfg = self._config
        drag = 2.0 * cfg.damping * math.sqrt(cfg.stiffness)
        substeps = max(1, math.ceil(total / cfg.SUBSTEP - 1e-9))
        h = total / substeps
        for _ in range(substeps):
            ax = (self._tx - self._x) * cfg.stiffness - drag * self._vx
            ay = (self._ty - self._y) * cfg.stiffness - drag * self._vy
            self.fling(self._vx + ax * h, self._vy + ay * h)
            self._x += self._vx * h
            self._y += self._vy * h
        self._clamp_to_bounds()
        return self._x, self._y

    def reset(self, x: float = 0.0, y: float = 0.0) -> None:
        """Kembalikan posisi, target, dan kecepatan ke nilai awal."""
        self._x = float(x)
        self._y = float(y)
        self._tx = self._x
        self._ty = self._y
        self._vx = 0.0
        self._vy = 0.0
        self._clamp_target()
        self._clamp_to_bounds()

    def _clamp_target(self) -> None:
        if self._bounds is not None:
            left, top, right, bottom = self._bounds
            self._tx = max(left, min(right, self._tx))
            self._ty = max(top, min(bottom, self._ty))

    def _clamp_to_bounds(self) -> None:
        bounds = self._bounds
        if bounds is None:
            return
        left, top, right, bottom = bounds
        if self._x < left:
            self._x, self._vx = left, 0.0 if self._vx < 0 else self._vx
        elif self._x > right:
            self._x, self._vx = right, 0.0 if self._vx > 0 else self._vx
        if self._y < top:
            self._y, self._vy = top, 0.0 if self._vy < 0 else self._vy
        elif self._y > bottom:
            self._y, self._vy = bottom, 0.0 if self._vy > 0 else self._vy
