"""Tes token Glass Stage: nilai, kontras, metrik, dan lukisan kaca."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from jarvis_hands.core.state import Status
from jarvis_hands.ui.tokens import (
    FONT,
    HEX,
    HEX_HIGH_CONTRAST,
    METRICS,
    MONO_CANDIDATES,
    SANS_CANDIDATES,
    TOKENS,
    build_palette,
    build_theme,
    contrast_ratio,
    paint_glass,
    resolve_family,
    status_color,
)


def test_token_values_match_spec() -> None:
    assert HEX == {
        "stage": "#070D0F",
        "teal": "#6FE5D6",
        "accent": "#8FF0E4",
        "band": "#8CEBF0",
        "hot_rim": "#E4FAFC",
        "text": "#ECFFFA",
        "muted": "#A8D8CF",
        "listening": "#78CDFA",
        "warning": "#F5A524",
        "border": "#8CF0E1",
    }


def test_token_catalog_covers_every_color() -> None:
    assert {token.key for token in TOKENS} == set(HEX) - {"border"}
    assert [token.key for token in TOKENS] == [
        "stage",
        "teal",
        "accent",
        "band",
        "hot_rim",
        "text",
        "muted",
        "listening",
        "warning",
    ]
    for token in TOKENS:
        assert token.hex_code == HEX[token.key]


def test_metrics_match_spec() -> None:
    assert METRICS.ring_size == 440
    assert METRICS.ring_band == 20
    assert METRICS.ring_ticks == 48
    assert METRICS.orb_size == 112
    assert METRICS.cursor_size == 28
    assert METRICS.idle_dot == 16
    assert METRICS.min_target == 56


def test_font_tokens_are_sane() -> None:
    assert 2.0 <= FONT.label_spacing <= 4.0
    assert SANS_CANDIDATES[-1] == "Sans Serif"
    assert MONO_CANDIDATES[-1] == "Monospace"


def test_text_contrast_on_stage_meets_wcag() -> None:
    palette = build_palette()
    stage = palette.stage
    for color in (palette.text, palette.muted, palette.teal, palette.accent, palette.warning):
        assert contrast_ratio(color, stage) >= 4.5, color.name()


def test_high_contrast_palette_is_stronger() -> None:
    palette = build_palette(high_contrast=True)
    assert palette.stage.name() == "#000000"
    assert palette.text.name() == "#ffffff"
    assert contrast_ratio(palette.text, palette.stage) == 21.0
    assert contrast_ratio(palette.muted, palette.stage) >= 15.0
    assert HEX_HIGH_CONTRAST["stage"] == "#000000"


def test_status_color_mapping() -> None:
    palette = build_palette()
    assert status_color(Status.IDLE, palette) == palette.band
    assert status_color(Status.LISTENING, palette) == palette.listening
    assert status_color(Status.THINKING, palette) == palette.teal
    assert status_color(Status.SPEAKING, palette) == palette.hot_rim
    assert status_color(Status.SENYAP, palette) == palette.muted


def test_resolve_family_prefers_installed(qtbot) -> None:  # type: ignore[no-untyped-def]
    del qtbot
    installed = resolve_family(("Font Yang Tidak Ada", "DejaVu Sans"))
    assert installed == "DejaVu Sans"
    assert resolve_family(SANS_CANDIDATES) in SANS_CANDIDATES
    assert resolve_family(MONO_CANDIDATES) in MONO_CANDIDATES


def test_paint_glass_renders_transparent_surface() -> None:
    image = QImage(240, 140, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    paint_glass(painter, QRectF(0, 0, 240, 140), build_theme())
    painter.end()

    center = image.pixelColor(120, 70)
    edge = image.pixelColor(1, 70)
    assert 0 < center.alpha() < 255
    assert edge.alpha() > center.alpha()
    assert QColor(center.red(), center.green(), center.blue()) != QColor(0, 0, 0)


def test_paint_glass_high_contrast_uses_black_stage() -> None:
    image = QImage(120, 80, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    paint_glass(painter, QRectF(0, 0, 120, 80), build_theme(high_contrast=True), alpha=0.3)
    painter.end()
    assert image.pixelColor(60, 40).alpha() > 0
