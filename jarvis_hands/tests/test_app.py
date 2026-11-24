"""Tes CLI dan bootstrap aplikasi."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_hands import __version__
from jarvis_hands.app import build_parser, main


def test_default_arguments() -> None:
    args = build_parser().parse_args([])
    assert args.config is None
    assert args.high_contrast is False


def test_config_and_high_contrast_arguments(tmp_path: Path) -> None:
    args = build_parser().parse_args(["--config", str(tmp_path / "config.json"), "--high-contrast"])
    assert args.config == tmp_path / "config.json"
    assert args.high_contrast is True


def test_no_onboarding_argument() -> None:
    args = build_parser().parse_args(["--no-onboarding"])
    assert args.no_onboarding is True


def test_version_flag() -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["--version"])
    assert exc.value.code == 0


def test_invalid_config_returns_two_without_starting_qt(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    broken = tmp_path / "broken.json"
    broken.write_text("{bukan json", encoding="utf-8")
    assert main(["--config", str(broken)]) == 2
    err = capsys.readouterr().err
    assert "konfigurasi tidak valid" in err


def test_version_is_exposed() -> None:
    assert __version__.count(".") == 2
