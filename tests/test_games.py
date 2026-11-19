import http.client
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

from paper import crossword, issue, learn, reading, server
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


class PlayTest(Base):
    """The game route and the pages over a real socket."""

    def setUp(self):
        super().setUp()
        os.environ["PAPER_HOME"] = str(self.root)
        self.h.digests.mkdir()
        for day, n in ((SAT, 1), (SUN, 1), (SUN, 2)):
            (self.h.digests / f"r-{day}-{n}.md").write_text("First paragraph.\n\nSecond.", encoding="utf-8")
        self.write([self.piece(1, SAT, digest=True)], SAT)
        self.opened(f"r-{SAT}-1")
        words = [{"answer": w, "clue": f"Clue {w}", "piece": f"r-{SAT}-1"} for w in WORDS]
        link = {"id": f"l-{SUN}-1", "link": f"r-{SUN}-2", "from": f"r-{SAT}-1", "prompt": "What happened?",
                "options": ["a", "b", "c"], "answer": 2}
        self.write([self.piece(1, digest=True), self.piece(2, digest=True, thread="t-budget"),
                    self.predict(1, f"r-{SUN}-1"), link, {"id": f"x-{SUN}", "crossword": words}])
        issue.validate(self.h, SUN)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.port = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        os.environ.pop("PAPER_HOME", None)

    def ask(self, method, path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request(method, path, json.dumps(body) if body is not None else None, {"Host": f"localhost:{self.port}"})
        r = c.getresponse()
        return r.status, r.read().decode()

    def test_a_prediction_holds_the_article_and_counts_once(self):
        status, page = self.ask("GET", f"/read/r-{SUN}-1")
        self.assertEqual(status, 200)
        self.assertIn("<article hidden>", page)
        self.assertIn('<h1 class=title data-title="Head 1">Head 1</h1>', page)
        self.assertIn("<title>Head 1</title>", page)
        self.assertNotIn('"answer"', page.split("const PAPER")[1].split("</script>")[0])
        self.assertEqual(self.ask("POST", "/game", {"id": f"p-{SUN}-1", "pick": 0}), (200, '{"answer": 1}'))
        self.assertEqual(self.ask("POST", "/game", {"id": f"p-{SUN}-1", "pick": 1})[0], 200)
        self.assertEqual(reading.games(self.h)[f"p-{SUN}-1"], {"pick": 0, "right": False})
        self.assertNotIn(f"p-{SUN}-1", reading.state(self.h))
        page = self.ask("GET", f"/read/r-{SUN}-1")[1]
        self.assertIn("<article>", page)
        self.assertIn('"pick": 0', page)
        games = reading.context(self.h, datetime(2026, 11, 22).date())["games"]
        self.assertEqual(next(g for g in games if g["id"] == f"p-{SUN}-1")["picked"], "a")

    def test_a_link_shows_the_story_so_far_once_answered(self):
        page = self.ask("GET", f"/read/r-{SUN}-2")[1]
        self.assertIn("<details class=thread hidden>", page)
        self.assertEqual(self.ask("POST", "/game", {"id": f"l-{SUN}-1", "skip": True})[0], 200)
        page = self.ask("GET", f"/read/r-{SUN}-2")[1]
        self.assertIn("<details class=thread>", page)  # nothing new since the piece they opened: Earlier only
        self.assertIn("<details class=earlier open>", page)
        self.assertEqual(reading.games(self.h)[f"l-{SUN}-1"], {"skipped": True})
        self.assertEqual(self.ask("POST", "/game", {"id": "l-nope", "pick": 0})[0], 404)

    def test_the_crossword(self):
        self.assertIn(f'href="/{SUN}/crossword"', self.ask("GET", f"/{SUN}")[1])
        self.assertIn(f'href="/{SUN}/crossword"', self.ask("GET", f"/{SUN}/done")[1])
        self.assertNotIn("crossword", self.ask("GET", f"/{SAT}")[1])
        status, page = self.ask("GET", f"/{SUN}/crossword")
        self.assertEqual(status, 200)
        self.assertIn(f'href="/read/r-{SAT}-1"', page)
        self.assertEqual(self.ask("GET", f"/{SAT}/crossword")[0], 404)
        x = f"x-{SUN}"
        self.assertEqual(self.ask("POST", "/game", {"id": x, "entry": 3, "word": "nope"})[0], 400)
        self.assertEqual(self.ask("POST", "/game", {"id": x, "entry": 3, "word": "vote"})[0], 204)
        self.assertEqual(self.ask("POST", "/game", {"id": x, "entry": 3, "word": "VOTE"})[0], 204)
        self.assertEqual(reading.games(self.h)[x], {"solved": {3}})
        self.assertEqual(sum(1 for e in reading.events(self.h) if e.get("ev") == "game"), 1)
        games = reading.context(self.h, datetime(2026, 11, 22).date())["games"]
        got = next(g for g in games if g["id"] == x)
        self.assertNotIn("VOTE", got["missed"])
        self.assertEqual(got["entries"] - 1, len(got["missed"]))


if __name__ == "__main__":
    unittest.main()
