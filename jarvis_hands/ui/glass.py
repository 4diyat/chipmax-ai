"""Chrome kaca bersama: pegangan geser, tombol tutup, dan permukaan kartu.

Dipakai Card, Panel, dan TreePane supaya ukuran target serta bahasa visualnya
satu: pegangan 48x4, tombol tutup dengan target sentuh 44 px, kaca 18-30%.
"""

from __future__ import annotations

from enum import StrEnum, unique

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from jarvis_hands.ui.tokens import METRICS, Theme, paint_glass, with_alpha

__all__ = [
    "CLOSE_TARGET",
    "HANDLE_SIZE",
    "SurfaceHit",
    "close_rect",
    "handle_rect",
    "paint_card_surface",
    "paint_close",
    "paint_handle",
    "paint_shadow",
]

HANDLE_SIZE = QSizeF(float(METRICS.handle_width), float(METRICS.handle_height))
CLOSE_TARGET = 44.0


@unique
class SurfaceHit(StrEnum):
    """Bagian permukaan kaca yang kena ketukan."""

    NONE = "none"
    BODY = "body"
    HANDLE = "handle"
    CLOSE = "close"


def handle_rect(rect: QRectF) -> QRectF:
    """Area pegangan geser (48x4) di tengah atas permukaan."""
    return QRectF(
        rect.center().x() - HANDLE_SIZE.width() / 2,
        rect.top() + 8,
        HANDLE_SIZE.width(),
        HANDLE_SIZE.height(),
    )


def close_rect(rect: QRectF) -> QRectF:
    """Area target tombol tutup 44x44 di kanan atas."""
    return QRectF(rect.right() - CLOSE_TARGET - 10, rect.top() + 8, CLOSE_TARGET, CLOSE_TARGET)


def paint_handle(painter: QPainter, rect: QRectF, theme: Theme) -> None:
    """Gambar pegangan geser."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(with_alpha(theme.palette.muted, 0.55))
    painter.drawRoundedRect(handle_rect(rect), 2, 2)


def paint_close(painter: QPainter, rect: QRectF, theme: Theme, *, hover: bool = False) -> None:
    """Gambar tombol tutup + cincin target 44 px."""
    area = close_rect(rect)
    center = area.center()
    painter.setPen(QPen(with_alpha(theme.palette.teal, 0.12), 1.0, Qt.PenStyle.DashLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(center, CLOSE_TARGET / 2, CLOSE_TARGET / 2)
    painter.setPen(QPen(with_alpha(theme.palette.accent, 0.90 if hover else 0.55), 1.2))
    painter.setBrush(with_alpha(theme.palette.teal, 0.22 if hover else 0.10))
    painter.drawEllipse(center, 15.0, 15.0)
    painter.setPen(QPen(theme.palette.text, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    k = 5.5
    painter.drawLine(
        QPointF(center.x() - k, center.y() - k), QPointF(center.x() + k, center.y() + k)
    )
    painter.drawLine(
        QPointF(center.x() + k, center.y() - k), QPointF(center.x() - k, center.y() + k)
    )


def paint_card_surface(
    painter: QPainter,
    rect: QRectF,
    theme: Theme,
    *,
    alpha: float = 0.22,
    radius: float = 20.0,
    accent: bool = False,
) -> None:
    """Permukaan kaca kartu/panel dengan tepi opsional."""
    paint_glass(
        painter,
        rect,
        theme,
        alpha=alpha,
        border=with_alpha(theme.palette.accent, 0.75) if accent else None,
        radius=radius,
    )


def paint_shadow(painter: QPainter, rect: QRectF, *, radius: float = 20.0) -> None:
    """Bayangan lembut di bawah kartu."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 100))
    painter.drawRoundedRect(rect.adjusted(5, 9, -5, 9), radius, radius)
