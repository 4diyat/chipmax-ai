"""Pengaturan aplikasi.

Modul ini sengaja bebas Qt: nilai default, validasi, dan serialisasi JSON bisa
dites tanpa QApplication. File konfigurasi adalah data lokal milik pengguna, bukan
input tepercaya dari jaringan; tetap divalidasi ketat dan tidak pernah memakai
``pickle``/``eval``.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum, unique
from pathlib import Path
from typing import Any, Final

__all__ = [
    "AppConfig",
    "CameraConfig",
    "ConfigError",
    "CursorConfig",
    "DisplayConfig",
    "DisplayMode",
    "GestureThresholds",
    "KeyColor",
    "KeyColorSpec",
    "default_config_path",
    "load_config",
    "normalize_hex",
    "parse_key_color",
    "save_config",
    "with_display_overrides",
]


class ConfigError(ValueError):
    """Konfigurasi tidak valid; pesan aman untuk ditampilkan ke pengguna."""


@unique
class DisplayMode(StrEnum):
    """Tiga mode tampil sesuai spesifikasi."""

    MIRROR = "mirror"
    OVERLAY = "overlay"
    KEY = "key"


@unique
class KeyColor(StrEnum):
    """Warna kunci untuk capture (chroma key)."""

    MAGENTA = "magenta"
    GREEN = "green"
    BLUE = "blue"
    CUSTOM = "custom"


KEY_COLOR_HEX: Final[dict[KeyColor, str]] = {
    KeyColor.MAGENTA: "#FF00FF",
    KeyColor.GREEN: "#00FF00",
    KeyColor.BLUE: "#0000FF",
}

#: Batas ukuran file konfigurasi (mencegah pembacaan file raksasa dari disk).
MAX_CONFIG_BYTES: Final[int] = 256 * 1024

_HEX_RE: Final = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")


@dataclass(frozen=True)
class KeyColorSpec:
    """Warna kunci terpilih beserta kode hex RGB hasil normalisasi."""

    color: KeyColor
    hex_code: str


def normalize_hex(value: str) -> str:
    """Normalisasi ``#RGB``/``#RRGGBB``/``#RRGGBBAA`` menjadi ``#RRGGBB``."""
    text = value.strip()
    if not _HEX_RE.fullmatch(text):
        raise ConfigError(f"warna hex tidak valid: {value!r} (contoh: #00FF00)")
    digits = text[1:]
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    # Alpha diabaikan: warna kunci dipakai sebagai latar capture.
    return f"#{digits[:6].upper()}"


def parse_key_color(value: str) -> KeyColorSpec:
    """Terima ``magenta|green|blue|#hex`` dan kembalikan spesifikasi warna kunci."""
    text = value.strip()
    if not text:
        raise ConfigError("warna kunci tidak boleh kosong")
    lowered = text.lower()
    if lowered in KeyColor.__members__.values() and lowered != KeyColor.CUSTOM.value:
        color = KeyColor(lowered)
        return KeyColorSpec(color=color, hex_code=KEY_COLOR_HEX[color])
    if text.startswith("#"):
        return KeyColorSpec(color=KeyColor.CUSTOM, hex_code=normalize_hex(text))
    raise ConfigError(
        f"warna kunci tidak dikenal: {value!r} (pilih magenta, green, blue, atau #RRGGBB)"
    )


@dataclass(frozen=True)
class CameraConfig:
    """Pengaturan kamera. ``use_dshow`` hanya berlaku di Windows (``CAP_DSHOW``).

    ``analysis_fps`` memisahkan laju inferensi dari laju capture: frame tetap
    dibaca 30 fps untuk mode Cermin, tetapi MediaPipe hanya dijalankan sesuai
    ``analysis_fps`` dan dibatasi ``max_cpu_percent`` (persen satu core).
    """

    index: int = 0
    width: int = 640
    height: int = 360
    fps: int = 30
    mirror: bool = True
    use_dshow: bool = True
    analysis_scale: float = 1.0
    analysis_fps: int = 30
    max_cpu_percent: float = 25.0


@dataclass(frozen=True)
class GestureThresholds:
    """Ambang gestur.

    ``pinch_*`` adalah rasio jarak jempol-telunjuk terhadap lebar telapak
    (landmark 4-8 dibagi jarak 0-9). Nilai lain bersatuan milidetik atau piksel.
    Histeresis ``pinch_close`` < ``pinch_open`` mencegah kedipan saat cubit.
    """

    pinch_close: float = 0.30
    pinch_open: float = 0.45
    tap_min_ms: int = 35
    tap_max_ms: int = 260
    hold_ms: int = 1000
    drag_start_px: float = 22.0
    clap_window_ms: int = 380
    two_hand_min_px: float = 80.0
    scrub_explode_px: float = 140.0
    scrub_window_ms: int = 700
    scrub_reversals: int = 3
    clap_approach_px: float = 40.0
    clap_min_speed_px_s: float = 600.0
    explode_min_speed_px_s: float = 800.0
    gesture_cooldown_ms: int = 400
    swipe_min_px: float = 100.0
    swipe_max_ms: int = 500
    fist_hold_ms: int = 400


@dataclass(frozen=True)
class CursorConfig:
    """Parameter One-Euro filter dan penguatan gerak kursor."""

    one_euro_min_cutoff: float = 1.2
    one_euro_beta: float = 0.02
    one_euro_d_cutoff: float = 1.0
    gain: float = 1.6


@dataclass(frozen=True)
class DisplayConfig:
    """Pengaturan tampilan, termasuk warna kunci dan mode kontras tinggi."""

    mode: DisplayMode = DisplayMode.OVERLAY
    key_color: KeyColor = KeyColor.MAGENTA
    custom_key_hex: str = "#FF00FF"
    high_contrast: bool = False
    auto_hide_s: int = 10
    #: ``False`` mematikan auto-hide; ``auto_hide_s`` tetap divalidasi >= 1.
    auto_hide_enabled: bool = True
    ui_scale: float = 1.0


@dataclass(frozen=True)
class AppConfig:
    """Konfigurasi akar. ``memory_root`` wajib folder yang sudah ada bila diisi."""

    camera: CameraConfig = field(default_factory=CameraConfig)
    gestures: GestureThresholds = field(default_factory=GestureThresholds)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    memory_root: Path | None = None
    onboarding_done: bool = False
    telemetry_consent: bool = False

    @classmethod
    def default(cls) -> AppConfig:
        """Konfigurasi bawaan tanpa membaca atau menulis disk."""
        return cls()

    def to_dict(self) -> dict[str, Any]:
        """Serialisasi ke dict siap-JSON (tanpa tipe Path)."""
        return {
            "camera": {
                "index": self.camera.index,
                "width": self.camera.width,
                "height": self.camera.height,
                "fps": self.camera.fps,
                "mirror": self.camera.mirror,
                "use_dshow": self.camera.use_dshow,
                "analysis_scale": self.camera.analysis_scale,
                "analysis_fps": self.camera.analysis_fps,
                "max_cpu_percent": self.camera.max_cpu_percent,
            },
            "gestures": {
                "pinch_close": self.gestures.pinch_close,
                "pinch_open": self.gestures.pinch_open,
                "tap_min_ms": self.gestures.tap_min_ms,
                "tap_max_ms": self.gestures.tap_max_ms,
                "hold_ms": self.gestures.hold_ms,
                "drag_start_px": self.gestures.drag_start_px,
                "clap_window_ms": self.gestures.clap_window_ms,
                "two_hand_min_px": self.gestures.two_hand_min_px,
                "scrub_explode_px": self.gestures.scrub_explode_px,
                "scrub_window_ms": self.gestures.scrub_window_ms,
                "scrub_reversals": self.gestures.scrub_reversals,
                "clap_approach_px": self.gestures.clap_approach_px,
                "clap_min_speed_px_s": self.gestures.clap_min_speed_px_s,
                "explode_min_speed_px_s": self.gestures.explode_min_speed_px_s,
                "gesture_cooldown_ms": self.gestures.gesture_cooldown_ms,
                "swipe_min_px": self.gestures.swipe_min_px,
                "swipe_max_ms": self.gestures.swipe_max_ms,
                "fist_hold_ms": self.gestures.fist_hold_ms,
            },
            "cursor": {
                "one_euro_min_cutoff": self.cursor.one_euro_min_cutoff,
                "one_euro_beta": self.cursor.one_euro_beta,
                "one_euro_d_cutoff": self.cursor.one_euro_d_cutoff,
                "gain": self.cursor.gain,
            },
            "display": {
                "mode": self.display.mode.value,
                "key_color": self.display.key_color.value,
                "custom_key_hex": self.display.custom_key_hex,
                "high_contrast": self.display.high_contrast,
                "auto_hide_s": self.display.auto_hide_s,
                "auto_hide_enabled": self.display.auto_hide_enabled,
                "ui_scale": self.display.ui_scale,
            },
            "memory_root": str(self.memory_root) if self.memory_root is not None else None,
            "onboarding_done": self.onboarding_done,
            "telemetry_consent": self.telemetry_consent,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AppConfig:
        """Baca dict (misal JSON) dan validasi setiap nilai."""
        if not isinstance(data, Mapping):
            raise ConfigError("konfigurasi akar harus objek JSON")
        camera = _section(data, "camera")
        gestures = _section(data, "gestures")
        cursor = _section(data, "cursor")
        display = _section(data, "display")

        pinch_close = _float(gestures, "pinch_close", 0.30, "gestures.pinch_close")
        pinch_open = _float(gestures, "pinch_open", 0.45, "gestures.pinch_open")
        if pinch_close >= pinch_open:
            raise ConfigError("gestures.pinch_close harus lebih kecil dari gestures.pinch_open")

        memory_root = _optional_path(data, "memory_root")
        custom_hex = _str(display, "custom_key_hex", "#FF00FF", "display.custom_key_hex")
        custom_hex = normalize_hex(custom_hex)

        return cls(
            camera=CameraConfig(
                index=_int(camera, "index", 0, "camera.index", minimum=0),
                width=_int(camera, "width", 640, "camera.width", minimum=160, maximum=3840),
                height=_int(camera, "height", 360, "camera.height", minimum=90, maximum=2160),
                fps=_int(camera, "fps", 30, "camera.fps", minimum=1, maximum=120),
                mirror=_bool(camera, "mirror", True, "camera.mirror"),
                use_dshow=_bool(camera, "use_dshow", True, "camera.use_dshow"),
                analysis_scale=_float(
                    camera,
                    "analysis_scale",
                    1.0,
                    "camera.analysis_scale",
                    minimum=0.25,
                    maximum=1.0,
                ),
                analysis_fps=_int(
                    camera, "analysis_fps", 30, "camera.analysis_fps", minimum=1, maximum=120
                ),
                max_cpu_percent=_float(
                    camera,
                    "max_cpu_percent",
                    25.0,
                    "camera.max_cpu_percent",
                    minimum=5.0,
                    maximum=100.0,
                ),
            ),
            gestures=GestureThresholds(
                pinch_close=pinch_close,
                pinch_open=pinch_open,
                tap_min_ms=_int(gestures, "tap_min_ms", 35, "gestures.tap_min_ms", minimum=0),
                tap_max_ms=_int(gestures, "tap_max_ms", 260, "gestures.tap_max_ms", minimum=1),
                hold_ms=_int(gestures, "hold_ms", 1000, "gestures.hold_ms", minimum=100),
                drag_start_px=_float(
                    gestures, "drag_start_px", 22.0, "gestures.drag_start_px", minimum=0.0
                ),
                clap_window_ms=_int(
                    gestures, "clap_window_ms", 380, "gestures.clap_window_ms", minimum=50
                ),
                two_hand_min_px=_float(
                    gestures, "two_hand_min_px", 80.0, "gestures.two_hand_min_px", minimum=0.0
                ),
                scrub_explode_px=_float(
                    gestures, "scrub_explode_px", 140.0, "gestures.scrub_explode_px", minimum=0.0
                ),
                scrub_window_ms=_int(
                    gestures, "scrub_window_ms", 700, "gestures.scrub_window_ms", minimum=100
                ),
                scrub_reversals=_int(
                    gestures, "scrub_reversals", 3, "gestures.scrub_reversals", minimum=1
                ),
                clap_approach_px=_float(
                    gestures, "clap_approach_px", 40.0, "gestures.clap_approach_px", minimum=0.0
                ),
                clap_min_speed_px_s=_float(
                    gestures,
                    "clap_min_speed_px_s",
                    600.0,
                    "gestures.clap_min_speed_px_s",
                    minimum=0.0,
                ),
                explode_min_speed_px_s=_float(
                    gestures,
                    "explode_min_speed_px_s",
                    800.0,
                    "gestures.explode_min_speed_px_s",
                    minimum=0.0,
                ),
                gesture_cooldown_ms=_int(
                    gestures,
                    "gesture_cooldown_ms",
                    400,
                    "gestures.gesture_cooldown_ms",
                    minimum=0,
                ),
                swipe_min_px=_float(
                    gestures,
                    "swipe_min_px",
                    100.0,
                    "gestures.swipe_min_px",
                    minimum=0.0,
                ),
                swipe_max_ms=_int(
                    gestures, "swipe_max_ms", 500, "gestures.swipe_max_ms", minimum=1
                ),
                fist_hold_ms=_int(
                    gestures, "fist_hold_ms", 400, "gestures.fist_hold_ms", minimum=1
                ),
            ),
            cursor=CursorConfig(
                one_euro_min_cutoff=_float(
                    cursor, "one_euro_min_cutoff", 1.2, "cursor.one_euro_min_cutoff", minimum=0.001
                ),
                one_euro_beta=_float(
                    cursor, "one_euro_beta", 0.02, "cursor.one_euro_beta", minimum=0.0
                ),
                one_euro_d_cutoff=_float(
                    cursor, "one_euro_d_cutoff", 1.0, "cursor.one_euro_d_cutoff", minimum=0.001
                ),
                gain=_float(cursor, "gain", 1.6, "cursor.gain", minimum=0.25, maximum=6.0),
            ),
            display=DisplayConfig(
                mode=_display_mode(display, "mode", DisplayMode.OVERLAY),
                key_color=_key_color(display, "key_color", KeyColor.MAGENTA),
                custom_key_hex=custom_hex,
                high_contrast=_bool(display, "high_contrast", False, "display.high_contrast"),
                auto_hide_s=_int(
                    display, "auto_hide_s", 10, "display.auto_hide_s", minimum=1, maximum=600
                ),
                auto_hide_enabled=_bool(
                    display, "auto_hide_enabled", True, "display.auto_hide_enabled"
                ),
                ui_scale=_float(
                    display, "ui_scale", 1.0, "display.ui_scale", minimum=0.5, maximum=3.0
                ),
            ),
            memory_root=memory_root,
            onboarding_done=_bool(data, "onboarding_done", False, "onboarding_done"),
            telemetry_consent=_bool(data, "telemetry_consent", False, "telemetry_consent"),
        )


def with_display_overrides(
    config: AppConfig,
    *,
    mode: DisplayMode | None = None,
    key: KeyColorSpec | None = None,
    high_contrast: bool | None = None,
) -> AppConfig:
    """Terapkan override CLI tanpa mengubah objek asli (frozen dataclass)."""
    display = config.display
    if mode is not None:
        display = replace(display, mode=mode)
    if key is not None:
        display = replace(
            display,
            key_color=key.color,
            custom_key_hex=key.hex_code if key.color is KeyColor.CUSTOM else display.custom_key_hex,
        )
    if high_contrast is not None:
        display = replace(display, high_contrast=high_contrast)
    return replace(config, display=display)


def default_config_path() -> Path:
    """Lokasi konfigurasi per platform (roaming di Windows)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "JarvisHands" / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    """Baca konfigurasi; file yang belum ada berarti pakai bawaan."""
    target = path or default_config_path()
    if not target.exists():
        return AppConfig.default()
    if not target.is_file():
        raise ConfigError(f"konfigurasi bukan file: {target}")
    try:
        with target.open("rb") as handle:
            raw_bytes = handle.read(MAX_CONFIG_BYTES + 1)
    except OSError as exc:
        raise ConfigError(f"tidak bisa membaca konfigurasi: {target} ({exc})") from exc
    if len(raw_bytes) > MAX_CONFIG_BYTES:
        raise ConfigError(f"konfigurasi terlalu besar: maksimal {MAX_CONFIG_BYTES} byte")
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError(f"konfigurasi bukan UTF-8: {target} ({exc})") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON konfigurasi rusak: {target} ({exc})") from exc
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    """Tulis konfigurasi secara atomik. Mengembalikan path yang dipakai."""
    target = path or default_config_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp")
        payload = json.dumps(config.to_dict(), indent=2, ensure_ascii=False) + "\n"
        if len(payload.encode("utf-8")) > MAX_CONFIG_BYTES:
            raise ConfigError(f"konfigurasi terlalu besar: maksimal {MAX_CONFIG_BYTES} byte")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, target)
    except OSError as exc:
        raise ConfigError(f"tidak bisa menyimpan konfigurasi: {target} ({exc})") from exc
    if os.name == "posix":
        with contextlib.suppress(OSError):
            target.chmod(0o600)
    return target


def _section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, Mapping):
        raise ConfigError(f"{name} harus objek JSON")
    return value


def _missing_ok(mapping: Mapping[str, Any], key: str) -> bool:
    return key not in mapping


def _str(mapping: Mapping[str, Any], key: str, default: str, name: str) -> str:
    if _missing_ok(mapping, key):
        return default
    value = mapping[key]
    if not isinstance(value, str):
        raise ConfigError(f"{name} harus string")
    return value


def _bool(mapping: Mapping[str, Any], key: str, default: bool, name: str) -> bool:
    if _missing_ok(mapping, key):
        return default
    value = mapping[key]
    if not isinstance(value, bool):
        raise ConfigError(f"{name} harus boolean")
    return value


def _int(
    mapping: Mapping[str, Any],
    key: str,
    default: int,
    name: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if _missing_ok(mapping, key):
        return default
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{name} harus bilangan bulat")
    return int(_checked(value, name, minimum=minimum, maximum=maximum))


def _float(
    mapping: Mapping[str, Any],
    key: str,
    default: float,
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if _missing_ok(mapping, key):
        return default
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"{name} harus angka")
    return float(_checked(float(value), name, minimum=minimum, maximum=maximum))


def _checked(
    value: int | float,
    name: str,
    *,
    minimum: int | float | None = None,
    maximum: int | float | None = None,
) -> int | float:
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} minimal {minimum}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name} maksimal {maximum}")
    return value


def _display_mode(mapping: Mapping[str, Any], key: str, default: DisplayMode) -> DisplayMode:
    raw = _str(mapping, key, default.value, f"display.{key}")
    try:
        return DisplayMode(raw)
    except ValueError as exc:
        raise ConfigError(f"display.{key} tidak dikenal: {raw!r}") from exc


def _key_color(mapping: Mapping[str, Any], key: str, default: KeyColor) -> KeyColor:
    raw = _str(mapping, key, default.value, f"display.{key}")
    try:
        return KeyColor(raw)
    except ValueError as exc:
        raise ConfigError(f"display.{key} tidak dikenal: {raw!r}") from exc


def _optional_path(mapping: Mapping[str, Any], key: str) -> Path | None:
    if _missing_ok(mapping, key) or mapping[key] is None:
        return None
    value = mapping[key]
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} harus path string")
    path = Path(value).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ConfigError(f"{key} tidak dapat diakses: {value!r}") from exc
    if not resolved.is_dir():
        raise ConfigError(f"{key} harus folder: {value!r}")
    return resolved
