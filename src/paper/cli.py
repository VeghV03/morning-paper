"""paper: a morning paper Claude writes in a cloud run, for the reader to read on any device.

  paper init       the home folder ($PAPER_HOME, default ~/paper) from the example
  paper check      which outlets and feeds answer, as JSON
  paper feed       every candidate since the last issue, written to candidates.json
  paper context    what the reader did and marked, written to context.json
  paper follow     make running stories the reader's, by thread id (setup)
  paper publish    check issues/<date>.jsonl, move the feed cursor, build the phone's edition (the run)
  paper read URL   the article at URL as the reader will see it, as JSON
  paper restore C  keep the recovery code C on this computer
  paper cloud      code: the recovery code, for the reader to save; key: the run key; pack, unpack
  paper days       the reader's own 30 days, counted in their own terminal (never in a session)
  paper model      download the local text encoder that groups stories and checks threads
  paper cover      the day's cover from the lead claim and a CC0 archive photo; `cover search` finds photos

The tool never calls a generative model or a model API; Claude does the choosing. It may run a
local text encoder, which turns text into numbers and writes nothing (D107).
"""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor

import feedparser
import httpx
import yaml

from . import feed as feed_mod
from . import article, brief, cloud, config, cover, days, edition, embed, issue, learn, net, reading, vault
from .home import commit_pending, home, pending

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "example"
PRESETS = REPO / "presets"


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
    try:
        if vault.ensure(h):
            print("made the recovery code: the reader saves it from `paper cloud code`, run in their own terminal")
        vault.migrate(h)
    except vault.Locked as e:
        print(e, file=sys.stderr)
        return 1
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
    found = article.extract(args.url)
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
    try:
        if not cloud.active():  # the cloud run has no reading record and no key for one (D46)
            vault.ensure(h)
            learn.refit(h, reading.reviews(h))
        out = brief.context(h) if cloud.active() else reading.context(h)  # the run reads the brief (D47)
    except vault.Locked as e:
        _print({"ok": False, "errors": [str(e)]})
        return 1
    out["today"] = date.today().isoformat()
    out["published_today"] = (h.issues / f"{out['today']}.jsonl").exists() and not pending(h.feed_state).exists()
    out["last_issue"] = next((d for d in reversed(issue.days(h)) if d < out["today"]), None)
    try:
        known = issue.threads(h)
        follows = brief.followed if cloud.active() else reading.followed
        mine = follows(h, known, (date.today() + timedelta(days=1)).isoformat())
        out["threads"] = [{**{k: v for k, v in t.items() if k != "_line"}, **mine.get(t["id"], {})} for t in known.values()]
    except issue.Invalid as e:
        out["threads"] = []
        out["warnings"] = e.errors
    path = h.root / "context.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    _print({"file": str(path), "today": out["today"], "published_today": out["published_today"], "last_issue": out["last_issue"],
            **{k: len(out[k]) for k in ("pieces", "marks", "to_card", "threads")},
            "recovery_unsaved": not cloud.active() and vault.unsaved(h), "warnings": out.get("warnings", [])})
    return 0


def follow(args) -> int:
    """Make running stories the reader's, by their thread ids in threads.jsonl, as setup does for
    the stories they name."""
    h = home()
    try:
        known = issue.threads(h)
    except issue.Invalid as e:
        _print({"ok": False, "errors": e.errors})
        return 1
    missing = [t for t in args.ids if t not in known]
    if missing:
        _print({"ok": False, "errors": [f"{t}: not in threads.jsonl; write the thread first" for t in missing]})
        return 1
    had = {e["id"] for e in reading.events(h) if e.get("ev") == "follow"}
    for t in dict.fromkeys(args.ids):
        if t not in had:
            reading.log(h, {"ev": "follow", "id": t})
    _print({"ok": True, "follows": sorted(had | set(args.ids))})
    return 0


def publish(args) -> int:
    h = home()
    day = args.date or date.today().isoformat()
    try:
        pieces = issue.validate(h, day)
        if note := issue.restated(h, day):
            print(note, file=sys.stderr)
    except issue.Invalid as e:
        print("\n".join(e.errors), file=sys.stderr)
        return 1
    feed_mod.remove_from_inbox(h, [p["url"] for p in pieces if p.get("saved")])
    commit_pending(h.feed_state)
    (h.root / "context.json").unlink(missing_ok=True)  # the record's plain summary lives only through the run
    if cloud.active():
        built = edition.build(h, day)
        print(f"published {day}: {built['texts']} of {built['pieces']} pieces with text for the phone; "
              "`paper cloud pack` seals it into the data repository")
        return 0
    print(f"checked {day}: the morning run builds the phone's edition when it publishes")
    return 0


def model(args) -> int:
    try:
        print(f"the text encoder is in {embed.fetch()}")
    except (embed.Unavailable, httpx.HTTPError, OSError) as e:
        print(f"paper model: {e}", file=sys.stderr)
        return 1
    return 0


def restore(args) -> int:
    """Keep a recovery code as this computer's key for the reading record."""
    try:
        vault.restore(home(), args.code)
    except (ValueError, vault.Locked) as e:
        print(e, file=sys.stderr)
        return 1
    print("restored: this computer reads the record again")
    return 0


def cloud_cmd(args) -> int:
    """`code` prints the recovery code for the reader to save; `key` the run key for the cloud
    environment, from it; `unpack` and `pack` open and seal the data repository in the run."""
    h = home()
    if args.action == "code":  # for the reader's own eyes: never run it where its output is logged
        code = vault.code()
        if not code:
            print("no recovery code on this computer: run `paper init`", file=sys.stderr)
            return 1
        print(code)
        return 0
    if args.action == "key":
        try:
            code = vault.normal(args.code) if args.code else vault.code()
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        if not code:
            print("no recovery code on this computer: run `paper init`, or pass --code", file=sys.stderr)
            return 1
        print(cloud.encoded(cloud.run_key(code)))
        return 0
    if not args.repo:
        print("--repo: the data repository's folder", file=sys.stderr)
        return 1
    repo, out = Path(args.repo).expanduser(), feed_mod.engine_dir() / "out"
    try:
        key = cloud.key_from_env()
        if args.action == "unpack":
            h.root.mkdir(parents=True, exist_ok=True)
            _print({"ok": True, "opened": len(cloud.unpack(h, out, repo, key)), "home": str(h.root)})
        else:
            _print({"ok": True, **cloud.pack(h, out, repo, key, prune=args.prune)})
    except cloud.Locked as e:
        _print({"ok": False, "errors": [str(e)]})
        return 1
    return 0


def days_cmd(args) -> int:
    """The 30 days as a table, from a clone of the data repository (days.py)."""
    if not sys.stdout.isatty():  # a session's shell, a pipe or a file: the counts are the reader's alone (T2)
        print("paper days shows the reader their own reading as numbers: they run it in their own terminal", file=sys.stderr)
        return 1
    repo = Path(args.repo).expanduser()
    if not (repo / ".git").exists():
        print(f"no data repository at {repo}: clone it there first (all of it: the run's commit times are the delivery record)", file=sys.stderr)
        return 1
    if subprocess.run(["git", "-C", str(repo), "pull", "--quiet", "--ff-only"], capture_output=True).returncode:
        print("could not fetch the data repository: counting what is here", file=sys.stderr)
    code = vault.code()
    if not code:
        print("no recovery code on this computer: run `paper restore <recovery code>`", file=sys.stderr)
        return 1
    try:
        print(days.table(days.tally(repo, args.first, date.today(), code)))
    except (cloud.Locked, subprocess.CalledProcessError) as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def cover_cmd(args) -> int:
    """`cover search <words>` prints CC0 candidates; `cover` draws the cover. With --out, one PNG at
    --size (the X4 calls it so). Without, the phone's pair in the edition: light and dark JPEGs at
    twice --size, the density the specimen was approved at, and cover.json for the front page."""
    if args.action == "search":
        found, errors = cover.search(" ".join(args.words))
        _print({"candidates": found, "warnings": errors})
        return 0 if found else 1
    try:
        day = date.fromisoformat(args.date).isoformat()
        w, _, h = args.size.lower().partition("x")
        size = (int(w), int(h))
        crop = tuple(float(f) for f in args.crop.split(",")) if args.crop else None
        if size[0] < 100 or size[1] < 100 or (crop and (len(crop) != 4 or not 0 <= crop[0] < crop[2] <= 1 or not 0 <= crop[1] < crop[3] <= 1)):
            raise ValueError
    except (TypeError, ValueError):
        _print({"ok": False, "errors": ["--date YYYY-MM-DD, --size WxH (100 or more), --crop left,top,right,bottom as fractions"]})
        return 1
    if bool(args.photo) == args.grim:
        _print({"ok": False, "errors": ["either --photo <id from `paper cover search`> or --grim"]})
        return 1
    try:
        rec = cover.record(args.photo) if args.photo else None
        img = cover.photo(rec) if rec else None
    except cover.Refused as e:
        _print({"ok": False, "errors": [str(e)]})
        return 1
    lang = args.lang or config.language(home())
    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(cover.png(cover.draw(day, args.claim, img, size, args.theme, lang, crop)))
        _print({"ok": True, "claim": args.claim, "files": [str(out)]})
        return 0
    folder = home().root / "edition" / day
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for theme in cover.THEMES:
        path = folder / f"cover-{theme}.jpg"
        cover.draw(day, args.claim, img, (size[0] * 2, size[1] * 2), theme, lang, crop).save(path, "JPEG", quality=90)
        files.append(str(path))
    (folder / "cover.json").write_text(json.dumps({"claim": args.claim, "photo": rec}, ensure_ascii=False), encoding="utf-8")
    _print({"ok": True, "claim": args.claim, "files": files})
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
    f = sub.add_parser("follow")
    f.add_argument("ids", nargs="+", metavar="t-<slug>")
    pub = sub.add_parser("publish")
    pub.add_argument("--date", help="YYYY-MM-DD, default today")
    rs = sub.add_parser("restore")
    rs.add_argument("code", help="the 24-character recovery code")
    sub.add_parser("model")
    cl = sub.add_parser("cloud")
    cl.add_argument("action", choices=["code", "key", "unpack", "pack"])
    cl.add_argument("--repo", help="the data repository's folder (unpack, pack)")
    cl.add_argument("--code", help="a recovery code (key), instead of this computer's")
    cl.add_argument("--prune", action="store_true", help="pack: let files gone from the folder go from the repository (the morning run)")
    dy = sub.add_parser("days")
    dy.add_argument("--repo", required=True, help="a clone of the data repository")
    dy.add_argument("--from", dest="first", required=True, type=date.fromisoformat, help="the first morning, YYYY-MM-DD")
    cv = sub.add_parser("cover")
    cv.add_argument("--date", help="YYYY-MM-DD, the issue's day")
    cv.add_argument("--claim", help="the lead claim, one sentence")
    cv.add_argument("--photo", help="a photo id from `paper cover search`: met-, cma- or aic-<number>")
    cv.add_argument("--grim", action="store_true", help="a grim lead: no photo, the claim alone, set large (BR37)")
    cv.add_argument("--crop", help="left,top,right,bottom as fractions of the photo: the picture inside a mount")
    cv.add_argument("--size", default="390x844", help="WxH in pixels, default 390x844")
    cv.add_argument("--theme", choices=list(cover.THEMES), default="light", help="with --out")
    cv.add_argument("--lang", choices=list(config.LABELS), help="the date's language; default the paper's")
    cv.add_argument("--out", help="write one PNG here; without it, the phone's pair goes into the edition")
    cv_sub = cv.add_subparsers(dest="action")
    cs = cv_sub.add_parser("search")
    cs.add_argument("words", nargs="+")
    args = p.parse_args(argv)
    if args.cmd == "cover" and args.action != "search" and not (args.date and args.claim):
        p.error("cover: --date and --claim, or `cover search <words>`")
    return {"init": init, "feed": feed, "context": context, "publish": publish, "check": check, "read": read, "follow": follow, "restore": restore, "model": model, "cloud": cloud_cmd, "days": days_cmd, "cover": cover_cmd}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
