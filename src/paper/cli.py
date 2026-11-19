"""paper: a morning paper for Claude to write and for the reader to read on their Mac and phone.

  paper init       the home folder ($PAPER_HOME, default ~/paper) from the example
  paper check      which outlets and feeds answer, as JSON
  paper feed       every candidate since the last issue, written to candidates.json
  paper context    what the reader did and marked, written to context.json
  paper publish    check issues/<date>.jsonl, move the feed cursor, open the issue
  paper serve      the issue, the reader and settings on http://localhost:4747 and a paired phone
  paper read URL   the article at URL as the reader will see it, as JSON
  paper install    keep `paper serve` running from login (macOS)

The tool never calls a language model; Claude does the choosing.
"""

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor

import feedparser
import yaml

from . import feed as feed_mod
from . import issue, net, reading, server
from .home import commit_pending, home, pending

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "example"
PRESETS = REPO / "presets"
LABEL = "local.morning-paper.serve"
AGENT = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _print(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def init(args) -> int:
    h = home()
    h.issues.mkdir(parents=True, exist_ok=True)
    for src in sorted(EXAMPLE.iterdir()):
        dst = h.root / src.name
        if not dst.exists():
            shutil.copy(src, dst)
            print(f"wrote {dst}")
    if not h.outlets.exists():
        shutil.copy(PRESETS / "world.json", h.outlets)
        print(f"wrote {h.outlets} (presets/world.json)")
    print(f"home: {h.root}")
    return 0


def feed(args) -> int:
    """Writes the candidates to $PAPER_HOME/candidates.json (too long to print) and prints what is in it."""
    h = home()
    data = feed_mod.feed(h)
    out = h.root / "candidates.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    _print({"file": str(out), **{k: len(v) for k, v in data.items() if isinstance(v, list) and k != "warnings"},
            "warnings": data.get("warnings", [])})
    return 0


def read(args) -> int:
    """The article at a URL as the reader view will show it, or why there is none."""
    found = server.extract(args.url)
    if not found:
        _print({"url": args.url, "error": "no article: the site refused, or the page is a wall or a teaser"})
        return 1
    _print({"url": args.url, **{k: found[k] for k in ("title", "author", "date", "words", "text")}})
    return 0


def _probe(entry: dict) -> dict:
    """The first URL of an outlet or feed that answers, and how many items it holds."""
    out = {"id": entry.get("id") or entry.get("name"), "ok": False}
    for url in entry.get("urls") or [entry.get("url")]:
        try:
            raw = net.fetch(str(url))
        except Exception as e:  # noqa: BLE001 - reported, not raised
            out["error"] = str(e)[:120]
            continue
        if entry.get("kind") in ("html", "external"):
            return {**out, "ok": True, "url": url}
        items = len(feedparser.parse(raw).entries)
        if items:
            return {**out, "ok": True, "url": url, "items": items}
        out["error"] = "no items"
    return out


def check(args) -> int:
    h = home()
    outlets = list(feed_mod.outlets(h).values())
    try:
        feeds = (yaml.safe_load(h.feeds.read_text(encoding="utf-8")) or {}).get("feeds") or [] if h.feeds.exists() else []
    except yaml.YAMLError as e:
        feeds, _ = [], print(f"{h.feeds}: {e}", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=12) as pool:
        result = {"outlets": list(pool.map(_probe, [o for o in outlets if not o.get("skip_snapshot")])),
                  "feeds": list(pool.map(_probe, [f for f in feeds if isinstance(f, dict)]))}
    _print(result)
    return 0 if all(r["ok"] for part in result.values() for r in part) else 1


def context(args) -> int:
    h = home()
    out = reading.context(h)
    out["today"] = date.today().isoformat()
    out["published_today"] = (h.issues / f"{out['today']}.jsonl").exists() and not pending(h.feed_state).exists()
    try:
        known = issue.threads(h)
        mine = reading.followed(h, known, (date.today() + timedelta(days=1)).isoformat())
        out["threads"] = [{**{k: v for k, v in t.items() if k != "_line"}, **mine.get(t["id"], {})} for t in known.values()]
    except issue.Invalid as e:
        out["threads"] = []
        out["warnings"] = e.errors
    path = h.root / "context.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    _print({"file": str(path), "today": out["today"], "published_today": out["published_today"],
            **{k: len(out[k]) for k in ("pieces", "marks", "to_card", "threads")},
            "warnings": out.get("warnings", [])})
    return 0


def _up() -> bool:
    try:
        urllib.request.urlopen(f"http://localhost:{server.PORT}/kept", timeout=2)
        return True
    except OSError:
        return False


def publish(args) -> int:
    h = home()
    day = args.date or date.today().isoformat()
    try:
        pieces = issue.validate(h, day)
    except issue.Invalid as e:
        print("\n".join(e.errors), file=sys.stderr)
        return 1
    feed_mod.remove_from_inbox(h, [p["url"] for p in pieces if p.get("saved")])
    commit_pending(h.feed_state)
    url = f"http://localhost:{server.PORT}/{day}"
    print(url if _up() else f"{url} (the server is not running: run `paper install` once, or `paper serve`)")
    if args.open and shutil.which("open"):
        subprocess.run(["open", url], check=False)
    return 0


def serve(args) -> int:
    print(f"http://localhost:{server.PORT}", flush=True)
    server.serve()
    return 0


def install(args) -> int:
    if sys.platform != "darwin":
        print("install is for macOS; elsewhere run `paper serve` yourself", file=sys.stderr)
        return 1
    h = home()
    env = {"PAPER_HOME": str(h.root), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    AGENT.parent.mkdir(parents=True, exist_ok=True)
    AGENT.write_bytes(plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [sys.executable, "-m", "paper.cli", "serve"],
        "EnvironmentVariables": env,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardErrorPath": str(h.root / "serve.log"),
    }))
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(AGENT)], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(AGENT)], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr.strip(), file=sys.stderr)
        return 1
    print(f"serving http://localhost:{server.PORT} from login ({AGENT})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="paper", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("feed")
    sub.add_parser("check")
    r = sub.add_parser("read")
    r.add_argument("url")
    sub.add_parser("context")
    pub = sub.add_parser("publish")
    pub.add_argument("--date", help="YYYY-MM-DD, default today")
    pub.add_argument("--open", action="store_true", help="open the issue in the browser")
    sub.add_parser("serve")
    sub.add_parser("install")
    args = p.parse_args(argv)
    return {"init": init, "feed": feed, "context": context, "publish": publish, "serve": serve, "install": install, "check": check, "read": read}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
