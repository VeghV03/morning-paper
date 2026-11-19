import os
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from paper import config, issue, reading
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain

DAY = "2026-11-18"


class IssueTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.h = Home(self.root)
        self.h.issues.mkdir()
        (self.root / "sections.md").write_text("# x\nMagyarország: hírek\nHosszú olvasmány: esszé\n", encoding="utf-8")

    def write(self, rows, day=DAY):
        (self.h.issues / f"{day}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def piece(self, n, **kw):
        return {"id": f"r-{DAY}-{n}", "section": "magyarorszag", "url": f"https://a.hu/{n}", "head": "Fej", "lead": "Lead.", **kw}

    def errors(self):
        with self.assertRaises(issue.Invalid) as e:
            issue.validate(self.h, DAY)
        return "\n".join(e.exception.errors)

    def test_section_ids(self):
        self.assertEqual([s.id for s in issue.sections(self.h)], ["magyarorszag", "hosszu-olvasmany"])

    def test_valid_issue(self):
        self.write([self.piece(1), self.piece(2, section="hosszu-olvasmany"),
                    {"id": f"r-{DAY}-3", "saved": True, "url": "https://b.hu", "head": "Mentett"}])
        self.assertEqual(len(issue.validate(self.h, DAY)), 3)

    def test_refuses_what_does_not_fit(self):
        self.write([self.piece(1), self.piece(2), self.piece(3), self.piece(4),
                    self.piece(5, section="nincs"), self.piece(6, head="x" * 61),
                    self.piece(7, url="https://a.hu/1"), self.piece(8, thread="t-nincs")])
        text = self.errors()
        for part in ("7 pieces in 'magyarorszag'", "section 'nincs'", "head is 61", "in the issue twice", "t-nincs"):
            self.assertIn(part, text)

    def test_id_names_the_day(self):
        self.write([{**self.piece(1), "id": "r-2026-11-17-1"}])
        self.assertIn(f"needs id, r-{DAY}-<n>", self.errors())

    def threads(self, *rows):
        self.h.threads.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def test_thread_entries(self):
        long = [{"day": DAY, "text": "é" * 280}] * 8
        self.threads({"id": "t-a", "title": "A", "entries": [{"day": DAY, "text": "x" * 281}]},
                     {"id": "t-b", "title": "B", "entries": [{"day": DAY, "text": "b"}, {"day": "2026-11-01", "text": "a"}]},
                     {"id": "t-c", "title": "C", "entries": long}, {"id": "t-d", "title": "D", "entries": []})
        self.write([self.piece(1, thread="t-a")])
        text = self.errors()
        for part in ("281 characters", "oldest first", "4480 bytes", "needs entries"):
            self.assertIn(part, text)

    def test_an_old_thread_reads_as_one_entry(self):
        self.threads({"id": "t-a", "title": "A", "body": "é" * 300, "since": "2026-11-10", "updated": "2026-11-17"})
        self.write([self.piece(1, thread="t-a")])
        issue.validate(self.h, DAY)
        self.assertEqual(issue.threads(self.h)["t-a"]["entries"][0]["day"], "2026-11-17")

    def test_reading_context(self):
        self.write([self.piece(1), self.piece(2), {"id": f"r-{DAY}-3", "saved": True, "url": "https://b.hu", "head": "M"}])
        reading.log(self.h, {"ev": "seen", "id": f"r-{DAY}-1"})
        reading.log(self.h, {"ev": "read", "id": f"r-{DAY}-1", "ms": 120000, "progress": 0.95})
        reading.log(self.h, {"ev": "keep", "id": f"r-{DAY}-2", "kept": True})
        rows = {r["id"]: r for r in reading.context(self.h, date.fromisoformat(DAY))["pieces"]}
        one, two, saved = rows[f"r-{DAY}-1"], rows[f"r-{DAY}-2"], rows[f"r-{DAY}-3"]
        self.assertEqual((one["opened"], one["finished"], one["min"]), (True, True, 2))
        self.assertEqual((two["seen"], two["kept"]), (False, True))
        self.assertEqual((saved["section"], saved["kept"]), ("saved", True))


    def test_quick_scroll_is_not_finished(self):
        self.write([self.piece(1)])
        self.h.cache.mkdir()
        (self.h.cache / f"r-{DAY}-1.json").write_text(json.dumps({"words": 1500}), encoding="utf-8")
        reading.log(self.h, {"ev": "read", "id": f"r-{DAY}-1", "ms": 30000, "progress": 1.0})
        row = reading.context(self.h, date.fromisoformat(DAY))["pieces"][0]
        self.assertFalse(row["finished"])  # 1500 words want 2 of their 6 minutes
        reading.log(self.h, {"ev": "read", "id": f"r-{DAY}-1", "ms": 90000, "progress": 1.0})
        self.assertTrue(reading.context(self.h, date.fromisoformat(DAY))["pieces"][0]["finished"])

    def test_digest_needs_its_text(self):
        self.write([self.piece(1, digest=True)])
        self.assertIn("a digest needs its text", self.errors())
        self.h.digests.mkdir()
        (self.h.digests / f"r-{DAY}-1.md").write_text("word " * 451, encoding="utf-8")
        self.assertIn("451 words", self.errors())

    def test_k_counts_newsrooms_not_feeds(self):
        from paper.feed import _k
        sources = [{"org": "BBC"}, {"org": "BBC"}, {"org": "Sky News"}, {"org": "Reuters", "channel": True}]
        self.assertEqual(_k(sources), 2)
        self.assertEqual(_k([{"org": "Reuters", "channel": True}]), 1)

    def test_dateline_follows_language(self):
        self.assertEqual(config.dateline(self.h, DAY), "Wednesday 18 November 2026")
        self.h.config.write_text("language: hu\n", encoding="utf-8")
        self.assertEqual(config.dateline(self.h, DAY), "2026. november 18., szerda")


if __name__ == "__main__":
    unittest.main()
