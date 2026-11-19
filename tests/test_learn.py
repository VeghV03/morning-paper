import os
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from paper import issue, learn, reading, settings
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain

DAY = "2026-11-18"
NEXT = "2026-11-19"


class LearnTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.h = Home(self.root)
        self.h.issues.mkdir()
        (self.root / "sections.md").write_text("World: news\nIdeas: essays | power, taste, method\n", encoding="utf-8")

    def write(self, rows, day=DAY):
        (self.h.issues / f"{day}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def piece(self, n, day=DAY, **kw):
        return {"id": f"r-{day}-{n}", "section": "world", "url": f"https://a.org/{day}/{n}", "head": "Head", "lead": "Lead.", **kw}

    def errors(self, day=DAY):
        with self.assertRaises(issue.Invalid) as e:
            issue.validate(self.h, day)
        return "\n".join(e.exception.errors)

    def test_topics_are_read_from_sections(self):
        secs = {s.id: s for s in issue.sections(self.h)}
        self.assertEqual(secs["ideas"].topics, ("power", "taste", "method"))
        self.assertEqual(secs["ideas"].what, "essays")
        self.assertEqual(secs["world"].topics, ())

    def test_steered_piece_needs_topic_and_fit(self):
        self.write([self.piece(1, section="ideas"), self.piece(2, section="ideas", topic="taste", fit="tries"),
                    self.piece(3, section="ideas", topic="cooking", fit="maybe")])
        text = self.errors()
        self.assertIn("topic must be one of: power, taste, method", text)
        self.assertIn("fit must be fits or tries", text)
        self.assertNotIn(":2:", text)

    def test_answers_and_cards(self):
        self.write([self.piece(1)])
        q = learn.add_mark(self.h, f"r-{DAY}-1", "question", "Why  did\nit fall?")
        h = learn.add_mark(self.h, f"r-{DAY}-1", "highlight", "It fell.")
        self.assertEqual(q["text"], "Why did it fall?")
        good = [self.piece(1, NEXT),
                {"id": f"a-{NEXT}-1", "answer": q["id"], "text": "Because."},
                {"id": f"c-{NEXT}-1", "card": "flip", "front": "F", "back": "B", "from": h["id"]},
                {"id": f"c-{NEXT}-2", "card": "choice", "prompt": "P", "options": ["a", "b", "c"], "answer": 1, "from": f"r-{DAY}-1"}]
        self.write(good, NEXT)
        self.assertEqual(len(issue.validate(self.h, NEXT)), 4)
        self.write([self.piece(1, NEXT),
                    {"id": f"a-{NEXT}-1", "answer": h["id"], "text": "x " * 121},
                    {"id": f"c-{NEXT}-1", "card": "choice", "prompt": "P", "options": ["a", "b"], "answer": 1, "from": "r-nope"},
                    {"id": f"c-{NEXT}-2", "card": "cloze", "from": f"r-{DAY}-1"}], NEXT)
        text = self.errors(NEXT)
        for part in ("must name a question", "121 words", "three options", "from must name", "flip or choice"):
            self.assertIn(part, text)

    def test_deleted_mark_is_gone(self):
        self.write([self.piece(1)])
        m = learn.add_mark(self.h, f"r-{DAY}-1", "highlight", "text")
        learn.delete_mark(self.h, m["id"])
        self.assertEqual(learn.marks(self.h), {})

    def cards(self, n):
        rows = [self.piece(1), self.piece(2)]
        rows += [{"id": f"c-{DAY}-{i}", "card": "flip", "front": "F", "back": "B", "from": f"r-{DAY}-{1 + i % 2}"} for i in range(1, n + 1)]
        self.write(rows)

    def test_due_never_from_the_piece_just_read(self):
        self.cards(2)  # c-1 from piece 2, c-2 from piece 1
        self.assertEqual(learn.due(self.h, [], f"r-{DAY}-1")["id"], f"c-{DAY}-1")
        self.assertEqual(learn.due(self.h, [], f"r-{DAY}-2")["id"], f"c-{DAY}-2")

    def test_new_cards_a_day(self):
        self.cards(12)
        now = datetime.now(timezone.utc)
        reviews = [{"id": f"c-{DAY}-{i}", "rating": "good", "t": (now - timedelta(minutes=i)).isoformat()} for i in range(1, 11)]
        self.assertIsNone(learn.due(self.h, reviews, "r-x", now))
        self.assertIsNotNone(learn.due(self.h, reviews[:9], "r-x", now))

    def test_reviewed_card_comes_back_after_days(self):
        self.cards(1)
        then = datetime.now(timezone.utc) - timedelta(days=30)
        reviews = [{"id": f"c-{DAY}-1", "rating": "good", "t": then.isoformat()}]
        self.assertEqual(learn.due(self.h, reviews, "r-x")["id"], f"c-{DAY}-1")
        self.assertIsNone(learn.due(self.h, reviews, "r-x", then + timedelta(hours=2)))

    def test_silent_section(self):
        today = date.fromisoformat(DAY)
        old = (today - timedelta(days=40)).isoformat()
        self.write([self.piece(1, old, section="ideas", topic="power", fit="fits")], old)
        self.write([self.piece(1, section="ideas", topic="power", fit="fits")])
        for pid in (f"r-{old}-1", f"r-{DAY}-1"):
            reading.log(self.h, {"ev": "look", "id": pid})
        self.assertTrue(reading.context(self.h, today)["steer"]["ideas"]["silent"])
        reading.log(self.h, {"ev": "open", "id": f"r-{DAY}-1"})
        self.assertFalse(reading.context(self.h, today)["steer"]["ideas"]["silent"])

    def test_settings_refuse_and_clean(self):
        with self.assertRaises(issue.Invalid):
            settings.save_sections(self.h, [{"name": "A: b", "what": "x"}])
        settings.save_sections(self.h, [{"name": "Ideas", "what": "essays\nand | more", "topics": "a, , b"}])
        self.assertEqual(issue.sections(self.h)[0].topics, ("a", "b"))
        self.assertIn("Ideas: essays and / more | a, b", self.h.sections.read_text())


if __name__ == "__main__":
    unittest.main()
