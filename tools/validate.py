#!/usr/bin/env python3
"""Validates the feed sources. Usage: validate.py [--no-urls] [--root DIR] [--min-stories N]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feedlib  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-urls", action="store_true", help="skip the URL reachability check")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--min-stories", type=int, default=5)
    a = ap.parse_args(argv)
    try:
        src = feedlib.load_sources(a.root)
        lessons = feedlib.load_app_lessons(a.root)
    except ValueError as e:
        print(f"ERROR {e}")
        return 1
    errs = feedlib.validate(src, lessons, not a.no_urls, a.min_stories)
    for e in errs:
        print("ERROR", e)
    print(f"{len(src.items)} items, {len(errs)} errors")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
