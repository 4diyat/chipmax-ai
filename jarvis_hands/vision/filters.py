"""One-Euro filter murni Python.

Digunakan untuk menghaluskan landmark/kursor tanpa Qt. Implementasi mengikuti
paper Casiez et al. (2012): cutoff naik saat gerakan cepat (beta), turun saat
diam (min_cutoff), sehingga kecil lag saat bergerak dan kecil noise saat diam.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import ClassVar

__all__ = ["OneEuroFilter", "OneEuroFilter2D", "OneEuroParams"]


@dataclass(frozen=True)
class OneEuroParams:
    """Parameter One-Euro. ``min_cutoff`` dan ``d_cutoff`` dalam Hz."""

    min_cutoff: float = 1.2
    beta: float = 0.02
    d_cutoff: float = 1.0

    def __post_init__(self) -> None:
        if self.min_cutoff <= 0:
            raise ValueError("min_cutoff harus > 0")
        if self.beta < 0:
            raise ValueError("beta harus >= 0")
        if self.d_cutoff <= 0:
            raise ValueError("d_cutoff harus > 0")


class _LowPass:
    """Filter low-pass exponential sederhana."""

    __slots__ = ("_value",)

    def __init__(self, initial: float = 0.0) -> None:
        self._value = initial

    @property
    def value(self) -> float:
        """Nilai terakhir."""
        return self._value

    def filter(self, sample: float, alpha: float) -> float:
        """Campur sample dengan nilai sebelumnya."""
        self._value = alpha * sample + (1.0 - alpha) * self._value
        return self._value

    def reset(self, value: float = 0.0) -> None:
        self._value = value


class OneEuroFilter:
    """Filter satu sumbu. ``filter(x, t)`` memakai ``t`` detik (monoton)."""

    #: Asumsi selang waktu frame pertama saat nilai awal diberikan tanpa waktu.
    _FIRST_DT: ClassVar[float] = 1.0 / 60.0

    def __init__(
        self,
        params: OneEuroParams | None = None,
        *,
        x0: float | None = None,
    ) -> None:
        self._params = params or OneEuroParams()
        self._x = _LowPass(x0 if x0 is not None else 0.0)
        self._dx = _LowPass()
        self._t_prev: float | None = None
        self._initialized = x0 is not None

    @property
    def params(self) -> OneEuroParams:
        """Parameter aktif."""
        return self._params

    def filter(self, x: float, t: float | None = None) -> float:
        """Haluskan satu sampel; return nilai terhalus."""
        now = time.monotonic() if t is None else float(t)
        if self._t_prev is None:
            if not self._initialized:
                self._x = _LowPass(x)
                self._dx = _LowPass()
                self._initialized = True
                self._t_prev = now
                return x
            self._t_prev = now - self._FIRST_DT
        assert self._t_prev is not None
        dt = max(1e-6, now - self._t_prev)
        self._t_prev = now
        dx = (x - self._x.value) / dt
        edx = self._dx.filter(dx, self._alpha(dt, self._params.d_cutoff))
        cutoff = self._params.min_cutoff + self._params.beta * abs(edx)
        return self._x.filter(x, self._alpha(dt, cutoff))

    def reset(self, x0: float | None = None) -> None:
        """Reset filter; bila ``x0`` diisi, sampel berikutnya langsung mulai dari sana."""
        self._x = _LowPass(x0 if x0 is not None else 0.0)
        self._dx = _LowPass()
        self._t_prev = None
        self._initialized = x0 is not None

    @staticmethod
    def _alpha(dt: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * max(1e-6, cutoff))
        return 1.0 / (1.0 + tau / max(1e-6, dt))


class OneEuroFilter2D:
    """Dua filter One-Euro untuk posisi (x, y)."""

    def __init__(
        self,
        params: OneEuroParams | None = None,
        *,
        x0: float | None = None,
        y0: float | None = None,
    ) -> None:
        self._x = OneEuroFilter(params, x0=x0)
        self._y = OneEuroFilter(params, x0=y0)

    def filter(
        self,
        x: float,
        y: float,
        t: float | None = None,
    ) -> tuple[float, float]:
        """Haluskan satu titik; return (x, y) terhalus."""
        return self._x.filter(x, t), self._y.filter(y, t)

    def reset(self, x0: float | None = None, y0: float | None = None) -> None:
        """Reset kedua sumbu."""
        self._x.reset(x0)
        self._y.reset(y0)
