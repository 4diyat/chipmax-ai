#!/usr/bin/env python3
"""Set the name ChipMax calls you. Fixes every place it is written, at once.

    python3 set-name.py Sam

The name lives in four places and nothing connects them, so they drift if you
edit one by hand. This writes all four, then reads each one back to prove it:

  1. backtalk/backtalk.json   "greeting"  ->  Hello Sam, what are we working on today?
  2. CLAUDE.md                the welcome line and the name note
  3. ChipVault/VAULT-INDEX.md "Who I Am"
  4. backtalk/backtalk.json   "name" stays ChipMax (that is the AGENT, not you)

If you leave the name out, it prints the current one.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
BOOT = REPO / "CLAUDE.md"
BT = REPO / "backtalk" / "backtalk.json"
IDX = REPO / "ChipVault" / "VAULT-INDEX.md"


def greeting_for(name):
    return f"Hello {name}, what are we working on today?"


def current_name():
    try:
        g = json.loads(BT.read_text())["greeting"]
    except Exception:
        return None
    m = re.match(r"Hello (.+?), what are we working on today\?", g)
    return m.group(1) if m else None


def set_name(name):
    wrote = []

    if BT.is_file():
        cfg = json.loads(BT.read_text())
        cfg["greeting"] = greeting_for(name)
        BT.write_text(json.dumps(cfg, indent=2) + "\n")
        got = json.loads(BT.read_text())["greeting"]
        assert got == greeting_for(name), got
        wrote.append(f"backtalk greeting  -> {got!r}")

    if BOOT.is_file():
        t = BOOT.read_text()
        # the welcome line
        t = re.sub(
            r"\*\*Welcome line:\*\* the first reply of every session is .*?\n",
            f'**Welcome line:** the first reply of every session is "{greeting_for(name)}" '
            f"\u2014 then wait for direction.\n",
            t, count=1, flags=re.S)
        # the standing note about not knowing the name
        t = re.sub(
            r"\*\*The name I go by is not written here yet\.\*\*.*?(?=\n## )",
            f"**My name is {name}.** Call me that. Use it. The greeting above already carries it, and "
            f"`backtalk/backtalk.json` speaks it at launch. Don't ask again, don't guess a "
            f"different one, and never substitute \"sir\" or \"boss\" in the spoken greeting.\n\n",
            t, count=1, flags=re.S)
        # me -> named me, in the one place it reads awkwardly
        BOOT.write_text(t)
        t2 = BOOT.read_text()
        assert name in t2 and "not written here yet" not in t2
        wrote.append

    if IDX.is_file():
        t = IDX.read_text()
        t = re.sub(
            r"## Who I Am\n.*?(?=\n## )",
            f"## Who I Am\n\nMy name is {name}. Everything else in this profile is mine to "
            f"write, and I fill it in as I go: what I do, what I'm building, the people I work "
            f"with, how I like to be talked to. ChipMax does not invent any of it — it asks, "
            f"and it writes down what I tell it.\n",
            t, count=1, flags=re.S)
        IDX.write_text(t)
        assert name in IDX.read_text()
        wrote.append(f"VAULT-INDEX        -> 'Who I Am' says {name}")
    return wrote


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        cur = current_name()
        print(f"current name: {cur}" if cur else
              "no name set. Try:  python3 set-name.py Sam")
        sys.exit(0)
    name = sys.argv[1].strip()
    for line in set_name(name):
        print("  ok:", line)
    print(f"\nChipMax will now say: \"{greeting_for(name)}\"")
    print("Take effect at the next launch of the voice line.")
