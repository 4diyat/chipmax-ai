"""Orb: inti kaca 112 px dengan lima mekar yang mengikuti status cincin.

Orb adalah versi ringkas cincin JARVIS untuk kartu/panel: pusat kaca dengan rim
panas, cahaya 6% di sekelilingnya, dan lima mekar yang berputar dengan laju
berbeda per status. Animasi dihitung dari jam dinding (bisa disuntik) dan
berhenti saat disembunyikan atau saat status SENYAP.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QHideEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QRadialGradient,
    QShowEvent,
)
from PySide6.QtWidgets import QWidget

from jarvis_hands.core.state import Status
from jarvis_hands.ui.tokens import METRICS, Theme, build_theme, status_color, with_alpha

__all__ = ["PETALS", "Orb"]

#: Jumlah mekar di sekeliling inti.
PETALS = 5

#: Laju putar mekar per status (derajat per detik).
SPIN_DEG_S: dict[Status, float] = {
    Status.IDLE: 10.0,
    Status.LISTENING: 26.0,
    Status.THINKING: 120.0,
    Status.SPEAKING: 64.0,
    Status.SENYAP: 0.0,
}


class Orb(QWidget):
    """Orb kaca 112 px, lima mekar, glow 6%."""

    #: Status berubah (payload: :class:`jarvis_hands.core.state.Status`).
    status_changed = Signal(object)

    def __init__(
        self,
        theme: Theme | None = None,
        *,
        size: int = METRICS.orb_size,
        clock: Callable[[], float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self._clock = clock or time.monotonic
        self._size = max(32, int(size))
        self._status = Status.IDLE
        self._level = 0.0
        self._peak = 0.06
        self._started = self._clock()
        self._last_clock = self._started
        self._peak_clock = self._started
        self._rotation = 0.0

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(1000 // 60)
        self._timer.timeout.connect(self._tick)

        self.setFixedSize(self._size, self._size)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("Orb JARVIS")
        self._update_accessible()

    def set_theme(self, theme: Theme) -> None:
        """Ganti tema (misal kontras tinggi) tanpa membangun ulang orb."""
        self._theme = theme
        self.update()

    # ------------------------------------------------------------------ state

    @property
    def status(self) -> Status:
        """Status aktif."""
        return self._status

    @property
    def level(self) -> float:
        """Level suara 0..1."""
        return self._level

    @property
    def size_px(self) -> int:
        """Ukuran sisi widget (112 px bawaan)."""
        return self._size

    @property
    def rotation(self) -> float:
        """Sudut putar mekar saat ini (derajat)."""
        return self._rotation

    @property
    def elapsed(self) -> float:
        """Detik sejak status terakhir berubah."""
        return max(0.0, self._clock() - self._started)

    @property
    def petal_count(self) -> int:
        """Jumlah mekar."""
        return PETALS

    def is_animating(self) -> bool:
        """True bila timer animasi berjalan."""
        return self._timer.isActive()

    def spin_deg_s(self) -> float:
        """Laju putar mekar untuk status aktif."""
        return SPIN_DEG_S[self._status]

    def normalized_level(self) -> float:
        """Level ternormalisasi auto-gain 0..1."""
        self._sync_peak()
        return min(1.0, self._level / max(self._peak, 0.06))

    def set_status(self, status: Status) -> None:
        """Ganti status; fase animasi dimulai dari nol."""
        if status is self._status:
            return
        self._status = status
        self._started = self._clock()
        self._update_accessible()
        self._update_timer()
        self.status_changed.emit(status)
        self.update()

    def set_level(self, level: float) -> None:
        """Terima level suara 0..1 dari bridge agen."""
        self._level = max(0.0, min(1.0, float(level)))
        self._sync_peak()
        self._peak = max(self._peak, self._level)
        if self._status is Status.SPEAKING:
            self.update()

    # --------------------------------------------------------------- lifecycle

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._last_clock = self._clock()
        self._update_timer()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def _update_timer(self) -> None:
        if self.isVisible() and self._status is not Status.SENYAP:
            self._timer.start()
        else:
            self._timer.stop()

    def _tick(self) -> None:
        now = self._clock()
        dt = max(0.0, min(0.1, now - self._last_clock))
        self._last_clock = now
        self._sync_peak()
        self._rotation = (self._rotation + self.spin_deg_s() * dt) % 360.0
        self.update()

    def _sync_peak(self) -> None:
        now = self._clock()
        dt = max(0.0, now - self._peak_clock)
        self._peak_clock = now
        self._decay_peak(dt)

    def _decay_peak(self, dt: float) -> None:
        if dt > 0.0:
            self._peak = max(self._level, self._peak * math.exp(-dt / 1.6), 0.06)

    def _update_accessible(self) -> None:
        self.setAccessibleDescription(f"Status {self._status.label}")

    # ----------------------------------------------------------------- paint

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        side = float(self._size)
        center = QPointF(side / 2.0, side / 2.0)
        t = max(0.0, self._clock() - self._started)
        color = status_color(self._status, self._theme.palette)

        self._paint_glow(painter, center, side, t)
        self._paint_petals(painter, center, color, t)
        self._paint_core(painter, center, side, color, t)
        painter.end()

    def _paint_glow(self, painter: QPainter, center: QPointF, side: float, t: float) -> None:
        pal = self._theme.palette
        pulse = 0.5 + 0.5 * math.sin(2.0 * math.pi * t / 2.4)
        quiet = self._status is Status.SENYAP
        alpha = 0.0 if quiet else self._theme.style.glow_alpha * (0.8 + 0.4 * pulse)
        if alpha <= 0.0:
            return
        glow = QRadialGradient(center, side / 2.0)
        glow.setColorAt(0.0, with_alpha(pal.teal, alpha))
        glow.setColorAt(0.62, with_alpha(pal.teal, alpha * 0.45))
        glow.setColorAt(1.0, with_alpha(pal.teal, 0.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(center, side / 2.0, side / 2.0)

    def _paint_petals(self, painter: QPainter, center: QPointF, color: QColor, t: float) -> None:
        status = self._status
        if status is Status.SPEAKING:
            norm = self.normalized_level()
            scale = 0.92 + 0.16 * norm
            alpha = 0.34 + 0.30 * norm
        elif status is Status.LISTENING:
            pulse = 0.5 + 0.5 * math.sin(2.0 * math.pi * t / 1.1)
            scale = 0.94 + 0.08 * pulse
            alpha = 0.40 + 0.25 * pulse
        elif status is Status.THINKING:
            scale, alpha = 1.0, 0.55
        elif status is Status.SENYAP:
            scale, alpha = 0.86, 0.16
        else:
            breath = 0.5 + 0.5 * math.sin(2.0 * math.pi * t / 4.5)
            scale, alpha = 0.94 + 0.05 * breath, 0.32 + 0.10 * breath

        painter.save()
        painter.translate(center)
        painter.rotate(self._rotation)
        painter.scale(scale, scale)
        path = self._petal_path()
        for index in range(PETALS):
            painter.save()
            painter.rotate(index * 360.0 / PETALS)
            painter.setPen(QPen(with_alpha(color, min(1.0, alpha + 0.35)), 1.2))
            painter.setBrush(with_alpha(color, alpha))
            painter.drawPath(path)
            painter.restore()
        painter.restore()

    def _petal_path(self) -> QPainterPath:
        """Satu mekar: daun ramping dari radius 24 ke 46 mengarah ke atas."""
        side = float(self._size)
        unit = side / 112.0
        path = QPainterPath()
        base = QPointF(0.0, -24.0 * unit)
        tip = QPointF(0.0, -46.0 * unit)
        path.moveTo(base)
        path.cubicTo(
            QPointF(-11.0 * unit, -28.0 * unit),
            QPointF(-8.0 * unit, -42.0 * unit),
            tip,
        )
        path.cubicTo(
            QPointF(8.0 * unit, -42.0 * unit),
            QPointF(11.0 * unit, -28.0 * unit),
            base,
        )
        path.closeSubpath()
        return path

    def _paint_core(
        self,
        painter: QPainter,
        center: QPointF,
        side: float,
        color: QColor,
        t: float,
    ) -> None:
        pal = self._theme.palette
        quiet = self._status is Status.SENYAP
        unit = side / 112.0
        radius = 21.0 * unit
        if self._status is Status.SPEAKING:
            radius += 2.0 * unit * self.normalized_level()
        elif self._status is Status.LISTENING:
            radius += 1.5 * unit * (0.5 + 0.5 * math.sin(2.0 * math.pi * t / 1.1))

        fill = QRadialGradient(center + QPointF(-3.0 * unit, -4.0 * unit), radius * 1.6)
        fill.setColorAt(0.0, with_alpha(pal.hot_rim, 0.0 if quiet else 0.30))
        fill.setColorAt(0.7, with_alpha(pal.teal, 0.22))
        fill.setColorAt(1.0, with_alpha(pal.stage, 0.70))
        painter.setPen(QPen(with_alpha(pal.border, 0.30 if quiet else 0.60), 1.5))
        painter.setBrush(fill)
        painter.drawEllipse(center, radius, radius)

        dot = 3.5 * unit
        if self._status is Status.SPEAKING:
            dot += 2.5 * unit * self.normalized_level()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(color, 0.45 if quiet else 0.95))
        painter.drawEllipse(center, dot, dot)
