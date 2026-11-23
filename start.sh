#!/bin/bash
# ChipMax — start the whole agent: the face, then the voice.
#
#   ./start.sh          the face and the voice together
#   ./start.sh voice    same thing (voice + face)
#
# Ctrl-C in this window stops everything. The face opens on the board; the
# gallery of all four faces stays at http://127.0.0.1:8790/.
#
# Two small additions over the stock launcher, both earned:
#   - paths are re-derived first, so a moved folder heals instead of starting
#     a stack with dead wires;
#   - the voice is skipped when this machine has no audio at all (a server,
#     a container), and the face still comes up. Better one honest line than
#     a traceback that reads like the whole install is broken.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if command -v python3 >/dev/null 2>&1; then
  python3 relink.py >/dev/null 2>&1 || true
fi

FACE="$(python3 - <<'PY' 2>/dev/null
import json
try:
    print(json.load(open("ai-visualizer/ai-visualizer.json")).get("face","board"))
except Exception:
    print("board")
PY
)"
[ -n "$FACE" ] || FACE=board

PIDS=()
cleanup() {
  trap - EXIT INT TERM
  for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null; done
  echo
  echo "ChipMax stopped."
}
trap cleanup EXIT INT TERM

FACE_STARTED=0
if [ -d ai-visualizer ]; then
  ( cd ai-visualizer && exec python3 server.py --no-open ) &
  PIDS+=($!)
  FACE_STARTED=1
  echo "  face:  up at http://127.0.0.1:8790/faces/$FACE/   (gallery at / )"
fi

# Can this machine actually hear and speak? Linux needs a display (the global
# hotkey) and PortAudio (the mic and speakers); every other platform says yes
# and lets the voice report its own problems.
VOICE_OK=1
if [ "$(uname -s)" = "Linux" ]; then
  [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || VOICE_OK=0
  python3 -c "import ctypes;ctypes.CDLL('libportaudio.so.2')" 2>/dev/null || VOICE_OK=0
fi

if [ -d backtalk ] && [ "$VOICE_OK" = 1 ]; then
  echo "  voice: starting (hold your talk key and speak; Ctrl-C stops everything)"
  ( cd backtalk && ./run.sh ) || echo "  voice: exited — see backtalk/TROUBLESHOOTING.md"
elif [ -d backtalk ]; then
  echo
  echo "  voice: not started on this machine — there is no microphone/speaker"
  echo "         device (or no desktop display) here. Everything else is wired;"
  echo "         run this on your own computer to talk to ChipMax."
  echo
  echo "         The face is running. Ctrl-C stops it."
  wait
else
  echo
  echo "  The face is up. Ctrl-C stops it."
  wait
fi
