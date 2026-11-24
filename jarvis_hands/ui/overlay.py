"""Jendela tampilan dan kontrol lokal Fase 5.

Koordinat Qt adalah piksel logis, termasuk origin negatif pada monitor kedua.
Overlay tidak menerima input OS; gestur dirutekan langsung ke komponen. Jendela
kontrol terpisah tetap bisa difokuskan untuk kamera dan jalan keluar yang aman.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QImage,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QScreen,
    QShortcut,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from jarvis_hands.agent.bridge import AgentBridge
from jarvis_hands.agent.gemini import MAX_PROMPT_CHARS
from jarvis_hands.agent.settings import LABELS, AgentSettings, SettingsError, load_settings
from jarvis_hands.core.config import KEY_COLOR_HEX, AppConfig, DisplayMode, KeyColor
from jarvis_hands.gestures.engine import GestureEngine
from jarvis_hands.gestures.types import GestureEvent, GestureKind, GesturePhase
from jarvis_hands.ui.accessibility import enforce_min_targets
from jarvis_hands.ui.autohide import AutoHideController
from jarvis_hands.ui.camera import CameraIndicator
from jarvis_hands.ui.card import Card, Panel
from jarvis_hands.ui.catalog import HintBar, ToastPreview
from jarvis_hands.ui.chrome import ChromeMode, ChromeToggle
from jarvis_hands.ui.cursor import CursorWidget
from jarvis_hands.ui.glass import SurfaceHit, idle_dot_hit_rect, paint_idle_dot
from jarvis_hands.ui.onboarding import OnboardingDialog
from jarvis_hands.ui.orb import Orb
from jarvis_hands.ui.qss import dialog_qss
from jarvis_hands.ui.ring import RingWidget
from jarvis_hands.ui.settings import SettingsDialog
from jarvis_hands.ui.tokens import FONT, build_theme, mono_font
from jarvis_hands.ui.treepane import TreePane
from jarvis_hands.vision.camera import Frame
from jarvis_hands.vision.session import CameraSession
from jarvis_hands.vision.tracker import TrackingResult


class OverlayWindow(QWidget):
    """Kanvas untuk satu monitor; hanya mode overlay tembus klik."""

    gesture = Signal(object)
    close_requested = Signal()

    def __init__(self, config: AppConfig, session: CameraSession, screen: QScreen) -> None:
        super().__init__()
        self.config = config
        self.session = session
        self.screen_target = screen
        self.mode = config.display.mode
        self._theme = build_theme(config.display.high_contrast)
        self._image = QImage()
        self._managed = False
        self._shutdown = False
        self._drag: Card | Panel | None = None
        self._press_target: Card | Panel | None = None
        self._pinch_started: int | None = None
        self._chrome_hidden = False
        self._chrome_visible: list[tuple[QWidget, bool]] = []
        self._dot_hover = False
        self._screen_geometry = QRect(screen.geometry())
        geo = self._screen_geometry
        self.engine = GestureEngine(
            thresholds=config.gestures,
            cursor_config=config.cursor,
            screen_width=geo.width(),
            screen_height=geo.height(),
            origin_x=geo.x(),
            origin_y=geo.y(),
        )
        self.setWindowTitle("JARVIS · tampilan")
        self._apply_flags()
        self.setGeometry(geo)
        self.ring = RingWidget(self._theme, parent=self)
        self.orb = Orb(self._theme, parent=self)
        self.response_panel = Panel(
            "Jawaban Gemini", chips=("TEKS",), theme=self._theme, parent=self
        )
        self.response_text = QPlainTextEdit()
        self.response_text.setReadOnly(True)
        self.response_text.setObjectName("agent-response-overlay")
        self.response_text.setAccessibleName("Jawaban agen")
        self._style_response_text()
        self.response_panel.body().addWidget(self.response_text, 1)
        self.response_panel.close_requested.connect(self.response_panel.hide)
        self.response_panel.hide()
        self.card = Card(
            "Memori",
            "Tahan untuk membuka memori; seret pegangan untuk pindah.",
            theme=self._theme,
            parent=self,
        )
        self.card.opened.connect(self.toggle_tree)
        self.card.close_requested.connect(self.card.hide)
        self.card.dismissed.connect(self.card.hide)
        self.tree = TreePane(config.memory_root, theme=self._theme, parent=self)
        self.tree.close_requested.connect(self.tree.hide)
        self.tree.hide()
        # Toast kanan atas dan baris petunjuk bawah adalah chrome overlay Fase 4.
        self.toast = ToastPreview(self._theme, parent=self)
        self.toast.hide()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.setInterval(4200)
        self._toast_timer.timeout.connect(self.toast.hide)
        self.hint = HintBar(self._theme, parent=self)
        session.fps_changed.connect(self._update_hint)
        self.chrome = ChromeToggle(parent=self)
        self.chrome.mode_changed.connect(self._chrome_mode_changed)
        self.indicator = CameraIndicator(self._theme, parent=self)
        session.attach_indicator(self.indicator)
        self.autohide = AutoHideController(
            config.display.auto_hide_s,
            enabled=config.display.auto_hide_enabled,
            parent=self,
        )
        self.autohide.hidden_changed.connect(self._set_chrome_hidden)
        session.fps_changed.connect(self.indicator.set_fps)
        session.fps_changed.connect(self._position_indicator)
        self.hand_cursor = CursorWidget(self._theme)
        self.hand_cursor.hide()
        session.landmarks_ready.connect(self.on_tracking)
        session.frame_ready.connect(self.on_frame)
        session.active_changed.connect(self._active_changed)
        session.paused_changed.connect(self._paused_changed)
        screen.geometryChanged.connect(self.set_screen_geometry)
        self._layout_items()

    def _apply_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.mode is DisplayMode.OVERLAY:
            flags |= (
                Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.WindowTransparentForInput
                | Qt.WindowType.WindowDoesNotAcceptFocus
            )
        self.setWindowFlags(flags)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, self.mode is DisplayMode.OVERLAY
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating, self.mode is DisplayMode.OVERLAY
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_NoSystemBackground, self.mode is DisplayMode.OVERLAY
        )
        self.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
            if self.mode is DisplayMode.OVERLAY
            else Qt.FocusPolicy.StrongFocus
        )

    def set_mode(self, mode: DisplayMode) -> None:
        if mode is self.mode:
            return
        self._reset_input()
        self.mode = mode
        if mode is not DisplayMode.MIRROR:
            self._image = QImage()
        visible = self.isVisible()
        self._apply_flags()
        self.setGeometry(self._screen_geometry)
        if visible:
            self.show()
        self.update()
        self.autohide.poke()

    def set_screen(self, screen: QScreen) -> None:
        if screen is self.screen_target:
            return
        with contextlib.suppress(RuntimeError, TypeError):
            self.screen_target.geometryChanged.disconnect(self.set_screen_geometry)
        self.screen_target = screen
        screen.geometryChanged.connect(self.set_screen_geometry)
        self.set_screen_geometry(screen.geometry())

    def set_screen_geometry(self, geometry: QRect) -> None:
        self._reset_input()
        self._screen_geometry = QRect(geometry)
        self.engine.set_screen(
            geometry.width(), geometry.height(), origin_x=geometry.x(), origin_y=geometry.y()
        )
        self.setGeometry(geometry)
        self._layout_items()

    def _layout_items(self) -> None:
        w, h = self.width(), self.height()
        self.ring.move(max(0, (w - self.ring.width()) // 2), max(0, (h - self.ring.height()) // 2))
        x = max(0, w - self.card.width() - 12)
        y = max(0, min(h - self.card.height(), h // 2 - self.card.height() // 2))
        self.card.set_bounds(QRectF(0, 0, w, h))
        self.card.set_home(x, y)
        self.tree.resize(min(max(620, w - 40), 1000), min(max(350, h - 40), 480))
        self.tree.move(max(0, (w - self.tree.width()) // 2), max(0, (h - self.tree.height()) // 2))
        self.tree.set_bounds(QRectF(0, 0, w, h))
        self.orb.move(
            min(max(0, self.ring.x() + self.ring.width() - 40), max(0, w - self.orb.width() - 16)),
            self.ring.y() + 44,
        )
        self.response_panel.resize(min(520, max(300, w - 32)), min(300, max(200, h - 32)))
        self.response_panel.move(16, max(0, h - self.response_panel.height() - 16))
        self.response_panel.set_bounds(QRectF(0, 0, w, h))
        self.indicator.move(max(0, w - self.indicator.width() - 18), 18)
        self.toast.move(max(0, w - self.toast.width() - 18), 18 + self.indicator.height() + 10)
        hint_w = max(320, min(self.hint.preferred_width(), w - 96))
        self.hint.resize(hint_w, self.hint.height())
        self.hint.move(max(0, (w - hint_w) // 2), max(0, h - self.hint.height() - 24))
        self.indicator.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "indicator"):
            self._layout_items()

    def toggle_tree(self) -> None:
        self.autohide.poke()
        self.tree.setVisible(not self.tree.isVisible())
        if self.tree.isVisible():
            self.tree.raise_()
            self.indicator.raise_()

    def show_response(self, text: str) -> None:
        """Tampilkan jawaban teks murni, tanpa menjalankan isi respons."""
        self.response_text.setPlainText(text)
        self.response_panel.show()
        self.response_panel.raise_()
        self.indicator.raise_()
        self.autohide.poke()

    def _update_hint(self, fps: float = 0.0) -> None:
        """Baris petunjuk kanan mengikuti status kamera (bukan angka tetap).

        Saat kamera aktif, status kamera sudah ditampilkan pill indikator di
        kanan atas, jadi hint kanan tetap pada petunjuk non-gestur seperti
        mockup (tidak ada duplikasi "KAMERA AKTIF · FPS").
        """
        del fps
        if self.session.is_paused:
            right = "KAMERA JEDA · CTRL+ALT+G"
        else:
            right = "SEMUA AKSI ADA JALAN NON-GESTUR"
        if right != self.hint.right_text:
            self.hint.set_right(right)
            self._layout_items()

    def show_toast(self, text: str, *, detail: str = "") -> None:
        """Tampilkan toast kanan atas; hilang sendiri setelah beberapa detik."""
        self.toast.set_message(text, detail)
        self.toast.show()
        self.toast.raise_()
        self.indicator.raise_()
        self._toast_timer.start()
        self.autohide.poke()

    def cycle_chrome(self) -> ChromeMode:
        """Putar status chrome lewat hotkey ``Ctrl+Alt+C``."""
        return self.chrome.cycle()

    def _chrome_mode_changed(self, mode: ChromeMode) -> None:
        """Terapkan status chrome baru tanpa mengubah status indikator."""
        if mode is ChromeMode.ON:
            self.autohide.set_enabled(False)
            self._set_chrome_hidden(False)
            self.show_toast("Chrome tampil", detail="Ctrl+Alt+C untuk sembunyikan")
        elif mode is ChromeMode.OFF:
            self.autohide.set_enabled(False)
            self._set_chrome_hidden(True)
            self.show_toast("Chrome disembunyikan", detail="Titik 16 px di bawah layar")
        else:
            self.autohide.set_enabled(self.config.display.auto_hide_enabled)
            self._set_chrome_hidden(False)
        self.update()

    @property
    def hint_visible(self) -> bool:
        """True bila baris petunjuk tampil (chrome terlihat)."""
        return self.hint.isVisible()

    # ------------------------------------------------------------------ settings

    def apply_config(self, config: AppConfig) -> None:
        """Terapkan pengaturan baru tanpa membatalkan sesi kamera."""
        self.config = config
        self.engine.set_thresholds(config.gestures)
        self.engine.set_cursor_config(config.cursor)
        self.autohide.set_delay_s(config.display.auto_hide_s)
        self.autohide.set_enabled(config.display.auto_hide_enabled)
        self.set_mode(config.display.mode)
        if config.display.high_contrast != self._theme.high_contrast:
            self._theme = build_theme(config.display.high_contrast)
            self._apply_theme_to_children()
        self.autohide.poke()
        self.update()

    def _style_response_text(self) -> None:
        """Terapkan palet theme ke kotak jawaban agen."""
        stage = self._theme.palette.stage
        self.response_text.setStyleSheet(
            f"background: rgba({stage.red()}, {stage.green()}, {stage.blue()}, 0.45); "
            f"color: {self._theme.palette.text.name()}; border: none;"
        )

    def _apply_theme_to_children(self) -> None:
        """Sebarkan theme (misal kontras tinggi) ke semua chrome overlay."""
        self.ring.set_theme(self._theme)
        self.orb.set_theme(self._theme)
        self.card.set_theme(self._theme)
        self.response_panel.set_theme(self._theme)
        self.tree.set_theme(self._theme)
        self.indicator.set_theme(self._theme)
        self.toast.set_theme(self._theme)
        self.hint.set_theme(self._theme)
        self.hand_cursor.set_theme(self._theme)
        self._style_response_text()
        self.setStyleSheet(dialog_qss(self._theme))
        self.update()

    def set_autohide_hold(self, hold: bool) -> None:
        """Tahan chrome tetap terlihat (misal saat agen sedang BERPIKIR)."""
        self.autohide.set_hold(hold)

    def _set_chrome_hidden(self, hidden: bool) -> None:
        """Sembunyikan/tampilkan ring, orb, kartu, hint, dan toast; indikator tetap.

        Saat tersembunyi, hanya titik idle 16 px yang tampil supaya pengguna
        tahu chrome masih bisa dipanggil kembali.
        """
        if hidden == self._chrome_hidden:
            return
        self._chrome_hidden = hidden
        if hidden:
            self.toast.hide()
        targets: tuple[QWidget, ...] = (self.ring, self.orb, self.card, self.hint)
        if hidden:
            self._chrome_visible = [(widget, widget.isVisible()) for widget in targets]
            for widget in targets:
                if widget.isVisible():
                    widget.hide()
        else:
            for widget, was_visible in self._chrome_visible:
                if was_visible:
                    widget.show()
                    widget.raise_()
            self._chrome_visible = []
        self.update()
        self.indicator.raise_()

    # ------------------------------------------------------------------ mouse

    def _dot_at(self, event: QMouseEvent) -> bool:
        """True bila kursor berada di area titik idle (saat chrome tersembunyi)."""
        if not self._chrome_hidden:
            return False
        return idle_dot_hit_rect(QRectF(self.rect())).contains(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        hover = self._dot_at(event)
        if hover != self._dot_hover:
            self._dot_hover = hover
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if hover else Qt.CursorShape.ArrowCursor
            )
            self.update()
        self.autohide.poke()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dot_at(event) and event.button() == Qt.MouseButton.LeftButton:
            # Ketuk titik idle = tampilkan chrome lagi.
            self.chrome.set_mode(ChromeMode.ON)
            event.accept()
            return
        self.autohide.poke()
        super().mousePressEvent(event)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if hasattr(self, "autohide"):
            self.autohide.poke()

    def on_frame(self, frame: Frame) -> None:
        if (
            self.mode is not DisplayMode.MIRROR
            or not self.session.is_active
            or self.session.is_paused
        ):
            return
        rgb = frame.rgb
        if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype.name != "uint8":
            return
        image = QImage(
            rgb.data, frame.width, frame.height, int(rgb.strides[0]), QImage.Format.Format_RGB888
        )
        self._image = image.copy()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        if self.mode is DisplayMode.OVERLAY:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        elif self.mode is DisplayMode.MIRROR:
            painter.fillRect(self.rect(), self._theme.palette.stage)
            if not self._image.isNull():
                painter.drawImage(QRectF(self.rect()), self._image)
        elif self.mode is DisplayMode.KEY:
            color = self.config.display.key_color
            value = (
                self.config.display.custom_key_hex
                if color is KeyColor.CUSTOM
                else KEY_COLOR_HEX[color]
            )
            painter.fillRect(self.rect(), QColor(value))
        if self._chrome_hidden:
            paint_idle_dot(painter, QRectF(self.rect()), self._theme, hover=self._dot_hover)
        painter.end()

    def _position_indicator(self, fps: float = 0.0) -> None:
        del fps
        self.indicator.move(max(0, self.width() - self.indicator.width() - 18), 18)

    def _active_changed(self, active: bool) -> None:
        if not active:
            self._reset_input()
            self._image = QImage()
            self.update()
        self.indicator.move(max(0, self.width() - self.indicator.width() - 18), 18)
        # Toast status kamera, sama seperti mockup ("Mode gestur aktif").
        self.show_toast(
            "Mode gestur aktif" if active else "Mode gestur nonaktif",
            detail="Kamera menyala · video tidak disimpan"
            if active
            else "Kamera mati · aktifkan hanya bila diperlukan",
        )

    def _paused_changed(self, paused: bool) -> None:
        if paused:
            self._reset_input()
            self._image = QImage()
            self.update()

    def _reset_input(self) -> None:
        if isinstance(self._drag, Card):
            self._drag.cancel_drag()
        elif self._drag is not None:
            self._drag.end_drag()
        self._drag = None
        self._press_target = None
        self._pinch_started = None
        self.engine.reset()
        self.hand_cursor.hide()
        self.hand_cursor.set_dwell(0)

    def _target_at(self, global_pos: QPoint) -> Card | Panel | None:
        local = self.mapFromGlobal(global_pos)
        widget = self.childAt(local)
        while widget is not None and widget is not self:
            if widget in (self.tree, self.response_panel, self.card):
                if isinstance(widget, Card):
                    point = QPointF(widget.mapFromGlobal(global_pos))
                    if widget.hit_test(point) is SurfaceHit.NONE:
                        return None
                if isinstance(widget, (Card, Panel)) and widget.isVisible():
                    return widget
            widget = widget.parentWidget()
        return None

    def on_tracking(self, result: TrackingResult) -> None:
        if not self.session.is_active or self.session.is_paused:
            return
        events = self.engine.process(result)
        sample = self.engine.last_sample
        if sample is None:
            return
        pos = QPoint(sample.x, sample.y)
        if sample.visible:
            self.autohide.poke()
            self.hand_cursor.move_to(pos)
            self.hand_cursor.set_hand_visible(True)
            self.hand_cursor.set_pinch(sample.pinch, sample.pinching)
            if not self.hand_cursor.isVisible():
                self.hand_cursor.show()
            if sample.pinching and self._pinch_started is None:
                self._pinch_started = sample.timestamp_ms
                self._press_target = self._target_at(pos)
            progress = (
                (sample.timestamp_ms - self._pinch_started) / self.config.gestures.hold_ms
                if self._pinch_started is not None
                else 0
            )
            self.hand_cursor.set_dwell(progress)
        else:
            self.hand_cursor.hide()
            self.hand_cursor.set_dwell(0)
        for event in events:
            self._route(event)
            self.gesture.emit(event)
        if not sample.pinching:
            self._pinch_started = None
            self._press_target = None

    def _route(self, event: GestureEvent) -> None:
        point = QPoint(event.x, event.y)
        target = self._press_target if self._pinch_started is not None else self._target_at(point)
        if event.kind is GestureKind.DRAG:
            if event.phase is GesturePhase.BEGIN and target is not None:
                self._drag = target
                target.begin_drag(QPointF(self.mapFromGlobal(point)))
            elif event.phase is GesturePhase.UPDATE and self._drag is not None:
                self._drag.update_drag(QPointF(self.mapFromGlobal(point)))
            elif event.phase is GesturePhase.END and self._drag is not None:
                if event.cancelled and isinstance(self._drag, Card):
                    self._drag.cancel_drag()
                else:
                    self._drag.end_drag()
                self._drag = None
        elif event.kind is GestureKind.TAP and target is not None:
            local = QPointF(target.mapFromGlobal(point))
            if target.hit_test(local) is SurfaceHit.CLOSE:
                target.close_requested.emit()
            elif target is self.card:
                self.card.opened.emit()
            elif target is self.tree:
                self._tree_tap(point)
        elif (
            event.kind is GestureKind.HOLD
            and event.phase is GesturePhase.BEGIN
            and target is self.card
            and not self.tree.isVisible()
        ):
            self.toggle_tree()
        elif event.kind is GestureKind.SWIPE and event.phase is GesturePhase.ONE_SHOT:
            self._route_swipe(event)
        elif event.kind is GestureKind.FIST and event.phase is GesturePhase.ONE_SHOT:
            self._route_fist()

    def _route_swipe(self, event: GestureEvent) -> None:
        """Terjemahkan gestur SWIPE menjadi aksi tampilan sesuai arah."""
        self.autohide.poke()
        direction = event.direction
        if direction in ("kanan", "kiri"):
            # Ganti mode tampilan: kanan = berikutnya, kiri = sebelumnya.
            modes = list(DisplayMode)
            current = modes.index(self.mode)
            step = 1 if direction == "kanan" else -1
            new_mode = modes[(current + step) % len(modes)]
            self.set_mode(new_mode)
            self.show_toast(
                f"Mode: {new_mode.value.title()}",
                detail="Geser tangan terbuka untuk pindah mode",
            )
        elif direction == "atas":
            self.chrome.set_mode(ChromeMode.ON)
            self.show_toast("Chrome tampil", detail="Geser tangan ke atas")
        elif direction == "bawah":
            self.chrome.set_mode(ChromeMode.OFF)
            self.show_toast("Chrome disembunyikan", detail="Geser tangan ke bawah")

    def _route_fist(self) -> None:
        """Genggaman tangan = jeda/lanjut Mode Gestur (ganti Ctrl+Alt+G)."""
        self.autohide.poke()
        self.session.toggle()
        status = "dijeda" if self.session.is_paused else "dilanjutkan"
        self.show_toast(
            f"Mode gestur {status}",
            detail="Tegang genggam lagi untuk kembali",
        )

    def _tree_tap(self, point: QPoint) -> None:
        tree = self.tree.findChild(QTreeWidget, "memory-tree")
        if tree is None:
            return
        item = tree.itemAt(tree.viewport().mapFromGlobal(point))
        if item is not None:
            tree.setCurrentItem(item)
            if (
                item.childCount()
                or item.childIndicatorPolicy() == item.ChildIndicatorPolicy.ShowIndicator
            ):
                item.setExpanded(not item.isExpanded())

    def shutdown(self) -> None:
        """Tutup setelah pemilik menghentikan kamera."""
        self._shutdown = True
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._managed and not self._shutdown:
            event.ignore()
            QTimer.singleShot(0, self.close_requested.emit)
            return
        if self.session.is_active:
            event.ignore()
            return
        self._reset_input()
        self.hand_cursor.close()
        super().closeEvent(event)


class ControlWindow(QWidget):
    """Kontrol yang dapat difokuskan, terpisah dari overlay tembus klik."""

    def __init__(
        self,
        config: AppConfig,
        screens: list[QScreen],
        *,
        monitor: int = 0,
        config_path: Path | None = None,
    ) -> None:
        super().__init__()
        if not screens or not 0 <= monitor < len(screens):
            raise ValueError("monitor tidak tersedia")
        self._config = config
        self._config_path = config_path
        self._theme = build_theme(config.display.high_contrast)
        self.session = CameraSession(config.camera, parent=self)
        try:
            agent_settings = load_settings()
            self._settings_error = ""
        except SettingsError as exc:
            agent_settings = AgentSettings()
            self._settings_error = str(exc)
        self.agent = AgentBridge(parent=self, settings=agent_settings)
        self._settings_dialog: SettingsDialog | None = None
        self._onboarding: OnboardingDialog | None = None
        self._request_label = LABELS[agent_settings.provider]
        self._exit_pending = False
        self.overlay = OverlayWindow(config, self.session, screens[monitor])
        self.overlay._managed = True
        self.overlay.close_requested.connect(self.close)
        self.agent.status_changed.connect(self.overlay.ring.set_status)
        self.agent.status_changed.connect(self.overlay.orb.set_status)
        self.setWindowTitle("JARVIS · kontrol")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setStyleSheet(dialog_qss(self._theme))
        layout = QVBoxLayout(self)
        self.heading = QLabel("JARVIS · KONTROL LOKAL")
        self.heading.setFont(mono_font(FONT.body))
        self.heading.setStyleSheet(f"color: {self._theme.palette.teal.name()};")
        layout.addWidget(self.heading)
        self.status = QLabel("Kamera mati · aktifkan hanya bila diperlukan")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.mode = QComboBox()
        for mode in DisplayMode:
            self.mode.addItem(mode.value.upper(), mode.value)
        self.mode.setCurrentIndex(list(DisplayMode).index(config.display.mode))
        self.mode.currentIndexChanged.connect(self._mode_changed)
        row.addWidget(self.mode)
        self.monitor = QComboBox()
        for index, screen in enumerate(screens):
            self.monitor.addItem(f"{index}: {screen.name()}", screen)
        self.monitor.setCurrentIndex(monitor)
        self.monitor.currentIndexChanged.connect(self._monitor_changed)
        row.addWidget(self.monitor)
        layout.addLayout(row)
        self.camera_button = QPushButton("Nyalakan kamera")
        self.camera_button.clicked.connect(self._camera_clicked)
        layout.addWidget(self.camera_button)
        self.pause_button = QPushButton("Jeda gestur · Ctrl+Alt+G")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.session.toggle)
        layout.addWidget(self.pause_button)
        show_card = QPushButton("Tampilkan kartu")
        show_card.clicked.connect(self._show_card)
        layout.addWidget(show_card)
        show_tree = QPushButton("Buka/tutup memori")
        show_tree.clicked.connect(self.overlay.toggle_tree)
        layout.addWidget(show_tree)
        self.provider_label = QLabel()
        layout.addWidget(self.provider_label)
        self.settings_button = QPushButton("Pengaturan")
        self.settings_button.setObjectName("open-agent-settings")
        self.settings_button.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_button)
        guide_button = QPushButton("Panduan kamera & gestur")
        guide_button.setObjectName("open-onboarding")
        guide_button.clicked.connect(self._open_onboarding)
        layout.addWidget(guide_button)
        self.prompt = QLineEdit()
        self.prompt.setObjectName("agent-prompt")
        self.prompt.setAccessibleName("Permintaan agen")
        self.prompt.setPlaceholderText("Tulis permintaan untuk agen")
        self.prompt.setMaxLength(MAX_PROMPT_CHARS)
        self.prompt.returnPressed.connect(self._send_prompt)
        layout.addWidget(self.prompt)
        self.send_button = QPushButton("Kirim")
        self.send_button.clicked.connect(self._send_prompt)
        layout.addWidget(self.send_button)
        self.agent_status = QLabel()
        self.agent_status.setWordWrap(True)
        layout.addWidget(self.agent_status)
        self.answer = QPlainTextEdit()
        self.answer.setObjectName("agent-response")
        self.answer.setAccessibleName("Jawaban agen")
        self.answer.setReadOnly(True)
        self.answer.setPlaceholderText("Jawaban agen akan tampil di sini")
        self.answer.setMaximumHeight(140)
        layout.addWidget(self.answer)
        self.agent.response.connect(self._agent_response)
        self.agent.error.connect(self._agent_error)
        self.agent.busy_changed.connect(self._agent_busy)
        close_button = QPushButton("Keluar")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)
        self.session.active_changed.connect(self._camera_status)
        self.session.paused_changed.connect(self._pause_status)
        self.session.error.connect(self._error)
        self._refresh_agent_label()
        if self._settings_error:
            self.send_button.setEnabled(False)
            self.agent_status.setText(self._settings_error + " Buka pengaturan untuk memperbaiki.")
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.screenAdded.connect(self._screens_changed)
            app.screenRemoved.connect(self._screens_changed)
        self.mode.setAccessibleName("Mode tampilan")
        self.monitor.setAccessibleName("Monitor tampilan")
        enforce_min_targets(self)
        self._chrome_shortcut = QShortcut(QKeySequence("Ctrl+Alt+C"), self)
        self._chrome_shortcut.activated.connect(self.overlay.cycle_chrome)
        self._settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self._settings_shortcut.activated.connect(self._open_settings)
        self._guide_shortcut = QShortcut(QKeySequence("F1"), self)
        self._guide_shortcut.activated.connect(self._open_onboarding)
        self.overlay.show()

    def _refresh_agent_label(self) -> None:
        settings = self.agent.settings
        label = LABELS[settings.provider]
        self.provider_label.setText(f"{label} · teks dikirim ke penyedia yang dipilih")
        self.send_button.setText(f"Kirim ke {label}")
        self.agent_status.setText(f"Model: {settings.model} · tanpa audio")

    def _open_settings(self) -> None:
        if self.agent.busy:
            return
        if self._settings_dialog is not None:
            self._settings_dialog.raise_()
            return
        dialog = SettingsDialog(
            self._config,
            self.agent.settings,
            self.agent.store,
            config_path=self._config_path,
            theme=self._theme,
            parent=self,
        )
        self._settings_dialog = dialog
        dialog.saved.connect(self._settings_saved)
        dialog.agent_saved.connect(self._agent_saved)
        dialog.onboarding_requested.connect(self._open_onboarding)
        dialog.finished.connect(self._settings_closed)
        dialog._tester.busy_changed.connect(self._settings_test_busy)
        dialog.open()

    def _settings_saved(self, config: AppConfig) -> None:
        self._config = config
        self.session.set_config(config.camera)
        self._apply_theme(config.display.high_contrast)
        self.overlay.apply_config(config)
        self._sync_mode_combo()

    def _agent_saved(self, settings: AgentSettings) -> None:
        self.agent.settings = settings
        self._settings_error = ""
        self.send_button.setEnabled(True)
        self._refresh_agent_label()

    def _open_onboarding(self) -> None:
        if self._onboarding is not None:
            return
        if self.session.is_active and not self.session.stop():
            self.status.setText("Kamera belum berhenti; coba lagi.")
            return
        dialog = OnboardingDialog(
            self._config,
            config_path=self._config_path,
            theme=self._theme,
            parent=self,
        )
        self._onboarding = dialog
        dialog.completed.connect(self._onboarding_done)
        dialog.finished.connect(self._onboarding_closed)
        dialog.open()

    def _onboarding_done(self, config: AppConfig) -> None:
        self._config = config
        self.session.set_config(config.camera)
        self._apply_theme(config.display.high_contrast)
        self.overlay.apply_config(config)
        self._sync_mode_combo()
        if self._settings_dialog is not None:
            self._settings_dialog.apply_external_config(config)

    def _apply_theme(self, high_contrast: bool) -> None:
        """Ganti tema jendela kontrol bila flag kontras tinggi berubah."""
        if high_contrast == self._theme.high_contrast:
            return
        self._theme = build_theme(high_contrast)
        self.setStyleSheet(dialog_qss(self._theme))
        self.heading.setStyleSheet(f"color: {self._theme.palette.teal.name()};")
        self.update()

    def _onboarding_closed(self, result: int) -> None:
        del result
        dialog = self._onboarding
        self._onboarding = None
        if dialog is not None:
            dialog.deleteLater()

    def _sync_mode_combo(self) -> None:
        index = self.mode.findData(self._config.display.mode.value)
        if index >= 0:
            self.mode.blockSignals(True)
            self.mode.setCurrentIndex(index)
            self.mode.blockSignals(False)

    def _settings_closed(self, result: int) -> None:
        del result
        dialog = self._settings_dialog
        self._settings_dialog = None
        if dialog is not None:
            dialog.deleteLater()

    def _settings_test_busy(self, busy: bool) -> None:
        if not busy and self._exit_pending:
            QTimer.singleShot(0, self.close)

    def _send_prompt(self) -> None:
        if self._settings_error:
            self.agent_status.setText("Perbaiki pengaturan agen sebelum mengirim.")
            return
        self._request_label = LABELS[self.agent.settings.provider]
        if self.agent.submit(self.prompt.text()):
            self.prompt.clear()
            self.agent_status.setText(f"Menghubungi {self._request_label} · teks dikirim")

    def _agent_response(self, text: str) -> None:
        self.answer.setPlainText(text)
        self.overlay.response_panel.set_title(f"Jawaban {self._request_label}")
        self.overlay.show_response(text)
        self.agent_status.setText(f"Jawaban {self._request_label} diterima · teks saja")

    def _agent_error(self, message: str) -> None:
        self.agent_status.setText(message)

    def _agent_busy(self, busy: bool) -> None:
        self.send_button.setEnabled(not busy and not self._settings_error)
        self.settings_button.setEnabled(not busy)
        self.prompt.setEnabled(not busy)
        self.overlay.set_autohide_hold(busy)
        if not busy and self._exit_pending:
            QTimer.singleShot(0, self.close)

    def _mode_changed(self, index: int) -> None:
        self.overlay.set_mode(DisplayMode(self.mode.itemData(index)))

    def _monitor_changed(self, index: int) -> None:
        screen = self.monitor.itemData(index)
        if isinstance(screen, QScreen):
            self.overlay.set_screen(screen)

    def _screens_changed(self, changed: QScreen) -> None:
        del changed
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            return
        screens = app.screens()
        current = self.overlay.screen_target
        self.monitor.blockSignals(True)
        self.monitor.clear()
        for index, screen in enumerate(screens):
            self.monitor.addItem(f"{index}: {screen.name()}", screen)
        if screens:
            index = screens.index(current) if current in screens else 0
            self.monitor.setCurrentIndex(index)
            self.overlay.set_screen(screens[index])
        self.monitor.blockSignals(False)

    def _show_card(self) -> None:
        self.overlay.autohide.poke()
        self.overlay.card.show()
        self.overlay.card.raise_()
        if self.overlay.tree.isVisible():
            self.overlay.tree.raise_()
        self.overlay.indicator.raise_()

    def _camera_clicked(self) -> None:
        if self.session.is_active:
            if not self.session.stop():
                self.status.setText("Kamera belum berhenti; coba lagi.")
        else:
            self.camera_button.setEnabled(False)
            if not self.session.start():
                self.camera_button.setEnabled(True)
                self.status.setText("Kamera belum siap; coba lagi.")

    def _camera_status(self, active: bool) -> None:
        self.camera_button.setEnabled(True)
        self.camera_button.setText("Matikan kamera" if active else "Nyalakan kamera")
        self.pause_button.setEnabled(active)
        error = self.session.controller.last_error
        self.status.setText(
            "Kamera aktif · pemrosesan lokal"
            if active
            else f"Kamera: {error}"
            if error
            else "Kamera mati"
        )

    def _pause_status(self, paused: bool) -> None:
        self.pause_button.setText(
            "Lanjutkan gestur · Ctrl+Alt+G" if paused else "Jeda gestur · Ctrl+Alt+G"
        )

    def _error(self, message: str) -> None:
        self.status.setText(f"Kamera: {message}")
        self.camera_button.setEnabled(True)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self.session.stop():
            self.status.setText("Kamera belum berhenti; coba keluar lagi.")
            event.ignore()
            return
        if self._onboarding is not None:
            self._onboarding.reject()
            if self._onboarding is not None:
                self.status.setText("Panduan belum menghentikan kamera; coba keluar lagi.")
                event.ignore()
                return
        if self._settings_dialog is not None and self._settings_dialog._tester.busy:
            self._exit_pending = True
            self.status.setText("Tunggu uji koneksi selesai sebelum keluar.")
            event.ignore()
            return
        if self.agent.busy:
            self._exit_pending = True
            self.agent_status.setText("Menunggu permintaan agen selesai sebelum keluar.")
            event.ignore()
            return
        self.overlay.shutdown()
        event.accept()
