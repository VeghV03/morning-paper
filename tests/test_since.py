"""Since you left: the running stories a reader follows, from where they left each."""

import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from paper import reading, server
from paper.home import Home

FRI, SAT, SUN = "2026-11-20", "2026-11-21", "2026-11-22"


class SinceTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.h = Home(self.root)
        self.h.issues.mkdir()
        self.h.digests.mkdir()
        os.environ["PAPER_HOME"] = str(self.root)
        (self.root / "sections.md").write_text("World: news\nScience: research\n", encoding="utf-8")
        self.write(FRI, [self.piece(FRI, 1), self.piece(FRI, 2), self.piece(FRI, 3)])
        self.write(SUN, [self.piece(SUN, 1), self.piece(SUN, 2, thread="t-budget", section="science")])
        stories = [
            # opened Friday, moved Saturday and Sunday, a piece today: leads the issue with Saturday's update
            {"id": "t-budget", "title": "The budget", "entries": [
                {"day": FRI, "text": "Tabled.", "piece": f"r-{FRI}-1"}, {"day": SAT, "text": "Sent back."},
                {"day": SUN, "text": "Passed.", "piece": f"r-{SUN}-2"}]},
            # opened Friday, moved Saturday, no piece today: a line of its own
            {"id": "t-court", "title": "The court", "entries": [
                {"day": FRI, "text": "Heard.", "piece": f"r-{FRI}-2"}, {"day": SAT, "text": "Ruled."}]},
            # opened Friday, has not moved: stays out
            {"id": "t-strike", "title": "The strike", "entries": [{"day": FRI, "text": "Began.", "piece": f"r-{FRI}-3"}]},
            # moved, but never opened: not the reader's
            {"id": "t-port", "title": "The port", "entries": [{"day": SAT, "text": "Closed."}]},
        ]
        self.h.threads.write_text("".join(json.dumps(t) + "\n" for t in stories), encoding="utf-8")
        for n in (1, 2, 3):
            reading.log(self.h, {"ev": "open", "id": f"r-{FRI}-{n}"})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.port = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        os.environ.pop("PAPER_HOME", None)

    def write(self, day, rows):
        (self.h.issues / f"{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        (self.h.digests / "x").write_text("", encoding="utf-8")
        for r in rows:
            (self.h.digests / f"{r['id']}.md").write_text("Body.", encoding="utf-8")

    def piece(self, day, n, section="world", **kw):
        return {"id": f"r-{day}-{n}", "section": section, "url": f"https://a.org/{day}/{n}", "head": f"Head {day} {n}",
                "lead": "Lead.", "digest": True, **kw}

    def get(self, path):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("GET", path, headers={"Host": f"localhost:{self.port}"})
        r = c.getresponse()
        return r.status, r.read().decode().split("<body>")[-1].split("<script>")[0]  # the page, not its style

    def since_events(self):
        return [e for e in reading.events(self.h) if e.get("ev") == "since"]

    def test_the_issue_opens_with_the_stories_that_moved(self):
        page = self.get(f"/{SUN}")[1]
        first = page.split("<section>")[1]
        self.assertIn("Since you left", first)
        self.assertIn(f'href="/read/r-{SUN}-2"', first)  # the piece moved up from Science
        self.assertIn('href="/thread/t-court', first)
        self.assertIn("Ruled.", first)
        self.assertNotIn("strike", page)
        self.assertNotIn("The port", page)
        self.assertNotIn("Science", page)  # its only piece moved up
        self.assertEqual([p["id"] for p in server.order(self.h, SUN)], [f"r-{SUN}-2", f"r-{SUN}-1"])
        self.assertEqual(self.get(f"/{SUN}")[1], page)  # the front page stays put through the day

    def test_a_piece_shows_what_is_new_since_the_reader_left(self):
        page = self.get(f"/read/r-{SUN}-2")[1]
        box = page.split("<details class=thread open>")[1].split("</details></details>")[0]
        self.assertIn("Sent back.", box.split("earlier")[0])
        self.assertIn("Tabled.", box.split("earlier")[1])
        self.assertNotIn("Passed.", box)  # today's update is the piece itself
        self.assertEqual([{k: e[k] for k in ("id", "piece", "entries", "upto", "gap")} for e in self.since_events()],
                         [{"id": "t-budget", "piece": f"r-{SUN}-2", "entries": 1, "upto": SUN, "gap": 2}])
        self.get(f"/read/r-{SUN}-2")
        self.assertEqual(len(self.since_events()), 1)

    def test_a_story_without_a_piece_has_its_own_page(self):
        status, page = self.get(f"/thread/t-court?day={SUN}")
        self.assertEqual(status, 200)
        self.assertIn("Ruled.", page.split("earlier")[0])
        self.assertEqual(self.since_events()[0]["entries"], 1)
        self.assertEqual(self.get("/thread/t-nope")[0], 404)
        # caught up only to the issue it was opened from, whatever day that happens
        self.assertEqual(reading.left_off(self.h, {"id": "t-court", "entries": []}, "9999-12-31"), SUN)

    def test_context_names_where_the_reader_left_each_story(self):
        from paper import issue

        mine = reading.followed(self.h, issue.threads(self.h), "9999-12-31")
        self.assertEqual(mine["t-budget"], {"left_off": FRI, "new": 2})
        self.assertEqual(mine["t-strike"], {"left_off": FRI, "new": 0})
        self.assertNotIn("t-port", mine)


if __name__ == "__main__":
    unittest.main()
