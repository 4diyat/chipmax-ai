# JARVIS Ring & Hands

Antarmuka kaca yang dikendalikan tangan kosong lewat webcam. Cincin adalah wajah
JARVIS; gestur adalah jalur utama, mouse dan keyboard hanya cadangan.

> **Status: Fase 0 sampai Fase 8 diimplementasikan.** Scaffold, design token Glass Stage, katalog
> komponen, CI, RingWidget lima status 60 fps, kamera + MediaPipe di QThread,
> filter One-Euro, kursor 28 px, indikator kamera, jeda Ctrl+Alt+G, dan mesin
> gestur dengan fixture landmark, Card, Panel, Orb, dan TreePane sudah jalan.
> Overlay tiga mode, integrasi kamera–gestur, pengaturan tampilan/kamera/gestur,
> onboarding kamera, auto-hide chrome, API teks Gemini/Ollama/Claude/ChatGPT,
> profiling mikro, audit aksesibilitas, penguatan keamanan, dan packaging Windows
> tersedia. Uji langsung tiap penyedia, kalibrasi gestur dengan tangan nyata, dan
> smoke test executable Windows perlu dilakukan di perangkat pengguna.

## Prinsip produk

1. **Tidak menutupi layar.** Mode utama overlay transparan, tembus klik, tidak
   merebut fokus keyboard. Layar penuh hanya opsional.
2. **Gestur dulu.** Semua interaksi bisa dengan tangan; mouse/keyboard cadangan.
3. **Privasi.** Kamera aktif hanya saat Mode Gestur menyala. Video diproses lokal,
   tidak pernah disimpan atau dikirim. Indikator kamera selalu terlihat.
4. **Tidak menjalankan server lokal.** Permintaan teks dikirim hanya saat
   pengguna menekan Kirim; Ollama memakai server yang sudah dijalankan pengguna.
5. **Satu bahasa desain.** Glass Stage, token di `jarvis_hands/ui/tokens.py`.

## Struktur

```
jarvis_hands/
  app.py                  # entry, CLI, wiring QApplication
  core/
    state.py              # Status: idle, listening, thinking, speaking, senyap
    config.py             # konfigurasi tervalidasi, JSON atomik, batas ukuran
    bus.py                # signal/slot internal (tanpa jaringan)
    hotkey.py             # Ctrl+Alt+G; pynput global atau fallback Qt
  profiling.py            # benchmark mikro One-Euro, kursor, dan mesin gestur
  vision/
    camera.py             # kamera + pelacakan di QThread, throttle CPU
    tracker.py            # pembungkus MediaPipe Hand Landmarker
    filters.py            # One-Euro filter 1D/2D
    cursor.py             # landmark -> kursor layar + histeresis cubit
    session.py            # kamera + hotkey + indikator dalam satu API
  agent/
    gemini.py             # klien HTTPS Gemini teks-saja, tanpa agen tiruan
    providers.py          # API Claude, OpenAI dan Ollama
    settings.py           # preferensi non-rahasia dan kredensial keyring
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
    agent_settings.py     # halaman/dialog pengaturan provider, model dan API key
    settings.py           # dialog pengaturan tampilan, kamera, gestur
    onboarding.py         # panduan empat langkah: privasi, kamera, gestur
    autohide.py           # pengatur waktu idle untuk auto-hide chrome
    accessibility.py      # audit nama aksesibel dan target tombol
    camera.py             # CameraIndicator: aktif/jeda/mati/error
  memory/tree.py          # pembaca folder memori dan batas keamanan
  tests/                  # pytest + pytest-qt
    fixtures/landmarks/   # 9 fixture gestur (tap, drag, hold, clap, ...)
tools/headless_qt/        # stub Qt untuk container tanpa libGL (dev saja)
packaging/                # spec PyInstaller dan skrip build Windows
.github/workflows/ci.yml  # ruff, mypy, pytest, build PyInstaller Windows
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

Dari folder repositori, instal dependensi aplikasi yang dikunci dalam
`requirements.txt` (Python 3.11 atau 3.12):

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m jarvis_hands
```

Windows:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m jarvis_hands
```

File tersebut hanya mencakup dependensi runtime, bukan paket proyek atau alat
pengembangan. Untuk tes/lint dan perintah `jarvis-hands`, pasang proyek beserta
extra pengembangan dengan `.venv/bin/python -m pip install -e ".[dev]"` (di
Windows gunakan `.venv\Scripts\python`). Setelah `uv.lock` berubah, perbarui
file dengan `uv export --locked --no-dev --no-emit-project --no-hashes --output-file requirements.txt`.

### Skrip untuk menjalankan

Setelah virtual environment dan dependensi terpasang seperti di atas, gunakan
`run.bat` di Windows (bisa diklik dua kali) atau `./run.sh` di Linux/macOS.
Skrip tidak menginstal paket secara otomatis. Argumen aplikasi juga diteruskan,
misalnya `run.bat --mode mirror` atau `./run.sh --catalog`.

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
python -m jarvis_hands --no-onboarding     # lewati panduan awal
python -m jarvis_hands --profile           # benchmark mikro jalur kursor/gestur
python -m jarvis_hands --a11y-audit        # audit aksesibilitas lalu keluar
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

## Pengaturan Agen & API

Buka **Pengaturan Agen & API** pada jendela kontrol. Pilih **Gemini, Ollama,
Claude, atau ChatGPT**, isi nama model dan API key sesuai penyedia, lalu tekan
**Simpan Pengaturan**. Key yang sudah tersimpan tidak ditampilkan kembali; kolom
kosong mempertahankan key sebelumnya. **Hapus Key** menghapus key tersimpan untuk
penyedia terpilih, tetapi tidak mengubah environment variable. Setiap penyedia
memiliki key dan model tersendiri. Tombol **Uji Koneksi** mengirim permintaan
nyata dan dapat memakai kuota/biaya; uji tidak menyimpan perubahan otomatis.

Key disimpan menggunakan kredensial sistem melalui `keyring`: Windows Credential
Manager, macOS Keychain atau Linux Secret Service. Bila backend sistem tidak
tersedia/terkunci, aplikasi **menolak menyimpan key**, tanpa fallback file teks.
Anda tetap dapat mengatur `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
atau `OLLAMA_API_KEY` di environment secara lokal. Key yang tersimpan didahulukan
daripada environment. Model, pilihan penyedia, dan alamat Ollama disimpan di
`agent.json` di direktori konfigurasi JARVIS; API key tidak ditulis di sana.
Jangan mengirim key ke chat atau memasukkannya ke repositori.

Ollama memerlukan server yang sudah dijalankan pengguna; aplikasi ini **tidak
menjalankan server lokal**. HTTP diizinkan hanya ke loopback (`localhost`,
`127.0.0.1`, atau `::1`); server lain wajib HTTPS. API key Ollama, jika digunakan,
hanya dikirim melalui HTTPS. Pilih model yang sudah terpasang pada server Ollama.
Claude menggunakan Anthropic API dan ChatGPT menggunakan OpenAI API; langganan
aplikasi chat tidak selalu mencakup akses atau biaya API. Sesuaikan model dengan
akses akun masing-masing; tidak ada pengunduhan model otomatis.

Setiap permintaan mengirim hanya teks yang diketik ke penyedia terpilih; kamera,
landmark, folder memori, dan riwayat tidak dikirim otomatis. Permintaan berdiri
sendiri; jangan ketik data yang tidak ingin Anda kirim. Tidak ada agen mock, tool
lokal, mikrofon, TTS, atau percakapan berkelanjutan. Ring dan Orb menampilkan
BERPIKIR selama permintaan dan SIAGA setelahnya. Satu permintaan aktif, dengan
batas 30 detik per operasi jaringan. Redirect dan proxy environment dinonaktifkan;
tidak ada retry otomatis. Saat keluar di tengah permintaan, kamera dihentikan dan
aplikasi menunggu thread selesai.

Referensi API: [Gemini](https://ai.google.dev/gemini-api/docs/quickstart),
[Claude](https://platform.claude.com/docs/en/api/messages/create),
[OpenAI](https://platform.openai.com/docs/api-reference/chat/completions),
[Ollama](https://docs.ollama.com/api/chat). Tes otomatis memakai respons HTTP
uji tanpa kunci atau jaringan. Sandbox ini tidak dapat memverifikasi layanan
cloud atau Ollama yang berjalan; uji live tiap provider dan keyring Windows perlu
dilakukan di perangkat pengguna.

## Pengaturan tampilan, kamera, gestur & onboarding

Buka **Pengaturan** pada jendela kontrol. Dialog ini memiliki empat halaman:
**Agen & API**, **Tampilan**, **Kamera**, dan **Gestur**. Perubahan hanya menjadi
draf sampai **SIMPAN PENGATURAN** ditekan; validasi dilakukan untuk semua halaman
sebelum `config.json` ditulis secara atomik di direktori konfigurasi platform
(`--config` dapat mengganti lokasi). Konfigurasi sekarang selalu dimuat dari lokasi
tersebut saat aplikasi dimulai, bukan hanya saat `--config` diberikan.

- **Tampilan**: mode overlay/cermin/key, warna kunci dan hex kustom, kontras
  tinggi, auto-hide (centang untuk menonaktifkan, jeda 1–600 detik), dan skala UI.
  Mode dan warna kunci langsung diterapkan; kontras tinggi dan skala UI diterapkan
  setelah aplikasi dimulai ulang.
- **Kamera**: indeks kamera, resolusi, FPS capture, mirror, DirectShow (Windows),
  laju analisis, skala analisis, dan batas CPU. Perubahan diterapkan saat kamera
  dinyalakan kembali. Tombol **Buka Panduan Kamera** membuka onboarding.
- **Gestur**: seluruh ambang `GestureThresholds` (cubit, tap, hold, drag, dua
  tangan, clap, scrub/explode, dan jeda gestur). Relasi `pinch_close < pinch_open`
  dan `tap_min_ms <= tap_max_ms` divalidasi. **Pulihkan Bawaan** mengembalikan
  nilai default tanpa menyimpan.
- **Agen & API**: halaman yang sama dengan Fase 6; key tetap di keyring dan tidak
  pernah ditulis ke `config.json`.

**Onboarding** empat langkah muncul otomatis saat `onboarding_done` bernilai
`false` (pengguna baru). Langkah kamera menampilkan pratinjau frame di memori dan
memakai `CameraSession` (kelas yang sama dengan aplikasi; kamera utama dihentikan
dulu bila sedang menyala); frame dibersihkan saat kamera berhenti atau dialog
ditutup. Langkah gestur memberi umpan balik langsung
(`Tangan terlihat`, `cubit`, dsb.). **LEWATI** atau menyelesaikan panduan menandai
`onboarding_done` dan menyimpan konfigurasi; bila kotak **Jangan tampilkan panduan
ini lagi** dinonaktifkan, panduan akan muncul lagi pada peluncuran berikutnya. Panduan
dapat dibuka kembali lewat tombol **Panduan kamera & gestur** di jendela kontrol
atau dari halaman Kamera.

**Auto-hide** menyembunyikan ring, orb, dan kartu setelah `display.auto_hide_s`
detik tanpa aktivitas (tangan terlihat, gerak/klik mouse, mode berubah, atau
jawaban agen). Indikator kamera **tidak pernah** ikut disembunyikan. Aktivitas
berikutnya menampilkan chrome kembali; saat agen sedang BERPIKIR, auto-hide ditahan.
Set `display.auto_hide_enabled` ke `false` (atau hilangkan centang di pengaturan)
untuk mematikan auto-hide tanpa mengubah jeda.

Pengaturan gestur yang baru langsung diterapkan ke mesin gestur dan filter kursor
tanpa me-restart aplikasi; pengaturan kamera baru dipakai pada penyalakan kamera
berikutnya.

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

### Profiling mikro

```bash
python -m jarvis_hands --profile
python -m jarvis_hands --profile --profile-iterations 5000
```

Perintah ini mengukur One-Euro 2D, konversi landmark ke kursor, dan mesin gestur
dengan landmark sintetis, lalu mencetak tabel Markdown. Jalur ini bebas Qt dan
jaringan sehingga bisa dipakai di CI atau sebelum/sesudah mengubah ambang. Hasil
satu mesin tidak boleh dibandingkan langsung dengan mesin lain; gunakan sebagai
deteksi regresi pada perangkat yang sama.

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
Mono). Font tidak dibundel agar lisensi tetap bersih. Skala huruf di
`tokens.FontTokens`: display 30 pt, title 20 pt, body 14 pt, small 12 pt, label
10 pt; tidak ada ukuran huruf lepas di modul UI.

Metrik: cincin 440 px, pita 20 px, 48 tick, orb 112 px, kursor 28 px, titik idle
16 px, target ketuk minimal 56 px. Radius panel 20 px dan radius kontrol 12 px
(`GlassStyle.control_radius`).

### QSS bersama

`ui/qss.py` membangun stylesheet dialog/jendela kontrol dari palet `Theme`, jadi
tidak ada warna hex lepas dan tema kontras tinggi otomatis dipakai. Guard statis
`tests/test_design_system.py` memblokir hex literal, `font-size` lepas, dan
pemanggilan `sans_font(<angka>)`/`mono_font(<angka>)` di luar `tokens.py`.
Warna transparan di QSS wajib lewat `tokens.rgba_css()`; Qt **tidak** memahami
`#AARRGGBB` dan membacanya terbalik sebagai `#RRGGBB`.

## Aksesibilitas

- Semua kontrol punya jalur mouse dan keyboard (tombol tetap `QPushButton`).
- Target ketuk >= 56 px; tinggi tombol dan input >= 44 px. Audit otomatis
  memeriksa `minimumHeight` tombol/input dan nama aksesibel input/tombol.
- Tema kontras tinggi (`--high-contrast`) memakai panggung hitam dan teks putih
  (rasio 21:1); teks redup tetap >= 15:1.
- `accessibleName`/`accessibleDescription` untuk tombol, status, toast, petunjuk,
  input pengaturan, pratinjau memori, dan jawaban agen.
- Pintasan keyboard: `Ctrl+,` membuka Pengaturan, `F1` membuka panduan kamera,
  `Ctrl+Alt+G` menjeda gestur, `Ctrl+Alt+C` memutar status chrome overlay
  (tampil → sembunyi → auto-hide), `Esc` menutup dialog.

```bash
python -m jarvis_hands --a11y-audit
```

Perintah ini membangun jendela katalog, pengaturan, onboarding, dan kontrol secara
offscreen, lalu mencetak temuan. Exit code 0 berarti tidak ada temuan pada widget
yang diperiksa; audit ini tidak menggantikan pengujian dengan pembaca layar
sungguhan (NVDA/JAWS/VoiceOver).

## Keamanan

- Tidak ada server lokal yang dimulai aplikasi atau modul runtime yang mengimpor
  `socket`, `http.server`, `subprocess`, `ctypes`, atau Qt Network;
  `test_security.py` memblokir pola tersebut lewat AST. Klien memakai `urllib`
  untuk koneksi keluar saat pengguna mengirim teks; Ollama dapat memakai server
  loopback yang sudah ada.
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
- `config.json` dibatasi 256 KiB dan `agent.json` 64 KiB; file lebih besar ditolak
  sebelum diparse. Kedua file ditulis atomik dan, di POSIX, diberi izin `0600`.
  API key tidak pernah masuk ke file tersebut.
- Tidak ada telemetri; `telemetry_consent` default `false`.

## Packaging Windows

Build memakai PyInstaller one-folder lewat `packaging/jarvis-hands.spec`; model
Hand Landmarker, lisensi, dan README-nya dibundel sebagai data aplikasi. Dari
PowerShell di folder repositori:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

Hasilnya di `dist\jarvis-hands\jarvis-hands.exe` beserta folder `_internal`.
Tidak ada installer, code signing, atau Auto Update. CI GitHub Actions
menjalankan build yang sama pada Windows dan mengunggah artefak
`jarvis-hands-windows-x64`. Uji packaging di sandbox Linux tidak mencakup
executable Windows; lakukan smoke test di Windows 10/11 bersih sebelum rilis.

## Komponen Fase 4

Visual acuan ada di `docs/mockups/`. Kartu berukuran 340×190 px dengan margin
animasi; seret lewat pegangan, pegas kembali ke posisi rumah, atau lepaskan cepat
untuk dismiss. Pegas mencapai sekitar target dalam 180 ms dan benar-benar diam
sekitar 350 ms; batas dan kecepatan dijepit. Panel dan kartu mengirim sinyal
untuk penutupan, bukan menutup otomatis. Orb 112 px memiliki lima mekar dan lima
status. TreePane menampilkan pohon malas, seleksi, dan pratinjau baca-saja.

Chrome overlay mengikuti mockup: toast kanan atas (mode gestur, status kamera),
baris petunjuk bawah dengan status kamera/FPS di kanan, dan titik idle 16 px saat
chrome disembunyikan (target ketuk 44 px). `Ctrl+Alt+C` memutar tiga status chrome:
tampil selalu, disembunyikan, atau auto-hide setelah idle.

Jalankan `python -m jarvis_hands --catalog`, gulir ke bagian **10** untuk mencoba mouse,
keyboard dan data contoh; kamera dan koneksi jaringan tidak digunakan katalog.
Bagian **11** menampilkan halaman pengaturan tampilan dan gestur Fase 7.
Contoh pemakaian akar riil dari aplikasi Qt: `TreePane(Path("folder-memori"))`.
Integrasi kamera dan gestur pada overlay tersedia di Fase 5.

## Selisih dengan mockup

Mockup di `docs/mockups/` ditinjau terhadap implementasi nyata (render offscreen)
dan bagian yang menyimpang sudah disamakan:

- **Card**: judul 20 pt tebal, chip di bawah judul, isi 12 pt, dan baris footer
  mono kecil (mis. `TAHAN 1 DETIK`) seperti mockup. Judul terlalu panjang
  diturunkan ukurannya lalu dipotong elipsis agar tidak menimpa tombol tutup.
- **Panel**: judul 20 pt tebal dan tidak lagi dipaksa kapital, chip sebaris di
  kanan judul.
- **TreePane**: breadcrumb `memori / proyek / jarvis / catatan.md` di header
  panel, judul berkas 20 pt + baris keterangan `4 KB · LOKAL · DATA TIDAK
  TERPERCAYA`, paragraf penjelasan, catatan keamanan amber, chip tunggal
  `AKAR AMAN`, baris 56 px, dan footnote `BARIS 56 PX …` di bawah panel.
  Seleksi memakai palette teal transparan — sebelumnya `#AARRGGBB` di QSS
  dibaca Qt sebagai `#RRGGBB` sehingga muncul blok biru pekat.
- **Pengaturan**: sidebar berikon (gear, monitor, kamera, tangan) dengan isian +
  bilah teal untuk halaman aktif, tombol nav menggambar ikon/teks sendiri agar
  label `AGEN & API` tidak menjadi `AGEN_API`; lambang mekar di piringan kaca,
  tombol tutup lingkaran berikon, tombol primer berisi teal.
- **Agen & API**: label mono di atas kolom input, baris `ALAMAT OLLAMA` hanya
  untuk Ollama, ikon mata di kolom key, notice berpagar gembok dengan badge
  status uji di kanan, tombol hapus key berupa ikon tempat sampah.
- **Overlay**: toast kanan atas, baris petunjuk bawah (petunjuk kiri, status
  kamera/FPS kanan), orb di samping cincin, dan titik idle 16 px.

Fitur yang juga mengikuti mockup (bukan hanya tampilan):

- **Kartu**: `CUBIT SINGKAT` mengaktifkan target/tombol tempat kursor berada;
  `TAHAN 1 DETIK` membuka memori dari kartu dengan progres tahan tampil di baris
  footer (`MENAHAN 50%`); `CUBIT + SERET` memindahkan kartu/panel dengan
  kemiringan mengikuti kecepatan; tombol tutup berlingkaran 44 px dengan area
  ketuk 56 px (mockup: "tutup 44 px" + "target >= 56 px").
- **Panel**: klik badan panel (mode cermin/mouse) memicu aksi yang sama seperti
  gestur tap — jalan non-gestur tetap tersedia.
- **TreePane**: folder dibuka di tempat (tanpa pindah halaman), seleksi tebal,
  isi berkas hanya dibaca sebagai teks (tanpa eval/exec/pickle).
- **Agen & API**: label penyedia mengikuti nama tampilan (Google Gemini dsb.),
  baris "Penyedia aktif · Gemini API" berubah per penyedia, placeholder kolom
  key menyesuaikan penyedia, dan `ALAMAT OLLAMA` hanya muncul untuk Ollama.
- **Overlay**: toast kanan atas, baris petunjuk bawah, titik idle 16 px saat
  chrome auto-hide (10 detik), status kamera/FPS di kanan bawah.

Yang **tetap berbeda karena keputusan produk** (bukan bug visual):

- Nama penyedia memakai label teks (Gemini/Ollama/Claude/ChatGPT), bukan empat
  logo merek berwarna; logo pihak ketiga tidak dibundel.
- Mockup menggambar cincin lebih tebal (±40 px) daripada metrik produk 20 px;
  mockup adalah pratinjau, angkanya tetap mengikuti `tokens.METRICS`.
- Tombol keyboard tetap ada di jendela kontrol terpisah (jalan non-gestur) walau
  tidak digambar di mockup.
- Pratinjau teks panjang di mockup (paragraf `Isi folder dibaca…`) memakai teks
  penjelasan tetap; isi berkas sebenarnya tampil di kotak pratinjau di bawahnya.
- Status uji koneksi tetap berupa teks (mis. `Keyring sistem tidak tersedia…`)
  di samping badge, karena pesannya bergantung pada hasil uji nyata.

## Status fase

| Fase | Cakupan | Status |
| --- | --- | --- |
| 0 | Scaffold, token, katalog komponen, CI | **Selesai** |
| 1 | RingWidget lima status + animasi 60 fps | **Selesai** |
| 2 | Kamera + MediaPipe di QThread, One-Euro, kursor, indikator kamera, Ctrl+Alt+G | **Selesai** |
| 3 | Mesin gestur + fixture landmark | **Selesai** |
| 4 | Card/Panel/Orb/TreePane, fisika sederhana | **Selesai** |
| 5 | Overlay tembus klik, tiga mode tampil, multi-monitor/DPI | **Selesai** |
| 6 | Agen teks Gemini, Ollama, Claude, ChatGPT dan pengaturannya | **Diimplementasikan; uji live tertunda** |
| 7 | Pengaturan, onboarding kamera, auto-hide | **Selesai** |
| 8 | Profiling, aksesibilitas, keamanan, packaging Windows | **Selesai; smoke test Windows tertunda** |

## Asumsi dan risiko

- `tests/` diletakkan di dalam `jarvis_hands/` sesuai struktur proyek, dan
  dikecualikan dari wheel.
- Build PyInstaller Windows hanya divalidasi lewat CI (artefak diunggah); sandbox
  Linux tidak bisa menjalankan executable Windows. Uji smoke build, SmartScreen,
  dan code signing tetap perlu dilakukan di Windows 10/11.
- Pengaturan tampilan, kamera, gestur, onboarding, dan auto-hide sudah tersedia.
  `memory_root` dipakai TreePane; bila tidak diisi, TreePane menampilkan data
  contoh. Uji onboarding dengan webcam dan keyring Windows tetap perlu dilakukan
  di perangkat pengguna.
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
- Bridge agen hanya mengirim teks; tidak ada tindakan lokal otonom, audio,
  atau memori percakapan. Endpoint nyata dan keyring Windows belum diuji di sandbox.
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
