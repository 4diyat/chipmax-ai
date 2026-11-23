"""Skrip peluncur bekerja dari direktori lain dan meneruskan argumen."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(sys.platform == "win32", reason="run.sh untuk sistem POSIX")
def test_shell_launcher_forwards_arguments_and_exit_code(tmp_path: Path) -> None:
    project = tmp_path / "project with spaces"
    project.mkdir()
    script = project / "run.sh"
    shutil.copyfile(ROOT / "run.sh", script)
    python = project / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$PWD" "$@"\nexit 37\n', encoding="utf-8")
    python.chmod(0o755)
    result = subprocess.run(
        ["sh", str(script), "--mode", "mirror", "argument with spaces"],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 37
    assert result.stdout.splitlines() == [
        str(project),
        "-m",
        "jarvis_hands",
        "--mode",
        "mirror",
        "argument with spaces",
    ]


@pytest.mark.skipif(sys.platform == "win32", reason="run.sh untuk sistem POSIX")
def test_shell_launcher_missing_venv_prints_help(tmp_path: Path) -> None:
    script = tmp_path / "run.sh"
    shutil.copyfile(ROOT / "run.sh", script)
    result = subprocess.run(
        ["sh", str(script)], text=True, capture_output=True, check=False, timeout=10
    )
    assert result.returncode == 1
    assert "python3.11 -m venv .venv" in result.stderr
    assert "pip install -r requirements.txt" in result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="run.bat untuk Windows")
def test_windows_launcher_missing_venv_prints_help(tmp_path: Path) -> None:
    script = tmp_path / "run.bat"
    shutil.copyfile(ROOT / "run.bat", script)
    result = subprocess.run(
        ["cmd", "/c", str(script)], text=True, capture_output=True, check=False, timeout=10
    )
    assert result.returncode == 1
    assert "py -3.11 -m venv .venv" in result.stdout
    assert "pip install -r requirements.txt" in result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="run.bat untuk Windows")
def test_windows_launcher_runs_real_version(tmp_path: Path) -> None:
    if not (ROOT / ".venv" / "Scripts" / "python.exe").exists():
        pytest.skip(".venv proyek belum tersedia")
    result = subprocess.run(
        ["cmd", "/c", str(ROOT / "run.bat"), "--version"],
        cwd=tmp_path,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("jarvis-hands ")
