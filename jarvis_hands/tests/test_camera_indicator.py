"""Tes indikator kamera: label, state, FPS, dan paint."""

from __future__ import annotations

import pytest

from jarvis_hands.ui.camera import CameraIndicator, CameraState
from jarvis_hands.ui.tokens import build_theme


def test_default_state_is_off(qapp: object) -> None:
    indicator = CameraIndicator()
    assert indicator.state is CameraState.OFF
    assert indicator.label == "KAMERA MATI"
    assert indicator.accessibleName() == "Indikator kamera"
    indicator.close()


def test_state_labels_and_signal(qapp: object) -> None:
    indicator = CameraIndicator()
    states: list[CameraState] = []
    indicator.state_changed.connect(states.append)

    indicator.set_state(CameraState.ACTIVE)
    assert indicator.label == "KAMERA AKTIF"
    indicator.set_state(CameraState.PAUSED)
    assert indicator.label == "KAMERA JEDA"
    indicator.set_state(CameraState.ERROR)
    assert indicator.label == "KAMERA ERROR"
    indicator.set_state(CameraState.OFF)
    assert indicator.label == "KAMERA MATI"
    assert states == [
        CameraState.ACTIVE,
        CameraState.PAUSED,
        CameraState.ERROR,
        CameraState.OFF,
    ]
    indicator.close()


def test_fps_only_shown_when_active(qapp: object) -> None:
    indicator = CameraIndicator()
    indicator.set_fps(29.6)
    assert indicator.label == "KAMERA MATI"
    indicator.set_active(True)
    assert indicator.label == "KAMERA AKTIF  30 FPS"
    indicator.set_paused(True)
    assert indicator.label == "KAMERA JEDA"
    indicator.close()


def test_state_change_is_idempotent(qapp: object) -> None:
    indicator = CameraIndicator()
    states: list[CameraState] = []
    indicator.state_changed.connect(states.append)
    indicator.set_state(CameraState.OFF)
    assert states == []
    indicator.close()


def test_paint_produces_image(qapp: object, qtbot: object) -> None:
    for high_contrast in (False, True):
        indicator = CameraIndicator(build_theme(high_contrast=high_contrast))
        qtbot.addWidget(indicator)  # type: ignore[attr-defined]
        indicator.show()
        qtbot.waitExposed(indicator)  # type: ignore[attr-defined]
        image = indicator.grab().toImage()
        assert not image.isNull()
        assert image.width() == indicator.width()
        indicator.close()


def test_width_grows_with_label(qapp: object) -> None:
    indicator = CameraIndicator()
    before = indicator.width()
    indicator.set_active(True)
    indicator.set_fps(30)
    assert indicator.width() > before
    indicator.close()


def test_error_state(qapp: object) -> None:
    indicator = CameraIndicator()
    indicator.set_error()
    assert indicator.state is CameraState.ERROR
    assert "ERROR" in indicator.accessibleDescription()
    indicator.close()


@pytest.mark.parametrize("state", list(CameraState))
def test_all_states_render(qapp: object, qtbot: object, state: CameraState) -> None:
    indicator = CameraIndicator()
    qtbot.addWidget(indicator)  # type: ignore[attr-defined]
    indicator.show()
    indicator.set_state(state)
    assert not indicator.grab().toImage().isNull()
    indicator.close()
