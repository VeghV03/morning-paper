"""`paper serve`: the issue and the reader on http://localhost:4747, and the reading log behind them.

- `/` the newest issue, `/<date>` any issue, `/kept` what the reader kept.
- `/read/<id>` the article in a clean reader view, built once from the page (trafilatura) and
  cached. A piece that continues a running story shows the story's updates above it: those since
  the reader last caught up, open, and the rest under Earlier. A site that refuses goes straight
  to the original.
- `/thread/<id>` a running story's updates, for one that moved without a piece in the issue.
- `/<date>/done` the end of an issue; `/<date>/crossword` Sunday's crossword; `/settings` the
  reader's own files. A piece with a prediction or a link asks it first (POST /game).
- `POST /log` reading heartbeats, `POST /keep/<id>` keep or let go, `POST /look` a headline on
  screen long enough, `POST /mark` a highlight or question (or its removal), `GET /card?after=<id>`
  the card due after a finished piece and `POST /review` its answer, `PUT /settings/<part>`.

The Mac is let in by its own address; a phone on the Wi-Fi pairs once with the QR code in
settings (`/pair`) and is let in by its key (phone.py). Everyone else gets the page that says so.
"""

import html
import json
import os
import re
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from http.cookies import SimpleCookie

from . import config, crossword, learn, net, phone, reading, settings
from .home import Home, home
from .issue import DAY, Invalid, all_pieces, all_rows, days, kind, load, sections, threads

PORT = int(os.environ.get("PAPER_PORT") or 4747)
ICON = Path(__file__).with_name("icon.png")
MAX_BODY = 64_000  # bytes; settings with every section and interest fit many times over
MIN_TEXT = 400  # characters; less is a cookie wall or a teaser, not the article
NO_FETCH = {"24.hu"}
e = html.escape


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


# the article


def extract(url: str) -> dict:
    """{title, author, date, html, text, words} of the article at `url`, as the reader view shows
    it; {} when the site refuses or the page holds no article."""
    if _host(url) in NO_FETCH:
        return {}
    import trafilatura

    try:
        raw = net.fetch(url).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - any failure means: read it on the site
        return {}
    body = trafilatura.extract(raw, url=url, output_format="html", include_comments=False,
                               include_tables=True, include_images=False, include_links=False)
    text = trafilatura.extract(raw, url=url, include_comments=False) or ""
    if not body or len(text) < MIN_TEXT:
        return {}
    meta = trafilatura.extract_metadata(raw, default_url=url)
    return {"title": getattr(meta, "title", None), "author": getattr(meta, "author", None),
            "date": getattr(meta, "date", None), "html": body, "text": text, "words": len(text.split())}


def article(h: Home, piece: dict) -> dict | None:
    """The piece's article from the cache, or extracted now and cached; None when there is none."""
    path = h.cache / f"{piece['id']}.json"
    if path.exists():
        cached = json.loads(path.read_text(encoding="utf-8"))
        return cached or None
    found = extract(piece["url"])
    found.pop("text", None)
    h.cache.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    return found or None


def digest(h: Home, piece: dict) -> dict:
    """A digest Claude wrote, as the reader view shows an article: paragraphs, `> ` lines quoted."""
    text = (h.digests / f"{piece['id']}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[-1]  # front matter is for Claude, not the reader
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    body = "".join(
        f"<blockquote>{e(' '.join(l.lstrip('> ') for l in b.splitlines()))}</blockquote>" if b.startswith(">")
        else f"<h2>{e(b.lstrip('# '))}</h2>" if b.startswith("#") else f"<p>{e(' '.join(b.splitlines()))}</p>"
        for b in blocks
    )
    return {"title": piece["head"], "html": body, "digest": True}


def _body(fragment: str, title: str = "") -> str:
    """trafilatura's HTML without its outer <html><body>, its <head> renamed to h2, and without
    the scraps some pages leave before the first paragraph (the title again, "Published")."""
    fragment = re.sub(r"</?(html|body|doc|main)[^>]*>", "", fragment)
    fragment = re.sub(r"<(/?)head\b[^>]*>", r"<\1h2>", fragment)
    try:
        import lxml.html

        root = lxml.html.fragment_fromstring(fragment, create_parent="div")
    except Exception:  # noqa: BLE001 - show it as it came
        return fragment
    els = list(root)
    lead = 0
    for el in els:  # before the first paragraph: the title again, "Published", a credit, "Listen"
        text = _plain(el)
        if el.tag == "p" and len(text) >= 40 and not _scrap(el):
            break
        if not (el.tag == "h1" or _scrap(el) or (title and text.lower().startswith(title.lower()[:40]))):
            break
        lead += 1
    tail = len(els)
    while tail > lead and len(els) - tail < 8 and _scrap(els[tail - 1], end=True):  # sign-ups, related links
        tail -= 1
    kept = [el for el in els[lead:tail] if not _credit(el)] or els
    return "".join(lxml.html.tostring(el, encoding="unicode") for el in kept) or fragment


def _plain(el) -> str:
    return " ".join(el.text_content().split())


# what pages leave around an article: photo credits, sign-ups, "support us"; English and Hungarian
CREDIT = re.compile(r"getty images|(\w+ ?/ ?){3}\w|\b(photo|photograph|credit|fotó|kép|borítókép)\s*:|\| [^|]*\b(afp|reuters|ap|epa)\b", re.I)
CALL = re.compile(r"newsletter|sign up (for|to|here|now)|subscribe (here|now|today)|subscribe to our|patreon|"
                  r"support us\b|support our (journalism|work|reporting)|hírlev|feliratkoz|iratkozz", re.I)  # said to the reader
RELATED = re.compile(r"Published|\bago\b|Publikálva", re.I)
SENTENCE = re.compile(r"[.!?…\"”»’']\)?$")


def _credit(el) -> bool:
    """A photo's credit, wherever it sits: the pictures are gone."""
    text = _plain(el)
    return el.tag == "p" and len(text.split()) <= 25 and not SENTENCE.search(text) and bool(CREDIT.search(text))


def _scrap(el, end: bool = False) -> bool:
    """A block that is not the article: empty; a short line that is no sentence (a credit, a
    dateline, "Advertisement:"); a credit or a call to sign up; a list of links; at the end, a
    heading with nothing under it."""
    text, words = _plain(el), len(_plain(el).split())
    if not text:
        return True
    if (words <= 60 and CREDIT.search(text)) or (words <= 40 and CALL.search(text)):
        return True
    if el.tag in ("ul", "ol"):  # at the top only "Published"; at the end, the outlet's related links
        return len(text) < 40 if not end else bool(RELATED.search(text))
    if re.fullmatch(r"h[1-6]", el.tag or ""):
        return words <= 15 and (end or len(text) < 40)
    if not end and text.endswith(":"):
        return False  # "Key developments on Nov. 17:" leads into what follows
    return words <= 14 and not SENTENCE.search(text)


# pages


def _threads(h: Home) -> dict[str, dict]:
    """The running stories; none when threads.jsonl is broken, which `paper publish` reports."""
    try:
        return threads(h)
    except Invalid:
        return {}


def moved(h: Home, day: str, pieces: list[dict]) -> list[dict]:
    """Since you left: each running story the reader follows that has news for them in the day's
    issue, newest first. `piece` is the issue's piece on it, if any; `new` its updates since they
    last caught up on it, before the day."""
    everything, st, out = all_pieces(h), reading.state(h), []
    for tid, th in _threads(h).items():
        left = reading.left_off(h, th, day, everything, st)
        if not left:
            continue
        piece = next((p for p in pieces if p.get("thread") == tid and not p.get("saved")), None)
        new = reading.since(th, left, day)
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


def _updates(h: Home, new: list[dict], old: list[dict]) -> str:
    """A story's updates, newest first: the new ones, then the rest folded under Earlier."""
    t = config.labels(h)
    li = lambda x: f"<li><span>{e(config.short_date(h, x['day']))}</span>{e(str(x['text']))}</li>"  # noqa: E731
    out = f"<ol class=updates>{''.join(map(li, new))}</ol>" if new else ""
    if old:
        out += f"<details class=earlier{'' if new else ' open'}><summary>{e(t['earlier'])}</summary><ol class=updates>{''.join(map(li, old))}</ol></details>"
    return out


def _caught_up(h: Home, th: dict, left: str | None, new: list[dict], upto: str, piece: str | None = None) -> None:
    """Log that the reader opened a story's new updates, shown in the issue of `upto`; once each."""
    if not new or any(x.get("ev") == "since" and x["id"] == th["id"] and x.get("upto") == upto for x in reading.events(h)):
        return
    event = {"ev": "since", "id": th["id"], "entries": len(new), "upto": upto, "gap": reading.gap(left, upto)}
    reading.log(h, {**event, "piece": piece} if piece else event)


def story(h: Home, piece: dict) -> tuple[dict, str | None, list[dict], list[dict]] | None:
    """The running story above a piece: the thread, where the reader left it, the updates new to
    them and the rest, newest first. A reader who never opened the story sees the newest three,
    the rest under Earlier. The piece's own update is the piece, so it is left out."""
    th = _threads(h).get(piece.get("thread"))
    if not th:
        return None
    left = reading.left_off(h, th, piece["day"])
    mine = [x for x in reversed(th["entries"]) if x.get("piece") != piece["id"] and x["day"] <= piece["day"]]
    new = [x for x in mine if left < x["day"]] if left else mine[:3]
    return th, left, new, [x for x in mine if x not in new]


def _page(h: Home, title: str, head: str, body: str, nav: str = "", script: str = "") -> str:
    return PAGE.format(lang=config.language(h), title=e(title), head=head, body=body, nav=nav, script=script)


def _json(data) -> str:
    """JSON safe inside a <script> element."""
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def issue_page(h: Home, day: str) -> str:
    t, dateline = config.labels(h), lambda d: config.dateline(h, d)
    secs = sections(h)
    rows = load(h, day)
    pieces = order(h, day)
    st = reading.state(h)
    for p in pieces:
        reading.log(h, {"ev": "seen", "id": p["id"]})
    stories = moved(h, day, pieces)
    for m in stories:
        if not m["piece"]:
            reading.log(h, {"ev": "seen", "id": m["thread"]["id"]})
    all_days = days(h)
    i = all_days.index(day)
    prev_day = all_days[i - 1] if i > 0 else None
    next_day = all_days[i + 1] if i + 1 < len(all_days) else None

    def item(p: dict, lead: bool = True) -> str:
        done = " class=done" if reading.finished(h, p["id"], st.get(p["id"])) else ""
        out = f'<li{done} data-id="{e(p["id"])}"><a href="/read/{e(p["id"])}">{e(p["head"])}</a>'
        if lead and p.get("lead"):
            out += f"<p>{e(p['lead'])}</p>"
        return out + f"<span>{e(_host(p['url']))}</span></li>"

    body = []
    answers = [r for r in rows if kind(r) == "answer"]
    if answers:
        marks = learn.marks(h)
        pieces_by_id = all_pieces(h)
        items = []
        for a in answers:
            m = marks.get(a.get("answer"), {})
            src = pieces_by_id.get(m.get("piece"), {})
            quote = f"<blockquote>{e(m.get('text', ''))}</blockquote>" if m else ""
            where = f'<span><a href="/read/{e(src["id"])}">{e(src["head"])}</a></span>' if src else ""
            items.append(f"<li class=answer>{quote}<p>{e(str(a.get('text', '')))}</p>{where}</li>")
        body.append(f"<section><h2>{e(t['answers'])}</h2><ol>{''.join(items)}</ol></section>")
    if stories:
        items = [item(m["piece"]) if m["piece"] else
                 f'<li data-id="{e(m["thread"]["id"])}"><a href="/thread/{e(m["thread"]["id"])}?day={day}">'
                 f'{e(m["thread"]["title"])}</a><p>{e(str(m["new"][0]["text"]))}</p></li>' for m in stories]
        body.append(f"<section><h2>{e(t['since'])}</h2><ol>{''.join(items)}</ol></section>")
    named = {s.id: s.name for s in secs}
    first = {m["piece"]["id"] for m in stories if m["piece"]}
    for sid in dict.fromkeys(p.get("section") for p in pieces if not p.get("saved") and p["id"] not in first):
        mine = [p for p in pieces if p.get("section") == sid and not p.get("saved") and p["id"] not in first]
        name = named.get(sid) or str(sid).replace("-", " ").capitalize()
        body.append(f"<section><h2>{e(name)}</h2><ol>{''.join(map(item, mine))}</ol></section>")
    saved = [p for p in pieces if p.get("saved")]
    if saved:
        body.append(f"<section><h2>{e(t['saved'])}</h2><ol>{''.join(item(p, False) for p in saved)}</ol></section>")
    if not body:
        body.append(f"<p class=empty>{e(t['empty'])}</p>")
    body.append(_crossword_link(h, day, rows))
    short = lambda d: config.short_date(h, d)  # noqa: E731
    left = f'<a href="/{prev_day}">← {e(short(prev_day))}</a>' if prev_day else "<span></span>"
    right = f'<a href="/{next_day}">{e(short(next_day))} →</a>' if next_day else "<span></span>"
    mid = f'<span class=links><a href="/kept">{e(t["kept"])}</a><a href="/settings">{e(t["settings"])}</a></span>'
    return _page(h, dateline(day), f"<h1>{e(dateline(day))}</h1>", "".join(body),
                 f"<nav>{left}{mid}{right}</nav>", LOOK_JS + ANSWERS_JS)


def done_page(h: Home, day: str) -> str:
    t, dateline = config.labels(h), config.dateline(h, day)
    later = [d for d in days(h) if d > day]
    right = f'<a href="/{later[0]}">{e(config.short_date(h, later[0]))} →</a>' if later else "<span></span>"
    nav = (f'<nav><a href="/{day}">← {e(config.short_date(h, day))}</a><span class=links>'
           f'<a href="/kept">{e(t["kept"])}</a><a href="/settings">{e(t["settings"])}</a></span>{right}</nav>')
    # the latest issue's end says when the next comes; an older one's points to it
    after = "" if later else e(t["next_at"].format(time=config.morning(h)))
    return _page(h, t["done"], f"<h1>{e(dateline)}</h1>",
                 f"<p class=end>{e(t['done'])}</p><p class=after>{after}</p>{_crossword_link(h, day)}", nav)


def _crossword_link(h: Home, day: str, rows: list[dict] | None = None) -> str:
    """The way to Sunday's crossword, at the end of the front page and of the issue."""
    rows = load(h, day) if rows is None else rows
    if not any(kind(r) == "crossword" for r in rows):
        return ""
    return f'<a class=next href="/{day}/crossword">{e(config.labels(h)["crossword"])}</a>'


def crossword_page(h: Home, day: str) -> str | None:
    t = config.labels(h)
    row = next((r for r in load(h, day) if kind(r) == "crossword"), None)
    if not row:
        return None
    words = row.get("crossword") or []
    grid = crossword.layout([w.get("answer") for w in words])
    solved = reading.games(h).get(row["id"], {}).get("solved", set())
    pieces = all_pieces(h)
    entries = [{**x, "answer": crossword.normal(words[x["i"]].get("answer")), "clue": words[x["i"]].get("clue"),
                "solved": x["i"] in solved} for x in grid["entries"]]
    lists = []
    for down in (False, True):
        items = []
        for x in (x for x in entries if x["down"] == down):
            p = pieces.get(words[x["i"]].get("piece"), {})
            src = f'<span><a href="/read/{e(p["id"])}">{e(p["head"])}</a></span>' if p else ""
            items.append(f'<li data-i="{x["i"]}"{" class=done" if x["solved"] else ""}><p><b>{x["num"]}</b> {e(str(x["clue"]))}</p>{src}</li>')
        if items:
            lists.append(f"<section><h2>{e(t['down' if down else 'across'])}</h2><ol>{''.join(items)}</ol></section>")
    data = {"id": row["id"], "rows": grid["rows"], "cols": grid["cols"], "entries": entries}
    head = f'<header><a href="/{day}">← {e(config.short_date(h, day))}</a></header><h1>{e(t["crossword"])}</h1>'
    body = ('<div class=grid id=grid><input id=type autocapitalize=characters autocomplete=off autocorrect=off '
            f'spellcheck=false aria-label="{e(t["crossword"])}"></div><div id=clues>{"".join(lists)}</div>'
            '<div class=clue id=clue hidden></div>')
    return _page(h, t["crossword"], head, body, "", f"<script>const PAPER = {_json(data)};</script>{CROSSWORD_JS}")


def _game(h: Home, piece: dict) -> dict | None:
    """The prediction or link asked before this piece, from the piece's own issue."""
    try:
        rows = load(h, piece["day"])
    except Invalid:
        return None
    return next((r for r in rows if kind(r) in ("predict", "link") and r.get(kind(r)) == piece["id"]), None)


def _authors(raw, url: str) -> str:
    """Up to three names, each once, without the outlet's own name, "Szerző", or a month the page
    glued on ("Charlie Wood November"; "April Rubin" keeps her name)."""
    months = {m for lang in config.LABELS.values() for m in lang["months"].lower().split()}
    host, names = _host(url).split(".")[0], {}
    for name in re.split(r"\s*[;,]\s*|\s+and\s+|\s+és\s+", str(raw or "")):
        words = name.split()
        if len(words) >= 3 and words[-1].lower() in months:
            words = words[:-1]
        key = " ".join(words).replace("-", " ").lower()
        if words and key not in ("szerzo", "szerző", host) and len(key) >= 3 and (key not in names or "-" in names[key]):
            names[key] = " ".join(words)  # "Weiler-Vilmos; Weiler Vilmos" is one writer
    return ", ".join(list(names.values())[:3])


def _when(h: Home, raw, day: str) -> str:
    """The article's date as the page writes dates, with the year when it is not the issue's;
    nothing when it is not a date."""
    try:
        when = config.short_date(h, str(raw)[:10])
    except ValueError:
        return ""
    year = str(raw)[:4]
    if year == day[:4]:
        return when
    return f"{year}. {when}" if config.language(h) == "hu" else f"{when} {year}"


def reader_page(h: Home, piece: dict, art: dict) -> str:
    t = config.labels(h)
    st = reading.state(h).get(piece["id"])
    game = _game(h, piece)
    played = reading.games(h).get(game["id"]) if game else None
    asking = bool(game) and played is None  # the article waits for a pick or a skip
    thread = ""
    if (found := story(h, piece)) and (found[2] or found[3]):
        th, left, new, old = found
        held = asking and kind(game) == "link"  # shown, and logged, once the reader has answered
        if not held:
            _caught_up(h, th, left, new if left else [], piece["day"], piece["id"])
        thread = (f"<details class=thread{' open' if new else ''}{' hidden' if held else ''}>"
                  f"<summary>{e(th['title'])}</summary>{_updates(h, new, old)}</details>")
    box = "<div id=game></div>" if game else ""
    kept = reading.kept(piece, st)
    byline = " · ".join(e(x) for x in (_host(piece["url"]), _authors(art.get("author"), piece["url"]),
                                        _when(h, art.get("date"), piece["day"])) if x)
    if art.get("digest"):
        byline = f'{e(t["digest"])} <a href="{e(piece["url"])}">{e(_host(piece["url"]))}</a>'

    title = re.sub(r"\s+[|–—]\s+[^|–—]+$", "", art.get("title") or "") or piece["head"]  # "Title | Site"
    link = game and kind(game) == "link"
    head = (f'<header><a href="/{piece["day"]}">← {e(config.short_date(h, piece["day"]))}</a></header>'
            f'{box if link else ""}{thread}' + (f'<h1 class=title data-title="{e(title)}">{e(piece["head"])}</h1>'
                                                if asking and not link else f"<h1 class=title>{e(title)}</h1>")
            + (f"<p class=byline>{byline}</p>" if byline else "") + ("" if link else box))
    try:
        seq = order(h, piece["day"])
    except Invalid:
        seq = []
    ids = [p["id"] for p in seq]
    nxt = seq[ids.index(piece["id"]) + 1] if piece["id"] in ids and ids.index(piece["id"]) + 1 < len(ids) else None
    if nxt:
        after = f'<a class=next href="/read/{e(nxt["id"])}"><span>{e(t["next"])}</span>{e(nxt["head"])}</a>'
    else:
        after = f'<a class=next href="/{piece["day"]}/done">{e(t["done"])}</a>'
    foot = (f'<footer><button id=keep data-kept="{str(kept).lower()}">{e(t["keeping"] if kept else t["keep"])}</button>'
            f'<a href="{e(piece["url"])}">{e(t["original"])} ↗</a></footer>{after}')
    data = {
        "id": piece["id"],
        "need": round(reading.words(h, piece["id"]) / reading.WPM * 60000 / 3),
        "had": st["ms"] if st else 0,
        "marks": [{"id": m["id"], "kind": m["kind"], "text": m["text"]}
                  for m in learn.marks(h).values() if m["piece"] == piece["id"]],
        "t": {k: t[k] for k in ("keep", "keeping", "highlight", "question", "remove", "show", "again", "good", "skip")},
    }
    if game:
        data["game"] = {"id": game["id"], "kind": kind(game), "prompt": game.get("prompt"), "options": game.get("options"),
                        "asking": asking}
        if not asking:
            data["game"].update(answer=game.get("answer"), pick=played.get("pick"))
    script = f"<script>const PAPER = {_json(data)};</script>{READER_JS}"
    article = f"<article{' hidden' if asking else ''}>{art['html'] if art.get('digest') else _body(art['html'], title)}</article><div id=reveal></div><div id=card></div>"
    # an outlet's title often states the finding: a prediction shows the paper's own headline until answered
    return _page(h, piece["head"] if asking and not link else title, head, article, foot, script)


def thread_page(h: Home, tid: str, day: str | None) -> str | None:
    """A running story that moved without a piece in the issue: its updates since the reader last
    caught up, the rest under Earlier."""
    from datetime import date

    th = _threads(h).get(tid)
    if not th:
        return None
    all_days = days(h)
    day = day if day in all_days else (all_days[-1] if all_days else date.today().isoformat())
    left = reading.left_off(h, th, day)
    mine = list(reversed(th["entries"]))
    new = [x for x in mine if left and left < x["day"] <= day]
    _caught_up(h, th, left, new, day)
    head = f'<header><a href="/{day}">← {e(config.short_date(h, day))}</a></header><h1 class=title>{e(th["title"])}</h1>'
    return _page(h, th["title"], head, f"<div class=story>{_updates(h, new, [x for x in mine if x not in new])}</div>")


def kept_page(h: Home) -> str:
    t, dateline = config.labels(h), lambda d: config.dateline(h, d)
    st = reading.state(h)
    pieces = sorted(all_pieces(h).values(), key=lambda p: (p["day"], p["id"]), reverse=True)
    items = [
        f'<li><a href="/read/{e(p["id"])}">{e(p["head"])}</a><span>{e(_host(p["url"]))} · {e(dateline(p["day"]))}</span></li>'
        for p in pieces if reading.kept(p, st.get(p["id"]))
    ]
    body = f"<ol>{''.join(items)}</ol>" if items else f"<p class=empty>{e(t['nothing_kept'])}</p>"
    latest = days(h)[-1:] or [None]
    nav = f'<nav><a href="/{latest[0]}">← {e(config.short_date(h, latest[0]))}</a></nav>' if latest[0] else ""
    return _page(h, t["kept"], f"<h1>{e(t['kept'])}</h1>", body, nav)


def settings_page(h: Home, mac: bool = False) -> str:
    t = config.labels(h)
    latest = days(h)[-1:] or [None]
    back = f'<nav><a href="/{latest[0]}">← {e(config.short_date(h, latest[0]))}</a></nav>' if latest[0] else ""
    data = {"state": settings.state(h), "t": {k: t[k] for k in (
        "sections", "interests", "feeds", "outlets", "language", "save_link", "add", "name", "what",
        "topics", "url", "remove", "saved", "phone", "new_code")}}
    if mac:
        url = phone.pair_url(h, PORT)
        phone.open_codes()
        data["phone"] = {"qr": phone.qr_svg(url), "address": phone.address(PORT), "code": phone.short_code(h)}
    body = "<div id=settings></div>"
    return _page(h, t["settings"], f"<h1>{e(t['settings'])}</h1>", body, back,
                 f"<script>const PAPER = {_json(data)};</script>{SETTINGS_JS}")


class Handler(BaseHTTPRequestHandler):
    server_version = "paper"

    def log_message(self, *args):  # quiet: the reading log is the record
        pass

    def _send(self, code: int, body: str = "", ctype: str = "text/html; charset=utf-8", location: str | None = None):
        data = body.encode()
        self.send_response(code)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_bytes(self, data: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _json_reply(self, data, code: int = 200):
        return self._send(code, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8")

    def _mac(self) -> bool:
        return phone.is_mac(self.client_address[0], self.headers.get("Host"))

    def _cookie_key(self) -> str | None:
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie") or "")
        except Exception:  # noqa: BLE001 - a bad cookie is no cookie
            return None
        return jar[phone.COOKIE].value if phone.COOKIE in jar else None

    def _allowed(self, h: Home) -> bool:
        return phone.allowed(h, self.client_address[0], self.headers.get("Host"), self._cookie_key())

    def _may_write(self, h: Home) -> bool:
        return self._allowed(h) and phone.same_origin(self.headers.get("Origin"), self.headers.get("Host"))

    def _unpaired(self, h: Home):
        t = config.labels(h)
        body = (f"<form id=pair><p class=empty>{e(t['unpaired'])}</p>"
                '<input name=code inputmode=numeric autocomplete=one-time-code maxlength=7 aria-label="code">'
                f"<button>{e(t['pair'])}</button><p class=err></p></form>")
        data = {"t": {k: t[k] for k in ("wrong_code", "locked")}}
        return self._send(403, _page(h, "Morning paper", "", body, "",
                                     f"<script>const PAPER = {_json(data)};</script>{UNPAIRED_JS}"))

    def _body_json(self):
        """The request's JSON body; None when it is not JSON or longer than any write needs."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 <= n <= MAX_BODY:
                return None
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return None

    def do_GET(self):
        h, url = home(), urlsplit(self.path)
        path = url.path.rstrip("/") or "/"
        if path == "/pair":
            return self._send(200, PAIR_PAGE)
        if path == "/icon.png":
            return self._send_bytes(ICON.read_bytes(), "image/png")
        if not self._allowed(h):
            return self._unpaired(h)
        try:
            if path == "/":
                all_days = days(h)
                if not all_days:
                    t = config.labels(h)
                    return self._send(200, _page(h, "Morning paper", "", f"<p class=empty>{e(t['no_issue'])}</p>",
                                                 '<nav><span></span><span class=links><a href="/settings">'
                                                 f'{e(t["settings"])}</a></span><span></span></nav>'))
                return self._send(302, location=f"/{all_days[-1]}")
            day, _, rest = path[1:].partition("/")
            if DAY.match(day) and rest in ("", "done", "crossword"):
                if not (h.issues / f"{day}.jsonl").exists():
                    return self._send(404, "No such issue.", "text/plain; charset=utf-8")
                if rest == "crossword":
                    page = crossword_page(h, day)
                    return self._send(200, page) if page else self._send(404, "No crossword.", "text/plain; charset=utf-8")
                return self._send(200, done_page(h, day) if rest else issue_page(h, day))
            if path == "/kept":
                return self._send(200, kept_page(h))
            if path.startswith("/thread/"):
                day = (parse_qs(url.query).get("day") or [None])[0]
                page = thread_page(h, path.removeprefix("/thread/"), day)
                return self._send(200, page) if page else self._send(404, "No such story.", "text/plain; charset=utf-8")
            if path == "/settings":
                return self._send(200, settings_page(h, self._mac()))
            if path == "/settings/code" and self._mac():
                return self._json_reply({"code": phone.short_code(h)})
            if path == "/card":
                after = (parse_qs(url.query).get("after") or [""])[0]
                card = learn.due(h, reading.reviews(h), after)
                if not card:
                    return self._send(204)
                return self._json_reply({k: v for k, v in card.items() if not k.startswith("_") and k != "day"})
            if path.startswith("/read/"):
                piece = all_pieces(h).get(path.removeprefix("/read/"))
                if not piece:
                    return self._send(404, "No such piece.", "text/plain; charset=utf-8")
                art = digest(h, piece) if piece.get("digest") else article(h, piece)
                if not art:
                    reading.log(h, {"ev": "open", "id": piece["id"], "external": True})
                    return self._send(302, location=piece["url"])
                reading.log(h, {"ev": "open", "id": piece["id"]})
                return self._send(200, reader_page(h, piece, art))
        except Invalid as err:
            return self._send(500, "\n".join(err.errors), "text/plain; charset=utf-8")
        return self._send(404, "Not found.", "text/plain; charset=utf-8")

    def do_POST(self):
        h, path = home(), urlsplit(self.path).path
        data = self._body_json()
        if not isinstance(data, dict):
            return self._send(400, "not JSON", "text/plain")
        if path == "/pair":
            if not phone.same_origin(self.headers.get("Origin"), self.headers.get("Host")):
                return self._send(403, "", "text/plain")
            ok = phone.paired(h, str(data.get("key") or "")) if "key" in data else phone.check_code(h, str(data.get("code") or ""))
            if not ok:
                return self._json_reply({"locked": phone.code_locked()}, 403)
            self.send_response(204)
            self.send_header("Set-Cookie", f"{phone.COOKIE}={phone.key(h)}; Max-Age=315360000; Path=/; HttpOnly; SameSite=Lax")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        if not self._may_write(h):
            return self._send(403, "", "text/plain")
        pieces = all_pieces(h)
        if path == "/log" and data.get("id") in pieces:
            ms = max(0, min(int(data.get("ms") or 0), 120_000))  # a heartbeat covers at most two minutes
            progress = max(0.0, min(float(data.get("progress") or 0), 1.0))
            reading.log(h, {"ev": "read", "id": data["id"], "ms": ms, "progress": round(progress, 3)})
            return self._send(204)
        if path == "/look" and (data.get("id") in pieces or data.get("id") in _threads(h)):
            reading.log(h, {"ev": "look", "id": data["id"]})
            return self._send(204)
        if path.startswith("/keep/") and path.removeprefix("/keep/") in pieces:
            reading.log(h, {"ev": "keep", "id": path.removeprefix("/keep/"), "kept": bool(data.get("kept"))})
            return self._send(204)
        if path == "/mark":
            if data.get("deleted") and data.get("id") in learn.marks(h):
                learn.delete_mark(h, data["id"])
                return self._send(204)
            if data.get("piece") in pieces and data.get("kind") in learn.KINDS and str(data.get("text") or "").strip():
                return self._json_reply(learn.add_mark(h, data["piece"], data["kind"], str(data["text"])))
            return self._send(400, "a mark needs piece, kind and text", "text/plain")
        if path == "/game":
            return self._game(h, data)
        if path == "/review" and data.get("id") in learn.cards(h) and data.get("rating") in learn.RATINGS:
            reading.log(h, {"ev": "review", "id": data["id"], "rating": data["rating"]})
            return self._send(204)
        return self._send(404, "", "text/plain")

    def _game(self, h: Home, data: dict):
        """A game answered: the first answer is logged and checked here, never by the page."""
        gid = str(data.get("id") or "")
        what = kind({"id": gid})
        g = all_rows(h, what).get(gid) if what in ("predict", "link", "crossword") else None
        if not g:
            return self._send(404, "", "text/plain")
        played = reading.games(h).get(gid)
        if what == "crossword":
            words, i = g.get("crossword") or [], data.get("entry")
            if not isinstance(i, int) or not 0 <= i < len(words) or \
                    crossword.normal(data.get("word")) != crossword.normal(words[i].get("answer")):
                return self._send(400, "", "text/plain")
            if i not in (played or {}).get("solved", ()):
                reading.log(h, {"ev": "game", "id": gid, "entry": i})
            return self._send(204)
        if played is None:
            if data.get("skip"):
                reading.log(h, {"ev": "game", "id": gid, "skipped": True})
            elif data.get("pick") in (0, 1, 2) and not isinstance(data.get("pick"), bool):
                reading.log(h, {"ev": "game", "id": gid, "pick": data["pick"], "right": data["pick"] == g.get("answer")})
            else:
                return self._send(400, "", "text/plain")
            piece = all_pieces(h).get(g.get(what))
            if what == "link" and piece and (found := story(h, piece)):
                th, left, new, _ = found
                _caught_up(h, th, left, new if left else [], piece["day"], piece["id"])
        return self._json_reply({"answer": g.get("answer")})

    def do_PUT(self):
        h, part = home(), urlsplit(self.path).path.removeprefix("/settings/")
        if not self._may_write(h):
            return self._send(403, "", "text/plain")
        if part == "phone":
            if not self._mac():
                return self._send(403, "", "text/plain")
            phone.new_key(h)
            return self._json_reply({})
        data = self._body_json()
        save = settings.SAVE.get(part)
        if not save or not isinstance(data, dict):
            return self._send(404, "", "text/plain")
        try:
            save(h, data.get("value"))
        except Invalid as err:
            return self._json_reply({"errors": err.errors}, 400)
        return self._json_reply(settings.state(h))


def serve(port: int = PORT) -> None:
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


ANSWERS_JS = """<script>
document.querySelectorAll("li.answer blockquote").forEach(q => q.addEventListener("click", () => q.classList.toggle("open")));
</script>"""

UNPAIRED_JS = """<script>
(() => {
  const form = document.getElementById("pair"), input = form.querySelector("input"), err = form.querySelector(".err");
  input.focus();
  form.addEventListener("submit", async ev => {
    ev.preventDefault();
    const res = await fetch("/pair", {method: "POST", body: JSON.stringify({code: input.value})});
    if (res.ok) return location.reload();
    const data = await res.json().catch(() => ({}));
    err.textContent = data.locked ? PAPER.t.locked : PAPER.t.wrong_code;
    input.value = ""; input.focus();
  });
})();
</script>"""

PAIR_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Morning paper</title></head><body>
<script>
(async () => {
  const key = location.hash.slice(1);
  history.replaceState(null, "", "/pair");
  if (key) await fetch("/pair", {method: "POST", body: JSON.stringify({key})}).catch(() => null);
  location.replace("/");
})();
</script></body></html>
"""

LOOK_JS = """<script>
(() => {
  const sent = new Set(), timers = new Map(), rows = [...document.querySelectorAll("li[data-id]")];
  const look = id => { sent.add(id); navigator.sendBeacon("/look", new Blob([JSON.stringify({id})], {type: "application/json"})); };
  const io = new IntersectionObserver(entries => {
    for (const en of entries) {
      const id = en.target.dataset.id;
      if (sent.has(id)) continue;
      clearTimeout(timers.get(id)); timers.delete(id);
      if (en.isIntersecting && document.visibilityState === "visible") timers.set(id, setTimeout(() => look(id), 2000));
    }
  }, {threshold: 0.6});
  const watch = () => rows.forEach(r => sent.has(r.dataset.id) || io.observe(r));
  document.addEventListener("visibilitychange", () => {
    for (const x of timers.values()) clearTimeout(x);
    timers.clear(); io.disconnect();
    if (document.visibilityState === "visible") watch();
  });
  watch();
})();
</script>"""

READER_JS = """<script>
(() => {
  const {id, need, had, t, game} = PAPER;
  const article = document.querySelector("article");
  // reading counts only once the article is out: a question first holds it back
  let ms = 0, total = had, progress = 0, last = Date.now(), active = Date.now(), asked = false, live = !game?.asking;
  const post = (url, body) => fetch(url, {method: "POST", body: JSON.stringify(body)});
  const el = (tag, cls, text) => { const x = document.createElement(tag); if (cls) x.className = cls; if (text != null) x.textContent = text; return x; };
  const measure = () => {
    if (!live) return;
    const el = document.scrollingElement, end = article.offsetTop + article.offsetHeight;
    progress = Math.max(progress, Math.min(1, (el.scrollTop + innerHeight - article.offsetTop) / Math.max(1, end - article.offsetTop)));
  };
  const tick = () => {
    if (!live) return;
    const now = Date.now();
    if (document.visibilityState === "visible" && now - active < 60000) { ms += now - last; total += now - last; }
    last = now;
  };
  const send = () => {
    if (!live) return;
    tick(); measure();
    if (!ms && !progress) return;
    navigator.sendBeacon("/log", new Blob([JSON.stringify({id, ms, progress})], {type: "application/json"}));
    ms = 0;
  };
  const finished = () => {
    if (asked || progress < 0.9 || total < need) return;
    asked = true; send(); card();
  };
  for (const ev of ["scroll", "keydown", "pointermove", "touchstart"])
    addEventListener(ev, () => { tick(); active = Date.now(); measure(); finished(); }, {passive: true});
  document.addEventListener("visibilitychange", () => document.visibilityState === "hidden" ? send() : (last = Date.now()));
  addEventListener("pagehide", send);
  setInterval(() => { send(); finished(); }, 15000);
  measure();

  // a prediction or a link: asked before the article; a link answers at once, a prediction at the end
  if (game) {
    const box = document.getElementById("game"), reveal = document.getElementById("reveal");
    const show = (pick, answer) => {
      const opts = el("div", "options"), out = el("div", "card");
      game.options.forEach((o, i) => {
        const b = el("button", i === answer ? "right" : i === pick ? "wrong" : "", o);
        b.disabled = true; opts.append(b);
      });
      out.append(el("p", "front", game.prompt), opts);
      (game.kind === "link" ? box : reveal).replaceChildren(out);
    };
    if (!game.asking) {
      if (game.kind === "predict") show(game.pick, game.answer);
    } else {
      const opts = el("div", "options"), skip = el("button", "quiet", t.skip), q = el("div", "card");
      const settle = async answer => {
        [...opts.children, skip].forEach(b => b.disabled = true);
        const res = await post("/game", {id: game.id, ...answer}).catch(() => null);
        const got = res && res.ok ? await res.json() : {};
        box.replaceChildren();
        article.hidden = false; article.classList.add("late");
        const h1 = document.querySelector("h1.title");
        if (h1.dataset.title) h1.textContent = h1.dataset.title;
        const thread = document.querySelector("details.thread");
        if (thread) { thread.hidden = false; thread.open = true; }
        live = true; last = active = Date.now(); measure();
        if (got.answer != null) show(answer.pick, got.answer);
      };
      game.options.forEach((o, i) => {
        const b = el("button", "", o);
        b.addEventListener("click", () => settle({pick: i}));
        opts.append(b);
      });
      skip.addEventListener("click", () => settle({skip: true}));
      q.append(el("p", "front", game.prompt), opts, skip);
      box.replaceChildren(q);
    }
  }

  const keep = document.getElementById("keep");
  keep.addEventListener("click", async () => {
    const kept = keep.dataset.kept !== "true";
    await post("/keep/" + encodeURIComponent(id), {kept});
    keep.dataset.kept = String(kept);
    keep.textContent = kept ? t.keeping : t.keep;
  });

  // marks: a tap on a paragraph highlights it or asks about it; a mark is kept by its text
  const BLOCKS = "p, li, blockquote, h2, h3, h4, td, th, figcaption";
  const squash = s => s.replace(/\\s+/g, " ").trim();
  const blocks = [...article.querySelectorAll(BLOCKS)].filter(b => !b.querySelector(BLOCKS));
  const on = new Map();  // block -> its marks
  const place = (block, text) => {
    const nodes = [], map = [];
    let s = "", space = true;
    const walk = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    for (let n; (n = walk.nextNode());) {
      for (let i = 0; i < n.data.length; i++) {
        const ws = /\\s/.test(n.data[i]);
        if (ws && space) continue;
        s += ws ? " " : n.data[i]; map.push([n, i]); space = ws;
      }
    }
    const at = s.indexOf(text);
    if (at < 0) return null;
    const r = document.createRange();
    r.setStart(...map[at]); r.setEnd(map[at + text.length - 1][0], map[at + text.length - 1][1] + 1);
    return r;
  };
  const paint = (block, m) => { block.classList.add("m-" + m.kind); on.set(block, [...(on.get(block) || []), m]); };
  const draw = m => {
    const whole = blocks.find(b => squash(b.textContent) === m.text);
    if (whole) return paint(whole, m);
    for (const b of blocks) {  // an older mark holds part of a paragraph
      const r = place(b, m.text);
      if (!r) continue;
      const el = document.createElement("mark");
      el.className = m.kind; el.dataset.id = m.id;
      el.appendChild(r.extractContents()); r.insertNode(el);
      return;
    }
  };
  PAPER.marks.forEach(draw);

  const bar = document.createElement("div");
  bar.className = "bar"; bar.hidden = true; document.body.appendChild(bar);
  let picked = null;
  const pick = b => { picked?.classList.remove("picked"); picked = b; b?.classList.add("picked"); };
  const close = () => { bar.hidden = true; pick(null); };
  const open = acts => {
    bar.replaceChildren(...acts.map(([label, fn]) => {
      const b = document.createElement("button"); b.textContent = label;
      b.addEventListener("click", () => { close(); fn(); });
      return b;
    }));
    bar.hidden = false;
  };
  const unmark = mid => post("/mark", {id: mid, deleted: true});
  article.addEventListener("click", ev => {
    if (!getSelection().isCollapsed) return;
    const part = ev.target.closest("mark[data-id]");
    if (part) { pick(null); return open([[t.remove, () => { unmark(part.dataset.id); part.replaceWith(...part.childNodes); }]]); }
    const block = ev.target.closest(BLOCKS);
    if (!block || !blocks.includes(block) || block === picked) return close();
    const text = squash(block.textContent);
    if (text.length < 3) return close();
    pick(block);
    const has = on.get(block) || [];
    const acts = [["highlight", t.highlight], ["question", t.question]].filter(([k]) => !has.some(m => m.kind === k))
      .map(([kind, label]) => [label, async () => {
        const res = await post("/mark", {piece: id, kind, text});
        if (res.ok) paint(block, await res.json());
      }]);
    if (has.length) acts.push([t.remove, () => {
      has.forEach(m => { unmark(m.id); block.classList.remove("m-" + m.kind); });
      on.delete(block);
    }]);
    open(acts);
  });
  document.addEventListener("click", ev => { if (!article.contains(ev.target) && !bar.contains(ev.target)) close(); });

  // one due card after a finished piece
  const card = async () => {
    const res = await fetch("/card?after=" + encodeURIComponent(id));
    if (res.status !== 200) return;
    const c = await res.json(), box = document.getElementById("card"), rate = r => post("/review", {id: c.id, rating: r});
    box.className = "card";
    if (c.card === "flip") {
      const front = el("p", "front", c.front), reveal = el("button", "", t.show), row = el("div", "row");
      reveal.addEventListener("click", () => {
        reveal.remove();
        const again = el("button", "", t.again), good = el("button", "", t.good);
        for (const [b, r] of [[again, "again"], [good, "good"]])
          b.addEventListener("click", () => { rate(r); row.replaceChildren(el("span", "rated", b.textContent)); });
        box.insertBefore(el("p", "back", c.back), row);
        row.replaceChildren(again, good);
      });
      row.append(reveal); box.replaceChildren(front, row);
    } else {
      const opts = el("div", "options");
      c.options.forEach((o, i) => {
        const b = el("button", "", o);
        b.addEventListener("click", () => {
          rate(i === c.answer ? "good" : "again");
          [...opts.children].forEach((x, j) => { x.disabled = true; if (j === c.answer) x.classList.add("right"); else if (j === i) x.classList.add("wrong"); });
        });
        opts.append(b);
      });
      box.replaceChildren(el("p", "front", c.prompt), opts);
    }
  };
})();
</script>"""

CROSSWORD_JS = """<script>
(() => {
  const {id, rows, cols, entries} = PAPER;
  const grid = document.getElementById("grid"), input = document.getElementById("type"), bar = document.getElementById("clue");
  const key = "crossword:" + id, cells = new Map();  // "r,c" -> {el, letter, across, down}
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(key) || "{}"); } catch { saved = {}; }
  const keep = () => { try { localStorage.setItem(key, JSON.stringify(saved)); } catch {} };
  grid.style.gridTemplateColumns = `repeat(${cols}, var(--cell))`;
  grid.style.setProperty("--cell", `min(40px, calc((100vw - 40px - ${cols - 1} * 3px) / ${cols}))`);
  const at = (x, k) => [x.row + (x.down ? k : 0), x.col + (x.down ? 0 : k)].join();
  entries.forEach((x, n) => {
    for (let k = 0; k < x.answer.length; k++) {
      const c = cells.get(at(x, k)) || {letter: ""};
      c[x.down ? "down" : "across"] = n;
      cells.set(at(x, k), c);
    }
  });
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const cell = cells.get([r, c].join()), d = document.createElement("div");
    if (cell) {
      d.className = "cell"; cell.el = d; d.dataset.at = [r, c].join();
      const num = entries.find(x => x.row === r && x.col === c);
      if (num) d.append(Object.assign(document.createElement("small"), {textContent: num.num}));
      d.append(document.createElement("span"));
    }
    grid.insertBefore(d, input);
  }
  const letters = x => [...x.answer].map((_, k) => cells.get(at(x, k)));
  const set = (c, ch) => { c.letter = ch; c.el.lastChild.textContent = ch; };
  const locked = c => [c.across, c.down].some(n => n != null && entries[n].solved);
  const solve = n => {
    entries[n].solved = true;
    letters(entries[n]).forEach((c, k) => { set(c, entries[n].answer[k]); c.el.classList.add("solved"); });
    document.querySelector(`#clues li[data-i="${entries[n].i}"]`)?.classList.add("done");
  };
  entries.forEach((x, n) => { if (x.solved) solve(n); });
  for (const [where, ch] of Object.entries(saved)) { const c = cells.get(where); if (c && !c.letter) set(c, ch); }

  let cur = null, dir = "across";
  const entry = () => { const c = cells.get(cur); return c[dir] ?? c[dir === "across" ? "down" : "across"]; };
  const pin = () => {  // the clue sits on the keyboard
    const vv = window.visualViewport;
    bar.style.bottom = vv ? Math.max(0, innerHeight - vv.height - vv.offsetTop) + "px" : "0";
  };
  window.visualViewport?.addEventListener("resize", pin);
  window.visualViewport?.addEventListener("scroll", pin);
  const draw = () => {
    for (const c of cells.values()) c.el.classList.remove("on", "at");
    document.querySelectorAll("#clues li.on").forEach(li => li.classList.remove("on"));
    if (!cur) return;
    const n = entry(), x = entries[n];
    dir = x.down ? "down" : "across";
    letters(x).forEach(c => c.el.classList.add("on"));
    cells.get(cur).el.classList.add("at");
    document.querySelector(`#clues li[data-i="${x.i}"]`)?.classList.add("on");
    bar.replaceChildren(Object.assign(document.createElement("b"), {textContent: x.num}), x.clue);
    bar.hidden = false; pin();
    const el = cells.get(cur).el;
    input.style.left = el.offsetLeft + "px"; input.style.top = el.offsetTop + "px";
  };
  const focus = () => { input.value = " "; input.focus({preventScroll: true}); input.setSelectionRange(1, 1); };
  const go = (where, d) => { cur = where; if (d) dir = d; draw(); focus(); };
  grid.addEventListener("click", ev => {
    const d = ev.target.closest(".cell");
    if (!d) return;
    const c = cells.get(d.dataset.at);
    if (d.dataset.at === cur && c.across != null && c.down != null) dir = dir === "across" ? "down" : "across";
    else if (c[dir] == null) dir = dir === "across" ? "down" : "across";
    go(d.dataset.at);
  });
  document.getElementById("clues").addEventListener("click", ev => {
    const li = ev.target.closest("li[data-i]");
    if (!li || ev.target.closest("a")) return;
    const x = entries.find(x => String(x.i) === li.dataset.i), cs = letters(x);
    const k = Math.max(0, cs.findIndex(c => !c.letter));
    go(at(x, k), x.down ? "down" : "across");
  });
  const step = by => {
    const x = entries[entry()], k = letters(x).findIndex(c => c === cells.get(cur)) + by;
    if (k >= 0 && k < x.answer.length) { cur = at(x, k); draw(); }
  };
  const check = () => {
    const c = cells.get(cur);
    for (const n of [c.across, c.down]) {
      if (n == null || entries[n].solved) continue;
      const word = letters(entries[n]).map(c => c.letter).join("");
      if (word !== entries[n].answer) continue;
      solve(n);
      fetch("/game", {method: "POST", body: JSON.stringify({id, entry: entries[n].i, word})});
    }
  };
  const type = ch => {
    const c = cells.get(cur);
    if (!locked(c)) { set(c, ch); saved[cur] = ch; keep(); check(); }
    step(1);
  };
  const erase = () => {
    const c = cells.get(cur);
    if (!c.letter || locked(c)) step(-1);
    const d = cells.get(cur);
    if (!locked(d)) { set(d, ""); delete saved[cur]; keep(); }
  };
  input.addEventListener("input", ev => {
    if (ev.isComposing || !cur) return;
    const v = input.value;  // a keyboard sends a letter at a time; a paste or a suggestion sends several
    if (!v) erase();
    else for (const ch of v.normalize("NFC").replace(/^ /, "")) if (/\\p{L}/u.test(ch)) type(ch.toLocaleUpperCase());
    focus();
  });
  input.addEventListener("compositionend", () => { input.dispatchEvent(new Event("input")); });
  input.addEventListener("keydown", ev => {
    const moves = {ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0]};
    if (!moves[ev.key] || !cur) return;
    ev.preventDefault();
    const [r, c] = cur.split(",").map(Number), [dr, dc] = moves[ev.key], next = [r + dr, c + dc].join();
    if (cells.has(next)) go(next, dr ? "down" : "across");
  });
  input.addEventListener("blur", () => setTimeout(() => {
    if (document.activeElement !== input) { cur = null; draw(); bar.hidden = true; }
  }, 100));
})();
</script>"""

SETTINGS_JS = """<script>
(() => {
  let {state, t} = PAPER;
  const root = document.getElementById("settings");
  const el = (tag, attrs = {}, ...kids) => {
    const x = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) k.startsWith("on") ? x.addEventListener(k.slice(2), v) : x.setAttribute(k, v);
    x.append(...kids); return x;
  };
  const save = async (part, value, err) => {
    const res = await fetch("/settings/" + part, {method: "PUT", body: JSON.stringify({value})});
    const data = await res.json();
    if (res.ok) { state = data; err.textContent = ""; return true; }
    err.textContent = data.errors.join(" · "); return false;
  };
  const block = (title, ...kids) => el("section", {}, el("h2", {}, title), ...kids);
  // a line of text that wraps instead of running off the screen; Return ends it
  const fit = a => { a.style.height = "auto"; a.style.height = a.scrollHeight + "px"; };
  const grow = (a, value) => {
    a.value = value || "";
    a.addEventListener("input", () => { if (a.value.includes("\\n")) a.value = a.value.replace(/\\s*\\n\\s*/g, " "); fit(a); });
    a.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); a.blur(); } });
    requestAnimationFrame(() => fit(a));
    addEventListener("resize", () => fit(a));
    return a;
  };

  const sections = () => {
    const err = el("p", {class: "err"}), list = el("div", {class: "rows"});
    const rows = () => [...list.children].map(r => Object.fromEntries([...r.querySelectorAll("[name]")].map(i => [i.name, i.value])));
    const commit = () => save("sections", rows(), err);
    const row = s => {
      const r = el("div", {class: "row sec"},
        el("input", {name: "name", value: s.name, placeholder: t.name, onchange: commit}),
        el("button", {class: "quiet", "aria-label": "↑", onclick: () => { r.previousElementSibling && list.insertBefore(r, r.previousElementSibling); commit(); }}, "↑"),
        el("button", {class: "quiet", "aria-label": t.remove, onclick: () => { r.remove(); commit(); }}, "×"),
        grow(el("textarea", {name: "what", rows: 1, placeholder: t.what, onchange: commit}), s.what),
        grow(el("textarea", {name: "topics", rows: 1, placeholder: t.topics, onchange: commit}), s.topics));
      return r;
    };
    state.sections.forEach(s => list.append(row(s)));
    const add = el("button", {class: "quiet", onclick: () => { const r = row({name: "", what: "", topics: ""}); list.append(r); r.querySelector("input").focus(); }}, t.add);
    return block(t.sections, list, add, err);
  };

  const interests = () => {
    const err = el("p", {class: "err"});
    let timer;
    const area = el("textarea", {rows: 8, oninput: () => { clearTimeout(timer); timer = setTimeout(() => save("interests", area.value, err), 600); }});
    area.value = state.interests;
    return block(t.interests, area, err);
  };

  const feeds = () => {
    const err = el("p", {class: "err"}), list = el("div", {class: "rows"});
    const rows = () => [...list.children].map(r => ({name: r.children[0].value, url: r.children[1].value}));
    const commit = () => save("feeds", rows(), err);
    const row = f => {
      const r = el("div", {class: "row feed"},
        el("input", {value: f.name, placeholder: t.name, onchange: commit}),
        el("input", {value: f.url, placeholder: t.url, onchange: commit}),
        el("button", {class: "quiet", "aria-label": t.remove, onclick: () => { r.remove(); commit(); }}, "×"));
      return r;
    };
    state.feeds.forEach(f => list.append(row(f)));
    const add = el("button", {class: "quiet", onclick: () => { const r = row({name: "", url: ""}); list.append(r); r.querySelector("input").focus(); }}, t.add);
    return block(t.feeds, list, add, err);
  };

  const outlets = () => {
    const err = el("p", {class: "err"}), list = el("div", {class: "chips"});
    const draw = () => list.replaceChildren(...state.outlets.map(o => el("span", {class: "chip"}, o.org,
      el("button", {class: "quiet", "aria-label": t.remove, onclick: async () => {
        if (await save("outlets", state.outlets.filter(x => x.org !== o.org).flatMap(x => x.ids), err)) draw();
      }}, "×"))));
    draw();
    return block(t.outlets, list, err);
  };

  const language = () => {
    const err = el("p", {class: "err"}), row = el("div", {class: "choice"});
    for (const [code, name] of [["en", "English"], ["hu", "Magyar"]]) {
      const b = el("button", {"aria-pressed": String(state.language === code), onclick: async () => {
        if (await save("language", code, err)) location.reload();
      }}, name);
      row.append(b);
    }
    return block(t.language, row, err);
  };

  const link = () => {
    const err = el("p", {class: "err"}), input = el("input", {type: "url", placeholder: "https://"});
    const add = el("button", {onclick: async () => {
      if (await save("link", input.value, err)) { input.value = ""; err.textContent = t.saved; }
    }}, t.add);
    return block(t.save_link, el("div", {class: "row link"}, input, add), err);
  };

  const pairing = () => {
    const qr = el("div", {class: "qr"});
    qr.innerHTML = PAPER.phone.qr;
    const fresh = el("button", {class: "quiet", onclick: async () => {
      if ((await fetch("/settings/phone", {method: "PUT", body: "{}"})).ok) location.reload();
    }}, t.new_code);
    const spaced = c => c.slice(0, 3) + " " + c.slice(3);
    const code = el("p", {class: "code"}, spaced(PAPER.phone.code));
    setInterval(async () => {
      const res = await fetch("/settings/code");
      if (res.ok) code.textContent = spaced((await res.json()).code);
    }, 30000);
    return block(t.phone, qr, code, el("p", {class: "addr"}, PAPER.phone.address), fresh);
  };
  root.append(sections(), interests(), feeds(), outlets(), language(), link(), ...(PAPER.phone ? [pairing()] : []));
})();
</script>"""

PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#fbfbfa" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#161617" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-title" content="Paper">
<meta name="mobile-web-app-capable" content="yes">
<link rel="apple-touch-icon" href="/icon.png">
<title>{title}</title>
<style>
:root {{ --serif: ui-serif, "New York", "Iowan Old Style", Georgia, serif;
  --sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", system-ui, sans-serif; --bg: #fbfbfa; --ink: #1d1d1f; --muted: #6e6e73; --faint: #a1a1a6; --rule: #e8e8e6; --chip: #f0f0ee;
  --hl: #fdf0a6; --q: #dce9fb; --right: #dcefdc; --wrong: #f8dcdc; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #161617; --ink: #f2f2f2; --muted: #a1a1a6; --faint: #6e6e73; --rule: #2a2a2c; --chip: #222224;
    --hl: #4d4215; --q: #1d3150; --right: #1e3a24; --wrong: #482225; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.55 var(--sans); -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }}
main {{ max-width: 640px; margin: 0 auto; padding: max(32px, env(safe-area-inset-top)) 20px calc(120px + env(safe-area-inset-bottom)); }}
@media (min-width: 700px) {{ main {{ padding-top: 64px; }} }}
a {{ color: inherit; }}
h1 {{ font: 700 30px/1.15 var(--serif); letter-spacing: -.015em; margin: 0 0 40px; text-wrap: balance; }}
section {{ margin: 0 0 48px; }}
h2 {{ font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .1em;
  margin: 0 0 4px; padding-top: 10px; border-top: 1px solid var(--ink); }}
ol {{ list-style: none; margin: 0; padding: 0; }}
li {{ padding: 16px 0; border-bottom: 1px solid var(--rule); }}
li:last-child {{ border-bottom: 0; }}
li a {{ text-decoration: none; font: 600 21px/1.25 var(--serif); letter-spacing: -.005em; text-wrap: balance; }}
li a:hover {{ text-decoration: underline; text-underline-offset: 3px; text-decoration-thickness: 1px; }}
li p {{ margin: 6px 0 0; color: var(--muted); font-size: 16px; line-height: 1.5; text-wrap: pretty; }}
li span {{ display: block; margin-top: 8px; font-size: 12px; letter-spacing: .02em; color: var(--faint); }}
li span a {{ font: inherit; }}
li.done a, li.done p {{ color: var(--faint); }}
ol.updates li {{ padding: 8px 0; border: 0; font-size: 16px; color: var(--muted); }}
ol.updates li span {{ display: inline; margin: 0 8px 0 0; }}
.story ol.updates li {{ font-size: 18px; color: var(--ink); }}
details.earlier {{ margin-top: 8px; }}
details.earlier summary {{ cursor: pointer; font-size: 13px; color: var(--faint); }}
li.answer blockquote {{ margin: 0 0 8px; padding-left: 14px; border-left: 2px solid var(--q); color: var(--muted); cursor: pointer;
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }}
li.answer blockquote.open {{ display: block; }}
li.answer p {{ color: var(--ink); }}
nav, footer {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; }}
nav {{ flex-wrap: wrap; border-top: 1px solid var(--rule); padding-top: 8px; }}
nav > a, nav > span {{ white-space: nowrap; }}
nav .links {{ display: flex; gap: 20px; }}
@media (max-width: 520px) {{ nav .links {{ order: 3; flex-basis: 100%; }} }}
nav a, footer a, header a {{ color: var(--muted); font-size: 15px; text-decoration: none; padding: 10px 0; }}
nav a:hover, footer a:hover, header a:hover {{ color: var(--ink); }}
header {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
h1.title {{ font-size: clamp(29px, 7.6vw, 38px); line-height: 1.12; letter-spacing: -.02em; margin: 0 0 12px; }}
.byline {{ color: var(--faint); font-size: 14px; margin: 0 0 36px; }}
article {{ font: 19px/1.62 var(--serif); margin: 32px 0 48px; overflow-wrap: break-word; hanging-punctuation: first; }}
article p {{ text-wrap: pretty; }}
article h2, article h3 {{ font: 700 21px/1.3 var(--serif); color: var(--ink); text-transform: none; letter-spacing: -.01em;
  border: 0; margin: 40px 0 8px; padding: 0; }}
article li {{ border: 0; padding: 4px 0; }}
article blockquote {{ margin: 24px 0; padding-left: 20px; border-left: 2px solid var(--rule); color: var(--muted); }}
article table {{ border-collapse: collapse; font-size: 15px; }}
article td, article th {{ border: 1px solid var(--rule); padding: 4px 8px; }}
mark {{ color: inherit; border-radius: 3px; cursor: pointer; }}
mark.highlight {{ background: var(--hl); }}
mark.question {{ background: var(--q); }}
article .m-highlight, article .m-question, article .picked {{ border-radius: 4px; }}
article .m-highlight {{ background: var(--hl); box-shadow: 0 0 0 6px var(--hl); }}
article .m-question {{ background: var(--q); box-shadow: 0 0 0 6px var(--q); }}
article .picked {{ outline: 1px solid var(--faint); outline-offset: 6px; }}
.bar {{ position: fixed; z-index: 2; left: 50%; transform: translateX(-50%); bottom: calc(20px + env(safe-area-inset-bottom));
  display: flex; gap: 4px; padding: 5px; border-radius: 999px; background: var(--ink); box-shadow: 0 6px 24px rgba(0,0,0,.22); }}
.bar[hidden] {{ display: none; }}
.bar button {{ background: transparent; color: var(--bg); padding: 12px 20px; font-size: 16px; white-space: nowrap; }}
.bar button:hover {{ background: rgba(127,127,127,.25); }}
.thread {{ background: var(--chip); border-radius: 10px; padding: 14px 18px; margin: 0 0 32px; }}
.thread > summary {{ cursor: pointer; font-weight: 600; font-size: 15px; list-style: none; display: flex; justify-content: space-between; gap: 12px; }}
.thread > summary::-webkit-details-marker {{ display: none; }}
.thread > summary::after {{ content: ""; flex: none; width: 7px; height: 7px; margin: 6px 4px 0 0; border: solid var(--muted);
  border-width: 0 1.5px 1.5px 0; transform: rotate(45deg); transition: transform .2s ease; }}
.thread[open] > summary::after {{ transform: rotate(-135deg); margin-top: 10px; }}
.thread p {{ margin: 8px 0 0; color: var(--muted); font-size: 16px; }}
button {{ font: inherit; font-size: 15px; font-weight: 600; color: var(--ink); background: var(--chip);
  border: 0; border-radius: 999px; padding: 8px 18px; cursor: pointer; }}
button[data-kept=true], button[aria-pressed=true] {{ background: var(--ink); color: var(--bg); }}
button.quiet {{ background: transparent; color: var(--faint); font-weight: 500; padding: 8px 10px; }}
button.quiet:hover {{ color: var(--ink); }}
.card {{ border: 1px solid var(--rule); border-radius: 14px; padding: 20px 22px; margin: 0 0 48px; }}
.card .front {{ font: 600 20px/1.35 var(--serif); margin: 0 0 16px; text-wrap: pretty; }}
.card .back {{ margin: 0 0 16px; color: var(--muted); }}
.card .row, .card .options {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.card .options {{ flex-direction: column; align-items: stretch; }}
.card .options button {{ text-align: left; border-radius: 10px; font-weight: 500; }}
.card button.right {{ background: var(--right); }}
.card button.wrong {{ background: var(--wrong); }}
.card button:disabled {{ cursor: default; color: var(--ink); }}
.card .rated {{ color: var(--faint); font-size: 15px; }}
.card button.quiet {{ margin-top: 8px; }}
#game .card, #reveal .card {{ margin: 0 0 32px; }}
#reveal .card {{ margin-top: -16px; }}
.grid {{ position: relative; display: grid; gap: 3px; width: fit-content; margin: 0 auto 48px; touch-action: manipulation; }}
.grid .cell {{ position: relative; width: var(--cell); height: var(--cell); border-radius: 4px; background: var(--chip);
  display: grid; place-items: center; font-weight: 600; font-size: calc(var(--cell) * .5); cursor: pointer; user-select: none; }}
.grid .cell small {{ position: absolute; top: 1px; left: 3px; font-size: 9px; font-weight: 500; color: var(--muted); line-height: 1.2; }}
.grid .cell.on {{ background: var(--q); }}
.grid .cell.at {{ box-shadow: inset 0 0 0 2px var(--ink); }}
.grid .cell.solved {{ background: var(--right); }}
.grid input {{ position: absolute; width: 1px; height: 1px; padding: 0; border: 0; opacity: 0; font-size: 16px; }}
#clues li {{ cursor: pointer; padding: 12px 0; }}
#clues li p {{ margin: 0; color: var(--ink); }}
#clues li b {{ display: inline-block; min-width: 1.6em; color: var(--muted); font-weight: 600; }}
#clues li.done p {{ color: var(--faint); }}
#clues li.on p {{ font-weight: 600; }}
.clue {{ position: fixed; z-index: 2; left: 0; right: 0; bottom: 0; padding: 14px 20px calc(14px + env(safe-area-inset-bottom));
  background: var(--ink); color: var(--bg); font-size: 16px; line-height: 1.4; }}
.clue[hidden] {{ display: none; }}
.clue b {{ margin-right: 8px; }}
a.next {{ display: block; margin-top: 56px; padding-top: 12px; border-top: 1px solid var(--ink); text-decoration: none;
  font: 600 24px/1.25 var(--serif); letter-spacing: -.01em; text-wrap: balance; }}
a.next span {{ display: block; font: 600 12px/1.5 var(--sans); color: var(--muted); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 10px; }}
a.next:hover {{ text-decoration: underline; text-underline-offset: 3px; text-decoration-thickness: 1px; }}
a.next:hover span {{ text-decoration: none; }}
.end {{ font: 700 34px/1.15 var(--serif); letter-spacing: -.02em; margin: 0 0 12px; }}
.after {{ color: var(--muted); margin: 0 0 64px; }}
#settings input, #settings textarea {{ font: inherit; font-size: 15px; color: var(--ink); background: transparent;
  border: 0; border-bottom: 1px solid var(--rule); padding: 8px 0; width: 100%; min-width: 0; }}
#settings textarea {{ border: 1px solid var(--rule); border-radius: 10px; padding: 12px 14px; line-height: 1.5; resize: vertical; }}
#settings input:focus, #settings textarea:focus {{ outline: none; border-color: var(--muted); }}
#settings .row {{ display: grid; gap: 12px; align-items: center; margin-bottom: 4px; }}
#settings .sec {{ grid-template-columns: 1fr auto auto; row-gap: 0; margin-bottom: 20px; }}
#settings .sec [name=what], #settings .sec [name=topics] {{ grid-column: 1 / -1; }}
#settings .sec [name=topics] {{ color: var(--muted); }}
#settings .sec textarea {{ border: 0; border-bottom: 1px solid var(--rule); border-radius: 0; padding: 8px 0; resize: none; overflow: hidden; }}
#settings .row button.quiet {{ min-width: 44px; min-height: 44px; color: var(--muted); font-size: 17px; }}
#settings .feed {{ grid-template-columns: 2fr 3fr auto; }}
#settings .link {{ grid-template-columns: 1fr auto; }}
#settings .sec input[name=name] {{ font-weight: 600; }}
#settings .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
#settings .chip {{ display: inline-flex; align-items: center; background: var(--chip); border-radius: 999px; padding: 2px 4px 2px 14px; font-size: 15px; }}
#settings .chip button {{ padding: 4px 10px; }}
#settings .choice {{ display: flex; gap: 8px; }}
#settings .qr svg {{ display: block; width: 180px; height: 180px; border-radius: 10px; }}
#settings .code {{ font-size: 28px; font-weight: 600; letter-spacing: .08em; margin: 16px 0 0; font-variant-numeric: tabular-nums; }}
#settings .addr {{ color: var(--muted); font-size: 15px; margin: 12px 0 0; }}
#settings .err {{ color: var(--muted); font-size: 14px; margin: 8px 0 0; min-height: 1em; }}
.empty {{ color: var(--muted); }}
#pair input {{ font: inherit; font-size: 28px; letter-spacing: .2em; width: 8ch; color: var(--ink); background: transparent;
  border: 0; border-bottom: 1px solid var(--rule); padding: 8px 0; margin: 8px 16px 0 0; }}
#pair input:focus {{ outline: none; border-color: var(--muted); }}
#pair .err {{ color: var(--muted); font-size: 15px; min-height: 1.5em; }}
@view-transition {{ navigation: auto; }}
::view-transition-old(root), ::view-transition-new(root) {{ animation-duration: .2s; }}
@keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} }}
@keyframes pop {{ from {{ opacity: 0; transform: translate(-50%, 8px); }} }}
@supports not (view-transition-name: none) {{ main {{ animation: rise .3s ease-out backwards; }} }}
article.late, #reveal > *, #card > *, #game > *, .thread[open] > :not(summary) {{ animation: rise .4s cubic-bezier(.2,.7,.2,1) backwards; }}
.bar:not([hidden]) {{ animation: pop .18s ease-out backwards; }}
button {{ transition: transform .12s ease, background-color .2s ease, color .2s ease; }}
button:active {{ transform: scale(.96); }}
li a, a.next, nav a, header a, footer a {{ transition: opacity .15s ease, color .15s ease; }}
li a:active, a.next:active {{ opacity: .55; }}
@media (prefers-reduced-motion: reduce) {{
  *, ::view-transition-group(*), ::view-transition-old(*), ::view-transition-new(*) {{ animation: none !important; transition: none !important; }}
}}
</style>
</head>
<body><main>{head}{body}{nav}</main>{script}</body>
</html>
"""
