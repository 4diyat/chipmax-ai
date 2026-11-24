"""Audit aksesibilitas statis untuk widget (Fase 8).

Audit memeriksa hal yang bisa diuji tanpa pembaca layar sungguhan: nama
aksesibel pada kontrol, tinggi minimum tombol, dan label pada input. Widget
internal Qt (mis. baris teks di dalam ``QSpinBox``) dilewati. Pemakaian:
``python -m jarvis_hands --a11y-audit``.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QToolButton,
    QWidget,
)

__all__ = [
    "MIN_BUTTON_HEIGHT",
    "AuditIssue",
    "audit_application",
    "audit_widget",
    "enforce_min_targets",
    "format_issues",
]

#: Tinggi minimum tombol target ketuk (px logis).
MIN_BUTTON_HEIGHT = 44

_INPUT_TYPES = (QLineEdit, QComboBox, QAbstractSpinBox, QPlainTextEdit, QTextEdit)


@dataclass(frozen=True)
class AuditIssue:
    """Satu temuan aksesibilitas."""

    widget: str
    kind: str
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.widget}: {self.message}"


def _describe(widget: QWidget) -> str:
    text_getter = getattr(widget, "text", None)
    text = text_getter() if callable(text_getter) else ""
    return f"{type(widget).__name__}(objectName={widget.objectName()!r}, text={text!r})"


def _is_internal(widget: QWidget) -> bool:
    """True untuk anak internal spinbox/combobox yang bukan kontrol produk."""
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractSpinBox | QComboBox):
            return True
        parent = parent.parentWidget()
    return False


def audit_widget(root: QWidget) -> list[AuditIssue]:
    """Audit kontrol di bawah ``root``; return daftar temuan."""
    issues: list[AuditIssue] = []
    for widget in root.findChildren(QWidget):
        if _is_internal(widget):
            continue
        if isinstance(widget, QAbstractButton):
            label = widget.accessibleName().strip()
            if not label:
                text_getter = getattr(widget, "text", None)
                label = text_getter().strip() if callable(text_getter) else ""
            if not label:
                issues.append(
                    AuditIssue(
                        _describe(widget),
                        "missing-name",
                        "Tombol kontrol tidak punya accessibleName atau teks.",
                    )
                )
            if (
                isinstance(widget, QPushButton | QToolButton)
                and widget.minimumHeight() < MIN_BUTTON_HEIGHT
            ):
                issues.append(
                    AuditIssue(
                        _describe(widget),
                        "small-target",
                        f"Tinggi minimum {widget.minimumHeight()} < {MIN_BUTTON_HEIGHT} px.",
                    )
                )
        elif isinstance(widget, _INPUT_TYPES):
            if not widget.accessibleName().strip():
                issues.append(
                    AuditIssue(
                        _describe(widget),
                        "missing-name",
                        "Input tidak punya accessibleName.",
                    )
                )
            if widget.minimumHeight() < MIN_BUTTON_HEIGHT:
                issues.append(
                    AuditIssue(
                        _describe(widget),
                        "small-target",
                        f"Tinggi minimum input {widget.minimumHeight()} < {MIN_BUTTON_HEIGHT} px.",
                    )
                )
    return issues


def enforce_min_targets(root: QWidget) -> None:
    """Pastikan tombol dan input di bawah ``root`` minimal 44 px tinggi.

    Dipanggil di akhir konstruktor halaman/dialog supaya target ketuk konsisten
    even jika stylesheet belum diterapkan (mis. widget belum ditampilkan).
    """
    for widget in root.findChildren(QWidget):
        if _is_internal(widget):
            continue
        if (
            isinstance(widget, (QAbstractButton, *_INPUT_TYPES))
            and widget.minimumHeight() < MIN_BUTTON_HEIGHT
        ):
            widget.setMinimumHeight(MIN_BUTTON_HEIGHT)


def format_issues(issues: list[AuditIssue]) -> str:
    """Format temuan untuk terminal."""
    if not issues:
        return "Aksesibilitas: tidak ada temuan pada widget yang diperiksa."
    lines = [f"Aksesibilitas: {len(issues)} temuan."]
    lines.extend(f"- {issue}" for issue in issues)
    return "\n".join(lines)


def audit_application() -> list[AuditIssue]:
    """Audit jendela utama yang dibangun aplikasi (tanpa menyalakan kamera)."""
    from jarvis_hands.agent.settings import AgentSettings, CredentialStore
    from jarvis_hands.core.config import AppConfig
    from jarvis_hands.ui.catalog import CatalogWindow
    from jarvis_hands.ui.onboarding import OnboardingDialog
    from jarvis_hands.ui.overlay import ControlWindow
    from jarvis_hands.ui.settings import SettingsDialog
    from jarvis_hands.vision.session import CameraSession

    issues: list[AuditIssue] = []
    config = AppConfig.default()

    catalog = CatalogWindow(config=config)
    issues.extend(audit_widget(catalog))
    catalog.close()
    catalog.deleteLater()

    settings = SettingsDialog(config, AgentSettings(), CredentialStore())
    issues.extend(audit_widget(settings))
    settings.close()
    settings.deleteLater()

    onboarding = OnboardingDialog(config, session=CameraSession(config.camera))
    issues.extend(audit_widget(onboarding))
    onboarding.close()
    onboarding.deleteLater()

    app = QApplication.instance()
    if isinstance(app, QApplication) and app.screens():
        control = ControlWindow(config, app.screens())
        issues.extend(audit_widget(control))
        control.close()
        control.deleteLater()
    return issues
