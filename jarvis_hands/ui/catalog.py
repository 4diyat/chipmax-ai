"""Katalog komponen Glass Stage (halaman uji Fase 0-2).

Halaman ini menampilkan seluruh bahasa visual: token warna, tipografi, kaca,
kontrol, status, kursor, indikator kamera, toast, dan petunjuk. Komponen yang
belum dibangun (Orb, Overlay, ...) muncul sebagai kartu terjadwal bertanda fase,
bukan sebagai tiruan yang menyesatkan.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from jarvis_hands.core.config import AppConfig
from jarvis_hands.core.state import Status
from jarvis_hands.ui.camera import CameraIndicator, CameraState
from jarvis_hands.ui.ring import RingWidget
from jarvis_hands.ui.tokens import (
    FONT,
    METRICS,
    MONO_CANDIDATES,
    SANS_CANDIDATES,
    TOKENS,
    Theme,
    TokenSpec,
    build_theme,
    caps,
    mono_font,
    paint_glass,
    paint_stage,
    resolve_family,
    sans_font,
    status_color,
)

__all__ = ["COMPONENTS", "CatalogWindow", "ComponentSpec", "Theme"]


@dataclass(frozen=True)
class ComponentSpec:
    """Satu komponen terdaftar. ``factory`` kosong berarti belum dibangun."""

    key: str
    title: str
    phase: int
    note: str
    factory: Callable[[Theme], QWidget] | None = None
    ready: bool = False


def _make_glass(theme: Theme) -> QWidget:
    return GlassFrame(theme=theme, minimum_height=84)


def _make_button(theme: Theme) -> QWidget:
    return GlassButton("PILIH", theme)


def _make_status_chip(theme: Theme) -> QWidget:
    return StatusChip(Status.LISTENING, theme)


def _make_toast(theme: Theme) -> QWidget:
    return ToastPreview(theme)


def _make_hint_bar(theme: Theme) -> QWidget:
    return HintBar(theme)


COMPONENTS: Final[tuple[ComponentSpec, ...]] = (
    ComponentSpec(
        "glass", "GlassFrame", 0, "Permukaan kaca, gradien tembus, tepi 1.5 px", _make_glass
    ),
    ComponentSpec(
        "button", "GlassButton", 0, "Tombol kaca, fokus keyboard, target >= 44 px", _make_button
    ),
    ComponentSpec(
        "status_chip", "StatusChip", 0, "Pil status dengan titik warna", _make_status_chip
    ),
    ComponentSpec("toast", "Toast", 0, "Notifikasi kecil kanan atas", _make_toast),
    ComponentSpec("hint_bar", "HintBar", 0, "Baris petunjuk gestur di bawah", _make_hint_bar),
    ComponentSpec(
        "ring",
        "RingWidget",
        1,
        "Cincin 440 px, lima status, animasi 60 fps",
        ready=True,
    ),
    ComponentSpec("cursor", "Cursor", 2, "Cincin 28 px, isi cubit, lingkaran dwell", ready=True),
    ComponentSpec(
        "camera_indicator",
        "CameraIndicator",
        2,
        "Titik rekam, selalu terlihat saat kamera aktif",
        ready=True,
    ),
    ComponentSpec("card", "Card", 4, "Kartu kaca dengan bar pegangan dan tombol tutup"),
    ComponentSpec("orb", "Orb", 4, "Orb kaca 112 px, mekar mengelilingi cincin"),
    ComponentSpec("panel", "Panel", 4, "Panel kaca untuk isi dan catatan"),
    ComponentSpec("tree_pane", "TreePane", 4, "Folder memori, baris tebal sebagai target ketuk"),
    ComponentSpec("overlay", "OverlayWindow", 5, "Overlay transparan, tembus klik, multi-monitor"),
    ComponentSpec("settings", "Settings", 7, "Layar pengaturan dan onboarding kamera"),
)


def _rgba(color: QColor, alpha: float) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha:.3f})"


def _alpha(color: QColor, alpha: float) -> QColor:
    out = QColor(color)
    out.setAlphaF(max(0.0, min(1.0, alpha)))
    return out


def _label(
    text: str,
    font: QFont,
    color: QColor,
    *,
    align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft,
    wrap: bool = False,
    name: str = "",
) -> QLabel:
    label = QLabel(text)
    label.setFont(font)
    label.setStyleSheet(f"color: {color.name()};")
    label.setAlignment(align)
    label.setWordWrap(wrap)
    if name:
        label.setObjectName(name)
    return label


def _hairline(theme: Theme, alpha: float = 0.16) -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {_rgba(theme.palette.teal, alpha)};")
    return line


class StagePage(QWidget):
    """Halaman latar panggung; isinya digambar sendiri, bukan QSS."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

    def box(self) -> QVBoxLayout:
        """Layout utama halaman."""
        return self._layout

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        paint_stage(painter, QRectF(self.rect()), self._theme)
        painter.end()


class GlassFrame(QWidget):
    """Permukaan kaca generik dengan layout vertikal siap pakai."""

    def __init__(
        self,
        *,
        theme: Theme,
        alpha: float | None = None,
        border: QColor | None = None,
        radius: float | None = None,
        margins: tuple[int, int, int, int] = (20, 18, 20, 18),
        minimum_height: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._alpha = alpha
        self._border = border
        self._radius = radius
        if minimum_height is not None:
            self.setMinimumHeight(minimum_height)
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(*margins)
        self._box.setSpacing(10)

    def box(self) -> QVBoxLayout:
        """Layout isi frame."""
        return self._box

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(320, 120)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        paint_glass(
            painter,
            QRectF(self.rect()),
            self._theme,
            alpha=self._alpha,
            border=self._border,
            radius=self._radius,
        )
        painter.end()


class ColorChip(QWidget):
    """Kotak warna 44 px; satu-satunya elemen katalog yang bukan kaca."""

    def __init__(self, color: QColor, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._theme = theme
        self.setFixedSize(44, 44)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawRoundedRect(rect, 10, 10)
        pen = QPen(_alpha(self._theme.palette.hot_rim, 0.35), 1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)
        painter.end()


class TokenCard(QWidget):
    """Satu token warna: chip, nama, hex, dan catatan."""

    def __init__(
        self, index: int, spec: TokenSpec, theme: Theme, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"token-{spec.key}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(ColorChip(QColor(spec.hex_code), theme))
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(3)
        name = _label(f"{index:02d}  {caps(spec.name)}", mono_font(FONT.label), theme.palette.teal)
        text.addWidget(name)
        text.addWidget(
            _label(spec.hex_code.upper(), mono_font(FONT.small, spacing=1.2), theme.palette.text)
        )
        text.addWidget(_label(spec.note, sans_font(11), theme.palette.muted, wrap=True))
        layout.addLayout(text, 1)


class SectionHeader(QWidget):
    """Nomor, judul, subjudul, dan garis tipis pemisah."""

    def __init__(self, number: str, title: str, subtitle: str, theme: Theme) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        number_label = _label(number, mono_font(FONT.label), theme.palette.teal)
        number_label.setFixedWidth(30)
        layout.addWidget(number_label)
        title_label = _label(caps(title), sans_font(FONT.title, bold=True), theme.palette.text)
        layout.addWidget(title_label)
        if subtitle:
            layout.addWidget(_label(subtitle, sans_font(FONT.small), theme.palette.muted))
        layout.addStretch(1)
        line = _hairline(theme)
        line.setFixedWidth(160)
        layout.addWidget(line)


class Section(QWidget):
    """Blok konten dengan header dan body vertikal."""

    def __init__(self, number: str, title: str, subtitle: str, theme: Theme) -> None:
        super().__init__()
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(18)
        self._box.addWidget(SectionHeader(number, title, subtitle, theme))

    def body(self) -> QVBoxLayout:
        """Layout isi section."""
        return self._box


class StatusChip(QWidget):
    """Pil status dengan titik warna; dipakai katalog dan nanti panel status."""

    def __init__(self, status: Status, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = status
        self._theme = theme
        self._font = mono_font(FONT.label)
        self.setFont(self._font)
        self.setObjectName(f"status-{status.value}")
        self.setAccessibleName(f"Status {status.label}")
        width = QFontMetrics(self._font).horizontalAdvance(status.label) + 44
        self.setFixedSize(width, 32)

    def status(self) -> Status:
        """Status yang digambarkan."""
        return self._status

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = status_color(self._status, self._theme.palette)
        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        painter.setPen(QPen(_alpha(color, 0.45), 1.5))
        painter.setBrush(_alpha(color, 0.12))
        painter.drawRoundedRect(rect, 16, 16)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPointF(17, self.height() / 2), 3.0, 3.0)
        painter.setFont(self._font)
        painter.setPen(self._theme.palette.text)
        painter.drawText(
            QRectF(28, 0, self.width() - 32, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._status.label,
        )
        painter.end()


class GlassButton(QPushButton):
    """Tombol kaca: tetap QPushButton supaya keyboard dan aksesibilitas jalan."""

    def __init__(
        self,
        text: str,
        theme: Theme,
        *,
        primary: bool = True,
        checkable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._theme = theme
        self._primary = primary
        self.setCheckable(checkable)
        self.setFont(sans_font(13, bold=True))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(132, 44)
        self.setAccessibleName(text)
        self.setAccessibleDescription("Tombol kaca; bisa diaktifkan dengan Space atau Enter")

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(148, 44)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        hovered = self.underMouse()
        down = self.isDown()
        checked = self.isChecked()
        alpha = 0.34 if (down or checked) else (0.30 if hovered else 0.22)
        border: QColor | None
        if checked:
            border = self._theme.palette.hot_rim
        else:
            border = self._theme.palette.accent if self._primary else None
        paint_glass(
            painter,
            QRectF(self.rect()),
            self._theme,
            alpha=alpha,
            border=border,
            radius=12,
        )
        if self.hasFocus():
            pen = QPen(_alpha(self._theme.palette.hot_rim, 0.8), 1.0, Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(3, 3, -3, -3), 9, 9)
        painter.setFont(self.font())
        if self._primary or self.isChecked():
            text_color = self._theme.palette.hot_rim
        else:
            text_color = self._theme.palette.text
        painter.setPen(text_color)
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            self.text(),
        )
        painter.end()


class IconButton(QPushButton):
    """Tombol tutup 32 px dengan glyph x; target sentuh diperbesar ke 44 px."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__("", parent)
        self._theme = theme
        self.setFixedSize(44, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Tutup")
        self.setAccessibleDescription("Tutup kartu atau panel")

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(6, 6, self.width() - 12, self.height() - 12)
        painter.setPen(QPen(_alpha(self._theme.palette.teal, 0.55), 1.5))
        painter.setBrush(_alpha(self._theme.palette.teal, 0.14 if not self.underMouse() else 0.24))
        painter.drawEllipse(rect)
        glyph = QPen(self._theme.palette.text, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(glyph)
        cx, cy, arm = self.width() / 2, self.height() / 2, 5.0
        painter.drawLine(QPointF(cx - arm, cy - arm), QPointF(cx + arm, cy + arm))
        painter.drawLine(QPointF(cx + arm, cy - arm), QPointF(cx - arm, cy + arm))
        painter.end()


class HandleBar(QWidget):
    """Bar pegangan 48 x 4 px: geser untuk memindah kartu/panel."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setFixedSize(METRICS.handle_width, METRICS.handle_height)
        self.setAccessibleName("Pegangan geser")

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_alpha(self._theme.palette.teal, 0.55))
        painter.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 2, 2)
        painter.end()


class Badge(QWidget):
    """Pil label mono kecil (fase, status, tag)."""

    def __init__(self, text: str, theme: Theme, *, color: QColor | None = None) -> None:
        super().__init__()
        self._text = text
        self._theme = theme
        self._color = color or theme.palette.teal
        self._font = mono_font(FONT.label, spacing=2.0)
        self.setFont(self._font)
        self.setFixedSize(QFontMetrics(self._font).horizontalAdvance(text) + 28, 26)

    def text(self) -> str:
        """Teks badge (untuk tes dan aksesibilitas)."""
        return self._text

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        painter.setPen(QPen(_alpha(self._color, 0.5), 1.0))
        painter.setBrush(_alpha(self._color, 0.10))
        painter.drawRoundedRect(rect, 13, 13)
        painter.setFont(self._font)
        painter.setPen(self._color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class CursorPreview(QWidget):
    """Pratinjau kursor 28 px: bebas, cubit, dan dwell terisi."""

    MODE_FREE = "free"
    MODE_PINCH = "pinch"
    MODE_DWELL = "dwell"

    def __init__(self, mode: str, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._theme = theme
        self.setFixedSize(132, 132)
        label = {
            self.MODE_FREE: "Kursor bebas",
            self.MODE_PINCH: "Cubit: terisi dan mengecil",
            self.MODE_DWELL: "Dwell: terisi 65%",
        }[mode]
        self.setAccessibleName(label)
        self.setObjectName(f"cursor-{mode}")

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pal = self._theme.palette
        center = QPointF(self.width() / 2, self.height() / 2)

        # Jejak halus agar posisi kursor terbaca.
        painter.setPen(QPen(_alpha(pal.teal, 0.10), 1.0, Qt.PenStyle.DotLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, 52, 52)

        radius = METRICS.cursor_size / 2
        if self._mode == self.MODE_PINCH:
            radius *= 0.72
            painter.setPen(QPen(_alpha(pal.accent, 0.9), 2.0))
            painter.setBrush(_alpha(pal.accent, 0.32))
            painter.drawEllipse(center, radius, radius)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal.hot_rim)
            painter.drawEllipse(center, 2.5, 2.5)
        elif self._mode == self.MODE_DWELL:
            painter.setPen(QPen(_alpha(pal.teal, 0.55), 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)
            painter.setBrush(_alpha(pal.teal, 0.10))
            painter.drawEllipse(center, radius, radius)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(pal.accent, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(
                QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2),
                90 * 16,
                -int(0.65 * 360 * 16),
            )
        else:
            painter.setPen(QPen(_alpha(pal.band, 0.85), 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pal.hot_rim)
            painter.drawEllipse(center, 2.0, 2.0)
        painter.end()


class ToastPreview(QWidget):
    """Toast kecil kanan atas; teks pendek, dua baris."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setFixedSize(METRICS.toast_width, 64)
        self.setObjectName("toast-preview")
        self.setAccessibleName("Toast: mode gestur aktif")

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        paint_glass(painter, QRectF(self.rect()), self._theme, alpha=0.30, radius=14)
        pal = self._theme.palette
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(pal.teal)
        painter.drawEllipse(QPointF(18, self.height() / 2), 3.5, 3.5)
        painter.setFont(mono_font(FONT.label))
        painter.setPen(pal.text)
        painter.drawText(QPointF(32, 26), "MODE GESTUR AKTIF")
        painter.setFont(sans_font(10))
        painter.setPen(pal.muted)
        painter.drawText(QPointF(32, 44), "Kamera menyala · video tidak disimpan")
        painter.end()


class HintBar(QWidget):
    """Baris petunjuk gestur di bawah; satu baris, mono kecil."""

    TEXT = "CUBIT UNTUK MEMILIH · TAHAN UNTUK MEMUTAR · CTRL+ALT+G JEDA"

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setFixedHeight(METRICS.hint_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setObjectName("hint-bar")
        self.setAccessibleName("Petunjuk gestur")

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        paint_glass(painter, QRectF(self.rect()), self._theme, alpha=0.24, radius=12)
        painter.setFont(mono_font(9, spacing=2.0))
        painter.setPen(self._theme.palette.muted)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.TEXT)
        painter.end()


class PlaceholderCard(GlassFrame):
    """Kartu komponen yang belum dibangun: fase + catatan + glyph."""

    def __init__(self, spec: ComponentSpec, theme: Theme) -> None:
        super().__init__(theme=theme, alpha=0.18, margins=(18, 16, 18, 16), minimum_height=150)
        self._spec = spec
        self.setObjectName(f"component-{spec.key}")
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        top.addWidget(Badge(f"FASE {spec.phase}", theme, color=theme.palette.teal))
        top.addStretch(1)
        ready = spec.ready or spec.factory is not None
        top.addWidget(
            _label(
                "SIAP" if ready else "TERJADWAL",
                mono_font(FONT.label, spacing=1.5),
                theme.palette.accent if ready else theme.palette.muted,
                align=Qt.AlignmentFlag.AlignRight,
            )
        )
        self.box().addLayout(top)
        self.box().addWidget(_label(spec.title, sans_font(15, bold=True), theme.palette.text))
        note = _label(spec.note, sans_font(11), theme.palette.muted, wrap=True)
        note.setFixedHeight(32)
        self.box().addWidget(note)
        self.box().addStretch(1)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._draw_glyph(painter)
        painter.end()

    def _draw_glyph(self, painter: QPainter) -> None:
        pal = self._theme.palette
        area = QRectF(self.width() - 96, self.height() - 86, 76, 60)
        pen = QPen(
            _alpha(pal.teal, 0.55 if self._spec.ready or self._spec.factory else 0.35),
            1.5,
            Qt.PenStyle.SolidLine
            if (self._spec.ready or self._spec.factory)
            else Qt.PenStyle.DashLine,
        )
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        key = self._spec.key
        if key == "ring":
            painter.drawEllipse(area.center(), 26, 26)
            painter.drawEllipse(area.center(), 16, 16)
        elif key in {"orb", "card", "panel", "settings"}:
            painter.drawRoundedRect(area.adjusted(4, 10, -4, -10), 8, 8)
        elif key in {"overlay", "cursor"}:
            painter.drawRoundedRect(area.adjusted(0, 14, -52, -14), 6, 6)
            painter.drawEllipse(area.center() + QPointF(18, 0), 9, 9)
        elif key == "tree_pane":
            for i in range(3):
                y = area.top() + 12 + i * 16
                painter.drawLine(QPointF(area.left() + 10, y), QPointF(area.right() - 10, y))
        elif key == "camera_indicator":
            painter.drawEllipse(area.center(), 10, 10)
            painter.setBrush(_alpha(pal.warning, 0.55))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(area.center(), 4, 4)
        else:
            painter.drawEllipse(area.center(), 20, 20)


class PreviewCard(GlassFrame):
    """Kartu kaca berisi satu pratinjau komponen dan keterangan."""

    def __init__(
        self,
        title: str,
        content: QWidget,
        caption: str,
        theme: Theme,
    ) -> None:
        super().__init__(theme=theme, alpha=0.22, margins=(18, 16, 18, 16), minimum_height=150)
        self.box().addWidget(_label(caps(title), mono_font(FONT.label), theme.palette.teal))
        holder = QHBoxLayout()
        holder.setContentsMargins(0, 4, 0, 4)
        holder.addStretch(1)
        holder.addWidget(content)
        holder.addStretch(1)
        self.box().addLayout(holder)
        self.box().addWidget(_label(caption, sans_font(11), theme.palette.muted, wrap=True))


class TypographyCard(GlassFrame):
    """Contoh huruf: display, isi, dan label mono."""

    def __init__(self, title: str, sample: str, font: QFont, caption: str, theme: Theme) -> None:
        super().__init__(theme=theme, alpha=0.18, margins=(18, 16, 18, 16), minimum_height=132)
        self.box().addWidget(_label(caps(title), mono_font(FONT.label), theme.palette.teal))
        self.box().addWidget(_label(sample, font, theme.palette.text, wrap=True))
        self.box().addStretch(1)
        self.box().addWidget(_label(caption, sans_font(10), theme.palette.muted, wrap=True))


class CatalogWindow(QMainWindow):
    """Jendela katalog Fase 0-2 (halaman pengembang, bukan overlay produk)."""

    def __init__(
        self,
        config: AppConfig | None = None,
        *,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config or AppConfig.default()
        self._theme = (
            theme if theme is not None else build_theme(self._config.display.high_contrast)
        )
        self.setWindowTitle("JARVIS — Katalog Glass Stage")
        self.setMinimumSize(1000, 700)
        self.resize(1280, 900)
        self.setAccessibleName("Katalog komponen JARVIS")

        page = StagePage(self._theme)
        page.setObjectName("catalog-page")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        scroll.viewport().setAutoFillBackground(False)
        self.setCentralWidget(scroll)

        self._build(page)

    @property
    def config(self) -> AppConfig:
        """Konfigurasi yang dipakai katalog."""
        return self._config

    @property
    def theme(self) -> Theme:
        """Tema aktif (normal atau kontras tinggi)."""
        return self._theme

    def _build(self, page: StagePage) -> None:
        content = QWidget()
        content.setMaximumWidth(1120)
        content.setMinimumWidth(820)
        root = page.box()
        root.setContentsMargins(48, 32, 48, 32)
        root.setSpacing(0)
        root.addWidget(content, 1)
        box = QVBoxLayout(content)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(30)

        box.addWidget(self._build_header())
        box.addWidget(
            _label(
                "Halaman uji bahasa visual JARVIS. Semua warna dan ukuran diambil dari token "
                "Glass Stage; kamera tidak aktif dan tidak ada port jaringan.",
                sans_font(13),
                self._theme.palette.muted,
                wrap=True,
            )
        )
        box.addWidget(_hairline(self._theme, 0.12))
        box.addWidget(self._build_tokens())
        box.addWidget(self._build_typography())
        box.addWidget(self._build_glass())
        box.addWidget(self._build_controls())
        box.addWidget(self._build_ring())
        box.addWidget(self._build_status())
        box.addWidget(self._build_cursor())
        box.addWidget(self._build_toasts())
        box.addWidget(self._build_map())
        box.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(4)
        wordmark_font = sans_font(32, bold=True)
        wordmark_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6.0)
        wordmark = _label("J.A.R.V.I.S", wordmark_font, self._theme.palette.text)
        wordmark.setObjectName("wordmark")
        left.addWidget(wordmark)
        left.addWidget(
            _label(
                "RING & HANDS · GLASS STAGE",
                mono_font(FONT.label, spacing=3.0),
                self._theme.palette.teal,
            )
        )
        layout.addLayout(left)
        layout.addStretch(1)
        layout.addWidget(Badge("KATALOG · FASE 0-2", self._theme, color=self._theme.palette.accent))
        return header

    def _build_tokens(self) -> QWidget:
        section = Section("01", "Token warna", "9 warna, satu bahasa", self._theme)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        for index, spec in enumerate(TOKENS):
            row, col = divmod(index, 3)
            grid.addWidget(TokenCard(index + 1, spec, self._theme), row, col)
        for col in range(3):
            grid.setColumnStretch(col, 1)
        section.body().addLayout(grid)
        return section

    def _build_typography(self) -> QWidget:
        section = Section("02", "Tipografi", "Space Grotesk + mono kapital", self._theme)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        row.addWidget(
            TypographyCard(
                "Display",
                "Ring & Hands",
                sans_font(FONT.display, bold=True),
                "Space Grotesk 30 px · judul wordmark",
                self._theme,
            )
        )
        row.addWidget(
            TypographyCard(
                "Isi",
                "Antarmuka kaca yang dikendalikan tangan kosong lewat webcam.",
                sans_font(FONT.body),
                "Space Grotesk 14 px · teks utama",
                self._theme,
            )
        )
        row.addWidget(
            TypographyCard(
                "Label mono",
                "MENDENGARKAN · 00:12:48",
                mono_font(FONT.small, spacing=2.5),
                "Mono 12 px · kapital · jarak 2.5 px",
                self._theme,
            )
        )
        section.body().addLayout(row)
        section.body().addWidget(
            _label(
                f"Font terpasang: {resolve_family(SANS_CANDIDATES)} · "
                f"{resolve_family(MONO_CANDIDATES)} (fallback otomatis bila Space Grotesk absen)",
                mono_font(FONT.label, spacing=1.2),
                self._theme.palette.muted,
            )
        )
        return section

    def _build_glass(self) -> QWidget:
        section = Section("03", "Kaca", "Gradien tembus 18-30%, tepi 1.5 px", self._theme)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        for alpha, border, caption in (
            (0.18, None, "KACA 18% · lemas"),
            (0.26, None, "KACA 26% · panel"),
            (0.30, _alpha(self._theme.palette.warning, 0.8), "TEPI PERINGATAN"),
        ):
            frame = GlassFrame(
                theme=self._theme,
                alpha=alpha,
                border=border,
                minimum_height=120,
                margins=(18, 16, 18, 16),
            )
            frame.box().addWidget(
                _label(caps(caption), mono_font(FONT.label), self._theme.palette.teal)
            )
            frame.box().addStretch(1)
            frame.box().addWidget(
                _label(
                    "Highlight inset di atas · tanpa chrome kawat",
                    sans_font(11),
                    self._theme.palette.muted,
                )
            )
            row.addWidget(frame, 1)
        section.body().addLayout(row)
        return section

    def _build_controls(self) -> QWidget:
        section = Section("04", "Kontrol", "Mouse dan keyboard tetap jalan", self._theme)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        row.addWidget(GlassButton("PILIH", self._theme))
        row.addWidget(GlassButton("BATAL", self._theme, primary=False))
        row.addWidget(Badge("AKTIF", self._theme, color=self._theme.palette.listening))
        row.addSpacing(8)
        row.addWidget(HandleBar(self._theme))
        row.addSpacing(8)
        row.addWidget(IconButton(self._theme))
        row.addStretch(1)
        section.body().addLayout(row)
        section.body().addWidget(
            _label(
                "Target ketuk gestur minimal 56 px; tombol bisa dipakai dengan Tab + Space.",
                sans_font(11),
                self._theme.palette.muted,
            )
        )
        return section

    def _build_ring(self) -> QWidget:
        section = Section("05", "Ring", "440 px · lima status · 60 fps", self._theme)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(28)

        ring = RingWidget(self._theme)
        ring.setObjectName("ring-live")
        row.addWidget(ring, 0, Qt.AlignmentFlag.AlignTop)

        controls = QVBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(12)
        controls.addWidget(_label("STATUS TIRUAN", mono_font(FONT.label), self._theme.palette.teal))

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for index, status in enumerate(Status):
            button = GlassButton(status.label, self._theme, checkable=True)
            button.setMinimumWidth(128)
            button.setObjectName(f"ring-status-{status.value}")
            button.setChecked(status is Status.IDLE)
            button.clicked.connect(lambda _checked=False, chosen=status: ring.set_status(chosen))
            group.addButton(button)
            grid.addWidget(button, index // 2, index % 2)
        controls.addLayout(grid)
        controls.addSpacing(6)

        controls.addWidget(
            _label("LEVEL SUARA · AUTO-GAIN", mono_font(FONT.label), self._theme.palette.teal)
        )
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(0)
        slider.setObjectName("ring-level")
        slider.setAccessibleName("Level suara")
        slider.setStyleSheet(
            "QSlider::groove:horizontal { height: 4px; "
            f"background: {_rgba(self._theme.palette.teal, 0.20)}; border-radius: 2px; }}"
            "QSlider::sub-page:horizontal { "
            f"background: {_rgba(self._theme.palette.band, 0.45)}; border-radius: 2px; }}"
            "QSlider::handle:horizontal { width: 14px; height: 14px; margin: -5px 0; "
            f"border-radius: 7px; background: {self._theme.palette.band.name()}; }}"
        )
        controls.addWidget(slider)

        readout = _label(
            "",
            mono_font(FONT.label, spacing=1.5),
            self._theme.palette.muted,
        )
        readout.setObjectName("ring-readout")
        controls.addWidget(readout)

        def refresh() -> None:
            readout.setText(
                f"LEVEL {ring.level:.2f} · NORM {ring.normalized_level():.2f} · {ring.status.label}"
            )

        def on_level(value: int) -> None:
            ring.set_level(value / 100.0)
            refresh()

        slider.valueChanged.connect(on_level)
        ring.status_changed.connect(lambda _status: refresh())
        refresh()

        controls.addStretch(1)
        row.addLayout(controls, 1)
        section.body().addLayout(row)
        section.body().addWidget(
            _label(
                "Satu QTimer 60 fps; fase animasi dihitung dari jam dinding, bukan counter frame.",
                sans_font(11),
                self._theme.palette.muted,
            )
        )
        return section

    def _build_status(self) -> QWidget:
        section = Section("06", "Status", "Warna yang dipakai RingWidget", self._theme)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        for status in Status:
            row.addWidget(StatusChip(status, self._theme))
        row.addStretch(1)
        section.body().addLayout(row)
        section.body().addWidget(
            _label(
                "Animasi cincin (napas, denyut, radar, gelombang suara) aktif di RingWidget.",
                sans_font(11),
                self._theme.palette.muted,
            )
        )
        return section

    def _build_cursor(self) -> QWidget:
        section = Section(
            "07", "Kamera & kursor", "Indikator selalu terlihat · cincin 28 px", self._theme
        )
        camera_row = QHBoxLayout()
        camera_row.setContentsMargins(0, 0, 0, 0)
        camera_row.setSpacing(10)
        for state in CameraState:
            indicator = CameraIndicator(self._theme)
            indicator.set_state(state)
            indicator.setObjectName(f"camera-{state.value}")
            camera_row.addWidget(indicator)
        camera_row.addStretch(1)
        section.body().addLayout(camera_row)
        section.body().addWidget(
            _label(
                "Indikator kamera tetap terlihat saat Mode Gestur aktif; state jeda dan error "
                "mengikuti Ctrl+Alt+G.",
                sans_font(11),
                self._theme.palette.muted,
            )
        )
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        for mode in (CursorPreview.MODE_FREE, CursorPreview.MODE_PINCH, CursorPreview.MODE_DWELL):
            row.addWidget(
                PreviewCard(
                    "Kursor",
                    CursorPreview(mode, self._theme),
                    {
                        CursorPreview.MODE_FREE: "Bebas: cincin tipis, titik pusat.",
                        CursorPreview.MODE_PINCH: "Cubit: terisi dan mengecil.",
                        CursorPreview.MODE_DWELL: "Dwell: busur terisi saat menahan.",
                    }[mode],
                    self._theme,
                ),
                1,
            )
        section.body().addLayout(row)
        return section

    def _build_toasts(self) -> QWidget:
        section = Section("08", "Toast & petunjuk", "Umpan balik singkat", self._theme)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        row.addWidget(ToastPreview(self._theme))
        row.addStretch(1)
        section.body().addLayout(row)
        section.body().addWidget(HintBar(self._theme))
        return section

    def _build_map(self) -> QWidget:
        section = Section("09", "Peta komponen", "Semua fase, satu katalog", self._theme)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        for index, spec in enumerate(COMPONENTS):
            row, col = divmod(index, 2)
            grid.addWidget(PlaceholderCard(spec, self._theme), row, col)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        section.body().addLayout(grid)
        return section

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        layout = QVBoxLayout(footer)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(_hairline(self._theme, 0.12))
        layout.addWidget(
            _label(
                "PRIVASI · KAMERA NONAKTIF · VIDEO TIDAK PERNAH DISIMPAN · TIDAK ADA PORT JARINGAN",
                mono_font(9, spacing=2.0),
                self._theme.palette.muted,
                align=Qt.AlignmentFlag.AlignCenter,
            )
        )
        return footer
