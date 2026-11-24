"""Tes onboarding Fase 7: navigasi, uji kamera, coach gestur, dan penyimpanan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtWidgets import QApplication

from jarvis_hands.core.config import AppConfig
from jarvis_hands.tests.support import make_hand, make_result
from jarvis_hands.tests.test_session import make_session
from jarvis_hands.ui.onboarding import OnboardingDialog
from jarvis_hands.vision.camera import Frame


def make_dialog(
    qtbot: Any, qapp: QApplication, *, config: AppConfig | None = None, path: Path | None = None
) -> tuple[OnboardingDialog, Any]:
    del qapp
    session, _controller, _backend, _indicator = make_session()
    dialog = OnboardingDialog(config or AppConfig.default(), config_path=path, session=session)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog, session


def test_onboarding_navigation_and_completion(
    qtbot: Any, qapp: QApplication, tmp_path: Path
) -> None:
    target = tmp_path / "config.json"
    dialog, session = make_dialog(qtbot, qapp, path=target)
    completed: list[AppConfig] = []
    dialog.completed.connect(completed.append)

    assert dialog.step == 0
    dialog._next()
    assert dialog.step == 1
    dialog._back()
    assert dialog.step == 0
    dialog._next()

    dialog.camera_button.click()
    assert session.is_active
    data = np.zeros((4, 5, 3), dtype=np.uint8)
    data[:, :] = [10, 200, 30]
    dialog._on_frame(Frame(data, 5, 4, 1))
    assert not dialog.preview.pixmap().isNull()
    dialog._on_tracking(make_result(make_hand(index=(0.5, 0.5), pinch_ratio=0.1), timestamp_ms=5))
    assert "cubit" in dialog.camera_status.text().lower()

    dialog._next()
    assert dialog.step == 2
    dialog._on_tracking(make_result(make_hand(index=(0.5, 0.5), pinch_ratio=0.7), timestamp_ms=15))
    assert "Tangan terlihat" in dialog.coach_status.text()
    dialog._next()
    assert dialog.step == 3
    assert dialog.next_button.text() == "SELESAI"
    dialog._next()
    assert len(completed) == 1
    assert completed[0].onboarding_done is True
    assert target.exists()
    assert not session.is_active


def test_onboarding_skip_marks_done(qtbot: Any, qapp: QApplication, tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    dialog, _session = make_dialog(qtbot, qapp, path=target)
    completed: list[AppConfig] = []
    dialog.completed.connect(completed.append)
    dialog._skip()
    assert dialog.skipped is True
    assert completed[0].onboarding_done is True
    assert target.exists()


def test_onboarding_respects_dont_show_choice(
    qtbot: Any, qapp: QApplication, tmp_path: Path
) -> None:
    target = tmp_path / "config.json"
    dialog, _session = make_dialog(qtbot, qapp, path=target)
    completed: list[AppConfig] = []
    dialog.completed.connect(completed.append)
    dialog.finish_choice.setChecked(False)
    dialog._finish(skipped=False)
    assert completed[0].onboarding_done is False
    assert not target.exists()


def test_onboarding_close_stops_camera(qtbot: Any, qapp: QApplication) -> None:
    dialog, session = make_dialog(qtbot, qapp)
    dialog._next()
    dialog.camera_button.click()
    assert session.is_active
    dialog.close()
    assert not session.is_active
    assert dialog.preview.pixmap().isNull()
