"""Render komponen Glass Stage ke PNG untuk membandingkan dengan docs/mockups.

Skrip ini hanya alat bantu pemeriksaan visual (bukan bagian runtime):

    QT_QPA_PLATFORM=offscreen .venv/bin/python tools/visual_check.py out/

Hasil ditulis ke direktori pertama argumen (bawaan: .artifacts/visual).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jarvis_hands.tests.conftest  # noqa: E402,F401  (muat stub Qt sebelum PySide6)
import numpy as np  # noqa: E402
from jarvis_hands.agent.settings import AgentSettings, CredentialStore  # noqa: E402
from jarvis_hands.core.config import AppConfig, DisplayMode  # noqa: E402
from jarvis_hands.core.state import Status  # noqa: E402
from jarvis_hands.ui.agent_settings import AgentSettingsPage  # noqa: E402
from jarvis_hands.ui.camera import CameraIndicator  # noqa: E402
from jarvis_hands.ui.card import Card, Panel  # noqa: E402
from jarvis_hands.ui.orb import Orb  # noqa: E402
from jarvis_hands.ui.ring import RingWidget  # noqa: E402
from jarvis_hands.ui.settings import SettingsDialog  # noqa: E402
from jarvis_hands.ui.tokens import build_theme, paint_stage  # noqa: E402
from jarvis_hands.ui.treepane import TreePane  # noqa: E402
from jarvis_hands.vision.camera import Frame  # noqa: E402
from jarvis_hands.vision.session import CameraSession  # noqa: E402
from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtGui import QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / ".artifacts" / "visual")

THEME = build_theme()


class Stage(QWidget):
    """Panggung latar token stage + glow."""

    def __init__(self, size: QSize) -> None:
        super().__init__()
        self.setFixedSize(size)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPainter

        painter = QPainter(self)
        paint_stage(painter, QRectF(self.rect()), THEME)
        painter.end()


class FakeSource:
    """Sumber frame sintetis (kamera palsu)."""

    def __init__(self) -> None:
        self.width = 640
        self.height = 360
        self.reads = 0
        self.released = 0

    def open(self) -> None:
        return None

    def read(self) -> Frame | None:
        self.reads += 1
        rgb = np.zeros((360, 640, 3), dtype=np.uint8)
        return Frame(rgb=rgb, timestamp_ms=self.reads * 33, index=self.reads)

    def release(self) -> None:
        self.released += 1


class FakeTracker:
    def __init__(self) -> None:
        self.closed = 0

    def process(self, frame: Frame) -> object:
        from jarvis_hands.vision.tracker import TrackingResult

        return TrackingResult(
            hands=(), timestamp_ms=frame.timestamp_ms, width=frame.width, height=frame.height
        )

    def close(self) -> None:
        self.closed += 1


def grab(widget: QWidget, name: str, *, background: bool = True) -> Path:
    """Ambil widget lalu tempel di atas panggung gelap (seperti overlay nyata)."""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    widget.show()
    QApplication.processEvents()
    shot = widget.grab().toImage()
    canvas = QImage(shot.size(), QImage.Format.Format_ARGB32_Premultiplied)
    canvas.fill(THEME.palette.stage)
    painter = QPainter(canvas)
    paint_stage(painter, QRectF(0, 0, shot.width(), shot.height()), THEME)
    painter.drawImage(0, 0, shot)
    painter.end()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.png"
    canvas.save(str(path))
    return path


def main() -> None:
    app = QApplication.instance() or QApplication([])
    print("font sans:", QFontDatabase.families()[:0] or "n/a")
    from jarvis_hands.ui.tokens import MONO_CANDIDATES, SANS_CANDIDATES, resolve_family

    print("sans:", resolve_family(SANS_CANDIDATES), "| mono:", resolve_family(MONO_CANDIDATES))

    # 1. Kartu + panel tunggal
    card = Card(
        "Kartu 01 · catatan",
        "Baris tebal sebagai target ketuk; pegangan 48x4 di atas kartu.",
        chip="DRAF",
        theme=THEME,
    )
    grab(card, "card")

    panel = Panel(
        "Panel · catatan",
        chips=("DRAF", "LOKAL"),
        theme=THEME,
    )
    panel.resize(700, 300)
    label = _label("Sesi 03 — kalibrasi ambang\n\nPanel kaca berisi catatan sesi.")
    panel.body().addWidget(label)
    grab(panel, "panel", background=True)

    # 2. Orb
    orb = Orb(THEME)
    grab(orb, "orb")

    # 3. Ring
    ring = RingWidget(THEME)
    ring.set_status(Status.THINKING)
    ring.resize(QSize(440, 440))
    grab(ring, "ring")

    # 4. TreePane
    tree = TreePane(theme=THEME)
    tree.resize(900, 460)
    grab(tree, "treepane", background=True)

    # 5. Indikator kamera
    indicator = CameraIndicator(THEME)
    indicator.set_active(True)
    indicator.set_fps(30)
    grab(indicator, "camera_indicator")

    # 6. Halaman Agen & API (lebar dialog)
    store = CredentialStore()
    page = AgentSettingsPage(AgentSettings(), store, theme=THEME, embedded=True)
    page.resize(760, 620)
    grab(page, "agent_page", background=True)

    # 7. Dialog pengaturan penuh
    dialog = SettingsDialog(AppConfig.default(), AgentSettings(), store, theme=THEME)
    dialog.show()
    QApplication.processEvents()
    path = OUT / "settings_dialog.png"
    dialog.grab().save(str(path))
    dialog.close()

    # 8. Komposisi overlay (ring + orb + card + tree + indikator)
    from dataclasses import replace

    base = AppConfig.default()

    # Mode MIRROR: latar panggung gelap (mode overlay asli transparan penuh).
    config = replace(base, display=replace(base.display, mode=DisplayMode.MIRROR))
    session = CameraSession(config.camera)
    from jarvis_hands.ui.overlay import OverlayWindow

    overlay = OverlayWindow(config, session, app.primaryScreen())
    overlay.show()
    overlay.resize(1440, 900)
    overlay.indicator.raise_()
    QApplication.processEvents()
    OUT.mkdir(parents=True, exist_ok=True)
    overlay.grab().save(str(OUT / "overlay_composition.png"))
    overlay.tree.show()
    overlay.tree.raise_()
    overlay.indicator.raise_()
    QApplication.processEvents()
    overlay.grab().save(str(OUT / "overlay_with_tree.png"))

    print("ditulis ke", OUT)


def _label(text: str) -> QWidget:
    from jarvis_hands.ui.tokens import FONT, sans_font
    from PySide6.QtWidgets import QLabel

    widget = QLabel(text)
    widget.setFont(sans_font(FONT.body))
    widget.setWordWrap(True)
    widget.setStyleSheet(f"color: {THEME.palette.text.name()};")
    return widget


if __name__ == "__main__":
    main()
