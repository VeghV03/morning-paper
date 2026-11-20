"""Since you left: the running stories a reader follows, from where they left each."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from paper import reading
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain

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

    def tearDown(self):
        os.environ.pop("PAPER_HOME", None)

    def write(self, day, rows):
        (self.h.issues / f"{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        (self.h.digests / "x").write_text("", encoding="utf-8")
        for r in rows:
            (self.h.digests / f"{r['id']}.md").write_text("Body.", encoding="utf-8")

    def piece(self, day, n, section="world", **kw):
        return {"id": f"r-{day}-{n}", "section": section, "url": f"https://a.org/{day}/{n}", "head": f"Head {day} {n}",
                "lead": "Lead.", "digest": True, **kw}

    def test_the_issue_opens_with_the_stories_that_moved(self):
        self.assertEqual([p["id"] for p in reading.order(self.h, SUN)], [f"r-{SUN}-2", f"r-{SUN}-1"])
        moved = reading.moved(self.h, SUN, [{**p, "day": SUN} for p in reading.order(self.h, SUN)])
        self.assertEqual({m["thread"]["id"] for m in moved}, {"t-budget", "t-court"})  # not the strike, not the port

    def test_a_story_is_caught_up_to_the_issue_it_was_opened_from(self):
        reading.log(self.h, {"ev": "since", "id": "t-court", "entries": 1, "upto": SUN, "gap": 2})  # as the phone logs it
        # caught up only to the issue it was opened from, whatever day that happens
        self.assertEqual(reading.left_off(self.h, {"id": "t-court", "entries": []}, "9999-12-31"), SUN)

    def test_context_names_where_the_reader_left_each_story(self):
        from paper import issue

        mine = reading.followed(self.h, issue.threads(self.h), "9999-12-31")
        self.assertEqual(mine["t-budget"], {"follows": True, "left_off": FRI, "new": 2})
        self.assertEqual(mine["t-strike"], {"follows": True, "left_off": FRI, "new": 0})
        self.assertNotIn("t-port", mine)

    def test_a_named_story_leads_with_its_newest_updates(self):
        from paper import cli

        self.assertEqual(cli.main(["follow", "t-nope"]), 1)
        self.assertEqual(cli.main(["follow", "t-port", "t-port"]), 0)
        self.assertEqual(cli.main(["follow", "t-port"]), 0)
        self.assertEqual(sum(e.get("ev") == "follow" for e in reading.events(self.h)), 1)

        stories = reading.followed(self.h, reading.stories(self.h), SUN)
        self.assertEqual(stories["t-port"], {"follows": True, "new": 1})

        reading.log(self.h, {"ev": "since", "id": "t-port", "entries": 1, "upto": SUN, "gap": None})
        self.assertEqual(reading.left_off(self.h, reading.stories(self.h)["t-port"], "2026-11-23"), SUN)


if __name__ == "__main__":
    unittest.main()
