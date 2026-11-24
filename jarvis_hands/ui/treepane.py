"""Panel memori baca-saja: pohon direktori dan pratinjau teks terbatas."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from jarvis_hands.memory.tree import MemoryNode, MemoryPathError, MemoryTree, NodeKind, format_size
from jarvis_hands.ui.accessibility import enforce_min_targets
from jarvis_hands.ui.card import Panel
from jarvis_hands.ui.tokens import (
    FONT,
    METRICS,
    Theme,
    build_theme,
    mono_font,
    rgba_css,
    sans_font,
    with_alpha,
)


def format_short_size(size: int | None) -> str:
    """Ukuran ringkas gaya mockup (``4 KB`` bukan ``4,0 KB``)."""
    return format_size(size or 0).replace(",0 ", " ")


class TreePane(Panel):
    """Pohon memori malas dan pratinjau teks. Tanpa akar, tampilkan contoh lokal.

    Akar riil hanya dibuka bila diberikan secara eksplisit. Semua pembacaan
    dilakukan oleh MemoryTree; widget tidak pernah memuat gambar atau kode.
    """

    selected = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        root: Path | None = None,
        *,
        theme: Theme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._tree_theme = theme or build_theme()
        super().__init__(
            "MEMORI",
            chips=("AKAR AMAN",),
            theme=self._tree_theme,
            title_size=FONT.label,
            parent=parent,
        )
        # Mockup menaruh breadcrumb di header, di sebelah judul panel.
        self._path = QLabel("memori")
        self._path.setObjectName("memory-path")
        self._path.setFont(mono_font(FONT.label, spacing=2.0))
        self._path.setWordWrap(False)
        header = self._header_row()
        header.insertSpacing(1, 18)
        header.insertWidget(2, self._path)
        self.setAccessibleName("Pohon memori")
        self._memory = MemoryTree(root) if root is not None else None
        self._nodes: dict[int, MemoryNode] = {}
        self.setMinimumSize(620, 350)
        row = QHBoxLayout()
        row.setSpacing(18)
        self._list = QTreeWidget()
        self._list.setObjectName("memory-tree")
        self._list.setHeaderHidden(True)
        self._list.setIndentation(22)
        self._list.setMinimumWidth(240)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setUniformRowHeights(True)
        self._list.setFont(sans_font(FONT.small))
        self._list.itemExpanded.connect(self._expanded)
        self._list.itemSelectionChanged.connect(self._select)
        row.addWidget(self._list, 3)
        right = QVBoxLayout()
        right.setSpacing(8)
        self._info = QLabel("Pilih berkas")
        self._info.setObjectName("memory-info")
        self._info.setFont(sans_font(FONT.title, bold=True))
        right.addWidget(self._info)
        self._meta = QLabel("")
        self._meta.setObjectName("memory-meta")
        self._meta.setFont(mono_font(FONT.label))
        right.addWidget(self._meta)
        self._explain = QLabel(
            "Isi berkas dibaca sebagai teks biasa. Tidak ada eval, exec, "
            "pickle, atau eksekusi apa pun dari isi memori."
        )
        self._explain.setObjectName("memory-explain")
        self._explain.setFont(sans_font(FONT.small))
        self._explain.setWordWrap(True)
        right.addWidget(self._explain)
        right.addSpacing(6)
        self._preview = QPlainTextEdit()
        self._preview.setObjectName("memory-preview")
        self._preview.setAccessibleName("Pratinjau isi memori")
        self._preview.setReadOnly(True)
        self._preview.setFont(mono_font(FONT.label))
        right.addWidget(self._preview, 1)
        warning = QLabel("PATH TRAVERSAL DITOLAK · SYMLINK LUAR ROOT DITOLAK")
        warning.setObjectName("memory-safety")
        warning.setWordWrap(True)
        warning.setFont(mono_font(FONT.label))
        self._safety = warning
        right.addWidget(warning)
        row.addLayout(right, 2)
        self.body().addLayout(row, 1)
        self._footnote = QLabel(
            f"BARIS {METRICS.tree_row} PX · FOLDER TERBUKA DI TEMPAT · SELEKSI TEBAL"
        )
        self._footnote.setObjectName("memory-footnote")
        self._footnote.setFont(mono_font(FONT.label, spacing=1.5))
        self.body().addWidget(self._footnote)
        self._list_stylesheet()
        self._populate()
        enforce_min_targets(self)

    @property
    def memory(self) -> MemoryTree | None:
        """Backend riil, atau None jika memakai data demonstrasi."""
        return self._memory

    def _list_stylesheet(self) -> None:
        """Terapkan palet theme ke pohon, pratinjau, dan label sisi kanan.

        Blok seleksi dilukis dari palette (bukan ``QSS::item:selected``): Qt
        mengisi seluruh baris termasuk area indentasi, sesuai baris 46-56 px di
        mockup. Nuansa amber dipakai untuk baris keamanan, seperti mockup.
        """
        pal = self._tree_theme.palette
        self._list.setStyleSheet(
            f"QTreeWidget {{ background: transparent; color: {pal.text.name()}; border: none; }}"
            f"QTreeWidget::item {{ min-height: {METRICS.tree_row}px; padding-left: 6px; }}"
            f"QTreeWidget::item:hover {{ background: {rgba_css(pal.teal, 0.10)}; }}"
        )
        selection = self._list.palette()
        selection.setColor(QPalette.ColorRole.Highlight, with_alpha(pal.teal, 0.22))
        selection.setColor(QPalette.ColorRole.HighlightedText, pal.text)
        self._list.setPalette(selection)
        self._path.setStyleSheet(f"color: {rgba_css(pal.muted, 0.85)}; background: transparent;")
        self._info.setStyleSheet(f"color: {pal.accent.name()}; background: transparent;")
        self._meta.setStyleSheet(f"color: {pal.muted.name()}; background: transparent;")
        self._explain.setStyleSheet(f"color: {rgba_css(pal.muted, 0.90)}; background: transparent;")
        self._footnote.setStyleSheet(f"color: {rgba_css(pal.muted, 0.75)};")
        self._preview.setStyleSheet(
            f"background: {rgba_css(pal.stage, 0.55)}; "
            f"color: {pal.muted.name()}; "
            f"border: 1px solid {rgba_css(pal.border, 0.35)}; "
            f"border-radius: {self._tree_theme.style.control_radius:.0f}px; padding: 8px;"
        )
        self._safety.setStyleSheet(
            f"color: {pal.warning.name()}; "
            f"background: {rgba_css(pal.warning, 0.10)}; "
            f"border: 1px solid {rgba_css(pal.warning, 0.45)}; "
            f"border-radius: {self._tree_theme.style.control_radius:.0f}px; padding: 10px;"
        )

    def set_theme(self, theme: Theme) -> None:
        """Ganti tema (misal kontras tinggi) tanpa membangun ulang pohon."""
        self._tree_theme = theme
        super().set_theme(theme)
        self._list_stylesheet()

    def _add(self, node: MemoryNode, parent: QTreeWidgetItem | None = None) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.name])
        item.setToolTip(0, node.rel_path or node.name)
        item.setIcon(0, self._node_icon(node.is_folder))
        self._nodes[id(item)] = node
        if parent is None:
            self._list.addTopLevelItem(item)
        else:
            parent.addChild(item)
        if node.is_folder:
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
            for child in node.children:
                self._add(child, item)
        return item

    def _node_icon(self, folder: bool) -> QIcon:
        pixmap = QPixmap(22, 22)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._tree_theme.palette.teal, 1.3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if folder:
            path = QPainterPath()
            path.moveTo(2, 7)
            path.lineTo(2, 4)
            path.lineTo(8, 4)
            path.lineTo(10, 6)
            path.lineTo(20, 6)
            path.lineTo(20, 18)
            path.lineTo(2, 18)
            path.closeSubpath()
            painter.drawPath(path)
        else:
            painter.drawRoundedRect(QRectF(5, 3, 12, 16), 2, 2)
            painter.drawLine(8, 9, 14, 9)
            painter.drawLine(8, 13, 14, 13)
        painter.end()
        return QIcon(pixmap)

    def _populate(self) -> None:
        if self._memory is not None:
            node = self._memory.root_node()
        else:
            node = MemoryNode("memori (contoh)", "", NodeKind.ROOT, children_loaded=True)
            project = node.add_child(
                MemoryNode("proyek", "proyek", NodeKind.FOLDER, children_loaded=True)
            )
            folder = project.add_child(
                MemoryNode("jarvis", "proyek/jarvis", NodeKind.FOLDER, children_loaded=True)
            )
            folder.add_child(
                MemoryNode(
                    "catatan.md",
                    "proyek/jarvis/catatan.md",
                    NodeKind.FILE,
                    size=4096,
                    preview=(
                        "# Catatan JARVIS\n\nContoh pratinjau lokal.\n"
                        "Tidak ada folder pengguna yang dibuka."
                    ),
                )
            )
        root = self._add(node)
        root.setExpanded(True)
        if self._memory is None:
            project_item = root.child(0)
            if project_item is not None:
                project_item.setExpanded(True)
                folder_item = project_item.child(0)
                if folder_item is not None:
                    folder_item.setExpanded(True)
                    sample_item = folder_item.child(0)
                    if sample_item is not None:
                        self._list.setCurrentItem(sample_item)

    def _expanded(self, item: QTreeWidgetItem) -> None:
        node = self._nodes.get(id(item))
        if node is None or node.children_loaded or self._memory is None:
            return
        try:
            node.children = self._memory.children_of(node)
            node.children_loaded = True
            for child in node.children:
                self._add(child, item)
            if not node.children:
                item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
        except MemoryPathError as exc:
            self._show_error(exc)

    def _select(self) -> None:
        items = self._list.selectedItems()
        if not items:
            return
        node = self._nodes.get(id(items[0]))
        if node is None:
            return
        root_name = self._memory.name if self._memory is not None else "memori"
        self._path.setText(" / ".join((root_name, *node.path_parts)))
        self.selected.emit(node.rel_path)
        self._preview.clear()
        if node.is_folder:
            self._info.setText(f"Folder · {node.name}")
            self._meta.setText("BUKA BARIS UNTUK MELIHAT ISI FOLDER")
            return
        self._info.setText(node.name)
        self._meta.setText(f"{format_short_size(node.size)} · LOKAL · DATA TIDAK TERPERCAYA")
        try:
            text = self._memory.read_preview(node.rel_path) if self._memory else node.preview or ""
            self._preview.setPlainText(text)
        except MemoryPathError as exc:
            self._show_error(exc)

    def _show_error(self, exc: MemoryPathError) -> None:
        self._preview.setPlainText(exc.message)
        self.error.emit(exc.message)
