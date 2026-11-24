"""Guard statis design system: warna dan huruf hanya boleh berasal dari token.

Modul UI boleh memakai palet ``Theme`` dan helper ``with_alpha``/``sans_font``/
``mono_font``, tetapi tidak boleh memakai hex literal atau ukuran huruf angka
lepas. ``tokens.py`` adalah satu-satunya sumber warna; ``qss.py`` membangun
stylesheet dari palet.
"""

from __future__ import annotations

import re
from pathlib import Path

UI_DIR = Path(__file__).resolve().parents[1] / "ui"
_SKIP = {"tokens.py", "qss.py"}
_HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
_FONT_LITERAL = re.compile(r"\b(?:sans_font|mono_font)\(\s*\d")
_FONT_SIZE_QSS = re.compile(r"font-size\s*:")


def _ui_modules() -> list[Path]:
    return [path for path in sorted(UI_DIR.glob("*.py")) if path.name not in _SKIP]


def test_no_hex_literals_outside_tokens() -> None:
    offenders: list[str] = []
    for path in _ui_modules():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _HEX.search(line):
                offenders.append(f"{path.name}:{number}")
    assert not offenders, offenders


def test_no_off_scale_font_sizes() -> None:
    offenders: list[str] = []
    for path in _ui_modules():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _FONT_LITERAL.search(line) or _FONT_SIZE_QSS.search(line):
                offenders.append(f"{path.name}:{number}")
    assert not offenders, offenders


def test_tokens_module_is_the_only_hex_source() -> None:
    assert (UI_DIR / "tokens.py").is_file()
    text = (UI_DIR / "tokens.py").read_text(encoding="utf-8")
    assert "HEX: Final[dict[str, str]]" in text
