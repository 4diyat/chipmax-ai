# Model Hand Landmarker

`hand_landmarker.task` adalah model resmi Google MediaPipe Hand Landmarker
(7.819.105 byte), dipakai tanpa modifikasi untuk mendeteksi 21 landmark tangan
di perangkat. Model berjalan sepenuhnya lokal; tidak ada frame atau landmark
yang dikirim keluar proses.

- Sumber: paket npm `ptmaker-vision-models@1.0.0`, yang mengemas model resmi
  Google MediaPipe tanpa perubahan.
- SHA-256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- Lisensi: Apache License 2.0 (salinan di `LICENSE` pada folder ini).
- Halaman model: https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker

Model dimuat malas oleh `jarvis_hands.vision.tracker.HandTracker`. Bila file
dihapus, pelacakan tangan gagal dengan pesan `TrackerError` yang aman; aplikasi
tetap bisa dijalankan untuk katalog dan mode non-kamera.
