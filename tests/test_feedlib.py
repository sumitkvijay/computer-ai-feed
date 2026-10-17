import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import feedlib  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
TREND = "trend-80s-photo"
NEWS = "news-free-gemini-feature"


class FeedTestCase(unittest.TestCase):
    def setUp(self):
        self.src = copy.deepcopy(feedlib.load_sources(FIX))
        self.lessons = feedlib.load_app_lessons(FIX)

    def item(self, item_id):
        return next(i for i in self.src.items if i["id"] == item_id)

    def errors(self):
        # The two-item fixture is smaller than a real 5-7 story batch.
        return feedlib.validate(self.src, self.lessons, False, min_stories=1)

    def assertError(self, needle):
        errs = self.errors()
        self.assertTrue(any(needle in e for e in errs), f"{needle!r} not in {errs}")
        return errs


class ValidateTests(FeedTestCase):
    def test_valid_fixture_passes(self):
        self.assertEqual(self.errors(), [])

    def test_missing_privacy_note_on_photo_trend(self):
        del self.item(TREND)["hi"]["privacyNote"]
        errs = self.assertError("privacyNote")
        self.assertTrue(all(e.startswith(TREND + ":") for e in errs if "privacyNote" in e))

    def test_hi_en_step_count_mismatch(self):
        self.item(TREND)["en"]["steps"].pop()
        self.assertError("steps count")

    def test_paid_tool_rejected(self):
        self.src.tools[0]["price"] = "paid"
        self.assertError("price")

    def test_apk_link_rejected(self):
        self.src.tools[0]["android"] = "https://example.com/app.apk"
        self.assertError(".apk")

    def test_http_url_rejected(self):
        self.src.tools[0]["web"] = "http://gemini.google.com"
        self.assertError("https")

    def test_news_requires_source(self):
        del self.item(NEWS)["sourceUrl"]
        errs = self.assertError("sourceUrl")
        self.assertTrue(any(e.startswith(NEWS + ":") for e in errs))

    def test_story_id_must_exist(self):
        self.src.week["stories"].append("trend-nope")
        self.assertError("stories")

    def test_title_over_60(self):
        self.item(TREND)["en"]["title"] = "x" * 61
        self.assertError("title length")

    def test_unknown_related_lesson(self):
        self.item(TREND)["relatedLesson"] = {"courseId": "ai-tools-basics", "lessonId": "L99"}
        self.assertError("relatedLesson")

    def test_unescaped_asterisk(self):
        self.item(TREND)["en"]["hook"] = "Use * to multiply"
        self.assertError("markdown")

    def test_escaped_and_paired_markdown_ok(self):
        self.item(TREND)["en"]["hook"] = r"**Bold** and *italic* and 2 \* 3"
        self.assertEqual(self.errors(), [])

    def test_story_count_enforced_by_default(self):
        errs = feedlib.validate(self.src, self.lessons, False)
        self.assertTrue(any("stories" in e and "5" in e for e in errs))

    def test_missing_image_alt(self):
        del self.item(TREND)["hi"]["imageAlt"]
        self.assertError("imageAlt")

    def test_image_not_webp(self):
        self.item(TREND)["image"] = "images/x.png"
        self.assertError("image")

    def test_trend_lifetime_over_28_rejected(self):
        self.item(TREND)["reviewBy"] = "2026-11-18"
        errs = self.assertError("lifetime")
        self.assertTrue(any(e.startswith(TREND + ":") and "lifetime" in e for e in errs))
        self.item(TREND)["reviewBy"] = "2026-11-17"
        self.assertEqual(self.errors(), [])

    def test_news_lifetime_over_14_rejected(self):
        self.item(NEWS)["reviewBy"] = "2026-11-05"
        errs = self.assertError("lifetime")
        self.assertTrue(any(e.startswith(NEWS + ":") for e in errs))

    def test_howto_long_lifetime_allowed(self):
        it = self.item(TREND)
        it["type"] = "howto"
        it["id"] = "howto-80s-photo"
        self.src.files[self.src.items.index(it)] = "howto-80s-photo"
        self.src.week["stories"] = ["howto-80s-photo", NEWS]
        self.src.week["featured"] = "howto-80s-photo"
        it["reviewBy"] = "2027-12-31"
        self.assertEqual(self.errors(), [])

    def test_privacy_check_matches_precomposed_nukta(self):
        it = self.item(TREND)
        del it["hi"]["privacyNote"]
        it["hi"]["steps"] = ["\u095e\u094b\u091f\u094b \u091a\u0941\u0928\u0947\u0902", "\u092d\u0947\u091c\u0947\u0902"]
        it["en"]["steps"] = ["Choose it", "Send"]
        it["en"]["prompt"] = "Make it retro"
        it["hi"]["prompt"] = "इसे रेट्रो बनाओ"
        self.assertError("privacyNote")

    def test_privacy_check_case_insensitive_english(self):
        it = self.item(TREND)
        del it["en"]["privacyNote"]
        it["en"]["steps"] = ["Upload your Photo", "Send"]
        it["en"]["prompt"] = "Make it retro"
        self.assertError("privacyNote")

    def test_malformed_fields_report_errors_not_crash(self):
        it = self.item(TREND)
        it["image"] = 5
        it["hi"]["steps"] = None
        it["tags"] = None
        it["toolIds"] = [["x"]]
        self.src.tools.append("junk")
        self.src.tasks.append(7)
        self.src.items.append(None)
        self.src.files.append("junk")
        self.src.week["stories"] = [{"a": 1}]
        errs = self.errors()
        self.assertTrue(errs)
        self.assertTrue(any("image" in e for e in errs))
        self.assertTrue(any("steps" in e for e in errs))
        self.src.week = None
        self.assertTrue(self.errors())

    def test_unknown_tool_id(self):
        self.item(TREND)["toolIds"] = ["ghost"]
        self.assertError("toolIds")

    def test_dates_out_of_order(self):
        self.item(TREND)["reviewBy"] = "2026-10-01"
        self.assertError("reviewBy")


class BuildTests(FeedTestCase):
    def test_build_flattens_language(self):
        hi = feedlib.build(self.src, "hi", "2026-10-20T03:30:00Z")
        en = feedlib.build(self.src, "en", "2026-10-20T03:30:00Z")
        self.assertEqual(hi["items"][0]["title"], self.item(NEWS)["hi"]["title"])
        self.assertEqual([i["id"] for i in hi["items"]], [i["id"] for i in en["items"]])
        self.assertEqual(hi["schemaVersion"], 1)
        self.assertEqual(hi["tools"][0]["loginNote"], "Google खाते से लॉगिन")
        self.assertNotIn("note", hi["tools"][0])
        self.assertEqual(hi["tasks"][0], {"id": "photos", "icon": "image", "title": "फ़ोटो बनाएँ और सुधारें"})
        self.assertNotIn("hi", hi["items"][0])

    def test_sort_publish_desc_then_id(self):
        ids = [i["id"] for i in feedlib.build(self.src, "en", "t")["items"]]
        self.assertEqual(ids, [NEWS, TREND])

    def test_prune_30_days_past_review(self):
        self.assertEqual(feedlib.prune(self.src, date(2026, 12, 4)), [NEWS])
        self.assertEqual(feedlib.prune(self.src, date(2026, 12, 3)), [])

    def test_build_copies_referenced_images(self):
        with tempfile.TemporaryDirectory() as out:
            r = subprocess.run(
                [sys.executable, "-I", str(REPO / "tools" / "build.py"), "--root", str(FIX), "--out", out,
                 "--generated-at", "2026-10-20T03:30:00Z", "--today", "2026-10-20", "--no-urls", "--min-stories", "1"],
                capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue((Path(out) / "images" / "x.webp").is_file())
            self.assertTrue((Path(out) / "images" / "tools" / "gemini.webp").is_file())
            hi = json.loads((Path(out) / "hi.json").read_text(encoding="utf-8"))
            self.assertIn("अपनी फ़ोटो", json.dumps(hi, ensure_ascii=False))
            self.assertTrue((Path(out) / "en.json").is_file())


if __name__ == "__main__":
    unittest.main()
