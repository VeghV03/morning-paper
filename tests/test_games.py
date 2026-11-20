import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from paper import crossword, edition, issue, learn, reading
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain

SAT = "2026-11-21"
SUN = "2026-11-22"
WORDS = ["HUNGARY", "BUDGET", "ORBAN", "VOTE", "DANUBE", "SENATE", "EURO", "COURT", "TAX", "LAW"]


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.h = Home(self.root)
        self.h.issues.mkdir()
        (self.root / "sections.md").write_text("World: news\n", encoding="utf-8")
        entries = [{"day": "2026-11-20", "text": "Tabled."}, {"day": SAT, "text": "Sent back.", "piece": f"r-{SAT}-1"}]
        self.h.threads.write_text(json.dumps({"id": "t-budget", "title": "The budget", "since": "2026-11-20",
                                              "entries": entries}) + "\n", encoding="utf-8")

    def write(self, rows, day=SUN):
        (self.h.issues / f"{day}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    def piece(self, n, day=SUN, **kw):
        return {"id": f"r-{day}-{n}", "section": "world", "url": f"https://a.org/{day}/{n}", "head": f"Head {n}",
                "lead": "Lead.", **kw}

    def errors(self, day=SUN):
        with self.assertRaises(issue.Invalid) as e:
            issue.validate(self.h, day)
        return "\n".join(e.exception.errors)

    def opened(self, *ids):
        for i in ids:
            reading.log(self.h, {"ev": "open", "id": i})

    def predict(self, n, piece, **kw):
        return {"id": f"p-{SUN}-{n}", "predict": piece, "prompt": "What did it find?", "options": ["a", "b", "c"],
                "answer": 1, **kw}


class CheckTest(Base):
    def test_predictions(self):
        self.write([self.piece(1), self.piece(2), self.predict(1, f"r-{SUN}-1")])
        self.assertEqual(len(issue.validate(self.h, SUN)), 3)
        self.write([self.piece(1), *[self.predict(n, f"r-{SUN}-1") for n in (1, 2)],
                    self.predict(3, "r-nope", answer=3), self.predict(4, f"r-{SUN}-1", answer=True)])
        text = self.errors()
        self.assertIn("has two games", text)
        self.assertIn("must name a piece of this issue", text)
        self.assertIn("answer is the right option's index", text)
        self.assertIn("4 predictions", text)

    def test_lede(self):
        w = {"id": f"w-{SUN}", "lede": "taxes", "piece": f"r-{SUN}-1"}
        self.write([self.piece(1), w])
        issue.validate(self.h, SUN)
        self.assertEqual(edition.front(self.h, SUN)["lede"], {"id": f"w-{SUN}", "word": "taxes", "piece": f"r-{SUN}-1"})
        for bad, says in (({"lede": "Taxes"}, "five lowercase letters"), ({"lede": "xqzzy"}, "five lowercase letters"),
                          ({"piece": "r-nope"}, "must name the piece"), ({"id": "w-1999-01-01"}, f"needs id, w-{SUN}")):
            self.write([self.piece(1), {**w, **bad}])
            self.assertIn(says, self.errors())
        self.h.config.write_text("language: hu\n", encoding="utf-8")  # no Lede on a Hungarian page (R6)
        self.write([self.piece(1), w])
        self.assertIn("English page only", self.errors())
        self.assertNotIn("lede", edition.front(self.h, SUN)["labels"])

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_lede_marks_a_letter_as_often_as_the_word_has_it(self):
        learn_js = Path(__file__).resolve().parent.parent / "reader" / "learn.js"
        run = ("const fs = require('fs'), vm = require('vm'); const c = vm.createContext({ crypto: globalThis.crypto, TextEncoder });"
               f"vm.runInContext(fs.readFileSync({json.dumps(str(learn_js))}, 'utf8'), c);"
               "process.stdout.write(JSON.stringify([['spend','speed'],['spend','spade'],['spend','dense'],['eerie','geese']]"
               ".map(([w, g]) => vm.runInContext(`ledeScore(${JSON.stringify(w)}, ${JSON.stringify(g)})`, c))))")
        out = subprocess.run(["node", "-e", run], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout), [
            ["in", "in", "in", "no", "in"],  # the second e: spend has one, already in place
            ["in", "in", "no", "near", "near"],
            ["near", "near", "near", "near", "no"],
            ["no", "in", "near", "no", "in"]])

    def test_a_link_needs_an_earlier_piece_the_reader_opened(self):
        self.write([self.piece(1, SAT)], SAT)
        link = {"id": f"l-{SUN}-1", "link": f"r-{SUN}-1", "from": f"r-{SAT}-1", "prompt": "What happened?",
                "options": ["a", "b", "c"], "answer": 0}
        self.write([self.piece(1, thread="t-budget"), link])
        self.assertIn("one the reader opened", self.errors())
        self.opened(f"r-{SAT}-1")
        self.assertEqual(len(issue.validate(self.h, SUN)), 2)
        self.write([self.piece(1), link])
        self.assertIn("a link is on a piece with a thread", self.errors())

    def test_crossword(self):
        self.write([self.piece(1, SAT)], SAT)
        words = [{"answer": w, "clue": f"Clue {w}", "piece": f"r-{SAT}-1"} for w in WORDS]
        self.write([self.piece(1), {"id": f"x-{SUN}", "crossword": words}])
        self.assertIn("piece must name a piece of the past week the reader opened", self.errors())
        self.opened(f"r-{SAT}-1")
        self.assertEqual(len(issue.validate(self.h, SUN)), 2)
        self.write([self.piece(1, SAT), {"id": f"x-{SAT}", "crossword": words}], SAT)
        self.assertIn("the crossword is for Sunday's issue", self.errors(SAT))
        bad = words[:5] + [{"answer": "two words", "clue": "c", "piece": f"r-{SAT}-1"}, words[0]]
        self.write([self.piece(1), {"id": f"x-{SUN}", "crossword": bad}])
        text = self.errors()
        self.assertIn("one word of 3 to 9 letters", text)
        self.write([self.piece(1), {"id": f"x-{SUN}", "crossword": words[:6] + [words[0]]}])
        self.assertIn("in the crossword twice", self.errors())

    def test_a_missed_game_can_become_a_card(self):
        self.write([self.piece(1), self.predict(1, f"r-{SUN}-1")])
        issue.validate(self.h, SUN)
        nxt = "2026-11-23"
        self.write([self.piece(1, nxt), {"id": f"c-{nxt}-1", "card": "flip", "front": "F", "back": "B",
                                         "from": f"p-{SUN}-1"}], nxt)
        self.assertEqual(len(issue.validate(self.h, nxt)), 2)
        card = learn.due(self.h, [], f"r-{nxt}-1", datetime(2026, 11, 23, 9, tzinfo=timezone.utc))
        self.assertEqual(card["id"], f"c-{nxt}-1")
        self.assertIsNone(learn.due(self.h, [], f"r-{SUN}-1", datetime(2026, 11, 23, 9, tzinfo=timezone.utc)))


class LayoutTest(unittest.TestCase):
    def test_words_cross_and_the_grid_is_the_same_each_time(self):
        a, b = crossword.layout(WORDS), crossword.layout(WORDS)
        self.assertEqual(a, b)
        self.assertGreaterEqual(len(a["entries"]), crossword.MIN_WORDS)
        self.assertLessEqual(max(a["rows"], a["cols"]), crossword.SIDE)
        cells = {}
        for x in a["entries"]:
            for k, ch in enumerate(crossword.normal(WORDS[x["i"]])):
                at = (x["row"] + k * x["down"], x["col"] + k * (not x["down"]))
                self.assertEqual(cells.setdefault(at, ch), ch)


if __name__ == "__main__":
    unittest.main()
