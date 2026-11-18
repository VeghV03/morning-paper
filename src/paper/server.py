"""`paper serve`: the issue and the reader on http://localhost:4747, and the reading log behind them.

- `/` the newest issue, `/<date>` any issue, `/kept` what the reader kept.
- `/read/<id>` the article in a clean reader view, built once from the page (trafilatura) and
  cached. The story so far comes first when the piece continues a thread, open when its text is
  new to the reader. A site that refuses goes straight to the original.
- `POST /log` reading heartbeats from the reader view, `POST /keep/<id>` keep or let go.

Only localhost is served: the log is the reader's own.
"""

import html
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from . import config, net, reading
from .home import Home, home
from .issue import DAY, Invalid, all_pieces, days, load, sections, threads

PORT = int(os.environ.get("PAPER_PORT") or 4747)
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


def issue_page(h: Home, day: str) -> str:
    t, dateline = config.labels(h), lambda d: config.dateline(h, d)
    secs = sections(h)
    pieces = load(h, day)
    st = reading.state(h)
    for p in pieces:
        if isinstance(p.get("id"), str):
            reading.log(h, {"ev": "seen", "id": p["id"]})
    all_days = days(h)
    i = all_days.index(day)
    prev_day = all_days[i - 1] if i > 0 else None
    next_day = all_days[i + 1] if i + 1 < len(all_days) else None

    def item(p: dict, lead: bool = True) -> str:
        s = st.get(p.get("id"))
        done = " class=done" if reading.finished(h, p["id"], s) else ""
        out = f'<li{done}><a href="/read/{e(p["id"])}">{e(p["head"])}</a>'
        if lead and p.get("lead"):
            out += f"<p>{e(p['lead'])}</p>"
        return out + f"<span>{e(_host(p['url']))}</span></li>"

    body = []
    for sec in secs:
        mine = [p for p in pieces if p.get("section") == sec.id and not p.get("saved")]
        if mine:
            body.append(f"<section><h2>{e(sec.name)}</h2><ol>{''.join(map(item, mine))}</ol></section>")
    saved = [p for p in pieces if p.get("saved")]
    if saved:
        body.append(f"<section><h2>{e(t['saved'])}</h2><ol>{''.join(item(p, False) for p in saved)}</ol></section>")
    if not body:
        body.append(f"<p class=empty>{e(t['empty'])}</p>")
    nav = []
    if prev_day:
        nav.append(f'<a href="/{prev_day}">← {e(dateline(prev_day))}</a>')
    nav.append(f'<a href="/kept">{e(t["kept"])}</a>')
    if next_day:
        nav.append(f'<a href="/{next_day}">{e(dateline(next_day))} →</a>')
    return PAGE.format(lang=config.language(h), title=e(dateline(day)), head=f"<h1>{e(dateline(day))}</h1>",
                       body="".join(body), nav=f"<nav>{''.join(nav)}</nav>", script="")


def reader_page(h: Home, piece: dict, art: dict) -> str:
    t, dateline = config.labels(h), lambda d: config.dateline(h, d)
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
    byline = " · ".join(e(str(x)) for x in (art.get("author"), art.get("date")) if x)
    if art.get("digest"):
        byline = f'{e(t["digest"])} <a href="{e(piece["url"])}">{e(_host(piece["url"]))}</a>'

    title = re.sub(r"\s+[|–—]\s+[^|–—]+$", "", art.get("title") or "") or piece["head"]  # "Title | Site"
    head = (f'<header><a href="/{piece["day"]}">← {e(dateline(piece["day"]))}</a>'
            f'<a href="{e(piece["url"])}">{e(_host(piece["url"]))} ↗</a></header>{thread}'
            f"<h1 class=title>{e(title)}</h1>" + (f"<p class=byline>{byline}</p>" if byline else ""))
    foot = (f'<footer><button id=keep data-kept="{str(kept).lower()}">{e(t["keeping"] if kept else t["keep"])}</button>'
            f'<a href="{e(piece["url"])}">{e(t["original"])} ↗</a></footer>')
    script = (READER_JS.replace("__ID__", json.dumps(piece["id"]))
              .replace("__KEEP__", json.dumps(t["keep"])).replace("__KEEPING__", json.dumps(t["keeping"])))
    return PAGE.format(lang=config.language(h), title=e(title), head=head,
                       body=f"<article>{_body(art['html'], title)}</article>", nav=foot, script=script)


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
    nav = f'<nav><a href="/{latest[0]}">← {e(dateline(latest[0]))}</a></nav>' if latest[0] else ""
    return PAGE.format(lang=config.language(h), title=e(t["kept"]), head=f"<h1>{e(t['kept'])}</h1>", body=body, nav=nav, script="")


class Handler(BaseHTTPRequestHandler):
    server_version = "news"

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

    def _local(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in {"localhost", "127.0.0.1"}

    def do_GET(self):
        if not self._local():
            return self._send(403, "localhost only")
        h, path = home(), urlsplit(self.path).path.rstrip("/") or "/"
        try:
            if path == "/":
                all_days = days(h)
                if not all_days:
                    t = config.labels(h)
                    return self._send(200, PAGE.format(lang=config.language(h), title="Morning paper", head="",
                                                       body=f"<p class=empty>{e(t['no_issue'])}</p>", nav="", script=""))
                return self._send(302, location=f"/{all_days[-1]}")
            if DAY.match(path[1:]):
                if not (h.issues / f"{path[1:]}.jsonl").exists():
                    return self._send(404, "No such issue.", "text/plain; charset=utf-8")
                return self._send(200, issue_page(h, path[1:]))
            if path == "/kept":
                return self._send(200, kept_page(h))
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
        if not self._local():
            return self._send(403, "localhost only")
        h, path = home(), urlsplit(self.path).path
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self._send(400, "not JSON", "text/plain")
        pieces = all_pieces(h)
        if path == "/log" and data.get("id") in pieces:
            ms = max(0, min(int(data.get("ms") or 0), 120_000))  # a heartbeat covers at most two minutes
            progress = max(0.0, min(float(data.get("progress") or 0), 1.0))
            reading.log(h, {"ev": "read", "id": data["id"], "ms": ms, "progress": round(progress, 3)})
            return self._send(204)
        if path.startswith("/keep/") and path.removeprefix("/keep/") in pieces:
            reading.log(h, {"ev": "keep", "id": path.removeprefix("/keep/"), "kept": bool(data.get("kept"))})
            return self._send(204)
        return self._send(404, "", "text/plain")


def serve(port: int = PORT) -> None:
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


READER_JS = """<script>
(() => {
  const id = __ID__;
  let ms = 0, progress = 0, last = Date.now(), active = Date.now();
  const measure = () => {
    const el = document.scrollingElement;
    progress = Math.max(progress, Math.min(1, (el.scrollTop + innerHeight) / el.scrollHeight));
  };
  const tick = () => {
    const t = Date.now();
    if (document.visibilityState === "visible" && t - active < 60000) ms += t - last;
    last = t;
  };
  const send = () => {
    tick(); measure();
    if (!ms && !progress) return;
    navigator.sendBeacon("/log", new Blob([JSON.stringify({id, ms, progress})], {type: "application/json"}));
    ms = 0;
  };
  for (const ev of ["scroll", "keydown", "pointermove", "touchstart"])
    addEventListener(ev, () => { tick(); active = Date.now(); measure(); }, {passive: true});
  document.addEventListener("visibilitychange", () => document.visibilityState === "hidden" ? send() : (last = Date.now()));
  addEventListener("pagehide", send);
  setInterval(send, 15000);
  measure();
  const keep = document.getElementById("keep");
  keep.addEventListener("click", async () => {
    const kept = keep.dataset.kept !== "true";
    await fetch("/keep/" + encodeURIComponent(id), {method: "POST", body: JSON.stringify({kept})});
    keep.dataset.kept = String(kept);
    keep.textContent = kept ? __KEEPING__ : __KEEP__;
  });
})();
</script>"""

PAGE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg: #fbfbfa; --ink: #1d1d1f; --muted: #6e6e73; --faint: #a1a1a6; --rule: #e8e8e6; --chip: #f0f0ee; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #161617; --ink: #f2f2f2; --muted: #a1a1a6; --faint: #6e6e73; --rule: #2a2a2c; --chip: #222224; }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.55 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased; }}
main {{ max-width: 640px; margin: 0 auto; padding: 64px 20px 96px; }}
a {{ color: inherit; }}
h1 {{ font-size: 15px; font-weight: 500; color: var(--muted); margin: 0 0 48px; letter-spacing: .01em; }}
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
li.done a, li.done p {{ color: var(--faint); }}
nav, footer {{ display: flex; justify-content: space-between; gap: 16px; align-items: center; }}
nav a, footer a, header a {{ color: var(--muted); font-size: 15px; text-decoration: none; }}
nav a:hover, footer a:hover, header a:hover {{ color: var(--ink); }}
header {{ display: flex; justify-content: space-between; margin-bottom: 40px; }}
h1.title {{ font-size: 32px; line-height: 1.2; font-weight: 700; letter-spacing: -.02em; color: var(--ink); margin: 0 0 8px; }}
.byline {{ color: var(--faint); font-size: 15px; margin: 0 0 32px; }}
article {{ font-size: 19px; line-height: 1.65; margin: 32px 0 48px; overflow-wrap: break-word; }}
article h2 {{ font-size: 21px; color: var(--ink); text-transform: none; letter-spacing: -.01em; border: 0; margin: 40px 0 8px; padding: 0; }}
article li {{ border: 0; padding: 4px 0; }}
article blockquote {{ margin: 24px 0; padding-left: 20px; border-left: 2px solid var(--rule); color: var(--muted); }}
article table {{ border-collapse: collapse; font-size: 15px; }}
article td, article th {{ border: 1px solid var(--rule); padding: 4px 8px; }}
.thread {{ background: var(--chip); border-radius: 10px; padding: 14px 18px; margin: 0 0 32px; }}
.thread summary {{ cursor: pointer; font-weight: 600; font-size: 15px; }}
.thread p {{ margin: 8px 0 0; color: var(--muted); font-size: 16px; }}
button {{ font: inherit; font-size: 15px; font-weight: 600; color: var(--ink); background: var(--chip);
  border: 0; border-radius: 999px; padding: 8px 18px; cursor: pointer; }}
button[data-kept=true] {{ background: var(--ink); color: var(--bg); }}
.empty {{ color: var(--muted); }}
</style>
</head>
<body><main>{head}{body}{nav}</main>{script}</body>
</html>
"""
