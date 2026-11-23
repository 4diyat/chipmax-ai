"""Klien Gemini REST teks-saja. Tidak ada server lokal atau fallback tiruan.

Setiap permintaan hanya membawa teks yang diketik pengguna. Kamera, landmark,
isi memori dan percakapan sebelumnya tidak disertakan. API key dikirim lewat
header, bukan URL; redirect dan proxy lingkungan dinonaktifkan agar key tidak
terkirim ke host lain. Kesalahan jaringan tidak menampilkan isi respons/key.
"""

from __future__ import annotations

import json
import os
import re
from http.client import HTTPMessage
from typing import IO
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

DEFAULT_MODEL = "gemini-3.8-flash"
MAX_PROMPT_CHARS = 12000
MAX_RESPONSE_BYTES = 1024 * 1024
TIMEOUT_SECONDS = 30.0
_MODEL_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$")


class AgentError(Exception):
    """Kesalahan aman untuk ditampilkan, tanpa key atau isi respons server."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: IO[bytes], code: int, msg: str, headers: HTTPMessage, newurl: str
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


def _response_text(data: object) -> str:
    if not isinstance(data, dict):
        raise AgentError("Respons Gemini tidak valid.")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise AgentError("Gemini tidak memberikan jawaban; permintaan mungkin diblokir.")
    candidate = candidates[0]
    if candidate.get("finishReason") not in (None, "STOP", "MAX_TOKENS"):
        raise AgentError("Jawaban Gemini diblokir atau tidak dapat diselesaikan.")
    content = candidate.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("parts"), list):
        raise AgentError("Gemini tidak memberikan teks jawaban.")
    texts = [
        part["text"]
        for part in content["parts"]
        if isinstance(part, dict) and isinstance(part.get("text"), str) and not part.get("thought")
    ]
    text = "".join(texts).strip()
    if not text:
        raise AgentError("Gemini tidak memberikan teks jawaban.")
    if candidate.get("finishReason") == "MAX_TOKENS":
        text += "\n\n[Jawaban terpotong oleh batas token.]"
    return text


def generate(prompt: str, *, api_key: str, model: str = DEFAULT_MODEL) -> str:
    """Kirim satu permintaan teks ke Gemini dan kembalikan respons teks.

    Tidak mengirim riwayat, menjalankan tool, atau mengikuti instruksi sebagai
    perintah lokal. Memanggil fungsi ini melakukan akses HTTPS keluar berbayar
    atau tunduk pada kuota/provisi penyedia.
    """
    prompt = prompt.strip()
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise AgentError(f"Teks harus berisi 1–{MAX_PROMPT_CHARS} karakter.")
    if not api_key.strip():
        raise AgentError("GEMINI_API_KEY belum diatur.")
    if not _MODEL_RE.fullmatch(model):
        raise AgentError("Nama model Gemini tidak valid.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = json.dumps(
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 2048},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        opener = build_opener(ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise AgentError("Akses Gemini ditolak; periksa key, izin, dan model.") from None
        if exc.code == 429:
            raise AgentError("Kuota Gemini habis atau terlalu banyak permintaan.") from None
        raise AgentError(f"Permintaan Gemini gagal (HTTP {exc.code}).") from None
    except (URLError, OSError, TimeoutError, ValueError):
        raise AgentError(
            "Gemini tidak dapat dihubungi; periksa koneksi dan akses jaringan."
        ) from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise AgentError("Respons Gemini melampaui batas ukuran.")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise AgentError("Respons Gemini tidak dapat dibaca.") from None
    return _response_text(data)


def configured_model() -> str:
    """Model opsional dari environment; URL/endpoint tidak dapat diubah."""
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip()
