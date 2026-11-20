"""The page's learner (reader/learn.js) weighs the record as topics.py does: the same evidence per
topic and the same why lines, from the same events. Only the draw's random numbers differ."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from paper import config, edition, topics, vault
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain
LEARN = Path(__file__).resolve().parent.parent / "reader" / "learn.js"
RUN = r"""
const fs = require("fs"), vm = require("vm");
const [learn, input] = process.argv.slice(2);
const ctx = vm.createContext({ crypto: globalThis.crypto, TextEncoder, console });
vm.runInContext(fs.readFileSync(learn, "utf8"), ctx);
const { index, events, at, pieces, labels, day, weeks } = JSON.parse(fs.readFileSync(input, "utf8"));
(async () => {
  const now = vm.runInContext(`startOf(${JSON.stringify(at)})`, ctx);
  const ev = ctx.evidence(index, events, now), out = { estimates: {}, why: {} };
  for (const [sid, ts] of Object.entries(ev))
    for (const [t, x] of Object.entries(ts)) out.estimates[`${sid}/${t}`] = ctx.estimate(x, now).map((v) => Math.round(v * 1e6) / 1e6);
  for (const id of pieces) out.why[id] = ctx.why(index, events, id, labels);
  out.brief = await ctx.brief(index, events, day);
  out.again = await ctx.brief(index, events, day);
  out.weeks = weeks.map(vm.runInContext("week", ctx));
  process.stdout.write(JSON.stringify(out));
})();
"""


def t(day, hh):
    return f"{day}T{hh:02d}:00:00+01:00"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class LearnParityTest(unittest.TestCase):
    def test_same_evidence_and_why_lines_as_python(self):
        h = Home(Path(tempfile.mkdtemp()))
        h.issues.mkdir()
        (h.root / "sections.md").write_text("World: news\nMind: ideas | sleep, memory, judgement\n", encoding="utf-8")
        issues = {
            "2026-11-10": [("r-1", "sleep", "fits"), ("r-2", "memory", "fits"), ("r-3", "judgement", "tries")],
            "2026-11-15": [("r-4", "sleep", "fits"), ("r-5", "judgement", "tries"), ("r-6", "memory", "fits")],
            "2026-11-20": [("r-7", "sleep", "fits"), ("r-8", "judgement", "tries"), ("r-9", "memory", "fits")],
        }
        for day, rows in issues.items():
            (h.issues / f"{day}.jsonl").write_text("".join(json.dumps(
                {"id": pid, "section": "mind", "url": f"https://a.org/{pid}", "head": pid, "lead": "L.", "topic": tp, "fit": fit}) + "\n"
                for pid, tp, fit in rows), encoding="utf-8")
        events = [
            {"t": t("2026-11-10", 8), "ev": "look", "id": "r-1"},
            {"t": t("2026-11-10", 8), "ev": "read", "id": "r-1", "ms": 90000, "progress": 1.0},  # finished
            {"t": t("2026-11-10", 9), "ev": "look", "id": "r-2"},
            {"t": t("2026-11-10", 9), "ev": "open", "id": "r-2"},  # opened, no further
            {"t": t("2026-11-10", 9), "ev": "look", "id": "r-3"},  # passed
            {"t": t("2026-11-11", 7), "ev": "less", "id": "r-3"},
            {"t": t("2026-11-15", 8), "ev": "look", "id": "r-4"},
            {"t": t("2026-11-15", 8), "ev": "keep", "id": "r-4", "kept": True},
            {"t": t("2026-11-15", 9), "ev": "look", "id": "r-6"},
            {"t": t("2026-11-15", 9), "ev": "less", "id": "r-6"},
            {"t": t("2026-11-15", 10), "ev": "less_undo", "id": "r-6"},
        ]
        mark = {"id": "h-1", "piece": "r-6", "kind": "highlight", "text": "A line.", "t": t("2026-11-15", 9)}
        old = {"ev": "mark", "id": "h-0", "piece": "r-0", "kind": "question", "text": "Long ago?", "t": t("2026-11-01", 9)}  # past 14 days
        for e in events:
            vault.append(h.reads, e)
        vault.append(h.marks, mark)
        small = edition.index(h, {}, "2026-11-20")
        months = [json.loads((h.root / "edition" / "months" / f"{m}.json").read_text()) for m in small["months"]]
        index = {"steered": small["steered"], "pieces": {k: v for m in months for k, v in m["pieces"].items()}}
        labels = config.LABELS["en"]
        at = "2026-11-20"
        py_est, now = {}, topics.start_of(at)
        for sid, ts in topics.evidence(h, now).items():
            for name, x in ts.items():
                py_est[f"{sid}/{name}"] = [round(v, 6) for v in topics.estimate(x, now)]
        pieces = [p for rows in issues.values() for p, _, _ in rows]
        everything = {pid: {**p, "day": p["day"]} for pid, p in index["pieces"].items()}
        py_why = {pid: topics.why(h, everything[pid], labels) for pid in pieces}

        tmp = Path(tempfile.mkdtemp())
        (tmp / "in.json").write_text(json.dumps({
            "index": index, "events": events + [{"ev": "mark", **mark}, old], "at": at, "weeks": [e["t"] for e in events[:1]] + ["2026-11-16T00:30:00+01:00", "2026-11-22T23:59:00Z"], "pieces": pieces,
            "labels": labels, "day": at}), encoding="utf-8")
        (tmp / "run.js").write_text(RUN, encoding="utf-8")
        out = subprocess.run(["node", str(tmp / "run.js"), str(LEARN), str(tmp / "in.json")], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        js = json.loads(out.stdout)
        self.assertEqual(js["estimates"], py_est)
        self.assertEqual(js["why"], py_why)
        b = js["brief"]
        self.assertEqual(sorted(b["steer"]["mind"]["order"]), ["judgement", "memory", "sleep"])
        self.assertEqual(b["steer"]["mind"]["order"], js["again"]["steer"]["mind"]["order"])  # the same day, the same draw
        self.assertFalse(b["steer"]["mind"]["silent"])
        self.assertEqual(sorted(b["steer"]["mind"]["tries"]), ["judgement", "memory", "sleep"])
        self.assertEqual(b["steer"]["mind"]["try"], b["steer"]["mind"]["tries"][0])
        self.assertEqual(b["marks"], [{k: mark[k] for k in ("id", "piece", "kind", "text")}])
        self.assertEqual(sorted(b["opened"]), ["r-1", "r-2"])  # opened within the 14 days before the 20th
        self.assertNotIn("ms", json.dumps(b))
        # weeks start on Monday, UTC: 10 Nov is a Tuesday; 00:30 on Monday the 16th in Budapest is still Sunday in UTC
        self.assertEqual(js["weeks"], ["2026-11-09", "2026-11-09", "2026-11-16"])


if __name__ == "__main__":
    unittest.main()
