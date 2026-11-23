"""Tes komponen fase 4, termasuk batas baca memori dan gerak."""

from __future__ import annotations

import math
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QTreeWidget, QWidget

from jarvis_hands.core.state import Status
from jarvis_hands.memory.tree import MemoryPathError, MemoryPathReason, MemoryTree, NodeKind
from jarvis_hands.ui.card import Card, Panel
from jarvis_hands.ui.catalog import COMPONENTS, CatalogWindow, PlaceholderCard
from jarvis_hands.ui.glass import SurfaceHit
from jarvis_hands.ui.orb import Orb
from jarvis_hands.ui.physics import SpringConfig, SpringMotion
from jarvis_hands.ui.treepane import TreePane


def test_spring_converges_consistently_and_obeys_bounds() -> None:
    positions = []
    for fps in (30, 60, 120):
        spring = SpringMotion(x=200)
        spring.set_target(0, 0)
        for _ in range(fps):
            spring.step(1 / fps)
        assert spring.settled
        positions.append(spring.x)
    assert max(positions) - min(positions) < 0.01
    spring.set_bounds(0, 0, 100, 100)
    spring.set_target(1000, -50)
    assert spring.target == (100, 0)
    spring.fling(9000, 9000)
    assert math.hypot(spring.vx, spring.vy) <= spring.config.max_speed + 1e-6
    for _ in range(120):
        spring.step(1 / 60)
        assert 0 <= spring.x <= 100 and 0 <= spring.y <= 100
    assert spring.settled


def test_spring_configuration_validation() -> None:
    for kwargs in ({"stiffness": 0}, {"damping": 2}, {"max_speed": 0}, {"rest_threshold": 0}):
        with pytest.raises(ValueError):
            SpringConfig(**kwargs)


def test_memory_listing_and_preview(tmp_path: Path) -> None:
    (tmp_path / "project").mkdir()
    (tmp_path / "project" / "notes.md").write_text("Halo dunia", encoding="utf-8")
    (tmp_path / ".hidden").write_text("secret", encoding="utf-8")
    tree = MemoryTree(tmp_path)
    assert [e.name for e in tree.list_dir()] == ["project"]
    assert tree.root_node().is_folder
    assert tree.children_of(tree.root_node())[0].kind == NodeKind.FOLDER
    assert tree.read_preview("project/notes.md") == "Halo dunia"
    assert tree.read_preview("project\\notes.md") == "Halo dunia"


@pytest.mark.parametrize(
    "path",
    [
        "../secret",
        "a/../../secret",
        "/etc/passwd",
        "/",
        "C:/outside",
        "\\\\server\\share",
        "x:stream",
        "x\0y",
    ],
)
def test_memory_rejects_unsafe_paths(tmp_path: Path, path: str) -> None:
    with pytest.raises(MemoryPathError):
        MemoryTree(tmp_path).resolve(path)


def test_memory_symlinks_are_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    try:
        (root / "link").symlink_to(tmp_path / "outside.txt")
    except OSError:
        pytest.skip("symlink tidak tersedia di sistem ini")
    tree = MemoryTree(root)
    assert tree.list_dir() == []
    with pytest.raises(MemoryPathError) as exc:
        tree.read_preview("link")
    assert exc.value.reason == MemoryPathReason.SYMLINK


def test_memory_size_binary_unicode_and_limits(tmp_path: Path) -> None:
    (tmp_path / "utf8").write_text("éééé", encoding="utf-8")
    (tmp_path / "binary").write_bytes(b"abc\x00def")
    (tmp_path / "big").write_bytes(b"a" * 20)
    tree = MemoryTree(tmp_path, preview_bytes=3, max_file_bytes=10)
    assert tree.read_preview("utf8") == "é\n…"
    with pytest.raises(MemoryPathError) as exc:
        tree.read_preview("big")
    assert exc.value.reason == MemoryPathReason.TOO_LARGE
    with pytest.raises(MemoryPathError) as exc:
        MemoryTree(tmp_path).read_preview("binary")
    assert exc.value.reason == MemoryPathReason.BINARY
    assert len(MemoryTree(tmp_path, max_entries=3).list_dir()) == 3
    with pytest.raises(MemoryPathError):
        MemoryTree(tmp_path, max_entries=2).list_dir()


def test_posix_race_symlink_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if os.name != "posix":
        pytest.skip("descriptor nofollow hanya pada POSIX")
    root = tmp_path / "root"
    root.mkdir()
    file = root / "file"
    file.write_text("normal", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.write_text("secret", encoding="utf-8")
    tree = MemoryTree(root)
    original = tree.resolve

    def swap(rel: str) -> Path:
        result = original(rel)
        file.unlink()
        file.symlink_to(outside)
        return result

    monkeypatch.setattr(tree, "resolve", swap)
    with pytest.raises(MemoryPathError):
        tree.read_preview("file")


def test_card_drag_and_close(qtbot) -> None:  # type: ignore[no-untyped-def]
    now = [0.0]
    parent = QWidget()
    parent.resize(900, 700)
    card = Card("Catatan", clock=lambda: now[0], parent=parent)
    qtbot.addWidget(parent)
    card.set_home(50, 50)
    parent.show()
    assert card.hit_test(card.handle_rect().center()) == SurfaceHit.HANDLE
    assert card.hit_test(card.close_rect().center()) == SurfaceHit.CLOSE
    assert card.begin_drag(QPointF(50, 50))
    now[0] = 0.1
    card.update_drag(QPointF(80, 50))
    now[0] = 0.2
    card.update_drag(QPointF(100, 50))
    assert card.velocity.x() == pytest.approx(200)
    assert not card.end_drag()
    for _ in range(120):
        now[0] += 1 / 60
        card._tick()
    assert card.pos() == QPoint(50, 50)
    assert not card.is_animating
    with qtbot.waitSignal(card.close_requested, timeout=1000):
        qtbot.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.close_rect().center().toPoint())


def test_card_fling_dismiss(qtbot) -> None:  # type: ignore[no-untyped-def]
    now = [1.0]
    card = Card("Uji", clock=lambda: now[0])
    qtbot.addWidget(card)
    card.show()
    card.begin_drag(QPointF(0, 0))
    card.update_drag(QPointF(0, 0), timestamp=1)
    now[0] = 1.01
    card.update_drag(QPointF(100, 0), timestamp=1.01)
    with qtbot.waitSignal(card.dismissed, timeout=1000):
        assert card.end_drag()
    assert card.isHidden()


def test_panel_and_orb(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = Panel("Catatan", chips=("DRAF", "LOKAL"))
    qtbot.addWidget(panel)
    panel.resize(600, 300)
    panel.show()
    assert panel.close_rect().width() == 44
    assert panel.hit_test(panel.handle_rect().center()) == SurfaceHit.HANDLE
    with qtbot.waitSignal(panel.close_requested, timeout=1000):
        qtbot.mouseClick(panel._close, Qt.MouseButton.LeftButton)
    orb = Orb()
    qtbot.addWidget(orb)
    orb.show()
    assert orb.petal_count == 5 and orb.size_px == 112
    for status in Status:
        orb.set_status(status)
        assert status.label in orb.accessibleDescription()
        assert not orb.grab().isNull()
    assert not orb.is_animating()


def test_treepane_real_and_sample(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "hello.txt").write_text("Teks lokal", encoding="utf-8")
    pane = TreePane(tmp_path)
    qtbot.addWidget(pane)
    pane.resize(800, 400)
    pane.show()
    tree = pane.findChild(QTreeWidget, "memory-tree")
    assert tree is not None
    root = tree.topLevelItem(0)
    assert root is not None
    assert root.childCount() == 1
    child = root.child(0)
    assert child is not None
    tree.setCurrentItem(child)
    preview = pane.findChild(QPlainTextEdit, "memory-preview")
    assert preview is not None and preview.toPlainText() == "Teks lokal"
    assert pane.findChild(QLabel, "memory-safety") is not None
    sample = TreePane()
    qtbot.addWidget(sample)
    assert sample.memory is None
    assert not sample.grab().isNull()


def test_catalog_phase4_ready(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = CatalogWindow()
    qtbot.addWidget(window)
    for key in ("card", "panel", "orb", "tree_pane"):
        spec = next(x for x in COMPONENTS if x.key == key)
        assert spec.ready and spec.factory is not None
        widget = spec.factory(window.theme)
        qtbot.addWidget(widget)
        assert isinstance(widget, QWidget)
        marker = window.findChild(PlaceholderCard, f"component-{key}")
        assert marker is not None
        assert "SIAP" in [label.text() for label in marker.findChildren(QLabel)]
