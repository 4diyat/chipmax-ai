# JARVIS Ring & Hands

Antarmuka kaca yang dikendalikan tangan kosong lewat webcam. Cincin adalah wajah
JARVIS; gestur adalah jalur utama, mouse dan keyboard hanya cadangan.

> **Status: Fase 0 sampai Fase 3 selesai.** Scaffold, design token Glass Stage, katalog
> komponen, CI, RingWidget lima status 60 fps, kamera + MediaPipe di QThread,
> filter One-Euro, kursor 28 px, indikator kamera, jeda Ctrl+Alt+G, dan mesin
> gestur dengan fixture landmark sudah jalan. Overlay, agen, dan pengaturan
> menyusul per fase.

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
    hotkey.py             # Ctrl+Alt+G; pynput global atau fallback Qt
  vision/
    camera.py             # kamera + pelacakan di QThread, throttle CPU
    tracker.py            # pembungkus MediaPipe Hand Landmarker
    filters.py            # One-Euro filter 1D/2D
    cursor.py             # landmark -> kursor layar + histeresis cubit
    session.py            # kamera + hotkey + indikator dalam satu API
  gestures/
    types.py              # GestureKind, GesturePhase, GestureEvent
    engine.py             # mesin gestur murni Python (tanpa Qt)
  assets/models/
    hand_landmarker.task  # model resmi Google (Apache-2.0)
  ui/
    tokens.py             # warna, kaca, huruf, metrik
    catalog.py            # halaman uji semua komponen (Fase 0-2)
    camera.py             # CameraIndicator: aktif/jeda/mati/error
  tests/                  # pytest + pytest-qt
    fixtures/landmarks/   # 9 fixture gestur (tap, drag, hold, clap, ...)
tools/headless_qt/        # stub Qt untuk container tanpa libGL (dev saja)
.github/workflows/ci.yml  # ruff, mypy, pytest (Linux 3.11/3.12 + Windows)
```

## Stack dan keputusan versi

| Komponen | Versi | Alasan |
| --- | --- | --- |
| Python | 3.11 / 3.12 | Mediapipe 1.2.3 mendeklarasikan 3.9–3.14; 3.11 adalah baseline, 3.12 diuji CI. |
| PySide6 | 6.11.3 | Qt 6, wheel `cp310-abi3` untuk Windows/Linux/macOS. 6.12.0 punya bug refcount pada setter yang mengembalikan `None` (mis. `QColor.setAlphaF`, `QFont.setPointSize`), jadi diturunkan. |
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

Aplikasi masih membuka **katalog komponen** (jendela pengembang, bukan overlay
produk). Katalog kini memperlihatkan indikator kamera empat state dan kursor
28 px. API kamera belum dihubungkan ke jendela overlay (Fase 5). Flag
`--config`, `--high-contrast`, dan `--version` tersedia.

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
`tools/headless_qt/build.py`, termasuk stub `libGLESv2.so.2` untuk MediaPipe;
di desktop normal, Windows, dan macOS jalur itu tidak aktif. Wheel PySide6
6.11.3 tidak menyertakan penanda `py.typed`, jadi `make typecheck` menjalankan
`tools/pyside6_typing.py` sebelum mypy.

Tes kamera memakai sumber frame dan tracker tiruan agar deterministik. Ada satu
tes integrasi yang memuat model Hand Landmarker asli di QThread dan memeriksa
SHA-256 bundel `hand_landmarker.task`; jalannya butuh ±1 detik. Mesin gestur
diuji dengan sembilan fixture landmark di `tests/fixtures/landmarks/` (lihat
README di folder tersebut); semua ambang gestur berasal dari `GestureThresholds`.

## Gestur

| Gestur | Pemicu | Event |
| --- | --- | --- |
| Tap | cubit 35-260 ms tanpa geser >= 22 px | `TAP` (one-shot) |
| Drag | cubit lalu kursor bergeser >= 22 px | `DRAG` begin/update/end |
| Hold | cubit >= 1000 ms tanpa geser | `HOLD` begin/update/end |
| Two-hand | dua tangan masuk radius 80 px | `TWO_HAND` begin/end |
| Clap | dua tangan mendekat >= 40 px dengan kecepatan >= 600 px/s | `CLAP` |
| Scrub | goyang horizontal >= 3 pembalikan arah, rentang >= 140 px | `SCRUB_EXPLODE` action `scrub` |
| Explode | dua tangan menjauh >= 140 px dengan kecepatan >= 800 px/s | `SCRUB_EXPLODE` action `explode` |

Semua ambang ada di `GestureThresholds` dan dapat diubah lewat konfigurasi JSON.

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
- Modul kamera hanya memproses frame di memori; tidak ada `cv2.imwrite`,
  `VideoWriter`, atau penyimpanan frame. `HandTracker` memuat model dari
  `assets/models`, bukan dari jaringan.
- Konfigurasi JSON divalidasi ketat; `memory_root` harus folder yang sudah ada.
  Path traversal/symlink akan ditangani di TreePane (Fase 4).
- Tidak ada telemetri; `telemetry_consent` default `false`.

## Status fase

| Fase | Cakupan | Status |
| --- | --- | --- |
| 0 | Scaffold, token, katalog komponen, CI | **Selesai** |
| 1 | RingWidget lima status + animasi 60 fps | **Selesai** |
| 2 | Kamera + MediaPipe di QThread, One-Euro, kursor, indikator kamera, Ctrl+Alt+G | **Selesai** |
| 3 | Mesin gestur + fixture landmark | **Selesai** |
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
- Orb, Card, TreePane, Overlay, dan Settings belum diimplementasikan; katalog
  menampilkan kartu "TERJADWAL" bertanda fase, bukan tiruan.
- Mediapipe 1.2.3 adalah major baru (classifier Alpha). `HandLandmarker` sudah
  diverifikasi end-to-end di QThread dengan model resmi; pada CPU uji 2 core
  Xeon 2.6 GHz inferensi ±14 ms, sehingga throttle otomatis menahan laju analisis
  di ±15 fps agar CPU tetap < 25% satu core. Mesin desktop yang lebih cepat akan
  naik ke 30 fps; `camera.analysis_fps` dan `camera.max_cpu_percent` bisa diatur.
- Wheel mediapipe 1.2.3 tidak membawa file model `.task`. Model resmi Google
  dibundel di `assets/models/hand_landmarker.task` (Apache-2.0, SHA-256 dicatat
  di `assets/models/README.md`).
- `pynput` hanya dipasang di non-Linux. Di Linux tanpa pynput, Ctrl+Alt+G memakai
  fallback Qt yang hanya bekerja saat aplikasi memegang fokus; jalur tanpa gestur
  tetap tersedia lewat pemanggilan `CameraSession.toggle()`/tombol UI.
- RingWidget sudah punya kontrol status tiruan di katalog, tetapi belum terhubung ke
  bridge agen (Fase 6) atau kamera (Fase 5).
- Mesin gestur belum dihubungkan ke kamera/UI; `GestureEngine.process()` siap dipanggil
  dari `landmarks_ready` di Fase 5. Ambang default (tap 35-260 ms, hold 1000 ms,
  drag 22 px, clap 600 px/s, explode 800 px/s) perlu dikalibrasi dengan tangan asli.
- Fixture landmark sintetis, bukan rekaman tangan; bentuk telapak dibuat sederhana
  (landmark lain menumpuk di pergelangan) agar pengujian ambang tetap deterministik.
- Belum diuji di Windows 10/11 bersih; CI Windows menjalankan pytest, uji packaging
  dan uji mesin bersih ada di Fase 8.
- Space Grotesk tidak dibundel; tampilan memakai fallback bila font tidak terpasang.

## Lisensi

Implementasi ditulis dari nol. Konsep terinspirasi proyek open source
**barehands** (jaredrhod/barehands, AGPL-3.0); tidak ada kode dari repo tersebut
yang disalin. **Lisensi proyek ini belum ditetapkan** — silakan pilih (misalnya
AGPL-3.0 jika ingin konsisten dengan inspirasi, atau lisensi lain) sebelum
publikasi. Dependensi pihak ketiga: PySide6 (LGPLv3), mediapipe/OpenCV
(Apache-2.0), numpy (BSD-3), pynput (LGPL-3.0). Model Hand Landmarker yang
dibundel berlisensi Apache-2.0; salinan lisensi ada di
`jarvis_hands/assets/models/LICENSE`.
