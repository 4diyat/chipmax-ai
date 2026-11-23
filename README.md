# JARVIS Ring & Hands

Antarmuka kaca yang dikendalikan tangan kosong lewat webcam. Cincin adalah wajah
JARVIS; gestur adalah jalur utama, mouse dan keyboard hanya cadangan.

> **Status: Fase 0 selesai.** Scaffold, design token Glass Stage, katalog komponen,
> dan CI (ruff, mypy, pytest) sudah jalan. RingWidget, kamera, gestur, overlay, dan
> agen menyusul per fase.

## Prinsip produk

1. **Tidak menutupi layar.** Mode utama overlay transparan, tembus klik, tidak
   merebut fokus keyboard. Layar penuh hanya opsional.
2. **Gestur dulu.** Semua interaksi bisa dengan tangan; mouse/keyboard cadangan.
3. **Privasi.** Kamera aktif hanya saat Mode Gestur menyala. Video diproses lokal,
   tidak pernah disimpan atau dikirim. Indikator kamera selalu terlihat.
4. **Satu proses, tanpa port jaringan.** Tidak ada server lokal.
5. **Satu bahasa desain.** Glass Stage, token di `jarvis_hands/ui/tokens.py`.

## Struktur

```
jarvis_hands/
  app.py                  # entry, CLI, wiring QApplication
  core/
    state.py              # Status: idle, listening, thinking, speaking, senyap
    config.py             # konfigurasi tervalidasi, JSON atomik
    bus.py                # signal/slot internal (tanpa jaringan)
  ui/
    tokens.py             # warna, kaca, huruf, metrik
    catalog.py            # halaman uji semua komponen (Fase 0)
  tests/                  # pytest + pytest-qt
tools/headless_qt/        # stub Qt untuk container tanpa libGL (dev saja)
.github/workflows/ci.yml  # ruff, mypy, pytest (Linux 3.11/3.12 + Windows)
```

## Stack dan keputusan versi

| Komponen | Versi | Alasan |
| --- | --- | --- |
| Python | 3.11 / 3.12 | Mediapipe 1.2.3 mendeklarasikan 3.9–3.14; 3.11 adalah baseline, 3.12 diuji CI. |
| PySide6 | 6.12.0 | Qt 6, wheel `cp310-abi3` untuk Windows/Linux/macOS. |
| mediapipe | 1.2.3 | Wheel `py3-none-manylinux_2_28_x86_64`, `win_amd64`, `win_arm64`; `HandLandmarker` terverifikasi. |
| OpenCV | 4.12.0.88 | Tidak memakai `opencv-python` karena mediapipe 1.2.3 mewajibkan `opencv-contrib-python` (superset). Memasang keduanya akan menimpa modul `cv2` yang sama. |
| numpy | >=2,<3 | Dikunci oleh `uv.lock`. |
| pynput | 1.8.2 | Hanya non-Linux: di Linux pynput menarik `evdev` yang butuh `python3-dev`; target rilis Windows 10/11. |
| pytest / pytest-qt | 8.4.2 / 4.5.0 | Headless dengan `QT_QPA_PLATFORM=offscreen`. |
| ruff / mypy | 0.14.4 / 1.18.2 | `ruff` format + lint, `mypy --strict`. |

Verifikasi versi Python Mediapipe dilakukan sebelum mengunci: wheel 1.2.3 ber-tag
`py3-none` (tidak membatasi ABI) dengan classifier 3.9–3.14. Proyek membatasi
`>=3.11,<3.13` agar tidak menjanjikan versi yang tidak diuji.

## Instalasi

### uv (disarankan)

```bash
uv sync --extra dev
uv run jarvis-hands
```

### venv + pip

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m jarvis_hands
```

Windows:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python -m jarvis_hands
```

Aplikasi Fase 0 membuka **katalog komponen** (jendela pengembang, bukan overlay
produk). Flag `--config`, `--high-contrast`, dan `--version` tersedia.

## Tes dan kualitas

```bash
make bootstrap      # venv + install
make check          # ruff + ruff format + mypy + pytest
# atau
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
```

Tes UI memakai `QT_QPA_PLATFORM=offscreen`. Di Linux tanpa `libGL` (container
minimal), `tests/conftest.py` otomatis membangun stub di `.qt-stubs/` lewat
`tools/headless_qt/build.py`; di desktop normal, Windows, dan macOS jalur itu
tidak aktif.

## Design token Glass Stage

| Token | Hex | Pemakaian |
| --- | --- | --- |
| Panggung | `#070D0F` | Latar utama |
| Teal kaca | `#6FE5D6` | Isi kaca, garis, orb |
| Aksen teks | `#8FF0E4` | Judul aktif |
| Pita cincin | `#8CEBF0` | RingWidget idle/thinking |
| Tepi panas | `#E4FAFC` | Rim putih, speaking |
| Teks | `#ECFFFA` | Teks utama |
| Teks redup | `#A8D8CF` | Keterangan |
| Mendengarkan | `#78CDFA` | Status listening |
| Peringatan | `#F5A524` | Error/ambang kritis |
| Tepi kaca | `#8CF0E1` @ 55% | Border 1.5 px |

Kaca: gradien tembus 18–30%, tepi 1.5 px `rgba(140,240,225,.55)`, highlight
inset di atas. Huruf isi Space Grotesk (fallback Inter/Segoe UI/DejaVu Sans),
label mono kapital berjarak 2–4 px (fallback JetBrains Mono/Consolas/DejaVu Sans
Mono). Font tidak dibundel agar lisensi tetap bersih.

Metrik: cincin 440 px, pita 20 px, 48 tick, orb 112 px, kursor 28 px, titik idle
16 px, target ketuk minimal 56 px.

## Aksesibilitas

- Semua kontrol punya jalur mouse dan keyboard (tombol tetap `QPushButton`).
- Target ketuk >= 56 px; tinggi tombol >= 44 px.
- Tema kontras tinggi (`--high-contrast`) memakai panggung hitam dan teks putih
  (rasio 21:1); teks redup tetap >= 15:1.
- `accessibleName`/`accessibleDescription` untuk tombol, status, toast, dan
  petunjuk.

## Keamanan

- Tidak ada modul runtime yang mengimpor `socket`, `http.server`, atau Qt Network;
  tes `test_security.py` memblokir pola tersebut lewat AST.
- Tidak ada `eval`, `exec`, `pickle`, `marshal`, atau `shelve` di runtime.
- Kamera belum aktif di Fase 0. Nanti frame tidak pernah ditulis ke disk
  (`cv2.imwrite`/`VideoWriter` juga dijaga tes).
- Konfigurasi JSON divalidasi ketat; `memory_root` harus folder yang sudah ada.
  Path traversal/symlink akan ditangani di TreePane (Fase 4).
- Tidak ada telemetri; `telemetry_consent` default `false`.

## Status fase

| Fase | Cakupan | Status |
| --- | --- | --- |
| 0 | Scaffold, token, katalog komponen, CI | **Selesai** |
| 1 | RingWidget lima status + animasi 60 fps | Belum |
| 2 | Kamera + MediaPipe di QThread, One-Euro, kursor, indikator kamera, Ctrl+Alt+G | Belum |
| 3 | Mesin gestur + fixture landmark | Belum |
| 4 | Card/Panel/Orb/TreePane, fisika sederhana | Belum |
| 5 | Overlay tembus klik, tiga mode tampil, multi-monitor/DPI | Belum |
| 6 | Integrasi agen lewat `bridge.py` | Belum |
| 7 | Pengaturan, onboarding kamera, auto-hide | Belum |
| 8 | Profiling, aksesibilitas, keamanan, packaging Windows | Belum |

## Asumsi dan risiko

- `tests/` diletakkan di dalam `jarvis_hands/` sesuai struktur proyek, dan
  dikecualikan dari wheel.
- Fase 0 belum punya `--mode`/`--key`; keduanya ditambahkan di Fase 5 agar tidak
  ada flag mati.
- RingWidget, Orb, Card, TreePane, Overlay, dan Settings belum diimplementasikan;
  katalog menampilkan kartu "TERJADWAL" bertanda fase, bukan tiruan.
- Mediapipe 1.2.3 adalah major baru (classifier Alpha). `HandLandmarker` sudah
  diverifikasi bisa diimpor, tetapi pipeline kamera end-to-end baru diuji di Fase 2.
- Belum diuji di Windows 10/11 bersih; CI Windows menjalankan pytest, uji packaging
  dan uji mesin bersih ada di Fase 8.
- Space Grotesk tidak dibundel; tampilan memakai fallback bila font tidak terpasang.

## Lisensi

Implementasi ditulis dari nol. Konsep terinspirasi proyek open source
**barehands** (jaredrhod/barehands, AGPL-3.0); tidak ada kode dari repo tersebut
yang disalin. **Lisensi proyek ini belum ditetapkan** — silakan pilih (misalnya
AGPL-3.0 jika ingin konsisten dengan inspirasi, atau lisensi lain) sebelum
publikasi. Dependensi pihak ketiga: PySide6 (LGPLv3), mediapipe/OpenCV
(Apache-2.0), numpy (BSD-3), pynput (LGPL-3.0).
