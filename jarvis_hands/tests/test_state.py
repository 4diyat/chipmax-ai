"""Tes enum Status."""

from __future__ import annotations

from jarvis_hands.core.state import Status


def test_status_order_matches_spec() -> None:
    assert [status.value for status in Status] == [
        "idle",
        "listening",
        "thinking",
        "speaking",
        "senyap",
    ]


def test_status_labels_are_capitalized() -> None:
    assert [status.label for status in Status] == [
        "SIAGA",
        "MENDENGARKAN",
        "BERPIKIR",
        "BERBICARA",
        "SENYAP",
    ]
    for status in Status:
        assert status.label == status.label.upper()


def test_only_senyap_is_inactive() -> None:
    assert Status.SENYAP.is_active is False
    for status in Status:
        if status is not Status.SENYAP:
            assert status.is_active is True
