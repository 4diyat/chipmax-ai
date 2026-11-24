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
    "idle_dot_hit_rect",
    "idle_dot_rect",
    "paint_card_surface",
    "paint_close",
    "paint_handle",
    "paint_idle_dot",
    "paint_shadow",
]

HANDLE_SIZE = QSizeF(float(METRICS.handle_width), float(METRICS.handle_height))
CLOSE_TARGET = 44.0
#: Jarak titik idle dari tepi bawah layar (mockup: "titik 16 px").
IDLE_DOT_MARGIN = 18.0


def paint_shadow(painter: QPainter, rect: QRectF, *, radius: float = 20.0) -> None:
    """Bayangan lembut di bawah kartu."""
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 100))
    painter.drawRoundedRect(rect.adjusted(5, 9, -5, 9), radius, radius)


def idle_dot_rect(area: QRectF) -> QRectF:
    """Kotak 16x16 di tengah bawah layar untuk titik idle."""
    size = float(METRICS.idle_dot)
    return QRectF(area.center().x() - size / 2, area.bottom() - IDLE_DOT_MARGIN - size, size, size)


def paint_idle_dot(painter: QPainter, area: QRectF, theme: Theme, *, hover: bool = False) -> None:
    """Titik teal 16 px: satu-satunya penanda chrome saat disembunyikan.

    Target ketuknya tetap 44 px lewat :func:`idle_dot_hit_rect`, tetapi yang
    terlihat hanya inti 16 px agar tidak mengganggu layar.
    """
    rect = idle_dot_rect(area)
    color = theme.palette.accent if hover else theme.palette.teal
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    halo = QRectF(rect).adjusted(-6, -6, 6, 6)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(with_alpha(color, 0.10))
    painter.drawEllipse(halo)
    painter.setPen(QPen(with_alpha(color, 0.85), 1.2))
    painter.setBrush(with_alpha(color, 0.55 if hover else 0.35))
    painter.drawEllipse(rect.adjusted(1, 1, -1, -1))
    painter.restore()


def idle_dot_hit_rect(area: QRectF) -> QRectF:
    """Area sentuh 44x44 di sekitar titik idle."""
    center = idle_dot_rect(area).center()
    half = 22.0
    return QRectF(center.x() - half, center.y() - half, half * 2, half * 2)


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
