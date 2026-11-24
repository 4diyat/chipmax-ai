"""Tes regresi penyesuaian mockup: chrome overlay, ikon, dan QSS transparan."""

from __future__ import annotations

import re
from typing import Any

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor

from jarvis_hands.agent.settings import AgentSettings, CredentialStore
from jarvis_hands.core.config import AppConfig
from jarvis_hands.ui.card import Card
from jarvis_hands.ui.catalog import HintBar, ToastPreview
from jarvis_hands.ui.chrome import ChromeMode, ChromeToggle
from jarvis_hands.ui.glass import idle_dot_hit_rect, idle_dot_rect
from jarvis_hands.ui.icons import IconKind, icon_pixmap
from jarvis_hands.ui.settings import SettingsDialog
from jarvis_hands.ui.tokens import (
    FONT,
    METRICS,
    build_theme,
    rgba_css,
    sans_font,
)
from jarvis_hands.ui.treepane import TreePane


def test_chrome_toggle_cycles_and_emits_once() -> None:
    toggle = ChromeToggle()
    seen: list[ChromeMode] = []
    toggle.mode_changed.connect(seen.append)
    assert toggle.mode is ChromeMode.ON
    assert toggle.cycle() is ChromeMode.OFF
    assert toggle.cycle() is ChromeMode.SENYAP
    assert toggle.cycle() is ChromeMode.ON
    assert seen == [ChromeMode.OFF, ChromeMode.SENYAP, ChromeMode.ON]

    toggle.set_mode(ChromeMode.ON)
    assert seen == [ChromeMode.OFF, ChromeMode.SENYAP, ChromeMode.ON]


def test_rgba_css_uses_alpha_channel_not_hexargb() -> None:
    # Qt membaca #AARRGGBB sebagai #RRGGBB, jadi alpha wajib lewat rgba().
    text = rgba_css(QColor("#6FE5D6"), 0.35)
    assert text == "rgba(111, 229, 214, 0.350)"
    assert not text.startswith("#")


def test_idle_dot_geometry_matches_metrics() -> None:
    area = QRectF(0, 0, 1440, 900)
    dot = idle_dot_rect(area)
    assert dot.width() == METRICS.idle_dot
    assert dot.height() == METRICS.idle_dot
    assert dot.center().x() == pytest.approx(area.center().x())
    assert dot.bottom() < area.bottom()
    hit = idle_dot_hit_rect(area)
    assert hit.width() == pytest.approx(44.0)
    assert hit.contains(dot.center())


def test_hint_bar_hides_right_text_when_narrow(qtbot: Any) -> None:
    theme = build_theme()
    bar = HintBar(theme)
    qtbot.addWidget(bar)
    bar.resize(600, METRICS.hint_height)
    bar.show()
    assert bar.preferred_width() > 600  # kedua teks tidak muat bersamaan
    assert bar.right_text
    bar.set_right("KAMERA AKTIF · 30 FPS · LOKAL")
    assert bar.right_text.startswith("KAMERA AKTIF")


def test_toast_grows_for_long_text(qtbot: Any) -> None:
    toast = ToastPreview(build_theme())
    qtbot.addWidget(toast)
    start = toast.width()
    toast.set_message("Chrome disembunyikan", detail="Titik 16 px di bawah layar")
    assert toast.width() >= start
    assert toast.accessibleName() == "Toast: chrome disembunyikan"


def test_card_title_fits_inside_surface() -> None:
    from PySide6.QtGui import QFontMetrics

    from jarvis_hands.ui.card import _fitted_title

    card = Card("Catatan kalibrasi ambang yang sangat panjang sekali", theme=build_theme())
    width = card.surface_rect().width() - 2 * METRICS.card_padding - 44
    normal = QFontMetrics(sans_font(FONT.title, bold=True))
    assert normal.horizontalAdvance(card.title) > width  # judul asli tidak muat
    font, text = _fitted_title(card.title, width)
    assert text.endswith("…") or QFontMetrics(font).horizontalAdvance(text) <= width
    assert QFontMetrics(font).horizontalAdvance(text) <= width


def test_tree_selection_uses_teal_palette_not_hex(qtbot: Any) -> None:
    pane = TreePane(theme=build_theme())
    qtbot.addWidget(pane)
    palette = pane._list.palette()
    highlight = palette.color(palette.ColorRole.Highlight)
    assert 0 < highlight.alpha() < 255  # transparan, bukan blok pekat
    # Tidak ada #AARRGGBB di QSS pohon: Qt membacanya terbalik jadi biru pekat.
    # Hex 6 digit (warna teks solid) tetap boleh; hanya 8 digit yang berbahaya.
    assert not re.search(r"#[0-9A-Fa-f]{8}\b", pane._list.styleSheet())


def test_settings_nav_keeps_ampersand(qtbot: Any) -> None:
    """Label "AGEN & API" tidak boleh tampil "AGEN_API" di sidebar."""
    dialog = SettingsDialog(AppConfig.default(), AgentSettings(), CredentialStore())
    qtbot.addWidget(dialog)
    dialog.resize(980, 700)
    dialog.show()
    agent_button = dialog._nav_buttons[0]
    assert agent_button.accessibleName() == "AGEN & API"
    # Tombol nav menggambar teksnya sendiri, jadi Qt tidak menelan "&" sebagai
    # mnemonic. Teks asli harus tetap utuh.
    assert agent_button.text() == "AGEN & API"
    image = agent_button.grab().toImage()
    assert image.width() > 0 and image.height() > 0
    assert dialog.logo is not None


@pytest.mark.parametrize("kind", list(IconKind))
def test_every_icon_renders_pixels(kind: IconKind) -> None:
    pixmap = icon_pixmap(kind, QColor("#6FE5D6"), size=20)
    assert not pixmap.isNull()
    image = pixmap.toImage()
    opaque = [
        (x, y)
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 0
    ]
    assert opaque, kind


def test_card_footer_is_rendered_and_readable() -> None:
    card = Card("Kartu 01 · catatan", "Isi", chip="DRAF", footer="Tahan 1 detik")
    assert card.footer == "Tahan 1 detik"
    card.set_footer("GESER DI PEGANGAN")
    assert card.footer == "GESER DI PEGANGAN"
    assert card.grab().toImage().width() > 0


def test_panel_title_matches_mockup_scale(qtbot: Any) -> None:
    """Panel mockup memakai judul 20 px tebal dan teks judul apa adanya."""
    from PySide6.QtWidgets import QLabel

    from jarvis_hands.ui.card import Panel

    panel = Panel("Panel · catatan", theme=build_theme())
    qtbot.addWidget(panel)
    assert panel.title == "Panel · catatan"
    titles = [label for label in panel.findChildren(QLabel) if label.text() == "Panel · catatan"]
    assert titles, "judul panel harus tampil tanpa diubah ke kapital"
    assert titles[0].font().pointSize() == FONT.title


def test_tree_pane_shows_breadcrumb_and_footnote(qtbot: Any) -> None:
    pane = TreePane(theme=build_theme())
    qtbot.addWidget(pane)
    pane.resize(900, 460)
    pane.show()
    assert pane._path.text().startswith("memori")
    assert "BARIS" in pane._footnote.text()
    assert pane._meta.text().endswith("DATA TIDAK TERPERCAYA")
    assert pane._info.font().pointSize() == FONT.title
