"""Plugin pytest: laporkan tes Windows yang gagal atau terhenti melalui CI."""

from __future__ import annotations

import os
import sys
import threading
import traceback
from typing import Any

import pytest

TEST_TIMEOUT_SECONDS = 60
MAX_ANNOTATION_CHARS = 25000


def _annotation(title: str, detail: str) -> None:
    message = detail[-MAX_ANNOTATION_CHARS:]
    message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title={title}::{message}", file=sys.__stdout__, flush=True)


def _timeout(nodeid: str) -> None:
    stacks = []
    for thread_id, frame in sys._current_frames().items():
        stacks.append(f"Thread {thread_id}:\n{''.join(traceback.format_stack(frame))}")
    _annotation(
        "Windows pytest timeout",
        f"Test exceeded {TEST_TIMEOUT_SECONDS} seconds: {nodeid}\n" + "\n".join(stacks),
    )
    # pytest cannot safely resume after a blocked test. Force a nonzero exit even
    # when a Qt worker or modal dialog would otherwise keep the interpreter alive.
    os._exit(1)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: Any) -> Any:
    timer = threading.Timer(TEST_TIMEOUT_SECONDS, _timeout, args=(item.nodeid,))
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any) -> Any:
    outcome = yield
    report = outcome.get_result()
    if report.failed:
        _annotation("Windows pytest failure", f"{report.nodeid} ({report.when})\n{report.longrepr}")
