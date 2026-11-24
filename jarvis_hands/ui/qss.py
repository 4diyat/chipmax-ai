"""QSS bersama untuk dialog dan jendela kontrol, dibangun dari token Glass Stage.

Semua warna diambil dari :class:`jarvis_hands.ui.tokens.Theme` (normal atau
kontras tinggi); tidak ada hex literal di sini. ``dialog_qss`` dipanggil ulang
saat tema berubah sehingga dialog ikut memakai palet kontras tinggi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtWidgets import QFormLayout, QLabel

from jarvis_hands.ui.tokens import FONT, Theme, build_theme, mono_font

__all__ = ["SETTINGS_QSS", "dialog_qss", "style_form_labels"]

#: Ikon SVG kecil untuk panah combo/spinbox (dibundel sebagai data aplikasi).
_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"


def _icon(name: str) -> str:
    """Path ikon untuk ``url()`` QSS (slash maju di semua platform)."""
    return (_ICON_DIR / name).as_posix()


def _rgba(color_hex: str, alpha: float) -> str:
    """``#RRGGBB`` + alpha menjadi ``rgba(r, g, b, a)`` untuk QSS."""
    text = color_hex.lstrip("#")
    red, green, blue = (int(text[index : index + 2], 16) for index in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {max(0.0, min(1.0, alpha)):.3f})"


def dialog_qss(theme: Theme) -> str:
    """Bangun stylesheet dialog dari tema aktif.

    Ukuran target mengikuti metrik aksesibilitas: kontrol minimal 44 px tinggi,
    sudut 12 px (satu tingkat di bawah radius kaca 20 px untuk panel).
    """
    p = theme.palette
    radius = theme.style.control_radius
    stage = p.stage.name()
    text = p.text.name()
    muted = p.muted.name()
    teal = p.teal.name()
    accent = p.accent.name()
    hot_rim = p.hot_rim.name()
    border = p.border.name()
    return f"""
QDialog, QWidget {{ background: {stage}; color: {text}; }}
QLabel {{ color: {muted}; background: transparent; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: {_rgba(stage, 0.55)}; color: {text};
    border: 1px solid {_rgba(border, 0.55)}; border-radius: {radius:.0f}px;
    padding: 0 10px; min-height: 44px;
    selection-background-color: {_rgba(teal, 0.35)};
    selection-color: {text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {teal};
}}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
    color: {_rgba(muted, 0.55)}; border-color: {_rgba(border, 0.25)};
    background: {_rgba(stage, 0.30)};
}}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{
    image: url("{_icon("chevron-down.svg")}"); width: 10px; height: 6px;
}}
QSpinBox, QDoubleSpinBox {{ padding-right: 26px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border; subcontrol-position: top right;
    width: 24px; border: none; background: transparent;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right;
    width: 24px; border: none; background: transparent;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("{_icon("chevron-up.svg")}"); width: 10px; height: 6px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("{_icon("chevron-down.svg")}"); width: 10px; height: 6px;
}}
QComboBox QAbstractItemView {{
    background: {stage}; color: {text};
    border: 1px solid {_rgba(border, 0.55)};
    selection-background-color: {_rgba(teal, 0.30)};
    selection-color: {text};
    outline: 0;
}}
QPushButton, QToolButton {{
    background: {_rgba(teal, 0.08)}; color: {text};
    border: 1px solid {_rgba(border, 0.55)}; border-radius: {radius:.0f}px;
    padding: 0 16px; min-height: 44px;
}}
QPushButton:hover, QToolButton:hover {{
    background: {_rgba(teal, 0.16)}; border-color: {teal};
}}
QPushButton:pressed, QToolButton:pressed {{
    background: {_rgba(teal, 0.26)};
}}
QPushButton:checked, QToolButton:checked {{
    background: {_rgba(teal, 0.22)}; border: 1px solid {teal}; color: {hot_rim};
}}
QPushButton:disabled, QToolButton:disabled {{
    color: {_rgba(muted, 0.50)}; border-color: {_rgba(border, 0.22)};
    background: transparent;
}}
QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border-radius: 4px;
    border: 1px solid {_rgba(border, 0.55)};
    background: {_rgba(stage, 0.55)};
}}
QCheckBox::indicator:hover {{ border-color: {teal}; }}
QCheckBox::indicator:checked {{
    background: {_rgba(teal, 0.22)}; border: 1px solid {teal};
    image: url("{_icon("check.svg")}");
}}
QCheckBox::indicator:disabled, QCheckBox::indicator:checked:disabled {{
    border-color: {_rgba(border, 0.25)}; background: transparent; image: none;
}}
QCheckBox:disabled {{ color: {_rgba(muted, 0.50)}; }}
QGroupBox {{
    border: 1px solid {_rgba(border, 0.35)}; border-radius: {radius:.0f}px;
    margin-top: 14px; padding-top: 12px; font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {accent};
    background: {stage};
}}
QScrollArea, QStackedWidget, QFrame {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {_rgba(teal, 0.22)}; min-height: 32px; border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{ background: {_rgba(teal, 0.45)}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QToolTip {{
    color: {text}; background-color: {stage};
    border: 1px solid {_rgba(border, 0.55)}; padding: 6px;
}}
"""


#: Style dialog tema bawaan (kompatibilitas untuk pemanggil lama).
SETTINGS_QSS: Final[str] = dialog_qss(build_theme())


def style_form_labels(form: QFormLayout) -> None:
    """Samakan label ``QFormLayout`` ke mono label kapital dari token."""
    font = mono_font(FONT.label)
    for index in range(form.rowCount()):
        item = form.itemAt(index, QFormLayout.ItemRole.LabelRole)
        widget = item.widget() if item is not None else None
        if isinstance(widget, QLabel):
            widget.setFont(font)
