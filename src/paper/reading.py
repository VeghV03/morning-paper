"""The reading log, $PAPER_HOME/reads.jsonl, and what Claude learns from it.

Events, one a line, each with `t` (ISO time) and `id` (a piece):
- `seen`: the piece was on an issue page the reader opened;
- `look`: its headline was on screen for LOOK_MS while the page was in front;
- `open`: the reader view opened it (`external`: the site refused, the original opened instead);
- `read`: a heartbeat from the reader view, `ms` read since the last one and `progress`, how far
  down the article they have been (0 to 1);
- `keep`: `kept` true or false;
- `thread`: the story so far was shown above the piece, `hash` of its body (before entries);
- `since`: the reader opened a running story's update (`id` t-…), from its own page or above a
  piece (`piece`): `entries`, how many were new to them, `upto`, the day of the issue it was
  shown in, and `gap`, the days from where they had left it to that day. It moves where they
  left the story to `upto`: opening an old issue's story catches them up only to that issue;
- `review`: a card (`id` c-…) was answered, `rating` again or good (learn.py);
- `game`: a prediction or link (`id` p-… or l-…) was answered, `pick` and `right`, or `skipped`;
  or a crossword (`id` x-…) word was solved, `entry` its index. Only the first answer counts.

A piece is finished when the reader got past FINISHED of it and spent at least a third of its
reading time on it at WPM words a minute, so a quick scroll to the end does not count.
"""

import hashlib
import json
from datetime import date, datetime, timedelta

from . import crossword, learn
from .home import Home
from .issue import all_pieces, all_rows, sections

FINISHED = 0.9
WPM = 250
RECENT = 14  # days of pieces in `news context`
WEEK = 7  # days of minutes per section
LOOK_MS = 2000  # a headline on screen this long, with the page in front, was looked at (x4r U16)
STEER = 28  # days of showings the steering rules count (x4r U9)
PASSED = 4  # a topic whose last PASSED showings were not opened is passed over (x4r U18)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(h: Home, event: dict) -> None:
    h.reads.parent.mkdir(parents=True, exist_ok=True)
    with h.reads.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": now(), **event}, ensure_ascii=False) + "\n")


def events(h: Home) -> list[dict]:
    if not h.reads.exists():
        return []
    out = []
    for line in h.reads.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue  # a line cut short by a crash
        if isinstance(e, dict) and isinstance(e.get("id"), str):
            out.append(e)
    return out


def body_hash(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def state(h: Home) -> dict[str, dict]:
    """Per piece id: seen, opened, progress, ms, kept, and the thread hashes shown."""
    out: dict[str, dict] = {}
    for e in events(h):
        ev = e.get("ev")
        if ev in ("review", "game", "since"):
            continue
        s = out.setdefault(e["id"], {"seen": False, "looked": False, "opened": False, "progress": 0.0, "ms": 0, "kept": None, "shown": set()})
        if ev == "seen":
            s["seen"] = True
        elif ev == "look":
            s["seen"] = s["looked"] = True
        elif ev == "open":
            s["seen"] = s["looked"] = s["opened"] = True
        elif ev == "read":
            s["seen"] = s["looked"] = s["opened"] = True
            s["ms"] += max(0, int(e.get("ms") or 0))
            s["progress"] = max(s["progress"], min(1.0, float(e.get("progress") or 0)))
        elif ev == "keep":
            s["kept"] = bool(e.get("kept"))
        elif ev == "thread" and e.get("hash"):
            s["shown"].add(e["hash"])
    return out


def left_off(h: Home, th: dict, before: str, pieces: dict | None = None, st: dict | None = None) -> str | None:
    """The day the reader last caught up on a running story, counting only what happened before
    the day `before`: the newest day of a piece of it they opened, or the day they opened its
    update. None when they never did, so the story is not theirs."""
    pieces = all_pieces(h) if pieces is None else pieces
    st = state(h) if st is None else st
    mine = {x.get("piece") for x in th.get("entries") or [] if isinstance(x, dict)}
    mine |= {pid for pid, p in pieces.items() if p.get("thread") == th["id"]}
    days = [pieces[pid]["day"] for pid in mine if pid in pieces and st.get(pid, {}).get("opened")]
    days += [str(e.get("upto") or e["t"][:10]) for e in events(h) if e.get("ev") == "since" and e["id"] == th["id"]]
    days = [d for d in days if d < before]
    return max(days) if days else None


def since(th: dict, left: str | None, upto: str) -> list[dict]:
    """The story's entries after `left` up to `upto`, newest first."""
    return [x for x in reversed(th.get("entries") or []) if (left or "") < x["day"] <= upto]


def gap(left: str | None, day: str) -> int | None:
    return (date.fromisoformat(day) - date.fromisoformat(left)).days if left else None


def followed(h: Home, threads: dict, before: str) -> dict[str, dict]:
    """Per running story the reader follows (they opened a piece of it): where they left it and
    how many entries are new to them."""
    pieces, st, out = all_pieces(h), state(h), {}
    for tid, th in threads.items():
        left = left_off(h, th, before, pieces, st)
        if left:
            out[tid] = {"left_off": left, "new": len(since(th, left, "9999-12-31"))}
    return out


def words(h: Home, pid: str) -> int:
    """The article's length as the reader view saw it; 0 when it was never extracted."""
    digest = h.digests / f"{pid}.md"
    if digest.exists():
        return len(digest.read_text(encoding="utf-8").split())
    try:
        return int(json.loads((h.cache / f"{pid}.json").read_text(encoding="utf-8")).get("words") or 0)
    except (OSError, ValueError, AttributeError):
        return 0


def finished(h: Home, pid: str, s: dict | None) -> bool:
    if not s or s["progress"] < FINISHED:
        return False
    return s["ms"] >= words(h, pid) / WPM * 60000 / 3


def kept(piece: dict, s: dict | None) -> bool:
    """A saved link arrives kept, as on the X4; anything else is kept once the reader keeps it."""
    if s and s["kept"] is not None:
        return s["kept"]
    return bool(piece.get("saved"))


def reviews(h: Home) -> list[dict]:
    return [e for e in events(h) if e.get("ev") == "review"]


def games(h: Home) -> dict[str, dict]:
    """Per game id, the first answer: `pick` and `right`, or `skipped`; a crossword's `solved`
    entries."""
    out: dict[str, dict] = {}
    for e in events(h):
        if e.get("ev") != "game":
            continue
        if isinstance(e.get("entry"), int):
            out.setdefault(e["id"], {"solved": set()})["solved"].add(e["entry"])
        elif e["id"] not in out:
            out[e["id"]] = {k: e[k] for k in ("pick", "right", "skipped") if k in e}
    return out


def context(h: Home, today: date | None = None) -> dict:
    """What `paper context` reports: every piece of the last RECENT days, newest issue first;
    minutes per section over the last WEEK days; the reader's marks; the finished pieces still
    without a card; the cards; and, for each steered section, what the steering rules see."""
    today = today or date.today()
    first = (today - timedelta(days=RECENT - 1)).isoformat()
    week = (today - timedelta(days=WEEK - 1)).isoformat()
    st = state(h)
    everything = all_pieces(h)
    pieces = [p for p in everything.values() if p["day"] >= first]
    pieces.sort(key=lambda p: (p["day"], p["id"]), reverse=True)
    m = learn.marks(h)
    answered = {a.get("answer") for a in all_rows(h, "answer").values()}
    carded = {c.get("from") for c in learn.cards(h).values()}
    marked = {x["piece"] for x in m.values()}
    rows, minutes = [], {}
    for p in pieces:
        s = st.get(p["id"])
        row = {
            "id": p["id"],
            "issue": p["day"],
            "section": "saved" if p.get("saved") else p.get("section"),
            "head": p.get("head"),
            "url": p.get("url"),
            "seen": bool(s and s["seen"]),
            "looked": bool(s and s["looked"]),
            "opened": bool(s and s["opened"]),
            "finished": finished(h, p["id"], s),
            "kept": kept(p, s),
            "min": round((s["ms"] if s else 0) / 60000),
        }
        for k in ("topic", "fit", "thread"):
            if p.get(k):
                row[k] = p[k]
        rows.append(row)
        if p["day"] >= week and s:
            minutes[row["section"]] = minutes.get(row["section"], 0) + s["ms"]
    return {
        "pieces": rows,
        "minutes": {k: round(v / 60000) for k, v in minutes.items()},
        "marks": [{"id": x["id"], "piece": x["piece"], "head": everything.get(x["piece"], {}).get("head"),
                   "kind": x["kind"], "text": x["text"], "answered": x["id"] in answered, "carded": x["id"] in carded}
                  for x in m.values()],
        "to_card": [r["id"] for r in rows if r["finished"] and r["id"] not in marked and r["id"] not in carded],
        "cards": learn.summary(h, reviews(h)),
        "games": _games(h, first, carded),
        "steer": steer(h, everything, st, marked, today),
    }


def _games(h: Home, first: str, carded: set) -> list[dict]:
    """The games of the last RECENT days and what the reader did with each, newest first."""
    played, out = games(h), []
    for what in ("predict", "link", "crossword"):
        for gid, g in all_rows(h, what).items():
            if g["day"] < first:
                continue
            got = played.get(gid, {})
            if what == "crossword":  # the words on the grid; missed only once the reader started it
                words = g.get("crossword") or []
                placed = [x["i"] for x in crossword.layout([w.get("answer") for w in words])["entries"]]
                solved = got.get("solved", set())
                out.append({"id": gid, "kind": what, "issue": g["day"], "entries": len(placed), "solved": len(solved),
                            "missed": [words[i].get("answer") for i in placed if i not in solved] if solved else []})
                continue
            row = {"id": gid, "kind": what, "issue": g["day"], "piece": g.get(what), "prompt": g.get("prompt"),
                   "answer": (g.get("options") or [None] * 3)[g.get("answer") or 0]}
            if "pick" in got:
                row.update(picked=g["options"][got["pick"]], right=got["right"])
            elif got.get("skipped"):
                row["skipped"] = True
            row["carded"] = gid in carded
            out.append(row)
    return sorted(out, key=lambda r: (r["issue"], r["id"]), reverse=True)


def steer(h: Home, everything: dict, st: dict, marked: set, today: date) -> dict:
    """Per steered section, over the last STEER days: each topic's showings (its headline was on
    screen for LOOK_MS, or it was opened), opens and good outcomes (finished, kept or marked); the
    topics passed over (their last PASSED showings not opened); the topics with a good outcome;
    and whether the section is silent: shown for STEER days or more, with nothing opened in the
    last STEER (x4r U21)."""
    first = (today - timedelta(days=STEER - 1)).isoformat()
    out = {}
    for sec in sections(h):
        if not sec.topics:
            continue
        ever = sorted((p for p in everything.values()
                       if p.get("section") == sec.id and st.get(p["id"], {}).get("looked")),
                      key=lambda p: (p["day"], p["id"]))
        shown = [p for p in ever if p["day"] >= first]
        topics = {t: {"shown": 0, "opened": 0, "good": 0} for t in sec.topics}
        last: dict[str, list[bool]] = {t: [] for t in sec.topics}
        for p in shown:
            t, s = p.get("topic"), st[p["id"]]
            if t not in topics:
                continue
            good = finished(h, p["id"], s) or kept(p, s) or p["id"] in marked
            topics[t]["shown"] += 1
            topics[t]["opened"] += s["opened"]
            topics[t]["good"] += good
            last[t].append(s["opened"])
        out[sec.id] = {
            "topics": topics,
            "passed_over": [t for t, xs in last.items() if len(xs) >= PASSED and not any(xs[-PASSED:])],
            "good": [t for t, x in topics.items() if x["good"]],
            "silent": bool(ever) and ever[0]["day"] < first and not any(st[p["id"]]["opened"] for p in shown),
        }
    return out
