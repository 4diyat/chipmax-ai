---
status: active
project: chipmax
type: reference
---
# Backing Up The Memory

Your memory is plain markdown files on one disk. That is the point of it, and it is also the risk: a dead machine takes the vault with it. There is no cloud copy unless you make one.

Good news: backup of a folder of text files is solved, free, and already partly in place.

## On a Mac: Time Machine, nothing to do

Time Machine covers your home folder automatically. Plug in an external drive once, turn it on, and the vault is covered like everything else.

## Windows: File History skips the home folder by default

Add the vault folder to File History's list once and it is covered:
Settings → Update & Security → Backup → More options → Add a folder.

## Anywhere: a private GitHub repo

The vault is text, so git handles it perfectly, and a **private** repo gives you versioned history plus an off-machine copy.

```
cd ~/chipmax-ai/ChipVault
git init -b main
gh repo create chipvault --private --source=. --push
```

Then, whenever you want a snapshot:

```
cd ~/chipmax-ai/ChipVault && git add -A && git commit -m "memory snapshot" && git push
```

**Ask ChipMax to do this for you** rather than doing it by hand. It can wire the commit and push into its own checkpoint routine, so every session that changes the vault also pushes it.

## What NOT to do

- **Do not put the vault inside a cloud-synced folder** (iCloud Drive, OneDrive, Dropbox, Google Drive). Two reasons, both real: syncing services sometimes replace local files with internet-only placeholders, and an agent that is told "the vault is at this path" then finds an empty stub with no error to explain it. A git repo is sync you control; a sync folder is sync someone else controls.
- **Do not store secrets in the vault.** No passwords, keys, or tokens, and no notes full of them. The vault is read by an AI, copied into backups, and pushed to git; anything in it should survive being read by a stranger.

## Restoring

Copy the vault back, run `python3 relink.py` from the agent folder so every path points at the new location, and reopen it in Obsidian. The vault is self-contained: every note is a file, and nothing lives in a database.
