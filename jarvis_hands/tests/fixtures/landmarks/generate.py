"""Pembuat fixture landmark gestur.

Jalankan dari root repo:

    .venv/bin/python -m jarvis_hands.tests.fixtures.landmarks.generate

Setiap fixture berisi frame 30 fps dengan landmark normalisasi. Nilai dibangun
dari koordinat layar 1920x1080 dengan gain kursor 1.6 supaya ambang piksel di
mesin gestur bisa diuji secara deterministik.
"""

from __future__ import annotations

import json
from pathlib import Path

from jarvis_hands.tests.support import make_hand
from jarvis_hands.vision.tracker import HandObservation

HERE = Path(__file__).resolve().parent
WIDTH = 1920
HEIGHT = 1080
GAIN = 1.6
FRAME_MS = 33


def _nx(screen_x: float) -> float:
    return 0.5 + (screen_x - WIDTH / 2) / (WIDTH * GAIN)


def _ny(screen_y: float) -> float:
    return 0.5 + (screen_y - HEIGHT / 2) / (HEIGHT * GAIN)


def _hand(
    screen_x: float,
    screen_y: float,
    *,
    pinch: float = 0.6,
    handedness: str = "Right",
) -> HandObservation:
    return make_hand(
        index=(_nx(screen_x), _ny(screen_y)),
        pinch_ratio=pinch,
        hand_size=0.15,
        handedness=handedness,
        width=WIDTH,
        height=HEIGHT,
    )


def _serialize(hand: HandObservation) -> dict[str, object]:
    return {
        "handedness": hand.handedness,
        "score": hand.score,
        "landmarks": [[round(p.x, 6), round(p.y, 6), round(p.z, 6)] for p in hand.landmarks],
    }


def _frame(timestamp_ms: int, *hands: HandObservation) -> dict[str, object]:
    return {"t": timestamp_ms, "hands": [_serialize(hand) for hand in hands]}


def _write(name: str, description: str, frames: list[dict[str, object]]) -> None:
    payload = {
        "name": name,
        "description": description,
        "width": WIDTH,
        "height": HEIGHT,
        "fps": 30,
        "frames": frames,
    }
    (HERE / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _tap() -> None:
    frames: list[dict[str, object]] = []
    t = 0
    for _ in range(6):
        frames.append(_frame(t, _hand(960, 540)))
        t += FRAME_MS
    for _ in range(4):
        frames.append(_frame(t, _hand(960, 540, pinch=0.15)))
        t += FRAME_MS
    for _ in range(4):
        frames.append(_frame(t, _hand(960, 540)))
        t += FRAME_MS
    _write("tap", "Cubit 132 ms tanpa pergeseran, lalu lepas.", frames)


def _tap_short() -> None:
    frames: list[dict[str, object]] = []
    t = 0
    for _ in range(4):
        frames.append(_frame(t, _hand(960, 540)))
        t += FRAME_MS
    frames.append(_frame(t, _hand(960, 540, pinch=0.15)))
    t += FRAME_MS
    for _ in range(4):
        frames.append(_frame(t, _hand(960, 540)))
        t += FRAME_MS
    _write("tap_short", "Cubit 33 ms, di bawah ambang tap minimum.", frames)


def _tap_long() -> None:
    frames: list[dict[str, object]] = []
    t = 0
    for _ in range(4):
        frames.append(_frame(t, _hand(960, 540)))
        t += FRAME_MS
    for _ in range(12):
        frames.append(_frame(t, _hand(960, 540, pinch=0.15)))
        t += FRAME_MS
    for _ in range(3):
        frames.append(_frame(t, _hand(960, 540)))
        t += FRAME_MS
    _write("tap_long", "Cubit 396 ms, di atas ambang tap dan di bawah hold.", frames)


def _drag() -> None:
    frames: list[dict[str, object]] = []
    t = 0
    for _ in range(4):
        frames.append(_frame(t, _hand(960, 540)))
        t += FRAME_MS
    for _ in range(3):
        frames.append(_frame(t, _hand(960, 540, pinch=0.15)))
        t += FRAME_MS
    for step in range(15):
        frames.append(_frame(t, _hand(960 + step * 10, 540, pinch=0.15)))
        t += FRAME_MS
    for _ in range(3):
        frames.append(_frame(t, _hand(1110, 540)))
        t += FRAME_MS
    _write("drag", "Cubit lalu kursor bergeser 140 px, lepas di ujung.", frames)


def _hold() -> None:
    frames: list[dict[str, object]] = []
    t = 0
    for _ in range(4):
        frames.append(_frame(t, _hand(960, 540)))
        t += FRAME_MS
    for _ in range(2):
        frames.append(_frame(t, _hand(960, 540, pinch=0.15)))
        t += FRAME_MS
    for _ in range(35):
        frames.append(_frame(t, _hand(960, 540, pinch=0.15)))
        t += FRAME_MS
    for _ in range(3):
        frames.append(_frame(t, _hand(960, 540)))
        t += FRAME_MS
    _write("hold", "Cubit ditahan 1,2 detik tanpa pergeseran.", frames)


def _two_hand() -> None:
    frames: list[dict[str, object]] = []
    t = 0
    for step in range(20):
        offset = 150 - step * 7.5
        frames.append(
            _frame(
                t,
                _hand(960 - offset, 540, handedness="Left"),
                _hand(960 + offset, 540, handedness="Right"),
            )
        )
        t += FRAME_MS
    for _ in range(8):
        frames.append(
            _frame(
                t,
                _hand(945, 540, handedness="Left"),
                _hand(975, 540, handedness="Right"),
            )
        )
        t += FRAME_MS
    for step in range(20):
        offset = 15 + step * 7.5
        frames.append(
            _frame(
                t,
                _hand(960 - offset, 540, handedness="Left"),
                _hand(960 + offset, 540, handedness="Right"),
            )
        )
        t += FRAME_MS
    _write("two_hand", "Dua tangan mendekat, berdiam, lalu menjauh pelan.", frames)


def _clap() -> None:
    frames: list[dict[str, object]] = []
    t = 0
    for step in range(4):
        offset = 200 - step * 60
        frames.append(
            _frame(
                t,
                _hand(960 - offset, 540, handedness="Left"),
                _hand(960 + offset, 540, handedness="Right"),
            )
        )
        t += FRAME_MS
    for _ in range(4):
        frames.append(
            _frame(
                t,
                _hand(940, 540, handedness="Left"),
                _hand(980, 540, handedness="Right"),
            )
        )
        t += FRAME_MS
    for step in range(6):
        offset = 20 + step * 30
        frames.append(
            _frame(
                t,
                _hand(960 - offset, 540, handedness="Left"),
                _hand(960 + offset, 540, handedness="Right"),
            )
        )
        t += FRAME_MS
    _write("clap", "Dua tangan bertepuk: mendekat 360 px dalam 132 ms.", frames)


def _scrub_explode() -> None:
    frames: list[dict[str, object]] = []
    t = 0
    for index in range(24):
        x = 960 + (-100 if index % 2 == 0 else 100)
        frames.append(_frame(t, _hand(x, 540)))
        t += FRAME_MS
    for _ in range(3):
        frames.append(
            _frame(
                t,
                _hand(930, 540, handedness="Left"),
                _hand(990, 540, handedness="Right"),
            )
        )
        t += FRAME_MS
    for step in range(5):
        offset = 30 + step * 42
        frames.append(
            _frame(
                t,
                _hand(960 - offset, 540, handedness="Left"),
                _hand(960 + offset, 540, handedness="Right"),
            )
        )
        t += FRAME_MS
    _write("scrub_explode", "Goyang horizontal berulang, lalu dua tangan meledak.", frames)


def _idle() -> None:
    frames: list[dict[str, object]] = []
    t = 0
    for step in range(30):
        frames.append(_frame(t, _hand(960 + step * 5, 540)))
        t += FRAME_MS
    _write("idle", "Tangan bergerak pelan tanpa cubit; tidak ada gestur.", frames)


def main() -> None:
    """Tulis seluruh fixture landmark."""
    _tap()
    _tap_short()
    _tap_long()
    _drag()
    _hold()
    _two_hand()
    _clap()
    _scrub_explode()
    _idle()
    print(f"fixture ditulis ke {HERE}")


if __name__ == "__main__":
    main()
