"""Penjaga keamanan statis untuk modul runtime.

Memblokir pola yang melanggar prinsip produk: membuka port/server lokal, serta
eval/exec/pickle pada data dari luar. Tes ini sengaja hanya memindai modul
runtime, bukan tes.
"""

from __future__ import annotations

import ast
from pathlib import Path

import jarvis_hands

RUNTIME_ROOT = Path(jarvis_hands.__file__).parent

FORBIDDEN_MODULES = {
    "socket",
    "http.server",
    "socketserver",
    "flask",
    "fastapi",
    "uvicorn",
    "aiohttp",
    "tornado",
    "django",
    "subprocess",
    "multiprocessing",
    "ctypes",
    "PySide6.QtNetwork",
}
FORBIDDEN_QUALIFIERS = {
    "QTcpServer",
    "QLocalServer",
    "QTcpSocket",
    "QUdpSocket",
    "QLocalSocket",
    "QProcess",
}
FORBIDDEN_CALLS = {"eval", "exec", "__import__"}
FORBIDDEN_ATTRIBUTE_CALLS = {"system", "popen", "startfile", "fork", "spawn"}


def _runtime_files() -> list[Path]:
    return [
        path
        for path in RUNTIME_ROOT.rglob("*.py")
        if "tests" not in path.parts and "__pycache__" not in path.parts
    ]


def _module_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        return node.names[0].name
    return node.module or ""


def test_runtime_never_opens_network_ports() -> None:
    offenders: list[str] = []
    for path in _runtime_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                module = _module_name(node)
                if module in FORBIDDEN_MODULES or any(
                    module.startswith(f"{bad}.") for bad in FORBIDDEN_MODULES
                ):
                    offenders.append(f"{path.name}:{node.lineno} import {module}")
            if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_QUALIFIERS:
                offenders.append(f"{path.name}:{node.lineno} {node.attr}")
            if isinstance(node, ast.Name) and node.id in FORBIDDEN_QUALIFIERS:
                offenders.append(f"{path.name}:{node.lineno} {node.id}")
    assert not offenders, offenders


def test_runtime_never_uses_eval_exec_or_pickle() -> None:
    offenders: list[str] = []
    for path in _runtime_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                    offenders.append(f"{path.name}:{node.lineno} {func.id}()")
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr in {"loads", "load"}
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "pickle"
                ):
                    offenders.append(f"{path.name}:{node.lineno} pickle.{func.attr}")
                if isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_ATTRIBUTE_CALLS:
                    offenders.append(f"{path.name}:{node.lineno} .{func.attr}()")
            if isinstance(node, ast.Import | ast.ImportFrom) and _module_name(node) in {
                "pickle",
                "marshal",
                "shelve",
            }:
                offenders.append(f"{path.name}:{node.lineno} import {_module_name(node)}")
    assert not offenders, offenders


def test_runtime_does_not_write_camera_frames() -> None:
    offenders: list[str] = []
    for path in _runtime_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in {
                    "imwrite",
                    "VideoWriter",
                    "imencode",
                }:
                    offenders.append(f"{path.name}:{node.lineno} {func.attr}")
    assert not offenders, offenders
