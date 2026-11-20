"""The reader's own 30 days (decisions/2026-11-20-thirty-days.md): per morning, whether the issue
was delivered, opened and finished, counted on the reader's computer from a clone of the data
repository.

Delivered is the run's "Issue <date>" commit landing by BY, the computer's local time (T1, T5):
nothing more is logged for it. Opened and finished come from the devices' week files, opened here
with the record key and counted only on the issue's own calendar day (T6). Nothing is written. The
cloud run cannot call this, since it holds no recovery code (D46, D47), and a Claude session must
not: the counts are for the reader's own terminal (T2).
"""

import json
import re
import subprocess
from datetime import date, datetime, time, timedelta, tzinfo
from pathlib import Path

from . import cloud, reading, vault

DAYS = 30
BY = time(6, 0)
PASS = (27, 21, 15)  # delivered, opened, with a piece finished (T8: guesses, measured against nothing)
ISSUE = re.compile(r"^Issue \d{4}-\d{2}-\d{2}$")  # the subject scripts/cloud-run.sh commits with


def _sealed(repo: Path, pattern: str, key: bytes):
    for f in sorted(repo.glob(pattern + cloud.SUFFIX)):
        rel = f.relative_to(repo).as_posix()[: -len(cloud.SUFFIX)]
        yield cloud.open_(key, rel, f.read_bytes()).decode("utf-8")


def delivered(repo: Path, tz: tzinfo | None = None) -> dict[str, datetime]:
    """Per local day, when the day's first "Issue" commit landed."""
    log = subprocess.run(["git", "-C", str(repo), "log", "--format=%cI%x09%s"],
                         capture_output=True, text=True, check=True).stdout
    out: dict[str, datetime] = {}
    for line in log.splitlines():
        t, _, subject = line.partition("\t")
        if ISSUE.match(subject):
            at = datetime.fromisoformat(t).astimezone(tz)
            day = at.date().isoformat()
            out[day] = min(at, out.get(day, at))
    return out


def tally(repo: Path, first: date, today: date, code: str, tz: tzinfo | None = None) -> list[dict]:
    """A row for each morning from `first`, up to DAYS of them and no later than `today`:
    `{day, at, delivered, opened, finished}`, `at` the time the issue landed and `finished` how
    many of its pieces were finished that day. Raises cloud.Locked when `code` is not the paper's."""
    pieces: dict[str, dict] = {}
    for text in _sealed(repo, "home/edition/months/*.json", cloud.run_key(code)):
        pieces.update(json.loads(text).get("pieces") or {})
    same_day: dict[str, list[dict]] = {}  # an issue's events made on its own day
    for text in _sealed(repo, "record/*/*.jsonl", vault._derive(code)):
        for line in filter(None, text.splitlines()):
            e = json.loads(line)
            p = pieces.get(e.get("id"))
            if p and datetime.fromisoformat(e["t"]).astimezone(tz).date().isoformat() == p["day"]:
                same_day.setdefault(p["day"], []).append(e)
    landed, rows = delivered(repo, tz), []
    for n in range(DAYS):
        day = (first + timedelta(days=n)).isoformat()
        if day > today.isoformat():
            break
        st, at = reading.state(None, same_day.get(day, [])), landed.get(day)
        rows.append({"day": day, "at": at.strftime("%H:%M") if at else None,
                     "delivered": bool(at) and at.time() <= BY,
                     "opened": any(s["seen"] for s in st.values()),
                     "finished": sum(s["progress"] >= reading.FINISHED
                                     and s["ms"] >= (pieces[pid].get("words") or 0) / reading.WPM * 60000 / 3
                                     for pid, s in st.items())})
    return rows


def table(rows: list[dict]) -> str:
    out = ["day         delivered  opened  finished"]
    for r in rows:
        at = "-" if not r["at"] else r["at"] if r["delivered"] else r["at"] + " late"
        out.append(f"{r['day']}  {at:<10} {'yes' if r['opened'] else '-':<7} {r['finished']}")
    got = (sum(r["delivered"] for r in rows), sum(r["opened"] for r in rows), sum(r["finished"] > 0 for r in rows))
    n = sum(r["finished"] for r in rows)
    out.append(f"\n{len(rows)} of {DAYS} mornings: delivered {got[0]}, opened {got[1]}, "
               f"finished on {got[2]} ({n} piece{'' if n == 1 else 's'})")
    out.append("pass mark: delivered {}, opened {}, finished on {}".format(*PASS))
    if len(rows) == DAYS:
        out.append("passed" if all(g >= p for g, p in zip(got, PASS)) else "not passed")
    return "\n".join(out)
