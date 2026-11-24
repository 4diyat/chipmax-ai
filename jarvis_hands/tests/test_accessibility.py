"""Tes audit aksesibilitas (Fase 8)."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QPushButton, QWidget

from jarvis_hands.app import main
from jarvis_hands.ui.accessibility import (
    MIN_BUTTON_HEIGHT,
    audit_application,
    audit_widget,
    format_issues,
)


def test_audit_flags_missing_name_and_small_target(qapp: Any) -> None:
    del qapp
    root = QWidget()
    button = QPushButton(root)
    button.setText("")
    issues = audit_widget(root)
    kinds = {issue.kind for issue in issues}
    assert "missing-name" in kinds
    assert "small-target" in kinds
    assert "Aksesibilitas: 2 temuan." in format_issues(issues)


def test_audit_passes_named_large_button(qapp: Any) -> None:
    del qapp
    root = QWidget()
    button = QPushButton("Simpan", root)
    button.setMinimumHeight(MIN_BUTTON_HEIGHT)
    assert audit_widget(root) == []
    assert "tidak ada temuan" in format_issues([])


def test_audit_application_has_no_issues(qapp: Any) -> None:
    del qapp
    assert audit_application() == []


def test_a11y_cli_reports_clean(qapp: Any, capsys: Any) -> None:
    del qapp
    assert main(["--a11y-audit"]) == 0
    assert "tidak ada temuan" in capsys.readouterr().out
