"""Ikon garis Glass Stage: digambar langsung dengan ``QPainter``.

Mockup memakai ikon garis tipis (gear, monitor, kamera, tangan, gembok, mata)
pada label mono. Tidak ada aset raster atau font ikon yang dibundel, jadi ikon
digambar pada grid desain 24x24 lalu diskalakan ke ukuran widget. Warna selalu
berasal dari :class:`jarvis_hands.ui.tokens.Theme`.
"""

from __future__ import annotations

import math
from enum import StrEnum, unique

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from jarvis_hands.ui.tokens import Theme, with_alpha

__all__ = ["GRID", "IconGlyph", "IconKind", "icon_icon", "icon_pixmap", "paint_icon"]

#: Grid desain ikon (piksel).
GRID = 24.0


@unique
class IconKind(StrEnum):
    """Ikon yang dipakai antarmuka."""

    GEAR = "gear"
    DISPLAY = "display"
    CAMERA = "camera"
    HAND = "hand"
    LOCK = "lock"
    EYE = "eye"
    EYE_OFF = "eye-off"
    TRASH = "trash"
    CLOSE = "close"
    BLOOM = "bloom"


def paint_icon(
    painter: QPainter,
    rect: QRectF,
    kind: IconKind,
    color: QColor,
    *,
    width: float = 1.4,
) -> None:
    """Gambar ``kind`` memenuhi ``rect`` (grid 24x24 diskalakan)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scale = min(rect.width(), rect.height()) / GRID
    painter.translate(rect.center())
    painter.scale(scale, scale)
    painter.translate(-GRID / 2.0, -GRID / 2.0)
    pen = QPen(color, width / max(scale, 1e-6))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    _DRAW[kind](painter, color)
    painter.restore()


def icon_pixmap(
    kind: IconKind,
    color: QColor,
    *,
    size: int = 20,
    ratio: float = 1.0,
) -> QPixmap:
    """Render ikon ke ``QPixmap`` (untuk ``QIcon`` tombol)."""
    px = max(1, round(size * ratio))
    pixmap = QPixmap(px, px)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    paint_icon(painter, QRectF(0, 0, px, px), kind, color, width=1.4 * ratio)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def icon_icon(kind: IconKind, color: QColor, *, size: int = 20) -> QIcon:
    """``QIcon`` dari ikon garis; ukuran mengikuti ``size``."""
    return QIcon(icon_pixmap(kind, color, size=size))


class IconGlyph(QWidget):
    """Widget kecil yang hanya menggambar satu ikon."""

    def __init__(
        self,
        kind: IconKind,
        theme: Theme,
        *,
        size: int = 20,
        color: QColor | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._theme = theme
        self._color = color
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.width(), self.height())

    def set_theme(self, theme: Theme) -> None:
        """Ganti tema ikon."""
        self._theme = theme
        self.update()

    def set_color(self, color: QColor | None) -> None:
        """Paksa warna (``None`` = warna aksen tema)."""
        self._color = color
        self.update()

    def paintEvent(self, event: object) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        color = self._color or with_alpha(self._theme.palette.accent, 0.92)
        paint_icon(painter, QRectF(self.rect()), self._kind, color)
        painter.end()


# ---------------------------------------------------------------- bentuk ikon


def _gear(painter: QPainter, color: QColor) -> None:
    center = QPointF(12, 12)
    painter.drawEllipse(center, 3.6, 3.6)
    painter.drawEllipse(center, 1.2, 1.2)
    for index in range(8):
        angle = math.radians(index * 45.0)
        inner = QPointF(12 + math.cos(angle) * 6.2, 12 + math.sin(angle) * 6.2)
        outer = QPointF(12 + math.cos(angle) * 8.6, 12 + math.sin(angle) * 8.6)
        painter.drawLine(inner, outer)


def _display(painter: QPainter, color: QColor) -> None:
    painter.drawRoundedRect(QRectF(2.5, 4.5, 19, 12.5), 2, 2)
    painter.drawLine(QPointF(12, 17), QPointF(12, 20.5))
    painter.drawLine(QPointF(8, 20.5), QPointF(16, 20.5))


def _camera(painter: QPainter, color: QColor) -> None:
    path = QPainterPath()
    path.moveTo(3.5, 7.5)
    path.lineTo(8.0, 7.5)
    path.lineTo(9.8, 4.8)
    path.lineTo(14.2, 4.8)
    path.lineTo(16.0, 7.5)
    path.lineTo(20.5, 7.5)
    path.lineTo(20.5, 19.0)
    path.lineTo(3.5, 19.0)
    path.closeSubpath()
    painter.drawPath(path)
    painter.drawEllipse(QPointF(12, 13.2), 3.4, 3.4)


def _hand(painter: QPainter, color: QColor) -> None:
    palm = QPainterPath()
    palm.addRoundedRect(QRectF(7.5, 10.0, 9.0, 10.0), 2.4, 2.4)
    painter.drawPath(palm)
    for x, top in ((8.6, 5.6), (11.0, 3.6), (13.4, 4.0), (15.8, 6.2)):
        painter.drawLine(QPointF(x, 10.0), QPointF(x, top))
    thumb = QPainterPath()
    thumb.moveTo(7.5, 12.4)
    thumb.lineTo(5.2, 10.6)
    thumb.lineTo(4.0, 7.6)
    painter.drawPath(thumb)


def _lock(painter: QPainter, color: QColor) -> None:
    painter.drawRoundedRect(QRectF(5.0, 10.6, 14.0, 9.4), 2.4, 2.4)
    shackle = QRectF(8.2, 4.6, 7.6, 10.0)
    painter.drawArc(shackle, 0 * 16, 180 * 16)
    painter.setBrush(color)
    painter.drawEllipse(QPointF(12, 15.0), 1.3, 1.3)


def _eye(painter: QPainter, color: QColor) -> None:
    shape = QPainterPath()
    shape.moveTo(2.5, 12.0)
    shape.quadTo(12.0, 3.6, 21.5, 12.0)
    shape.quadTo(12.0, 20.4, 2.5, 12.0)
    painter.drawPath(shape)
    painter.drawEllipse(QPointF(12, 12), 2.9, 2.9)


def _eye_off(painter: QPainter, color: QColor) -> None:
    _eye(painter, color)
    painter.drawLine(QPointF(4.0, 3.5), QPointF(20.0, 20.5))


def _trash(painter: QPainter, color: QColor) -> None:
    painter.drawLine(QPointF(3.6, 6.4), QPointF(20.4, 6.4))
    painter.drawLine(QPointF(9.4, 6.4), QPointF(9.4, 4.2))
    painter.drawLine(QPointF(9.4, 4.2), QPointF(14.6, 4.2))
    painter.drawLine(QPointF(14.6, 4.2), QPointF(14.6, 6.4))
    body = QPainterPath()
    body.moveTo(5.6, 6.4)
    body.lineTo(6.6, 20.2)
    body.lineTo(17.4, 20.2)
    body.lineTo(18.4, 6.4)
    painter.drawPath(body)
    painter.drawLine(QPointF(10.2, 9.8), QPointF(10.6, 17.0))
    painter.drawLine(QPointF(13.8, 9.8), QPointF(13.4, 17.0))


def _close(painter: QPainter, color: QColor) -> None:
    painter.drawLine(QPointF(6.4, 6.4), QPointF(17.6, 17.6))
    painter.drawLine(QPointF(17.6, 6.4), QPointF(6.4, 17.6))


def _bloom(painter: QPainter, color: QColor) -> None:
    """Lima mekar Orb pada lambang JARVIS di kanan atas dialog."""
    painter.drawEllipse(QPointF(12, 12), 3.0, 3.0)
    for index in range(5):
        angle = math.radians(-90.0 + index * 72.0)
        center = QPointF(12 + math.cos(angle) * 6.6, 12 + math.sin(angle) * 6.6)
        painter.save()
        painter.translate(center)
        painter.rotate(index * 72.0)
        painter.drawEllipse(QPointF(0, 0), 2.1, 3.2)
        painter.restore()


_DRAW = {
    IconKind.GEAR: _gear,
    IconKind.DISPLAY: _display,
    IconKind.CAMERA: _camera,
    IconKind.HAND: _hand,
    IconKind.LOCK: _lock,
    IconKind.EYE: _eye,
    IconKind.EYE_OFF: _eye_off,
    IconKind.TRASH: _trash,
    IconKind.CLOSE: _close,
    IconKind.BLOOM: _bloom,
}
