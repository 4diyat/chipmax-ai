"""Onboarding kamera dan gestur (Fase 7).

Panduan empat langkah: selamat datang + privasi, uji kamera dengan pratinjau
lokal, latihan gestur, lalu ringkasan. Frame hanya ditampilkan di memori dan
dihapus saat kamera berhenti. ``onboarding_done`` disimpan hanya bila pengguna
menyelesaikan atau melewati panduan.
"""

from __future__ import annotations

import html
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from jarvis_hands.core.config import AppConfig, ConfigError, save_config
from jarvis_hands.gestures.engine import GestureEngine
from jarvis_hands.ui.accessibility import enforce_min_targets
from jarvis_hands.ui.camera import CameraIndicator
from jarvis_hands.ui.qss import dialog_qss
from jarvis_hands.ui.tokens import FONT, Theme, build_theme, mono_font, sans_font, with_alpha
from jarvis_hands.vision.camera import Frame
from jarvis_hands.vision.session import CameraSession
from jarvis_hands.vision.tracker import TrackingResult

__all__ = ["OnboardingDialog"]


class OnboardingDialog(QDialog):
    """Panduan awal: privasi, uji kamera, gestur, dan selesai."""

    #: Panduan selesai/dilewati (payload: :class:`AppConfig` terbaru).
    completed = Signal(object)

    def __init__(
        self,
        config: AppConfig,
        *,
        config_path: Path | None = None,
        session: CameraSession | None = None,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._theme = theme or build_theme(config.display.high_contrast)
        self._step = 0
        self._skipped = False
        self.session = session or CameraSession(config.camera, parent=self)
        self._coach = GestureEngine(
            thresholds=config.gestures,
            cursor_config=config.cursor,
            screen_width=1920,
            screen_height=1080,
        )
        self.setWindowTitle("Panduan · JARVIS")
        self.setObjectName("onboarding-dialog")
        self.resize(820, 620)
        self.setStyleSheet(dialog_qss(self._theme))

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)
        head = QHBoxLayout()
        title = QLabel("PANDUAN KAMERA & GESTUR")
        title.setFont(mono_font(FONT.body))
        title.setStyleSheet(f"color: {self._theme.palette.teal.name()};")
        head.addWidget(title)
        head.addStretch(1)
        self.step_label = QLabel("1 / 4")
        self.step_label.setObjectName("onboarding-step")
        self.step_label.setFont(mono_font(FONT.small))
        self.step_label.setStyleSheet(f"color: {self._theme.palette.muted.name()};")
        head.addWidget(self.step_label)
        root.addLayout(head)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_welcome())
        self.pages.addWidget(self._build_camera())
        self.pages.addWidget(self._build_gestures())
        self.pages.addWidget(self._build_done())
        root.addWidget(self.pages, 1)

        self.status = QLabel("Kamera mati · aktifkan hanya bila diperlukan")
        self.status.setObjectName("onboarding-status")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {self._theme.palette.warning.name()};")
        root.addWidget(self.status)

        nav = QHBoxLayout()
        self.skip_button = QPushButton("LEWATI")
        self.skip_button.setObjectName("onboarding-skip")
        self.skip_button.setMinimumHeight(44)
        self.skip_button.clicked.connect(self._skip)
        nav.addWidget(self.skip_button)
        nav.addStretch(1)
        self.back_button = QPushButton("KEMBALI")
        self.back_button.setObjectName("onboarding-back")
        self.back_button.setMinimumHeight(44)
        self.back_button.clicked.connect(self._back)
        nav.addWidget(self.back_button)
        self.next_button = QPushButton("LANJUT")
        self.next_button.setObjectName("onboarding-next")
        self.next_button.setMinimumHeight(44)
        self.next_button.clicked.connect(self._next)
        nav.addWidget(self.next_button)
        root.addLayout(nav)

        self.session.active_changed.connect(self._on_active)
        self.session.error.connect(self._on_error)
        self.session.landmarks_ready.connect(self._on_tracking)
        self.session.frame_ready.connect(self._on_frame)
        self._show_step(0)
        enforce_min_targets(self)

    # ------------------------------------------------------------------ pages

    def _build_welcome(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)
        title = QLabel("Selamat datang di JARVIS")
        title.setFont(sans_font(FONT.display, bold=True))
        title.setStyleSheet(f"color: {self._theme.palette.text.name()};")
        box.addWidget(title)
        box.addWidget(
            _muted(
                "JARVIS Ring & Hands mengendalikan antarmuka kaca dengan tangan kosong.",
                self._theme,
            )
        )
        box.addWidget(_muted("Tiga hal yang perlu diketahui:", self._theme))
        for text in (
            "Cubit jempol–telunjuk untuk mengetuk, menahan, dan menyeret.",
            "Kamera hanya menyala saat Anda menyalakannya; frame diproses lokal.",
            "Tidak ada frame yang disimpan atau dikirim; indikator kamera selalu terlihat.",
        ):
            box.addWidget(_bullet(text, self._theme))
        # Catatan kaki mengikuti isi langsung; sisa ruang jatuh ke bawah halaman
        # supaya tidak ada celah besar di tengah (pola yang sama dengan langkah akhir).
        note = QLabel("Mouse dan keyboard tetap tersedia sebagai jalur cadangan.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {self._theme.palette.accent.name()};")
        box.addWidget(note)
        box.addStretch(1)
        return page

    def _build_camera(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)
        title = QLabel("Nyalakan kamera")
        title.setFont(sans_font(FONT.title, bold=True))
        title.setStyleSheet(f"color: {self._theme.palette.text.name()};")
        box.addWidget(title)
        box.addWidget(
            _muted(
                "Uji kamera dan izin akses. Pratinjau hanya ada di layar ini; "
                "frame tidak pernah ditulis ke disk.",
                self._theme,
            )
        )
        row = QHBoxLayout()
        self.preview = QLabel("KAMERA MATI")
        self.preview.setObjectName("onboarding-preview")
        self.preview.setAccessibleName("Pratinjau kamera lokal")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(320, 180)
        stage_bg = with_alpha(self._theme.palette.stage, 0.85).name(QColor.NameFormat.HexArgb)
        edge = with_alpha(self._theme.palette.border, 0.55).name(QColor.NameFormat.HexArgb)
        self.preview.setStyleSheet(
            f"background: {stage_bg}; border: 1px solid {edge}; "
            f"border-radius: {self._theme.style.control_radius:.0f}px; "
            f"color: {self._theme.palette.muted.name()};"
        )
        row.addWidget(self.preview)
        side = QVBoxLayout()
        side.setSpacing(10)
        self.camera_button = QPushButton("NYALAKAN KAMERA")
        self.camera_button.setObjectName("onboarding-camera")
        self.camera_button.setMinimumHeight(44)
        self.camera_button.clicked.connect(self._toggle_camera)
        side.addWidget(self.camera_button)
        self.camera_status = QLabel("Kamera mati")
        self.camera_status.setObjectName("onboarding-camera-status")
        self.camera_status.setAccessibleName("Status kamera")
        self.camera_status.setWordWrap(True)
        side.addWidget(self.camera_status)
        self.indicator = CameraIndicator(self._theme, parent=self)
        side.addWidget(self.indicator)
        side.addStretch(1)
        row.addLayout(side, 1)
        box.addLayout(row)
        box.addStretch(1)
        box.addWidget(
            _muted(
                "Izin kamera diminta oleh sistem operasi saat kamera pertama dinyalakan.",
                self._theme,
            )
        )
        return page

    def _build_gestures(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)
        title = QLabel("Gestur dasar")
        title.setFont(sans_font(FONT.title, bold=True))
        title.setStyleSheet(f"color: {self._theme.palette.text.name()};")
        box.addWidget(title)
        box.addWidget(_muted("Cubit adalah jempol dan telunjuk yang dirapatkan.", self._theme))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        cards = (
            ("CUBIT SINGKAT", "Mengetuk target atau tombol."),
            ("TAHAN 1 DETIK", "Membuka memori dari kartu."),
            ("CUBIT + SERET", "Memindahkan kartu dan panel."),
            ("DUA TANGAN", "Clap dan explode untuk mode berikutnya."),
        )
        for index, (head, body) in enumerate(cards):
            row, col = divmod(index, 2)
            grid.addWidget(_gesture_card(head, body, self._theme), row, col)
        box.addLayout(grid)
        self.gesture_camera_button = QPushButton("NYALAKAN KAMERA")
        self.gesture_camera_button.setObjectName("onboarding-gesture-camera")
        self.gesture_camera_button.setMinimumHeight(44)
        self.gesture_camera_button.clicked.connect(self._toggle_camera)
        box.addWidget(self.gesture_camera_button)
        self.coach_status = QLabel("Nyalakan kamera untuk mencoba gestur.")
        self.coach_status.setObjectName("onboarding-coach")
        self.coach_status.setAccessibleName("Status latihan gestur")
        self.coach_status.setWordWrap(True)
        self.coach_status.setStyleSheet(
            f"color: {self._theme.palette.accent.name()}; "
            f"border: 1px solid {_rgba(self._theme.palette.border, 0.35)}; "
            f"border-radius: {self._theme.style.control_radius:.0f}px; padding: 10px;"
        )
        box.addWidget(self.coach_status)
        box.addStretch(1)
        return page

    def _build_done(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)
        title = QLabel("Siap digunakan")
        title.setFont(sans_font(FONT.title, bold=True))
        title.setStyleSheet(f"color: {self._theme.palette.text.name()};")
        box.addWidget(title)
        box.addWidget(
            _muted(
                "Nyalakan kamera dari jendela kontrol kapan saja. "
                "Ctrl+Alt+G menjeda gestur tanpa mematikan kamera.",
                self._theme,
            )
        )
        box.addWidget(
            _muted(
                "Pengaturan tampilan, kamera, dan gestur tersedia di jendela kontrol.",
                self._theme,
            )
        )
        self.finish_choice = QCheckBox("Jangan tampilkan panduan ini lagi")
        self.finish_choice.setObjectName("onboarding-dont-show")
        self.finish_choice.setAccessibleName("Jangan tampilkan panduan ini lagi")
        self.finish_choice.setChecked(True)
        box.addWidget(self.finish_choice)
        box.addStretch(1)
        return page

    # ------------------------------------------------------------------ state

    @property
    def config(self) -> AppConfig:
        """Konfigurasi terbaru (``onboarding_done`` bila panduan selesai)."""
        return self._config

    @property
    def step(self) -> int:
        """Langkah aktif (0..3)."""
        return self._step

    @property
    def skipped(self) -> bool:
        """True bila pengguna memilih LEWATI."""
        return self._skipped

    # ------------------------------------------------------------------ nav

    def _show_step(self, step: int) -> None:
        if step not in (1, 2):
            self._stop_camera()
        self._step = max(0, min(self.pages.count() - 1, step))
        self.pages.setCurrentIndex(self._step)
        self.step_label.setText(f"{self._step + 1} / {self.pages.count()}")
        self.back_button.setEnabled(self._step > 0)
        self.next_button.setText("SELESAI" if self._step == self.pages.count() - 1 else "LANJUT")
        self.skip_button.setVisible(self._step != self.pages.count() - 1)

    def _next(self) -> None:
        if self._step >= self.pages.count() - 1:
            self._finish(skipped=False)
            return
        self._show_step(self._step + 1)

    def _back(self) -> None:
        if self._step > 0:
            self._show_step(self._step - 1)

    def _skip(self) -> None:
        self._finish(skipped=True)

    def _finish(self, *, skipped: bool) -> None:
        if not self._stop_camera():
            return
        mark_done = skipped or self.finish_choice.isChecked()
        if mark_done:
            self._config = replace(self._config, onboarding_done=True)
            if self._config_path is not None:
                try:
                    save_config(self._config, self._config_path)
                except ConfigError as exc:
                    self._set_status(f"Tidak bisa menyimpan panduan: {exc}", error=True)
                    return
        self._skipped = skipped
        self.completed.emit(self._config)
        self.accept()

    # ------------------------------------------------------------------ camera

    def _toggle_camera(self) -> None:
        if self.session.is_active:
            self._stop_camera()
            return
        self.camera_button.setEnabled(False)
        if not self.session.start():
            self.camera_button.setEnabled(True)
            self._set_status("Kamera belum siap; periksa izin dan indeks kamera.", error=True)

    def _stop_camera(self) -> bool:
        if not self.session.stop():
            self._set_status("Kamera belum berhenti; coba lagi.", error=True)
            return False
        self.preview.setPixmap(QPixmap())
        self.preview.setText("KAMERA MATI")
        self.camera_status.setText("Kamera mati")
        self.camera_button.setText("NYALAKAN KAMERA")
        self.camera_button.setEnabled(True)
        self.gesture_camera_button.setText("NYALAKAN KAMERA")
        return True

    def _on_active(self, active: bool) -> None:
        self.camera_button.setEnabled(True)
        self.camera_button.setText("MATIKAN KAMERA" if active else "NYALAKAN KAMERA")
        self.gesture_camera_button.setText("MATIKAN KAMERA" if active else "NYALAKAN KAMERA")
        if active:
            self.camera_status.setText("Kamera aktif · pemrosesan lokal")
            self._set_status("Kamera aktif · pratinjau hanya di layar ini.")
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("KAMERA MATI")
            error = getattr(self.session.controller, "last_error", "")
            self.camera_status.setText(error if error else "Kamera mati")

    def _on_error(self, message: str) -> None:
        self._set_status(f"Kamera: {message}", error=True)

    def _on_frame(self, frame: Frame) -> None:
        if self._step != 1 or not self.session.is_active:
            return
        rgb = frame.rgb
        if rgb.ndim != 3 or rgb.shape[2] != 3:
            return
        image = QImage(
            rgb.data,
            frame.width,
            frame.height,
            int(rgb.strides[0]),
            QImage.Format.Format_RGB888,
        ).copy()
        self.preview.setPixmap(
            QPixmap.fromImage(
                image.scaled(
                    self.preview.width() - 2,
                    self.preview.height() - 2,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        )
        self.preview.setText("")

    def _on_tracking(self, result: TrackingResult) -> None:
        if not self.session.is_active:
            return
        self._coach.process(result)
        sample = self._coach.last_sample
        if sample is None or not sample.visible:
            text = "Arahkan tangan ke kamera"
        elif sample.pinching:
            text = f"Tangan terlihat · cubit {sample.pinch:.0%}"
        else:
            text = "Tangan terlihat · buka jempol–telunjuk"
        if self._step == 2:
            self.coach_status.setText(text)
        if self._step == 1:
            self.camera_status.setText(text)

    # ------------------------------------------------------------------ close

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status.setText(text)
        color = self._theme.palette.warning if error else self._theme.palette.accent
        self.status.setStyleSheet(f"color: {color.name()};")

    def reject(self) -> None:
        if not self._stop_camera():
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._stop_camera():
            event.ignore()
            return
        super().closeEvent(event)


def _rgba(color: QColor, alpha: float) -> str:
    """QColor + alpha menjadi ``rgba(...)`` untuk stylesheet."""
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {max(0.0, min(1.0, alpha)):.3f})"


def _muted(text: str, theme: Theme) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {theme.palette.muted.name()};")
    return label


def _bullet(text: str, theme: Theme) -> QLabel:
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setText(
        f"<p style='margin-left:16px; text-indent:-16px;'>•&nbsp;&nbsp;{html.escape(text)}</p>"
    )
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {theme.palette.muted.name()};")
    return label


def _gesture_card(head: str, body: str, theme: Theme) -> QFrame:
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background: {_rgba(theme.palette.teal, 0.08)}; "
        f"border: 1px solid {_rgba(theme.palette.border, 0.55)}; "
        f"border-radius: {theme.style.control_radius:.0f}px; }}"
        "QLabel { border: none; }"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(14, 12, 14, 12)
    box.setSpacing(4)
    title = QLabel(head)
    title.setFont(mono_font(FONT.small))
    title.setStyleSheet(f"color: {theme.palette.teal.name()};")
    box.addWidget(title)
    text = QLabel(body)
    text.setWordWrap(True)
    text.setStyleSheet(f"color: {theme.palette.muted.name()};")
    box.addWidget(text)
    return card
