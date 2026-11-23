"""Titik masuk aplikasi: argumen CLI, QApplication, dan wiring katalog.

Fase 0 hanya membuka halaman katalog. Flag mode tampil (``--mode``, ``--key``)
ditambahkan di Fase 5 saat ketiga mode benar-benar tersedia; di sini sengaja
tidak ada flag mati.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from jarvis_hands import __version__
from jarvis_hands.core.config import (
    AppConfig,
    ConfigError,
    load_config,
    with_display_overrides,
)
from jarvis_hands.ui.catalog import CatalogWindow
from jarvis_hands.ui.tokens import apply_theme, build_theme

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """Parser CLI Fase 0."""
    parser = argparse.ArgumentParser(
        prog="jarvis-hands",
        description="JARVIS Ring & Hands - antarmuka kaca gestur tangan.",
    )
    parser.add_argument("--version", action="version", version=f"jarvis-hands {__version__}")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path konfigurasi JSON (opsional; bawaan memakai lokasi platform)",
    )
    parser.add_argument(
        "--high-contrast",
        action="store_true",
        help="paksa tema kontras tinggi",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Jalankan aplikasi. Mengembalikan exit code."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config) if args.config is not None else AppConfig.default()
        if args.high_contrast:
            config = with_display_overrides(config, high_contrast=True)
    except ConfigError as exc:
        print(f"jarvis-hands: konfigurasi tidak valid: {exc}", file=sys.stderr)
        return 2

    instance = QApplication.instance()
    if isinstance(instance, QApplication):
        app = instance
    else:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication([sys.argv[0]])
    _configure(app, config)

    window = CatalogWindow(config=config)
    window.show()
    return app.exec()


def _configure(app: QApplication, config: AppConfig) -> None:
    app.setApplicationName("JARVIS Ring & Hands")
    app.setApplicationDisplayName("JARVIS")
    app.setOrganizationName("Chipmax")
    apply_theme(app, build_theme(config.display.high_contrast))
