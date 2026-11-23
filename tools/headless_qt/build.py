"""Stub Qt untuk Linux headless tanpa libGL.

Hanya dipakai di lingkungan uji/CI yang tidak punya ``libGL.so.1``,
``libEGL.so.1``, ``libxkbcommon.so.0``, dan ``libdbus-1.so.3`` (misalnya
container minimal). Implementasi ini **bukan** OpenGL/EGL/xkb/D-Bus: setiap
fungsi mengembalikan 0/NULL. Qt platform ``offscreen`` tidak memanggil jalur
rendering tersebut, jadi cukup untuk menjalankan pytest-qt.

Jangan pernah memaketkan direktori ini ke dalam aplikasi.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_OUT = ROOT / ".qt-stubs"

TARGETS: tuple[tuple[str, str, str | None], ...] = (
    ("libGL.so.1", "stub_gl.c", None),
    ("libEGL.so.1", "stub_gl.c", None),
    ("libxkbcommon.so.0", "stub_xkb.c", "xkb.map"),
    ("libdbus-1.so.3", "stub_dbus.c", "dbus.map"),
)


def build_stubs(out_dir: Path = DEFAULT_OUT) -> Path:
    """Kompilasi stub bila belum ada; kembalikan direktori hasil."""
    gcc = shutil.which("gcc")
    if gcc is None:
        raise RuntimeError("gcc tidak ditemukan; tidak bisa membangun stub Qt headless")
    out_dir.mkdir(parents=True, exist_ok=True)
    for soname, source, version_script in TARGETS:
        target = out_dir / soname
        if target.exists():
            continue
        command: list[str] = [
            gcc,
            "-shared",
            "-fPIC",
            "-o",
            str(target),
            str(HERE / source),
            f"-Wl,-soname,{soname}",
        ]
        if version_script is not None:
            command.append(f"-Wl,--version-script={HERE / version_script}")
        # Alat pengembang; argumen dibangun dari path internal.
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"gagal mengompilasi {soname}: {result.stderr.strip()}")
    return out_dir


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``python tools/headless_qt/build.py [--out DIR]``."""
    args = list(sys.argv[1:] if argv is None else argv)
    out = DEFAULT_OUT
    if "--out" in args:
        index = args.index("--out")
        if index + 1 >= len(args):
            print("--out butuh direktori", file=sys.stderr)
            return 2
        out = Path(args[index + 1]).resolve()
    try:
        path = build_stubs(out)
    except RuntimeError as exc:
        print(f"headless-qt: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
