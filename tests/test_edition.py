"""The edition the phone reads: front page, piece texts, digests, the 30-day limit."""

import json
import tempfile
import unittest
from pathlib import Path

from paper import edition
from paper.home import Home

DAY = "2026-11-19"
ARTICLE = "<p>" + "The council met and voted on the budget for the coming year. " * 10 + "</p>"


def fake_extract(url):
    if "refuses" in url:
        return {}
    return {"title": "The budget passes | Daily", "author": "Ann Lee", "date": DAY, "html": ARTICLE}


class EditionTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.h.issues.mkdir()
        self.h.digests.mkdir()
        (self.h.root / "sections.md").write_text("World: news\nScience: research\n", encoding="utf-8")
        rows = [
            {"id": "r-1", "section": "science", "url": "https://www.lab.org/a", "head": "A finding", "lead": "Lead one."},
            {"id": "r-2", "section": "world", "url": "https://daily.com/b", "head": "The budget", "lead": "Lead two."},
            {"id": "r-3", "section": "world", "url": "https://refuses.com/c", "head": "Walled", "lead": "Lead three."},
            {"id": "r-4", "saved": True, "url": "https://essays.net/d", "head": "An essay"},
            {"id": "p-1", "predict": "r-2", "prompt": "Will it pass?", "options": ["Yes", "No"], "answer": 0},
        ]
        self.write(DAY, rows)
        (self.h.digests / "r-1.md").write_text("---\nnote: for Claude\n---\nWhat it found.\n\n> A key line.", encoding="utf-8")

    def write(self, day, rows):
        (self.h.issues / f"{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def read(self, rel):
        return json.loads((self.h.root / "edition" / rel).read_text(encoding="utf-8"))

    def test_a_file_a_month_and_a_past_month_left_alone(self):
        self.write("2026-10-30", [{"id": "r-o", "section": "world", "url": "https://daily.com/o", "head": "Old", "lead": "L."},
                                  {"id": "c-o", "card": "flip", "front": "Q?", "back": "A.", "from": "r-o"}])
        (self.h.root / "edition").mkdir()
        (self.h.root / "edition" / "index.json").write_text(json.dumps({"pieces": {"r-o": {"words": 321}}}))  # before D84
        edition.build(self.h, DAY, fake_extract)
        october = self.read("months/2026-10.json")
        self.assertEqual(october["pieces"]["r-o"]["words"], 321)  # carried over from the one index
        self.assertEqual(october["cards"]["c-o"], {"day": "2026-10-30", "card": "flip", "front": "Q?", "back": "A.", "from": "r-o"})
        self.assertEqual(sorted(self.read("months/2026-11.json")["pieces"]), ["r-1", "r-2", "r-3", "r-4"])
        self.assertEqual(self.read("index.json"), {"steered": {}, "months": ["2026-10", "2026-11"]})
        (self.h.root / "edition" / "months" / "2026-10.json").write_text('{"pieces": {}, "cards": {}}')
        edition.build(self.h, DAY, fake_extract)
        self.assertEqual(self.read("months/2026-10.json"), {"pieces": {}, "cards": {}})  # a past month is final
        self.assertTrue((self.h.root / "edition" / "months").is_dir())  # not taken for an old day's texts

    def test_front_page_follows_sections_md_and_leaves_games_out(self):
        built = edition.build(self.h, DAY, fake_extract)
        self.assertEqual(built, {"pieces": 4, "texts": 3, "dropped": []})
        page = self.read(f"{DAY}.json")
        self.assertEqual([s["name"] for s in page["sections"]], ["World", "Science"])
        self.assertEqual([p["id"] for p in page["sections"][0]["pieces"]], ["r-2", "r-3"])
        self.assertEqual(page["sections"][0]["pieces"][0]["host"], "daily.com")
        self.assertEqual([p["id"] for p in page["saved"]], ["r-4"])
        self.assertNotIn("Will it pass?", json.dumps(page))
        self.assertEqual(page["dateline"], "Thursday 19 November 2026")

    def test_pieces_carry_text_a_digest_or_only_their_address(self):
        edition.build(self.h, DAY, fake_extract)
        art = self.read(f"{DAY}/r-2.json")
        self.assertEqual(art["title"], "The budget passes")
        self.assertEqual(art["byline"], "daily.com · Ann Lee · 19 November")
        self.assertIn("voted on the budget", art["html"])
        digest = self.read(f"{DAY}/r-1.json")
        self.assertIn("<blockquote>A key line.</blockquote>", digest["html"])
        self.assertNotIn("for Claude", digest["html"])
        self.assertEqual(self.read(f"{DAY}/r-3.json"), {"url": "https://refuses.com/c"})

    def test_texts_older_than_thirty_days_go_and_front_pages_stay(self):
        old = "2026-10-01"
        self.write(old, [{"id": "r-9", "section": "world", "url": "https://daily.com/z", "head": "Old", "lead": "Old."}])
        edition.build(self.h, old, fake_extract)
        built = edition.build(self.h, DAY, fake_extract)
        self.assertEqual(built["dropped"], [old])
        self.assertFalse((self.h.root / "edition" / old).exists())
        self.assertEqual(self.read(f"{old}.json")["sections"][0]["pieces"][0]["url"], "https://daily.com/z")  # opens there

    def test_a_page_that_breaks_the_cleaner_opens_at_its_outlet(self):
        def broken(url):
            raise RuntimeError("odd page")
        built = edition.build(self.h, DAY, broken)
        self.assertEqual(built["texts"], 1)  # the digest
        self.assertEqual(self.read(f"{DAY}/r-2.json"), {"url": "https://daily.com/b"})


if __name__ == "__main__":
    unittest.main()
