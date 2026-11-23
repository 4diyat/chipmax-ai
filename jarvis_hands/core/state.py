"""Status JARVIS.

Pemetaan warna dan label ada di :mod:`jarvis_hands.ui.tokens`; modul ini sengaja
bebas Qt supaya bisa dipakai dari mesin gestur maupun worker tanpa aplikasi.
"""

from __future__ import annotations

from enum import StrEnum, unique


@unique
class Status(StrEnum):
    """Lima status yang ditampilkan cincin JARVIS."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    SENYAP = "senyap"

    @property
    def label(self) -> str:
        """Label mono kapital untuk cincin dan panel status."""
        return _LABELS[self]

    @property
    def is_active(self) -> bool:
        """Status ``senyap`` adalah satu-satunya status tanpa cahaya."""
        return self is not Status.SENYAP


_LABELS: dict[Status, str] = {
    Status.IDLE: "SIAGA",
    Status.LISTENING: "MENDENGARKAN",
    Status.THINKING: "BERPIKIR",
    Status.SPEAKING: "BERBICARA",
    Status.SENYAP: "SENYAP",
}


__all__ = ["Status"]
