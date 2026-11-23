"""Tambahkan penanda PEP 561 ``py.typed`` ke instalasi PySide6.

Wheel PySide6 6.11.3 membawa berkas ``.pyi`` lengkap tetapi lupa menyertakan
``py.typed``, sehingga mypy memperlakukan seluruh PySide6 sebagai ``Any``.
Skrip ini hanya untuk lingkungan pengembang/CI; ia tidak mengubah runtime dan
tidak dipaketkan ke aplikasi.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def ensure_marker() -> Path:
    """Pastikan ``PySide6/py.typed`` ada; kembalikan lokasinya."""
    spec = importlib.util.find_spec("PySide6")
    if spec is None or spec.submodule_search_locations is None:
        raise RuntimeError("PySide6 belum terpasang")
    package = Path(next(iter(spec.submodule_search_locations)))
    marker = package / "py.typed"
    if not marker.exists():
        marker.write_text("", encoding="utf-8")
    return marker


def main() -> int:
    """CLI: ``python tools/pyside6_typing.py``."""
    try:
        print(ensure_marker())
    except (RuntimeError, OSError) as exc:
        print(f"pyside6-typing: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
