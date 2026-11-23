# Fixture landmark gestur

Setiap file JSON berisi satu urutan frame 30 fps dengan 21 landmark per tangan
dalam koordinat normalisasi 0..1. Fixture dipakai untuk menguji mesin gestur
secara deterministik tanpa webcam.

```json
{
  "name": "tap",
  "description": "Cubit 132 ms tanpa pergeseran, lalu lepas.",
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "frames": [
    {
      "t": 0,
      "hands": [
        {
          "handedness": "Right",
          "score": 0.92,
          "landmarks": [[0.5, 0.5, 0.0], [0.5, 0.48, 0.0], ["..."]]
        }
      ]
    }
  ]
}
```

Daftar fixture:

| Nama | Isi | Harapan |
| --- | --- | --- |
| `tap` | cubit 132 ms, diam | satu `TAP` |
| `tap_short` | cubit 33 ms | tidak ada event |
| `tap_long` | cubit 396 ms | tidak ada event (di bawah hold) |
| `drag` | cubit lalu geser 140 px | `DRAG` begin/update/end |
| `hold` | cubit 1,2 detik | `HOLD` begin/update/end |
| `two_hand` | dua tangan mendekat pelan | `TWO_HAND` begin/end |
| `clap` | dua tangan bertepuk cepat | `CLAP` |
| `scrub_explode` | goyang lalu dua tangan meledak | `SCRUB` + `EXPLODE` |
| `idle` | tangan bergerak pelan tanpa cubit | tidak ada event |

Nilai layar dibangun dengan gain kursor 1.6 dari target 1920x1080, sehingga
ambang piksel di `GestureThresholds` bisa diuji langsung.

Regenerasi (dari root repo):

```bash
.venv/bin/python -m jarvis_hands.tests.fixtures.landmarks.generate
```

Fixture adalah data tiruan; tidak ada frame kamera atau data pribadi di dalamnya.
