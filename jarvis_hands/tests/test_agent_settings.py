"""Tes pengaturan, kredensial dan protokol API tanpa kunci atau jaringan nyata."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt

from jarvis_hands.agent import providers
from jarvis_hands.agent.gemini import AgentError
from jarvis_hands.agent.settings import (
    DEFAULT_MODELS,
    MAX_SETTINGS_BYTES,
    AgentSettings,
    CredentialStore,
    Provider,
    SettingsError,
    load_settings,
    save_settings,
    validate_ollama_url,
)
from jarvis_hands.tests.test_gemini import Transport
from jarvis_hands.ui.agent_settings import AgentSettingsDialog


class LocalStore(CredentialStore):
    """Penyimpanan dalam memori hanya di tes, tidak digunakan aplikasi."""

    def __init__(self) -> None:
        self.keys: dict[Provider, str] = {}

    def get(self, provider: Provider) -> str:
        return self.keys.get(provider, "")

    def set(self, provider: Provider, key: str) -> None:
        self.keys[provider] = key

    def delete(self, provider: Provider) -> None:
        self.keys.pop(provider, None)


def test_settings_roundtrip_no_secrets(tmp_path: Path) -> None:
    settings = AgentSettings()
    settings.provider = Provider.CLAUDE
    settings.models[Provider.CLAUDE] = "claude-test"
    path = tmp_path / "agent.json"
    save_settings(settings, path)
    assert load_settings(path) == settings
    assert "key" not in path.read_text(encoding="utf-8").lower()
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_load_settings_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "agent.json"
    path.write_text(
        '{"models": {"gemini": "' + "a" * (MAX_SETTINGS_BYTES + 16) + '"}}',
        encoding="utf-8",
    )
    with pytest.raises(SettingsError, match="terlalu besar"):
        load_settings(path)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:11434",
        "file:///etc/passwd",
        "http://user:secret@localhost:11434",
        "http://localhost:11434/api",
        "https://example.com?key=secret",
        "http://127.0.0.1:99999",
    ],
)
def test_ollama_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(SettingsError):
        validate_ollama_url(url)


def test_ollama_local_and_https_urls() -> None:
    assert validate_ollama_url("http://localhost:11434/") == "http://127.0.0.1:11434"
    assert validate_ollama_url("https://example.com:443") == "https://example.com:443"
    assert validate_ollama_url("http://[::1]:11434") == "http://[::1]:11434"


def test_unavailable_keyring_never_uses_plaintext(monkeypatch: Any) -> None:
    class Insecure:
        pass

    monkeypatch.setattr("keyring.get_keyring", lambda: Insecure())
    with pytest.raises(SettingsError):
        CredentialStore().set(Provider.GEMINI, "secret")


@pytest.mark.parametrize(
    ("provider", "url", "output"),
    [
        (
            Provider.CLAUDE,
            "https://api.anthropic.com/v1/messages",
            {"content": [{"type": "text", "text": "hasil claude"}]},
        ),
        (
            Provider.CHATGPT,
            "https://api.openai.com/v1/chat/completions",
            {"choices": [{"message": {"content": "hasil openai"}, "finish_reason": "stop"}]},
        ),
        (
            Provider.OLLAMA,
            "http://127.0.0.1:11434/api/chat",
            {"message": {"content": "hasil ollama"}, "done": True},
        ),
    ],
)
def test_provider_wire_contract(
    provider: Provider, url: str, output: dict[str, Any], monkeypatch: Any
) -> None:
    transport = Transport(json.dumps(output).encode())
    monkeypatch.setattr(providers, "build_opener", lambda *handlers: transport)
    settings = AgentSettings(provider=provider)
    key = "" if provider is Provider.OLLAMA else "test-secret"
    assert providers.generate("Halo", settings=settings, key=key).startswith("hasil")
    request = transport.request
    assert request.full_url == url
    assert "test-secret" not in url
    body = json.loads(request.data)
    assert body["model"] == DEFAULT_MODELS[provider]
    assert body["messages"] == [{"role": "user", "content": "Halo"}]
    assert "tools" not in body
    if provider is Provider.CLAUDE:
        assert request.get_header("X-api-key") == "test-secret"
        assert request.get_header("Anthropic-version") == "2023-06-01"
    elif provider is Provider.CHATGPT:
        assert request.get_header("Authorization") == "Bearer test-secret"
    else:
        assert body["stream"] is False
        assert request.get_header("Authorization") is None


def test_ollama_never_sends_key_over_http() -> None:
    with pytest.raises(AgentError):
        providers.generate("halo", settings=AgentSettings(provider=Provider.OLLAMA), key="secret")


def test_provider_responses_invalid() -> None:
    for provider in (Provider.CLAUDE, Provider.CHATGPT, Provider.OLLAMA):
        with pytest.raises(AgentError):
            providers.parse_response(provider, {})


def test_dialog_saves_separate_provider_keys(qtbot: Any, tmp_path: Path) -> None:
    store = LocalStore()
    path = tmp_path / "agent.json"
    dialog = AgentSettingsDialog(AgentSettings(), store, path=path)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.key.echoMode() == dialog.key.EchoMode.Password
    dialog.key.setText("gemini-secret")
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    assert store.keys[Provider.GEMINI] == "gemini-secret"
    assert "gemini-secret" not in path.read_text(encoding="utf-8")
    assert not dialog.key.text()
    dialog.provider_dropdown.setCurrentText("Claude")
    dialog.model.setCurrentText("claude-user-model")
    dialog.key.setText("claude-secret")
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    assert store.keys[Provider.CLAUDE] == "claude-secret"
    saved = load_settings(path)
    assert saved.provider is Provider.CLAUDE
    assert saved.models[Provider.CLAUDE] == "claude-user-model"
    assert "claude-secret" not in path.read_text(encoding="utf-8")
    dialog.provider_dropdown.setCurrentText("Ollama")
    assert dialog.url.isEnabled()
    assert not dialog.key.text()
    dialog.close()


def test_connection_test_calls_selected_provider(
    qtbot: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    store = LocalStore()
    dialog = AgentSettingsDialog(AgentSettings(), store, path=tmp_path / "agent.json")
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.provider_dropdown.setCurrentText("Ollama")
    transport = Transport(json.dumps({"message": {"content": "OK"}}).encode())
    monkeypatch.setattr(providers, "build_opener", lambda *handlers: transport)
    qtbot.mouseClick(dialog.test_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not dialog._tester.busy, timeout=5000)
    assert "Koneksi berhasil" in dialog.test_status.text()
    assert transport.request.full_url.endswith("/api/chat")
    assert not (tmp_path / "agent.json").exists()
    dialog.close()


def test_control_settings_apply_and_reload(
    qtbot: Any, qapp: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    from jarvis_hands.core.config import AppConfig
    from jarvis_hands.ui.overlay import ControlWindow

    path = tmp_path / "agent.json"
    monkeypatch.setattr("jarvis_hands.agent.settings.settings_path", lambda: path)
    store = LocalStore()
    control = ControlWindow(AppConfig.default(), qapp.screens())
    qtbot.addWidget(control)
    control.agent.store = store
    control.show()
    qtbot.mouseClick(control.settings_button, Qt.MouseButton.LeftButton)
    dialog = control._settings_dialog
    assert dialog is not None
    dialog.provider_dropdown.setCurrentText("ChatGPT")
    dialog.model.setCurrentText("gpt-user-model")
    dialog.key.setText("openai-key-test")
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
    assert control.agent.settings.provider is Provider.CHATGPT
    assert "ChatGPT" in control.send_button.text()
    assert "openai-key-test" not in path.read_text(encoding="utf-8")
    dialog.reject()
    transport = Transport(json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode())
    monkeypatch.setattr(providers, "build_opener", lambda *handlers: transport)
    control.prompt.setText("Halo")
    control._send_prompt()
    qtbot.waitUntil(lambda: not control.agent.busy, timeout=5000)
    assert control.answer.toPlainText() == "OK"
    assert transport.request.get_header("Authorization") == "Bearer openai-key-test"
    control.close()
    new_control = ControlWindow(AppConfig.default(), qapp.screens())
    qtbot.addWidget(new_control)
    assert new_control.agent.settings.provider is Provider.CHATGPT
    assert new_control.agent.settings.model == "gpt-user-model"
    new_control.close()


def test_cancel_wipes_unsaved_key(qtbot: Any, tmp_path: Path) -> None:
    dialog = AgentSettingsDialog(AgentSettings(), LocalStore(), path=tmp_path / "agent.json")
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.key.setText("secret")
    dialog.reject()
    assert dialog.key.text() == ""
    assert not (tmp_path / "agent.json").exists()


def test_invalid_settings_fail_closed_until_fixed(
    qtbot: Any, qapp: Any, tmp_path: Path, monkeypatch: Any
) -> None:
    from jarvis_hands.core.config import AppConfig
    from jarvis_hands.ui.overlay import ControlWindow

    path = tmp_path / "agent.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setattr("jarvis_hands.agent.settings.settings_path", lambda: path)
    control = ControlWindow(AppConfig.default(), qapp.screens())
    qtbot.addWidget(control)
    control.agent.store = LocalStore()
    control.show()
    assert not control.send_button.isEnabled()
    control.prompt.setText("private")
    control._send_prompt()
    assert not control.agent.busy
    control._open_settings()
    dialog = control._settings_dialog
    assert dialog is not None
    dialog._save()
    assert control.send_button.isEnabled()
    dialog.reject()
    control.close()


def test_system_keyring_methods_are_used(monkeypatch: Any) -> None:
    class NativeBackend:
        pass

    NativeBackend.__module__ = "keyring.backends.Windows"
    keys: dict[tuple[str, str], str] = {}
    monkeypatch.setattr("keyring.get_keyring", lambda: NativeBackend())
    monkeypatch.setattr("keyring.get_password", lambda service, user: keys.get((service, user)))
    monkeypatch.setattr(
        "keyring.set_password", lambda service, user, secret: keys.update({(service, user): secret})
    )
    monkeypatch.setattr("keyring.delete_password", lambda service, user: keys.pop((service, user)))
    store = CredentialStore()
    store.set(Provider.GEMINI, "test-secret")
    assert store.get(Provider.GEMINI) == "test-secret"
    assert store.get(Provider.CLAUDE) == ""
    store.delete(Provider.GEMINI)
    assert store.get(Provider.GEMINI) == ""
