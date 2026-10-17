"""Shared logic for the AI feed: load sources, validate, build, prune."""
import copy
import json
import re
import shutil
import time
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

SCHEMA_VERSION = 1
MIN_APP_VERSION_CODE = 1
LANGS = ("hi", "en")
TYPES = ("trend", "howto", "news", "safety")
PRICES = ("free", "freemium")
LOGINS = ("none", "google", "phone")
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PRUNE_AFTER_DAYS = 30
DEFAULT_HELPLINE = "1930 / cybercrime.gov.in"
MAX_IMAGE_BYTES = 40 * 1024
MAX_TASKS = 8

SHARED_FIELDS = ("id", "type", "publishAt", "reviewBy", "tags", "image", "minutes",
                 "toolIds", "relatedLesson", "sourceUrl")
LANG_FIELDS = ("title", "hook", "imageAlt", "steps", "prompt", "example", "privacyNote", "body",
               "whyItMatters", "sourceName", "whatsHappening", "howToSpot", "whatToDo", "helpline")
# Fields rendered as inline markdown (prompt is copied verbatim, so it is not checked).
MARKDOWN_FIELDS = ("title", "hook", "steps", "example", "privacyNote", "body", "whyItMatters",
                   "whatsHappening", "howToSpot", "whatToDo", "helpline")
LIST_LIMITS = {"steps": (2, 6), "howToSpot": (2, 4), "whatToDo": (2, 4)}

PRIVACY_EN = re.compile(r"\b(photo|selfie|face|voice|document)", re.IGNORECASE)
PRIVACY_HI = re.compile(unicodedata.normalize("NFC", "फ़ोटो|फोटो|सेल्फ़ी|चेहरा|आवाज़|दस्तावेज़"))
MAX_LIFETIME_DAYS = {"trend": 28, "news": 14}


@dataclass
class Sources:
    root: Path
    items: list = field(default_factory=list)
    files: list = field(default_factory=list)  # file stem for each item, parallel to items
    tools: list = field(default_factory=list)
    tasks: list = field(default_factory=list)
    week: dict = field(default_factory=dict)


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"{path}: {e}") from e


def load_sources(root: Path) -> Sources:
    root = Path(root)
    src = Sources(root=root)
    for p in sorted((root / "content" / "items").glob("*.json")):
        src.items.append(_read(p))
        src.files.append(p.stem)
    src.tools = _read(root / "content" / "tools.json")
    src.tasks = _read(root / "content" / "tasks.json")
    src.week = _read(root / "content" / "week.json")
    return src


def load_app_lessons(root: Path) -> set:
    """Reads tools/app-lessons.json ({courseId: [lessonId]}) into {'courseId/lessonId'}."""
    data = _read(Path(root) / "tools" / "app-lessons.json")
    return {f"{c}/{l}" for c, lessons in data.items() for l in lessons}


# ---------------------------------------------------------------- validation

def _parse_date(s):
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def markdown_problem(text: str):
    """Returns a message if text has unbalanced or unescaped inline markdown, else None."""
    stripped = text.replace("\\\\", "").replace("\\*", "")
    runs = re.findall(r"\*+", stripped)
    if any(len(r) > 2 for r in runs):
        return "run of 3 or more '*'"
    for n in (1, 2):
        if sum(1 for r in runs if len(r) == n) % 2:
            return "unpaired '*' (write a literal asterisk as \\*)" if n == 1 else "unpaired '**'"
    return None


def _check_url(url, where, errs, label):
    if not isinstance(url, str) or not url:
        errs.append(f"{where}: {label} must be a non-empty string")
        return False
    if not url.startswith("https://"):
        errs.append(f"{where}: {label} must be https, got {url}")
        return False
    if url.lower().split("?")[0].split("#")[0].endswith(".apk"):
        errs.append(f"{where}: {label} must not be an .apk link: {url}")
        return False
    return True


def _reachable(url):
    for attempt in range(2):
        for method in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(url, method=method, headers={"User-Agent": "computer-ai-feed-validator"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    if 200 <= r.status < 400:
                        return True
            except Exception:
                pass
        if attempt == 0:
            time.sleep(1)
    return False


def _check_image(root, path, where, errs, label="image"):
    if not isinstance(path, str):
        errs.append(f"{where}: {label} must be a string path")
        return
    p = Path(path)
    if p.is_absolute() or ".." in p.parts or not path.startswith("images/"):
        errs.append(f"{where}: {label} must be a relative path under images/, got {path}")
        return
    if p.suffix.lower() != ".webp":
        errs.append(f"{where}: {label} must be WebP (.webp), got {path}")
        return
    f = root / p
    if not f.is_file():
        errs.append(f"{where}: {label} file not found: {path}")
        return
    data = f.read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        errs.append(f"{where}: {label} is not a valid WebP file: {path}")
    if len(data) > MAX_IMAGE_BYTES:
        errs.append(f"{where}: {label} is {len(data)} bytes, over the {MAX_IMAGE_BYTES} byte limit: {path}")


def _is_str(v):
    return isinstance(v, str) and v.strip() != ""


def _check_item(src, it, stem, tool_ids, lessons, errs, urls):
    iid = it.get("id") if isinstance(it.get("id"), str) else stem
    e = lambda msg: errs.append(f"{iid}: {msg}")
    typ = it.get("type")
    if iid != stem:
        e(f"id does not match file name {stem}.json")
    if not KEBAB.match(iid):
        e("id must be kebab-case")
    if typ not in TYPES:
        e(f"type must be one of {', '.join(TYPES)}, got {typ!r}")
        return
    if not iid.startswith(typ + "-"):
        e(f"id must be prefixed with '{typ}-'")

    pub, rev = _parse_date(it.get("publishAt")), _parse_date(it.get("reviewBy"))
    if pub is None:
        e("publishAt must be a valid YYYY-MM-DD date")
    if rev is None:
        e("reviewBy must be a valid YYYY-MM-DD date")
    if pub and rev and pub > rev:
        e("reviewBy must be on or after publishAt")
    elif pub and rev and typ in MAX_LIFETIME_DAYS and (rev - pub).days > MAX_LIFETIME_DAYS[typ]:
        e(f"lifetime {(rev - pub).days} days is over the {MAX_LIFETIME_DAYS[typ]} day maximum for {typ} items")

    tags = it.get("tags")
    if not isinstance(tags, list) or not 1 <= len(tags) <= 3 or not all(_is_str(t) for t in tags):
        e("tags must be a list of 1 to 3 ids")

    if "toolIds" in it:
        ids = it["toolIds"]
        if not isinstance(ids, list):
            e("toolIds must be a list")
        else:
            for t in ids:
                if not isinstance(t, str) or t not in tool_ids:
                    e(f"toolIds references unknown tool {t!r}")

    if "relatedLesson" in it:
        rl = it["relatedLesson"]
        if not isinstance(rl, dict) or f"{rl.get('courseId')}/{rl.get('lessonId')}" not in lessons:
            e(f"relatedLesson {rl!r} is not in tools/app-lessons.json")

    if "image" in it:
        _check_image(src.root, it["image"], iid, errs)
    if "minutes" in it and not _is_str(it["minutes"]):
        e("minutes must be a non-empty string")

    if typ == "news":
        if "sourceUrl" not in it:
            e("news item requires sourceUrl")
        elif _check_url(it["sourceUrl"], iid, errs, "sourceUrl"):
            urls.append((iid, it["sourceUrl"]))

    langs = {}
    for lang in LANGS:
        d = it.get(lang)
        if not isinstance(d, dict):
            e(f"missing language block {lang}")
            continue
        langs[lang] = d
    for lang, d in langs.items():
        le = lambda msg, lang=lang: errs.append(f"{iid}: {lang}: {msg}")
        for f in ("title", "hook"):
            if not _is_str(d.get(f)):
                le(f"{f} is required")
        if _is_str(d.get("title")) and len(d["title"]) > 60:
            le(f"title length {len(d['title'])} is over 60")
        if _is_str(d.get("hook")) and len(d["hook"]) > 90:
            le(f"hook length {len(d['hook'])} is over 90")
        if "image" in it and not _is_str(d.get("imageAlt")):
            le("imageAlt is required when image is set")
        if typ in ("trend", "howto"):
            if not _is_str(d.get("prompt")):
                le("prompt is required")
            elif len(d["prompt"]) > 600:
                le(f"prompt length {len(d['prompt'])} is over 600")
            steps = d.get("steps")
            steps = steps if isinstance(steps, list) else []
            text = unicodedata.normalize(
                "NFC", " ".join(x for x in steps if isinstance(x, str)) + " " + str(d.get("prompt") or ""))
            if (PRIVACY_EN.search(text) or PRIVACY_HI.search(text)) and not _is_str(d.get("privacyNote")):
                le("privacyNote is required when steps or prompt mention a photo, selfie, face, voice or document")
            required = ("steps",)
        elif typ == "news":
            required = ("body", "whyItMatters", "sourceName")
        else:
            required = ("whatsHappening", "howToSpot", "whatToDo")
        for f in required:
            if f in LIST_LIMITS:
                lo, hi_ = LIST_LIMITS[f]
                v = d.get(f)
                if not isinstance(v, list) or not all(_is_str(x) for x in v):
                    le(f"{f} must be a list of non-empty strings")
                elif not lo <= len(v) <= hi_:
                    le(f"{f} count {len(v)} must be {lo} to {hi_}")
            elif not _is_str(d.get(f)):
                le(f"{f} is required")
        for f in MARKDOWN_FIELDS:
            v = d.get(f)
            for s in (v if isinstance(v, list) else [v]):
                if isinstance(s, str):
                    p = markdown_problem(s)
                    if p:
                        le(f"markdown error in {f}: {p}")

    if len(langs) == 2:
        for f in LIST_LIMITS:
            a, b = langs["hi"].get(f), langs["en"].get(f)
            if isinstance(a, list) and isinstance(b, list) and len(a) != len(b):
                errs.append(f"{iid}: hi/en {f} count differs ({len(a)} vs {len(b)})")
        for f in LANG_FIELDS:
            if f in ("steps", "howToSpot", "whatToDo"):
                continue
            if (f in langs["hi"]) != (f in langs["en"]) and f in ("imageAlt", "privacyNote", "example", "helpline"):
                errs.append(f"{iid}: {f} is present in only one of hi/en")


def validate(src: Sources, app_lessons: set, check_urls: bool, min_stories: int = 5) -> list:
    try:
        return _validate(src, app_lessons, check_urls, min_stories)
    except Exception as ex:  # malformed input must be reported, never crash
        return [f"malformed input: {type(ex).__name__}: {ex}"]


def _validate(src, app_lessons, check_urls, min_stories):
    errs, urls = [], []
    tool_ids = set()

    for t in src.tools:
        if not isinstance(t, dict):
            errs.append(f"tool {t!r}: must be an object")
            continue
        tid = t.get("id", "?")
        where = f"tool {tid}"
        if tid in tool_ids:
            errs.append(f"{where}: duplicate tool id")
        tool_ids.add(tid)
        if not _is_str(t.get("name")):
            errs.append(f"{where}: name is required")
        if t.get("price") not in PRICES:
            errs.append(f"{where}: price must be free or freemium, got {t.get('price')!r} (paid-only tools are rejected)")
        if t.get("login") not in LOGINS:
            errs.append(f"{where}: login must be one of {', '.join(LOGINS)}")
        if not (t.get("android") or t.get("web")):
            errs.append(f"{where}: needs an android or web link")
        for k in ("android", "web"):
            if k in t and _check_url(t[k], where, errs, k):
                urls.append((where, t[k]))
        if "icon" in t:
            _check_image(src.root, t["icon"], where, errs, "icon")
        for lang in LANGS:
            if not isinstance(t.get(lang), dict) or not _is_str(t[lang].get("note")):
                errs.append(f"{where}: {lang}.note is required")

    task_ids = set()
    if len(src.tasks) > MAX_TASKS:
        errs.append(f"tasks: at most {MAX_TASKS} allowed, got {len(src.tasks)}")
    for t in src.tasks:
        if not isinstance(t, dict):
            errs.append(f"task {t!r}: must be an object")
            continue
        tid = t.get("id", "?")
        task_ids.add(tid)
        if not _is_str(t.get("icon")):
            errs.append(f"task {tid}: icon is required")
        for lang in LANGS:
            if not isinstance(t.get(lang), dict) or not _is_str(t[lang].get("title")):
                errs.append(f"task {tid}: {lang}.title is required")

    seen = set()
    for it, stem in zip(src.items, src.files):
        if not isinstance(it, dict):
            errs.append(f"{stem}: item must be an object")
            continue
        iid = it.get("id", stem)
        if iid in seen:
            errs.append(f"{iid}: duplicate id")
        seen.add(iid)
        _check_item(src, it, stem, tool_ids, app_lessons, errs, urls)

    by_id = {i.get("id"): i for i in src.items if isinstance(i, dict)}
    week = src.week if isinstance(src.week, dict) else {}
    if week is not src.week:
        errs.append("week: must be an object")
    stories, featured = week.get("stories"), week.get("featured")
    if not isinstance(stories, list) or not all(isinstance(x, str) for x in stories):
        errs.append("week: stories must be a list of ids")
        stories = []
    elif not min_stories <= len(stories) <= 7:
        errs.append(f"week: stories count {len(stories)} must be {min_stories} to 7")
    if len(set(stories)) != len(stories):
        errs.append("week: stories contains duplicate ids")
    refs = [("stories", x) for x in stories] + [("featured", featured)]
    for kind, rid in refs:
        if rid not in by_id:
            errs.append(f"week: {kind} references unknown item {rid!r}")
    starts = [d for d in (_parse_date(by_id[s].get("publishAt")) for s in stories if s in by_id) if d]
    if starts:
        w0 = min(starts)
        w1 = w0 + timedelta(days=6)
        for kind, rid in refs:
            it = by_id.get(rid)
            pub, rev = (_parse_date(it.get("publishAt")), _parse_date(it.get("reviewBy"))) if it else (None, None)
            if pub and rev and (pub > w1 or rev < w0):
                errs.append(f"week: {kind} item {rid} is not live during the batch week {w0} to {w1}")

    if check_urls:
        for where, url in dict.fromkeys(urls):
            if not _reachable(url):
                errs.append(f"{where}: URL not reachable (needs HTTP 2xx or 3xx): {url}")
    return errs


# --------------------------------------------------------------------- build

def _sort_key(it):
    return (it["publishAt"], it["id"])


def _flatten_item(it, lang):
    out = {k: copy.deepcopy(it[k]) for k in SHARED_FIELDS if k in it}
    out.update({k: copy.deepcopy(v) for k, v in it[lang].items() if k in LANG_FIELDS})
    if it["type"] == "safety":
        out.setdefault("helpline", DEFAULT_HELPLINE)
    return out


def build(src: Sources, lang: str, generated_at: str) -> dict:
    items = sorted(src.items, key=lambda i: i["id"])
    items = sorted(items, key=lambda i: i["publishAt"], reverse=True)
    ids = {i["id"] for i in items}
    tools = []
    for t in src.tools:
        o = {k: t[k] for k in ("id", "name", "icon", "price", "login", "android", "web") if k in t}
        o["loginNote"] = t[lang]["note"]
        tools.append(o)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "minAppVersionCode": MIN_APP_VERSION_CODE,
        "generatedAt": generated_at,
        "stories": [s for s in src.week["stories"] if s in ids],
        "featured": src.week["featured"] if src.week["featured"] in ids else None,
        "tasks": [{"id": t["id"], "icon": t["icon"], "title": t[lang]["title"]} for t in src.tasks],
        "tools": tools,
        "items": [_flatten_item(i, lang) for i in items],
    }


def prune(src: Sources, today: date) -> list:
    out = []
    for it in src.items:
        rev = _parse_date(it.get("reviewBy"))
        if rev and today >= rev + timedelta(days=PRUNE_AFTER_DAYS):
            out.append(it["id"])
    return out


def without_items(src: Sources, ids) -> Sources:
    ids = set(ids)
    keep = [(i, f) for i, f in zip(src.items, src.files) if i["id"] not in ids]
    return Sources(root=src.root, items=[i for i, _ in keep], files=[f for _, f in keep],
                   tools=src.tools, tasks=src.tasks, week=src.week)


def referenced_images(doc: dict) -> list:
    paths = [i["image"] for i in doc["items"] if "image" in i]
    paths += [t["icon"] for t in doc["tools"] if str(t.get("icon", "")).startswith("images/")]
    return sorted(set(paths))


def copy_images(root: Path, out_dir: Path, paths) -> None:
    """Copies each 'images/...' path from root into out_dir/images/..., keeping the sub-path."""
    for rel in paths:
        dest = Path(out_dir) / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(root) / rel, dest)
