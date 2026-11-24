"""Halaman dan dialog pengaturan penyedia serta kredensial (mockup Agen & API)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from jarvis_hands.agent.bridge import AgentBridge
from jarvis_hands.agent.settings import (
    DEFAULT_MODELS,
    ENV_KEYS,
    LABELS,
    AgentSettings,
    CredentialStore,
    Provider,
    SettingsError,
    resolve_key,
    save_settings,
)

#: Style kaca gelap bersama untuk semua halaman pengaturan.
SETTINGS_QSS = """
QDialog { background: #070d0f; color: #ecfffa; }
QWidget { color: #ecfffa; }
QLabel { color: #c2e8e1; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #112524; color: #ecfffa;
    border: 1px solid #548f88; border-radius: 8px; padding: 9px; }
QComboBox QAbstractItemView { background: #112524; color: #ecfffa; }
QPushButton, QToolButton { background: #112524; color: #c9f9f1;
    border: 1px solid #548f88; border-radius: 8px; padding: 10px; }
QPushButton:checked { background: #22534e; border: 2px solid #6fe5d6; }
QPushButton:disabled { color: #536963; border-color: #354743; }
QCheckBox { spacing: 10px; }
QGroupBox { border: 1px solid #35514d; border-radius: 10px; margin-top: 14px;
    padding-top: 12px; font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: #8ff0e4; }
"""


class AgentSettingsPage(QWidget):
    """Pilihan provider, model, keyring, dan uji koneksi aktual.

    Halaman ini bisa berdiri sendiri (:class:`AgentSettingsDialog`) maupun
    menjadi tab di :class:`jarvis_hands.ui.settings.SettingsDialog`.
    """

    #: Pengaturan agen tersimpan (payload: :class:`AgentSettings`).
    saved = Signal(object)

    def __init__(
        self,
        settings: AgentSettings,
        store: CredentialStore,
        *,
        path: Path | None = None,
        show_save: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._draft = AgentSettings(settings.provider, dict(settings.models), settings.ollama_url)
        self._store = store
        self._path = path
        self._tester = AgentBridge(self, store=store)
        self._tester.response.connect(self._test_success)
        self._tester.error.connect(self._test_error)
        self._tester.busy_changed.connect(self._test_busy)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(26)
        side = QVBoxLayout()
        heading = QLabel("AGEN & API")
        heading.setStyleSheet("color: #6fe5d6; font-size: 17px; font-weight: bold;")
        side.addWidget(heading)
        side.addWidget(QLabel("Penyedia teks dan kredensial"))
        side.addStretch(1)
        root.addLayout(side, 1)
        body = QVBoxLayout()
        body.setSpacing(12)
        title = QLabel("Agen & API")
        title.setStyleSheet("color: #ecfffa; font-size: 25px; font-weight: bold;")
        body.addWidget(title)
        body.addWidget(QLabel("Pilih penyedia dan atur kunci API di perangkat ini"))
        body.addWidget(QLabel("JENIS AGEN"))
        choices = QHBoxLayout()
        self.buttons = QButtonGroup(self)
        self._provider_buttons: dict[Provider, QPushButton] = {}
        for index, provider in enumerate(Provider):
            button = QPushButton(LABELS[provider])
            button.setObjectName(f"provider-{provider.value}")
            button.setMinimumHeight(44)
            button.setCheckable(True)
            self.buttons.addButton(button, index)
            self._provider_buttons[provider] = button
            choices.addWidget(button)
        self.buttons.idClicked.connect(self._select_provider)
        body.addLayout(choices)
        self.note = QLabel("Ollama: alamat server · API key opsional")
        self.note.setWordWrap(True)
        body.addWidget(self.note)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setObjectName("agent-model")
        self.model.setAccessibleName("Model agen")
        form.addRow("MODEL", self.model)
        self.url = QLineEdit()
        self.url.setObjectName("ollama-url")
        self.url.setAccessibleName("Alamat server Ollama")
        self.url.setPlaceholderText("http://127.0.0.1:11434")
        form.addRow("ALAMAT OLLAMA", self.url)
        self.key = QLineEdit()
        self.key.setObjectName("agent-key")
        self.key.setAccessibleName("API key")
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Masukkan key baru; kosongkan untuk mempertahankan")
        keyrow = QHBoxLayout()
        keyrow.addWidget(self.key, 1)
        self.eye = QToolButton()
        self.eye.setText("Tampilkan")
        self.eye.setCheckable(True)
        self.eye.setMinimumHeight(44)
        self.eye.setAccessibleName("Tampilkan atau sembunyikan API key")
        self.eye.toggled.connect(self._toggle_key)
        keyrow.addWidget(self.eye)
        form.addRow("API KEY", keyrow)
        body.addLayout(form)
        self.key_status = QLabel()
        self.key_status.setObjectName("credential-status")
        self.key_status.setWordWrap(True)
        body.addWidget(self.key_status)
        row = QHBoxLayout()
        self.save_button = QPushButton("SIMPAN PENGATURAN")
        self.save_button.setObjectName("save-agent-settings")
        self.save_button.setMinimumHeight(44)
        self.save_button.clicked.connect(self._save)
        self.save_button.setVisible(show_save)
        row.addWidget(self.save_button)
        self.test_button = QPushButton("UJI KONEKSI")
        self.test_button.setObjectName("test-agent-connection")
        self.test_button.setMinimumHeight(44)
        self.test_button.clicked.connect(self._test)
        row.addWidget(self.test_button)
        self.delete_button = QPushButton("HAPUS KEY")
        self.delete_button.setMinimumHeight(44)
        self.delete_button.clicked.connect(self._delete)
        row.addWidget(self.delete_button)
        body.addLayout(row)
        self.test_status = QLabel("BELUM DIUJI")
        self.test_status.setObjectName("agent-test-status")
        self.test_status.setWordWrap(True)
        body.addWidget(self.test_status)
        notice = QLabel(
            "Teks permintaan dikirim ke penyedia. Frame kamera tetap lokal.\n"
            "Uji koneksi mengirim permintaan nyata dan dapat memakai kuota API."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "color: #f5c269; border: 1px solid #856c36; border-radius: 8px; padding: 12px;"
        )
        body.addStretch(1)
        body.addWidget(notice)
        root.addLayout(body, 4)
        initial = list(Provider).index(settings.provider)
        self._select_provider(initial)

    # ------------------------------------------------------------------ draft

    def _select_provider(self, index: int) -> None:
        provider = list(Provider)[index]
        if hasattr(self, "model") and self.model.currentText():
            self._draft.models[self._draft.provider] = self.model.currentText().strip()
            self._draft.ollama_url = self.url.text().strip() or self._draft.ollama_url
        self._draft.provider = provider
        self._provider_buttons[provider].setChecked(True)
        self.model.clear()
        self.model.addItem(self._draft.models[provider])
        if DEFAULT_MODELS[provider] != self._draft.models[provider]:
            self.model.addItem(DEFAULT_MODELS[provider])
        self.model.setCurrentText(self._draft.models[provider])
        self.url.setText(self._draft.ollama_url)
        self.url.setEnabled(provider is Provider.OLLAMA)
        self.key.clear()
        self.eye.setChecked(False)
        self.test_status.setText("BELUM DIUJI")
        self._update_key_status()

    def _toggle_key(self, checked: bool) -> None:
        self.key.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.eye.setText("Sembunyikan" if checked else "Tampilkan")

    def _update_key_status(self) -> None:
        provider = self._draft.provider
        try:
            stored = bool(self._store.get(provider))
        except SettingsError:
            self.key_status.setText(f"Keyring sistem tidak tersedia; gunakan {ENV_KEYS[provider]}.")
            return
        if stored:
            self.key_status.setText("Kunci tersimpan di penyimpanan kredensial sistem.")
        elif os.environ.get(ENV_KEYS[provider]):
            self.key_status.setText(f"Kunci tersedia melalui {ENV_KEYS[provider]}.")
        elif provider is Provider.OLLAMA:
            self.key_status.setText("API key opsional untuk Ollama lokal.")
        else:
            self.key_status.setText("Belum ada API key untuk penyedia ini.")

    def _current(self) -> AgentSettings:
        result = AgentSettings(
            self._draft.provider, dict(self._draft.models), self.url.text().strip()
        )
        result.models[result.provider] = self.model.currentText().strip()
        result.validate()
        return result

    # ------------------------------------------------------------------ actions

    def _save(self) -> bool:
        """Simpan model/penyedia dan key bila diisi; return True bila berhasil."""
        key_stored = False
        try:
            settings = self._current()
            key = self.key.text().strip()
            if key:
                self._store.set(settings.provider, key)
                key_stored = True
            save_settings(settings, self._path)
        except SettingsError as exc:
            note = " API key sudah disimpan di keyring." if key_stored else ""
            self.test_status.setText(str(exc) + note)
            return False
        self._draft = settings
        self.key.clear()
        self.eye.setChecked(False)
        self._update_key_status()
        self.test_status.setText("Pengaturan disimpan.")
        self.saved.emit(settings)
        return True

    def _delete(self) -> None:
        try:
            self._store.delete(self._draft.provider)
        except SettingsError as exc:
            self.test_status.setText(str(exc))
            return
        self.key.clear()
        self._update_key_status()
        self.test_status.setText("Key tersimpan dihapus. Key dari environment tidak diubah.")

    def _test(self) -> None:
        try:
            settings = self._current()
        except SettingsError as exc:
            self.test_status.setText(str(exc))
            return
        key = self.key.text().strip() or resolve_key(settings.provider, self._store)
        if self._tester.submit("Balas dengan kata OK.", settings=settings, key=key):
            self.test_status.setText("Menguji koneksi dengan permintaan nyata…")

    def _test_success(self, text: str) -> None:
        del text
        self.test_status.setText("Koneksi berhasil · respons nyata diterima.")

    def _test_error(self, message: str) -> None:
        self.test_status.setText(f"Uji gagal: {message}")

    def _test_busy(self, busy: bool) -> None:
        for button in self._provider_buttons.values():
            button.setEnabled(not busy)
        self.save_button.setEnabled(not busy)
        self.test_button.setEnabled(not busy)
        self.delete_button.setEnabled(not busy)
        self.model.setEnabled(not busy)
        self.key.setEnabled(not busy)
        self.url.setEnabled(not busy and self._draft.provider is Provider.OLLAMA)


class AgentSettingsDialog(QDialog):
    """Dialog tunggal untuk :class:`AgentSettingsPage` (kompatibilitas Fase 6)."""

    #: Pengaturan agen tersimpan (payload: :class:`AgentSettings`).
    saved = Signal(object)

    def __init__(
        self,
        settings: AgentSettings,
        store: CredentialStore,
        *,
        path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pengaturan · Agen & API")
        self.setObjectName("agent-settings")
        self.resize(900, 600)
        self.setStyleSheet(SETTINGS_QSS)
        self.page = AgentSettingsPage(settings, store, path=path, parent=self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(self.page)
        self.page.saved.connect(self.saved)

    def __getattr__(self, name: str) -> Any:
        """Delegasikan atribut halaman (dipakai tes dan ControlWindow)."""
        if name == "page" or name.startswith("__"):
            raise AttributeError(name)
        return getattr(self.page, name)

    def accept(self) -> None:
        if self.page._tester.busy:
            self.page.test_status.setText("Tunggu uji koneksi selesai sebelum menutup.")
            return
        self.page.key.clear()
        super().accept()

    def reject(self) -> None:
        if self.page._tester.busy:
            self.page.test_status.setText("Tunggu uji koneksi selesai sebelum menutup.")
            return
        self.page.key.clear()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.page._tester.busy:
            self.page.test_status.setText("Tunggu uji koneksi selesai sebelum menutup.")
            event.ignore()
            return
        self.page.key.clear()
        super().closeEvent(event)
