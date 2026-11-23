# ChipMax

An AI agent with a full stack: **memory, voice, and face.** Built from the
open-source [Jared Rhodenizer](https://github.com/jaredrhod) stack, assembled
and wired.

```
CLAUDE.md          who ChipMax is. Claude Code loads this automatically.
ChipVault/         the memory: an Obsidian vault of plain markdown notes
backtalk/          the voice: hold Home, speak, get a spoken answer
ai-visualizer/     the face: the living circuit board, driven by the voice
fullstack-agent/   the installer and launcher (start/update scripts)
ai-memory-vault/   the memory system's wizard and templates (a toolbox)
relink.py          re-wire every path after the folder moves
set-name.py        set the name ChipMax calls you, everywhere at once
start.sh           one command: face + voice
install-chipmax.sh portable setup for a fresh machine
audio/             ChipMax's first hello, spoken
```

## Start it

```
./start.sh
```

The face opens on the board and the voice comes up behind it. Ctrl-C stops both.
The gallery of all four faces stays at <http://127.0.0.1:8790/>.

## First thing to do

```
python3 set-name.py YourName
```

ChipMax's greeting is "Hello, what are we working on today?" until it knows
your name. That one command writes it into the boot config, the spoken
greeting, and the vault profile at once, and prints what it changed.

## The rule that matters

ChipMax only wakes up as ChipMax when Claude Code opens **in this folder**.
Opened anywhere else, Claude is a stranger with none of this memory.

## Moved the folder?

```
python3 relink.py
```

Every piece is wired by absolute path. That script rewrites them all to the
current location and prints what it changed. `--check` reports without writing.

## Settings

| What | Where |
|---|---|
| Who ChipMax is | `CLAUDE.md` |
| Voice, key, mic mode, permissions, greeting | `backtalk/backtalk.json` |
| Face, agent name on the chip | `ai-visualizer/ai-visualizer.json` |
| Memory | `ChipVault/` (open it in Obsidian) |

## If something breaks

Ask ChipMax. Each piece ships a `TROUBLESHOOTING.md` written for the agent to
read; cross-piece problems start at `fullstack-agent/TROUBLESHOOTING.md`.
Fixing it is the agent's job, not yours.

## Credit

Memory, voice, face, and installer by Jared Rhodenizer, AGPL-3.0 (the memory
templates are CC BY-SA 4.0). Everything here is free and open.
