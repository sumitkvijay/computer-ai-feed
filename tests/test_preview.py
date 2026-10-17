import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import feedlib  # noqa: E402
import preview  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"


def fixture_copy():
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(FIX, tmp / "r")
    return tmp, tmp / "r"


class PreviewTests(unittest.TestCase):
    def test_preview_lists_new_items_hindi_first(self):
        tmp, root = fixture_copy()
        self.addCleanup(shutil.rmtree, tmp)
        dist = root / "dist" / "v1"
        dist.mkdir(parents=True)
        (dist / "hi.json").write_text(json.dumps({"items": [{"id": "news-free-gemini-feature"}]}))
        out = preview.preview(feedlib.load_sources(root))
        hi, en = "अपनी फ़ोटो को 80 के दशक का बनाएँ", "Make your photo look like the 80s"
        self.assertIn(hi, out)
        self.assertIn(en, out)
        self.assertLess(out.index(hi), out.index(en))
        self.assertNotIn("news-free-gemini-feature", out)
        self.assertEqual(out.count("### "), 1)
        self.assertIn("```", out)  # prompt in a code block
        self.assertIn("2026-10-20", out)
        self.assertIn("अपनी फ़ोटो सिर्फ़ भरोसेमंद ऐप में डालें।", out)  # privacy note

    def test_preview_without_dist_lists_all_items(self):
        out = preview.preview(feedlib.load_sources(FIX))
        self.assertEqual(out.count("### "), 2)
        self.assertIn("https://", out)  # news source

    def test_preview_nothing_new(self):
        tmp, root = fixture_copy()
        self.addCleanup(shutil.rmtree, tmp)
        dist = root / "dist" / "v1"
        dist.mkdir(parents=True)
        (dist / "hi.json").write_text(json.dumps({"items": [{"id": i} for i in
                                      ("trend-80s-photo", "news-free-gemini-feature")]}))
        out = preview.preview(feedlib.load_sources(root))
        self.assertNotIn("### ", out)
        self.assertIn("No new items", out)


class PruneCliTests(unittest.TestCase):
    def run_cli(self, root, *extra):
        return subprocess.run([sys.executable, str(REPO / "tools" / "prune.py"), "--root", str(root), *extra],
                              capture_output=True, text=True)

    def test_prints_expired_ids(self):
        r = self.run_cli(FIX, "--today", "2026-12-04")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split(), ["news-free-gemini-feature"])
        self.assertEqual(self.run_cli(FIX, "--today", "2026-12-03").stdout.strip(), "")

    def test_move_relocates_sources_to_archive(self):
        tmp, root = fixture_copy()
        self.addCleanup(shutil.rmtree, tmp)
        r = self.run_cli(root, "--today", "2026-12-04", "--move")
        self.assertEqual(r.returncode, 0, r.stderr)
        name = "news-free-gemini-feature.json"
        self.assertTrue((root / "archive" / "items" / name).is_file())
        self.assertFalse((root / "content" / "items" / name).exists())
        self.assertTrue((root / "content" / "items" / "trend-80s-photo.json").is_file())


if __name__ == "__main__":
    unittest.main()
