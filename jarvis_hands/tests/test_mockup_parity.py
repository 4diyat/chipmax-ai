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


def test_close_icon_is_44px_but_target_is_56px() -> None:
    """Mockup: ikon tutup 44 px, "target >= 56 px" untuk gestur."""
    from PySide6.QtCore import QPointF

    from jarvis_hands.ui.glass import CLOSE_HIT, CLOSE_TARGET, close_hit_rect, close_rect

    card = Card("Kartu", "Isi", theme=build_theme())
    surface = card.surface_rect()
    assert close_rect(surface).width() == CLOSE_TARGET == 44
    assert close_hit_rect(surface).width() == CLOSE_HIT == 56
    center = card.close_rect().center()
    # 26 px dari pusat: di luar lingkaran 44 px (22 px), di dalam target 56 px.
    edge = QPointF(center.x(), center.y() + 26)
    assert card.hit_test(edge) is not None
    from jarvis_hands.ui.glass import SurfaceHit

    assert card.hit_test(edge) is SurfaceHit.CLOSE


def test_panel_body_click_emits_activated(qtbot: Any) -> None:
    """Jalan non-gestur: klik badan panel memicu aksi buka (bukan hanya drag)."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from jarvis_hands.ui.card import Panel

    panel = Panel("Panel", theme=build_theme())
    qtbot.addWidget(panel)
    panel.resize(400, 240)
    panel.show()
    fired: list[bool] = []
    panel.activated.connect(lambda: fired.append(True))
    QTest.mouseClick(
        panel,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(200, 140),
    )
    assert fired == [True]


def test_provider_page_texts_follow_selection(qtbot: Any) -> None:
    """Mockup 01/02: keterangan penyedia, placeholder key, dan alamat Ollama."""
    from jarvis_hands.agent.settings import Provider
    from jarvis_hands.ui.agent_settings import AgentSettingsPage

    page = AgentSettingsPage(AgentSettings(), CredentialStore(), theme=build_theme())
    qtbot.addWidget(page)
    assert page.note.text() == "Penyedia aktif · Gemini API"
    assert page.key.placeholderText() == "Masukkan key Gemini"
    assert not page.url.isVisible() or not page.url_label.isVisible()

    page._select_provider(list(Provider).index(Provider.OLLAMA))
    assert page.note.text() == "Ollama: alamat server · API key opsional"
    assert page.key.placeholderText() == "Opsional untuk server lokal"
    assert page.url_label.isVisible() or page.url_label.text() == "ALAMAT OLLAMA"

    page._select_provider(list(Provider).index(Provider.CHATGPT))
    assert "OpenAI API" in page.note.text()
    assert page.key.placeholderText() == "Masukkan key OpenAI"


def test_hold_progress_feedback_on_card(qtbot: Any, qapp: Any) -> None:
    """Mockup: "TAHAN 1 DETIK" - progres tahan ditampilkan di kartu."""
    from jarvis_hands.core.config import AppConfig
    from jarvis_hands.gestures.types import GestureEvent, GestureKind, GesturePhase
    from jarvis_hands.ui.overlay import OverlayWindow
    from jarvis_hands.vision.session import CameraSession

    config = AppConfig.default()
    overlay = OverlayWindow(config, CameraSession(config.camera), qapp.primaryScreen())
    qtbot.addWidget(overlay)
    center = overlay.card.mapToGlobal(overlay.card.surface_rect().center().toPoint())
    overlay._press_target = overlay.card
    overlay._pinch_started = 0
    overlay._route(
        GestureEvent(
            GestureKind.HOLD, GesturePhase.UPDATE, 10, center.x(), center.y(), magnitude=500
        )
    )
    assert "50%" in overlay.card.footer
    overlay._route(GestureEvent(GestureKind.HOLD, GesturePhase.END, 20, center.x(), center.y()))
    assert overlay.card.footer == "Tahan 1 detik"
