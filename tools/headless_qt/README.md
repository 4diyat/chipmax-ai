# Stub Qt headless (Linux)

Direktori ini hanya untuk **lingkungan uji** yang tidak memiliki pustaka sistem
Qt: `libGL.so.1`, `libEGL.so.1`, `libxkbcommon.so.0`, dan `libdbus-1.so.3`.
Contohnya container Debian minimal tanpa `libgl1`.

Isinya:

- `stub_gl.c`, `stub_xkb.c`, `stub_dbus.c` — fungsi kosong yang mengembalikan
  `0`/`NULL`, bukan implementasi OpenGL/EGL/xkb/D-Bus.
- `xkb.map`, `dbus.map` — version script agar simbol versi (`V_0.5.0`,
  `LIBDBUS_1_3`) cocok dengan yang diminta Qt.
- `build.py` — mengompilasi stub ke `.qt-stubs/` (diabaikan Git).

`jarvis_hands/tests/conftest.py` memanggil `build_stubs()` hanya jika
`ctypes.CDLL("libGL.so.1")` gagal, lalu memuat keempat stub dengan `RTLD_GLOBAL`
sebelum PySide6 diimpor. Di Linux desktop normal, Windows, dan macOS, jalur ini
tidak aktif.

Jangan memaketkan direktori ini ke dalam aplikasi. Target rilis tetap
Windows 10/11 dengan PySide6 dan driver grafis asli.
