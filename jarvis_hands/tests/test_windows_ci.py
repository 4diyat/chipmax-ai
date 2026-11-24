"""Diagnostik CI tetap melaporkan kegagalan dan batas waktu pytest."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest
from tools import windows_pytest


@pytest.mark.parametrize("exit_code", [0, 1, 5])
def test_runner_reports_result(
    monkeypatch: pytest.MonkeyPatch, capsys: Any, exit_code: int
) -> None:
    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        kwargs["stdout"].write(b"test_example.py::test_one FAILED\n")
        assert kwargs["timeout"] == windows_pytest.TIMEOUT_SECONDS
        return subprocess.CompletedProcess(command, exit_code)

    monkeypatch.setattr(subprocess, "run", run)
    assert windows_pytest.main() == exit_code
    output = capsys.readouterr().out
    assert "test_example.py::test_one FAILED" in output
    assert ("::error title=Windows pytest diagnostics::" in output) == (exit_code != 0)


def test_runner_reports_timeout(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    def run(command: list[str], **kwargs: Any) -> None:
        kwargs["stdout"].write(b"test_example.py::test_stuck ")
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", run)
    assert windows_pytest.main() == 1
    output = capsys.readouterr().out
    assert "pytest exceeded 300 seconds" in output
    assert "test_example.py::test_stuck" in output
