"""`paper feed`: every candidate for the next issue in one object. It fetches; Claude chooses.

- news: the news engine in ../../engine reads the outlets in $PAPER_HOME/outlets.json
  (snapshot, then its claim clustering for each day since the last run), group.py merges what
  is one story across languages and days, and the stories are ranked by `k`, the number of
  independent outlets. Each source URL is reported once, so a story seen before comes back only
  with new coverage. The top stories carry `primary`: the acts, rulings and documents they rest
  on (primary.py).
- follow: entries from $PAPER_HOME/feeds.yaml not reported before, a few per feed.
- inbox: links saved in $PAPER_HOME/inbox.md.
- interests: $PAPER_HOME/interests.md as written.

Nothing here fails the command: a missing engine, Node or feed becomes a `warnings` line.
"""

import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import lxml.html
import yaml
from lxml import etree

from . import group, net, primary, settings
from .home import Home, pending, read_json, write_json

ENGINE = Path(__file__).resolve().parents[2] / "engine"
NODE_MAJOR = 22
TIMEOUT = 600  # seconds per engine script; the snapshot fetches every outlet one by one
MAX_DAYS = 14  # discover at most this many past days
MAX_NEWS = 30
KEEP_DAYS = 30  # how long a reported news URL is remembered
SUMMARY_CHARS = 200
PER_FEED = 3  # follow entries per feed; feeds.yaml max_per_feed


class EngineError(Exception):
    """An engine script failed; the message becomes a warning."""


def engine_dir() -> Path:
    return Path(os.environ.get("PAPER_ENGINE") or ENGINE).expanduser()


def check_node() -> str | None:
    """A warning if Node 22+ is not available, else None."""
    node = shutil.which("node")
    if not node:
        return "news: Node.js not found; run /paper:setup to install the paper's tools"
    try:
        version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
        major = int(version.lstrip("v").split(".")[0])
    except (OSError, ValueError, subprocess.SubprocessError):
        return f"news: {node} --version failed; reinstall Node {NODE_MAJOR}+"
    if major < NODE_MAJOR:
        return f"news: Node {version} is too old; run /paper:setup to install the paper's tools"
    return None


# What the engine may see: the shell basics, locale, network and TLS settings, and its own
# PAPER_* switches. API keys and other secrets in the user's environment stay out.
ENGINE_ENV = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "LANG", "TZ", "SSL_CERT_FILE", "SSL_CERT_DIR"}
ENGINE_ENV_PREFIXES = ("LC_", "PAPER_", "NODE_EXTRA_CA_CERTS")
PROXY_ENV = {"http_proxy", "https_proxy", "no_proxy", "all_proxy"}


def engine_env() -> dict[str, str]:
    """A minimal environment without this tool's virtualenv: the engine's scripts call the
    user's python3 (kozlony.mjs reads PDFs with pdfplumber when pdftotext is missing)."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k in ENGINE_ENV or k.startswith(ENGINE_ENV_PREFIXES) or k.lower() in PROXY_ENV
    }
    if sys.prefix != sys.base_prefix:
        own = str(Path(sys.prefix) / "bin")
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if p.rstrip("/") != own)
    return env


def run_node(root: Path, script: str, args: list[str], timeout: int = TIMEOUT) -> None:
    """Run one engine script with the engine folder as working directory."""
    try:
        r = subprocess.run(
            ["node", f"scripts/{script}", *args], cwd=root, env=engine_env(), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        raise EngineError(f"{script} timed out after {timeout} s") from None
    except OSError as e:
        raise EngineError(f"{script} did not start ({e})") from None
    if r.returncode:
        last = ((r.stderr or "").strip() or (r.stdout or "").strip()).splitlines()[-1:] or [""]
        raise EngineError(f"{script} failed (exit {r.returncode}): {last[0][:200]}")


# news


def _clean_url(url: str) -> str:
    """Unescape and drop tracking parameters, so one article has one URL."""
    url = html.unescape(url.strip())
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.startswith("utm_")]
    return urlunsplit(parts._replace(query=urlencode(query), fragment=""))


def outlets(h: Home) -> dict[str, dict]:
    """The reader's outlets by id, from outlets.json; {} when it is missing or unreadable."""
    try:
        return {str(o["id"]): o for o in json.loads(h.outlets.read_text(encoding="utf-8")) if isinstance(o, dict) and "id" in o}
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def _orgs(root: Path) -> dict[str, str]:
    """Feed id -> organisation name, from the engine's snapshot manifest."""
    out: dict[str, str] = {}
    manifest = root / "out" / "feed-snapshots" / "manifest.jsonl"
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                out[str(rec["id"])] = str(rec["org"])
            except (ValueError, KeyError, TypeError):
                continue
    return out


NO_BODY = {"24", "24.hu"}  # discover.mjs's TILTOTT_TORZS: feeds whose articles refuse downloads


def _score(c: dict) -> int:
    """discover.mjs's triage points, which break ties in `k`: a constitutive source, outlets whose
    text can be read, signs of a rule, a body or public money."""
    brands = {str(m.get("brand") or "") for m in c.get("members") or []}
    body = {b for b in brands if b not in NO_BODY and b not in primary.CONSTITUTIVE}
    only = bool(brands) and brands <= primary.CONSTITUTIVE.keys()
    official = 40 if brands & primary.CONSTITUTIVE.keys() and not only else 0
    return official + min(len(body), 4) * 15 + min(len(c.get("mechanismHits") or []), 4) * 8


def _candidates(data: dict, orgs: dict[str, str], day: str, facts: dict[str, dict]) -> list[dict]:
    """The engine's clusters as stories with deduplicated sources."""
    stories = []
    for c in data.get("clusters") or []:
        sources: dict[str, dict] = {}
        official: dict[str, dict] = {}  # the engine's constitutive members: the record itself, not coverage
        for m in c.get("members") or []:
            url = _clean_url(str(m.get("link") or ""))
            if not url.startswith(("http://", "https://")) or url in sources or url in official:
                continue
            brand = str(m.get("brand") or "")
            title = str(m.get("title") or "").strip()
            if brand in primary.CONSTITUTIVE:
                official[url] = {"title": title, "url": url, "kind": primary.CONSTITUTIVE[brand], "date": day}
                continue
            o = facts.get(brand, {})
            sources[url] = {"org": o.get("org") or orgs.get(brand, brand), "url": url, "lang": o.get("lang", "en"), "title": title, "brand": brand}
            if o.get("paywalled"):
                sources[url]["paywalled"] = True
            if o.get("paywalled") or o.get("piece") is False:
                sources[url]["piece"] = False
            if o.get("channel"):
                sources[url]["channel"] = True
            if o.get("article_fetch") == "blocked":
                sources[url]["fetch"] = False
        if sources:
            stories.append({
                "day": day, "claim": c.get("claimKey"), "score": _score(c),
                "sources": list(sources.values()), "primary": list(official.values()),
            })  # fmt: skip
    return stories


def _k(sources: list[dict]) -> int:
    """Independent sources: distinct organisations by name, so two feeds of one newsroom count
    once; wires (`channel`) not counted unless alone."""
    return len({s["org"] for s in sources if not s.get("channel")}) or 1


def _story(raw: dict) -> dict:
    # Sources that can be the piece first, then the ones that refuse downloads, then the rest.
    sources = sorted(raw["sources"], key=lambda s: ("piece" in s, "fetch" in s))
    title = sources[0]["title"]
    out = {"title": title, "k": _k(sources), "day": raw["day"]}
    out["sources"] = [
        {k: v for k, v in s.items() if k not in ("brand", "channel") and not (k == "title" and v == title)} for s in sources
    ]
    if raw.get("claim"):
        out["claim"] = raw["claim"]
    if raw.get("primary"):
        out["primary"] = raw["primary"]
    return out


def _days(state: dict, today: date) -> list[str]:
    try:
        first = date.fromisoformat(state["news_day"])
    except (KeyError, TypeError, ValueError):
        first = today
    first = max(first, today - timedelta(days=MAX_DAYS - 1))
    return [(first + timedelta(days=i)).isoformat() for i in range((today - first).days + 1)]


def news(h: Home, state: dict, today: date) -> tuple[list[dict], list[str]]:
    """Stories since the last run, most independent sources first."""
    root = engine_dir()
    if not (root / "scripts" / "discover.mjs").is_file():
        return [], [f"news: news engine not found at {root}; set PAPER_ENGINE to its folder"]
    if warning := check_node():
        return [], [warning]
    facts = outlets(h)
    if not facts:
        return [], [f"news: {h.outlets} missing or unreadable; run /setup, or copy a file from presets/"]
    os.environ["PAPER_OUTLETS"] = str(h.outlets)  # the engine reads the reader's outlets
    warnings = []
    try:
        run_node(root, "snapshot-feeds.mjs", [])
    except EngineError as e:
        warnings.append(f"news: {e}")
    orgs = _orgs(root)
    raw: list[dict] = []
    discovered = False
    for day in _days(state, today):
        if not (root / "out" / "feed-snapshots" / day).is_dir():
            continue
        try:  # every cluster, not discover's top 60: most of one story's other-language halves rank below it (D101)
            run_node(root, "cluster-claims.mjs", [day])
            data = json.loads((root / "out" / "genealogy" / f"{day}-claim-clusters.json").read_text(encoding="utf-8"))
        except EngineError as e:
            warnings.append(f"news: {e}")
            continue
        except (OSError, ValueError) as e:
            warnings.append(f"news: out/genealogy/{day}-claim-clusters.json not readable ({e})")
            continue
        discovered = True
        raw += _candidates(data, orgs, day, facts)
    if not discovered:
        return [], warnings or [f"news: no snapshot for {today}; run the engine's snapshot-feeds.mjs to see why"]

    raw, w_group = group.merge(raw, _k)
    warnings += w_group

    # Each URL once: strongest cluster first, nothing reported by an earlier run. Only the
    # MAX_NEWS stories reported are remembered: the engine's every cluster would be ~1,300 URLs a day.
    seen: dict[str, str] = state.get("news_seen", {})
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    seen = {u: d for u, d in seen.items() if d >= cutoff}
    raw.sort(key=lambda s: (-_k(s["sources"]), -s["score"], s["day"]))
    stories, used = [], set()
    for s in raw:
        s["sources"] = [x for x in s["sources"] if x["url"] not in seen and x["url"] not in used]
        used.update(x["url"] for x in s["sources"])
        if s["sources"]:
            stories.append(s)
    stories.sort(key=lambda s: (-_k(s["sources"]), -s["score"]))
    stories = stories[:MAX_NEWS]
    for s in stories:
        for x in s["sources"]:
            seen[x["url"]] = s["day"]
    state["news_seen"] = seen
    state["news_day"] = today.isoformat()
    return [_story(s) for s in stories], warnings


# follow


def _text(fragment: str) -> str:
    if not fragment.strip():
        return ""
    try:
        text = lxml.html.fromstring(fragment).text_content()
    except (ValueError, etree.ParserError):
        text = re.sub(r"<[^>]+>", " ", fragment)
    return " ".join(text.split())


def _summary(entry) -> str:
    content = entry.get("content") or []
    text = _text(entry.get("summary") or (content[0].get("value", "") if content else ""))
    if len(text) <= SUMMARY_CHARS:
        return text
    return text[:SUMMARY_CHARS].rsplit(" ", 1)[0] + "…"


def _entry_id(entry) -> str:
    return str(entry.get("id") or entry.get("link") or entry.get("title") or "")


def _entry_time(entry) -> time.struct_time | None:
    return entry.get("published_parsed") or entry.get("updated_parsed")


def _fetch_feed(url: str):
    return feedparser.parse(net.fetch(url))


def follow(h: Home, state: dict) -> tuple[list[dict], list[str]]:
    """Entries of the feeds in feeds.yaml not reported before: newest first, `max_per_feed` per
    feed, taking each feed's newest entry before anyone's second."""
    if not h.feeds.exists():
        return [], []
    try:
        config = yaml.safe_load(h.feeds.read_text(encoding="utf-8")) or {}
        per_feed = int(config.get("max_per_feed", PER_FEED))
        feeds = [f if isinstance(f, dict) else {"url": f} for f in config.get("feeds") or []]
    except (yaml.YAMLError, AttributeError, TypeError, ValueError) as e:
        return [], [f"follow: {h.feeds}: not readable ({e}); write feeds: [{{name, url}}]"]
    seen_by: dict[str, list[str]] = state.get("follow_seen", {})
    warnings, kept, ranked = [], {}, []
    with ThreadPoolExecutor(max_workers=8) as pool:
        parsed_all = list(pool.map(lambda f: _try(_fetch_feed, str(f.get("url") or "")), feeds))
    for feed, (parsed, error) in zip(feeds, parsed_all):
        url = str(feed.get("url") or "")
        name = str(feed.get("name") or url)
        if url in seen_by:
            kept[url] = seen_by[url]
        if error is not None:
            warnings.append(f"follow: {name}: not fetched ({error})")
            continue
        if parsed.get("bozo") and not parsed.entries:
            warnings.append(f"follow: {name}: not a readable feed ({parsed.get('bozo_exception')})")
            continue
        entries = [e for e in parsed.entries if _entry_id(e)]
        seen = set(seen_by.get(url, []))
        new = [e for e in entries if _entry_id(e) not in seen]
        new.sort(key=lambda e: _entry_time(e) or time.gmtime(0), reverse=True)
        for rank, e in enumerate(new[:per_feed]):
            stamp = _entry_time(e)
            item = {
                "title": " ".join(str(e.get("title") or e.get("link") or "").split()),
                "url": str(e.get("link") or ""),
                "source": name,
                "date": time.strftime("%Y-%m-%d", stamp) if stamp else None,
                "summary": _summary(e),
            }
            ranked.append((rank, stamp or time.gmtime(0), {k: v for k, v in item.items() if v}))
        kept[url] = sorted({_entry_id(e) for e in entries})  # beyond the limit: skipped for good
    state["follow_seen"] = kept
    ranked.sort(key=lambda r: (r[0], tuple(-x for x in r[1][:6])))
    return [item for _, _, item in ranked], warnings


def _try(fn, *args):
    try:
        return fn(*args), None
    except Exception as e:  # noqa: BLE001 - a failing feed is skipped, retried next time
        return None, e


# inbox and interests


def _link(line: str) -> str | None:
    """The URL on an inbox line, or None for blank lines and # lines."""
    s = line.strip()
    if not s or s.startswith("#"):
        return None
    s = re.sub(r"^([-*+]|\d+\.)\s+", "", s).strip("<>")
    return s.split()[0] if s else None


def _same(a: str, b: str) -> bool:
    return a.rstrip("/") == b.rstrip("/")


def inbox(h: Home) -> tuple[list[str], list[str]]:
    if not h.inbox.exists():
        return [], []
    links, warnings = [], []
    for n, line in enumerate(h.inbox.read_text(encoding="utf-8").splitlines(), 1):
        link = _link(line)
        if link is None:
            continue
        if link.startswith(("http://", "https://")):
            links.append(link)
        else:
            warnings.append(f"inbox: {h.inbox}:{n}: '{line.strip()[:60]}' is not a link; write one http(s) link per line")
    return links, warnings


def fold_saved(h: Home) -> list[str]:
    """The links the phone saved, a file each in `saved/` so a save never meets the run's own edit
    of inbox.md (D86), moved into inbox.md. Returns them."""
    d = h.root / "saved"
    files = sorted(d.glob("*.txt")) if d.is_dir() else []
    links = [x for f in files for x in map(_link, f.read_text(encoding="utf-8").splitlines()) if x]
    if links:
        text = h.inbox.read_text(encoding="utf-8") if h.inbox.exists() else settings.INBOX_HEAD
        h.inbox.write_text(text.rstrip("\n") + "\n" + "\n".join(links) + "\n", encoding="utf-8")
    for f in files:
        f.unlink()
    return links


def remove_from_inbox(h: Home, urls: list[str]) -> list[str]:
    """Drop the lines holding these links from inbox.md; returns the links removed."""
    if not urls or not h.inbox.exists():
        return []
    removed, keep = [], []
    for line in h.inbox.read_text(encoding="utf-8").splitlines(keepends=True):
        link = _link(line)
        if link and any(_same(link, u) for u in urls):
            removed.append(link)
        else:
            keep.append(line)
    if removed:
        tmp = h.inbox.with_name(h.inbox.name + ".tmp")
        tmp.write_text("".join(keep), encoding="utf-8")
        tmp.replace(h.inbox)
    return removed


def interests(h: Home) -> str | None:
    if not h.interests.exists():
        return None
    return h.interests.read_text(encoding="utf-8").strip() or None


def feed(h: Home) -> dict:
    """Every candidate since the last issue: news, follow, inbox, interests, warnings."""
    state = read_json(h.feed_state, {})
    since = state.get("last")
    today = date.today()
    stories, w_news = news(h, state, today)
    entries, w_follow = follow(h, state)
    w_primary = primary.attach(stories, engine_dir(), today, lambda *a: run_node(*a)) if stories else []
    fold_saved(h)
    links, w_inbox = inbox(h)
    state["last"] = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(pending(h.feed_state), state)
    return {
        "since": since,
        "news": stories,
        "follow": entries,
        "inbox": links,
        "interests": interests(h),
        "warnings": w_news + w_primary + w_follow + w_inbox,
    }
