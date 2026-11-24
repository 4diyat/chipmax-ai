"""Pengaturan tampilan, kamera, dan gestur (Fase 7).

Dialog ini menyatukan empat halaman: Agen & API, Tampilan, Kamera, dan Gestur.
Nilai yang belum disimpan hanya berupa draf; ``SIMPAN PENGATURAN`` memvalidasi
semua halaman sebelum menulis ``config.json`` secara atomik. Tidak ada kredensial
yang ditulis ke konfigurasi ini.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from jarvis_hands.agent.settings import AgentSettings, CredentialStore
from jarvis_hands.core.config import (
    AppConfig,
    CameraConfig,
    ConfigError,
    DisplayMode,
    GestureThresholds,
    KeyColor,
    normalize_hex,
    save_config,
)
from jarvis_hands.ui.accessibility import enforce_min_targets
from jarvis_hands.ui.agent_settings import AgentSettingsPage
from jarvis_hands.ui.icons import IconGlyph, IconKind, icon_icon
from jarvis_hands.ui.qss import dialog_qss, style_form_labels
from jarvis_hands.ui.tokens import FONT, Theme, build_theme, mono_font

__all__ = [
    "CameraSettingsPage",
    "DisplaySettingsPage",
    "GestureSettingsPage",
    "SettingsDialog",
]


def _plain_label(text: str) -> str:
    """Tampilkan ``&`` apa adanya pada teks tombol.

    Qt memperlakukan ``&`` sebagai penanda huruf pintas, sehingga "AGEN & API"
    akan tampil "AGEN_API" tanpa escape ganda.
    """
    return text.replace("&", "&&")


def _rgba(color: QColor, alpha: float) -> str:
    """QColor + alpha menjadi ``rgba(...)`` untuk stylesheet."""
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {max(0.0, min(1.0, alpha)):.3f})"


class DisplaySettingsPage(QWidget):
    """Mode tampilan, warna kunci, kontras, auto-hide, dan skala UI."""

    def __init__(
        self,
        config: AppConfig,
        *,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self._config = config
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setContentsMargins(0, 0, 0, 0)
        self.mode = QComboBox()
        self.mode.setObjectName("display-mode")
        self.mode.addItem("Overlay · tembus klik", DisplayMode.OVERLAY.value)
        self.mode.addItem("Cermin · frame kamera", DisplayMode.MIRROR.value)
        self.mode.addItem("Chroma key · latar solid", DisplayMode.KEY.value)
        form.addRow("MODE TAMPILAN", self.mode)
        self.key_color = QComboBox()
        self.key_color.setObjectName("display-key-color")
        self.key_color.addItem("Magenta", KeyColor.MAGENTA.value)
        self.key_color.addItem("Hijau", KeyColor.GREEN.value)
        self.key_color.addItem("Biru", KeyColor.BLUE.value)
        self.key_color.addItem("Kustom", KeyColor.CUSTOM.value)
        self.key_color.currentIndexChanged.connect(self._key_color_changed)
        form.addRow("WARNA KUNCI", self.key_color)
        self.custom_hex = QLineEdit()
        self.custom_hex.setObjectName("display-custom-hex")
        self.custom_hex.setPlaceholderText("#RRGGBB")
        self.custom_hex.setMaxLength(9)
        form.addRow("HEX KUSTOM", self.custom_hex)
        self.high_contrast = QCheckBox("Kontras tinggi")
        self.high_contrast.setObjectName("display-high-contrast")
        form.addRow("KONTRAS", self.high_contrast)
        self.auto_hide_enabled = QCheckBox("Sembunyikan chrome saat idle")
        self.auto_hide_enabled.setObjectName("display-auto-hide")
        form.addRow("AUTO-HIDE", self.auto_hide_enabled)
        self.auto_hide_s = QSpinBox()
        self.auto_hide_s.setObjectName("display-auto-hide-s")
        self.auto_hide_s.setRange(1, 600)
        self.auto_hide_s.setSuffix(" dtk")
        self.auto_hide_s.setAccessibleName("Jeda auto-hide dalam detik")
        form.addRow("JEDA AUTO-HIDE", self.auto_hide_s)
        self.ui_scale = QDoubleSpinBox()
        self.ui_scale.setObjectName("display-ui-scale")
        self.ui_scale.setRange(0.5, 3.0)
        self.ui_scale.setSingleStep(0.1)
        self.ui_scale.setDecimals(2)
        self.ui_scale.setSuffix(" ×")
        form.addRow("SKALA UI", self.ui_scale)
        note = QLabel(
            "Mode dan warna kunci langsung diterapkan. Kontras tinggi dan skala UI "
            "diterapkan setelah aplikasi dimulai ulang."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {self._theme.palette.warning.name()};")
        form.addRow(note)
        style_form_labels(form)
        self.mode.setAccessibleName("Mode tampilan")
        self.key_color.setAccessibleName("Warna kunci chroma key")
        self.custom_hex.setAccessibleName("Hex warna kunci kustom")
        self.high_contrast.setAccessibleName("Kontras tinggi")
        self.auto_hide_enabled.setAccessibleName("Sembunyikan chrome saat idle")
        self.auto_hide_s.setAccessibleName("Jeda auto-hide dalam detik")
        self.ui_scale.setAccessibleName("Skala UI")
        self.load(config)
        enforce_min_targets(self)

    # ------------------------------------------------------------------ state

    def load(self, config: AppConfig) -> None:
        self._config = config
        display = config.display
        self.mode.setCurrentIndex(self.mode.findData(display.mode.value))
        self.key_color.setCurrentIndex(self.key_color.findData(display.key_color.value))
        self.custom_hex.setText(display.custom_key_hex)
        self.high_contrast.setChecked(display.high_contrast)
        self.auto_hide_enabled.setChecked(display.auto_hide_enabled)
        self.auto_hide_s.setValue(display.auto_hide_s)
        self.ui_scale.setValue(display.ui_scale)
        self._key_color_changed()

    def apply(self, config: AppConfig) -> AppConfig:
        """Validasi draf dan kembalikan konfigurasi baru (tanpa mutasi asli)."""
        key = KeyColor(self.key_color.currentData())
        custom = config.display.custom_key_hex
        if key is KeyColor.CUSTOM:
            custom = normalize_hex(self.custom_hex.text())
        return replace(
            config,
            display=replace(
                config.display,
                mode=DisplayMode(self.mode.currentData()),
                key_color=key,
                custom_key_hex=custom,
                high_contrast=self.high_contrast.isChecked(),
                auto_hide_s=int(self.auto_hide_s.value()),
                auto_hide_enabled=self.auto_hide_enabled.isChecked(),
                ui_scale=float(self.ui_scale.value()),
            ),
        )

    def reset(self) -> None:
        self.load(AppConfig.default())

    # ------------------------------------------------------------------ private

    def _key_color_changed(self) -> None:
        custom = self.key_color.currentData() == KeyColor.CUSTOM.value
        self.custom_hex.setEnabled(custom)


class CameraSettingsPage(QWidget):
    """Kamera, resolusi, laju analisis, dan batas CPU."""

    #: Pengguna meminta panduan kamera dibuka dari pengaturan.
    onboarding_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        *,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self._config = config
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setContentsMargins(0, 0, 0, 0)
        self.index = QSpinBox()
        self.index.setObjectName("camera-index")
        self.index.setRange(0, 16)
        form.addRow("INDEKS KAMERA", self.index)
        size_row = QHBoxLayout()
        self.frame_width = QSpinBox()
        self.frame_width.setObjectName("camera-width")
        self.frame_width.setRange(160, 3840)
        self.frame_width.setSingleStep(2)
        size_row.addWidget(self.frame_width, 1)
        size_row.addWidget(QLabel("×"))
        self.frame_height = QSpinBox()
        self.frame_height.setObjectName("camera-height")
        self.frame_height.setRange(90, 2160)
        self.frame_height.setSingleStep(2)
        size_row.addWidget(self.frame_height, 1)
        form.addRow("RESOLUSI", size_row)
        self.fps = QSpinBox()
        self.fps.setObjectName("camera-fps")
        self.fps.setRange(1, 120)
        self.fps.setSuffix(" fps")
        form.addRow("LAJU CAPTURE", self.fps)
        self.mirror = QCheckBox("Cermin (mirror)")
        self.mirror.setObjectName("camera-mirror")
        form.addRow("CERMIN", self.mirror)
        self.use_dshow = QCheckBox("DirectShow (hanya Windows)")
        self.use_dshow.setObjectName("camera-dshow")
        self.use_dshow.setEnabled(sys.platform == "win32")
        if sys.platform != "win32":
            self.use_dshow.setToolTip("Opsi ini hanya berlaku pada Windows.")
        form.addRow("DIRECTSHOW", self.use_dshow)
        self.analysis_fps = QSpinBox()
        self.analysis_fps.setObjectName("camera-analysis-fps")
        self.analysis_fps.setRange(1, 120)
        self.analysis_fps.setSuffix(" fps")
        form.addRow("LAJU ANALISIS", self.analysis_fps)
        self.analysis_scale = QDoubleSpinBox()
        self.analysis_scale.setObjectName("camera-analysis-scale")
        self.analysis_scale.setRange(0.25, 1.0)
        self.analysis_scale.setSingleStep(0.05)
        self.analysis_scale.setDecimals(2)
        form.addRow("SKALA ANALISIS", self.analysis_scale)
        self.max_cpu = QDoubleSpinBox()
        self.max_cpu.setObjectName("camera-max-cpu")
        self.max_cpu.setRange(5.0, 100.0)
        self.max_cpu.setSingleStep(1.0)
        self.max_cpu.setDecimals(1)
        self.max_cpu.setSuffix(" %")
        form.addRow("BATAS CPU", self.max_cpu)
        note = QLabel(
            "Perubahan kamera diterapkan saat kamera dinyalakan kembali. "
            "Frame diproses lokal dan tidak pernah disimpan."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {self._theme.palette.warning.name()};")
        form.addRow(note)
        self.guide_button = QPushButton("BUKA PANDUAN KAMERA")
        self.guide_button.setObjectName("open-camera-onboarding")
        self.guide_button.setMinimumHeight(44)
        self.guide_button.clicked.connect(self._request_onboarding)
        form.addRow(self.guide_button)
        style_form_labels(form)
        self.index.setAccessibleName("Indeks kamera")
        self.frame_width.setAccessibleName("Lebar frame kamera")
        self.frame_height.setAccessibleName("Tinggi frame kamera")
        self.fps.setAccessibleName("Laju capture kamera")
        self.mirror.setAccessibleName("Cermin kamera")
        self.use_dshow.setAccessibleName("DirectShow Windows")
        self.analysis_fps.setAccessibleName("Laju analisis kamera")
        self.analysis_scale.setAccessibleName("Skala analisis kamera")
        self.max_cpu.setAccessibleName("Batas CPU kamera")
        self.load(config)
        enforce_min_targets(self)

    def load(self, config: AppConfig) -> None:
        self._config = config
        camera = config.camera
        self.index.setValue(camera.index)
        self.frame_width.setValue(camera.width)
        self.frame_height.setValue(camera.height)
        self.fps.setValue(camera.fps)
        self.mirror.setChecked(camera.mirror)
        self.use_dshow.setChecked(camera.use_dshow)
        self.analysis_fps.setValue(camera.analysis_fps)
        self.analysis_scale.setValue(camera.analysis_scale)
        self.max_cpu.setValue(camera.max_cpu_percent)

    def apply(self, config: AppConfig) -> AppConfig:
        """Kembalikan konfigurasi dengan pengaturan kamera dari draf."""
        camera = CameraConfig(
            index=int(self.index.value()),
            width=int(self.frame_width.value()),
            height=int(self.frame_height.value()),
            fps=int(self.fps.value()),
            mirror=self.mirror.isChecked(),
            use_dshow=self.use_dshow.isChecked(),
            analysis_scale=float(self.analysis_scale.value()),
            analysis_fps=int(self.analysis_fps.value()),
            max_cpu_percent=float(self.max_cpu.value()),
        )
        return replace(config, camera=camera)

    def reset(self) -> None:
        self.load(AppConfig.default())

    def _request_onboarding(self) -> None:
        self.onboarding_requested.emit()


class GestureSettingsPage(QWidget):
    """Ambang gestur lengkap; semua nilai divalidasi ulang saat menyimpan."""

    def __init__(
        self,
        config: AppConfig,
        *,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme or build_theme()
        self._config = config
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)
        self._int_fields: dict[str, QSpinBox] = {}
        self._float_fields: dict[str, QDoubleSpinBox] = {}

        pinch = QGroupBox("Cubit, ketuk, tahan & seret")
        pinch_form = QFormLayout(pinch)
        pinch_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._add_float(pinch_form, "pinch_close", "CUBIT MENUTUP", 0.05, 0.90, 0.01)
        self._add_float(pinch_form, "pinch_open", "CUBIT MEMBUKA", 0.10, 1.00, 0.01)
        self._add_int(pinch_form, "tap_min_ms", "KETUK MINIMUM", 0, 1000, " ms")
        self._add_int(pinch_form, "tap_max_ms", "KETUK MAKSIMUM", 1, 2000, " ms")
        self._add_int(pinch_form, "hold_ms", "TAHAN", 100, 5000, " ms")
        self._add_float(pinch_form, "drag_start_px", "MULAI SERET", 0.0, 200.0, 1.0, " px")
        style_form_labels(pinch_form)
        root.addWidget(pinch)

        hands = QGroupBox("Dua tangan")
        hands_form = QFormLayout(hands)
        hands_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._add_float(hands_form, "two_hand_min_px", "JARAK DUA TANGAN", 0.0, 400.0, 1.0, " px")
        self._add_int(hands_form, "clap_window_ms", "JENDELA CLAP", 50, 2000, " ms")
        self._add_float(hands_form, "clap_approach_px", "PENDEKATAN CLAP", 0.0, 200.0, 1.0, " px")
        self._add_float(
            hands_form, "clap_min_speed_px_s", "KECEPATAN CLAP", 0.0, 5000.0, 10.0, " px/s"
        )
        self._add_float(
            hands_form, "explode_min_speed_px_s", "KECEPATAN EXPLODE", 0.0, 5000.0, 10.0, " px/s"
        )
        style_form_labels(hands_form)
        root.addWidget(hands)

        scrub = QGroupBox("Scrub & jeda")
        scrub_form = QFormLayout(scrub)
        scrub_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._add_int(scrub_form, "scrub_window_ms", "JENDELA SCRUB", 100, 5000, " ms")
        self._add_int(scrub_form, "scrub_reversals", "JUMLAH PEMBALIKAN", 1, 20, "×")
        self._add_float(scrub_form, "scrub_explode_px", "RENTANG SCRUB", 0.0, 500.0, 1.0, " px")
        self._add_int(scrub_form, "gesture_cooldown_ms", "JEDA GESTUR", 0, 5000, " ms")
        style_form_labels(scrub_form)
        root.addWidget(scrub)

        row = QHBoxLayout()
        self.reset_button = QPushButton("PULIHKAN BAWAAN")
        self.reset_button.setObjectName("reset-gesture-settings")
        self.reset_button.setMinimumHeight(44)
        self.reset_button.clicked.connect(self.reset)
        row.addWidget(self.reset_button)
        row.addStretch(1)
        root.addLayout(row)
        note = QLabel(
            "Rasio cubit adalah jarak jempol–telunjuk dibagi lebar telapak. "
            "Kalibrasi dengan tangan nyata; nilai default sudah diuji fixture sintetis."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {self._theme.palette.warning.name()};")
        root.addWidget(note)
        root.addStretch(1)
        self.load(config)
        enforce_min_targets(self)

    # ------------------------------------------------------------------ build

    def _add_int(
        self,
        form: QFormLayout,
        name: str,
        label: str,
        minimum: int,
        maximum: int,
        suffix: str = "",
    ) -> None:
        spin = QSpinBox()
        spin.setObjectName(f"gesture-{name.replace('_', '-')}")
        spin.setRange(minimum, maximum)
        if suffix:
            spin.setSuffix(suffix)
        spin.setAccessibleName(label)
        self._int_fields[name] = spin
        form.addRow(label, spin)

    def _add_float(
        self,
        form: QFormLayout,
        name: str,
        label: str,
        minimum: float,
        maximum: float,
        step: float,
        suffix: str = "",
    ) -> None:
        spin = QDoubleSpinBox()
        spin.setObjectName(f"gesture-{name.replace('_', '-')}")
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setDecimals(2)
        if suffix:
            spin.setSuffix(suffix)
        spin.setAccessibleName(label)
        self._float_fields[name] = spin
        form.addRow(label, spin)

    # ------------------------------------------------------------------ state

    def load(self, config: AppConfig) -> None:
        self._config = config
        thresholds = config.gestures
        for name, int_spin in self._int_fields.items():
            int_spin.setValue(int(getattr(thresholds, name)))
        for name, float_spin in self._float_fields.items():
            float_spin.setValue(float(getattr(thresholds, name)))

    def apply(self, config: AppConfig) -> AppConfig:
        """Bangun ambang baru dan validasi relasi antar nilai."""
        values: dict[str, float | int] = {
            name: spin.value() for name, spin in self._int_fields.items()
        }
        values.update({name: spin.value() for name, spin in self._float_fields.items()})
        thresholds = GestureThresholds(
            pinch_close=float(values["pinch_close"]),
            pinch_open=float(values["pinch_open"]),
            tap_min_ms=int(values["tap_min_ms"]),
            tap_max_ms=int(values["tap_max_ms"]),
            hold_ms=int(values["hold_ms"]),
            drag_start_px=float(values["drag_start_px"]),
            clap_window_ms=int(values["clap_window_ms"]),
            two_hand_min_px=float(values["two_hand_min_px"]),
            scrub_explode_px=float(values["scrub_explode_px"]),
            scrub_window_ms=int(values["scrub_window_ms"]),
            scrub_reversals=int(values["scrub_reversals"]),
            clap_approach_px=float(values["clap_approach_px"]),
            clap_min_speed_px_s=float(values["clap_min_speed_px_s"]),
            explode_min_speed_px_s=float(values["explode_min_speed_px_s"]),
            gesture_cooldown_ms=int(values["gesture_cooldown_ms"]),
        )
        if thresholds.pinch_close >= thresholds.pinch_open:
            raise ConfigError("gestures.pinch_close harus lebih kecil dari gestures.pinch_open")
        if thresholds.tap_min_ms > thresholds.tap_max_ms:
            raise ConfigError("gestures.tap_min_ms tidak boleh melebihi gestures.tap_max_ms")
        return replace(config, gestures=thresholds)

    def reset(self) -> None:
        self.load(AppConfig.default())


#: Gaya tombol navigasi sidebar: ikon di kiri, teks mono kapital.
_NAV_QSS = (
    "QPushButton { text-align: left; padding-left: 14px; }"
    "QPushButton:checked { font-weight: bold; }"
)


#: Ikon sidebar per halaman.
_NAV_ICONS: dict[str, IconKind] = {
    "agent": IconKind.GEAR,
    "display": IconKind.DISPLAY,
    "camera": IconKind.CAMERA,
    "gesture": IconKind.HAND,
}


class SettingsDialog(QDialog):
    """Pengaturan terpadu: Agen & API, Tampilan, Kamera, dan Gestur."""

    #: Konfigurasi aplikasi tersimpan (payload: :class:`AppConfig`).
    saved = Signal(object)
    #: Pengaturan agen tersimpan (payload: :class:`AgentSettings`).
    agent_saved = Signal(object)
    #: Panduan kamera diminta dari halaman Kamera.
    onboarding_requested = Signal()

    def __init__(
        self,
        config: AppConfig,
        agent_settings: AgentSettings,
        store: CredentialStore,
        *,
        config_path: Path | None = None,
        agent_path: Path | None = None,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._config_path = config_path
        self._agent_path = agent_path
        self._theme = theme or build_theme(config.display.high_contrast)
        self.setWindowTitle("Pengaturan · JARVIS")
        self.setObjectName("settings-dialog")
        self.resize(980, 700)
        self.setStyleSheet(dialog_qss(self._theme))

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(26)
        side_widget = QWidget()
        side_widget.setFixedWidth(212)
        side = QVBoxLayout(side_widget)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(6)
        heading = QLabel("PENGATURAN")
        heading.setFont(mono_font(FONT.body, spacing=6.0))
        heading.setStyleSheet(f"color: {self._theme.palette.teal.name()};")
        side.addWidget(heading)
        underline = QFrame()
        underline.setObjectName("sidebar-rule")
        underline.setFixedHeight(1)
        underline.setStyleSheet(
            f"background: {_rgba(self._theme.palette.border, 0.45)}; border: none;"
        )
        side.addWidget(underline)
        side.addSpacing(6)
        self._nav_icons = _NAV_ICONS
        self._nav = QButtonGroup(self)
        self._nav.setExclusive(True)
        self._nav_buttons: list[QPushButton] = []
        for index, (label, name) in enumerate(
            (
                ("AGEN & API", "agent"),
                ("TAMPILAN", "display"),
                ("KAMERA", "camera"),
                ("GESTUR", "gesture"),
            )
        ):
            button = QPushButton(_plain_label(label))
            button.setObjectName(f"settings-nav-{name}")
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.setMinimumHeight(44)
            button.setIcon(icon_icon(self._nav_icons[name], self._theme.palette.teal, size=18))
            button.setIconSize(QSize(18, 18))
            # Ikon di kiri teks dengan jarak 12 px (QSS padding tidak menyisakan
            # ruang untuk ikon, jadi jarak diatur lewat awalan ruang tipis).
            button.setStyleSheet(_NAV_QSS)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(label)
            self._nav.addButton(button, index)
            self._nav_buttons.append(button)
            side.addWidget(button)
        self._nav.idClicked.connect(self._show_page)
        side.addStretch(1)
        root.addWidget(side_widget)

        body = QVBoxLayout()
        body.setSpacing(14)
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addStretch(1)
        self.logo = IconGlyph(IconKind.BLOOM, self._theme, size=64)
        self.logo.setAccessibleName("Lambang JARVIS")
        header.addWidget(self.logo)
        self.header_close = QPushButton("")
        self.header_close.setObjectName("close-settings-x")
        self.header_close.setFlat(True)
        self.header_close.setFixedSize(44, 44)
        self.header_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_close.setAccessibleName("Tutup pengaturan")
        self.header_close.setToolTip("Tutup (Esc)")
        self.header_close.setIcon(icon_icon(IconKind.CLOSE, self._theme.palette.accent, size=20))
        self.header_close.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0px; }"
            "QPushButton:hover, QPushButton:focus { background: transparent; border: none; }"
        )
        self.header_close.clicked.connect(self.reject)
        header.addWidget(self.header_close, 0, Qt.AlignmentFlag.AlignTop)
        body.addLayout(header)
        self.pages = QStackedWidget()
        self.agent_page = AgentSettingsPage(
            agent_settings,
            store,
            path=agent_path,
            show_save=False,
            embedded=True,
            theme=self._theme,
            parent=self,
        )
        self.display_page = DisplaySettingsPage(config, theme=self._theme, parent=self)
        self.camera_page = CameraSettingsPage(config, theme=self._theme, parent=self)
        self.gesture_page = GestureSettingsPage(config, theme=self._theme, parent=self)
        self.gesture_scroll = QScrollArea()
        self.gesture_scroll.setWidgetResizable(True)
        self.gesture_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.gesture_scroll.setWidget(self.gesture_page)
        self.gesture_scroll.setMinimumHeight(340)
        self.gesture_scroll.setMaximumHeight(500)
        for page in (self.agent_page, self.display_page, self.camera_page, self.gesture_scroll):
            self.pages.addWidget(page)
        body.addWidget(self.pages, 1)
        self.status = QLabel("Perubahan belum disimpan.")
        self.status.setObjectName("settings-status")
        self.status.setAccessibleName("Status pengaturan")
        self.status.setWordWrap(True)
        body.addWidget(self.status)
        actions = QHBoxLayout()
        self.close_button = QPushButton("TUTUP")
        self.close_button.setObjectName("close-settings")
        self.close_button.setMinimumHeight(44)
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        actions.addStretch(1)
        self.save_button = QPushButton("SIMPAN PENGATURAN")
        self.save_button.setObjectName("save-settings")
        self.save_button.setProperty("primary", True)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setMinimumHeight(44)
        self.save_button.clicked.connect(self._save)
        actions.addWidget(self.save_button)
        body.addLayout(actions)
        root.addLayout(body, 1)

        self.agent_page.saved.connect(self.agent_saved)
        self.camera_page.onboarding_requested.connect(self.onboarding_requested)
        self.agent_page._tester.busy_changed.connect(self._tester_busy)
        self._nav_buttons[0].setChecked(True)
        self._nav_buttons[0].setProperty("current", True)
        self.pages.setCurrentIndex(0)

    # ------------------------------------------------------------------ props

    @property
    def config(self) -> AppConfig:
        """Konfigurasi terakhir yang tersimpan/terapkan."""
        return self._config

    def __getattr__(self, name: str) -> Any:
        """Delegasikan atribut halaman agen (kompatibilitas ControlWindow/tes)."""
        if name == "agent_page" or name.startswith("__"):
            raise AttributeError(name)
        return getattr(self.agent_page, name)

    # ------------------------------------------------------------------ actions

    def _show_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for position, button in enumerate(self._nav_buttons):
            button.setProperty("current", position == index)
            button.style().unpolish(button)
            button.style().polish(button)

    def apply_external_config(self, config: AppConfig) -> None:
        """Segarkan draf setelah konfigurasi berubah di luar dialog (onboarding)."""
        self._config = config
        self.display_page.load(config)
        self.camera_page.load(config)
        self.gesture_page.load(config)
        self._set_status("Pengaturan diperbarui dari panduan kamera.")

    def _save(self) -> None:
        try:
            config = self.display_page.apply(self._config)
            config = self.camera_page.apply(config)
            config = self.gesture_page.apply(config)
        except ConfigError as exc:
            self._set_status(f"Tidak disimpan: {exc}", error=True)
            return
        if self._config_path is not None:
            try:
                save_config(config, self._config_path)
            except ConfigError as exc:
                self._set_status(f"Tidak disimpan: {exc}", error=True)
                return
        self._config = config
        if self.agent_page._save():
            self._set_status("Pengaturan disimpan.")
        else:
            self._set_status(
                "Pengaturan tampilan/kamera/gestur disimpan; "
                "periksa pesan pada halaman Agen & API.",
                error=True,
            )
        self.saved.emit(config)

    def _tester_busy(self, busy: bool) -> None:
        self.save_button.setEnabled(not busy)
        self.close_button.setEnabled(not busy)

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status.setText(text)
        color = self._theme.palette.warning if error else self._theme.palette.accent
        self.status.setStyleSheet(f"color: {color.name()};")

    def accept(self) -> None:
        if self.agent_page._tester.busy:
            self._set_status("Tunggu uji koneksi selesai sebelum menutup.", error=True)
            return
        self.agent_page.key.clear()
        super().accept()

    def reject(self) -> None:
        if self.agent_page._tester.busy:
            self._set_status("Tunggu uji koneksi selesai sebelum menutup.", error=True)
            return
        self.agent_page.key.clear()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.agent_page._tester.busy:
            self._set_status("Tunggu uji koneksi selesai sebelum menutup.", error=True)
            event.ignore()
            return
        self.agent_page.key.clear()
        super().closeEvent(event)
