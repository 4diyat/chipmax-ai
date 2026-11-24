"""Titik masuk aplikasi: argumen CLI, kontrol lokal, overlay, dan katalog."""

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
    DisplayMode,
    default_config_path,
    load_config,
    parse_key_color,
    with_display_overrides,
)
from jarvis_hands.memory.tree import MemoryPathError
from jarvis_hands.profiling import run_profile
from jarvis_hands.ui.accessibility import audit_application, format_issues
from jarvis_hands.ui.catalog import CatalogWindow
from jarvis_hands.ui.onboarding import OnboardingDialog
from jarvis_hands.ui.overlay import ControlWindow
from jarvis_hands.ui.tokens import apply_theme, build_theme

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """Parser CLI."""
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
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in DisplayMode],
        default=None,
        help="mode mirror, overlay, atau key",
    )
    parser.add_argument("--key", default=None, help="magenta, green, blue, atau #RRGGBB")
    parser.add_argument("--monitor", type=int, default=0, help="indeks monitor (mulai dari 0)")
    parser.add_argument("--camera", action="store_true", help="aktifkan kamera saat mulai")
    parser.add_argument("--catalog", action="store_true", help="buka katalog komponen")
    parser.add_argument(
        "--no-onboarding",
        action="store_true",
        help="lewati panduan awal kamera dan gestur",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="jalankan benchmark mikro jalur kursor/gestur lalu keluar",
    )
    parser.add_argument(
        "--profile-iterations",
        type=int,
        default=2000,
        help="jumlah iterasi per benchmark (default: 2000)",
    )
    parser.add_argument(
        "--a11y-audit",
        action="store_true",
        help="audit nama aksesibel dan target tombol lalu keluar",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Jalankan aplikasi. Mengembalikan exit code."""
    args = build_parser().parse_args(argv)
    if args.profile:
        print(run_profile(args.profile_iterations).to_markdown())
        return 0
    try:
        config = load_config(args.config)
        config = with_display_overrides(
            config,
            mode=DisplayMode(args.mode) if args.mode else None,
            key=parse_key_color(args.key) if args.key else None,
            high_contrast=True if args.high_contrast else None,
        )
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

    if args.a11y_audit:
        issues = audit_application()
        print(format_issues(issues))
        return 1 if issues else 0

    if args.catalog:
        catalog = CatalogWindow(config=config)
        catalog.show()
        return app.exec()
    screens = app.screens()
    if args.monitor < 0 or args.monitor >= len(screens):
        print(f"jarvis-hands: monitor {args.monitor} tidak tersedia", file=sys.stderr)
        return 2
    config_path = args.config if args.config is not None else default_config_path()
    if not config.onboarding_done and not args.no_onboarding:
        guide = OnboardingDialog(config, config_path=config_path)
        if guide.exec():
            config = guide.config
    try:
        window = ControlWindow(config, screens, monitor=args.monitor, config_path=config_path)
    except MemoryPathError as exc:
        print(f"jarvis-hands: memori tidak tersedia: {exc}", file=sys.stderr)
        return 2
    window.show()
    if args.camera:
        window.session.start()
    return app.exec()


def _configure(app: QApplication, config: AppConfig) -> None:
    app.setApplicationName("JARVIS Ring & Hands")
    app.setApplicationDisplayName("JARVIS")
    app.setOrganizationName("Chipmax")
    apply_theme(app, build_theme(config.display.high_contrast))
