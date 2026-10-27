#!/usr/bin/env python3
"""Add MIDI files to this repo's Songs folder, rebuild index.json, commit, and push.

Place this file and Publish Songs.bat in the root of a cloned song repository.
Then drag one or more .mid/.midi files onto Publish Songs.bat.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SONGS = ROOT / "Songs"


def run(*args: str, capture: bool = False) -> str:
    result = subprocess.run(
        args,
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if result.returncode:
        if capture and result.stdout:
            print(result.stdout)
        raise RuntimeError(f"Command failed: {' '.join(args)}")
    return result.stdout.strip() if capture and result.stdout else ""


def midi_files(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            found.extend(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in (".mid", ".midi"))
        elif path.is_file() and path.suffix.lower() in (".mid", ".midi"):
            found.append(path)
        else:
            print(f"Skipping (not a MIDI file or folder): {path}")
    return found


def destination_for(source: Path) -> Path:
    target = SONGS / source.name
    if not target.exists() or target.read_bytes() == source.read_bytes():
        return target
    stem, suffix = source.stem, source.suffix
    number = 2
    while True:
        candidate = SONGS / f"{stem} ({number}){suffix}"
        if not candidate.exists() or candidate.read_bytes() == source.read_bytes():
            return candidate
        number += 1


def build_index() -> int:
    index: dict[str, list[str]] = {}
    for entry in sorted(SONGS.iterdir(), key=lambda p: p.name.lower()):
        if entry.is_dir():
            files = sorted((p.name for p in entry.iterdir() if p.is_file() and p.suffix.lower() in (".mid", ".midi")), key=str.lower)
            if files:
                index[entry.name] = files
    loose = sorted((p.name for p in SONGS.iterdir() if p.is_file() and p.suffix.lower() in (".mid", ".midi")), key=str.lower)
    if loose:
        index["Misc"] = loose
    (ROOT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return sum(map(len, index.values()))


def main() -> int:
    if not (ROOT / ".git").exists():
        print("This tool must be inside the root of a cloned GitHub repository.")
        print("Clone your song repo once, then put this file and Publish Songs.bat beside its .git folder.")
        return 1
    if not SONGS.is_dir():
        print("Couldn't find the Songs folder beside this tool.")
        return 1
    if not run("git", "remote", "get-url", "origin", capture=True):
        print("This repo has no 'origin' remote configured.")
        return 1

    sources = midi_files(sys.argv[1:])
    if not sources:
        print("Drag one or more .mid/.midi files (or a folder of MIDI files) onto Publish Songs.bat.")
        return 1

    copied = 0
    for source in sources:
        target = destination_for(source)
        if target.exists() and target.read_bytes() == source.read_bytes():
            print(f"Already present: {target.name}")
            continue
        target.write_bytes(source.read_bytes())
        print(f"Added: {target.name}")
        copied += 1

    total = build_index()
    print(f"Index updated ({total} MIDI files total).")
    run("git", "add", "--", "Songs", "index.json")
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode
    if staged == 0:
        print("No changes to publish.")
        return 0
    message = f"Add {copied} MIDI file{'s' if copied != 1 else ''}"
    run("git", "commit", "-m", message)
    branch = run("git", "branch", "--show-current", capture=True)
    if not branch:
        print("Commit created, but this checkout has no current branch; push it manually.")
        return 1
    run("git", "push", "origin", branch)
    print("Published. The website index may take a short moment to refresh.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as error:
        print(f"\nPublish failed: {error}")
        print("Your MIDI files and generated index are still in the local repo; resolve the Git error and run again.")
        raise SystemExit(1)
