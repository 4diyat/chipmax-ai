"""Tes aset packaging Windows (Fase 8)."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_spec_is_valid_and_bundles_model() -> None:
    spec = ROOT / "packaging" / "jarvis-hands.spec"
    text = spec.read_text(encoding="utf-8")
    ast.parse(text)
    assert "hand_landmarker.task" in text
    assert "jarvis_hands/assets/models" in text
    assert "COLLECT" in text
    assert "collect_all" in text
    assert "console=False" in text


def test_windows_build_scripts_reference_spec() -> None:
    ps1 = (ROOT / "packaging" / "build_windows.ps1").read_text(encoding="utf-8")
    assert "jarvis-hands.spec" in ps1
    assert "uv sync --frozen --extra packaging" in ps1
    bat = (ROOT / "packaging" / "build_windows.bat").read_text(encoding="utf-8")
    assert "build_windows.ps1" in bat


def test_packaging_extra_is_declared() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"]["optional-dependencies"]["packaging"]
    assert any("pyinstaller" in dependency for dependency in extras)


def test_bundled_model_assets_exist() -> None:
    models = ROOT / "jarvis_hands" / "assets" / "models"
    assert (models / "hand_landmarker.task").is_file()
    assert (models / "LICENSE").is_file()
    assert (models / "README.md").is_file()
