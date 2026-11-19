"""The issue as the phone reads it (D63 to D68), built by the cloud run when it publishes.

`edition/<day>.json` is the front page: the dateline, the labels, the sections in sections.md's
order with each piece's headline, lead and outlet, then saved links. `edition/<day>/<id>.json` is
one piece as the reader view shows it: the article's text, cleaned, or Claude's digest. A piece
whose site refused gets no text and opens at its outlet. `cloud pack` seals them like any other
file, so the phone opens them with the run key and nothing on the page parses HTML or Markdown.

Texts older than KEEP_DAYS go (D64); front pages stay, and their pieces then open at the outlet.
Since you left, games and answers need the reading record and wait for step 3 (D66, D68).
"""

import json
import re
import shutil
from datetime import date, timedelta
from typing import Callable

from . import config
from .home import Home
from .issue import kind, load, sections

KEEP_DAYS = 30
LABEL_KEYS = ("saved", "empty", "original", "digest", "next", "done", "no_issue", "months", "days")


def _dir(h: Home):
    return h.root / "edition"


def front(h: Home, day: str) -> dict:
    """The day's front page: sections in sections.md's order, then saved links, as the issue
    file lists them within each."""
    from .server import _host  # noqa: PLC0415 - the server pulls in much the run does not need

    pieces = [r for r in load(h, day) if kind(r) == "piece"]
    named = {s.id: s.name for s in sections(h)}
    rank = {sid: n for n, sid in enumerate(named)}
    item = lambda p: {"id": p["id"], "head": p["head"], "lead": p.get("lead", ""), "host": _host(p["url"])}  # noqa: E731
    out = []
    for sid in sorted(dict.fromkeys(p.get("section") for p in pieces if not p.get("saved")),
                      key=lambda s: rank.get(s, len(rank))):  # a renamed section's pieces last
        name = named.get(sid) or str(sid).replace("-", " ").capitalize()
        out.append({"name": name, "pieces": [item(p) for p in pieces if p.get("section") == sid and not p.get("saved")]})
    labels = config.labels(h)
    return {"day": day, "lang": config.language(h), "dateline": config.dateline(h, day),
            "labels": {k: labels[k] for k in LABEL_KEYS}, "sections": out,
            "saved": [item(p) for p in pieces if p.get("saved")]}


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
    (root / f"{day}.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    texts = 0
    for p in [r for r in load(h, day) if kind(r) == "piece"]:
        one = piece(h, p, day, extract)
        texts += "html" in one
        (root / day / f"{p['id']}.json").write_text(json.dumps(one, ensure_ascii=False), encoding="utf-8")
    cutoff = (date.fromisoformat(day) - timedelta(days=KEEP_DAYS)).isoformat()
    dropped = [d.name for d in root.iterdir() if d.is_dir() and d.name < cutoff]
    for name in dropped:
        shutil.rmtree(root / name)
    return {"pieces": sum(len(s["pieces"]) for s in page["sections"]) + len(page["saved"]), "texts": texts,
            "dropped": sorted(dropped)}
