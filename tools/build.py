#!/usr/bin/env python3
"""Builds dist/v1/{hi,en}.json plus images. Usage: build.py [--out DIR] [--generated-at ISO]"""
import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feedlib  # noqa: E402


def main(argv=None) -> int:
    root_default = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=root_default)
    ap.add_argument("--out", type=Path, default=None, help="default: <root>/dist/v1")
    ap.add_argument("--generated-at", default=None)
    ap.add_argument("--today", type=date.fromisoformat, default=None, help="for pruning; default today")
    ap.add_argument("--no-urls", action="store_true")
    ap.add_argument("--min-stories", type=int, default=5)
    a = ap.parse_args(argv)
    out = a.out or a.root / "dist" / "v1"
    generated_at = a.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        src = feedlib.load_sources(a.root)
        lessons = feedlib.load_app_lessons(a.root)
    except ValueError as e:
        print(f"ERROR {e}")
        return 1
    errs = feedlib.validate(src, lessons, not a.no_urls, a.min_stories)
    if errs:
        for e in errs:
            print("ERROR", e)
        print("Validation failed; nothing written.")
        return 1

    pruned = feedlib.prune(src, a.today or date.today())
    if pruned:
        print("Leaving out (30+ days past reviewBy):", ", ".join(pruned))
    src = feedlib.without_items(src, pruned)
    for rid in feedlib.stale_week_ids(src):
        print(f"WARNING week.json references {rid!r}, which is archived or pruned; leaving it out")

    out.mkdir(parents=True, exist_ok=True)
    for lang in feedlib.LANGS:
        doc = feedlib.build(src, lang, generated_at)
        feedlib.copy_images(a.root, out, feedlib.referenced_images(doc))
        (out / f"{lang}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {out}/hi.json and en.json ({len(src.items)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
