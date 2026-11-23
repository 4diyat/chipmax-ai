#!/bin/bash
# ChipMax — portable setup for a fresh machine.
#
# You copy this whole folder to the new machine, then run this once. It is
# safe to re-run: every step skips what already exists, and it never
# overwrites anything you wrote. On Windows, run the equivalents from this
# file in PowerShell (each step names them); this script is the Mac/Linux lane.
#
#   ./install-chipmax.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE" || exit 1
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

say()  { printf '\n== %s\n' "$*"; }
ok()   { printf '   ok: %s\n' "$*"; }
warn() { printf '   !  %s\n' "$*"; }
FAILS=0

# ---------------------------------------------------------------- 1. paths
say "1/7  Re-wiring every path to this folder"
if command -v python3 >/dev/null 2>&1; then
  python3 relink.py || warn "relink reported a problem"
elif command -v python >/dev/null 2>&1; then
  python relink.py || warn "relink reported a problem"
else
  warn "Python 3 not found. Install it first (macOS: brew install python; Windows: winget install Python.Python.3.12), then re-run."
  exit 1
fi

# ------------------------------------------------------------- 2. the tools
say "2/7  Checking the four tool folders"
for d in fullstack-agent ai-memory-vault backtalk ai-visualizer; do
  if [ -d "$d" ]; then
    ok "$d"
  elif command -v git >/dev/null 2>&1; then
    warn "$d missing - cloning it"
    git clone "https://github.com/jaredrhod/$d.git" "$d" && ok "$d" || FAILS=1
  else
    warn "$d missing and git is not installed"
    FAILS=1
  fi
done

# ------------------------------------------------------------ 3. the voice
say "3/7  The voice (backtalk): Python environment, engines, ~1GB of models"
if [ ! -f backtalk/backtalk.json ]; then
  cp backtalk/backtalk.json.example backtalk/backtalk.json
  python3 relink.py >/dev/null 2>&1   # put the real paths back
  warn "backtalk.json was missing, so a fresh one was written and re-wired"
fi
if [ -f backtalk/install.sh ]; then
  ( cd backtalk && ./install.sh ) || { warn "backtalk installer reported a problem"; FAILS=1; }
fi

# ------------------------------------------------------------- 4. Obsidian
say "4/7  Obsidian, the app your memory lives in"
case "$(uname -s)" in
  Darwin)
    if [ -d /Applications/Obsidian.app ] || [ -d "$HOME/Applications/Obsidian.app" ]; then
      ok "Obsidian already installed"
    elif command -v brew >/dev/null 2>&1; then
      printf '   Install Obsidian now with Homebrew? [Y/n] '
      read -r a
      [ "${a:-Y}" = "n" ] || brew install --cask obsidian || FAILS=1
    else
      warn "Homebrew not found. Install Obsidian from https://obsidian.md, then re-run."
    fi ;;
  Linux)
    ok "install Obsidian from https://obsidian.md (AppImage) or: snap install obsidian --classic" ;;
  *)
    warn "Windows: winget install --id Obsidian.Obsidian --silent" ;;
esac

say "     Registering the vault so Obsidian opens into it"
python3 - "$HERE/ChipVault" <<'PY' || FAILS=1
import json, os, secrets, shutil, sys, time
from pathlib import Path
vault = str(Path(sys.argv[1]).resolve())
cands = [Path.home()/".config/obsidian/obsidian.json",
         Path.home()/"Library/Application Support/obsidian/obsidian.json"]
if os.environ.get("APPDATA"):
    cands.append(Path(os.environ["APPDATA"])/"obsidian"/"obsidian.json")
reg = next((c for c in cands if c.exists()), cands[0])
reg.parent.mkdir(parents=True, exist_ok=True)
if reg.exists():
    shutil.copy2(reg, str(reg) + ".bak")
    try:
        data = json.loads(reg.read_text() or "{}")
    except ValueError:
        data = {}
else:
    data = {}
before = dict(data.get("vaults") or {})
if any(v.get("path") == vault for v in before.values()):
    print("   ok: vault already registered at", vault); sys.exit(0)
vaults = dict(before)
vaults[secrets.token_hex(8)] = {"path": vault, "ts": int(time.time()*1000), "open": True}
data["vaults"] = vaults
reg.write_text(json.dumps(data, indent=2))
back = json.loads(reg.read_text())            # verify by walking the paths
assert any(v["path"] == vault and os.path.isdir(v["path"]) for v in back["vaults"].values())
assert set(before) <= set(back["vaults"]), "a previous vault was lost"
print("   ok: vault registered at", vault)
PY

# --------------------------------------------------------- 5. the shortcuts
say "5/7  Desktop shortcuts"
DESK="$HOME/Desktop"
mkdir -p "$DESK"
mac_icon() {
  f="$DESK/$1.command"
  { echo '#!/bin/bash'
    echo 'export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"'
    echo "$2"; } > "$f"
  chmod +x "$f"
  ok "$1"
}
case "$(uname -s)" in
  Darwin)
    mac_icon "Chat with ChipMax"   "cd \"$HERE\" && claude"
    mac_icon "Talk to ChipMax"     "cd \"$HERE\" && ./start.sh voice"
    mac_icon "Update ChipMax"      "cd \"$HERE/fullstack-agent\" && ./update.sh"
    warn "the first double-click of a .command may ask permission: that is macOS being protective, click Open" ;;
  MINGW*|MSYS*|CYGWIN*)
    W="$(cygpath -w "$HERE" 2>/dev/null || echo "$HERE")"
    printf '@echo off\r\ncd /d "%s"\r\nclaude\r\npause\r\n' "$W" > "$DESK/Chat with ChipMax.bat"
    printf '@echo off\r\ncd /d "%s"\r\nbash start.sh voice\r\npause\r\n' "$W" > "$DESK/Talk to ChipMax.bat"
    ok "Chat with ChipMax.bat"
    ok "Talk to ChipMax.bat"
    warn "Windows: no Update shortcut on purpose. Say \"update everything and tell me what changed\" in a chat instead." ;;
  *)
    ok "skipped (Linux): run ./start.sh from this folder, or make your own launcher" ;;
esac

# ---------------------------------------------------------------- 6. verify
say "6/7  Verifying the wiring"
python3 - <<'PY' || FAILS=1
import json, os, sys
here = os.getcwd()
bt = json.load(open("backtalk/backtalk.json"))
av = json.load(open("ai-visualizer/ai-visualizer.json"))
checks = [
    ("backtalk.agent_dir points here", bt.get("agent_dir") == here),
    ("vault is in extra_dirs", any(d.endswith("ChipVault") for d in bt.get("extra_dirs", []))),
    ("greeting is set", bool(bt.get("greeting"))),
    ("face bus_dir points at backtalk", av.get("bus_dir") == os.path.join(here, "backtalk")),
    ("face name is ChipMax", av.get("name") == "ChipMax"),
    ("CLAUDE.md present", os.path.isfile("CLAUDE.md")),
    ("vault present", os.path.isdir("ChipVault")),
]
good = True
for label, fine in checks:
    print(("   ok: " if fine else "   !  FAILED: ") + label)
    good = good and fine
sys.exit(0 if good else 1)
PY

# -------------------------------------------------------------- 7. the test
say "7/7  Done"
cat <<EOT

   Two things left, both one step:

     ./start.sh          the face and the voice together
                         (the "Talk to ChipMax" shortcut runs this)
     open Obsidian       and pick the "ChipVault" vault from its list

   Your memory:      $HERE/ChipVault
   Your agent:       $HERE/CLAUDE.md

   If anything fails, do not debug it alone. Open Claude Code in this folder
   and say "something is broken: <what you saw>". Fixing it is ChipMax's job.

EOT
if [ "$FAILS" = 0 ]; then ok "all checks passed"; else warn "one or more steps above need attention"; fi
