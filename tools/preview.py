#!/usr/bin/env python3
"""Writes the PR preview (markdown) for items not yet in dist/. Usage: preview.py [--root DIR]"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feedlib  # noqa: E402

EMOJI = {"trend": "🔥", "howto": "🛠️", "news": "📰", "safety": "🛡️"}
LANG_LABEL = {"hi": "हिन्दी", "en": "English"}


def _published_ids(root: Path) -> set:
    ids = set()
    for lang in feedlib.LANGS:
        p = Path(root) / "dist" / "v1" / f"{lang}.json"
        try:
            ids |= {i["id"] for i in json.loads(p.read_text(encoding="utf-8")).get("items", [])}
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return ids


def _bullets(xs):
    return [f"- {x}" for x in xs]


def _lang_block(it, lang):
    d = it[lang]
    lines = [f"**{LANG_LABEL.get(lang, lang)}: {d.get('title', '')}**", "", f"_{d.get('hook', '')}_", ""]
    if d.get("steps"):
        lines += [f"{n}. {s}" for n, s in enumerate(d["steps"], 1)] + [""]
    if d.get("prompt"):
        lines += ["```", d["prompt"], "```", ""]
    if d.get("example"):
        lines += [f"Example: {d['example']}", ""]
    if d.get("privacyNote"):
        lines += [f"Privacy: {d['privacyNote']}", ""]
    if d.get("body"):
        lines += [d["body"], ""]
    if d.get("whyItMatters"):
        lines += [f"Why it matters: {d['whyItMatters']}", ""]
    if d.get("sourceName"):
        lines += [f"Source: {d['sourceName']}", ""]
    if d.get("whatsHappening"):
        lines += [d["whatsHappening"], ""]
    if d.get("howToSpot"):
        lines += ["How to spot it:"] + _bullets(d["howToSpot"]) + [""]
    if d.get("whatToDo"):
        lines += ["What to do:"] + _bullets(d["whatToDo"]) + [""]
    if d.get("helpline"):
        lines += [f"Helpline: {d['helpline']}", ""]
    return lines


def preview(src: feedlib.Sources, lang_order=("hi", "en")) -> str:
    published = _published_ids(src.root)
    new = sorted((i for i in src.items if i["id"] not in published),
                 key=lambda i: (i["publishAt"], i["id"]))
    if not new:
        return "## AI feed preview\n\nNo new items in this PR.\n"
    tools = {t["id"]: t["name"] for t in src.tools}
    out = [f"## AI feed preview ({len(new)} new items)", ""]
    for it in new:
        first = it[lang_order[0]]["title"]
        out += [f"### {EMOJI.get(it['type'], '')} {first}", "",
                f"`{it['id']}` | {it['type']} | shows {it['publishAt']}, review by {it['reviewBy']}", ""]
        if it.get("image"):
            out += [f"Image: `{it['image']}`", ""]
        if it.get("toolIds"):
            out += ["Tools: " + ", ".join(tools.get(t, t) for t in it["toolIds"]), ""]
        if it.get("sourceUrl"):
            out += [f"Source link: {it['sourceUrl']}", ""]
        for lang in lang_order:
            out += _lang_block(it, lang)
    return "\n".join(out).rstrip() + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(preview(feedlib.load_sources(a.root)))
    except (ValueError, KeyError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
