"""Pengaturan agen non-rahasia; API key disimpan terpisah di keyring sistem."""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import keyring
from keyring.errors import KeyringError

from jarvis_hands.core.config import default_config_path


class Provider(StrEnum):
    GEMINI = "gemini"
    OLLAMA = "ollama"
    CLAUDE = "claude"
    CHATGPT = "chatgpt"


LABELS = {
    Provider.GEMINI: "Gemini",
    Provider.OLLAMA: "Ollama",
    Provider.CLAUDE: "Claude",
    Provider.CHATGPT: "ChatGPT",
}
DEFAULT_MODELS = {
    Provider.GEMINI: "gemini-3.8-flash",
    Provider.OLLAMA: "llama3.2",
    Provider.CLAUDE: "claude-sonnet-4-6",
    Provider.CHATGPT: "gpt-4.1-mini",
}
ENV_KEYS = {
    Provider.GEMINI: "GEMINI_API_KEY",
    Provider.OLLAMA: "OLLAMA_API_KEY",
    Provider.CLAUDE: "ANTHROPIC_API_KEY",
    Provider.CHATGPT: "OPENAI_API_KEY",
}
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
SERVICE = "jarvis-hands-agent"
_MODEL = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,199}$")


class SettingsError(ValueError):
    """Pengaturan tidak valid atau keyring tidak tersedia."""


def validate_model(value: str, provider: Provider) -> str:
    model = value.strip()
    if not _MODEL.fullmatch(model) or (
        provider is not Provider.OLLAMA and ("/" in model or ":" in model)
    ):
        raise SettingsError("Nama model tidak valid.")
    return model


def validate_ollama_url(value: str) -> str:
    try:
        url = urlsplit(value.strip())
        hostname = url.hostname
        port = url.port
    except ValueError:
        raise SettingsError("Alamat Ollama tidak valid.") from None
    if (
        port == 0
        or not hostname
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
        or url.path not in ("", "/")
    ):
        raise SettingsError("Alamat Ollama harus berupa origin tanpa path, key, atau query.")
    if url.scheme == "http" and hostname not in ("localhost", "127.0.0.1", "::1"):
        raise SettingsError("HTTP hanya diizinkan untuk Ollama lokal; server lain wajib HTTPS.")
    if url.scheme not in ("http", "https"):
        raise SettingsError("Alamat Ollama harus menggunakan HTTP lokal atau HTTPS.")
    if hostname == "localhost" and url.scheme == "http":
        hostname = "127.0.0.1"
    host = f"[{hostname}]" if ":" in hostname else hostname
    return urlunsplit((url.scheme, host + (f":{port}" if port else ""), "", "", ""))


@dataclass
class AgentSettings:
    provider: Provider = Provider.GEMINI
    models: dict[Provider, str] = field(default_factory=lambda: dict(DEFAULT_MODELS))
    ollama_url: str = DEFAULT_OLLAMA_URL

    @property
    def model(self) -> str:
        return self.models[self.provider]

    def validate(self) -> None:
        for provider in Provider:
            self.models[provider] = validate_model(self.models.get(provider, ""), provider)
        self.ollama_url = validate_ollama_url(self.ollama_url)


def settings_path() -> Path:
    return default_config_path().with_name("agent.json")


def load_settings(path: Path | None = None) -> AgentSettings:
    target = path or settings_path()
    if not target.exists():
        settings = AgentSettings()
        model = os.environ.get("GEMINI_MODEL", "").strip()
        if model:
            settings.models[Provider.GEMINI] = model
        settings.validate()
        return settings
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("models", {}), dict):
            raise SettingsError("Pengaturan agen tidak valid.")
        provider = Provider(data.get("provider", "gemini"))
        models = {p: data.get("models", {}).get(p.value, DEFAULT_MODELS[p]) for p in Provider}
        if not all(isinstance(v, str) for v in models.values()) or not isinstance(
            data.get("ollama_url", DEFAULT_OLLAMA_URL), str
        ):
            raise SettingsError("Pengaturan agen tidak valid.")
        settings = AgentSettings(provider, models, data.get("ollama_url", DEFAULT_OLLAMA_URL))
        settings.validate()
        return settings
    except (OSError, ValueError, TypeError) as exc:
        raise SettingsError("Pengaturan agen tidak dapat dibaca atau tidak valid.") from exc


def save_settings(settings: AgentSettings, path: Path | None = None) -> None:
    settings.validate()
    target = path or settings_path()
    payload = {
        "provider": settings.provider.value,
        "models": {p.value: settings.models[p] for p in Provider},
        "ollama_url": settings.ollama_url,
    }
    temp: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent, prefix=".agent-", delete=False
        ) as handle:
            temp = Path(handle.name)
            json.dump(payload, handle, indent=2)
        os.replace(temp, target)
    except OSError as exc:
        raise SettingsError("Pengaturan agen tidak dapat disimpan.") from exc
    finally:
        if temp is not None:
            with contextlib.suppress(OSError):
                temp.unlink(missing_ok=True)


class CredentialStore:
    """Penyimpanan kredensial sistem, tanpa fallback file teks biasa."""

    def _backend(self) -> None:
        backend = keyring.get_keyring()
        # Chainer dapat memasukkan backend tidak aman; hanya backend OS resmi.
        module = type(backend).__module__
        if module not in (
            "keyring.backends.Windows",
            "keyring.backends.macOS",
            "keyring.backends.SecretService",
        ):
            raise SettingsError(
                "Penyimpanan kredensial sistem tidak tersedia. Gunakan environment variable."
            )

    def get(self, provider: Provider) -> str:
        try:
            self._backend()
            return keyring.get_password(SERVICE, provider.value) or ""
        except (KeyringError, RuntimeError):
            raise SettingsError("Penyimpanan kredensial sistem tidak dapat dibaca.") from None

    def set(self, provider: Provider, key: str) -> None:
        if not key.strip():
            raise SettingsError("API key kosong.")
        try:
            self._backend()
            keyring.set_password(SERVICE, provider.value, key.strip())
        except (KeyringError, RuntimeError):
            raise SettingsError("API key tidak dapat disimpan di penyimpanan sistem.") from None

    def delete(self, provider: Provider) -> None:
        try:
            self._backend()
            if keyring.get_password(SERVICE, provider.value) is not None:
                keyring.delete_password(SERVICE, provider.value)
        except (KeyringError, RuntimeError):
            raise SettingsError("API key tidak dapat dihapus dari penyimpanan sistem.") from None


def resolve_key(provider: Provider, store: CredentialStore) -> str:
    """Kunci keyring diutamakan; environment mendukung sistem tanpa keyring."""
    try:
        stored = store.get(provider)
    except SettingsError:
        stored = ""
    return stored or os.environ.get(ENV_KEYS[provider], "").strip()
