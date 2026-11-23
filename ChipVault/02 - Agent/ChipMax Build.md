---
status: active
project: chipmax
type: guide
---
# ChipMax Build

How this agent was assembled, and where every piece physically lives. Updated by the agent itself whenever the setup changes.

## What I chose at setup

- **Identity:** door C — my own agent, named **ChipMax**. Not Jared's Jarvis; a fresh personality written during setup.
- **Pieces:** the stack — memory, voice, face. No hands (the webcam board), by choice.
- **Voice engine:** built-in (Kokoro), default voice `bm_lewis` — free, local, offline, noticeably computer-generated but no account needed.
- **Face:** `board`, the living circuit board.
- **Microphone:** push to talk, key `Home`. The mic is closed the rest of the time, so room audio can't trigger it.
- **Permissions:** `ask` — when the agent wants to do something real mid-conversation (write a file, run a command) it asks out loud and waits for a spoken yes. Flip it by saying "stop asking for permission" (then "confirm") inside a voice session, or change `permission_mode` in `backtalk/backtalk.json` and relaunch.

## Where everything lives

Everything is under `/home/user/chipmax-ai`:

```
chipmax-ai/
  CLAUDE.md            ← the boot config: who ChipMax is. Claude Code reads it
                          automatically when opened in this folder.
  ChipVault/           ← the memory vault (an Obsidian vault, plain markdown)
  backtalk/            ← the voice (backtalk.json holds its config)
  ai-visualizer/       ← the face (ai-visualizer.json holds its config)
  ai-memory-vault/     ← the memory system's wizard + templates (a toolbox, not memory)
  fullstack-agent/     ← the installer + start/update scripts
  install-chipmax.sh   ← portable setup for a fresh machine
  start.sh             ← one command: face + voice
```

**The folder rule:** ChipMax only wakes up as ChipMax when Claude Code opens in `chipmax-ai/`. Opened anywhere else, Claude is a stranger with none of this.

## The hardware half

This build happened in a cloud sandbox: no microphone, no speakers, no webcam, and no way to install the desktop apps. That means:

- **Done and real here:** the vault and every note, `CLAUDE.md`, every config, the wiring between the pieces, and the face (it runs and serves).
- **Must be finished on my own machine:** the microphone and speakers (backtalk's local speech models), Obsidian itself (the app that opens this vault), and the Desktop shortcuts.

`install-chipmax.sh` does that second half. It is safe to re-run: it skips what already exists and never overwrites anything I built.

## Related

- [[Agent Tools]]
