"""What the reader learns from: marks they make in the reader, the cards Claude writes from them,
and the reviews that schedule those cards.

- marks.jsonl, one a line: `{"id": "h-…", "piece", "kind": "highlight" | "question", "text", "t"}`;
  a later `{"id", "deleted": true}` takes one back.
- Cards are rows of the issues (issue.py), written by Claude in the morning run.
- Reviews are `review` events in reads.jsonl: `{"ev": "review", "id": "c-…", "rating": "again" |
  "good"}`. FSRS replays them to say when each card is due. One due card follows a finished piece;
  at most NEW_A_DAY cards are seen for the first time a day.
- $PAPER_HOME/.fsrs.json: FSRS's memory parameters fitted to the reader's own reviews (D31), once
  a week, and kept only when they predict the most recent reviews better than the defaults.
"""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone

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
REFIT_DAYS = 7
HELD_OUT = 0.2  # the newest share of reviews a fit is judged on


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


def card_pieces(h: Home) -> dict[str, str]:
    """Per card id, the piece it comes from, through its mark or game."""
    m = marks(h)
    played = {**all_rows(h, "predict"), **all_rows(h, "link")}

    def source(c: dict) -> str:
        g = played.get(c.get("from"), {})
        return m.get(c.get("from"), {}).get("piece") or g.get("predict") or g.get("link") or c.get("from")

    return {cid: source(c) for cid, c in cards(h).items()}


def _when(t: str) -> datetime:
    return datetime.fromisoformat(t).astimezone(timezone.utc)


def _fit_path(h: Home):
    return h.root / ".fsrs.json"


def scheduler(h: Home) -> Scheduler:
    """The reader's own FSRS parameters when a fit won, else the defaults."""
    try:
        fitted = json.loads(_fit_path(h).read_text(encoding="utf-8")).get("parameters")
        if fitted:
            return Scheduler(parameters=fitted, learning_steps=(), relearning_steps=(), enable_fuzzing=False)
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return SCHEDULER


def _items(reviews: list[dict]):
    """FSRS training items, one per review after a card's first: the card's history up to it,
    with days between reviews. Returned with the time of their last review, oldest first."""
    from fsrs_rs_python import FSRSItem, FSRSReview

    by_card: dict[str, list] = {}
    for r in sorted(reviews, key=lambda r: r["t"]):
        if r.get("rating") in RATINGS:
            by_card.setdefault(r["id"], []).append(r)
    out = []
    for rs in by_card.values():
        hist, prev = [], None
        for r in rs:
            day = _when(r["t"]).astimezone().date()
            hist.append(FSRSReview(1 if r["rating"] == "again" else 3, (day - prev).days if prev else 0))
            prev = day
            if len(hist) > 1:
                out.append((r["t"], FSRSItem(list(hist))))
    return [item for _, item in sorted(out, key=lambda x: x[0])]


def refit(h: Home, reviews: list[dict], today: date | None = None) -> dict | None:
    """Once every REFIT_DAYS: fit FSRS to the older reviews, judge it against the defaults on the
    newest HELD_OUT of them, keep it only if it predicts them better. Never raises: a failed fit
    leaves the cards as they were."""
    today = today or date.today()
    try:
        last = json.loads(_fit_path(h).read_text(encoding="utf-8"))
        if (today - date.fromisoformat(last["fitted"])).days < REFIT_DAYS:
            return None
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        from fsrs_rs_python import DEFAULT_PARAMETERS, FSRS

        items = _items(reviews)
        cut = int(len(items) * (1 - HELD_OUT))
        train, test = items[:cut], items[cut:]
        if not train or not test:
            return None
        fitted = FSRS(DEFAULT_PARAMETERS).compute_parameters(train)
        mine, default = FSRS(fitted).evaluate(test).log_loss, FSRS(DEFAULT_PARAMETERS).evaluate(test).log_loss
        Scheduler(parameters=fitted)  # refuses parameters out of its bounds
        result = {"fitted": today.isoformat(), "reviews": len(reviews), "log_loss": round(mine, 4),
                  "default_log_loss": round(default, 4), **({"parameters": list(fitted)} if mine < default else {})}
    except Exception:  # noqa: BLE001 - the morning run goes on with the parameters it had
        return None
    _fit_path(h).write_text(json.dumps(result), encoding="utf-8")
    return result


def schedule(h: Home, reviews: list[dict]) -> dict[str, dict]:
    """Per card id: its FSRS card (`due`), when it was first reviewed, and its last review."""
    sched = scheduler(h)
    out: dict[str, dict] = {}
    for cid in cards(h):
        out[cid] = {"card": Card(), "first": None, "last": None}
    for r in sorted(reviews, key=lambda r: r["t"]):
        s = out.get(r["id"])
        rating = RATINGS.get(r.get("rating"))
        if not s or not rating:
            continue
        at = _when(r["t"])
        s["card"], _ = sched.review_card(s["card"], rating, at)
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
    pieces = card_pieces(h)

    def today(at: datetime | None) -> bool:
        return bool(at and at.astimezone().date() == local_day)

    open_cards = [(cid, s) for cid, s in sched.items()
                  if pieces.get(cid) != after and not today(s["last"])]
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
        "own_parameters": scheduler(h) is not SCHEDULER,
    }
