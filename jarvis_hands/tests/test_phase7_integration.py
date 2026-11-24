"""Tes integrasi Fase 7: auto-hide overlay, penerapan pengaturan, dan ambang dinamis."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication

from jarvis_hands.core.config import AppConfig, CursorConfig, GestureThresholds
from jarvis_hands.gestures.engine import GestureEngine
from jarvis_hands.tests.support import make_hand, make_result
from jarvis_hands.tests.test_overlay import make_overlay
from jarvis_hands.ui.overlay import ControlWindow
from jarvis_hands.ui.settings import SettingsDialog


def test_autohide_hides_chrome_but_keeps_indicator(qtbot: Any, qapp: QApplication) -> None:
    overlay, session, _controller, _backend = make_overlay(qtbot, qapp)
    assert overlay.ring.isVisible()
    assert overlay.card.isVisible()
    clock = [0.0]
    overlay.autohide._clock = lambda: clock[0]
    overlay.autohide._last_activity = 0.0
    clock[0] = 60.0
    assert overlay.autohide.tick() is True
    assert not overlay.ring.isVisible()
    assert not overlay.orb.isVisible()
    assert not overlay.card.isVisible()
    assert overlay.indicator.isVisible()
    overlay.autohide.poke()
    assert overlay.ring.isVisible()
    assert overlay.orb.isVisible()
    assert overlay.card.isVisible()
    session.stop()
    overlay.close()


def test_overlay_apply_config_updates_engine_and_autohide(qtbot: Any, qapp: QApplication) -> None:
    overlay, session, _controller, _backend = make_overlay(qtbot, qapp)
    config = replace(
        AppConfig.default(),
        gestures=replace(AppConfig.default().gestures, hold_ms=500),
        display=replace(AppConfig.default().display, auto_hide_s=4, auto_hide_enabled=False),
    )
    overlay.apply_config(config)
    assert overlay.config.gestures.hold_ms == 500
    assert overlay.engine._thresholds.hold_ms == 500
    assert overlay.autohide.delay_s == 4
    assert not overlay.autohide.enabled
    session.stop()
    overlay.close()


def test_engine_accepts_new_thresholds_and_cursor_config() -> None:
    engine = GestureEngine()
    first = make_result(make_hand(index=(0.5, 0.5), pinch_ratio=0.5), timestamp_ms=1)
    engine.process(first)
    assert engine.last_sample is not None
    assert bool(engine.last_sample.pinching) is False
    engine.set_thresholds(GestureThresholds(pinch_close=0.6, pinch_open=0.9))
    second = make_result(make_hand(index=(0.5, 0.5), pinch_ratio=0.5), timestamp_ms=100)
    engine.process(second)
    assert engine.last_sample is not None
    assert bool(engine.last_sample.pinching) is True
    engine.set_cursor_config(CursorConfig(gain=3.0))
    assert engine._cursor._config.gain == 3.0


def test_control_settings_apply_display_and_gestures(
    qtbot: Any, qapp: QApplication, tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(
        "jarvis_hands.agent.settings.settings_path", lambda: tmp_path / "agent.json"
    )
    control = ControlWindow(
        AppConfig.default(), qapp.screens(), config_path=tmp_path / "config.json"
    )
    qtbot.addWidget(control)
    control.show()
    control.settings_button.click()
    dialog = control._settings_dialog
    assert isinstance(dialog, SettingsDialog)
    dialog.display_page.auto_hide_s.setValue(9)
    dialog.gesture_page._int_fields["hold_ms"].setValue(750)
    dialog._save()
    assert control.overlay.autohide.delay_s == 9
    assert control.overlay.engine._thresholds.hold_ms == 750
    assert (tmp_path / "config.json").exists()
    dialog.close()
    control.close()


def test_camera_settings_reach_session_for_next_start(
    qtbot: Any, qapp: QApplication, tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(
        "jarvis_hands.agent.settings.settings_path", lambda: tmp_path / "agent.json"
    )
    control = ControlWindow(
        AppConfig.default(), qapp.screens(), config_path=tmp_path / "config.json"
    )
    qtbot.addWidget(control)
    control.show()
    control.settings_button.click()
    dialog = control._settings_dialog
    assert isinstance(dialog, SettingsDialog)
    dialog.camera_page.index.setValue(3)
    dialog.camera_page.frame_width.setValue(1280)
    dialog.camera_page.analysis_fps.setValue(12)
    dialog._save()
    assert control.session.config.index == 3
    assert control.session.controller.config.index == 3
    assert control.session.controller.config.width == 1280
    assert control.session.controller.config.analysis_fps == 12
    dialog.close()
    control.close()


def test_onboarding_config_reaches_session(
    qtbot: Any, qapp: QApplication, tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(
        "jarvis_hands.agent.settings.settings_path", lambda: tmp_path / "agent.json"
    )
    control = ControlWindow(
        AppConfig.default(), qapp.screens(), config_path=tmp_path / "config.json"
    )
    qtbot.addWidget(control)
    control.show()
    config = replace(
        AppConfig.default(),
        camera=replace(AppConfig.default().camera, index=2, height=720),
    )
    control._onboarding_done(config)
    assert control.session.config.index == 2
    assert control.session.controller.config.height == 720
    control.close()


def test_overlay_apply_config_propagates_high_contrast(qtbot: Any, qapp: QApplication) -> None:
    overlay, session, _controller, _backend = make_overlay(qtbot, qapp)
    assert overlay._theme.high_contrast is False
    config = replace(
        AppConfig.default(),
        display=replace(AppConfig.default().display, high_contrast=True),
    )
    overlay.apply_config(config)
    assert bool(overlay._theme.high_contrast) is True
    assert overlay.ring._theme.high_contrast is True
    assert overlay.orb._theme.high_contrast is True
    assert overlay.card._theme.high_contrast is True
    assert overlay.response_panel._theme.high_contrast is True
    assert overlay.tree._tree_theme.high_contrast is True
    assert overlay.indicator._theme.high_contrast is True
    assert overlay.hand_cursor._theme.high_contrast is True
    overlay.apply_config(replace(AppConfig.default()))
    assert bool(overlay._theme.high_contrast) is False
    assert bool(overlay.ring._theme.high_contrast) is False
    session.stop()
    overlay.close()


def test_control_window_follows_high_contrast_setting(
    qtbot: Any, qapp: QApplication, tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setattr(
        "jarvis_hands.agent.settings.settings_path", lambda: tmp_path / "agent.json"
    )
    control = ControlWindow(
        AppConfig.default(), qapp.screens(), config_path=tmp_path / "config.json"
    )
    qtbot.addWidget(control)
    control.show()
    control.settings_button.click()
    dialog = control._settings_dialog
    assert isinstance(dialog, SettingsDialog)
    dialog.display_page.high_contrast.setChecked(True)
    dialog._save()
    assert control._theme.high_contrast is True
    assert control.overlay._theme.high_contrast is True
    assert control.overlay.ring._theme.high_contrast is True
    dialog.close()
    control.close()
