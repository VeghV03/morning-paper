"""The reader's 30 days, counted from a made-up data repository (T1 to T8)."""

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta, timezone
from pathlib import Path

from paper import cli, cloud, days, vault

CODE = "K7QM-W4XR-P9ND-3HTB-ZC6F-VJ2E"
CET = timezone(timedelta(hours=1))  # the run's 05:07 is 04:07 UTC
MINUTE = 60000


class DaysTest(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        # a 250-word piece is finished past 90% with 20 s on it
        self.seal(cloud.run_key(CODE), "home/edition/months/2026-11.json", json.dumps({"pieces": {
            "r-21": {"day": "2026-11-21", "words": 250}, "r-21b": {"day": "2026-11-21", "words": 250},
            "r-22": {"day": "2026-11-22", "words": 250}, "r-23": {"day": "2026-11-23", "words": 250}}}))
        events = [
            {"t": "2026-11-21T06:30:00.000Z", "ev": "seen", "id": "r-21"},
            {"t": "2026-11-21T06:31:00.000Z", "ev": "read", "id": "r-21", "ms": MINUTE, "progress": 0.95},
            {"t": "2026-11-21T06:40:00.000Z", "ev": "read", "id": "r-21b", "ms": MINUTE, "progress": 0.5},  # left halfway
            {"t": "2026-11-23T07:00:00.000Z", "ev": "read", "id": "r-22", "ms": MINUTE, "progress": 1},  # a day late
            {"t": "2026-11-23T07:05:00.000Z", "ev": "read", "id": "r-23", "ms": 2000, "progress": 1},  # a quick scroll
            {"t": "2026-11-23T07:06:00.000Z", "ev": "mark", "id": "h-1", "piece": "r-23", "kind": "highlight", "text": "x"},
        ]
        self.seal(vault._derive(CODE), "record/abc123/2026-11-16.jsonl", "".join(json.dumps(e) + "\n" for e in events))
        self.commit("2026-11-21T04:12:00+00:00", "Issue 2026-11-21")
        self.commit("2026-11-21T09:00:00+00:00", "Issue 2026-11-21")  # run again by hand: the first one counts
        self.commit("2026-11-22T05:30:00+00:00", "Issue 2026-11-22")  # 06:30 local: late
        self.commit("2026-11-23T04:10:00+00:00", "Edition of 2026-11-23 rebuilt")  # not the run's own commit
        self.commit("2026-11-23T07:07:00+00:00", "Record")

    def seal(self, key: bytes, rel: str, text: str):
        p = self.repo / (rel + cloud.SUFFIX)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(cloud.seal(key, rel, text.encode()))

    def commit(self, when: str, subject: str):
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@localhost", "commit", "-q",
                        "--allow-empty", "-m", subject],
                       check=True, env={**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})

    def tally(self, today="2026-11-23", code=CODE):
        return days.tally(self.repo, date(2026, 11, 21), date.fromisoformat(today), code, CET)

    def test_a_morning_delivered_opened_and_finished(self):
        self.assertEqual(self.tally()[0], {"day": "2026-11-21", "at": "05:12", "delivered": True, "opened": True, "finished": 1})

    def test_a_late_issue_is_no_delivery_and_catching_up_earns_the_day_nothing(self):
        self.assertEqual(self.tally()[1], {"day": "2026-11-22", "at": "06:30", "delivered": False, "opened": False, "finished": 0})

    def test_no_run_commit_is_no_delivery_and_a_quick_scroll_is_not_finished(self):
        self.assertEqual(self.tally()[2], {"day": "2026-11-23", "at": None, "delivered": False, "opened": True, "finished": 0})

    def test_the_cover_shown_that_day_is_opened(self):  # BR32
        late = {"t": "2026-11-22T23:30:00.000Z", "ev": "cover", "id": "2026-11-22"}  # 00:30 the next day, local
        self.seal(vault._derive(CODE), "record/def456/2026-11-16.jsonl", json.dumps(late) + "\n")
        self.assertFalse(self.tally()[1]["opened"])
        shown = {"t": "2026-11-22T07:00:00.000Z", "ev": "cover", "id": "2026-11-22"}
        self.seal(vault._derive(CODE), "record/def456/2026-11-16.jsonl", json.dumps(shown) + "\n")
        self.assertTrue(self.tally()[1]["opened"])

    def test_the_window_is_thirty_days_and_stops_at_today(self):
        self.assertEqual(len(self.tally()), 3)
        rows = self.tally(today="2027-01-31")
        self.assertEqual((len(rows), rows[-1]["day"]), (30, "2026-12-20"))
        self.assertTrue(days.table(rows).endswith("not passed"))

    def test_the_pass_mark(self):
        row = {"day": "d", "at": "05:12", "delivered": True, "opened": True, "finished": 1}
        miss = {"day": "d", "at": None, "delivered": False, "opened": False, "finished": 0}
        self.assertTrue(days.table([row] * 27 + [miss] * 3).endswith("\npassed"))
        self.assertTrue(days.table([row] * 26 + [miss] * 4).endswith("not passed"))
        self.assertNotIn("passed", days.table([row] * 29))  # no verdict before the 30th morning

    def test_another_code_opens_nothing(self):
        with self.assertRaises(cloud.Locked):
            self.tally(code="A" * 24)

    def test_the_command_prints_nothing_outside_a_terminal(self):
        buf = io.StringIO()  # not a terminal, like a session's shell
        with redirect_stdout(buf):
            code = cli.main(["days", "--repo", str(self.repo), "--from", "2026-11-21"])
        self.assertEqual((code, buf.getvalue()), (1, ""))


if __name__ == "__main__":
    unittest.main()
