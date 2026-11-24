"""Tes pengaturan Fase 7: halaman tampilan, kamera, gestur, dan dialog terpadu."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt

from jarvis_hands.agent.settings import AgentSettings
from jarvis_hands.core.config import (
    AppConfig,
    ConfigError,
    DisplayMode,
    GestureThresholds,
    KeyColor,
)
from jarvis_hands.tests.test_agent_settings import LocalStore
from jarvis_hands.ui.settings import (
    CameraSettingsPage,
    DisplaySettingsPage,
    GestureSettingsPage,
    SettingsDialog,
)


def test_display_page_applies_and_preserves_custom_hex() -> None:
    config = AppConfig.default()
    page = DisplaySettingsPage(config)
    page.mode.setCurrentIndex(page.mode.findData(DisplayMode.KEY.value))
    page.key_color.setCurrentIndex(page.key_color.findData(KeyColor.GREEN.value))
    page.high_contrast.setChecked(True)
    page.auto_hide_enabled.setChecked(False)
    page.auto_hide_s.setValue(3)
    page.ui_scale.setValue(1.25)
    changed = page.apply(config)
    assert changed.display.mode is DisplayMode.KEY
    assert changed.display.key_color is KeyColor.GREEN
    assert changed.display.high_contrast is True
    assert changed.display.auto_hide_enabled is False
    assert changed.display.auto_hide_s == 3
    assert changed.display.ui_scale == 1.25
    assert config.display.mode is DisplayMode.OVERLAY
    assert page.custom_hex.isEnabled() is False


def test_display_page_validates_custom_hex() -> None:
    config = AppConfig.default()
    page = DisplaySettingsPage(config)
    page.key_color.setCurrentIndex(page.key_color.findData(KeyColor.CUSTOM.value))
    assert page.custom_hex.isEnabled()
    page.custom_hex.setText("#0f0")
    changed = page.apply(config)
    assert changed.display.key_color is KeyColor.CUSTOM
    assert changed.display.custom_key_hex == "#00FF00"
    page.custom_hex.setText("bukan warna")
    with pytest.raises(ConfigError):
        page.apply(config)


def test_camera_page_applies_every_field() -> None:
    config = AppConfig.default()
    page = CameraSettingsPage(config)
    page.index.setValue(2)
    page.frame_width.setValue(1280)
    page.frame_height.setValue(720)
    page.fps.setValue(24)
    page.mirror.setChecked(False)
    page.use_dshow.setChecked(False)
    page.analysis_fps.setValue(12)
    page.analysis_scale.setValue(0.5)
    page.max_cpu.setValue(40.0)
    changed = page.apply(config)
    assert changed.camera.index == 2
    assert changed.camera.width == 1280
    assert changed.camera.height == 720
    assert changed.camera.fps == 24
    assert changed.camera.mirror is False
    assert changed.camera.use_dshow is False
    assert changed.camera.analysis_fps == 12
    assert changed.camera.analysis_scale == 0.5
    assert changed.camera.max_cpu_percent == 40.0
    assert config.camera.index == 0


def test_gesture_page_builds_thresholds_and_rejects_bad_relation() -> None:
    config = AppConfig.default()
    page = GestureSettingsPage(config)
    page._int_fields["hold_ms"].setValue(1500)
    page._float_fields["drag_start_px"].setValue(30.0)
    changed = page.apply(config)
    assert isinstance(changed.gestures, GestureThresholds)
    assert changed.gestures.hold_ms == 1500
    assert changed.gestures.drag_start_px == 30.0

    page._float_fields["pinch_close"].setValue(0.80)
    page._float_fields["pinch_open"].setValue(0.50)
    with pytest.raises(ConfigError, match="pinch_close"):
        page.apply(config)


def test_gesture_page_rejects_inverted_tap_window() -> None:
    page = GestureSettingsPage(AppConfig.default())
    page._int_fields["tap_min_ms"].setValue(500)
    page._int_fields["tap_max_ms"].setValue(100)
    with pytest.raises(ConfigError, match="tap_min_ms"):
        page.apply(AppConfig.default())


def test_settings_dialog_saves_all_pages(qtbot: Any, tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "jarvis_hands.agent.settings.settings_path", lambda: tmp_path / "default-agent.json"
    )
    target = tmp_path / "config.json"
    agent_target = tmp_path / "agent.json"
    dialog = SettingsDialog(
        AppConfig.default(),
        AgentSettings(),
        LocalStore(),
        config_path=target,
        agent_path=agent_target,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    saved: list[AppConfig] = []
    agent_saved: list[AgentSettings] = []
    dialog.saved.connect(saved.append)
    dialog.agent_saved.connect(agent_saved.append)

    dialog.display_page.auto_hide_s.setValue(7)
    dialog.camera_page.index.setValue(2)
    dialog.gesture_page._int_fields["hold_ms"].setValue(1500)
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    assert len(saved) == 1
    assert saved[0].display.auto_hide_s == 7
    assert saved[0].camera.index == 2
    assert saved[0].gestures.hold_ms == 1500
    assert dialog.config == saved[0]
    assert target.exists()
    assert agent_target.exists()
    assert len(agent_saved) == 1
    assert "disimpan" in dialog.status.text()
    dialog.close()


def test_settings_dialog_blocks_invalid_gestures(qtbot: Any, tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    dialog = SettingsDialog(
        AppConfig.default(),
        AgentSettings(),
        LocalStore(),
        config_path=target,
        agent_path=tmp_path / "agent.json",
    )
    qtbot.addWidget(dialog)
    dialog.gesture_page._float_fields["pinch_close"].setValue(0.9)
    dialog.gesture_page._float_fields["pinch_open"].setValue(0.4)
    dialog._save()
    assert not target.exists()
    assert "pinch_close" in dialog.status.text()
    dialog.close()


def test_settings_dialog_reject_clears_unsaved_key(qtbot: Any, tmp_path: Path) -> None:
    dialog = SettingsDialog(
        AppConfig.default(),
        AgentSettings(),
        LocalStore(),
        config_path=tmp_path / "config.json",
        agent_path=tmp_path / "agent.json",
    )
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.key.setText("secret")
    dialog.reject()
    assert dialog.key.text() == ""
    assert not (tmp_path / "config.json").exists()


def test_settings_dialog_refreshes_after_external_change(qtbot: Any, tmp_path: Path) -> None:
    dialog = SettingsDialog(
        AppConfig.default(),
        AgentSettings(),
        LocalStore(),
        config_path=tmp_path / "config.json",
        agent_path=tmp_path / "agent.json",
    )
    qtbot.addWidget(dialog)
    changed = AppConfig.default()
    changed = replace(changed, display=replace(changed.display, auto_hide_s=42))
    dialog.apply_external_config(changed)
    assert dialog.config.display.auto_hide_s == 42
    assert dialog.display_page.auto_hide_s.value() == 42
    assert "panduan" in dialog.status.text().lower()
    dialog.close()
