"""Kursor gestur 28 px: cincin yang mengisi dan mengecil saat cubit.

Widget ini jendela kecil tembus klik yang tidak pernah mengambil fokus.
Posisinya diatur oleh :class:`CursorPresenter` dari sampel
:class:`jarvis_hands.vision.cursor.CursorSample`.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QHideEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from jarvis_hands.core.config import CursorConfig, GestureThresholds
from jarvis_hands.ui.tokens import METRICS, Theme, build_theme, with_alpha
from jarvis_hands.vision.cursor import CursorSample, CursorTracker
from jarvis_hands.vision.tracker import TrackingResult

__all__ = ["CursorPresenter", "CursorWidget"]


class CursorWidget(QWidget):
    """Cincin kursor 28 px dengan isian cubit dan cincin dwell."""

    #: Kursor berpindah (payload: :class:`PySide6.QtCore.QPoint` di koordinat layar).
    moved = Signal(QPoint)

    def __init__(
        self,
        theme: Theme | None = None,
        *,
        size: int = METRICS.cursor_size,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self._size = max(8, int(size))
        self._pinch = 0.0
        self._pinching = False
        self._dwell = 0.0
        self._hand_visible = False
        self._center = QPoint(0, 0)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(self._size, self._size)
        self.setAccessibleName("Kursor gestur")
        self.setAccessibleDescription("Cincin 28 piksel; mengisi saat mencubit.")
        palette = self._theme.palette
        self._ring = with_alpha(palette.accent, 0.92)
        self._ring_dim = with_alpha(palette.muted, 0.35)
        self._fill = with_alpha(palette.teal, 0.85)
        self._dwell_color = with_alpha(palette.hot_rim, 0.95)

    # ------------------------------------------------------------------ state

    @property
    def size_px(self) -> int:
        """Ukuran sisi widget (28 px bawaan)."""
        return self._size

    @property
    def pinch(self) -> float:
        """Isian cubit 0..1."""
        return self._pinch

    @property
    def pinching(self) -> bool:
        """Status cubit."""
        return self._pinching

    @property
    def dwell(self) -> float:
        """Kemajuan dwell 0..1 (diisi mesin gestur)."""
        return self._dwell

    @property
    def center(self) -> QPoint:
        """Titik tengah kursor di koordinat layar."""
        return self._center

    def set_pinch(self, amount: float, pinching: bool | None = None) -> None:
        """Atur isian cubit; ``pinching`` None berarti pertahankan status."""
        clamped = min(1.0, max(0.0, float(amount)))
        next_pinching = self._pinching if pinching is None else bool(pinching)
        if abs(clamped - self._pinch) < 0.001 and next_pinching == self._pinching:
            return
        self._pinch = clamped
        self._pinching = next_pinching
        self.update()

    def set_dwell(self, progress: float) -> None:
        """Atur kemajuan dwell 0..1."""
        clamped = min(1.0, max(0.0, float(progress)))
        if abs(clamped - self._dwell) < 0.001:
            return
        self._dwell = clamped
        self.update()

    def set_hand_visible(self, visible: bool) -> None:
        """Tampilkan redup bila tangan hilang dari kamera."""
        visible = bool(visible)
        if visible == self._hand_visible:
            return
        self._hand_visible = visible
        self.update()

    def move_to(self, point: QPoint) -> None:
        """Pindahkan kursor sehingga titik tengah berada di ``point``."""
        self._center = QPoint(point)
        half = self._size // 2
        self.move(point.x() - half, point.y() - half)
        self.moved.emit(self._center)

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event: QPaintEvent | None) -> None:  # noqa: N802
        """Gambar cincin, isian cubit, dan arc dwell."""
        del event
        center = QRectF(0.0, 0.0, float(self._size), float(self._size)).center()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        pinch = self._pinch if self._hand_visible else 0.0
        if pinch > 0.001:
            radius = 3.0 + 6.0 * pinch
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._fill)
            painter.drawEllipse(center, radius, radius)

        outer = 13.5 - 1.5 * pinch
        pen = QPen(self._ring if self._hand_visible else self._ring_dim, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, outer, outer)

        if self._dwell > 0.001:
            span = 360.0 * self._dwell
            dwell_pen = QPen(self._dwell_color, 2.5)
            dwell_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(dwell_pen)
            rect = QRectF(
                center.x() - 11.5,
                center.y() - 11.5,
                23.0,
                23.0,
            )
            painter.drawArc(rect, -90 * 16, int(-span * 16))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._ring if self._hand_visible else self._ring_dim)
        painter.drawEllipse(center, 2.0, 2.0)
        painter.end()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        """Reset isian saat disembunyikan."""
        del event
        self._pinch = 0.0
        self._dwell = 0.0


class CursorPresenter(QObject):
    """Terhubung ke kamera: landmark -> sampel kursor -> widget."""

    #: Sampel kursor terbaru (payload: :class:`CursorSample`).
    sample_ready = Signal(object)
    #: Status cubit berubah.
    pinch_changed = Signal(bool)
    #: Tangan terlihat/hilang.
    visibility_changed = Signal(bool)
    #: Kursor berpindah (payload: :class:`QPoint`).
    moved = Signal(QPoint)

    def __init__(
        self,
        tracker: CursorTracker | None = None,
        *,
        config: CursorConfig | None = None,
        thresholds: GestureThresholds | None = None,
        widget: CursorWidget | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._tracker = tracker or CursorTracker(
            cursor_config=config,
            thresholds=thresholds,
        )
        self._widget = widget
        self._visible = False
        self._pinching = False
        self._last: CursorSample | None = None

    @property
    def tracker(self) -> CursorTracker:
        """Tracker kursor."""
        return self._tracker

    @property
    def widget(self) -> CursorWidget | None:
        """Widget yang digerakkan (bila ada)."""
        return self._widget

    @property
    def last_sample(self) -> CursorSample | None:
        """Sampel terakhir."""
        return self._last

    @property
    def hand_visible(self) -> bool:
        """True bila tangan terlihat pada frame terakhir."""
        return self._visible

    def set_screen(self, width: int, height: int, origin_x: int = 0, origin_y: int = 0) -> None:
        """Teruskan ukuran layar ke tracker."""
        self._tracker.set_screen(width, height, origin_x=origin_x, origin_y=origin_y)

    def set_dwell(self, progress: float) -> None:
        """Atur arc dwell pada widget (dipakai mesin gestur)."""
        if self._widget is not None:
            self._widget.set_dwell(progress)

    def process(self, result: TrackingResult) -> CursorSample:
        """Hitung sampel dan perbarui widget. Dipanggil dari signal kamera."""
        sample = self._tracker.update(result)
        self._last = sample
        if sample.visible != self._visible:
            self._visible = sample.visible
            self.visibility_changed.emit(sample.visible)
        if self._widget is not None:
            self._widget.set_hand_visible(sample.visible)
            self._widget.set_pinch(sample.pinch, sample.pinching)
            self._widget.move_to(QPoint(sample.x, sample.y))
        pinching = bool(sample.visible and sample.pinching)
        if pinching != self._pinching:
            self._pinching = pinching
            self.pinch_changed.emit(pinching)
        self.sample_ready.emit(sample)
        self.moved.emit(QPoint(sample.x, sample.y))
        return sample

    def reset(self) -> None:
        """Hapus status saat kamera mati."""
        self._tracker.reset()
        self._last = None
        self._visible = False
        if self._pinching:
            self._pinching = False
            self.pinch_changed.emit(False)
        self.visibility_changed.emit(False)
        if self._widget is not None:
            self._widget.set_hand_visible(False)
            self._widget.set_pinch(0.0, False)
            self._widget.set_dwell(0.0)
