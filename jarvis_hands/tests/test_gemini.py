"""Kontrak Gemini REST diuji tanpa kredensial dan tanpa trafik nyata.

Transport tes menggantikan hanya respons HTTP; aplikasi tidak memiliki agen mock.
"""

from __future__ import annotations

import json
from http.client import HTTPMessage
from io import BytesIO
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest
from PySide6.QtWidgets import QApplication

from jarvis_hands.agent import gemini
from jarvis_hands.agent.bridge import AgentBridge
from jarvis_hands.agent.gemini import AgentError
from jarvis_hands.core.config import AppConfig
from jarvis_hands.core.state import Status
from jarvis_hands.ui.overlay import ControlWindow


class Reply:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def __enter__(self) -> Reply:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def read(self, limit: int) -> bytes:
        return self.data[:limit]


class Transport:
    def __init__(self, response: bytes) -> None:
        self.response = response
        self.request: Any = None
        self.timeout = 0.0

    def open(self, request: Any, *, timeout: float) -> Reply:
        self.request = request
        self.timeout = timeout
        return Reply(self.response)


def response(text: str) -> bytes:
    return json.dumps(
        {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}
    ).encode()


def test_real_request_contract_and_privacy(monkeypatch: Any) -> None:
    transport = Transport(response("Jawaban aktual"))
    monkeypatch.setattr(gemini, "build_opener", lambda *handlers: transport)
    assert gemini.generate("Halo", api_key="secret", model="gemini-3.8-flash") == "Jawaban aktual"
    req = transport.request
    assert (
        req.full_url
        == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"
    )
    assert "secret" not in req.full_url
    assert req.get_header("X-goog-api-key") == "secret"
    data = json.loads(req.data)
    assert data["contents"] == [{"role": "user", "parts": [{"text": "Halo"}]}]
    assert "tools" not in data
    assert transport.timeout == gemini.TIMEOUT_SECONDS


@pytest.mark.parametrize("value", ["", " ", "x" * (gemini.MAX_PROMPT_CHARS + 1)])
def test_invalid_prompt_rejected(value: str) -> None:
    with pytest.raises(AgentError):
        gemini.generate(value, api_key="key")


@pytest.mark.parametrize("model", ["../wrong", "foo/bar", "http://evil", ""])
def test_model_cannot_change_endpoint(model: str) -> None:
    with pytest.raises(AgentError):
        gemini.generate("test", api_key="key", model=model)


def test_key_required(monkeypatch: Any, qapp: QApplication) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    bridge = AgentBridge()
    errors: list[str] = []
    bridge.error.connect(errors.append)
    assert not bridge.submit("test")
    assert errors == ["GEMINI_API_KEY belum diatur."]
    assert not bridge.busy
    assert bridge.status == Status.IDLE


def test_error_codes_never_expose_key(monkeypatch: Any) -> None:
    class Broken:
        def open(self, request: Any, *, timeout: float) -> None:
            raise HTTPError(request.full_url + "secret", 403, "secret", HTTPMessage(), None)

    monkeypatch.setattr(gemini, "build_opener", lambda *handlers: Broken())
    with pytest.raises(AgentError) as error:
        gemini.generate("test", api_key="secret")
    assert "secret" not in str(error.value)

    class Offline:
        def open(self, request: Any, *, timeout: float) -> None:
            raise URLError("secret")

    monkeypatch.setattr(gemini, "build_opener", lambda *handlers: Offline())
    with pytest.raises(AgentError) as error:
        gemini.generate("test", api_key="secret")
    assert "secret" not in str(error.value)


def test_redirects_rejected() -> None:
    assert (
        gemini._NoRedirect().redirect_request(
            Request("https://example.com"), BytesIO(), 302, "", HTTPMessage(), "https://evil"
        )
        is None
    )


@pytest.mark.parametrize(
    "raw", [b"not json", b"{}", b'{"candidates": []}', b"x" * (gemini.MAX_RESPONSE_BYTES + 1)]
)
def test_invalid_response_rejected(monkeypatch: Any, raw: bytes) -> None:
    monkeypatch.setattr(gemini, "build_opener", lambda *handlers: Transport(raw))
    with pytest.raises(AgentError):
        gemini.generate("test", api_key="key")


def test_thoughts_and_blocked_response() -> None:
    candidate = {
        "content": {"parts": [{"text": "private", "thought": True}, {"text": "hasil"}]},
        "finishReason": "STOP",
    }
    assert gemini._response_text({"candidates": [candidate]}) == "hasil"
    candidate["finishReason"] = "SAFETY"
    with pytest.raises(AgentError):
        gemini._response_text({"candidates": [candidate]})


def test_bridge_thread_updates_ui(qtbot: Any, qapp: QApplication, monkeypatch: Any) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setattr(
        gemini, "build_opener", lambda *handlers: Transport(response("Jawaban uji"))
    )
    control = ControlWindow(AppConfig.default(), qapp.screens())
    qtbot.addWidget(control)
    control.show()
    statuses: list[Status] = []
    control.agent.status_changed.connect(statuses.append)
    control.prompt.setText("Pertanyaan")
    control._send_prompt()
    assert control.agent.busy
    assert control.overlay.ring.status is Status.THINKING
    qtbot.waitUntil(lambda: not control.agent.busy, timeout=5000)
    assert statuses == [Status.THINKING, Status.IDLE]
    assert control.answer.toPlainText() == "Jawaban uji"
    assert control.overlay.response_text.toPlainText() == "Jawaban uji"
    assert control.overlay.response_panel.isVisible()
    assert control.overlay.orb.status is Status.IDLE
    control.close()


def test_single_flight_and_graceful_close(qtbot: Any, qapp: QApplication, monkeypatch: Any) -> None:
    import threading

    started, release = threading.Event(), threading.Event()

    class BlockingTransport(Transport):
        def open(self, request: Any, *, timeout: float) -> Reply:
            started.set()
            if not release.wait(3):
                raise URLError("timeout")
            return super().open(request, timeout=timeout)

    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setattr(gemini, "build_opener", lambda *handlers: BlockingTransport(response("ok")))
    control = ControlWindow(AppConfig.default(), qapp.screens())
    qtbot.addWidget(control)
    control.show()
    assert control.agent.submit("pertanyaan")
    qtbot.waitUntil(started.is_set, timeout=1000)
    assert not control.agent.submit("permintaan kedua")
    control.close()
    assert control.isVisible()
    assert "Menunggu" in control.agent_status.text()
    release.set()
    qtbot.waitUntil(lambda: not control.isVisible(), timeout=5000)
    assert not control.overlay.isVisible()


def test_max_token_response_is_marked() -> None:
    payload = {
        "candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "parsial"}]}}]
    }
    assert "terpotong" in gemini._response_text(payload)
