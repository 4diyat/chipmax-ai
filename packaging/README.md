# Packaging Windows

Build memakai PyInstaller (extra `packaging`) dan menghasilkan aplikasi
**one-folder** di `dist/jarvis-hands/`. Model Hand Landmarker, lisensi, dan
README-nya dibundel sebagai data aplikasi, jadi aplikasi tidak mengunduh apa pun
saat runtime.

## Prasyarat

- Windows 10/11 x64
- Python 3.12 dan [uv](https://docs.astral.sh/uv/)
- Koneksi internet untuk sinkronisasi dependensi pertama kali

## Build

Dari folder repositori:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

atau klik dua kali `packaging\build_windows.bat`. Hasilnya:

```text
dist\jarvis-hands\jarvis-hands.exe
dist\jarvis-hands\_internal\...
```

Jalankan `jarvis-hands.exe --version` untuk memastikan build bisa dimulai. Build
GUI memakai `console=False`; untuk diagnosa, jalankan dari PowerShell dan periksa
log aplikasi.

## Catatan

- PyInstaller one-folder dipilih agar ukuran dan waktu build lebih terkendali
  dibanding one-file; seluruh folder `dist\jarvis-hands` harus dibagikan.
- Tidak ada installer, code signing, atau Auto Update. Untuk distribusi publik,
  tanda tangani executable dan bundel dengan installer resmi (MSIX/Inno Setup)
  sesuai kebijakan rilis.
- Windows SmartScreen dapat memperingatkan executable yang belum ditandatangani.
- CI GitHub Actions menjalankan build yang sama dan mengunggah artefak
  `jarvis-hands-windows-x64` pada setiap push/pull request.
- Uji packaging di sandbox Linux tidak mencakup smoke test executable Windows;
  jalankan hasil build di Windows 10/11 bersih sebelum rilis.
