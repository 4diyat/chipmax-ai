---
status: active
project: chipmax
type: reference
---
# Agent Tools

The three pieces and how they connect. Read this before touching any config: the wiring is small, path-based, and easy to break by "fixing" the wrong side.

## The pieces

| Piece | What it is | Config file |
|---|---|---|
| **Vault** (`ChipVault/`) | The memory. Plain markdown files any AI reads and writes. Obsidian is the app for looking at it. | none — it is just files |
| **backtalk** (`backtalk/`) | The voice. Local speech-to-text in, local text-to-speech out, driving a live Claude session in the home folder. | `backtalk/backtalk.json` |
| **ai-visualizer** (`ai-visualizer/`) | The face. A browser page that animates from the voice's status files. | `ai-visualizer/ai-visualizer.json` |

## How they connect

The voice writes little status notes into its own folder; the face reads them. That is the whole connection.

- `backtalk/.voice_state` — one word: `idle`, `listening`, `thinking`, `speaking`
- `backtalk/.voice_waveform` — the loudness snapshot the face pulses to
- `backtalk/.voice_alert` — exists when the agent needs attention

The wire is one config line, `bus_dir` in `ai-visualizer.json`, pointing at the backtalk folder. The reverse direction exists (`signals_dir` in `backtalk.json` pointing at the visualizer), but **one direction only, never both.**

## Current wiring

- `backtalk.json` → `agent_dir`: `/home/user/chipmax-ai` · `name`: `ChipMax` · `extra_dirs`: the vault · `permission_mode`: `ask` · `mic_mode`: `ptt` · `ptt_key`: `home` · `voice`: `bm_lewis`
- `ai-visualizer.json` → `name`: `ChipMax` · `face`: `board` · `bus_dir`: `/home/user/chipmax-ai/backtalk`

## Starting it

```
./start.sh          the face and the voice together
./start.sh voice    voice and face (same as above)
./fullstack-agent/start.sh    the same thing, from the installer
```

Ctrl-C in that window stops everything. The face opens at `http://127.0.0.1:8790/`; the gallery lives at the root if I want to switch faces.

## Keys and phrases

- **Home** (hold) — talk. Release to send.
- **F** — fullscreen on the face. **Space** — the board's cinematic flythrough.
- **"goodbye ChipMax"** — hang up the voice line.
- Voice console phrases, spoken alone: "clear the session", "compact the session", "switch to the deep model", "usage report", "go hands free", "push to talk mode", "stop asking for permission", "start asking again".

## Related

- [[ChipMax Build]]
