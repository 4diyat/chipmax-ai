"""Tes overlay: mode, privasi, koordinat, dan perutean gestur."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QTreeWidget

from jarvis_hands.app import build_parser, main
from jarvis_hands.core.config import AppConfig, DisplayMode, KeyColor
from jarvis_hands.gestures.types import GestureEvent, GestureKind, GesturePhase
from jarvis_hands.tests.support import make_hand, make_result
from jarvis_hands.tests.test_session import make_session
from jarvis_hands.ui.overlay import ControlWindow, OverlayWindow
from jarvis_hands.vision.camera import Frame


def make_overlay(qtbot: Any, qapp: QApplication, config: AppConfig | None = None) -> Any:
    session, controller, backend, indicator = make_session()
    overlay = OverlayWindow(config or AppConfig.default(), session, qapp.primaryScreen())
    qtbot.addWidget(overlay)
    qtbot.addWidget(indicator)
    overlay.show()
    qtbot.wait(1)
    return overlay, session, controller, backend


def test_cli_modes_and_invalid_key(capsys: Any) -> None:
    args = build_parser().parse_args(["--mode", "key", "--key", "#abc", "--monitor", "1"])
    assert (args.mode, args.key, args.monitor) == ("key", "#abc", 1)
    assert main(["--key", "invalid"]) == 2
    assert "konfigurasi tidak valid" in capsys.readouterr().err


def test_overlay_flags_modes_and_key_color(qtbot: Any, qapp: QApplication) -> None:
    config = AppConfig.default()
    config = replace(config, display=replace(config.display, key_color=KeyColor.GREEN))
    overlay, session, _, _ = make_overlay(qtbot, qapp, config)
    assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert overlay.grab().toImage().pixelColor(2, 2).alpha() == 0
    assert not session.is_active
    overlay.set_mode(DisplayMode.KEY)
    assert not (overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput)
    image = overlay.grab().toImage()
    assert image.pixelColor(2, 2) == QColor("#00ff00")
    overlay.set_mode(DisplayMode.OVERLAY)
    assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
    overlay.close()


def test_mirror_frame_copied_and_cleared(qtbot: Any, qapp: QApplication) -> None:
    overlay, session, _, _ = make_overlay(qtbot, qapp)
    overlay.set_mode(DisplayMode.MIRROR)
    data = np.zeros((4, 5, 3), dtype=np.uint8)
    data[:, :] = [255, 12, 34]
    frame = Frame(data, 5, 4, 1)
    overlay.on_frame(frame)
    assert overlay._image.isNull()
    session.start()
    overlay.on_frame(frame)
    data[:] = 0
    assert overlay._image.pixelColor(0, 0) == QColor(255, 12, 34)
    session.set_paused(True)
    assert overlay._image.isNull()
    overlay.on_frame(frame)
    assert overlay._image.isNull()
    session.set_paused(False)
    overlay.on_frame(frame)
    session.stop()
    assert overlay._image.isNull()
    overlay.close()


def test_negative_monitor_origin(qtbot: Any, qapp: QApplication) -> None:
    overlay, session, _, _ = make_overlay(qtbot, qapp)
    overlay.set_screen_geometry(QRect(-1200, -80, 1200, 800))
    assert overlay.geometry() == QRect(-1200, -80, 1200, 800)
    session.start()
    overlay.on_tracking(make_result(make_hand(index=(0.5, 0.5)), timestamp_ms=10))
    assert overlay.hand_cursor.center == QPoint(-600, 320)
    assert overlay.hand_cursor.isVisible()
    overlay.on_tracking(make_result(None, timestamp_ms=20))
    assert not overlay.hand_cursor.isVisible()
    session.stop()
    overlay.close()


def test_landmarks_to_tap_and_hold(qtbot: Any, qapp: QApplication) -> None:
    config = AppConfig.default()
    config = replace(config, cursor=replace(config.cursor, gain=1.0))
    overlay, session, _, _ = make_overlay(qtbot, qapp, config)
    session.start()
    pos = overlay.card.mapToGlobal(overlay.card.surface_rect().center().toPoint())
    geo = overlay.geometry()
    xy = ((pos.x() - geo.x()) / geo.width(), (pos.y() - geo.y()) / geo.height())
    closed = make_hand(index=xy, pinch_ratio=0.1)
    opened = make_hand(index=xy, pinch_ratio=0.7)
    overlay.on_tracking(make_result(closed, timestamp_ms=100))
    overlay.on_tracking(make_result(opened, timestamp_ms=220))
    assert overlay.tree.isVisible()
    overlay.tree.hide()
    overlay.on_tracking(make_result(closed, timestamp_ms=1000))
    overlay.on_tracking(make_result(closed, timestamp_ms=2001))
    assert overlay.tree.isVisible()
    assert overlay.hand_cursor.dwell == pytest.approx(1)
    session.set_paused(True)
    assert not overlay.hand_cursor.isVisible()
    session.stop()
    overlay.close()


def test_drag_cancel_and_tree_tap(qtbot: Any, qapp: QApplication) -> None:
    overlay, session, _, _ = make_overlay(qtbot, qapp)
    session.start()
    start = overlay.card.mapToGlobal(overlay.card.surface_rect().center().toPoint())
    overlay._press_target = overlay.card
    overlay._pinch_started = 0
    overlay._route(GestureEvent(GestureKind.DRAG, GesturePhase.BEGIN, 0, start.x(), start.y()))
    overlay._route(
        GestureEvent(GestureKind.DRAG, GesturePhase.UPDATE, 10, start.x() - 40, start.y())
    )
    assert overlay.card.is_dragging
    overlay._route(
        GestureEvent(
            GestureKind.DRAG, GesturePhase.END, 20, start.x() - 40, start.y(), cancelled=True
        )
    )
    assert not overlay.card.is_dragging
    overlay.tree.show()
    tree = overlay.tree.findChild(QTreeWidget, "memory-tree")
    assert tree is not None
    item = tree.topLevelItem(0)
    assert item is not None
    point = tree.viewport().mapToGlobal(tree.visualItemRect(item).center())
    overlay._tree_tap(point)
    assert tree.currentItem() == item
    session.stop()
    overlay.close()


def test_control_has_safe_exit_and_camera_off(qtbot: Any, qapp: QApplication) -> None:
    control = ControlWindow(AppConfig.default(), qapp.screens())
    qtbot.addWidget(control)
    control.show()
    assert not control.session.is_active
    control.overlay.card.hide()
    control._show_card()
    assert control.overlay.card.isVisible()
    control.close()
    assert not control.overlay.isVisible()


def test_landmark_drag_is_cancelled_when_hand_lost(qtbot: Any, qapp: QApplication) -> None:
    config = AppConfig.default()
    config = replace(config, cursor=replace(config.cursor, gain=1.0))
    overlay, session, _, _ = make_overlay(qtbot, qapp, config)
    session.start()
    pos = overlay.card.mapToGlobal(overlay.card.surface_rect().center().toPoint())
    geo = overlay.geometry()
    xy = ((pos.x() - geo.x()) / geo.width(), (pos.y() - geo.y()) / geo.height())
    overlay.on_tracking(make_result(make_hand(index=xy, pinch_ratio=0.1), timestamp_ms=100))
    moved = (max(0.01, xy[0] - 0.20), xy[1])
    overlay.on_tracking(make_result(make_hand(index=moved, pinch_ratio=0.1), timestamp_ms=300))
    assert overlay.card.is_dragging
    overlay.on_tracking(make_result(None, timestamp_ms=400))
    assert not overlay.card.is_dragging
    assert overlay.card.isVisible()
    session.stop()
    overlay.close()


def test_managed_overlay_close_closes_control(qtbot: Any, qapp: QApplication) -> None:
    control = ControlWindow(AppConfig.default(), qapp.screens())
    qtbot.addWidget(control)
    control.show()
    control.overlay.close()
    qtbot.waitUntil(lambda: not control.isVisible(), timeout=1000)
    assert not control.overlay.isVisible()
