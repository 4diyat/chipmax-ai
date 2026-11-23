"""Bus signal/slot internal.

Bus hanya menyambungkan komponen dalam satu proses; ia tidak membuka socket,
server, atau port jaringan apa pun. Tipe payload sengaja ``object`` agar modul
inti tidak bergantung pada widget konkret (misal event gestur fase 3).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

__all__ = ["Bus"]


class Bus(QObject):
    """Hub signal internal untuk UI, kamera, gestur, dan agen."""

    #: Status JARVIS berubah (payload: :class:`jarvis_hands.core.state.Status`).
    status_changed = Signal(object)
    #: Level gelombang suara 0.0..1.0 dari agen TTS.
    level_changed = Signal(float)
    #: Pesan teks untuk toast/panel.
    message = Signal(str)
    #: Event gestur dari mesin (payload: subclass ``GestureEvent`` fase 3).
    gesture_event = Signal(object)
    #: Mode gestur / kamera menyala atau mati.
    camera_active_changed = Signal(bool)
    #: Perintah teks dari UI ke agen.
    command = Signal(str)
    #: Notifikasi singkat (diteruskan ke toast).
    toast = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def set_status(self, status: object) -> None:
        """Kirim status; dipakai juga oleh pemutar status tiruan."""
        self.status_changed.emit(status)

    def set_level(self, level: float) -> None:
        """Kirim level gelombang suara, dibatasi 0.0..1.0."""
        self.level_changed.emit(max(0.0, min(1.0, level)))

    def show_toast(self, text: str) -> None:
        """Tampilkan notifikasi singkat."""
        self.toast.emit(text)
