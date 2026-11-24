"""RingWidget: cincin 440 px, lima status, satu QTimer 60 fps.

Animasi dihitung dari jam dinding (``time.monotonic``), bukan counter per frame,
supaya tetap konsisten saat frame terlewat. Clock bisa disuntik untuk tes.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QFont,
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
from jarvis_hands.ui.tokens import (
    FONT,
    METRICS,
    Theme,
    build_theme,
    mono_font,
    sans_font,
    status_color,
    with_alpha,
)

__all__ = ["RingWidget"]


class RingWidget(QWidget):
    """Cincin JARVIS dengan lima status dan animasi berbasis jam dinding."""

    #: Status berubah (payload: :class:`jarvis_hands.core.state.Status`).
    status_changed = Signal(object)

    def __init__(
        self,
        theme: Theme | None = None,
        *,
        clock: Callable[[], float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self._clock = clock or time.monotonic
        self._status = Status.IDLE
        self._level = 0.0
        self._peak = 0.06
        self._last_clock = self._clock()
        self._started = self._last_clock

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(1000 // 60)
        self._timer.timeout.connect(self._tick)

        self.setFixedSize(METRICS.ring_size, METRICS.ring_size)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAutoFillBackground(False)
        self.setAccessibleName("Cincin JARVIS")
        self._word_font = sans_font(FONT.title, bold=True)
        self._word_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 7.0)
        self._status_font = mono_font(FONT.label, spacing=3.0)
        self._update_accessible()

    def set_theme(self, theme: Theme) -> None:
        """Ganti tema (misal kontras tinggi) tanpa membangun ulang cincin."""
        self._theme = theme
        self.update()

    # ------------------------------------------------------------------ state

    @property
    def status(self) -> Status:
        """Status aktif."""
        return self._status

    @property
    def level(self) -> float:
        """Level gelombang suara mentah 0..1."""
        return self._level

    @property
    def elapsed(self) -> float:
        """Detik sejak status terakhir berubah."""
        return max(0.0, self._clock() - self._started)

    @property
    def tick_count(self) -> int:
        """Jumlah tick cincin (48)."""
        return METRICS.ring_ticks

    @property
    def timer_interval_ms(self) -> int:
        """Interval QTimer; 16 ms untuk 60 fps."""
        return self._timer.interval()

    def is_animating(self) -> bool:
        """True bila timer animasi sedang berjalan."""
        return self._timer.isActive()

    def normalized_level(self) -> float:
        """Level ternormalisasi auto-gain 0..1.

        Puncak mengikuti level lalu meluruh dengan konstanta waktu 1.6 detik;
        lantai 0.06 membuat suara pelan tetap terlihat.
        """
        self._sync_peak()
        return min(1.0, self._level / max(self._peak, 0.06))

    def set_status(self, status: Status) -> None:
        """Ganti status; animasi dimulai dari fase nol."""
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

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(METRICS.ring_size, METRICS.ring_size)

    def _update_timer(self) -> None:
        if self.isVisible() and self._status is not Status.SENYAP:
            self._timer.start()
        else:
            self._timer.stop()

    def _tick(self) -> None:
        self._sync_peak()
        if self._status is not Status.SENYAP:
            self.update()

    def _sync_peak(self) -> None:
        now = self._clock()
        dt = max(0.0, now - self._last_clock)
        self._last_clock = now
        if dt > 0.0:
            self._peak = max(self._level, self._peak * math.exp(-dt / 1.6), 0.06)

    def _update_accessible(self) -> None:
        self.setAccessibleDescription(f"Status {self._status.label}")

    # ----------------------------------------------------------------- paint

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        self._sync_peak()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        t = max(0.0, self._clock() - self._started)
        side = min(self.width(), self.height())
        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        outer = side / 2.0 - 22.0
        inner = outer - METRICS.ring_band
        core = inner - 10.0

        self._paint_ticks(painter, center, side, t)
        self._paint_band(painter, center, outer, inner, core, t)
        self._paint_core(painter, center, core, t)
        self._paint_text(painter, center, core)
        painter.end()

    def _paint_ticks(self, painter: QPainter, center: QPointF, side: float, t: float) -> None:
        pal = self._theme.palette
        status = self._status
        count = METRICS.ring_ticks
        rotation = (t * 6.0) % 360.0 if status is Status.THINKING else 0.0
        listening = 0.5 + 0.5 * math.sin(2.0 * math.pi * t / 1.1)
        color = status_color(status, pal)
        for index in range(count):
            angle = math.radians(rotation + index * 360.0 / count - 90.0)
            major = index % 6 == 0
            r0 = side / 2.0 - (10.0 if major else 8.0)
            r1 = side / 2.0 - (3.0 if major else 4.5)
            alpha = 0.42 if major else 0.22
            if status is Status.LISTENING:
                alpha *= 0.7 + 0.6 * listening
            elif status is Status.SENYAP:
                alpha *= 0.5
            pen = QPen(with_alpha(color, alpha), 2.0 if major else 1.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(
                center + QPointF(math.cos(angle) * r0, math.sin(angle) * r0),
                center + QPointF(math.cos(angle) * r1, math.sin(angle) * r1),
            )

    def _paint_band(
        self,
        painter: QPainter,
        center: QPointF,
        outer: float,
        inner: float,
        core: float,
        t: float,
    ) -> None:
        pal = self._theme.palette
        status = self._status
        if status is Status.SENYAP:
            color = pal.muted
            alpha = 0.30
        elif status is Status.LISTENING:
            pulse = 0.5 + 0.5 * math.sin(2.0 * math.pi * t / 1.1)
            color = pal.listening
            alpha = 0.60 + 0.30 * pulse
            outer -= 4.0 * pulse
            inner -= 4.0 * pulse
        elif status is Status.THINKING:
            color = pal.teal
            alpha = 0.75
        elif status is Status.SPEAKING:
            norm = self.normalized_level()
            color = _lerp(pal.band, pal.hot_rim, 0.15 + 0.85 * norm)
            alpha = 0.55 + 0.40 * norm
            outer -= 1.5 * norm
            inner -= 1.5 * norm
        else:
            breath = 0.5 + 0.5 * math.sin(2.0 * math.pi * t / 4.5)
            color = pal.band
            alpha = 0.48 + 0.20 * breath
            outer *= 1.0 + 0.008 * breath
            inner *= 1.0 + 0.008 * breath

        mid = (outer + inner) / 2.0
        rect = QRectF(center.x() - mid, center.y() - mid, mid * 2.0, mid * 2.0)

        if status is not Status.SENYAP:
            for extra, glow in ((20.0, 0.03), (12.0, 0.05), (5.0, 0.08)):
                glow_pen = QPen(
                    with_alpha(color, alpha * glow),
                    METRICS.ring_band + extra,
                )
                painter.setPen(glow_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawArc(rect, 0, 360 * 16)

        band_pen = QPen(with_alpha(color, alpha), METRICS.ring_band)
        band_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(band_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(rect, 0, 360 * 16)

        if status is Status.SPEAKING:
            rim_alpha = 0.55
        elif status is Status.SENYAP:
            rim_alpha = 0.18
        else:
            rim_alpha = 0.35
        rim_pen = QPen(with_alpha(pal.hot_rim, rim_alpha), 1.5)
        painter.setPen(rim_pen)
        for radius in (outer, inner):
            painter.drawEllipse(center, radius, radius)

        if status is Status.LISTENING:
            for index in range(2):
                phase = ((t / 1.1) + index * 0.5) % 1.0
                radius = outer - phase * max(1.0, outer - core)
                echo = QPen(with_alpha(pal.listening, (1.0 - phase) * 0.28), 2.0)
                painter.setPen(echo)
                painter.drawEllipse(center, radius, radius)

        if status is Status.SPEAKING:
            norm = self.normalized_level()
            if norm > 0.01:
                level_pen = QPen(
                    with_alpha(pal.hot_rim, 0.15 + 0.55 * norm),
                    3.0,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
                painter.setPen(level_pen)
                level_radius = inner - 5.0
                painter.drawArc(
                    QRectF(
                        center.x() - level_radius,
                        center.y() - level_radius,
                        level_radius * 2.0,
                        level_radius * 2.0,
                    ),
                    90 * 16,
                    -int(norm * 360 * 16),
                )

    def _paint_core(self, painter: QPainter, center: QPointF, core: float, t: float) -> None:
        pal = self._theme.palette
        dim = self._status is Status.SENYAP
        path = QPainterPath()
        path.addEllipse(center, core, core)

        gradient = QRadialGradient(
            center + QPointF(-core * 0.25, -core * 0.30),
            core * 1.25,
        )
        gradient.setColorAt(0.0, with_alpha(pal.hot_rim, 0.04 if dim else 0.10))
        gradient.setColorAt(0.55, with_alpha(pal.teal, 0.02 if dim else 0.05))
        gradient.setColorAt(1.0, with_alpha(pal.stage, 0.24 if dim else 0.20))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(path)

        if self._status is Status.THINKING:
            painter.save()
            painter.setClipPath(path)
            angle = -(t * 110.0) % 360.0
            sweep = QConicalGradient(center, angle)
            sweep.setColorAt(0.0, with_alpha(pal.teal, 0.0))
            sweep.setColorAt(0.70, with_alpha(pal.teal, 0.0))
            sweep.setColorAt(0.93, with_alpha(pal.teal, 0.20))
            sweep.setColorAt(1.0, with_alpha(pal.accent, 0.45))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(sweep)
            painter.drawEllipse(center, core - 6.0, core - 6.0)
            rad = math.radians(angle)
            painter.setPen(QPen(with_alpha(pal.hot_rim, 0.45), 1.5))
            painter.drawLine(
                center,
                center + QPointF(math.cos(rad) * (core - 8.0), math.sin(rad) * (core - 8.0)),
            )
            painter.restore()

        painter.setPen(QPen(with_alpha(pal.teal, 0.16 if dim else 0.28), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, core - 10.0, core - 10.0)

    def _paint_text(self, painter: QPainter, center: QPointF, core: float) -> None:
        pal = self._theme.palette
        status = self._status
        word_color = with_alpha(pal.hot_rim, 0.50 if status is Status.SENYAP else 0.92)
        status_color_value = with_alpha(
            status_color(status, pal), 0.65 if status is Status.SENYAP else 0.95
        )
        painter.setFont(self._word_font)
        painter.setPen(word_color)
        painter.drawText(
            QRectF(center.x() - core, center.y() - 34.0, core * 2.0, 34.0),
            Qt.AlignmentFlag.AlignCenter,
            "J.A.R.V.I.S",
        )
        painter.setFont(self._status_font)
        painter.setPen(status_color_value)
        painter.drawText(
            QRectF(center.x() - core, center.y() + 6.0, core * 2.0, 20.0),
            Qt.AlignmentFlag.AlignCenter,
            status.label,
        )


def _lerp(first: QColor, second: QColor, factor: float) -> QColor:
    factor = max(0.0, min(1.0, factor))
    return QColor(
        round(first.red() + (second.red() - first.red()) * factor),
        round(first.green() + (second.green() - first.green()) * factor),
        round(first.blue() + (second.blue() - first.blue()) * factor),
    )
