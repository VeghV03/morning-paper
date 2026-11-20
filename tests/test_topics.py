"""The topic model of the steered sections, the morning draw, the why line and "less of this"
(D25 to D32)."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from paper import config, learn, reading, topics, vault
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain

DAY = "2026-11-19"
T = config.LABELS["en"]


def at(day: str, hour: int = 8) -> str:
    return datetime.fromisoformat(f"{day}T{hour:02d}:00:00").astimezone().isoformat()


def before(n: int) -> str:
    return (date.fromisoformat(DAY) - timedelta(days=n)).isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.h.issues.mkdir()
        self.h.digests.mkdir()
        self.h.sections.write_text("World: news\nIdeas: essays | power, taste, method\n", encoding="utf-8")
        self.issues: dict[str, list] = {}

    def piece(self, day, n, topic, fit="fits", section="ideas"):
        row = {"id": f"r-{day}-{n}", "section": section, "url": f"https://a.org/{day}/{n}", "head": f"Head {n}",
               "lead": "Lead.", "digest": True, **({"topic": topic, "fit": fit} if topic else {})}
        self.issues.setdefault(day, []).append(row)
        (self.h.issues / f"{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in self.issues[day]),
                                                    encoding="utf-8")
        (self.h.digests / f"{row['id']}.md").write_text("Body " * 10, encoding="utf-8")
        return row["id"]

    def ev(self, day, ev, pid, **kw):
        vault.append(self.h.reads, {"t": at(day), "ev": ev, "id": pid, **kw})

    def finish(self, day, pid):
        self.ev(day, "open", pid)
        self.ev(day, "read", pid, ms=60000, progress=1.0)

    def est(self, topic):
        a, b = topics.estimate(topics.evidence(self.h, topics.start_of(DAY))["ideas"][topic], topics.start_of(DAY))
        return a / (a + b)


class TopicsTest(Base):
    def test_finishing_counts_more_than_opening_and_passing_counts_against(self):
        for n, (topic, outcome) in enumerate([("power", "finish"), ("taste", "open"), ("method", "pass")]):
            pid = self.piece(before(1), n, topic)
            self.ev(before(1), "look", pid)
            if outcome == "finish":
                self.finish(before(1), pid)
            elif outcome == "open":
                self.ev(before(1), "open", pid)
        self.assertGreater(self.est("power"), self.est("taste"))
        self.assertGreater(self.est("taste"), self.est("method"))
        self.assertAlmostEqual(self.est("taste"), (1 + 0.25 * 0.5 ** (16 / 24 / 30)) / (2 + 0.5 ** (16 / 24 / 30)), places=6)

    def test_on_the_page_but_never_on_screen_is_no_trial(self):
        pid = self.piece(before(1), 1, "power")
        self.ev(before(1), "seen", pid)
        self.assertEqual(topics.evidence(self.h, topics.start_of(DAY))["ideas"]["power"].trials, [])

    def test_evidence_fades_with_a_30_day_half_life(self):
        old, new = self.piece(before(60), 1, "power"), self.piece(before(1), 2, "taste")
        for day, pid in ((before(60), old), (before(1), new)):
            self.ev(day, "look", pid)
            self.finish(day, pid)
        a, b = topics.estimate(topics.evidence(self.h, topics.start_of(DAY))["ideas"]["power"], topics.start_of(DAY))
        self.assertAlmostEqual(a - 1, 0.25, places=2)  # about two half-lives
        self.assertGreater(self.est("taste"), self.est("power"))

    def test_less_of_this_is_three_misses_and_can_be_taken_back(self):
        pid = self.piece(before(1), 1, "power")
        self.ev(before(1), "look", pid)
        self.finish(before(1), pid)
        liked = self.est("power")
        self.ev(before(1), "less", pid)
        self.assertLess(self.est("power"), 0.5)
        self.ev(before(1), "less_undo", pid)
        self.assertAlmostEqual(self.est("power"), liked)

    def test_a_card_remembered_adds_half_a_success_once(self):
        pid = self.piece(before(3), 1, "power")
        self.ev(before(3), "look", pid)
        card = {"id": f"c-{before(2)}-1", "from": pid, "front": "Q", "back": "A"}
        self.issues.setdefault(before(2), []).append(card)
        (self.h.issues / f"{before(2)}.jsonl").write_text(json.dumps(card) + "\n", encoding="utf-8")
        plain = self.est("power")
        for d in (2, 1):
            self.ev(before(d), "review", card["id"], rating="good")
        trials = topics.evidence(self.h, topics.start_of(DAY))["ideas"]["power"].trials
        self.assertEqual([t[1] for t in trials], [0.0, topics.RECALL])
        self.assertGreater(self.est("power"), plain)

    def test_the_record_is_read_as_it_stood_that_morning(self):
        pid = self.piece(before(1), 1, "power")
        self.ev(before(1), "look", pid)
        self.ev(DAY, "open", pid)  # read later the same day: not in that morning's draw
        self.assertEqual(topics.evidence(self.h, topics.start_of(DAY))["ideas"]["power"].showings, ["passed"])

    def test_the_draw_is_the_same_all_morning_and_its_try_is_the_least_known(self):
        for d in range(1, 6):
            pid = self.piece(before(d), 1, "power")
            self.ev(before(d), "look", pid)
            self.finish(before(d), pid)
            pid = self.piece(before(d), 2, "taste")
            self.ev(before(d), "look", pid)
        first = topics.draw(self.h, DAY)["ideas"]
        self.assertEqual(topics.draw(self.h, DAY)["ideas"], first)
        self.assertEqual(sorted(first["order"]), ["method", "power", "taste"])
        self.assertEqual(first["try"], "method")  # never shown
        self.assertEqual(first["topics"]["method"], {"estimate": 0.5, "evidence": 0.0})
        self.assertNotIn("world", topics.draw(self.h, DAY))  # news is not steered

    def test_the_try_is_the_topic_with_least_evidence_not_the_most_uncertain(self):
        for n, topic in enumerate(["power", "power"], 1):  # passed twice, ten days ago
            self.ev(before(10), "look", self.piece(before(10), n, topic))
        pid = self.piece(before(1), 1, "taste")  # finished once and passed once, yesterday
        self.ev(before(1), "look", pid)
        self.finish(before(1), pid)
        self.ev(before(1), "look", self.piece(before(1), 2, "taste"))
        for n in (3, 4, 5):
            pid = self.piece(before(1), n, "method")
            self.ev(before(1), "look", pid)
            self.finish(before(1), pid)
        draw = topics.draw(self.h, DAY)["ideas"]
        self.assertLess(draw["topics"]["power"]["evidence"], draw["topics"]["taste"]["evidence"])
        self.assertEqual(draw["try"], "power")  # taste sits nearer a half, but rests on more

    def test_context_carries_the_draw_and_the_silent_rule(self):
        self.piece(before(1), 1, "power")
        steer = reading.context(self.h, date.fromisoformat(DAY))["steer"]["ideas"]
        self.assertEqual(set(steer), {"order", "try", "tries", "topics", "silent"})
        self.assertEqual(steer["try"], steer["tries"][0])


class WhyTest(Base):
    def line(self, pid, fit=None):
        day = pid[2:12]
        p = next(x for x in self.issues[day] if x["id"] == pid)
        return topics.why(self.h, {**p, "day": day, **({"fit": fit} if fit else {})}, T)

    def test_each_case_reads_true(self):
        today = self.piece(DAY, 1, "power")
        self.assertEqual(self.line(today), "Something new: you haven't read about power here yet.")
        p1 = self.piece(before(3), 1, "power")
        self.ev(before(3), "look", p1)
        self.assertEqual(self.line(today, "tries"), "Trying power again: you passed your last piece on it.")
        self.ev(before(3), "open", p1)
        self.assertEqual(self.line(today), "You opened your last piece on power.")
        p2 = self.piece(before(2), 1, "power")
        self.ev(before(2), "look", p2)
        self.finish(before(2), p2)
        self.assertEqual(self.line(today), "You finished 1 of your last 2 pieces on power.")
        self.ev(before(1), "less", p2)
        self.assertEqual(self.line(today, "tries"),
                         f"Trying power again, though you asked for less of it on {before(1)}.")
        self.assertIsNone(self.line(self.piece(DAY, 2, None, section="world")))

    def test_every_label_has_both_languages(self):
        keys = [k for k in T if k.startswith("why_") or k.startswith("less")]
        for lang in config.LABELS:
            for k in keys:
                self.assertIn(k, config.LABELS[lang], f"{lang}: {k}")
                config.LABELS[lang][k].format(topic="x", k=1, n=2, date=DAY)


class FitTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))

    def reviews(self, cards=30):
        out, start = [], datetime(2026, 9, 1).astimezone()
        for c in range(cards):
            when = start + timedelta(days=c % 7)
            for k, gap in enumerate((0, 1, 3, 7, 15)):
                when += timedelta(days=gap)
                out.append({"ev": "review", "id": f"c-{c}", "t": when.isoformat(),
                            "rating": "again" if (c + k) % 5 == 0 else "good"})
        return out

    def test_a_fit_is_kept_only_if_it_predicts_better_and_runs_weekly(self):
        result = learn.refit(self.h, self.reviews(), date(2026, 11, 19))
        self.assertIsNotNone(result)
        self.assertEqual("parameters" in result, result["log_loss"] < result["default_log_loss"])
        self.assertEqual(learn.scheduler(self.h) is not learn.SCHEDULER, "parameters" in result)
        self.assertIsNone(learn.refit(self.h, self.reviews(), date(2026, 11, 22)))  # within the week
        self.assertIsNotNone(learn.refit(self.h, self.reviews(), date(2026, 11, 26)))

    def test_too_few_reviews_change_nothing(self):
        self.assertIsNone(learn.refit(self.h, self.reviews(1)[:1]))
        self.assertFalse((self.h.root / ".fsrs.json").exists())
        self.assertIs(learn.scheduler(self.h), learn.SCHEDULER)


if __name__ == "__main__":
    unittest.main()
