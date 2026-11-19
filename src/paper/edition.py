"""The issue as the phone reads it (D63 to D68), built by the cloud run when it publishes.

`edition/<day>.json` is the front page: the dateline, the labels, the sections in sections.md's
order with each piece's headline, lead and outlet, then saved links. `edition/<day>/<id>.json` is
one piece as the reader view shows it: the article's text, cleaned, or Claude's digest. A piece
whose site refused gets no text and opens at its outlet. `cloud pack` seals them like any other
file, so the phone opens them with the run key and nothing on the page parses HTML or Markdown.

Texts older than KEEP_DAYS go (D64); front pages stay, and their pieces then open at the outlet.
`edition/index.json` lists every piece ever (day, section, topic, length) and the steered
sections, so the phone's learner reads one file, not every issue (step 3, D70). Answers to the
reader's questions are on the front page by mark id; the phone quotes the mark from its own record.
Since you left, cards and games wait for step 3's second part.
"""

import json
import re
import shutil
from datetime import date, timedelta
from typing import Callable

from . import config
from .home import Home
from .issue import all_pieces, kind, load, sections

KEEP_DAYS = 30
LABEL_KEYS = ("saved", "empty", "original", "digest", "next", "done", "no_issue", "months", "days", "answers",
              "kept", "nothing_kept", "keep", "keeping", "highlight", "question", "remove", "less", "undo",
              "less_done", "why_new", "why_less", "why_finished", "why_finished_one", "why_kept", "why_kept_one",
              "why_opened", "why_opened_one", "why_passed", "why_passed_one")
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


def index(h: Home, words: dict[str, int]) -> dict:
    """Every piece in every issue, for the phone's learner and Kept page; `words` adds the lengths
    measured today, and older pieces keep what the last index measured."""
    from .server import _host  # noqa: PLC0415

    path = _dir(h) / "index.json"
    old = json.loads(path.read_text(encoding="utf-8")).get("pieces", {}) if path.exists() else {}
    pieces = {}
    for pid, p in all_pieces(h).items():
        pieces[pid] = {"day": p["day"], "head": p["head"], "url": p["url"], "host": _host(p["url"]),
                       "words": words.get(pid, old.get(pid, {}).get("words", 0)),
                       **{k: p[k] for k in (*STEER_KEYS, "saved", "thread") if p.get(k)}}
    return {"steered": {s.id: list(s.topics) for s in sections(h) if s.topics}, "pieces": pieces}


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
    (root / "index.json").write_text(json.dumps(index(h, words), ensure_ascii=False), encoding="utf-8")
    # the front page last: a run that stops halfway leaves no page pointing at missing pieces
    (root / f"{day}.json").write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
    cutoff = (date.fromisoformat(day) - timedelta(days=KEEP_DAYS)).isoformat()
    dropped = [d.name for d in root.iterdir() if d.is_dir() and d.name < cutoff]
    for name in dropped:
        shutil.rmtree(root / name)
    return {"pieces": sum(len(s["pieces"]) for s in page["sections"]) + len(page["saved"]), "texts": texts,
            "dropped": sorted(dropped)}
