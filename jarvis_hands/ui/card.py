"""Card dan Panel: kartu kaca 340x190 dan panel kaca dengan pegangan/tombol tutup.

Kartu diseret di pegangannya, lewat mouse maupun gestur (``begin_drag`` /
``update_drag`` / ``end_drag`` menerima titik dalam koordinat induk). Saat
diseret kartu miring mengikuti kecepatan horizontal (3-4 derajat pada
420 px/s), bayangannya melebar, dan jejak putus-putus tercetak di belakangnya.
Saat dilepas, posisi dan kecepatan masuk ke :class:`SpringMotion` yang menarik
kartu kembali ke rumahnya di dalam batas layar; lepasan cepat menghilangkan
kartu lewat sinyal ``dismissed``.

Panel memakai chrome yang sama (pegangan 48x4, tombol tutup 44 px yang tetap
``QPushButton`` agar bisa dijangkau keyboard) dan berisi widget apa pun lewat
``body()``. Panel tidak memantul: ia tinggal di tempat dilepas.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable, Sequence
from typing import Final

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QFontMetrics,
    QHideEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from jarvis_hands.ui.glass import (
    CLOSE_TARGET,
    SurfaceHit,
    close_rect,
    handle_rect,
    paint_card_surface,
    paint_close,
    paint_handle,
    paint_shadow,
)
from jarvis_hands.ui.physics import SpringConfig, SpringMotion
from jarvis_hands.ui.tokens import (
    FONT,
    METRICS,
    Theme,
    build_theme,
    caps,
    mono_font,
    sans_font,
    with_alpha,
)

__all__ = ["CARD_HEIGHT", "CARD_WIDTH", "Card", "Panel"]

#: Ukuran permukaan kartu (tanpa margin bayangan/jejak).
CARD_WIDTH: Final = 340
CARD_HEIGHT: Final = 190
#: Margin transparan di sekeliling permukaan untuk bayangan dan jejak.
CARD_MARGIN: Final = 36
#: Kecepatan horizontal yang menghasilkan kemiringan penuh.
TILT_REFERENCE_PX_S: Final = 420.0
MAX_TILT_DEG: Final = 4.0
TRAIL_LIMIT: Final = 16
#: Lepasan dengan kecepatan >= ini menghilangkan kartu.
DISMISS_SPEED_PX_S: Final = 1600.0
#: Jendela waktu sampel kecepatan saat melepas.
VELOCITY_WINDOW_S: Final = 0.12


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class Card(QWidget):
    """Kartu kaca 340x190: pegangan, tombol tutup, chip, judul, dan teks."""

    #: Tombol tutup ditekan (mouse, keyboard, atau gestur).
    close_requested = Signal()
    #: Badan kartu diketuk/ditekan-enter.
    opened = Signal()
    #: Kartu dilepas cepat dan menghilang.
    dismissed = Signal()
    #: Mulai seret (payload: posisi kartu di koordinat induk).
    drag_started = Signal(QPoint)
    #: Kartu bergerak saat diseret.
    drag_moved = Signal(QPoint)
    #: Seret selesai (juga sebelum ``dismissed``).
    drag_ended = Signal(QPoint)
    #: Pegas selesai; kartu diam di rumahnya.
    settled = Signal(QPoint)

    def __init__(
        self,
        title: str,
        text: str = "",
        *,
        chip: str = "DRAF",
        theme: Theme | None = None,
        clock: Callable[[], float] | None = None,
        spring: SpringConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self._clock = clock or time.monotonic
        self._title = title
        self._text = text
        self._chip = chip
        self._motion = SpringMotion(spring)
        self._area: QRectF | None = None
        self._dragging = False
        self._drag_offset = QPointF()
        self._press_body = False
        self._hover_close = False
        self._samples: deque[tuple[float, QPointF]] = deque(maxlen=24)
        self._trail: deque[QPointF] = deque(maxlen=TRAIL_LIMIT)
        self._tilt = 0.0
        self._dismiss_speed = DISMISS_SPEED_PX_S
        self._last_tick = self._clock()

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(1000 // 60)
        self._timer.timeout.connect(self._tick)

        self.setFixedSize(CARD_WIDTH + 2 * CARD_MARGIN, CARD_HEIGHT + 2 * CARD_MARGIN)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Kartu {title}")
        self._update_accessible()

    # ------------------------------------------------------------------ state

    @property
    def title(self) -> str:
        """Judul kartu."""
        return self._title

    @property
    def text(self) -> str:
        """Teks isi kartu."""
        return self._text

    @property
    def chip(self) -> str:
        """Label chip (mis. DRAF, LOKAL)."""
        return self._chip

    @property
    def is_dragging(self) -> bool:
        """True saat kartu sedang diseret."""
        return self._dragging

    @property
    def tilt(self) -> float:
        """Kemiringan saat ini (derajat, -4..4)."""
        return self._tilt

    @property
    def velocity(self) -> QPointF:
        """Kecepatan terukur saat diseret, atau kecepatan pegas."""
        if self._dragging:
            return self._drag_velocity()
        return QPointF(self._motion.vx, self._motion.vy)

    @property
    def home(self) -> QPoint:
        """Posisi rumah (target pegas) di koordinat induk."""
        return QPoint(round(self._motion.target[0]), round(self._motion.target[1]))

    @property
    def trail(self) -> list[QPoint]:
        """Jejak posisi kartu di koordinat induk (terbaru terakhir)."""
        return [QPoint(round(p.x()), round(p.y())) for p in self._trail]

    @property
    def is_animating(self) -> bool:
        """True bila timer pegas/jejak sedang berjalan."""
        return self._timer.isActive()

    def set_title(self, title: str) -> None:
        """Ganti judul."""
        self._title = title
        self._update_accessible()
        self.update()

    def set_text(self, text: str) -> None:
        """Ganti teks isi."""
        self._text = text
        self._update_accessible()
        self.update()

    def set_chip(self, chip: str) -> None:
        """Ganti label chip."""
        self._chip = chip
        self._update_accessible()
        self.update()

    def set_bounds(self, area: QRectF | None) -> None:
        """Batasi gerak kartu ke ``area`` induk (None = tanpa batas)."""
        self._area = QRectF(area) if area is not None else None
        self._sync_bounds()
        self._clamp_into_area()

    def set_home(self, x: float, y: float) -> None:
        """Tetapkan rumah kartu; kartu yang diam langsung pindah ke sana."""
        self._motion.set_target(x, y)
        self._sync_bounds()
        if not self._dragging and not self._timer.isActive():
            self._motion.set_position(x, y)
            self.move(self.home)

    def set_theme(self, theme: Theme) -> None:
        """Ganti tema (misal kontras tinggi) tanpa membangun ulang kartu."""
        self._theme = theme
        self.update()

    def dismiss_speed(self) -> float:
        """Ambang kecepatan lepasan yang menghilangkan kartu."""
        return self._dismiss_speed

    def set_dismiss_speed(self, px_per_s: float) -> None:
        """Atur ambang lepasan cepat."""
        self._dismiss_speed = max(0.0, float(px_per_s))

    # -------------------------------------------------------------- geometri

    def surface_rect(self) -> QRectF:
        """Permukaan kaca 340x190 dalam koordinat kartu."""
        return QRectF(CARD_MARGIN, CARD_MARGIN, float(CARD_WIDTH), float(CARD_HEIGHT))

    def handle_rect(self) -> QRectF:
        """Pegangan geser 48x4 dalam koordinat kartu."""
        return handle_rect(self.surface_rect())

    def close_rect(self) -> QRectF:
        """Target tombol tutup 44x44 dalam koordinat kartu."""
        return close_rect(self.surface_rect())

    def hit_test(self, local: QPointF) -> SurfaceHit:
        """Bagian mana dari kartu yang berada di ``local``."""
        if not self.surface_rect().contains(local):
            return SurfaceHit.NONE
        if self.close_rect().contains(local):
            return SurfaceHit.CLOSE
        if self.handle_rect().adjusted(-8, -8, 8, 8).contains(local):
            return SurfaceHit.HANDLE
        return SurfaceHit.BODY

    # ------------------------------------------------------------------ drag

    def begin_drag(self, point: QPointF) -> bool:
        """Mulai seret; ``point`` adalah posisi kursor di koordinat induk."""
        if self._dragging:
            return False
        self._dragging = True
        self._drag_offset = point - QPointF(self.pos())
        self._samples.clear()
        self._samples.append((self._clock(), QPointF(point)))
        self._trail.clear()
        self._motion.set_position(self.x(), self.y())
        self._last_tick = self._clock()
        self._timer.start()
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.drag_started.emit(self.pos())
        return True

    def update_drag(self, point: QPointF, timestamp: float | None = None) -> None:
        """Gerakkan kartu mengikuti ``point`` (koordinat induk)."""
        if not self._dragging:
            return
        target = point - self._drag_offset
        self._trail.append(QPointF(self.pos()))
        self.move(round(target.x()), round(target.y()))
        self._clamp_into_area()
        now = self._clock() if timestamp is None else float(timestamp)
        self._samples.append((now, QPointF(point)))
        self.drag_moved.emit(self.pos())

    def end_drag(self) -> bool:
        """Akhiri seret. Return True bila kartu dilepas cepat (dismissed)."""
        if not self._dragging:
            return False
        self._dragging = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        velocity = self._drag_velocity()
        if self._samples and self._clock() - self._samples[-1][0] > VELOCITY_WINDOW_S:
            velocity = QPointF()
        pos = QPointF(self.pos())
        self._motion.set_position(pos.x(), pos.y())
        self.drag_ended.emit(self.pos())
        if math.hypot(velocity.x(), velocity.y()) >= self._dismiss_speed:
            self._samples.clear()
            self._trail.clear()
            self._timer.stop()
            self.hide()
            self.dismissed.emit()
            return True
        self._motion.fling(velocity.x(), velocity.y())
        self._last_tick = self._clock()
        self._timer.start()
        self.update()
        return False

    def cancel_drag(self) -> None:
        """Batalkan seret: kembali ke rumah tanpa kecepatan."""
        if not self._dragging:
            return
        self._dragging = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._samples.clear()
        self._motion.set_position(self.x(), self.y())
        self._last_tick = self._clock()
        self._timer.start()

    def _drag_velocity(self) -> QPointF:
        if len(self._samples) < 2:
            return QPointF()
        t_last, p_last = self._samples[-1]
        t_first, p_first = self._samples[0]
        for stamp, point in self._samples:
            if t_last - stamp <= VELOCITY_WINDOW_S:
                t_first, p_first = stamp, point
                break
        dt = t_last - t_first
        if dt <= 1e-3:
            return QPointF()
        return QPointF((p_last.x() - p_first.x()) / dt, (p_last.y() - p_first.y()) / dt)

    # ------------------------------------------------------------------ tick

    def _tick(self) -> None:
        now = self._clock()
        dt = _clamp(now - self._last_tick, 0.0, 1.0 / 30.0)
        self._last_tick = now
        if not self._dragging:
            x, y = self._motion.step(dt)
            self.move(round(x), round(y))
            if self._trail:
                self._trail.popleft()
        target_tilt = _clamp(
            self.velocity.x() / TILT_REFERENCE_PX_S * 3.5, -MAX_TILT_DEG, MAX_TILT_DEG
        )
        self._tilt += (target_tilt - self._tilt) * 0.35
        if (
            not self._dragging
            and self._motion.settled
            and not self._trail
            and abs(self._tilt) < 0.05
        ):
            self._tilt = 0.0
            self._motion.set_position(*self._motion.target)
            self.move(self.home)
            self._timer.stop()
            self.update()
            self.settled.emit(self.pos())
            return
        self.update()

    def _sync_bounds(self) -> None:
        if self._area is None:
            self._motion.set_bounds()
            return
        self._motion.set_bounds(
            self._area.left(),
            self._area.top(),
            max(self._area.left(), self._area.right() - self.width()),
            max(self._area.top(), self._area.bottom() - self.height()),
        )

    def _clamp_into_area(self) -> None:
        area = self._area
        if area is None:
            return
        x = _clamp(self.x(), area.left(), max(area.left(), area.right() - self.width()))
        y = _clamp(self.y(), area.top(), max(area.top(), area.bottom() - self.height()))
        if x != self.x() or y != self.y():
            self.move(round(x), round(y))

    # ------------------------------------------------------------- Qt events

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(CARD_WIDTH + 2 * CARD_MARGIN, CARD_HEIGHT + 2 * CARD_MARGIN)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._last_tick = self._clock()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._timer.stop()
        self._dragging = False
        super().hideEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        hit = self.hit_test(event.position())
        if hit is SurfaceHit.CLOSE and event.button() == Qt.MouseButton.LeftButton:
            self.close_requested.emit()
            event.accept()
            return
        if hit is SurfaceHit.HANDLE and event.button() == Qt.MouseButton.LeftButton:
            self.begin_drag(QPointF(self.mapToParent(event.position().toPoint())))
            event.accept()
            return
        self._press_body = hit is SurfaceHit.BODY and event.button() == Qt.MouseButton.LeftButton
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self.update_drag(QPointF(self.mapToParent(event.position().toPoint())))
            event.accept()
            return
        hit = self.hit_test(event.position())
        hover = hit is SurfaceHit.CLOSE
        if hover != self._hover_close:
            self._hover_close = hover
            self.update()
        self.setCursor(
            Qt.CursorShape.OpenHandCursor
            if hit is SurfaceHit.HANDLE
            else Qt.CursorShape.PointingHandCursor
            if hover
            else Qt.CursorShape.ArrowCursor
        )
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self.end_drag()
            event.accept()
            return
        if self._press_body and event.button() == Qt.MouseButton.LeftButton:
            self._press_body = False
            if self.hit_test(event.position()) is SurfaceHit.BODY:
                self.opened.emit()
            event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.opened.emit()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # ----------------------------------------------------------------- paint

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        surface = self.surface_rect()
        if self._trail:
            self._paint_trail(painter)
        center = surface.center()
        painter.save()
        painter.translate(center)
        painter.rotate(self._tilt)
        painter.translate(-center)
        paint_shadow(painter, surface)
        paint_card_surface(painter, surface, self._theme, alpha=0.22, accent=self._dragging)
        paint_handle(painter, surface, self._theme)
        paint_close(painter, surface, self._theme, hover=self._hover_close or self.hasFocus())
        self._paint_chip(painter, surface)
        self._paint_text(painter, surface)
        painter.restore()
        painter.end()

    def _paint_trail(self, painter: QPainter) -> None:
        origin = QPointF(self.pos())
        points = [QPointF(p.x() - origin.x(), p.y() - origin.y()) for p in self._trail]
        if len(points) < 2:
            return
        points.append(QPointF(CARD_MARGIN, CARD_MARGIN))
        pen = QPen(with_alpha(self._theme.palette.teal, 0.42), 1.2, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(QPolygonF(points))

    def _paint_chip(self, painter: QPainter, surface: QRectF) -> None:
        pal = self._theme.palette
        font = mono_font(FONT.label, spacing=1.5)
        painter.setFont(font)
        label = caps(self._chip)
        width = painter.fontMetrics().horizontalAdvance(label) + 18
        rect = QRectF(surface.left() + METRICS.card_padding, surface.top() + 20, width, 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(pal.teal, 0.18))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setPen(with_alpha(pal.teal, 0.95))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _paint_text(self, painter: QPainter, surface: QRectF) -> None:
        pal = self._theme.palette
        left = surface.left() + METRICS.card_padding
        width = surface.width() - 2 * METRICS.card_padding - CLOSE_TARGET
        title = QRectF(left, surface.top() + 48, width, 26)
        painter.setFont(sans_font(FONT.small, bold=True))
        painter.setPen(pal.text)
        painter.drawText(
            title, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._title
        )
        body = QRectF(left, surface.top() + 80, surface.width() - 2 * METRICS.card_padding, 92)
        painter.setFont(sans_font(FONT.label))
        painter.setPen(pal.muted)
        flags = int(Qt.AlignmentFlag.AlignLeft) | int(Qt.AlignmentFlag.AlignTop)
        flags |= int(Qt.TextFlag.TextWordWrap)
        painter.drawText(body, flags, self._text)

    def _update_accessible(self) -> None:
        self.setAccessibleDescription(f"{caps(self._chip)}. {self._text}")


class Panel(QWidget):
    """Panel kaca dengan pegangan geser, judul, chip, tombol tutup, dan isi."""

    #: Tombol tutup ditekan.
    close_requested = Signal()
    #: Mulai seret panel (payload: posisi di koordinat induk).
    drag_started = Signal(QPoint)
    #: Panel bergerak saat diseret.
    drag_moved = Signal(QPoint)
    #: Seret selesai.
    drag_ended = Signal(QPoint)

    HEADER_TOP: Final = 60

    def __init__(
        self,
        title: str = "",
        *,
        chips: Sequence[str] = (),
        theme: Theme | None = None,
        alpha: float = 0.22,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self._alpha = alpha
        self._title = title
        self._chips = tuple(chips)
        self._dragging = False
        self._drag_offset = QPointF()
        self._area: QRectF | None = None
        self._hover_close = False

        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("Panel kaca")

        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(20, self.HEADER_TOP, 20, 20)
        self._box.setSpacing(12)
        self._box.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._header = QWidget(self)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        self._title_label = QLabel(caps(title), self._header)
        self._title_label.setFont(sans_font(FONT.small, bold=True))
        self._title_label.setStyleSheet(f"color: {self._theme.palette.text.name()};")
        header_layout.addWidget(self._title_label)
        self._chip_host = QWidget(self._header)
        self._chip_layout = QHBoxLayout(self._chip_host)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(6)
        header_layout.addWidget(self._chip_host)
        header_layout.addStretch(1)
        header_layout.addSpacing(int(CLOSE_TARGET) + 4)
        self._box.addWidget(self._header)

        self._close = QPushButton(self)
        self._close.setFlat(True)
        self._close.setFixedSize(int(CLOSE_TARGET), int(CLOSE_TARGET))
        self._close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._close.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover, QPushButton:focus { background: transparent; border: none; }"
        )
        self._close.setAccessibleName("Tutup panel")
        self._close.setAccessibleDescription("Tutup panel ini")
        self._close.setToolTip("Tutup (Esc)")
        self._close.installEventFilter(self)
        self._close.clicked.connect(self.close_requested.emit)
        self._set_chips(self._chips)

    # ------------------------------------------------------------------ state

    @property
    def title(self) -> str:
        """Judul panel."""
        return self._title

    @property
    def chips(self) -> tuple[str, ...]:
        """Label chip di header."""
        return self._chips

    @property
    def is_dragging(self) -> bool:
        """True saat panel diseret."""
        return self._dragging

    def body(self) -> QVBoxLayout:
        """Layout isi; tambahkan widget ke sini."""
        return self._box

    def set_title(self, title: str) -> None:
        """Ganti judul."""
        self._title = title
        self._title_label.setText(caps(title))
        self.setAccessibleName(f"Panel {title}" if title else "Panel kaca")

    def set_chips(self, chips: Sequence[str]) -> None:
        """Ganti chip header."""
        self._chips = tuple(chips)
        self._set_chips(self._chips)

    def set_bounds(self, area: QRectF | None) -> None:
        """Batasi gerak panel ke ``area`` induk."""
        self._area = QRectF(area) if area is not None else None
        self._clamp_into_area()

    def set_theme(self, theme: Theme) -> None:
        """Ganti tema dan segarkan label/chip panel."""
        self._theme = theme
        self._title_label.setStyleSheet(f"color: {theme.palette.text.name()};")
        for chip in self._chip_host.findChildren(_Chip):
            chip.set_theme(theme)
        self.update()

    def _set_chips(self, chips: Sequence[str]) -> None:
        while self._chip_layout.count():
            item = self._chip_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, chip in enumerate(chips):
            self._chip_layout.addWidget(_Chip(chip, self._theme, color_index=index))

    # -------------------------------------------------------------- geometri

    def handle_rect(self) -> QRectF:
        """Pegangan geser 48x4 dalam koordinat panel."""
        return handle_rect(QRectF(self.rect()))

    def close_rect(self) -> QRectF:
        """Target tombol tutup 44x44 dalam koordinat panel."""
        return close_rect(QRectF(self.rect()))

    def hit_test(self, local: QPointF) -> SurfaceHit:
        """Bagian mana dari panel yang berada di ``local``."""
        if self.close_rect().contains(local):
            return SurfaceHit.CLOSE
        if self.handle_rect().adjusted(-8, -8, 8, 8).contains(local):
            return SurfaceHit.HANDLE
        return SurfaceHit.BODY

    # ------------------------------------------------------------------ drag

    def begin_drag(self, point: QPointF) -> bool:
        """Mulai seret panel; ``point`` di koordinat induk."""
        if self._dragging:
            return False
        self._dragging = True
        self._drag_offset = point - QPointF(self.pos())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.drag_started.emit(self.pos())
        return True

    def update_drag(self, point: QPointF) -> None:
        """Gerakkan panel mengikuti ``point``."""
        if not self._dragging:
            return
        target = point - self._drag_offset
        self.move(round(target.x()), round(target.y()))
        self._clamp_into_area()
        self.drag_moved.emit(self.pos())

    def end_drag(self) -> None:
        """Akhiri seret; panel tinggal di tempat."""
        if not self._dragging:
            return
        self._dragging = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.drag_ended.emit(self.pos())

    def _clamp_into_area(self) -> None:
        area = self._area
        if area is None:
            return
        x = _clamp(self.x(), area.left(), max(area.left(), area.right() - self.width()))
        y = _clamp(self.y(), area.top(), max(area.top(), area.bottom() - self.height()))
        if x != self.x() or y != self.y():
            self.move(round(x), round(y))

    # ------------------------------------------------------------- Qt events

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        area = self.close_rect()
        self._close.move(round(area.left()), round(area.top()))
        self._clamp_into_area()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self.hit_test(event.position()) is SurfaceHit.HANDLE
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.begin_drag(QPointF(self.mapToParent(event.position().toPoint())))
            event.accept()
            return
        event.ignore()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self.update_drag(QPointF(self.mapToParent(event.position().toPoint())))
            event.accept()
            return
        hit = self.hit_test(event.position())
        self.setCursor(
            Qt.CursorShape.OpenHandCursor
            if hit is SurfaceHit.HANDLE
            else Qt.CursorShape.ArrowCursor
        )
        event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            self.end_drag()
            event.accept()
            return
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._close:
            kind = event.type()
            if kind in (QEvent.Type.Enter, QEvent.Type.FocusIn):
                self._hover_close = True
                self.update()
            elif kind in (QEvent.Type.Leave, QEvent.Type.FocusOut):
                self._hover_close = False
                self.update()
        return super().eventFilter(watched, event)

    # ----------------------------------------------------------------- paint

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        surface = QRectF(self.rect())
        paint_card_surface(
            painter, surface, self._theme, alpha=self._alpha, radius=METRICS.panel_radius
        )
        paint_handle(painter, surface, self._theme)
        paint_close(painter, surface, self._theme, hover=self._hover_close)
        painter.end()


class _Chip(QWidget):
    """Chip kecil mono kapital (DRAF, LOKAL, AKAR AMAN)."""

    def __init__(
        self,
        text: str,
        theme: Theme,
        *,
        color_index: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = caps(text)
        self._theme = theme
        self._color_index = color_index
        pal = theme.palette
        self._color = pal.teal if color_index == 0 else pal.listening
        font = mono_font(FONT.label, spacing=1.5)
        self.setFont(font)
        width = QFontMetrics(font).horizontalAdvance(self._text) + 18
        self.setFixedSize(width, 18)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAccessibleName(self._text)

    def set_theme(self, theme: Theme) -> None:
        """Ganti tema chip."""
        self._theme = theme
        pal = theme.palette
        self._color = pal.teal if self._color_index == 0 else pal.listening
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(with_alpha(self._color, 0.18))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setFont(self.font())
        painter.setPen(with_alpha(self._color, 0.95))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()
