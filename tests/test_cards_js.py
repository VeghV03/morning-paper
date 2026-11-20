"""The page's cards and running stories (reader/learn.js) agree with the Mac's: FSRS gives the same
due dates, the same card comes after a finished piece, and a story is left off, caught up on and
shown under Since you left on the same days (learn.py, reading.py, server.py)."""

import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paper import edition, learn, reading, server, vault
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain
LEARN = Path(__file__).resolve().parent.parent / "reader" / "learn.js"
RUN = r"""
const fs = require("fs"), vm = require("vm");
const [learn, input] = process.argv.slice(2);
const ctx = vm.createContext({ crypto: globalThis.crypto, TextEncoder, console });
vm.runInContext(fs.readFileSync(learn, "utf8"), ctx);
const { index, events, threads, day, nows, after } = JSON.parse(fs.readFileSync(input, "utf8"));
const out = { sched: {}, due: [], left: {}, moved: [] };
for (const [id, s] of Object.entries(ctx.schedule(index.cards, events))) out.sched[id] = s.card.due ?? null;
for (const now of nows) { const c = ctx.due(index.cards, events, after, now); out.due.push(c ? c.id : null); }
for (const th of threads) out.left[th.id] = ctx.leftOff(index, events, th, day);
out.moved = ctx.moved(index, events, threads, day, Object.keys(index.pieces).filter((id) => index.pieces[id].day === day))
  .map((m) => [m.thread.id, m.piece, m.new.map((x) => x.day)]);
out.to_card = ctx.toCard(index, events, day);
process.stdout.write(JSON.stringify(out));
"""


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class CardsAndStoriesParityTest(unittest.TestCase):
    def test_same_schedule_card_stories_and_to_card_as_python(self):
        h = Home(Path(tempfile.mkdtemp()))
        h.issues.mkdir()
        h.cache.mkdir()
        (h.root / "sections.md").write_text("World: news\nMind: ideas\n", encoding="utf-8")
        days = [f"2026-10-{d:02d}" for d in (1, 5, 12, 20, 28)] + ["2026-11-03"]
        words = {}
        for n, day in enumerate(days):
            rows = [{"id": f"r-{day}-1", "section": "world", "url": f"https://a.org/{n}a", "head": "A", "lead": "L.",
                     **({"thread": "t-budget"} if n % 2 == 0 else {})},
                    {"id": f"r-{day}-2", "section": "mind", "url": f"https://a.org/{n}b", "head": "B", "lead": "L."}]
            rows += [{"id": f"c-{day}-{k}", "card": "flip", "front": "Q?", "back": "A.", "from": f"r-{day}-{k % 2 + 1}"}
                     for k in range(1, 4) if day != days[-1]]  # the last issue's pieces have no card yet
            (h.issues / f"{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            for r in rows[:2]:
                words[r["id"]] = 300
                (h.cache / f"{r['id']}.json").write_text(json.dumps({"words": 300}), encoding="utf-8")
        h.threads.write_text("".join(json.dumps(t) + "\n" for t in [
            {"id": "t-budget", "title": "Budget", "since": "2026-10-01", "entries": [
                {"day": "2026-10-01", "text": "Tabled.", "piece": "r-2026-10-01-1"}, {"day": "2026-10-10", "text": "Debated."},
                {"day": "2026-10-12", "text": "Amended.", "piece": "r-2026-10-12-1"}, {"day": "2026-10-30", "text": "Passed."},
                {"day": "2026-11-02", "text": "Signed."}]},
            {"id": "t-strike", "title": "Strike", "since": "2026-10-05", "entries": [
                {"day": "2026-10-05", "text": "Called."}, {"day": "2026-11-01", "text": "Ended."}]}]), encoding="utf-8")

        rng = random.Random(7)
        t0 = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)
        events = [{"t": iso(t0), "ev": "open", "id": "r-2026-10-01-1"},
                  {"t": iso(t0 + timedelta(days=11, hours=2)), "ev": "open", "id": "r-2026-10-12-1"},
                  {"t": iso(t0 + timedelta(days=4)), "ev": "since", "id": "t-strike", "entries": 1, "upto": "2026-10-05", "gap": None},
                  {"t": iso(t0 + timedelta(days=33)), "ev": "read", "id": "r-2026-11-03-2", "ms": 600000, "progress": 1.0},
                  {"t": iso(t0 + timedelta(days=33)), "ev": "read", "id": "r-2026-11-03-1", "ms": 600000, "progress": 1.0},
                  {"t": iso(t0 + timedelta(days=33)), "ev": "mark", "id": "h-1", "piece": "r-2026-11-03-1", "kind": "highlight", "text": "A line."}]
        cards = sorted(learn.cards(h))
        for _ in range(60):
            when = t0 + timedelta(days=rng.randint(0, 60), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
            events.append({"t": iso(when), "ev": "review", "id": rng.choice(cards[:9]), "rating": rng.choice(["again", "good", "good"])})
        for e in events:
            (vault.append(h.marks, {k: v for k, v in e.items() if k != "ev"}) if e["ev"] == "mark" else vault.append(h.reads, e))

        small = edition.index(h, words, "2026-11-03")
        months = [json.loads((h.root / "edition" / "months" / f"{m}.json").read_text()) for m in small["months"]]
        index = {"steered": small["steered"], "pieces": {}, "cards": {}}
        for m in months:
            index["pieces"].update(m["pieces"])
            index["cards"].update(m["cards"])
        reviews = reading.reviews(h)
        py_sched = {cid: (round(s["card"].due.timestamp() * 1000) if s["first"] else None)
                    for cid, s in learn.schedule(h, reviews).items()}
        nows = [t0 + timedelta(days=d, hours=h_) for d, h_ in ((10, 9), (30, 20), (45, 7), (61, 12), (90, 0))]
        after = "r-2026-10-05-1"
        py_due = [(c["id"] if (c := learn.due(h, reviews, after, now)) else None) for now in nows]
        threads = [json.loads(line) for line in h.threads.read_text().splitlines()]
        day = "2026-11-03"
        py_left = {th["id"]: reading.left_off(h, th, day) for th in threads}
        pieces = [p for p in edition.load(h, day) if p["id"].startswith("r-")]
        py_moved = [[m["thread"]["id"], m["piece"]["id"] if m["piece"] else None, [x["day"] for x in m["new"]]]
                    for m in server.moved(h, day, [{**p, "day": day} for p in pieces])]
        py_to_card = reading.context(h, datetime.fromisoformat(day).date())["to_card"]

        tmp = Path(tempfile.mkdtemp())
        (tmp / "in.json").write_text(json.dumps({"index": index, "events": events, "threads": threads, "day": day, "after": after,
                                                 "nows": [round(n.timestamp() * 1000) for n in nows]}), encoding="utf-8")
        (tmp / "run.js").write_text(RUN, encoding="utf-8")
        out = subprocess.run(["node", str(tmp / "run.js"), str(LEARN), str(tmp / "in.json")], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        js = json.loads(out.stdout)
        self.assertGreater(sum(1 for v in py_sched.values() if v), 5)  # enough cards were reviewed to mean something
        self.assertEqual(js["sched"], py_sched)
        self.assertEqual(js["due"], py_due)
        self.assertTrue(any(py_due))
        self.assertEqual(js["left"], py_left)
        self.assertEqual(js["moved"], py_moved)
        self.assertEqual(js["to_card"], py_to_card)
        self.assertEqual(py_to_card, ["r-2026-11-03-2"])  # finished; its neighbour is marked


if __name__ == "__main__":
    unittest.main()
