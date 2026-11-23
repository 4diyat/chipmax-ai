"""Endpoint API nyata untuk Gemini, Claude, OpenAI, dan Ollama."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from jarvis_hands.agent import gemini
from jarvis_hands.agent.gemini import (
    MAX_PROMPT_CHARS,
    MAX_RESPONSE_BYTES,
    TIMEOUT_SECONDS,
    AgentError,
)
from jarvis_hands.agent.settings import AgentSettings, Provider, validate_model, validate_ollama_url


def generate(prompt: str, *, settings: AgentSettings, key: str) -> str:
    """Kirim teks ke penyedia terpilih. Tidak memakai riwayat, tools atau gambar."""
    prompt = prompt.strip()
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise AgentError(f"Teks harus berisi 1–{MAX_PROMPT_CHARS} karakter.")
    provider = settings.provider
    model = validate_model(settings.model, provider)
    if provider is Provider.GEMINI:
        return gemini.generate(prompt, api_key=key, model=model)
    if provider is not Provider.OLLAMA and not key:
        raise AgentError("API key belum diatur untuk penyedia ini.")
    headers = {"Content-Type": "application/json"}
    if provider is Provider.CLAUDE:
        url = "https://api.anthropic.com/v1/messages"
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
        payload = {
            "model": model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
    elif provider is Provider.CHATGPT:
        url = "https://api.openai.com/v1/chat/completions"
        headers["Authorization"] = f"Bearer {key}"
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    else:
        base = validate_ollama_url(settings.ollama_url)
        if key and not base.startswith("https://"):
            raise AgentError("API key Ollama hanya dapat dikirim melalui HTTPS.")
        url = base + "/api/chat"
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        opener = build_opener(ProxyHandler({}), gemini._NoRedirect())
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise AgentError("Akses ditolak; periksa API key dan izin model.") from None
        if exc.code == 429:
            raise AgentError("Kuota habis atau terlalu banyak permintaan.") from None
        raise AgentError(f"Permintaan agen gagal (HTTP {exc.code}).") from None
    except (URLError, OSError, TimeoutError, ValueError):
        raise AgentError("Penyedia tidak dapat dihubungi; periksa koneksi dan alamat.") from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise AgentError("Respons agen melampaui batas ukuran.")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise AgentError("Respons agen tidak dapat dibaca.") from None
    return parse_response(provider, data)


def parse_response(provider: Provider, data: object) -> str:
    if not isinstance(data, dict):
        raise AgentError("Respons agen tidak valid.")
    text = ""
    truncated = False
    if provider is Provider.CLAUDE:
        content = data.get("content")
        if isinstance(content, list):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            )
        truncated = data.get("stop_reason") == "max_tokens"
    elif provider is Provider.CHATGPT:
        choices = data.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            choice = choices[0]
            message = choice.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                text = message["content"]
            truncated = choice.get("finish_reason") == "length"
    elif provider is Provider.OLLAMA:
        message = data.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            text = message["content"]
        truncated = data.get("done_reason") == "length"
    if not text.strip():
        raise AgentError("Penyedia tidak memberikan teks jawaban.")
    return text.strip() + ("\n\n[Jawaban terpotong oleh batas token.]" if truncated else "")
