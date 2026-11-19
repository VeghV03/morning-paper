"""The run reads the brief, never the record (D46, D47)."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from paper import brief, cloud, vault
from paper.home import Home

DAY = date(2026, 11, 20)
CODE = "K7QM-W4XR-P9ND-3HTB-ZC6F-VJ2E"


class BriefTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.h.issues.mkdir()
        (self.h.root / "sections.md").write_text("World: news\nMind: ideas | memory, judgement, sleep\n", encoding="utf-8")
        rows = [
            {"id": "r-1", "section": "world", "url": "https://a.org/1", "head": "Budget", "lead": "L.", "thread": "t-budget"},
            {"id": "r-2", "section": "mind", "url": "https://a.org/2", "head": "Sleep", "lead": "L.", "topic": "sleep", "fit": "fits"},
            {"id": "a-1", "answer": "h-q1", "text": "Because."},
        ]
        (self.h.issues / "2026-11-19.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        self.h.threads.write_text(json.dumps({"id": "t-budget", "title": "The budget", "entries": [
            {"day": "2026-11-19", "text": "Tabled.", "piece": "r-1"}, {"day": "2026-11-20", "text": "Passed."}]}) + "\n",
            encoding="utf-8")

    def write_brief(self, data):
        (self.h.root / brief.NAME).write_text(json.dumps(data), encoding="utf-8")

    def test_the_brief_steers_and_carries_marks_and_opens_but_no_counts(self):
        self.write_brief({"day": "2026-11-20", "made": "2026-11-19T21:00:00+01:00",
                          "steer": {"mind": {"order": ["sleep", "memory", "judgement"], "try": "judgement",
                                                    "tries": ["judgement", "sleep", "memory"], "silent": True}},
                          "marks": [{"id": "h-q1", "piece": "r-2", "kind": "question", "text": "Why?"},
                                    {"id": "h-q2", "piece": "r-2", "kind": "question", "text": "How?"}],
                          "opened": ["r-1"]})
        c = brief.context(self.h, DAY)
        self.assertEqual(c["steer"]["mind"], {"order": ["sleep", "memory", "judgement"], "try": "judgement",
                                               "tries": ["judgement", "sleep", "memory"], "silent": True})
        self.assertEqual([(m["id"], m["answered"]) for m in c["marks"]], [("h-q1", True), ("h-q2", False)])
        self.assertEqual({p["id"]: p["opened"] for p in c["pieces"]}, {"r-1": True, "r-2": False})
        self.assertEqual(c["minutes"], {})
        self.assertNotIn("min", c["pieces"][0])
        self.assertEqual(brief.followed(self.h, {"t-budget": json.loads(self.h.threads.read_text())}, "2026-11-21"),
                         {"t-budget": {"follows": True, "left_off": "2026-11-19", "new": 1}})

    def test_without_a_brief_the_draw_is_flat_and_nothing_is_followed(self):
        c = brief.context(self.h, DAY)
        self.assertEqual(sorted(c["steer"]["mind"]["order"]), ["judgement", "memory", "sleep"])
        self.assertFalse(c["steer"]["mind"]["silent"])
        self.assertNotIn("topics", c["steer"]["mind"])
        self.assertEqual(c["marks"], [])

    def test_the_run_leaves_the_record_files_alone(self):
        repo, out = Path(tempfile.mkdtemp()), Path(tempfile.mkdtemp())
        key = cloud.run_key(CODE)
        cloud.pack(self.h, out, repo, key)
        sealed = repo / "record" / "abc123" / "2026-11.jsonl.sealed"
        sealed.parent.mkdir(parents=True)
        sealed.write_bytes(cloud.seal(vault._derive(CODE), "record/abc123/2026-11.jsonl", b'{"ev":"open"}\n'))
        h2 = Home(Path(tempfile.mkdtemp()))
        cloud.unpack(h2, out, repo, key)  # a file under the record key does not stop the run
        cloud.pack(h2, out, repo, key)
        self.assertTrue(sealed.exists())
        self.assertFalse((h2.root / "record").exists())


if __name__ == "__main__":
    unittest.main()
