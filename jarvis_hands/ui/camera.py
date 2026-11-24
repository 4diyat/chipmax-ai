"""Indikator kamera: titik status + label mono, selalu terlihat.

Indikator tidak pernah disembunyikan selama Mode Gestur aktif; saat kamera mati
ia tetap menampilkan ``KAMERA MATI`` supaya pengguna tahu kondisi perangkat.
"""

from __future__ import annotations

from enum import StrEnum, unique

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from jarvis_hands.ui.tokens import (
    FONT,
    Theme,
    build_theme,
    mono_font,
    paint_glass,
    with_alpha,
)

__all__ = ["CameraIndicator", "CameraState"]


@unique
class CameraState(StrEnum):
    """Kondisi kamera yang ditampilkan indikator."""

    OFF = "off"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


_LABELS: dict[CameraState, str] = {
    CameraState.OFF: "KAMERA MATI",
    CameraState.ACTIVE: "KAMERA AKTIF",
    CameraState.PAUSED: "KAMERA JEDA",
    CameraState.ERROR: "KAMERA ERROR",
}


class CameraIndicator(QWidget):
    """Pil kaca kecil dengan titik status dan label mono kapital."""

    #: State indikator berubah (payload: :class:`CameraState`).
    state_changed = Signal(object)

    def __init__(self, theme: Theme | None = None, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self._state = CameraState.OFF
        self._fps = 0.0
        self._font = mono_font(FONT.small, spacing=2.0)
        palette = self._theme.palette
        self._active_color = palette.teal
        self._warning_color = palette.warning
        self._off_color = with_alpha(palette.muted, 0.75)
        self._text_color = palette.text
        self._muted_color = palette.muted
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName("Indikator kamera")
        self._update_accessible()
        self._apply_size()

    def set_theme(self, theme: Theme) -> None:
        """Ganti tema (misal kontras tinggi) tanpa membangun ulang indikator."""
        self._theme = theme
        palette = theme.palette
        self._active_color = palette.teal
        self._warning_color = palette.warning
        self._off_color = with_alpha(palette.muted, 0.75)
        self._text_color = palette.text
        self._muted_color = palette.muted
        self.update()

    # ------------------------------------------------------------------ state

    @property
    def state(self) -> CameraState:
        """State indikator saat ini."""
        return self._state

    @property
    def fps(self) -> float:
        """FPS analisis terakhir (0 bila belum ada)."""
        return self._fps

    @property
    def label(self) -> str:
        """Label tampilan saat ini (dimasukkan bullet seperti mockup)."""
        text = _LABELS[self._state]
        if self._state is CameraState.ACTIVE and self._fps >= 1.0:
            text += f"   {round(self._fps)} FPS"
        return f"• {text}"

    def set_state(self, state: CameraState) -> None:
        """Ganti state; hanya memicu repaint bila berubah."""
        state = CameraState(state)
        if state == self._state:
            return
        self._state = state
        self._update_accessible()
        self._apply_size()
        self.update()
        self.state_changed.emit(state)

    def set_active(self, active: bool) -> None:
        """Aktif/matikan indikator (kamera menyala atau tidak)."""
        self.set_state(CameraState.ACTIVE if active else CameraState.OFF)

    def set_paused(self, paused: bool) -> None:
        """Tampilkan state jeda bila kamera aktif."""
        self.set_state(CameraState.PAUSED if paused else CameraState.ACTIVE)

    def set_error(self) -> None:
        """Tampilkan state kesalahan."""
        self.set_state(CameraState.ERROR)

    def set_fps(self, fps: float) -> None:
        """Perbarui label FPS (dibulatkan, hanya saat aktif)."""
        value = max(0.0, float(fps))
        changed = round(value) != round(self._fps)
        self._fps = value
        if changed:
            self._apply_size()
            self.update()

    # ------------------------------------------------------------------ paint

    def paintEvent(self, event: QPaintEvent | None) -> None:  # noqa: N802
        """Gambar pil kaca, titik status, dan label."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0.0, 0.0, float(self.width()), float(self.height()))
        paint_glass(painter, rect, self._theme, radius=rect.height() / 2.0)

        color = self._dot_color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(9.0, rect.center().y() - 3.0, 6.0, 6.0))

        painter.setFont(self._font)
        painter.setPen(QPen(self._text_color, 1.0))
        text_rect = rect.adjusted(22.0, 0.0, -10.0, 0.0)
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self.label,
        )
        painter.end()

    def _dot_color(self) -> QColor:
        if self._state is CameraState.ACTIVE:
            return self._active_color
        if self._state is CameraState.PAUSED:
            return self._warning_color
        if self._state is CameraState.ERROR:
            return self._warning_color
        return self._off_color

    def _apply_size(self) -> None:
        metrics = QFontMetrics(self._font)
        width = 22 + metrics.horizontalAdvance(self.label) + 12
        self.setFixedSize(max(96, width), 24)

    def _update_accessible(self) -> None:
        self.setAccessibleDescription(f"Kamera {self._state.value}. {self.label}.")
