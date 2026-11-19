"""The brief: what the morning run knows of the reader (D46, D47, step 3).

The reader's devices keep the reading record, sealed with the record key the run never holds.
Each time a device writes the record to the data repository it also writes `brief.json`, sealed
with the run key, holding only decisions:

- `day`: the issue the brief was made for;
- `steer`: per steered section, the topic order, the try, the topics from least evidence up
  (`tries`) and whether it is silent;
- `marks`: the reader's live highlights and questions, `{id, piece, kind, text}`;
- `opened`: the pieces of the last RECENT days the reader opened.

No reading times, no counts. `context` turns it into what `paper context` gives the morning
skill, with the same keys as on a computer that holds the record. When the reader has been away,
the run works from the last brief (D47). Cards, games and Since you left come with step 3's
second part; until then `to_card` and `games` are empty.
"""

import json
from datetime import date, timedelta

from . import learn, reading, topics
from .home import Home
from .issue import all_pieces, all_rows

NAME = "brief.json"


def load(h: Home) -> dict | None:
    path = h.root / NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def context(h: Home, today: date | None = None) -> dict:
    today = today or date.today()
    b = load(h) or {}
    first = (today - timedelta(days=reading.RECENT - 1)).isoformat()
    opened = {x for x in b.get("opened") or [] if isinstance(x, str)}
    everything = all_pieces(h)
    rows = []
    for p in sorted((p for p in everything.values() if p["day"] >= first), key=lambda p: (p["day"], p["id"]), reverse=True):
        row = {"id": p["id"], "issue": p["day"], "section": "saved" if p.get("saved") else p.get("section"),
               "head": p.get("head"), "url": p.get("url"), "opened": p["id"] in opened}
        row.update({k: p[k] for k in ("topic", "fit", "thread") if p.get(k)})
        rows.append(row)
    answered = {a.get("answer") for a in all_rows(h, "answer").values()}
    carded = {c.get("from") for c in learn.cards(h).values()}
    marks = [{"id": m["id"], "piece": m["piece"], "head": everything.get(m["piece"], {}).get("head"), "kind": m["kind"],
              "text": m["text"], "answered": m["id"] in answered, "carded": m["id"] in carded}
             for m in b.get("marks") or [] if isinstance(m, dict) and m.get("kind") in learn.KINDS and m.get("id")]
    drawn = topics.draw(h, today.isoformat())  # the flat draw, for a section the brief does not steer
    steer = {sid: {**d, **{k: v for k, v in (b.get("steer") or {}).get(sid, {}).items() if k in ("order", "try", "tries", "silent")}}
             for sid, d in drawn.items()}
    for d in steer.values():
        d.setdefault("silent", False)
        d.pop("topics", None)  # estimates are counts; the run gets the decisions (D47)
    return {"pieces": rows, "minutes": {}, "marks": marks, "to_card": [], "cards": learn.summary(h, []), "games": [],
            "steer": steer, "brief": {"day": b.get("day"), "made": b.get("made")}}


def followed(h: Home, threads: dict, before: str) -> dict[str, dict]:
    """reading.followed, from the brief's opened pieces: the day of the newest piece of a story
    the reader opened is where they left it."""
    opened = set((load(h) or {}).get("opened") or [])
    pieces, out = all_pieces(h), {}
    for tid, th in threads.items():
        mine = {x.get("piece") for x in th.get("entries") or [] if isinstance(x, dict)}
        mine |= {pid for pid, p in pieces.items() if p.get("thread") == tid}
        days = [pieces[pid]["day"] for pid in mine if pid in pieces and pid in opened and pieces[pid]["day"] < before]
        if days:
            left = max(days)
            out[tid] = {"follows": True, "left_off": left, "new": len(reading.since(th, left, "9999-12-31"))}
    return out
