"""Tes halaman katalog komponen Fase 0."""

from __future__ import annotations

from PySide6.QtCore import Qt

from jarvis_hands.core.config import AppConfig, with_display_overrides
from jarvis_hands.core.state import Status
from jarvis_hands.ui.catalog import (
    COMPONENTS,
    CatalogWindow,
    CursorPreview,
    GlassButton,
    GlassFrame,
    HintBar,
    IconButton,
    PlaceholderCard,
    StatusChip,
    ToastPreview,
    TokenCard,
)
from jarvis_hands.ui.tokens import METRICS


def _show(qtbot, window: CatalogWindow) -> CatalogWindow:  # type: ignore[no-untyped-def]
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(30)
    return window


def test_catalog_builds_and_shows(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    assert window.windowTitle() == "JARVIS — Katalog Glass Stage"
    assert window.theme.high_contrast is False
    assert window.config == AppConfig.default()
    assert window.isVisible()


def test_catalog_has_every_token(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    cards = window.findChildren(TokenCard)
    assert len(cards) == 9
    names = {card.objectName() for card in cards}
    assert names == {
        "token-stage",
        "token-teal",
        "token-accent",
        "token-band",
        "token-hot_rim",
        "token-text",
        "token-muted",
        "token-listening",
        "token-warning",
    }


def test_catalog_has_all_status_chips(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    chips = window.findChildren(StatusChip)
    assert {chip.status() for chip in chips} == set(Status)
    for chip in chips:
        assert chip.height() >= 32
        assert chip.accessibleName().startswith("Status ")


def test_catalog_component_map_is_complete(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    keys = [spec.key for spec in COMPONENTS]
    assert len(keys) == len(set(keys))
    for spec in COMPONENTS:
        card = window.findChild(PlaceholderCard, f"component-{spec.key}")
        assert card is not None, spec.key
        assert 0 <= spec.phase <= 7
    assert [spec.phase for spec in COMPONENTS if spec.factory is not None] == [0, 0, 0, 0, 0]


def test_catalog_renders_glass_stage(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    image = window.grab().toImage()
    assert not image.isNull()
    assert image.width() >= 1000
    assert image.height() >= 700
    sampled = {
        image.pixelColor(x, y).name()
        for x in range(0, image.width(), 24)
        for y in range(0, image.height(), 24)
    }
    assert len(sampled) > 15
    assert image.pixelColor(8, 8).name() == "#070d0f"


def test_catalog_high_contrast(qtbot) -> None:  # type: ignore[no-untyped-def]
    config = with_display_overrides(AppConfig.default(), high_contrast=True)
    window = _show(qtbot, CatalogWindow(config=config))
    assert window.theme.high_contrast is True
    assert window.theme.palette.stage.name() == "#000000"
    assert window.theme.palette.text.name() == "#ffffff"


def test_catalog_window_is_not_the_product_overlay(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    flags = window.windowFlags()
    assert not flags & Qt.WindowType.WindowTransparentForInput
    assert not flags & Qt.WindowType.WindowStaysOnTopHint
    assert not flags & Qt.WindowType.FramelessWindowHint


def test_glass_controls_have_accessible_names(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    buttons = window.findChildren(GlassButton)
    assert {button.text() for button in buttons} == {"PILIH", "BATAL"}
    for button in buttons:
        assert button.minimumHeight() >= 44
        assert button.accessibleName() == button.text()
    close = window.findChild(IconButton)
    assert close is not None
    assert close.width() >= 44 and close.height() >= 44
    assert close.accessibleName() == "Tutup"
    assert METRICS.min_target >= 56


def test_cursor_variants_exist(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    for mode in (CursorPreview.MODE_FREE, CursorPreview.MODE_PINCH, CursorPreview.MODE_DWELL):
        preview = window.findChild(CursorPreview, f"cursor-{mode}")
        assert preview is not None, mode
        assert preview.width() == 132 and preview.height() == 132


def test_toast_and_hint_present(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    toast = window.findChild(ToastPreview)
    hint = window.findChild(HintBar)
    assert toast is not None and toast.width() == METRICS.toast_width
    assert hint is not None and hint.height() == METRICS.hint_height
    assert "CUBIT" in hint.TEXT


def test_glass_frames_render(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = _show(qtbot, CatalogWindow())
    frames = window.findChildren(GlassFrame)
    assert len(frames) >= 8
    for frame in frames:
        assert frame.width() > 0 and frame.height() > 0
