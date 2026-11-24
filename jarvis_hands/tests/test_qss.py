"""Tes QSS bersama: token, tema kontras tinggi, dan ikon panah."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit

from jarvis_hands.ui.qss import SETTINGS_QSS, dialog_qss, style_form_labels
from jarvis_hands.ui.tokens import FONT, build_theme

ROOT = Path(__file__).resolve().parents[2]


def test_dialog_qss_uses_palette_tokens() -> None:
    qss = dialog_qss(build_theme())
    assert "#070d0f" in qss
    assert "#ecfffa" in qss
    assert "min-height: 44px" in qss
    assert "border-radius: 12px" in qss


def test_dialog_qss_follows_high_contrast() -> None:
    qss = dialog_qss(build_theme(high_contrast=True))
    assert "#000000" in qss
    assert "#ffffff" in qss
    assert "#070d0f" not in qss


def test_settings_qss_is_the_default_theme() -> None:
    assert dialog_qss(build_theme()) == SETTINGS_QSS


def test_chevron_icons_are_bundled_and_referenced() -> None:
    icons = ROOT / "jarvis_hands" / "assets" / "icons"
    assert (icons / "chevron-down.svg").is_file()
    assert (icons / "chevron-up.svg").is_file()
    assert (icons / "check.svg").is_file()
    qss = dialog_qss(build_theme())
    assert "chevron-down.svg" in qss
    assert "chevron-up.svg" in qss
    assert "check.svg" in qss


def test_style_form_labels_applies_mono_label(qapp: object) -> None:
    del qapp
    form = QFormLayout()
    field = QLineEdit()
    form.addRow("MODE TAMPILAN", field)
    style_form_labels(form)
    item = form.itemAt(0, QFormLayout.ItemRole.LabelRole)
    assert item is not None
    label = item.widget()
    assert isinstance(label, QLabel)
    assert label.font().pointSize() == FONT.label
