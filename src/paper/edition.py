"""The issue as the phone reads it (D63 to D68), built by the cloud run when it publishes.

`edition/<day>.json` is the front page: the dateline, the labels, the sections in sections.md's
order with each piece's headline, lead and outlet, then saved links. `edition/<day>/<id>.json` is
one piece as the reader view shows it: the article's text, cleaned, or Claude's digest. A piece
whose site refused gets no text and opens at its outlet. `cloud pack` seals them like any other
file, so the phone opens them with the run key and nothing on the page parses HTML or Markdown.

Texts older than KEEP_DAYS go (D64); front pages stay, and their pieces then open at the outlet.
`edition/months/<YYYY-MM>.json` lists the month's pieces (day, section, topic, length, story) and
cards, so the phone's learner and cards read a file a month, not every issue (D70, D84). Only the
month being published is rewritten: a past month's file stays as it was. `edition/index.json` is
small: the steered sections and the months there are. Answers to the reader's questions are on the
front page by mark id; the phone quotes the mark from its own record. Running stories are read
from `threads.jsonl` itself. Games wait for step 3's second round (D80).
"""

import json
import re
import shutil
from datetime import date, timedelta
from typing import Callable

from . import config
from .home import Home
from .issue import DAY, all_pieces, all_rows, kind, load, sections

KEEP_DAYS = 30
LABEL_KEYS = ("saved", "empty", "original", "digest", "next", "done", "no_issue", "months", "days", "answers",
              "kept", "nothing_kept", "keep", "keeping", "highlight", "question", "remove", "less", "undo",
              "less_done", "why_new", "why_less", "why_finished", "why_finished_one", "why_kept", "why_kept_one",
              "why_opened", "why_opened_one", "why_passed", "why_passed_one", "since", "earlier", "show", "again", "good")
STEER_KEYS = ("section", "topic", "fit")


def _dir(h: Home):
    return h.root / "edition"


def front(h: Home, day: str) -> dict:
    """The day's front page: sections in sections.md's order, then saved links, as the issue
    file lists them within each."""
    from .server import _host  # noqa: PLC0415 - the server pulls in much the run does not need

    pieces = [r for r in load(h, day) if kind(r) == "piece"]
    named = {s.id: s.name for s in sections(h)}
    rank = {sid: n for n, sid in enumerate(named)}
    def item(p: dict) -> dict:
        return {"id": p["id"], "head": p["head"], "lead": p.get("lead", ""), "url": p["url"], "host": _host(p["url"]),
                **{k: p[k] for k in STEER_KEYS if p.get(k)}}

    out = []
    for sid in sorted(dict.fromkeys(p.get("section") for p in pieces if not p.get("saved")),
                      key=lambda s: rank.get(s, len(rank))):  # a renamed section's pieces last
        name = named.get(sid) or str(sid).replace("-", " ").capitalize()
        out.append({"name": name, "pieces": [item(p) for p in pieces if p.get("section") == sid and not p.get("saved")]})
    labels = config.labels(h)
    answers = [{"id": r["id"], "mark": r["answer"], "text": str(r.get("text", ""))}
               for r in load(h, day) if kind(r) == "answer" and r.get("answer")]
    return {"day": day, "lang": config.language(h), "dateline": config.dateline(h, day), "morning": config.morning(h),
            "labels": {k: labels[k] for k in LABEL_KEYS}, "answers": answers, "sections": out,
            "saved": [item(p) for p in pieces if p.get("saved")]}


def _words(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html).split())


CARD_KEYS = ("card", "front", "back", "prompt", "options", "answer", "from")


def _read(path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def index(h: Home, words: dict[str, int], day: str) -> dict:
    """Writes the month files the day touches (D84) and returns the small index. A month file holds
    every piece and card of its issues, for the phone's learner, cards and Kept page; `words` adds
    the lengths measured today, and older pieces keep what their month file measured. A past
    month's file is written once and then left alone."""
    from .server import _host  # noqa: PLC0415

    root = _dir(h) / "months"
    root.mkdir(parents=True, exist_ok=True)
    before = _read(_dir(h) / "index.json").get("pieces", {})  # the one index before D84
    pieces: dict[str, dict] = {}
    for pid, p in all_pieces(h).items():
        pieces.setdefault(p["day"][:7], {})[pid] = p
    cards: dict[str, dict] = {}
    for cid, c in all_rows(h, "card").items():
        cards.setdefault(c["day"][:7], {})[cid] = c
    for month in sorted(set(pieces) | set(cards)):
        path = root / f"{month}.json"
        if month != day[:7] and path.exists():
            continue
        old = {**before, **_read(path).get("pieces", {})}
        out = {"pieces": {pid: {"day": p["day"], "head": p["head"], "url": p["url"], "host": _host(p["url"]),
                                "words": words.get(pid, old.get(pid, {}).get("words", 0)),
                                **{k: p[k] for k in (*STEER_KEYS, "saved", "thread") if p.get(k)}}
                          for pid, p in pieces.get(month, {}).items()},
               "cards": {cid: {"day": c["day"], **{k: c[k] for k in CARD_KEYS if k in c}}
                         for cid, c in cards.get(month, {}).items()}}
        path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return {"steered": {s.id: list(s.topics) for s in sections(h) if s.topics},
            "months": sorted(p.stem for p in root.glob("*.json"))}


def piece(h: Home, p: dict, day: str, extract: Callable[[str], dict]) -> dict:
    """One piece for the reader view: {url, title, byline, html}, or {url} when there is no text."""
    from . import server  # noqa: PLC0415

    t, host = config.labels(h), server._host(p["url"])
    if (h.digests / f"{p['id']}.md").exists():
        d = server.digest(h, p)
        return {"url": p["url"], "title": p["head"], "byline": f"{t['digest']} {host}", "html": d["html"]}
    art = extract(p["url"])
    if not art.get("html"):
        return {"url": p["url"]}
    title = re.sub(r"\s+[|–—]\s+[^|–—]+$", "", art.get("title") or "") or p["head"]  # "Title | Site"
    byline = " · ".join(x for x in (host, server._authors(art.get("author"), p["url"]),
                                     server._when(h, art.get("date"), day)) if x)
    return {"url": p["url"], "title": title, "byline": byline, "html": server._body(art["html"], title)}


def build(h: Home, day: str, extract: Callable[[str], dict] | None = None) -> dict:
    """Writes the day's edition and drops texts older than KEEP_DAYS. Returns what it wrote."""
    if extract is None:
        from .server import extract  # noqa: PLC0415
    root = _dir(h)
    (root / day).mkdir(parents=True, exist_ok=True)
    page = front(h, day)
    texts, words = 0, {}
    for p in [r for r in load(h, day) if kind(r) == "piece"]:
        try:
            one = piece(h, p, day, extract)
        except Exception:  # noqa: BLE001 - one odd page must not stop the issue; it opens at its outlet
            one = {"url": p["url"]}
        texts += "html" in one
        words[p["id"]] = _words(one.get("html", ""))
        (root / day / f"{p['id']}.json").write_text(json.dumps(one, ensure_ascii=False), encoding="utf-8")
    (root / "index.json").write_text(json.dumps(index(h, words, day), ensure_ascii=False), encoding="utf-8")
    # the front page last: a run that stops halfway leaves no page pointing at missing pieces
    (root / f"{day}.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    cutoff = (date.fromisoformat(day) - timedelta(days=KEEP_DAYS)).isoformat()
    dropped = [d.name for d in root.iterdir() if d.is_dir() and DAY.match(d.name) and d.name < cutoff]
    for name in dropped:
        shutil.rmtree(root / name)
    return {"pieces": sum(len(s["pieces"]) for s in page["sections"]) + len(page["saved"]), "texts": texts,
            "dropped": sorted(dropped)}
