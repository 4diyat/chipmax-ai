#!/bin/sh
# Jalankan dari direktori mana pun; tidak memasang dependensi secara otomatis.
set -eu

PROJECT_DIR=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
cd "$PROJECT_DIR"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    printf '%s\n' \
        "Virtual environment belum tersedia. Jalankan perintah berikut di $PROJECT_DIR:" \
        '  python3.11 -m venv .venv' \
        '  .venv/bin/python -m pip install -r requirements.txt' >&2
    exit 1
fi

exec "$PYTHON" -m jarvis_hands "$@"
