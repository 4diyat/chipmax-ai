"""Kasus tepi komponen kaca fase 4."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QWidget

from jarvis_hands.core.state import Status
from jarvis_hands.memory.tree import MemoryPathError, MemoryTree
from jarvis_hands.ui.card import Card, Panel
from jarvis_hands.ui.glass import SurfaceHit
from jarvis_hands.ui.orb import Orb


def test_card_stale_fling_and_small_bounds(qtbot) -> None:  # type: ignore[no-untyped-def]
    clock = [0.0]
    parent = QWidget()
    card = Card("test", clock=lambda: clock[0], parent=parent)
    qtbot.addWidget(parent)
    card.set_bounds(QRectF(0, 0, 100, 100))
    card.set_home(300, 300)
    assert card.home.x() == 0 and card.home.y() == 0
    assert card.hit_test(QPointF(0, 0)) == SurfaceHit.NONE
    card.begin_drag(QPointF(0, 0))
    clock[0] = 0.01
    card.update_drag(QPointF(100, 0))
    clock[0] = 1.0
    assert not card.end_drag()
    panel = Panel()
    qtbot.addWidget(panel)
    panel.resize(300, 300)
    panel.set_bounds(QRectF(0, 0, 100, 100))
    panel.move(10, 10)
    panel.begin_drag(QPointF(10, 10))
    panel.update_drag(QPointF(50, 50))
    assert panel.x() == 0 and panel.y() == 0


def test_orb_rotation_peak_and_timer(qtbot) -> None:  # type: ignore[no-untyped-def]
    clock = [0.0]
    orb = Orb(clock=lambda: clock[0])
    qtbot.addWidget(orb)
    orb.show()
    assert orb.is_animating()
    clock[0] = 0.1
    orb._tick()
    assert orb.rotation == pytest.approx(1.0)
    orb.set_status(Status.SPEAKING)
    orb.set_level(0.8)
    assert orb.normalized_level() == pytest.approx(1)
    orb.set_level(0.2)
    assert orb.normalized_level() == pytest.approx(0.25)
    orb.set_status(Status.SENYAP)
    assert not orb.is_animating()
    orb.set_status(Status.IDLE)
    assert orb.is_animating()
    orb.hide()
    assert not orb.is_animating()


def test_nested_symlink_and_missing(tmp_path: Path) -> None:
    root = tmp_path / "memory"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("secret", encoding="utf-8")
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink tidak tersedia")
    tree = MemoryTree(root)
    with pytest.raises(MemoryPathError):
        tree.read_preview("link/secret")
    with pytest.raises(MemoryPathError):
        tree.list_dir("link")
    with pytest.raises(MemoryPathError):
        tree.read_preview("missing")
