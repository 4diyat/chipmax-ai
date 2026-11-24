"""Jalankan pytest dengan batas waktu dan diagnostik yang terlihat di CI Windows."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_SECONDS = 300
MAX_ANNOTATION_CHARS = 25000


def main() -> int:
    command = [
        sys.executable,
        "-u",
        "-m",
        "pytest",
        "-vv",
        "--color=no",
        "-o",
        "faulthandler_timeout=60",
    ]
    with tempfile.TemporaryDirectory(prefix="jarvis-pytest-") as tmp:
        log_path = Path(tmp) / "pytest.log"
        timed_out = False
        with log_path.open("wb") as log:
            try:
                completed = subprocess.run(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=TIMEOUT_SECONDS,
                    check=False,
                )
                code = completed.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                code = 1
        output = log_path.read_text(encoding="utf-8", errors="replace")
    print(output, end="", flush=True)
    if code:
        reason = (
            f"pytest exceeded {TIMEOUT_SECONDS} seconds" if timed_out else f"pytest exited {code}"
        )
        # GitHub annotations are accessible through the checks API even when job logs
        # are unavailable. Escape workflow command data and keep it below its limit.
        detail = output[-MAX_ANNOTATION_CHARS:]
        message = f"{reason}\nLast pytest output:\n{detail}"
        message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=Windows pytest diagnostics::{message}", flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
