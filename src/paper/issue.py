"""The day's issue: sections.md gives the sections, issues/<date>.jsonl the pieces Claude chose,
threads.jsonl the running stories.

A piece is `{"id", "section", "url", "head", "lead"}`, with `"thread": "t-<slug>"` when it
continues a running story. A digest Claude wrote of an article in a language the reader does
not read adds `"digest": true`; its text is digests/<id>.md and `url` is the original. A saved link from inbox.md is `{"id", "saved": true, "url", "head"}`,
with no section. Ids are `r-<date>-<n>`. A thread is `{"id", "title", "body", "since",
"updated"}`: the story so far, shown above the piece in the reader.
"""

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date

from .home import Home

MAX_SECTIONS = 8
PER_SECTION = 3
SAVED = 8
HEAD_CHARS = 60
LEAD_CHARS = 140
THREAD_BYTES = 600
THREADS = 32
DIGEST_WORDS = 450
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Invalid(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Section:
    id: str
    name: str


def section_id(name: str) -> str:
    """The name in lower case, accents dropped, spaces as `-`."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def sections(h: Home) -> list[Section]:
    if not h.sections.exists():
        raise Invalid([f"{h.sections}: missing; run `paper init`"])
    out, errors = [], []
    for n, line in enumerate(h.sections.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, colon, _ = line.partition(":")
        sid = section_id(name)
        if not colon or not sid:
            errors.append(f"{h.sections}:{n}: write a section as 'Name: what belongs in it'")
        elif any(s.id == sid for s in out):
            errors.append(f"{h.sections}:{n}: '{name.strip()}' is there twice")
        else:
            out.append(Section(sid, name.strip()))
    if len(out) > MAX_SECTIONS:
        errors.append(f"{h.sections}: {len(out)} sections; an issue holds {MAX_SECTIONS}")
    if errors:
        raise Invalid(errors)
    return out


def _jsonl(path, errors: list[str]) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as e:
            errors.append(f"{path}:{n}: not JSON ({e})")
            continue
        if not isinstance(row, dict):
            errors.append(f"{path}:{n}: write one JSON object a line")
            continue
        rows.append({**row, "_line": n})
    return rows


def days(h: Home) -> list[str]:
    """Every day with an issue, oldest first."""
    return sorted(p.stem for p in h.issues.glob("*.jsonl") if DAY.match(p.stem))


def load(h: Home, day: str) -> list[dict]:
    path = h.issues / f"{day}.jsonl"
    if not path.exists():
        raise Invalid([f"{path}: missing; write the day's pieces there, one JSON object a line"])
    errors: list[str] = []
    rows = _jsonl(path, errors)
    if errors:
        raise Invalid(errors)
    return rows


def all_pieces(h: Home) -> dict[str, dict]:
    """Every piece of every issue by id, each with its `day`. A broken issue file is skipped."""
    out = {}
    for day in days(h):
        try:
            for p in load(h, day):
                if isinstance(p.get("id"), str):
                    out[p["id"]] = {**p, "day": day}
        except Invalid:
            continue
    return out


def threads(h: Home) -> dict[str, dict]:
    if not h.threads.exists():
        return {}
    errors: list[str] = []
    rows = _jsonl(h.threads, errors)
    if errors:
        raise Invalid(errors)
    out = {}
    for t in rows:
        at = f"{h.threads}:{t['_line']}"
        tid = t.get("id")
        if not isinstance(tid, str) or not tid.startswith("t-"):
            errors.append(f"{at}: needs id, t-<slug>")
        elif tid in out:
            errors.append(f"{at}: {tid} is there twice")
        if not t.get("title") or not t.get("body"):
            errors.append(f"{at}: needs title and body, the story so far")
        elif len(str(t["body"]).encode()) > THREAD_BYTES:
            errors.append(f"{at}: body is {len(str(t['body']).encode())} bytes; {THREAD_BYTES} at most")
        out[tid] = t
    if len(out) > THREADS:
        errors.append(f"{h.threads}: {len(out)} threads; {THREADS} at most, drop the stories that ended")
    if errors:
        raise Invalid(errors)
    return out


def check(h: Home, secs: list[Section], pieces: list[dict], day: str) -> None:
    ids = [s.id for s in secs]
    where = h.issues / f"{day}.jsonl"
    known = threads(h)
    errors = []
    urls = Counter(str(p.get("url", "")).rstrip("/") for p in pieces)
    pids = Counter(p.get("id") for p in pieces)
    for p in pieces:
        at = f"{where}:{p['_line']}"
        pid, url = p.get("id"), str(p.get("url") or "")
        head, lead = str(p.get("head") or ""), str(p.get("lead") or "")
        if not isinstance(pid, str) or not re.match(rf"^r-{day}-\d+$", pid):
            errors.append(f"{at}: needs id, r-{day}-<n>")
        elif pids[pid] > 1:
            errors.append(f"{at}: {pid} is in the issue twice")
        if not url.startswith(("http://", "https://")):
            errors.append(f"{at}: needs url, the article's own address")
        elif urls[url.rstrip("/")] > 1:
            errors.append(f"{at}: {url} is in the issue twice")
        if not head:
            errors.append(f"{at}: needs head, the headline ({HEAD_CHARS} characters at most)")
        elif len(head) > HEAD_CHARS:
            errors.append(f"{at}: head is {len(head)} characters; {HEAD_CHARS} at most")
        if p.get("saved"):
            continue
        if p.get("section") not in ids:
            errors.append(f"{at}: section '{p.get('section')}' is not in sections.md ({', '.join(ids)}); a saved link has \"saved\": true")
        if not lead:
            errors.append(f"{at}: needs lead, what the piece says ({LEAD_CHARS} characters at most)")
        elif len(lead) > LEAD_CHARS:
            errors.append(f"{at}: lead is {len(lead)} characters; {LEAD_CHARS} at most")
        if p.get("digest"):
            path = h.digests / f"{pid}.md"
            if not path.exists():
                errors.append(f"{at}: a digest needs its text in {path}")
            elif (n := len(path.read_text(encoding="utf-8").split())) > DIGEST_WORDS:
                errors.append(f"{at}: {path.name} is {n} words; a digest is {DIGEST_WORDS} at most")
        if p.get("thread") and p["thread"] not in known:
            errors.append(f"{at}: thread '{p['thread']}' is not in threads.jsonl; write the story so far there, or leave the field out")
    for sid, n in Counter(p.get("section") for p in pieces if not p.get("saved")).items():
        if n > PER_SECTION:
            errors.append(f"{where}: {n} pieces in '{sid}'; a section holds {PER_SECTION}")
    if (n := sum(1 for p in pieces if p.get("saved"))) > SAVED:
        errors.append(f"{where}: {n} saved links; an issue brings {SAVED}, the rest wait in inbox.md")
    if errors:
        raise Invalid(errors)


def validate(h: Home, day: str) -> list[dict]:
    """The day's pieces, checked. Raises Invalid with every error at once."""
    if not DAY.match(day):
        raise Invalid([f"'{day}' is not a date; write YYYY-MM-DD"])
    date.fromisoformat(day)
    secs = sections(h)
    pieces = load(h, day)
    check(h, secs, pieces, day)
    return pieces
