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
- `follow`: the reader named a running story (`id` t-…) at setup. It is theirs from that day,
  with nothing of it read yet;
- `review`: a card (`id` c-…) was answered, `rating` again or good (learn.py);
- `game`: a prediction or link (`id` p-… or l-…) was answered, `pick` and `right`, or `skipped`;
  or a crossword (`id` x-…) word was solved, `entry` its index. Only the first answer counts;
- `less`: "less of this" on a steered piece, which turns its topic down in its section
  (topics.py); `less_undo` takes it back.

A piece is finished when the reader got past FINISHED of it and spent at least a third of its
reading time on it at WPM words a minute, so a quick scroll to the end does not count.
"""

import hashlib
import json
from datetime import date, datetime, timedelta

from . import crossword, learn, vault
from .home import Home
from .issue import Invalid, all_pieces, all_rows, kind, load, sections, threads

FINISHED = 0.9
WPM = 250
RECENT = 14  # days of pieces in `news context`
WEEK = 7  # days of minutes per section
LOOK_MS = 2000  # a headline on screen this long, with the page in front, was looked at (x4r U16)
STEER = 28  # days without an open that make a steered section silent (x4r U21)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(h: Home, event: dict) -> None:
    vault.append(h.reads, {"t": now(), **event})


def events(h: Home) -> list[dict]:
    return [e for e in vault.rows(h.reads) if isinstance(e.get("id"), str)]


def body_hash(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def state(h: Home, evs: list[dict] | None = None) -> dict[str, dict]:
    """Per piece id: seen, opened, progress, ms, kept, and the thread hashes shown; from `evs`
    when given (the record up to a moment), else the whole record."""
    out: dict[str, dict] = {}
    for e in events(h) if evs is None else evs:
        ev = e.get("ev")
        if ev in ("review", "game", "since", "follow", "less", "less_undo", "cover"):
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


def named(h: Home, before: str) -> set[str]:
    """The running stories the reader named by the day `before`, inclusive: named at setup, a
    story leads that morning's first issue."""
    return {e["id"] for e in events(h) if e.get("ev") == "follow" and e["t"][:10] <= before}


def followed(h: Home, threads: dict, before: str) -> dict[str, dict]:
    """Per running story the reader follows (they opened a piece of it, or named it): `follows`,
    where they left it, if anywhere, and how many entries are new to them."""
    pieces, st, mine, out = all_pieces(h), state(h), named(h, before), {}
    for tid, th in threads.items():
        left = left_off(h, th, before, pieces, st)
        if left or tid in mine:
            out[tid] = {"follows": True, **({"left_off": left} if left else {}), "new": len(since(th, left, "9999-12-31"))}
    return out


def stories(h: Home) -> dict[str, dict]:
    """The running stories; none when threads.jsonl is broken, which `paper publish` reports."""
    try:
        return threads(h)
    except Invalid:
        return {}


def moved(h: Home, day: str, pieces: list[dict]) -> list[dict]:
    """Since you left, as the page shows it (learn.js `moved`): each running story the reader
    follows that has news for them in the day's issue, newest first. `piece` is the issue's piece
    on it, if any; `new` its updates since they last caught up on it, before the day."""
    everything, st, mine, out = all_pieces(h), state(h), named(h, day), []
    for tid, th in stories(h).items():
        left = left_off(h, th, day, everything, st)
        if not left and tid not in mine:
            continue
        piece = next((p for p in pieces if p.get("thread") == tid and not p.get("saved")), None)
        new = since(th, left, day)
        if new or piece:
            out.append({"thread": th, "piece": piece, "new": new, "last": new[0]["day"] if new else day})
    return sorted(out, key=lambda m: m["last"], reverse=True)


def order(h: Home, day: str) -> list[dict]:
    """The issue's pieces in page order: Since you left's, the sections in sections.md's order,
    then saved links."""
    secs = sections(h)
    pieces = [r for r in load(h, day) if kind(r) == "piece"]
    first = [m["piece"] for m in moved(h, day, pieces) if m["piece"]]
    rank = {s.id: n for n, s in enumerate(secs)}
    placed = [p for p in pieces if not p.get("saved") and p not in first]
    placed.sort(key=lambda p: rank.get(p.get("section"), len(rank)))  # a renamed section's pieces last
    return first + placed + [p for p in pieces if p.get("saved")]


def story(h: Home, piece: dict) -> tuple[dict, str | None, list[dict], list[dict]] | None:
    """The running story above a piece (learn.js `story`): the thread, where the reader left it,
    the updates new to them and the rest, newest first. A reader who never opened the story sees
    the newest three, the rest under Earlier. The piece's own update is the piece, so it is left out."""
    th = stories(h).get(piece.get("thread"))
    if not th:
        return None
    left = left_off(h, th, piece["day"])
    mine = [x for x in reversed(th["entries"]) if x.get("piece") != piece["id"] and x["day"] <= piece["day"]]
    new = [x for x in mine if left < x["day"]] if left else mine[:3]
    return th, left, new, [x for x in mine if x not in new]


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
    entries; Lede's `tries` and whether it was `solved`, from each guess the record keeps (R7, R9)."""
    out: dict[str, dict] = {}
    words = {gid: g.get("lede") for gid, g in all_rows(h, "lede").items()}
    for e in events(h):
        if e.get("ev") != "game":
            continue
        if isinstance(e.get("guess"), str):
            g = out.setdefault(e["id"], {"tries": 0, "solved": False})
            if not g["solved"]:
                g["tries"] += 1
                g["solved"] = e["guess"] == words.get(e["id"])
        elif isinstance(e.get("entry"), int):
            out.setdefault(e["id"], {"solved": set()})["solved"].add(e["entry"])
        elif e["id"] not in out:
            out[e["id"]] = {k: e[k] for k in ("pick", "right", "skipped") if k in e}
    return out


def context(h: Home, today: date | None = None) -> dict:
    """What `paper context` reports: every piece of the last RECENT days, newest issue first;
    minutes per section over the last WEEK days; the reader's marks; the finished pieces still
    without a card; the cards; and, for each steered section, the morning's topic draw."""
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
        "steer": steer(h, everything, st, today),
    }


def _games(h: Home, first: str, carded: set, played: dict | None = None) -> list[dict]:
    """The games of the last RECENT days and what the reader did with each, newest first;
    `played` as `games` gives it, from the record unless the brief gives it."""
    played, out = games(h) if played is None else played, []
    for what in ("predict", "link", "crossword", "lede"):
        for gid, g in all_rows(h, what).items():
            if g["day"] < first:
                continue
            got = played.get(gid, {})
            if what == "lede":  # the word, and how it went once played
                out.append({"id": gid, "kind": what, "issue": g["day"], "piece": g.get("piece"), "word": g.get("lede"),
                            **{k: got[k] for k in ("tries", "solved") if k in got}})
                continue
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


def steer(h: Home, everything: dict, st: dict, today: date) -> dict:
    """Per steered section: the morning's topic draw (topics.py), and whether the section is
    silent: shown for STEER days or more, with nothing opened in the last STEER (x4r U21)."""
    from . import topics

    first = (today - timedelta(days=STEER - 1)).isoformat()
    out = topics.draw(h, today.isoformat())
    for sid, d in out.items():
        ever = sorted((p for p in everything.values() if p.get("section") == sid and st.get(p["id"], {}).get("looked")),
                      key=lambda p: (p["day"], p["id"]))
        shown = [p for p in ever if p["day"] >= first]
        d["silent"] = bool(ever) and ever[0]["day"] < first and not any(st[p["id"]]["opened"] for p in shown)
    return out
