"""What the reader learns from: marks they make in the reader, the cards Claude writes from them,
and the reviews that schedule those cards.

- marks.jsonl, one a line: `{"id": "h-…", "piece", "kind": "highlight" | "question", "text", "t"}`;
  a later `{"id", "deleted": true}` takes one back.
- Cards are rows of the issues (issue.py), written by Claude in the morning run.
- Reviews are `review` events in reads.jsonl: `{"ev": "review", "id": "c-…", "rating": "again" |
  "good"}`. FSRS replays them to say when each card is due. One due card follows a finished piece;
  at most NEW_A_DAY cards are seen for the first time a day.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from fsrs import Card, Rating, Scheduler

from . import vault
from .home import Home
from .issue import all_rows

NEW_A_DAY = 10
KINDS = ("highlight", "question")
MARK_CHARS = 4000  # a long paragraph, whole
# A card comes back after a day at the soonest: the paper is read once a day, so FSRS's
# minute-long learning steps would only ever fall inside the same sitting.
SCHEDULER = Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)
RATINGS = {"again": Rating.Again, "good": Rating.Good}


def _rows(path) -> list[dict]:
    return [r for r in vault.rows(path) if isinstance(r.get("id"), str)]


def marks(h: Home) -> dict[str, dict]:
    """The reader's live marks by id, oldest first."""
    out: dict[str, dict] = {}
    for m in _rows(h.marks):
        if m.get("deleted"):
            out.pop(m["id"], None)
        elif m.get("kind") in KINDS and m.get("text") and m.get("piece"):
            out[m["id"]] = m
    return out


def add_mark(h: Home, piece: str, kind: str, text: str) -> dict:
    text = " ".join(text.split())[:MARK_CHARS]
    mid = "h-" + hashlib.sha256(f"{piece}\n{kind}\n{text}".encode()).hexdigest()[:10]
    m = {"id": mid, "piece": piece, "kind": kind, "text": text,
         "t": datetime.now().astimezone().isoformat(timespec="seconds")}
    _append(h.marks, m)
    return m


def delete_mark(h: Home, mid: str) -> None:
    _append(h.marks, {"id": mid, "deleted": True})


def _append(path, row: dict) -> None:
    vault.append(path, row)


def cards(h: Home) -> dict[str, dict]:
    return all_rows(h, "card")


def _when(t: str) -> datetime:
    return datetime.fromisoformat(t).astimezone(timezone.utc)


def schedule(h: Home, reviews: list[dict]) -> dict[str, dict]:
    """Per card id: its FSRS card (`due`), when it was first reviewed, and its last review."""
    out: dict[str, dict] = {}
    for cid in cards(h):
        out[cid] = {"card": Card(), "first": None, "last": None}
    for r in sorted(reviews, key=lambda r: r["t"]):
        s = out.get(r["id"])
        rating = RATINGS.get(r.get("rating"))
        if not s or not rating:
            continue
        at = _when(r["t"])
        s["card"], _ = SCHEDULER.review_card(s["card"], rating, at)
        s["first"] = s["first"] or at
        s["last"] = at
    return out


def due(h: Home, reviews: list[dict], after: str, now: datetime | None = None) -> dict | None:
    """The one card to show below the piece `after`: the most overdue reviewed card, else a new
    one while fewer than NEW_A_DAY were new today. Never a card from that piece or reviewed today."""
    now = now or datetime.now(timezone.utc)
    local_day = now.astimezone().date()
    all_cards = cards(h)
    sched = schedule(h, reviews)
    m = marks(h)

    played = {**all_rows(h, "predict"), **all_rows(h, "link")}

    def source(c: dict) -> str:  # the piece a card comes from, through its mark or game
        g = played.get(c.get("from"), {})
        return m.get(c.get("from"), {}).get("piece") or g.get("predict") or g.get("link") or c.get("from")

    def today(at: datetime | None) -> bool:
        return bool(at and at.astimezone().date() == local_day)

    open_cards = [(cid, s) for cid, s in sched.items()
                  if source(all_cards[cid]) != after and not today(s["last"])]
    old = sorted((s["card"].due, cid) for cid, s in open_cards if s["first"] and s["card"].due <= now)
    if old:
        return all_cards[old[0][1]]
    new_today = sum(1 for s in sched.values() if today(s["first"]))
    if new_today >= NEW_A_DAY:
        return None
    new = sorted((all_cards[cid]["day"], cid) for cid, s in open_cards if not s["first"])
    return all_cards[new[0][1]] if new else None


def summary(h: Home, reviews: list[dict], now: datetime | None = None) -> dict:
    """For `paper context`: how many cards exist, are due, and were reviewed in the last week."""
    now = now or datetime.now(timezone.utc)
    sched = schedule(h, reviews)
    week = now - timedelta(days=7)
    return {
        "cards": len(sched),
        "due": sum(1 for s in sched.values() if s["first"] and s["card"].due <= now),
        "new": sum(1 for s in sched.values() if not s["first"]),
        "reviewed_week": sum(1 for r in reviews if r["id"] in sched and _when(r["t"]) >= week),
        "again_week": sum(1 for r in reviews if r["id"] in sched and r.get("rating") == "again" and _when(r["t"]) >= week),
    }
