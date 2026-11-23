#!/usr/bin/env python3
# ChipMax — rewrite every config path to wherever this folder currently lives.
#
# Every piece is wired by absolute paths, which is what makes them fast and
# dumb and reliable, and also what breaks the day the folder moves. This
# script is the one place that knows how to re-derive them. It is safe to run
# any time: it only writes when a value is actually wrong, it keeps every
# other key in each file, and it prints what it changed.
#
#   python3 relink.py            fix and report
#   python3 relink.py --check    report only, change nothing (exit 1 if drifted)
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
VAULT = REPO / "ChipVault"
CHECK_ONLY = "--check" in sys.argv
# any absolute path ending in /ChipVault, on either separator style
PATH_TAIL = re.compile(r"(?:[A-Za-z]:)?[/\\][^\s`'\"]*ChipVault")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, data):
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(p)


def want_extra(cfg):
    """The vault, kept in extra_dirs, without dropping anything else added."""
    dirs = [str(VAULT)]
    for d in cfg.get("extra_dirs") or []:
        if Path(d).name != "ChipVault":
            dirs.append(d)
    return dirs


def relink():
    changed = []
    problems = []

    bt = REPO / "backtalk" / "backtalk.json"
    if bt.is_file():
        cfg = load(bt)
        if cfg.get("agent_dir") != str(REPO):
            cfg["agent_dir"] = str(REPO)
            changed.append(f"backtalk.agent_dir -> {REPO}")
        if cfg.get("extra_dirs") != want_extra(cfg):
            cfg["extra_dirs"] = want_extra(cfg)
            changed.append(f"backtalk.extra_dirs -> {VAULT}")
        # One direction only. bus_dir in the visualizer carries the wire.
        if cfg.get("signals_dir"):
            cfg["signals_dir"] = ""
            changed.append("backtalk.signals_dir cleared (the wire runs one way)")
        if changed and not CHECK_ONLY:
            save(bt, cfg)

    av = REPO / "ai-visualizer" / "ai-visualizer.json"
    if av.is_file():
        cfg = load(av)
        if cfg.get("bus_dir") != str(REPO / "backtalk"):
            cfg["bus_dir"] = str(REPO / "backtalk")
            changed.append(f"ai-visualizer.bus_dir -> {REPO / 'backtalk'}")
            if not CHECK_ONLY:
                save(av, cfg)

    bh = REPO / "barehands" / "barehands.json"
    if bh.is_file():
        cfg = load(bh)
        changed.append("barehands config present (its paths are relative; nothing to fix)")

    # The vault path is written into two notes as prose. Keep those honest.
    vpath = str(VAULT)
    idx = VAULT / "VAULT-INDEX.md"
    if idx.is_file():
        text = idx.read_text(encoding="utf-8")
        seen = [ln for ln in text.splitlines() if ln.startswith("This vault lives at `")]
        if not seen:
            problems.append("VAULT-INDEX.md has no 'This vault lives at' line")
        elif seen[0] != f"This vault lives at `{vpath}`.":
            if not CHECK_ONLY:
                new = text.replace(seen[0], f"This vault lives at `{vpath}`.")
                idx.write_text(new, encoding="utf-8")
            changed.append(f"VAULT-INDEX vault location -> {vpath}")

    # CLAUDE.md carries the vault path twice: once in the sentence that sends
    # the AI to it, once in the bare code block. Rewrite any absolute path that
    # still ends in /ChipVault, then verify the right one is actually there.
    boot = REPO / "CLAUDE.md"
    if boot.is_file():
        text = boot.read_text(encoding="utf-8")
        stale = set(PATH_TAIL.findall(text)) - {vpath}
        if stale and not CHECK_ONLY:
            for old in stale:
                text = text.replace(old, vpath)
            boot.write_text(text, encoding="utf-8")
        if stale:
            changed.append(f"CLAUDE.md vault path -> {vpath}")
        if vpath not in text:
            problems.append(f"CLAUDE.md does not mention the vault path {vpath}")

    if not VAULT.is_dir():
        problems.append(f"vault folder missing: {VAULT}")

    return changed, problems


if __name__ == "__main__":
    changes, problems = relink()
    for c in changes:
        print(("would fix: " if CHECK_ONLY else "fixed: ") + c)
    for p in problems:
        print("PROBLEM: " + p)
    if not changes and not problems:
        print(f"all paths correct: {REPO}")
    if problems:
        sys.exit(1)
    if CHECK_ONLY and changes:
        sys.exit(1)
