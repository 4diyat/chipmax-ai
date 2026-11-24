"""Onboarding kamera dan gestur (Fase 7).

Panduan empat langkah: selamat datang + privasi, uji kamera dengan pratinjau
lokal, latihan gestur, lalu ringkasan. Frame hanya ditampilkan di memori dan
dihapus saat kamera berhenti. ``onboarding_done`` disimpan hanya bila pengguna
menyelesaikan atau melewati panduan.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
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
from jarvis_hands.ui.agent_settings import SETTINGS_QSS
from jarvis_hands.ui.camera import CameraIndicator
from jarvis_hands.ui.tokens import Theme, build_theme
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
        self.setStyleSheet(SETTINGS_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)
        head = QHBoxLayout()
        title = QLabel("PANDUAN KAMERA & GESTUR")
        title.setStyleSheet("color: #6fe5d6; font-size: 16px; font-weight: bold;")
        head.addWidget(title)
        head.addStretch(1)
        self.step_label = QLabel("1 / 4")
        self.step_label.setObjectName("onboarding-step")
        self.step_label.setStyleSheet("color: #a8d8cf;")
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
        self.status.setStyleSheet("color: #f5c269;")
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

    # ------------------------------------------------------------------ pages

    def _build_welcome(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)
        title = QLabel("Selamat datang di JARVIS")
        title.setStyleSheet("color: #ecfffa; font-size: 28px; font-weight: bold;")
        box.addWidget(title)
        box.addWidget(
            _muted("JARVIS Ring & Hands mengendalikan antarmuka kaca dengan tangan kosong.")
        )
        box.addWidget(_muted("Tiga hal yang perlu diketahui:"))
        for text in (
            "Cubit jempol–telunjuk untuk mengetuk, menahan, dan menyeret.",
            "Kamera hanya menyala saat Anda menyalakannya; frame diproses lokal.",
            "Tidak ada frame yang disimpan atau dikirim; indikator kamera selalu terlihat.",
        ):
            box.addWidget(_bullet(text))
        box.addStretch(1)
        note = QLabel("Mouse dan keyboard tetap tersedia sebagai jalur cadangan.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #8ff0e4;")
        box.addWidget(note)
        return page

    def _build_camera(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)
        title = QLabel("Nyalakan kamera")
        title.setStyleSheet("color: #ecfffa; font-size: 24px; font-weight: bold;")
        box.addWidget(title)
        box.addWidget(
            _muted(
                "Uji kamera dan izin akses. Pratinjau hanya ada di layar ini; "
                "frame tidak pernah ditulis ke disk."
            )
        )
        row = QHBoxLayout()
        self.preview = QLabel("KAMERA MATI")
        self.preview.setObjectName("onboarding-preview")
        self.preview.setAccessibleName("Pratinjau kamera lokal")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(320, 180)
        self.preview.setStyleSheet(
            "background: #04100f; border: 1px solid #548f88; border-radius: 10px;color: #688d87;"
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
            _muted("Izin kamera diminta oleh sistem operasi saat kamera pertama dinyalakan.")
        )
        return page

    def _build_gestures(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)
        title = QLabel("Gestur dasar")
        title.setStyleSheet("color: #ecfffa; font-size: 24px; font-weight: bold;")
        box.addWidget(title)
        box.addWidget(_muted("Cubit adalah jempol dan telunjuk yang dirapatkan."))
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
            grid.addWidget(_gesture_card(head, body), row, col)
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
            "color: #8ff0e4; border: 1px solid #35514d; border-radius: 8px; padding: 10px;"
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
        title.setStyleSheet("color: #ecfffa; font-size: 24px; font-weight: bold;")
        box.addWidget(title)
        box.addWidget(
            _muted(
                "Nyalakan kamera dari jendela kontrol kapan saja. "
                "Ctrl+Alt+G menjeda gestur tanpa mematikan kamera."
            )
        )
        box.addWidget(
            _muted("Pengaturan tampilan, kamera, dan gestur tersedia di jendela kontrol.")
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
        self.status.setStyleSheet("color: #f5a524;" if error else "color: #f5c269;")

    def reject(self) -> None:
        if not self._stop_camera():
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self._stop_camera():
            event.ignore()
            return
        super().closeEvent(event)


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #c2e8e1;")
    return label


def _bullet(text: str) -> QLabel:
    label = QLabel("•  " + text)
    label.setWordWrap(True)
    label.setStyleSheet("color: #c2e8e1; padding-left: 6px;")
    return label


def _gesture_card(head: str, body: str) -> QFrame:
    card = QFrame()
    card.setStyleSheet(
        "QFrame { background: #112524; border: 1px solid #548f88; border-radius: 10px; }"
        "QLabel { border: none; }"
    )
    box = QVBoxLayout(card)
    box.setContentsMargins(14, 12, 14, 12)
    box.setSpacing(4)
    title = QLabel(head)
    title.setStyleSheet("color: #6fe5d6; font-weight: bold;")
    box.addWidget(title)
    text = QLabel(body)
    text.setWordWrap(True)
    text.setStyleSheet("color: #c2e8e1;")
    box.addWidget(text)
    return card
