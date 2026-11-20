"""An article as the phone's reader view shows it: fetched and cut to its text (trafilatura), with
the page's scraps around it dropped (the title again, credits, sign-ups, related links), and its
byline. Claude's digests are shown the same way. The morning run builds the edition from these
(edition.py); `paper read` shows what a link would give.
"""

import html
import re
from urllib.parse import urlsplit

from . import config, net
from .home import Home

MIN_TEXT = 400  # characters; less is a cookie wall or a teaser, not the article
NO_FETCH = {"24.hu"}
e = html.escape


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").removeprefix("www.")


# the article


def extract(url: str) -> dict:
    """{title, author, date, html, text, words} of the article at `url`, as the reader view shows
    it; {} when the site refuses or the page holds no article."""
    if host(url) in NO_FETCH:
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


def digest(h: Home, piece: dict) -> dict:
    """A digest Claude wrote, as the reader view shows an article: paragraphs, `> ` lines quoted."""
    text = (h.digests / f"{piece['id']}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[-1]  # front matter is for Claude, not the reader
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    out = "".join(
        f"<blockquote>{e(' '.join(l.lstrip('> ') for l in b.splitlines()))}</blockquote>" if b.startswith(">")
        else f"<h2>{e(b.lstrip('# '))}</h2>" if b.startswith("#") else f"<p>{e(' '.join(b.splitlines()))}</p>"
        for b in blocks
    )
    return {"title": piece["head"], "html": out, "digest": True}


def body(fragment: str, title: str = "") -> str:
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


def authors(raw, url: str) -> str:
    """Up to three names, each once, without the outlet's own name, "Szerző", or a month the page
    glued on ("Charlie Wood November"; "April Rubin" keeps her name)."""
    months = {m for lang in config.LABELS.values() for m in lang["months"].lower().split()}
    site, names = host(url).split(".")[0], {}
    for name in re.split(r"\s*[;,]\s*|\s+and\s+|\s+és\s+", str(raw or "")):
        words = name.split()
        if len(words) >= 3 and words[-1].lower() in months:
            words = words[:-1]
        key = " ".join(words).replace("-", " ").lower()
        if words and key not in ("szerzo", "szerző", site) and len(key) >= 3 and (key not in names or "-" in names[key]):
            names[key] = " ".join(words)  # "Weiler-Vilmos; Weiler Vilmos" is one writer
    return ", ".join(list(names.values())[:3])


def when(h: Home, raw, day: str) -> str:
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

