"""`paper serve`: the issue and the reader on http://localhost:4747, and the reading log behind them.

- `/` the newest issue, `/<date>` any issue, `/kept` what the reader kept.
- `/read/<id>` the article in a clean reader view, built once from the page (trafilatura) and
  cached. The story so far comes first when the piece continues a thread, open when its text is
  new to the reader. A site that refuses goes straight to the original.
- `/<date>/done` the end of an issue; `/settings` the reader's own files.
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

from . import config, learn, net, phone, reading, settings
from .home import Home, home
from .issue import DAY, Invalid, all_pieces, days, kind, load, sections, threads

PORT = int(os.environ.get("PAPER_PORT") or 4747)
ICON = Path(__file__).with_name("icon.png")
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
    plain = lambda el: " ".join(el.text_content().split())  # noqa: E731
    for el in list(root):
        text = plain(el)
        if el.tag == "p" and len(text) >= 40:
            break
        if len(text) < 40 or (title and text.lower().startswith(title.lower()[:40])):
            root.remove(el)
    return "".join(lxml.html.tostring(el, encoding="unicode") for el in root) or fragment


# pages


def order(h: Home, day: str) -> list[dict]:
    """The issue's pieces in page order: the sections in sections.md's order, then saved links."""
    secs = sections(h)
    pieces = [r for r in load(h, day) if kind(r) == "piece"]
    rank = {s.id: n for n, s in enumerate(secs)}
    placed = [p for p in pieces if not p.get("saved")]
    placed.sort(key=lambda p: rank.get(p.get("section"), len(rank)))  # a renamed section's pieces last
    return placed + [p for p in pieces if p.get("saved")]


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
    named = {s.id: s.name for s in secs}
    for sid in dict.fromkeys(p.get("section") for p in pieces if not p.get("saved")):
        mine = [p for p in pieces if p.get("section") == sid and not p.get("saved")]
        name = named.get(sid) or str(sid).replace("-", " ").capitalize()
        body.append(f"<section><h2>{e(name)}</h2><ol>{''.join(map(item, mine))}</ol></section>")
    saved = [p for p in pieces if p.get("saved")]
    if saved:
        body.append(f"<section><h2>{e(t['saved'])}</h2><ol>{''.join(item(p, False) for p in saved)}</ol></section>")
    if not body:
        body.append(f"<p class=empty>{e(t['empty'])}</p>")
    short = lambda d: config.short_date(h, d)  # noqa: E731
    left = f'<a href="/{prev_day}">← {e(short(prev_day))}</a>' if prev_day else "<span></span>"
    right = f'<a href="/{next_day}">{e(short(next_day))} →</a>' if next_day else "<span></span>"
    mid = f'<span class=links><a href="/kept">{e(t["kept"])}</a><a href="/settings">{e(t["settings"])}</a></span>'
    return _page(h, dateline(day), f"<h1>{e(dateline(day))}</h1>", "".join(body),
                 f"<nav>{left}{mid}{right}</nav>", LOOK_JS + ANSWERS_JS)


def done_page(h: Home, day: str) -> str:
    t, dateline = config.labels(h), config.dateline(h, day)
    nav = (f'<nav><a href="/{day}">← {e(config.short_date(h, day))}</a><span class=links>'
           f'<a href="/kept">{e(t["kept"])}</a><a href="/settings">{e(t["settings"])}</a></span><span></span></nav>')
    return _page(h, t["done"], f"<h1>{e(dateline)}</h1>", f"<p class=end>{e(t['done'])}</p>", nav)


def reader_page(h: Home, piece: dict, art: dict) -> str:
    t = config.labels(h)
    st = reading.state(h).get(piece["id"])
    thread = ""
    if piece.get("thread"):
        th = threads(h).get(piece["thread"])
        if th:
            mark = reading.body_hash(str(th["body"]))
            fresh = not (st and mark in st["shown"])
            reading.log(h, {"ev": "thread", "id": piece["id"], "hash": mark})
            thread = (f"<details class=thread{' open' if fresh else ''}><summary>{e(th['title'])}</summary>"
                      f"<p>{e(str(th['body']))}</p></details>")
    kept = reading.kept(piece, st)
    byline = " · ".join(e(str(x)) for x in (_host(piece["url"]), art.get("author"), art.get("date")) if x)
    if art.get("digest"):
        byline = f'{e(t["digest"])} <a href="{e(piece["url"])}">{e(_host(piece["url"]))}</a>'

    title = re.sub(r"\s+[|–—]\s+[^|–—]+$", "", art.get("title") or "") or piece["head"]  # "Title | Site"
    head = (f'<header><a href="/{piece["day"]}">← {e(config.short_date(h, piece["day"]))}</a></header>{thread}'
            f"<h1 class=title>{e(title)}</h1>" + (f"<p class=byline>{byline}</p>" if byline else ""))
    try:
        seq = order(h, piece["day"])
    except Invalid:
        seq = []
    ids = [p["id"] for p in seq]
    nxt = seq[ids.index(piece["id"]) + 1] if piece["id"] in ids and ids.index(piece["id"]) + 1 < len(ids) else None
    if nxt:
        after = f'<a class=next href="/read/{e(nxt["id"])}"><span>{e(t["next"])}</span>{e(nxt["head"])}</a>'
    else:
        after = f'<a class=next href="/{piece["day"]}/done"><span>{e(t["next"])}</span>{e(t["done"])}</a>'
    foot = (f'<footer><button id=keep data-kept="{str(kept).lower()}">{e(t["keeping"] if kept else t["keep"])}</button>'
            f'<a href="{e(piece["url"])}">{e(t["original"])} ↗</a></footer>{after}')
    data = {
        "id": piece["id"],
        "need": round(reading.words(h, piece["id"]) / reading.WPM * 60000 / 3),
        "had": st["ms"] if st else 0,
        "marks": [{"id": m["id"], "kind": m["kind"], "text": m["text"]}
                  for m in learn.marks(h).values() if m["piece"] == piece["id"]],
        "t": {k: t[k] for k in ("keep", "keeping", "highlight", "question", "remove", "show", "again", "good")},
    }
    script = f"<script>const PAPER = {_json(data)};</script>{READER_JS}"
    return _page(h, title, head, f"<article>{_body(art['html'], title)}</article><div id=card></div>", foot, script)


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
        data["phone"] = {"qr": phone.qr_svg(url), "address": phone.address(PORT)}
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
        return self._send(403, _page(h, "Morning paper", "", f"<p class=empty>{e(t['unpaired'])}</p>"))

    def _body_json(self):
        try:
            return json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
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
            if DAY.match(day) and rest in ("", "done"):
                if not (h.issues / f"{day}.jsonl").exists():
                    return self._send(404, "No such issue.", "text/plain; charset=utf-8")
                return self._send(200, done_page(h, day) if rest else issue_page(h, day))
            if path == "/kept":
                return self._send(200, kept_page(h))
            if path == "/settings":
                return self._send(200, settings_page(h, self._mac()))
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
            if not phone.same_origin(self.headers.get("Origin"), self.headers.get("Host")) or not phone.paired(h, str(data.get("key") or "")):
                return self._send(403, "", "text/plain")
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
        if path == "/look" and data.get("id") in pieces:
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
        if path == "/review" and data.get("id") in learn.cards(h) and data.get("rating") in learn.RATINGS:
            reading.log(h, {"ev": "review", "id": data["id"], "rating": data["rating"]})
            return self._send(204)
        return self._send(404, "", "text/plain")

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
  const {id, need, had, t} = PAPER;
  const article = document.querySelector("article");
  let ms = 0, total = had, progress = 0, last = Date.now(), active = Date.now(), asked = false;
  const post = (url, body) => fetch(url, {method: "POST", body: JSON.stringify(body)});
  const measure = () => {
    const el = document.scrollingElement, end = article.offsetTop + article.offsetHeight;
    progress = Math.max(progress, Math.min(1, (el.scrollTop + innerHeight - article.offsetTop) / Math.max(1, end - article.offsetTop)));
  };
  const tick = () => {
    const now = Date.now();
    if (document.visibilityState === "visible" && now - active < 60000) { ms += now - last; total += now - last; }
    last = now;
  };
  const send = () => {
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
    if (!block || !article.contains(block) || block === picked) return close();
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
  const el = (tag, cls, text) => { const x = document.createElement(tag); if (cls) x.className = cls; if (text != null) x.textContent = text; return x; };
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

  const sections = () => {
    const err = el("p", {class: "err"}), list = el("div", {class: "rows"});
    const rows = () => [...list.children].map(r => Object.fromEntries([...r.querySelectorAll("input")].map(i => [i.name, i.value])));
    const commit = () => save("sections", rows(), err);
    const row = s => {
      const r = el("div", {class: "row sec"},
        el("input", {name: "name", value: s.name, placeholder: t.name, onchange: commit}),
        el("button", {class: "quiet", "aria-label": "↑", onclick: () => { r.previousElementSibling && list.insertBefore(r, r.previousElementSibling); commit(); }}, "↑"),
        el("button", {class: "quiet", "aria-label": t.remove, onclick: () => { r.remove(); commit(); }}, "×"),
        el("input", {name: "what", value: s.what, placeholder: t.what, onchange: commit}),
        el("input", {name: "topics", value: s.topics, placeholder: t.topics, onchange: commit}));
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
    return block(t.phone, qr, el("p", {class: "addr"}, PAPER.phone.address), fresh);
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
:root {{ --bg: #fbfbfa; --ink: #1d1d1f; --muted: #6e6e73; --faint: #a1a1a6; --rule: #e8e8e6; --chip: #f0f0ee;
  --hl: #fdf0a6; --q: #dce9fb; --right: #dcefdc; --wrong: #f8dcdc; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #161617; --ink: #f2f2f2; --muted: #a1a1a6; --faint: #6e6e73; --rule: #2a2a2c; --chip: #222224;
    --hl: #4d4215; --q: #1d3150; --right: #1e3a24; --wrong: #482225; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.55 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased; }}
main {{ max-width: 640px; margin: 0 auto; padding: max(32px, env(safe-area-inset-top)) 20px calc(120px + env(safe-area-inset-bottom)); }}
@media (min-width: 700px) {{ main {{ padding-top: 64px; }} }}
a {{ color: inherit; }}
h1 {{ font-size: 15px; font-weight: 500; color: var(--muted); margin: 0 0 40px; letter-spacing: .01em; }}
section {{ margin: 0 0 48px; }}
h2 {{ font-size: 13px; font-weight: 600; color: var(--faint); text-transform: uppercase; letter-spacing: .08em;
  margin: 0 0 8px; padding-bottom: 8px; border-bottom: 1px solid var(--rule); }}
ol {{ list-style: none; margin: 0; padding: 0; }}
li {{ padding: 16px 0; border-bottom: 1px solid var(--rule); }}
li:last-child {{ border-bottom: 0; }}
li a {{ text-decoration: none; font-size: 20px; font-weight: 600; line-height: 1.3; letter-spacing: -.01em; }}
li a:hover {{ text-decoration: underline; text-underline-offset: 3px; text-decoration-thickness: 1px; }}
li p {{ margin: 6px 0 0; color: var(--muted); }}
li span {{ display: block; margin-top: 6px; font-size: 13px; color: var(--faint); }}
li span a {{ font-size: 13px; font-weight: 400; }}
li.done a, li.done p {{ color: var(--faint); }}
li.answer blockquote {{ margin: 0 0 8px; padding-left: 14px; border-left: 2px solid var(--q); color: var(--muted); cursor: pointer;
  display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }}
li.answer blockquote.open {{ display: block; }}
li.answer p {{ color: var(--ink); }}
nav, footer {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; }}
nav .links {{ display: flex; gap: 20px; }}
nav a, footer a, header a {{ color: var(--muted); font-size: 15px; text-decoration: none; padding: 10px 0; }}
nav a:hover, footer a:hover, header a:hover {{ color: var(--ink); }}
header {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
h1.title {{ font-size: 32px; line-height: 1.2; font-weight: 700; letter-spacing: -.02em; color: var(--ink); margin: 0 0 8px; }}
.byline {{ color: var(--faint); font-size: 15px; margin: 0 0 32px; }}
article {{ font: 19px/1.6 ui-serif, "New York", Georgia, serif; margin: 32px 0 48px; overflow-wrap: break-word; }}
article h2 {{ font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif; }}
article h2 {{ font-size: 21px; color: var(--ink); text-transform: none; letter-spacing: -.01em; border: 0; margin: 40px 0 8px; padding: 0; }}
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
.thread summary {{ cursor: pointer; font-weight: 600; font-size: 15px; }}
.thread p {{ margin: 8px 0 0; color: var(--muted); font-size: 16px; }}
button {{ font: inherit; font-size: 15px; font-weight: 600; color: var(--ink); background: var(--chip);
  border: 0; border-radius: 999px; padding: 8px 18px; cursor: pointer; }}
button[data-kept=true], button[aria-pressed=true] {{ background: var(--ink); color: var(--bg); }}
button.quiet {{ background: transparent; color: var(--faint); font-weight: 500; padding: 8px 10px; }}
button.quiet:hover {{ color: var(--ink); }}
.card {{ border: 1px solid var(--rule); border-radius: 14px; padding: 20px 22px; margin: 0 0 48px; }}
.card .front {{ font-size: 19px; font-weight: 600; line-height: 1.4; margin: 0 0 16px; }}
.card .back {{ margin: 0 0 16px; color: var(--muted); }}
.card .row, .card .options {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.card .options {{ flex-direction: column; align-items: stretch; }}
.card .options button {{ text-align: left; border-radius: 10px; font-weight: 500; }}
.card button.right {{ background: var(--right); }}
.card button.wrong {{ background: var(--wrong); }}
.card button:disabled {{ cursor: default; color: var(--ink); }}
.card .rated {{ color: var(--faint); font-size: 15px; }}
a.next {{ display: block; margin-top: 56px; padding-top: 20px; border-top: 1px solid var(--rule); text-decoration: none;
  font-size: 22px; font-weight: 600; line-height: 1.3; letter-spacing: -.01em; }}
a.next span {{ display: block; font-size: 13px; font-weight: 600; color: var(--faint); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; }}
a.next:hover {{ text-decoration: underline; text-underline-offset: 3px; text-decoration-thickness: 1px; }}
a.next:hover span {{ text-decoration: none; }}
.end {{ font-size: 28px; font-weight: 700; letter-spacing: -.02em; margin: 0 0 64px; }}
#settings input, #settings textarea {{ font: inherit; font-size: 15px; color: var(--ink); background: transparent;
  border: 0; border-bottom: 1px solid var(--rule); padding: 8px 0; width: 100%; min-width: 0; }}
#settings textarea {{ border: 1px solid var(--rule); border-radius: 10px; padding: 12px 14px; line-height: 1.5; resize: vertical; }}
#settings input:focus, #settings textarea:focus {{ outline: none; border-color: var(--muted); }}
#settings .row {{ display: grid; gap: 12px; align-items: center; margin-bottom: 4px; }}
#settings .sec {{ grid-template-columns: 1fr auto auto; row-gap: 0; margin-bottom: 20px; }}
#settings .sec input[name=what], #settings .sec input[name=topics] {{ grid-column: 1 / -1; }}
#settings .sec input[name=topics] {{ color: var(--muted); }}
#settings .feed {{ grid-template-columns: 2fr 3fr auto; }}
#settings .link {{ grid-template-columns: 1fr auto; }}
#settings .sec input[name=name] {{ font-weight: 600; }}
#settings .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
#settings .chip {{ display: inline-flex; align-items: center; background: var(--chip); border-radius: 999px; padding: 2px 4px 2px 14px; font-size: 15px; }}
#settings .chip button {{ padding: 4px 10px; }}
#settings .choice {{ display: flex; gap: 8px; }}
#settings .qr svg {{ display: block; width: 180px; height: 180px; border-radius: 10px; }}
#settings .addr {{ color: var(--muted); font-size: 15px; margin: 12px 0 0; }}
#settings .err {{ color: var(--muted); font-size: 14px; margin: 8px 0 0; min-height: 1em; }}
.empty {{ color: var(--muted); }}
</style>
</head>
<body><main>{head}{body}{nav}</main>{script}</body>
</html>
"""
