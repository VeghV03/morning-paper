"""paper: a morning paper for Claude to write and for the reader to read on their computer and phone.

  paper init       the home folder ($PAPER_HOME, default ~/paper) from the example
  paper check      which outlets and feeds answer, as JSON
  paper feed       every candidate since the last issue, written to candidates.json
  paper context    what the reader did and marked, written to context.json
  paper follow     make running stories the reader's, by thread id (setup)
  paper publish    check issues/<date>.jsonl, move the feed cursor, open the issue
  paper serve      the issue, the reader and settings on http://localhost:4747 and a paired phone
  paper read URL   the article at URL as the reader will see it, as JSON
  paper install    keep `paper serve` running from login
  paper restore C  the recovery code C opens the reading record on this computer

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
import webbrowser
from datetime import date, timedelta
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor

import feedparser
import yaml

from . import feed as feed_mod
from . import brief, cloud, edition, issue, learn, net, reading, server, vault
from .home import commit_pending, home, pending

REPO = Path(__file__).resolve().parents[2]
EXAMPLE = REPO / "example"
PRESETS = REPO / "presets"
LABEL = "local.morning-paper.serve"
AGENT = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"  # macOS
UNIT = Path.home() / ".config" / "systemd" / "user" / "morning-paper.service"  # Linux
RUN_KEY, RUN_NAME = r"Software\Microsoft\Windows\CurrentVersion\Run", "Morning paper"  # Windows


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
            print("made the reading record's key: its recovery code is in Settings on this computer")
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
    (h.root / "context.json").unlink(missing_ok=True)  # the record's plain summary lives only through the run
    if cloud.active():
        built = edition.build(h, day)
        print(f"published {day}: {built['texts']} of {built['pieces']} pieces with text for the phone; "
              "`paper cloud pack` seals it into the data repository")
        return 0
    url = f"http://localhost:{server.PORT}/{day}"
    print(url if _up() else f"{url} (the server is not running: run `paper install` once, or `paper serve`)")
    if args.open:
        webbrowser.open(url)
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


def serve(args) -> int:
    h = home()
    h.root.mkdir(parents=True, exist_ok=True)
    (h.root / ".serve.pid").write_text(str(os.getpid()), encoding="utf-8")  # for `paper install --stop`
    try:
        vault.ensure(h)
        vault.migrate(h)
    except vault.Locked as e:
        print(e, file=sys.stderr)  # the pages say so too, until `paper restore`
    print(f"http://localhost:{server.PORT}", flush=True)
    server.serve()
    return 0


def _env(h) -> dict:
    """What the server needs from the shell the wrapper set up: the home, and Node on the PATH."""
    return {"PAPER_HOME": str(h.root), "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONUTF8": "1"}


def _install_mac(h, again: bool) -> int:
    uid = os.getuid()
    if again:
        if AGENT.exists():
            subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"], capture_output=True)
        return 0
    AGENT.parent.mkdir(parents=True, exist_ok=True)
    AGENT.write_bytes(plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": [sys.executable, "-m", "paper.cli", "serve"],
        "EnvironmentVariables": _env(h),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardErrorPath": str(h.root / "serve.log"),
    }))
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(AGENT)], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(AGENT)], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr.strip(), file=sys.stderr)
        return 1
    print(f"serving http://localhost:{server.PORT} from login ({AGENT})")
    return 0


def _install_linux(h, again: bool) -> int:
    ctl = ["systemctl", "--user"]
    if again:
        if UNIT.exists():
            subprocess.run([*ctl, "restart", UNIT.name], capture_output=True)
        return 0
    if not shutil.which("systemctl"):
        print("install needs systemd; run `paper serve` yourself", file=sys.stderr)
        return 1
    env = "".join(f'Environment="{k}={v}"\n' for k, v in _env(h).items())
    UNIT.parent.mkdir(parents=True, exist_ok=True)
    UNIT.write_text(f"""[Unit]
Description=Morning paper

[Service]
{env}ExecStart="{sys.executable}" -m paper.cli serve
Restart=on-failure
StandardError=append:{h.root / "serve.log"}

[Install]
WantedBy=default.target
""", encoding="utf-8")
    for step in (["daemon-reload"], ["enable", UNIT.name], ["restart", UNIT.name]):
        r = subprocess.run([*ctl, *step], capture_output=True, text=True)
        if r.returncode:
            print(r.stderr.strip(), file=sys.stderr)
            return 1
    print(f"serving http://localhost:{server.PORT} from login ({UNIT})")
    return 0


def _windows_pid(h) -> int | None:
    """The running server's process, when the pid file still names one of the paper's Pythons."""
    try:
        pid = int((h.root / ".serve.pid").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True)
    return pid if "python" in r.stdout.lower() else None


def _install_windows(h, stop: bool, again: bool) -> int:
    import winreg
    pid = _windows_pid(h)
    if pid:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    if stop:
        return 0
    launcher = Path(sys.executable).parents[2] / "serve.pyw"  # .tools/venv/Scripts/python.exe
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:  # absent on a new account
        if again:
            try:
                winreg.QueryValueEx(key, RUN_NAME)
            except FileNotFoundError:
                return 0  # never installed: nothing to start again
        env = "".join(f"os.environ[{k!r}] = {v!r}\n" for k, v in _env(h).items())
        launcher.write_text(f"""import os, sys
{env}sys.stdout = sys.stderr = open({str(h.root / "serve.log")!r}, "a", encoding="utf-8", buffering=1)
from paper.cli import main
sys.exit(main(["serve"]))
""", encoding="utf-8")
        windowless = Path(sys.executable).with_name("pythonw.exe")
        command = [str(windowless), "-X", "utf8", str(launcher)]
        winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(command))
    subprocess.Popen(command, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                     close_fds=True)
    if not again:
        print(f"serving http://localhost:{server.PORT} from login (the {RUN_NAME!r} entry in your startup apps)")
    return 0


def install(args) -> int:
    """Keeps `paper serve` running from login. --again starts it on new code where it was installed;
    --stop stops it while the tools are replaced (Windows locks a running program's files)."""
    h = home()
    if sys.platform == "win32":
        return _install_windows(h, args.stop, args.again)
    if args.stop:
        return 0
    if sys.platform == "darwin":
        return _install_mac(h, args.again)
    return _install_linux(h, args.again)


def cloud_cmd(args) -> int:
    """The data repository: `key` prints the run key for the cloud environment, from this
    computer's recovery code; `unpack` and `pack` open and seal the repository in the run."""
    h = home()
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
            _print({"ok": True, **cloud.pack(h, out, repo, key)})
    except cloud.Locked as e:
        _print({"ok": False, "errors": [str(e)]})
        return 1
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
    pub.add_argument("--open", action="store_true", help="open the issue in the browser")
    sub.add_parser("serve")
    ins = sub.add_parser("install")
    ins.add_argument("--again", action="store_true", help=argparse.SUPPRESS)
    ins.add_argument("--stop", action="store_true", help=argparse.SUPPRESS)
    rs = sub.add_parser("restore")
    rs.add_argument("code", help="the 24-character recovery code from Settings")
    cl = sub.add_parser("cloud")
    cl.add_argument("action", choices=["key", "unpack", "pack"])
    cl.add_argument("--repo", help="the data repository's folder (unpack, pack)")
    cl.add_argument("--code", help="a recovery code (key), instead of this computer's")
    args = p.parse_args(argv)
    return {"init": init, "feed": feed, "context": context, "publish": publish, "serve": serve, "install": install, "check": check, "read": read, "follow": follow, "restore": restore, "cloud": cloud_cmd}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
