#!/usr/bin/env python3
"""One-off generator for tools/app-lessons.json ({courseId: [lessonId, ...]}).

Reads the app's bundled English course files and lists every lesson id per course.
Run it by hand whenever the app's course content changes:

    python3 -I tools/gen_app_lessons.py [--courses DIR] [--out FILE]
"""
import argparse
import json
import sys
from pathlib import Path

DEFAULT_COURSES = Path.home() / "MIIA/computer/app/src/main/assets/content/en/courses"
DEFAULT_OUT = Path(__file__).resolve().parent / "app-lessons.json"


def collect(courses_dir: Path) -> dict:
    out = {}
    for p in sorted(courses_dir.glob("*.json")):
        if p.stem.endswith("-questions"):
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        cid = data.get("id") or p.stem
        ids = [l["id"] for ch in data.get("chapters", []) for l in ch.get("lessons", []) if "id" in l]
        if ids:
            out[cid] = ids
    return dict(sorted(out.items()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--courses", type=Path, default=DEFAULT_COURSES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args(argv)
    if not a.courses.is_dir():
        print(f"ERROR courses directory not found: {a.courses}")
        return 1
    lessons = collect(a.courses)
    a.out.write_text(json.dumps(lessons, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {a.out}: {len(lessons)} courses, {sum(map(len, lessons.values()))} lessons")
    return 0


if __name__ == "__main__":
    sys.exit(main())
