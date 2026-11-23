"""Bridge Qt ke penyedia agen: satu permintaan aktif di thread terpisah."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from jarvis_hands.agent.gemini import MAX_PROMPT_CHARS, AgentError
from jarvis_hands.agent.providers import generate
from jarvis_hands.agent.settings import (
    AgentSettings,
    CredentialStore,
    Provider,
    SettingsError,
    resolve_key,
)
from jarvis_hands.core.state import Status


class _RequestThread(QThread):
    answer = Signal(str)
    failure = Signal(str)

    def __init__(self, prompt: str, key: str, settings: AgentSettings, parent: QObject) -> None:
        super().__init__(parent)
        self._prompt = prompt
        self._key = key
        self._settings = AgentSettings(
            settings.provider, dict(settings.models), settings.ollama_url
        )

    def run(self) -> None:
        try:
            text = generate(self._prompt, settings=self._settings, key=self._key)
        except (AgentError, SettingsError) as exc:
            self.failure.emit(str(exc))
        except Exception:
            self.failure.emit("Terjadi kesalahan internal saat menghubungi agen.")
        else:
            self.answer.emit(text)
        finally:
            self._key = ""
            self._prompt = ""


class AgentBridge(QObject):
    """Jembatan nyata; tidak mensimulasikan respons atau status suara."""

    status_changed = Signal(object)
    response = Signal(str)
    error = Signal(str)
    busy_changed = Signal(bool)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        settings: AgentSettings | None = None,
        store: CredentialStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._worker: _RequestThread | None = None
        self._status = Status.IDLE
        self.settings = settings or AgentSettings()
        self.store = store or CredentialStore()

    @property
    def busy(self) -> bool:
        return self._worker is not None

    @property
    def status(self) -> Status:
        return self._status

    def _set_status(self, status: Status) -> None:
        if self._status is not status:
            self._status = status
            self.status_changed.emit(status)

    def submit(
        self, prompt: str, *, settings: AgentSettings | None = None, key: str | None = None
    ) -> bool:
        """Validasi dan kirim permintaan, atau tampilkan error tanpa jaringan."""
        if self.busy:
            self.error.emit("Tunggu sampai permintaan agen selesai.")
            return False
        prompt = prompt.strip()
        if not prompt or len(prompt) > MAX_PROMPT_CHARS:
            self.error.emit(f"Teks harus berisi 1–{MAX_PROMPT_CHARS} karakter.")
            return False
        selected = settings or self.settings
        try:
            selected.validate()
        except SettingsError as exc:
            self.error.emit(str(exc))
            return False
        credential = resolve_key(selected.provider, self.store) if key is None else key.strip()
        if not credential and selected.provider is not Provider.OLLAMA:
            message = (
                "GEMINI_API_KEY belum diatur."
                if selected.provider is Provider.GEMINI
                else "API key belum diatur untuk penyedia ini."
            )
            self.error.emit(message)
            return False
        worker = _RequestThread(prompt, credential, selected, self)
        worker.answer.connect(self.response.emit)
        worker.failure.connect(self.error.emit)
        worker.finished.connect(self._done)
        self._worker = worker
        self._set_status(Status.THINKING)
        self.busy_changed.emit(True)
        worker.start()
        return True

    @Slot()
    def _done(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self._set_status(Status.IDLE)
        self.busy_changed.emit(False)
