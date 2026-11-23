"""Penjelajahan folder memori yang aman (murni Python, tanpa Qt).

``MemoryTree`` membaca satu folder akar (``AppConfig.memory_root``) dan tidak
pernah keluar darinya. Aturan yang dipaksa:

* path relatif saja: path absolut, huruf drive, UNC, dan segmen ``..`` ditolak;
* setiap komponen path diperiksa ``is_symlink()`` sebelum dibuka, lalu hasil
  ``resolve()`` harus tetap di dalam akar (menutup junction/disk terhubung);
* symlink tidak pernah diikuti, termasuk saat mendaftar isi folder;
* berkas hanya dibaca sebagai teks UTF-8, dibatasi ``max_file_bytes``, dan
  pratinjau dipotong ``preview_bytes``; berkas biner ditolak;
* jumlah entri per folder dibatasi ``max_entries``; nama berawalan ``.`` dilewati.

Tidak ada ``eval``/``exec``/``pickle``: isi berkas hanya ditampilkan.
"""

from __future__ import annotations

import codecs
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum, unique
from pathlib import Path, PureWindowsPath

__all__ = [
    "MAX_ENTRIES",
    "MAX_FILE_BYTES",
    "PREVIEW_BYTES",
    "MemoryEntry",
    "MemoryNode",
    "MemoryPathError",
    "MemoryPathReason",
    "MemoryTree",
    "NodeKind",
]

PREVIEW_BYTES = 4096
MAX_FILE_BYTES = 64 * 1024
MAX_ENTRIES = 500


@unique
class NodeKind(StrEnum):
    """Jenis simpul pohon memori."""

    ROOT = "root"
    FOLDER = "folder"
    FILE = "file"


@unique
class MemoryPathReason(StrEnum):
    """Alasan permintaan path ditolak/gagal."""

    ROOT_INVALID = "root_invalid"
    EMPTY = "empty"
    ABSOLUTE = "absolute"
    TRAVERSAL = "traversal"
    INVALID = "invalid"
    SYMLINK = "symlink"
    OUTSIDE_ROOT = "outside_root"
    NOT_FOUND = "not_found"
    NOT_A_FOLDER = "not_a_folder"
    NOT_A_FILE = "not_a_file"
    TOO_LARGE = "too_large"
    BINARY = "binary"
    LIMIT = "limit"
    IO_ERROR = "io_error"


_MESSAGES: dict[MemoryPathReason, str] = {
    MemoryPathReason.ROOT_INVALID: "Akar memori bukan folder yang bisa dibaca",
    MemoryPathReason.EMPTY: "Path kosong",
    MemoryPathReason.ABSOLUTE: "Path absolut ditolak",
    MemoryPathReason.TRAVERSAL: "Path traversal ditolak",
    MemoryPathReason.INVALID: "Path tidak valid",
    MemoryPathReason.SYMLINK: "Symlink tidak dibaca",
    MemoryPathReason.OUTSIDE_ROOT: "Di luar akar memori",
    MemoryPathReason.NOT_FOUND: "Tidak ditemukan",
    MemoryPathReason.NOT_A_FOLDER: "Bukan folder",
    MemoryPathReason.NOT_A_FILE: "Bukan berkas",
    MemoryPathReason.TOO_LARGE: "Berkas terlalu besar",
    MemoryPathReason.BINARY: "Berkas biner tidak ditampilkan",
    MemoryPathReason.LIMIT: "Terlalu banyak entri",
    MemoryPathReason.IO_ERROR: "Tidak bisa dibaca",
}


class MemoryPathError(ValueError):
    """Permintaan path memori ditolak; ``reason`` menjelaskan mengapa."""

    def __init__(self, reason: MemoryPathReason, rel_path: str, detail: str = "") -> None:
        self.reason = MemoryPathReason(reason)
        self.rel_path = rel_path
        self.detail = detail
        super().__init__(self.message)

    @property
    def message(self) -> str:
        """Pesan singkat untuk ditampilkan di panel peringatan."""
        text = _MESSAGES[self.reason]
        if self.detail:
            return f"{text}: {self.detail}"
        return text


@dataclass(frozen=True)
class MemoryEntry:
    """Satu entri direktori (folder atau berkas) dengan path relatif posix."""

    name: str
    rel_path: str
    kind: NodeKind
    size: int = 0
    modified: float = 0.0

    @property
    def is_folder(self) -> bool:
        """True bila entri adalah folder."""
        return self.kind is NodeKind.FOLDER


@dataclass
class MemoryNode:
    """Simpul pohon untuk TreePane; ``children`` terisi malas."""

    name: str
    rel_path: str
    kind: NodeKind
    size: int = 0
    modified: float = 0.0
    depth: int = 0
    expanded: bool = False
    children_loaded: bool = False
    children: list[MemoryNode] = field(default_factory=list)
    #: Pratinjau teks bila sudah dibaca (atau disediakan sintetis).
    preview: str | None = None

    @property
    def is_folder(self) -> bool:
        """True bila simpul adalah folder."""
        return self.kind in (NodeKind.FOLDER, NodeKind.ROOT)

    @property
    def path_parts(self) -> tuple[str, ...]:
        """Komponen path relatif (kosong untuk akar)."""
        return tuple(part for part in self.rel_path.split("/") if part)

    def add_child(self, child: MemoryNode) -> MemoryNode:
        """Tambah anak dan kembalikannya."""
        child.depth = self.depth + 1
        self.children.append(child)
        return child


class MemoryTree:
    """Akses baca-saja terbatas ke satu folder akar."""

    def __init__(
        self,
        root: Path,
        *,
        preview_bytes: int = PREVIEW_BYTES,
        max_file_bytes: int = MAX_FILE_BYTES,
        max_entries: int = MAX_ENTRIES,
    ) -> None:
        root_path = Path(root)
        if not root_path.is_dir():
            raise MemoryPathError(MemoryPathReason.ROOT_INVALID, "", str(root_path))
        try:
            self._root = root_path.resolve(strict=True)
        except OSError as exc:
            raise MemoryPathError(MemoryPathReason.ROOT_INVALID, "", str(exc)) from exc
        if not self._root.is_dir():
            raise MemoryPathError(MemoryPathReason.ROOT_INVALID, "", str(self._root))
        self._preview_bytes = max(1, int(preview_bytes))
        self._max_file_bytes = max(1, int(max_file_bytes))
        self._max_entries = max(1, int(max_entries))

    @property
    def root(self) -> Path:
        """Folder akar yang sudah di-resolve."""
        return self._root

    @property
    def name(self) -> str:
        """Nama akar untuk badge (mis. ``memori``)."""
        return self._root.name or str(self._root)

    @property
    def limits(self) -> tuple[int, int, int]:
        """(preview_bytes, max_file_bytes, max_entries)."""
        return self._preview_bytes, self._max_file_bytes, self._max_entries

    # -------------------------------------------------------------- validasi

    def validate(self, rel: str) -> str:
        """Normalisasi path relatif; return path posix (``""`` untuk akar).

        Melempar :class:`MemoryPathError` bila path absolut, mengandung ``..``,
        huruf drive/ADS, atau karakter NUL.
        """
        text = str(rel).strip().replace("\\", "/")
        if "\x00" in text:
            raise MemoryPathError(MemoryPathReason.INVALID, "", "karakter NUL")
        if text in {"", "."}:
            return ""
        if text.startswith("/"):
            raise MemoryPathError(MemoryPathReason.ABSOLUTE, text)
        if PureWindowsPath(text).is_absolute() or PureWindowsPath(text).drive:
            raise MemoryPathError(MemoryPathReason.ABSOLUTE, text)
        parts: list[str] = []
        for part in PureWindowsPath(text).parts or text.split("/"):
            if part in {"", ".", "/"}:
                continue
            if part == "..":
                raise MemoryPathError(MemoryPathReason.TRAVERSAL, text)
            if ":" in part or "\x00" in part:
                raise MemoryPathError(MemoryPathReason.INVALID, text, part)
            parts.append(part)
        if not parts:
            return ""
        return "/".join(parts)

    def resolve(self, rel: str) -> Path:
        """Path absolut yang aman untuk ``rel``; tidak pernah keluar akar."""
        normalized = self.validate(rel)
        if not normalized:
            return self._root
        current = self._root
        for part in normalized.split("/"):
            current = current / part
            if current.is_symlink():
                raise MemoryPathError(MemoryPathReason.SYMLINK, normalized, part)
            try:
                attrs = getattr(current.lstat(), "st_file_attributes", 0)
                if attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                    raise MemoryPathError(MemoryPathReason.SYMLINK, normalized, part)
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise MemoryPathError(MemoryPathReason.IO_ERROR, normalized, str(exc)) from exc
        try:
            resolved = current.resolve(strict=False)
        except OSError as exc:
            raise MemoryPathError(MemoryPathReason.IO_ERROR, normalized, str(exc)) from exc
        try:
            resolved.relative_to(self._root)
        except ValueError as exc:
            raise MemoryPathError(MemoryPathReason.OUTSIDE_ROOT, normalized) from exc
        return resolved

    @contextmanager
    def _safe_fd(self, normalized: str, *, directory: bool) -> Iterator[int]:
        """Buka relatif ke direktori root dengan O_NOFOLLOW pada setiap komponen (POSIX)."""
        descriptors: list[int] = []
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
        try:
            descriptors.append(os.open(self._root, flags))
            parts = normalized.split("/") if normalized else []
            for index, part in enumerate(parts):
                is_directory = index < len(parts) - 1 or directory
                child_flags = os.O_RDONLY | os.O_NOFOLLOW
                if is_directory:
                    child_flags |= os.O_DIRECTORY
                else:
                    child_flags |= os.O_NONBLOCK
                descriptors.append(os.open(part, child_flags, dir_fd=descriptors[-1]))
            yield descriptors[-1]
        except OSError as exc:
            raise MemoryPathError(MemoryPathReason.IO_ERROR, normalized, str(exc)) from exc
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    # ----------------------------------------------------------------- baca

    def exists(self, rel: str) -> bool:
        """True bila path ada (tanpa mengikuti symlink)."""
        return self.resolve(rel).exists()

    def entry(self, rel: str) -> MemoryEntry:
        """Stat satu entri; error bila tidak ada."""
        normalized = self.validate(rel)
        if not normalized:
            return MemoryEntry(self.name, "", NodeKind.ROOT)
        target = self.resolve(normalized)
        try:
            stat = target.stat()
        except FileNotFoundError as exc:
            raise MemoryPathError(MemoryPathReason.NOT_FOUND, normalized) from exc
        except OSError as exc:
            raise MemoryPathError(MemoryPathReason.IO_ERROR, normalized, str(exc)) from exc
        kind = NodeKind.FOLDER if target.is_dir() else NodeKind.FILE
        return MemoryEntry(
            target.name,
            normalized,
            kind,
            0 if kind is NodeKind.FOLDER else stat.st_size,
            stat.st_mtime,
        )

    def list_dir(self, rel: str = "") -> list[MemoryEntry]:
        """Daftar isi folder: folder dulu, lalu berkas, nama tidak peka huruf."""
        normalized = self.validate(rel)
        target = self.resolve(normalized)
        if not target.exists():
            raise MemoryPathError(MemoryPathReason.NOT_FOUND, normalized)
        if not target.is_dir():
            raise MemoryPathError(MemoryPathReason.NOT_A_FOLDER, normalized)
        if os.name == "posix":
            with self._safe_fd(normalized, directory=True) as fd:
                return self._scan_dir(fd, normalized)
        return self._scan_dir(target, normalized)

    def _scan_dir(self, target: Path | int, normalized: str) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        try:
            scanner = os.scandir(target)
        except OSError as exc:
            raise MemoryPathError(MemoryPathReason.IO_ERROR, normalized, str(exc)) from exc
        with scanner:
            for item in scanner:
                if item.name.startswith("."):
                    continue
                if item.is_symlink():
                    continue
                try:
                    is_dir = item.is_dir(follow_symlinks=False)
                    info = item.stat(follow_symlinks=False)
                    if getattr(info, "st_file_attributes", 0) & getattr(
                        stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
                    ):
                        continue
                    if not is_dir and not stat.S_ISREG(info.st_mode):
                        continue
                except OSError:
                    continue
                child_rel = f"{normalized}/{item.name}" if normalized else item.name
                entries.append(
                    MemoryEntry(
                        item.name,
                        child_rel,
                        NodeKind.FOLDER if is_dir else NodeKind.FILE,
                        0 if is_dir else info.st_size,
                        info.st_mtime,
                    )
                )
                if len(entries) > self._max_entries:
                    raise MemoryPathError(
                        MemoryPathReason.LIMIT, normalized, f">{self._max_entries} entri"
                    )
        entries.sort(key=lambda e: (not e.is_folder, e.name.casefold()))
        return entries

    def children_of(self, node: MemoryNode) -> list[MemoryNode]:
        """Anak ``node`` sebagai MemoryNode (malas; folder saja)."""
        if not node.is_folder:
            return []
        return [
            MemoryNode(
                entry.name,
                entry.rel_path,
                entry.kind,
                entry.size,
                entry.modified,
                depth=node.depth + 1,
                children_loaded=entry.is_folder is False,
            )
            for entry in self.list_dir(node.rel_path)
        ]

    def read_preview(self, rel: str) -> str:
        """Pratinjau teks UTF-8 (dipotong ``preview_bytes``); biner ditolak."""
        normalized = self.validate(rel)
        target = self.resolve(normalized)
        if not target.exists():
            raise MemoryPathError(MemoryPathReason.NOT_FOUND, normalized)
        if not target.is_file():
            raise MemoryPathError(MemoryPathReason.NOT_A_FILE, normalized)
        try:
            if os.name == "posix":
                with self._safe_fd(normalized, directory=False) as fd:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode):
                        raise MemoryPathError(MemoryPathReason.NOT_A_FILE, normalized)
                    size = info.st_size
                    if size > self._max_file_bytes:
                        raise MemoryPathError(
                            MemoryPathReason.TOO_LARGE, normalized, f"{size} byte"
                        )
                    data = os.read(fd, self._preview_bytes)
            else:
                size = target.stat().st_size
                if size > self._max_file_bytes:
                    raise MemoryPathError(MemoryPathReason.TOO_LARGE, normalized, f"{size} byte")
                with open(target, "rb") as handle:
                    data = handle.read(self._preview_bytes)
        except OSError as exc:
            raise MemoryPathError(MemoryPathReason.IO_ERROR, normalized, str(exc)) from exc
        if b"\x00" in data:
            raise MemoryPathError(MemoryPathReason.BINARY, normalized)
        try:
            decoder = codecs.getincrementaldecoder("utf-8")()
            text = decoder.decode(data, final=len(data) >= size)
        except UnicodeDecodeError as exc:
            raise MemoryPathError(MemoryPathReason.BINARY, normalized) from exc
        if len(data) == self._preview_bytes and size > self._preview_bytes:
            text = text.rstrip("\n") + "\n…"
        return text

    def root_node(self) -> MemoryNode:
        """Simpul akar (belum dimuat)."""
        return MemoryNode(self.name, "", NodeKind.ROOT)

    def walk(self, rel: str = "", *, max_depth: int = 3) -> Iterator[MemoryEntry]:
        """Iterasi entri sampai ``max_depth`` (untuk tes/diagnostik)."""
        if max_depth < 0:
            return
        for entry in self.list_dir(rel):
            yield entry
            if entry.is_folder and max_depth > 0:
                yield from self.walk(entry.rel_path, max_depth=max_depth - 1)


def format_size(size: int) -> str:
    """Ukuran berkas ramah tampilan (``4,0 KB``)."""
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024.0 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024.0
    return f"{value:.1f} GB"
