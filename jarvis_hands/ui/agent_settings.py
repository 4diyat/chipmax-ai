"""Halaman dan dialog pengaturan penyedia serta kredensial (mockup Agen & API)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
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
    API_LABELS,
    DEFAULT_MODELS,
    DISPLAY,
    ENV_KEYS,
    KEY_PLACEHOLDERS,
    LABELS,
    PROVIDER_NOTES,
    AgentSettings,
    CredentialStore,
    Provider,
    SettingsError,
    resolve_key,
    save_settings,
)
from jarvis_hands.ui.accessibility import enforce_min_targets
from jarvis_hands.ui.icons import IconGlyph, IconKind, icon_icon
from jarvis_hands.ui.qss import SETTINGS_QSS, dialog_qss
from jarvis_hands.ui.tokens import (
    FONT,
    Theme,
    build_theme,
    mono_font,
    rgba_css,
    sans_font,
    with_alpha,
)

__all__ = ["SETTINGS_QSS", "AgentSettingsDialog", "AgentSettingsPage"]


def _rgba(color: QColor, alpha: float) -> str:
    """QColor + alpha menjadi ``rgba(...)`` untuk stylesheet."""
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {max(0.0, min(1.0, alpha)):.3f})"


def _provider_note(provider: Provider) -> str:
    """Baris keterangan penyedia (mockup: hanya Ollama menyebut alamat server)."""
    if provider is Provider.OLLAMA:
        return PROVIDER_NOTES[Provider.OLLAMA]
    return f"Penyedia aktif · {API_LABELS[provider]}"


def _field_label(text: str, theme: Theme) -> QLabel:
    """Label mono kapital di atas kolom input."""
    label = QLabel(text)
    label.setFont(mono_font(FONT.label, spacing=2.5))
    label.setStyleSheet(f"color: {theme.palette.muted.name()};")
    return label


def _hint_label(text: str, theme: Theme) -> QLabel:
    """Keterangan kecil di bawah kontrol."""
    label = QLabel(text)
    label.setFont(sans_font(FONT.label))
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {rgba_css(theme.palette.muted, 0.85)};")
    return label


class _TestBadge(QWidget):
    """Pil status kecil (amber) di kanan baris uji koneksi."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._text = "BELUM DIUJI"
        self.setFont(mono_font(FONT.label, spacing=1.5))
        self.setFixedHeight(24)
        self._resize()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    @property
    def text(self) -> str:
        """Label badge saat ini."""
        return self._text

    def set_state(self, text: str) -> None:
        """Ganti label; hijau untuk sukses, amber untuk belum diuji/gagal."""
        self._text = text.upper()
        self._resize()
        self.update()

    def _resize(self) -> None:
        width = self.fontMetrics().horizontalAdvance(self._text) + 26
        self.setFixedWidth(max(96, width))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        ok = "BERHASIL" in self._text
        color = self._theme.palette.teal if ok else self._theme.palette.warning
        painter.setPen(with_alpha(color, 0.55))
        painter.setBrush(with_alpha(color, 0.10))
        painter.drawRoundedRect(rect, rect.height() / 2.0, rect.height() / 2.0)
        painter.setFont(self.font())
        painter.setPen(with_alpha(color, 0.95))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


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
        embedded: bool = False,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
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
        if not embedded:
            side = QVBoxLayout()
            heading = QLabel("AGEN & API")
            heading.setFont(mono_font(FONT.body))
            heading.setStyleSheet(f"color: {self._theme.palette.teal.name()};")
            side.addWidget(heading)
            side.addWidget(QLabel("Penyedia teks dan kredensial"))
            side.addStretch(1)
            root.addLayout(side, 1)
        body = QVBoxLayout()
        body.setSpacing(12)
        title = QLabel("Agen & API")
        title.setFont(sans_font(FONT.title, bold=True))
        title.setStyleSheet(f"color: {self._theme.palette.text.name()};")
        body.addWidget(title)
        body.addWidget(QLabel("Pilih penyedia dan atur kunci API di perangkat ini"))
        body.addWidget(QLabel("JENIS AGEN"))
        choices = QHBoxLayout()
        self.buttons = QButtonGroup(self)
        self._provider_buttons: dict[Provider, QPushButton] = {}
        for index, provider in enumerate(Provider):
            button = QPushButton(LABELS[provider])
            button.setAccessibleName(f"Penyedia {DISPLAY[provider]}")
            button.setObjectName(f"provider-{provider.value}")
            button.setMinimumHeight(44)
            button.setCheckable(True)
            button.setProperty("provider", True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.buttons.addButton(button, index)
            self._provider_buttons[provider] = button
            choices.addWidget(button)
        self.buttons.idClicked.connect(self._select_provider)
        body.addLayout(choices)
        # Mockup 02: satu baris di bawah segmen penyedia — "Ollama: alamat
        # server · API key opsional" untuk Ollama, "Penyedia aktif · …" lainnya.
        self.note = QLabel(_provider_note(settings.provider))
        self.note.setObjectName("provider-note")
        self.note.setWordWrap(True)
        self.note.setFont(sans_font(FONT.small))
        body.addWidget(self.note)
        # Grid label/kolom menggantikan QFormLayout: label mono berdiri di atas
        # kolom input (mockup), bukan di sampingnya, dan tiap kontrol diberi
        # baris keterangan kecil di bawahnya.
        form = QGridLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(6)
        form.setColumnStretch(1, 1)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setObjectName("agent-model")
        self.model.setAccessibleName("Model agen")
        self.model.setMaximumWidth(380)
        form.addWidget(_field_label("MODEL", self._theme), 0, 0, 1, 2)
        form.addWidget(self.model, 1, 0, 1, 2)
        model_hint = _hint_label("Dapat diubah sesuai akses akun", self._theme)
        form.addWidget(model_hint, 2, 0, 1, 2)
        self.url = QLineEdit()
        self.url.setObjectName("ollama-url")
        self.url.setAccessibleName("Alamat server Ollama")
        self.url.setPlaceholderText("http://127.0.0.1:11434")
        self.url_label = _field_label("ALAMAT OLLAMA", self._theme)
        form.addWidget(self.url_label, 3, 0, 1, 2)
        form.addWidget(self.url, 4, 0, 1, 2)
        self._url_rows = (self.url_label, self.url)
        self.key = QLineEdit()
        self.key.setObjectName("agent-key")
        self.key.setAccessibleName("API key")
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText(KEY_PLACEHOLDERS[settings.provider])
        self.key.setToolTip("Kosongkan untuk mempertahankan key yang tersimpan.")
        # Ikon mata menempel di dalam kolom input (mockup), jadi key dan tombol
        # dibungkus satu baris tanpa kotak tambahan di kanan.
        form.addWidget(_field_label("API KEY", self._theme), 5, 0, 1, 2)
        keyrow = QHBoxLayout()
        keyrow.setSpacing(8)
        keyrow.addWidget(self.key, 1)
        self.eye = QToolButton()
        self.eye.setText("")
        self.eye.setCheckable(True)
        self.eye.setFixedSize(44, 44)
        self.eye.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye.setIcon(icon_icon(IconKind.EYE, self._theme.palette.muted, size=20))
        self.eye.setIconSize(QSize(20, 20))
        self.eye.setStyleSheet("QToolButton { padding: 0px; }")
        self.eye.setAccessibleName("Tampilkan atau sembunyikan API key")
        self.eye.setToolTip("Tampilkan API key")
        self.eye.toggled.connect(self._toggle_key)
        keyrow.addWidget(self.eye)
        keyrow_host = QWidget()
        keyrow_host.setLayout(keyrow)
        form.addWidget(keyrow_host, 6, 0, 1, 2)
        self.key_status = QLabel()
        self.key_status.setObjectName("credential-status")
        self.key_status.setWordWrap(True)
        self.key_status.setFont(sans_font(FONT.label))
        form.addWidget(self.key_status, 7, 0, 1, 2)
        body.addLayout(form)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.save_button = QPushButton("SIMPAN PENGATURAN")
        self.save_button.setObjectName("save-agent-settings")
        self.save_button.setProperty("primary", True)
        self.save_button.setMinimumHeight(44)
        self.save_button.setMinimumWidth(220)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.clicked.connect(self._save)
        self.save_button.setVisible(show_save)
        row.addWidget(self.save_button)
        self.test_button = QPushButton("UJI KONEKSI")
        self.test_button.setObjectName("test-agent-connection")
        self.test_button.setMinimumHeight(44)
        self.test_button.setMinimumWidth(180)
        self.test_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_button.clicked.connect(self._test)
        row.addWidget(self.test_button)
        row.addStretch(1)
        self.delete_button = QToolButton()
        self.delete_button.setObjectName("delete-agent-key")
        self.delete_button.setText("")
        self.delete_button.setFixedSize(44, 44)
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setIcon(icon_icon(IconKind.TRASH, self._theme.palette.muted, size=18))
        self.delete_button.setIconSize(QSize(18, 18))
        self.delete_button.setStyleSheet("QToolButton { padding: 0px; }")
        self.delete_button.setAccessibleName("Hapus API key tersimpan")
        self.delete_button.setToolTip("Hapus key yang tersimpan di keyring")
        self.delete_button.clicked.connect(self._delete)
        row.addWidget(self.delete_button)
        body.addLayout(row)
        # Baris status uji: teks status + badge amber "BELUM DIUJI".
        self.test_status = QLabel("")
        self.test_status.setObjectName("agent-test-status")
        self.test_status.setWordWrap(True)
        self.test_status.setFont(sans_font(FONT.label))
        body.addWidget(self.test_status)
        self.test_badge = _TestBadge(self._theme)

        notice_box = QFrame()
        notice_box.setObjectName("agent-notice")
        notice_box.setStyleSheet(
            f"#agent-notice {{ background: {_rgba(self._theme.palette.warning, 0.08)}; "
            f"border: 1px solid {_rgba(self._theme.palette.warning, 0.55)}; "
            f"border-radius: {self._theme.style.control_radius:.0f}px; }}"
        )
        notice_row = QHBoxLayout(notice_box)
        notice_row.setContentsMargins(14, 12, 14, 12)
        notice_row.setSpacing(12)
        lock = IconGlyph(IconKind.LOCK, self._theme, size=24, color=self._theme.palette.warning)
        notice_row.addWidget(lock, 0, Qt.AlignmentFlag.AlignTop)
        notice = QLabel(
            "Teks permintaan dikirim ke penyedia. Frame kamera tetap lokal.\n"
            "Uji koneksi mengirim permintaan nyata dan dapat memakai kuota API."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(f"color: {self._theme.palette.text.name()}; background: transparent;")
        notice_row.addWidget(notice, 1)
        notice_row.addWidget(self.test_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.notice = notice_box
        body.addStretch(1)
        body.addWidget(notice_box)
        root.addLayout(body, 1 if embedded else 4)
        initial = list(Provider).index(settings.provider)
        self._select_provider(initial)
        enforce_min_targets(self)

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
        self.note.setText(_provider_note(provider))
        self.key.setPlaceholderText(KEY_PLACEHOLDERS[provider])
        self.url.setText(self._draft.ollama_url)
        is_ollama = provider is Provider.OLLAMA
        self.url.setEnabled(is_ollama)
        for row in self._url_rows:
            row.setVisible(is_ollama)
        self.key.clear()
        self.eye.setChecked(False)
        self.test_status.setText("")
        self.test_badge.set_state("BELUM DIUJI")
        self._update_key_status()

    def _toggle_key(self, checked: bool) -> None:
        self.key.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self.eye.setIcon(
            icon_icon(
                IconKind.EYE_OFF if checked else IconKind.EYE,
                self._theme.palette.accent if checked else self._theme.palette.muted,
                size=20,
            )
        )
        self.eye.setToolTip("Sembunyikan API key" if checked else "Tampilkan API key")

    def _update_key_status(self) -> None:
        provider = self._draft.provider
        try:
            stored = bool(self._store.get(provider))
        except SettingsError:
            self._set_key_status(
                f"Keyring sistem tidak tersedia; gunakan {ENV_KEYS[provider]}.", ok=False
            )
            return
        if stored:
            self._set_key_status("Kunci tersimpan di perangkat.", ok=True)
        elif os.environ.get(ENV_KEYS[provider]):
            self._set_key_status(f"Kunci tersedia melalui {ENV_KEYS[provider]}.", ok=True)
        elif provider is Provider.OLLAMA:
            self._set_key_status("API key opsional untuk Ollama lokal.", ok=True)
        else:
            self._set_key_status("Belum ada API key untuk penyedia ini.", ok=False)

    def _set_key_status(self, text: str, *, ok: bool) -> None:
        """Baris status kunci dengan titik warna (hijau tersedia, amber belum)."""
        color = self._theme.palette.teal if ok else self._theme.palette.warning
        self.key_status.setText(
            f'<span style="color:{color.name()};">●</span> '
            f'<span style="color:{self._theme.palette.muted.name()};">{text}</span>'
        )

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
            self.test_badge.set_state("GAGAL")
            return False
        self._draft = settings
        self.key.clear()
        self.eye.setChecked(False)
        self._update_key_status()
        self.test_status.setText("Pengaturan disimpan.")
        self.test_badge.set_state("TERSIMPAN")
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
        self.test_badge.set_state("BERHASIL")

    def _test_error(self, message: str) -> None:
        self.test_status.setText(f"Uji gagal: {message}")
        self.test_badge.set_state("GAGAL")

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
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self.setWindowTitle("Pengaturan · Agen & API")
        self.setObjectName("agent-settings")
        self.resize(900, 620)
        self.setStyleSheet(dialog_qss(self._theme))
        self.page = AgentSettingsPage(settings, store, path=path, theme=self._theme, parent=self)
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
