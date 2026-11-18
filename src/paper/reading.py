"""The reading log, $PAPER_HOME/reads.jsonl, and what Claude learns from it.

Events, one a line, each with `t` (ISO time) and `id` (a piece):
- `seen`: the piece was on an issue page the reader opened;
- `open`: the reader view opened it (`external`: the site refused, the original opened instead);
- `read`: a heartbeat from the reader view, `ms` read since the last one and `progress`, how far
  down the article they have been (0 to 1);
- `keep`: `kept` true or false;
- `thread`: the story so far was shown above the piece, `hash` of its body.

A piece is finished when the reader got past FINISHED of it and spent at least a third of its
reading time on it at WPM words a minute, so a quick scroll to the end does not count.
"""

import hashlib
import json
from datetime import date, datetime, timedelta

from .home import Home
from .issue import all_pieces

FINISHED = 0.9
WPM = 250
RECENT = 14  # days of pieces in `news context`
WEEK = 7  # days of minutes per section


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
        s = out.setdefault(e["id"], {"seen": False, "opened": False, "progress": 0.0, "ms": 0, "kept": None, "shown": set()})
        ev = e.get("ev")
        if ev == "seen":
            s["seen"] = True
        elif ev == "open":
            s["seen"] = s["opened"] = True
        elif ev == "read":
            s["seen"] = s["opened"] = True
            s["ms"] += max(0, int(e.get("ms") or 0))
            s["progress"] = max(s["progress"], min(1.0, float(e.get("progress") or 0)))
        elif ev == "keep":
            s["kept"] = bool(e.get("kept"))
        elif ev == "thread" and e.get("hash"):
            s["shown"].add(e["hash"])
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


def context(h: Home, today: date | None = None) -> dict:
    """What `news context` reports: every piece of the last RECENT days, newest issue first, and
    minutes per section over the last WEEK days."""
    today = today or date.today()
    first = (today - timedelta(days=RECENT - 1)).isoformat()
    week = (today - timedelta(days=WEEK - 1)).isoformat()
    st = state(h)
    pieces = [p for p in all_pieces(h).values() if p["day"] >= first]
    pieces.sort(key=lambda p: (p["day"], p["id"]), reverse=True)
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
            "opened": bool(s and s["opened"]),
            "finished": finished(h, p["id"], s),
            "kept": kept(p, s),
            "min": round((s["ms"] if s else 0) / 60000),
        }
        if p.get("thread"):
            row["thread"] = p["thread"]
        rows.append(row)
        if p["day"] >= week and s:
            minutes[row["section"]] = minutes.get(row["section"], 0) + s["ms"]
    return {"pieces": rows, "minutes": {k: round(v / 60000) for k, v in minutes.items()}}
