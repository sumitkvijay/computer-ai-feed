#!/usr/bin/env python3
"""Prints ids of items 30+ days past reviewBy. With --move, git mv their sources to archive/items/."""
import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feedlib  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--today", type=date.fromisoformat, default=None)
    ap.add_argument("--move", action="store_true", help="move expired sources into archive/items/")
    a = ap.parse_args(argv)
    try:
        src = feedlib.load_sources(a.root)
    except ValueError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    ids = feedlib.prune(src, a.today or date.today())
    stems = {i["id"]: f for i, f in zip(src.items, src.files)}
    for iid in ids:
        if a.move:
            dest_dir = a.root / "archive" / "items"
            dest_dir.mkdir(parents=True, exist_ok=True)
            rel = f"content/items/{stems[iid]}.json"
            r = subprocess.run(["git", "mv", rel, "archive/items/"], cwd=a.root, capture_output=True)
            if r.returncode != 0:  # not a git checkout, or file untracked
                shutil.move(str(a.root / rel), str(dest_dir / f"{stems[iid]}.json"))
        print(iid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
