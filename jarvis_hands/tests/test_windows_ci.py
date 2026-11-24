"""Diagnostik CI melaporkan kegagalan dan tes yang macet."""

from __future__ import annotations

import io
import os
import sys

import pytest
from tools import windows_pytest


def test_annotation_escapes_workflow_command_data(monkeypatch: pytest.MonkeyPatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr(sys, "__stdout__", output)
    windows_pytest._annotation("Test", "one%two\r\nthree")
    assert output.getvalue() == "::error title=Test::one%25two%0D%0Athree\n"


def test_timeout_reports_test_and_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    output = io.StringIO()
    codes: list[int] = []
    monkeypatch.setattr(sys, "__stdout__", output)
    monkeypatch.setattr(os, "_exit", codes.append)
    windows_pytest._timeout("test_example.py::test_stuck")
    assert "test_example.py::test_stuck" in output.getvalue()
    assert "Test exceeded 60 seconds" in output.getvalue()
    assert "Thread" in output.getvalue()
    assert codes == [1]
