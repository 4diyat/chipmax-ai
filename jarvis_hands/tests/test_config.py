"""Tes konfigurasi: default, validasi, dan serialisasi."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from jarvis_hands.core.config import (
    MAX_CONFIG_BYTES,
    AppConfig,
    CameraConfig,
    ConfigError,
    DisplayMode,
    KeyColor,
    KeyColorSpec,
    load_config,
    normalize_hex,
    parse_key_color,
    save_config,
    with_display_overrides,
)


def test_defaults_match_spec() -> None:
    config = AppConfig.default()
    assert config.display.mode is DisplayMode.OVERLAY
    assert config.display.key_color is KeyColor.MAGENTA
    assert config.display.auto_hide_s == 10
    assert config.display.auto_hide_enabled is True
    assert config.display.high_contrast is False
    assert config.camera == CameraConfig(index=0, width=640, height=360, fps=30)
    assert config.gestures.pinch_close < config.gestures.pinch_open
    assert config.gestures.hold_ms == 1000
    assert config.telemetry_consent is False


def test_round_trip_through_dict(tmp_path: Path) -> None:
    config = AppConfig.default()
    rebuilt = AppConfig.from_dict(config.to_dict())
    assert rebuilt == config


def test_save_and_load(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    config = with_display_overrides(AppConfig.default(), high_contrast=True)
    saved = save_config(config, target)
    assert saved == target
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["display"]["high_contrast"] is True
    assert load_config(target) == config
    if os.name == "posix":
        assert (target.stat().st_mode & 0o777) == 0o600


def test_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    assert load_config(tmp_path / "absen.json") == AppConfig.default()


def test_load_rejects_broken_json(tmp_path: Path) -> None:
    target = tmp_path / "broken.json"
    target.write_text("{bukan json", encoding="utf-8")
    with pytest.raises(ConfigError, match="rusak"):
        load_config(target)


def test_load_rejects_oversized_config(tmp_path: Path) -> None:
    target = tmp_path / "big.json"
    target.write_text('{"x": "' + "a" * (MAX_CONFIG_BYTES + 16) + '"}', encoding="utf-8")
    with pytest.raises(ConfigError, match="terlalu besar"):
        load_config(target)


def test_parse_key_colors() -> None:
    assert parse_key_color("magenta") == KeyColorSpec(KeyColor.MAGENTA, "#FF00FF")
    assert parse_key_color("green") == KeyColorSpec(KeyColor.GREEN, "#00FF00")
    assert parse_key_color("blue") == KeyColorSpec(KeyColor.BLUE, "#0000FF")
    assert parse_key_color("#0f0") == KeyColorSpec(KeyColor.CUSTOM, "#00FF00")
    assert parse_key_color("#12ab34") == KeyColorSpec(KeyColor.CUSTOM, "#12AB34")
    assert parse_key_color("#AABBCC80") == KeyColorSpec(KeyColor.CUSTOM, "#AABBCC")


def test_normalize_hex_expands_short_form() -> None:
    assert normalize_hex("#abc") == "#AABBCC"
    assert normalize_hex("#AABBCC80") == "#AABBCC"
    for bad in ("AABBCC", "#12", "#12G45Z", "#12345", ""):
        with pytest.raises(ConfigError):
            normalize_hex(bad)


def test_parse_key_color_rejects_unknown() -> None:
    with pytest.raises(ConfigError):
        parse_key_color("custom")
    with pytest.raises(ConfigError):
        parse_key_color("cyan")


def test_display_overrides_do_not_mutate_original() -> None:
    original = AppConfig.default()
    key = parse_key_color("green")
    changed = with_display_overrides(original, mode=DisplayMode.KEY, key=key, high_contrast=True)
    assert original.display.mode is DisplayMode.OVERLAY
    assert original.display.high_contrast is False
    assert changed.display.mode is DisplayMode.KEY
    assert changed.display.key_color is KeyColor.GREEN
    assert changed.display.high_contrast is True
    assert changed.display.custom_key_hex == original.display.custom_key_hex


def test_memory_root_must_be_existing_directory(tmp_path: Path) -> None:
    folder = tmp_path / "memori"
    folder.mkdir()
    data = AppConfig.default().to_dict()
    data["memory_root"] = str(folder)
    assert AppConfig.from_dict(data).memory_root == folder.resolve()

    data["memory_root"] = str(tmp_path / "absen")
    with pytest.raises(ConfigError, match="tidak dapat diakses"):
        AppConfig.from_dict(data)

    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    data["memory_root"] = str(file_path)
    with pytest.raises(ConfigError, match="harus folder"):
        AppConfig.from_dict(data)


def test_invalid_values_are_rejected() -> None:
    base = AppConfig.default().to_dict()

    base["camera"]["width"] = "640"
    with pytest.raises(ConfigError, match="bilangan bulat"):
        AppConfig.from_dict(base)

    base = AppConfig.default().to_dict()
    base["gestures"]["pinch_close"] = 0.9
    base["gestures"]["pinch_open"] = 0.5
    with pytest.raises(ConfigError, match="pinch_open"):
        AppConfig.from_dict(base)

    base = AppConfig.default().to_dict()
    base["display"]["mode"] = "hologram"
    with pytest.raises(ConfigError, match="tidak dikenal"):
        AppConfig.from_dict(base)

    base = AppConfig.default().to_dict()
    base["display"]["auto_hide_s"] = 0
    with pytest.raises(ConfigError, match="minimal"):
        AppConfig.from_dict(base)

    base = AppConfig.default().to_dict()
    base["display"]["auto_hide_enabled"] = "ya"
    with pytest.raises(ConfigError, match="boolean"):
        AppConfig.from_dict(base)

    base = AppConfig.default().to_dict()
    base["camera"]["mirror"] = "ya"
    with pytest.raises(ConfigError, match="boolean"):
        AppConfig.from_dict(base)


def test_unknown_keys_are_ignored() -> None:
    data = AppConfig.default().to_dict()
    data["masa_depan"] = {"fitur": True}
    data["camera"]["lensa"] = "lebar"
    assert AppConfig.from_dict(data) == AppConfig.default()


def test_camera_analysis_defaults_and_round_trip() -> None:
    config = AppConfig.default()
    assert config.camera.analysis_fps == 30
    assert config.camera.max_cpu_percent == 25.0

    payload = config.to_dict()
    payload["camera"]["analysis_fps"] = 15
    payload["camera"]["max_cpu_percent"] = 40.0
    rebuilt = AppConfig.from_dict(payload)
    assert rebuilt.camera.analysis_fps == 15
    assert rebuilt.camera.max_cpu_percent == 40.0


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("analysis_fps", 0),
        ("analysis_fps", 121),
        ("max_cpu_percent", 0.0),
        ("max_cpu_percent", 101.0),
    ],
)
def test_camera_analysis_rejects_out_of_range(key: str, value: object) -> None:
    payload = AppConfig.default().to_dict()
    payload["camera"][key] = value
    with pytest.raises(ConfigError):
        AppConfig.from_dict(payload)


def test_gesture_thresholds_defaults_and_round_trip() -> None:
    config = AppConfig.default()
    assert config.gestures.scrub_window_ms == 700
    assert config.gestures.scrub_reversals == 3
    assert config.gestures.clap_approach_px == 40.0
    assert config.gestures.clap_min_speed_px_s == 600.0
    assert config.gestures.explode_min_speed_px_s == 800.0
    assert config.gestures.gesture_cooldown_ms == 400

    payload = config.to_dict()
    payload["gestures"].update(
        {
            "scrub_window_ms": 900,
            "scrub_reversals": 5,
            "clap_approach_px": 55.0,
            "clap_min_speed_px_s": 750.0,
            "explode_min_speed_px_s": 900.0,
            "gesture_cooldown_ms": 250,
        }
    )
    rebuilt = AppConfig.from_dict(payload)
    assert rebuilt.gestures.scrub_window_ms == 900
    assert rebuilt.gestures.scrub_reversals == 5
    assert rebuilt.gestures.clap_approach_px == 55.0
    assert rebuilt.gestures.clap_min_speed_px_s == 750.0
    assert rebuilt.gestures.explode_min_speed_px_s == 900.0
    assert rebuilt.gestures.gesture_cooldown_ms == 250


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("scrub_reversals", 0),
        ("scrub_window_ms", 10),
        ("clap_approach_px", -1.0),
        ("clap_min_speed_px_s", -1.0),
        ("explode_min_speed_px_s", -1.0),
        ("gesture_cooldown_ms", -1),
    ],
)
def test_gesture_thresholds_reject_out_of_range(key: str, value: object) -> None:
    payload = AppConfig.default().to_dict()
    payload["gestures"][key] = value
    with pytest.raises(ConfigError):
        AppConfig.from_dict(payload)
