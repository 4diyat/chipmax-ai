"""Design token Glass Stage: warna, kaca, huruf, metrik.

Nilai warna disimpan sebagai string hex murni supaya bisa dites tanpa Qt; helper
QColor/QFont baru dipakai saat menggambar. Tidak ada font yang dibundel: jika
Space Grotesk tidak terpasang, rantai fallback di bawah yang dipakai.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication

from jarvis_hands.core.state import Status

__all__ = [
    "GLASS_STYLE",
    "HEX",
    "HEX_HIGH_CONTRAST",
    "METRICS",
    "MONO_CANDIDATES",
    "SANS_CANDIDATES",
    "TOKENS",
    "FontTokens",
    "GlassStyle",
    "Metrics",
    "Palette",
    "Theme",
    "TokenSpec",
    "apply_app_font",
    "apply_theme",
    "build_palette",
    "build_theme",
    "caps",
    "contrast_ratio",
    "label_font",
    "mono_font",
    "paint_glass",
    "paint_stage",
    "relative_luminance",
    "resolve_family",
    "rgba_css",
    "sans_font",
    "status_color",
    "with_alpha",
]

HEX: Final[dict[str, str]] = {
    "stage": "#070D0F",
    "teal": "#6FE5D6",
    "accent": "#8FF0E4",
    "band": "#8CEBF0",
    "hot_rim": "#E4FAFC",
    "text": "#ECFFFA",
    "muted": "#A8D8CF",
    "listening": "#78CDFA",
    "warning": "#F5A524",
    # Tepi kaca: 140,240,225 pada alpha 0.55 (lihat GlassStyle).
    "border": "#8CF0E1",
}

HEX_HIGH_CONTRAST: Final[dict[str, str]] = {
    "stage": "#000000",
    "teal": "#7FF0DF",
    "accent": "#B8FFF6",
    "band": "#A5F7FF",
    "hot_rim": "#FFFFFF",
    "text": "#FFFFFF",
    "muted": "#D6FFF7",
    "listening": "#8FD8FF",
    "warning": "#FFC24D",
    "border": "#A5F7FF",
}


@dataclass(frozen=True)
class TokenSpec:
    """Entri katalog warna: kunci, nama tampilan, hex, dan catatan pemakaian."""

    key: str
    name: str
    hex_code: str
    note: str


TOKENS: Final[tuple[TokenSpec, ...]] = (
    TokenSpec("stage", "Panggung", HEX["stage"], "Latar utama, nyaris hitam kehijauan"),
    TokenSpec("teal", "Teal kaca", HEX["teal"], "Isi kaca, aksen garis, orb"),
    TokenSpec("accent", "Aksen teks", HEX["accent"], "Judul aktif, angka penting"),
    TokenSpec("band", "Pita cincin", HEX["band"], "Pita RingWidget status idle/thinking"),
    TokenSpec("hot_rim", "Tepi panas", HEX["hot_rim"], "Rim putih panas, status speaking"),
    TokenSpec("text", "Teks", HEX["text"], "Teks utama"),
    TokenSpec("muted", "Teks redup", HEX["muted"], "Keterangan, label sekunder"),
    TokenSpec("listening", "Mendengarkan", HEX["listening"], "Status listening, biru"),
    TokenSpec("warning", "Peringatan", HEX["warning"], "Error, ambang kritis"),
)


@dataclass(frozen=True)
class Palette:
    """QColor siap pakai untuk satu tema (normal atau kontras tinggi)."""

    stage: QColor
    teal: QColor
    accent: QColor
    band: QColor
    hot_rim: QColor
    text: QColor
    muted: QColor
    listening: QColor
    warning: QColor
    border: QColor


def build_palette(high_contrast: bool = False) -> Palette:
    """Bangun palet dari token; tidak ada mutasi QColor setelah dibuat."""
    source = HEX_HIGH_CONTRAST if high_contrast else HEX
    return Palette(
        stage=QColor(source["stage"]),
        teal=QColor(source["teal"]),
        accent=QColor(source["accent"]),
        band=QColor(source["band"]),
        hot_rim=QColor(source["hot_rim"]),
        text=QColor(source["text"]),
        muted=QColor(source["muted"]),
        listening=QColor(source["listening"]),
        warning=QColor(source["warning"]),
        border=QColor(source["border"]),
    )


@dataclass(frozen=True)
class GlassStyle:
    """Ukuran dan alpha gaya kaca."""

    border_width: float = 1.5
    radius: float = 20.0
    #: Radius kontrol (tombol, input, group box); satu tingkat di bawah panel.
    control_radius: float = 12.0
    surface_alpha_min: float = 0.18
    surface_alpha_max: float = 0.30
    border_alpha: float = 0.55
    highlight_alpha: float = 0.14
    glow_alpha: float = 0.06


GLASS_STYLE: Final = GlassStyle()


@dataclass(frozen=True)
class Metrics:
    """Metrik tetap dari spesifikasi mockup (piksel logis)."""

    ring_size: int = 440
    ring_band: int = 20
    ring_ticks: int = 48
    orb_size: int = 112
    cursor_size: int = 28
    idle_dot: int = 16
    min_target: int = 56
    toast_width: int = 320
    hint_height: int = 44
    panel_radius: int = 20
    card_padding: int = 20
    handle_width: int = 48
    handle_height: int = 4


METRICS: Final = Metrics()


@dataclass(frozen=True)
class FontTokens:
    """Ukuran huruf; label mono selalu kapital dan berjarak 2-4 px."""

    display: int = 30
    title: int = 20
    body: int = 14
    small: int = 12
    label: int = 10
    label_spacing: float = 2.5


FONT: Final = FontTokens()

SANS_CANDIDATES: Final[tuple[str, ...]] = (
    "Space Grotesk",
    "Space Grotesk Variable",
    "Inter",
    "Segoe UI",
    "Noto Sans",
    "DejaVu Sans",
    "Sans Serif",
)

MONO_CANDIDATES: Final[tuple[str, ...]] = (
    "JetBrains Mono",
    "IBM Plex Mono",
    "Cascadia Mono",
    "Consolas",
    "DejaVu Sans Mono",
    "Noto Sans Mono",
    "Monospace",
)


@dataclass(frozen=True)
class Theme:
    """Palet + gaya kaca + kontras; dikirim ke semua widget."""

    palette: Palette
    style: GlassStyle = GLASS_STYLE
    high_contrast: bool = False


def build_theme(high_contrast: bool = False) -> Theme:
    """Bangun tema lengkap."""
    return Theme(
        palette=build_palette(high_contrast),
        style=GLASS_STYLE,
        high_contrast=high_contrast,
    )


def status_color(status: Status, palette: Palette) -> QColor:
    """Warna utama tiap status cincin."""
    return {
        Status.IDLE: palette.band,
        Status.LISTENING: palette.listening,
        Status.THINKING: palette.teal,
        Status.SPEAKING: palette.hot_rim,
        Status.SENYAP: palette.muted,
    }[status]


def caps(text: str) -> str:
    """Label mono kapital (tanpa mengubah isi teks)."""
    return text.upper()


def resolve_family(candidates: Sequence[str]) -> str:
    """Pilih keluarga font pertama yang terpasang; fallback ke kandidat terakhir."""
    return _resolve_family(tuple(candidates))


@lru_cache(maxsize=8)
def _resolve_family(candidates: tuple[str, ...]) -> str:
    if QGuiApplication.instance() is None:
        return candidates[-1]
    available = set(QFontDatabase.families())
    for name in candidates:
        if name in available:
            return name
    return candidates[-1]


def sans_font(size: int = FONT.body, *, bold: bool = False) -> QFont:
    """Font isi Space Grotesk (atau fallback)."""
    font = QFont(resolve_family(SANS_CANDIDATES))
    font.setPointSize(size)
    font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def mono_font(size: int = FONT.label, *, spacing: float = FONT.label_spacing) -> QFont:
    """Font label mono kapital berjarak."""
    font = QFont(resolve_family(MONO_CANDIDATES))
    font.setPointSize(size)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def label_font(size: int = FONT.label) -> QFont:
    """Alias ``mono_font`` untuk label status."""
    return mono_font(size)


def apply_app_font(app: QApplication) -> None:
    """Terapkan font isi ke seluruh aplikasi."""
    app.setFont(sans_font(FONT.body))


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Terapkan style Fusion, palet, dan font dasar."""
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, theme.palette.stage)
    pal.setColor(QPalette.ColorRole.WindowText, theme.palette.text)
    pal.setColor(QPalette.ColorRole.Base, QColor("#0A1417"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#0D1B1E"))
    pal.setColor(QPalette.ColorRole.Text, theme.palette.text)
    pal.setColor(QPalette.ColorRole.Button, QColor("#0E1B1E"))
    pal.setColor(QPalette.ColorRole.ButtonText, theme.palette.text)
    pal.setColor(QPalette.ColorRole.Highlight, theme.palette.teal)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#04100F"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#0A1417"))
    pal.setColor(QPalette.ColorRole.ToolTipText, theme.palette.text)
    pal.setColor(QPalette.ColorRole.PlaceholderText, theme.palette.muted)
    app.setPalette(pal)
    app.setStyleSheet(
        f"QToolTip {{ color: {theme.palette.text.name()}; "
        f"background-color: {theme.palette.stage.name()}; "
        f"border: 1px solid {theme.palette.border.name()}; padding: 6px; }}"
        "QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }"
        f"QScrollBar::handle:vertical {{ background: {_qss_alpha(theme.palette.teal, 0.22)}; "
        "min-height: 32px; border-radius: 4px; }"
        f"QScrollBar::handle:vertical:hover {{ background: "
        f"{_qss_alpha(theme.palette.teal, 0.45)}; }}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }"
        "QScrollArea { background: transparent; }"
    )
    apply_app_font(app)


def _qss_alpha(color: QColor, alpha: float) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha:.3f})"


def relative_luminance(color: QColor) -> float:
    """Luminance relatif WCAG dari QColor."""

    def channel(value: int) -> float:
        c = value / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(color.red())
        + 0.7152 * channel(color.green())
        + 0.0722 * channel(color.blue())
    )


def contrast_ratio(first: QColor, second: QColor) -> float:
    """Rasio kontras WCAG 2.x (1..21)."""
    high, low = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def paint_stage(painter: QPainter, rect: QRectF, theme: Theme) -> None:
    """Latar panggung + pendar teal halus di atas."""
    painter.fillRect(rect, theme.palette.stage)
    glow = QRadialGradient(
        QPointF(rect.center().x(), rect.top() - rect.height() * 0.15), rect.width() * 0.62
    )
    glow.setColorAt(0.0, _alpha(theme.palette.teal, theme.style.glow_alpha))
    glow.setColorAt(0.55, _alpha(theme.palette.teal, theme.style.glow_alpha * 0.35))
    glow.setColorAt(1.0, _alpha(theme.palette.teal, 0.0))
    painter.fillRect(rect, glow)


def paint_glass(
    painter: QPainter,
    rect: QRectF,
    theme: Theme,
    *,
    alpha: float | None = None,
    border: QColor | None = None,
    radius: float | None = None,
) -> None:
    """Gambar satu permukaan kaca: gradien tembus, tepi 1.5 px, highlight inset.

    ``alpha`` mengesampingkan gradien permukaan (untuk variasi panel). Fungsi ini
    tidak memanggil ``begin``/``end``; pemanggil memiliki painter.
    """
    style = theme.style
    surface = style.surface_alpha_min if alpha is None else max(0.0, min(1.0, alpha))
    r = style.radius if radius is None else max(0.0, radius)
    inner = QRectF(rect.left() + 0.75, rect.top() + 0.75, rect.width() - 1.5, rect.height() - 1.5)
    path = QPainterPath()
    path.addRoundedRect(inner, r, r)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # Isi gradien: atas lebih terang (teal), bawah lebih gelap (panggung).
    gradient = QLinearGradient(
        QPointF(inner.left(), inner.top()), QPointF(inner.left(), inner.bottom())
    )
    top = _alpha(theme.palette.teal, surface)
    bottom = _alpha(theme.palette.stage, min(1.0, surface + 0.08))
    gradient.setColorAt(0.0, top)
    gradient.setColorAt(0.55, _alpha(theme.palette.stage, surface * 0.85))
    gradient.setColorAt(1.0, bottom)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawPath(path)

    # Pendar dalam di pojok kiri atas.
    glow = QRadialGradient(
        QPointF(inner.left() + inner.width() * 0.18, inner.top() + inner.height() * 0.12),
        max(inner.width(), inner.height()) * 0.75,
    )
    glow.setColorAt(0.0, _alpha(theme.palette.hot_rim, style.highlight_alpha * 0.35))
    glow.setColorAt(1.0, _alpha(theme.palette.hot_rim, 0.0))
    painter.setBrush(glow)
    painter.drawPath(path)

    # Tepi kaca.
    edge = border if border is not None else _alpha(theme.palette.border, style.border_alpha)
    pen = QPen(edge, style.border_width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(pen)
    painter.drawPath(path)

    # Highlight inset di atas, dipotong bentuk kaca.
    painter.setClipPath(path)
    highlight = QPen(_alpha(theme.palette.hot_rim, style.highlight_alpha), 1.0)
    painter.setPen(highlight)
    y = inner.top() + 1.0
    painter.drawLine(
        QPointF(inner.left() + r * 0.55, y),
        QPointF(inner.right() - r * 0.55, y),
    )
    painter.restore()


def _alpha(color: QColor, alpha: float) -> QColor:
    # Konstruktor RGBA dipakai alih-alih setAlphaF: lebih murah dan menghindari
    # bug refcount setter None pada PySide6 6.12.0.
    alpha_int = round(max(0.0, min(1.0, alpha)) * 255)
    return QColor(color.red(), color.green(), color.blue(), alpha_int)


def with_alpha(color: QColor, alpha: float) -> QColor:
    """Salin QColor dengan alpha baru (0..1), untuk painter eksternal."""
    return _alpha(color, alpha)


def rgba_css(color: QColor, alpha: float) -> str:
    """Warna transparan untuk stylesheet QSS berbentuk ``rgba(r, g, b, a)``.

    QSS tidak memahami ``#AARRGGBB`` (yang justru dibaca terbalik sebagai
    ``#RRGGBB``), jadi semua alpha di stylesheet harus lewat helper ini.
    """
    tinted = _alpha(color, alpha)
    return f"rgba({tinted.red()}, {tinted.green()}, {tinted.blue()}, {alpha:.3f})"
