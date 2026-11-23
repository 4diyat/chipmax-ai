# JARVIS Ring & Hands

Antarmuka kaca yang dikendalikan tangan kosong lewat webcam. Cincin adalah wajah
JARVIS; gestur adalah jalur utama, mouse dan keyboard hanya cadangan.

> **Status: Fase 0 sampai Fase 6 diimplementasikan.** Scaffold, design token Glass Stage, katalog
> komponen, CI, RingWidget lima status 60 fps, kamera + MediaPipe di QThread,
> filter One-Euro, kursor 28 px, indikator kamera, jeda Ctrl+Alt+G, dan mesin
> gestur dengan fixture landmark, Card, Panel, Orb, dan TreePane sudah jalan.
> Overlay tiga mode, integrasi kamera–gestur, dan bridge Gemini API teks sudah
> tersedia. Pengaturan menyusul; uji Gemini langsung perlu dilakukan di komputer
> dengan akses internet dan API key.

## Prinsip produk

1. **Tidak menutupi layar.** Mode utama overlay transparan, tembus klik, tidak
   merebut fokus keyboard. Layar penuh hanya opsional.
2. **Gestur dulu.** Semua interaksi bisa dengan tangan; mouse/keyboard cadangan.
3. **Privasi.** Kamera aktif hanya saat Mode Gestur menyala. Video diproses lokal,
   tidak pernah disimpan atau dikirim. Indikator kamera selalu terlihat.
4. **Satu proses, tanpa server lokal.** Permintaan teks Gemini menggunakan
   koneksi HTTPS keluar hanya saat pengguna menekan Kirim.
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
  agent/
    gemini.py             # klien HTTPS Gemini teks-saja, tanpa agen tiruan
    bridge.py             # status dan permintaan di QThread
  gestures/
    types.py              # GestureKind, GesturePhase, GestureEvent
    engine.py             # mesin gestur murni Python (tanpa Qt)
  assets/models/
    hand_landmarker.task  # model resmi Google (Apache-2.0)
  ui/
    tokens.py             # warna, kaca, huruf, metrik
    catalog.py            # halaman uji semua komponen (Fase 0-4)
    card.py / glass.py    # Card, Panel, dan chrome kaca bersama
    physics.py / orb.py   # pegas teredam dan Orb lima status
    treepane.py           # UI pohon memori dan pratinjau baca-saja
    overlay.py            # tiga mode, kontrol, perutean gestur dan monitor
    camera.py             # CameraIndicator: aktif/jeda/mati/error
  memory/tree.py          # pembaca folder memori dan batas keamanan
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

Aplikasi membuka **jendela kontrol** dan jendela tampilan. Kamera **mati secara
bawaan**: tekan *Nyalakan kamera* untuk mulai dan *Matikan kamera* untuk berhenti.
Tombol kontrol juga dapat membuka memori, mengembalikan kartu, menjeda gestur,
dan keluar. Ctrl+Alt+G menjeda/melanjutkan; pada Linux tanpa pynput, pintasan
Qt hanya aktif saat aplikasi memiliki fokus.

```bash
python -m jarvis_hands --mode overlay      # transparan, tidak menerima klik/fokus
python -m jarvis_hands --mode mirror       # frame kamera dalam memori
python -m jarvis_hands --mode key --key green  # latar chroma key
python -m jarvis_hands --mode key --key '#123456' --monitor 1
python -m jarvis_hands --camera            # secara eksplisit nyalakan saat mulai
python -m jarvis_hands --catalog           # katalog komponen pengembang
```

Mode dan monitor dapat diganti lewat jendela kontrol. Monitor bernomor mulai 0;
koordinat menggunakan piksel logis Qt, termasuk origin negatif. Mode cermin dan
key menerima input mouse; mode overlay meneruskan klik ke aplikasi di bawahnya,
dan gestur dirutekan langsung ke komponen JARVIS. Tap kartu membuka memori,
tahan kartu membuka memori, seret memindahkan kartu/panel, dan tap tutup menutup
komponen. Di pohon, tap baris memilih dan membuka/menutup folder. Gestur dua
tangan, clap, scrub, dan explode diterbitkan sebagai sinyal `gesture`; belum
diberi aksi produk sampai integrasi berikutnya. Frame cermin dibersihkan saat
kamera berhenti atau dijeda dan tidak pernah disimpan ke disk.

## Gemini API (Fase 6)

Tidak ada agen mock. Dapatkan Gemini API key sendiri dari Google AI Studio dan
atur environment di komputer Anda **tanpa memasukkan key ke repositori atau chat**.
Contoh Linux/macOS (masukkan key Anda secara lokal):

```bash
export GEMINI_API_KEY='KUNCI_ANDA'
python -m jarvis_hands
```

Windows PowerShell:

```powershell
$env:GEMINI_API_KEY = 'KUNCI_ANDA'
.venv\Scripts\python -m jarvis_hands
```

Pada jendela kontrol, ketik teks lalu tekan **Kirim ke Gemini**. Teks itu dikirim
melalui HTTPS ke Google dan dapat dikenai kuota/biaya sesuai akun. Frame kamera,
landmark, isi folder memori, dan riwayat tidak dikirim otomatis. Setiap permintaan
berdiri sendiri; jangan ketik data rahasia bila tidak ingin mengirimkannya ke
Google. Respons ditampilkan sebagai teks, bukan dieksekusi sebagai perintah.
Tidak ada tool agen, percakapan berkelanjutan, mikrofon, TTS, atau suara sintetis.
Ring dan Orb menampilkan BERPIKIR saat menunggu dan SIAGA setelah selesai; status
MENDENGARKAN dan BERBICARA tidak dipalsukan tanpa sumber audio nyata.

Model bawaan `gemini-3.8-flash` mengikuti [dokumentasi model Google](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).
Untuk memilih model Gemini yang tersedia di akun Anda, atur `GEMINI_MODEL` di
environment sebelum menjalankan aplikasi. Key dikirim melalui header HTTPS,
bukan URL; redirect dan proxy lingkungan dinonaktifkan. Satu permintaan aktif,
timeout jaringan 30 detik per operasi; jika keluar saat permintaan masih aktif,
aplikasi menunggu permintaan selesai agar thread tidak dihentikan paksa. Tidak ada
retry otomatis. Endpoint, format dan header mengikuti [Gemini REST quickstart](https://ai.google.dev/gemini-api/docs/quickstart).

Tes otomatis memakai respons HTTP uji tanpa kunci atau jaringan. Sandbox pengembang
tidak dapat menghubungi endpoint Gemini; **panggilan nyata dan ketersediaan model
belum diverifikasi** dan perlu dicoba sendiri di komputer yang memiliki akses.

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

- Tidak ada server lokal atau modul runtime yang mengimpor `socket`, `http.server`,
  atau Qt Network; `test_security.py` memblokir pola tersebut lewat AST. Klien
  Gemini memakai `urllib` untuk HTTPS keluar ketika pengguna mengirim teks.
- Tidak ada `eval`, `exec`, `pickle`, `marshal`, atau `shelve` di runtime.
- Modul kamera hanya memproses frame di memori; tidak ada `cv2.imwrite`,
  `VideoWriter`, atau penyimpanan frame. `HandTracker` memuat model dari
  `assets/models`, bukan dari jaringan.
- `MemoryTree` hanya membaca di akar yang dipilih: path absolut, `..`, symlink,
  dan reparse point ditolak; entri tersembunyi dilewati. Pratinjau hanya UTF-8,
  maksimal 4 KiB dari file maksimal 64 KiB, hingga 500 entri per folder.
  Pada POSIX, pembukaan folder/file memakai descriptor relatif dan `O_NOFOLLOW`.
  Pada Windows validasi path tidak atomik terhadap perubahan folder oleh proses
  lain (TOCTOU): gunakan akar yang hanya dapat ditulis pengguna tepercaya;
  penguatan dengan handle Windows dan pengujian adversarial masih diperlukan.
  Hard link di dalam akar juga tidak bisa dibedakan dari file biasa.
- Tidak ada telemetri; `telemetry_consent` default `false`.

## Komponen Fase 4

Visual acuan ada di `docs/mockups/`. Kartu berukuran 340×190 px dengan margin
animasi; seret lewat pegangan, pegas kembali ke posisi rumah, atau lepaskan cepat
untuk dismiss. Pegas mencapai sekitar target dalam 180 ms dan benar-benar diam
sekitar 350 ms; batas dan kecepatan dijepit. Panel dan kartu mengirim sinyal
untuk penutupan, bukan menutup otomatis. Orb 112 px memiliki lima mekar dan lima
status. TreePane menampilkan pohon malas, seleksi, dan pratinjau baca-saja.

Jalankan `python -m jarvis_hands --catalog`, gulir ke bagian **10** untuk mencoba mouse,
keyboard dan data contoh; kamera dan koneksi jaringan tidak digunakan katalog.
Contoh pemakaian akar riil dari aplikasi Qt: `TreePane(Path("folder-memori"))`.
Integrasi kamera dan gestur pada overlay tersedia di Fase 5.

## Status fase

| Fase | Cakupan | Status |
| --- | --- | --- |
| 0 | Scaffold, token, katalog komponen, CI | **Selesai** |
| 1 | RingWidget lima status + animasi 60 fps | **Selesai** |
| 2 | Kamera + MediaPipe di QThread, One-Euro, kursor, indikator kamera, Ctrl+Alt+G | **Selesai** |
| 3 | Mesin gestur + fixture landmark | **Selesai** |
| 4 | Card/Panel/Orb/TreePane, fisika sederhana | **Selesai** |
| 5 | Overlay tembus klik, tiga mode tampil, multi-monitor/DPI | **Selesai** |
| 6 | Gemini API teks melalui `bridge.py` | **Diimplementasikan; uji live tertunda** |
| 7 | Pengaturan, onboarding kamera, auto-hide | Belum |
| 8 | Profiling, aksesibilitas, keamanan, packaging Windows | Belum |

## Asumsi dan risiko

- `tests/` diletakkan di dalam `jarvis_hands/` sesuai struktur proyek, dan
  dikecualikan dari wheel.
- Settings belum diimplementasikan. `memory_root` konfigurasi dipakai TreePane;
  jika tidak diisi TreePane menampilkan data contoh.
- Perilaku jendela tembus klik, DPI dan multi-monitor diuji secara otomatis di Qt
  offscreen, bukan pada compositor Windows sesungguhnya; masih perlu diuji manual
  di Windows 10/11, termasuk monitor berbeda DPI dan pelepasan monitor.
- Jendela kontrol sengaja selalu di atas agar kamera bisa dimatikan dan aplikasi
  bisa ditutup walau overlay tidak menerima klik. Pada layar kecil elemen dapat
  bertumpang tindih; kalibrasi gestur dengan tangan nyata masih diperlukan.
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
- Bridge Gemini hanya mengirim teks; tidak ada tindakan lokal otonom, audio,
  atau memori percakapan. Endpoint nyata belum diuji dari sandbox ini.
- Mesin gestur terhubung ke kamera dan komponen overlay; ambang default (tap
  35-260 ms, hold 1000 ms, drag 22 px, clap 600 px/s, explode 800 px/s) perlu
  dikalibrasi dengan tangan asli.
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
