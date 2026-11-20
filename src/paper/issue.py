"""The day's issue: sections.md gives the sections, issues/<date>.jsonl the pieces Claude chose,
threads.jsonl the running stories.

A piece is `{"id", "section", "url", "head", "lead"}`, with `"thread": "t-<slug>"` when it
continues a running story. In a steered section (its line in sections.md lists topics after a
`|`), a piece also names its `topic`, one from that list, and its `fit`: `fits` when it follows
what the reader reads, `tries` when it tests something they have not shown interest in. A digest Claude wrote of an article in a language the reader does
not read adds `"digest": true`; its text is digests/<id>.md and `url` is the original. A saved link from inbox.md is `{"id", "saved": true, "url", "head"}`,
with no section. Ids are `r-<date>-<n>`. A thread is `{"id", "title", "since", "entries"}`, a
running story: each entry `{"day", "text"}`, with `"piece": "r-…"` when an issue carried that
day's news, oldest first. The reader sees the entries since they last opened the story (Since you
left, at the top of the issue) and the rest folded under them. An older thread with one `body`
paragraph reads as one entry dated `updated`. An entry written since the last issue may not
restate an earlier entry of its story (`restated`, D104).

The issue also carries what the reader learns from:
- an answer, `{"id": "a-<date>-<n>", "answer": "h-…", "text"}`: Claude's reply to a question the
  reader marked (marks.jsonl), at most ANSWER_WORDS, shown at the top of the issue;
- a card, `{"id": "c-<date>-<n>", "card": "flip", "front", "back", "from"}` or
  `{"id", "card": "choice", "prompt", "options": [three], "answer": <0-2>, "from"}`, where `from`
  is the piece or mark it comes from. Cards come due in the reader after a finished piece.

And the games (each a choice of three, `"prompt", "options": [three], "answer": <0-2>`):
- a prediction, `{"id": "p-<date>-<n>", "predict": "r-…", …}`: asked when the piece opens, about
  its main finding, answered by reading it; PREDICTS an issue at most;
- a link, `{"id": "l-<date>-<n>", "link": "r-…", "from": "r-…", …}`: on a piece with a thread,
  what happened in `from`, an earlier piece of the story the reader opened; asked before the
  story so far;
- the Sunday crossword, `{"id": "x-<date>", "crossword": [{"answer", "clue", "piece"}, …]}`,
  from pieces of the past week the reader opened; crossword.py lays it out.
"""

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from . import embed
from .home import Home

MAX_SECTIONS = 8
PER_SECTION = 3
SAVED = 8
HEAD_CHARS = 60
LEAD_CHARS = 140
ENTRY_CHARS = 280
THREAD_BYTES = 4000  # every entry's text together
THREADS = 32
DIGEST_WORDS = 450
ANSWER_WORDS = 120
CARDS = 12
PREDICTS = 3
CLUE_CHARS = 90
FITS = ("fits", "tries")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RESTATES = 0.93  # with no new number or name; set on 17 pairs written for it (D104)


class Invalid(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Section:
    id: str
    name: str
    what: str = ""
    topics: tuple[str, ...] = ()


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
        name, colon, rest = line.partition(":")
        what, _, topics = rest.partition("|")
        sid = section_id(name)
        if not colon or not sid:
            errors.append(f"{h.sections}:{n}: write a section as 'Name: what belongs in it'")
        elif any(s.id == sid for s in out):
            errors.append(f"{h.sections}:{n}: '{name.strip()}' is there twice")
        else:
            out.append(Section(sid, name.strip(), what.strip(), tuple(x.strip() for x in topics.split(",") if x.strip())))
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


def kind(row: dict) -> str:
    """`piece`, `answer`, `card`, `predict`, `link` or `crossword`, by the id's prefix."""
    pid = str(row.get("id") or "")
    return {"a-": "answer", "c-": "card", "p-": "predict", "l-": "link", "x-": "crossword"}.get(pid[:2], "piece")


def load(h: Home, day: str) -> list[dict]:
    path = h.issues / f"{day}.jsonl"
    if not path.exists():
        raise Invalid([f"{path}: missing; write the day's pieces there, one JSON object a line"])
    errors: list[str] = []
    rows = _jsonl(path, errors)
    if errors:
        raise Invalid(errors)
    return rows


def all_rows(h: Home, what: str = "piece") -> dict[str, dict]:
    """Every row of one kind in every issue by id, each with its `day`. A broken file is skipped."""
    out = {}
    for day in days(h):
        try:
            for p in load(h, day):
                if isinstance(p.get("id"), str) and kind(p) == what:
                    out[p["id"]] = {**p, "day": day}
        except Invalid:
            continue
    return out


def all_pieces(h: Home) -> dict[str, dict]:
    return all_rows(h, "piece")


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
        if "entries" not in t and t.get("body"):  # the one-paragraph threads before entries
            t["entries"] = [{"day": str(t.get("updated") or t.get("since") or ""), "text": str(t["body"]), "old": True}]
        entries = t.get("entries")
        if not t.get("title"):
            errors.append(f"{at}: needs title, the story's name")
        if not isinstance(entries, list) or not entries:
            errors.append(f"{at}: needs entries, the story's developments: {{\"day\", \"text\"}} each, oldest first")
            entries = []
        last = ""
        for n, x in enumerate(entries, 1):
            x = x if isinstance(x, dict) else {}
            day, text = str(x.get("day") or ""), str(x.get("text") or "")
            if not DAY.match(day):
                errors.append(f"{at}: entry {n}: needs day, YYYY-MM-DD")
            elif day < last:
                errors.append(f"{at}: entry {n}: entries go oldest first")
            else:
                last = day
            if not text:
                errors.append(f"{at}: entry {n}: needs text, what happened that day")
            elif len(text) > ENTRY_CHARS and not x.get("old"):
                errors.append(f"{at}: entry {n}: text is {len(text)} characters; {ENTRY_CHARS} at most")
            if x.get("piece") is not None and not re.match(r"^r-\d{4}-\d{2}-\d{2}-\d+$", str(x["piece"])):
                errors.append(f"{at}: entry {n}: piece names the issue's piece that carried it (r-…), or is left out")
        if (size := sum(len(str(x.get("text") or "").encode()) for x in entries if isinstance(x, dict))) > THREAD_BYTES:
            errors.append(f"{at}: the entries are {size} bytes; {THREAD_BYTES} at most, shorten the oldest")
        t["updated"] = last
        out[tid] = t
    if len(out) > THREADS:
        errors.append(f"{h.threads}: {len(out)} threads; {THREADS} at most, drop the stories that ended")
    if errors:
        raise Invalid(errors)
    return out


def check(h: Home, secs: list[Section], rows: list[dict], day: str) -> None:
    ids = [s.id for s in secs]
    by_id = {s.id: s for s in secs}
    where = h.issues / f"{day}.jsonl"
    known = threads(h)
    errors = []
    pieces = [r for r in rows if kind(r) == "piece"]
    _check_learning(h, [r for r in rows if kind(r) != "piece"], {p.get("id"): {**p, "day": day} for p in pieces}, day, errors)
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
        sec = by_id.get(p.get("section"))
        if sec and sec.topics:
            if p.get("topic") not in sec.topics:
                errors.append(f"{at}: '{sec.name}' is steered; topic must be one of: {', '.join(sec.topics)}")
            if p.get("fit") not in FITS:
                errors.append(f"{at}: '{sec.name}' is steered; fit must be fits or tries")
        if p.get("thread") and p["thread"] not in known:
            errors.append(f"{at}: thread '{p['thread']}' is not in threads.jsonl; write the story there, or leave the field out")
    for sid, n in Counter(p.get("section") for p in pieces if not p.get("saved")).items():
        if n > PER_SECTION:
            errors.append(f"{where}: {n} pieces in '{sid}'; a section holds {PER_SECTION}")
    if (n := sum(1 for p in pieces if p.get("saved"))) > SAVED:
        errors.append(f"{where}: {n} saved links; an issue brings {SAVED}, the rest wait in inbox.md")
    if errors:
        raise Invalid(errors)


def _choice(r: dict, at: str, errors: list[str], what: str) -> None:
    opts = r.get("options")
    if not r.get("prompt") or not isinstance(opts, list) or len(opts) != 3 or not all(isinstance(o, str) and o for o in opts):
        errors.append(f"{at}: {what} needs prompt and three options")
    elif r.get("answer") not in (0, 1, 2) or isinstance(r.get("answer"), bool):
        errors.append(f"{at}: answer is the right option's index, 0 to 2")


def _check_learning(h: Home, rows: list[dict], pieces: dict, day: str, errors: list[str]) -> None:
    """Answers, cards and games; `pieces` are this issue's, by id."""
    from . import crossword, reading  # they read issues too
    from .learn import marks

    where = h.issues / f"{day}.jsonl"
    known_marks = marks(h)
    known_pieces = {**all_pieces(h), **pieces}
    known_games = {**all_rows(h, "predict"), **all_rows(h, "link")}
    st = reading.state(h)
    seen = Counter(r.get("id") for r in rows)
    played = Counter(r.get("predict") or r.get("link") for r in rows if kind(r) in ("predict", "link"))
    count = Counter(kind(r) for r in rows)
    for r in rows:
        at, rid, what = f"{where}:{r['_line']}", str(r.get("id")), kind(r)
        if seen[rid] > 1:
            errors.append(f"{at}: {rid} is in the issue twice")
        if what == "answer":
            if not re.match(rf"^a-{day}-\d+$", rid):
                errors.append(f"{at}: needs id, a-{day}-<n>")
            m = known_marks.get(r.get("answer"))
            if not m or m["kind"] != "question":
                errors.append(f"{at}: answer must name a question in marks.jsonl (h-…)")
            text = str(r.get("text") or "")
            if not text:
                errors.append(f"{at}: needs text, the reply")
            elif (n := len(text.split())) > ANSWER_WORDS:
                errors.append(f"{at}: text is {n} words; an answer is {ANSWER_WORDS} at most")
        elif what == "card":
            if not re.match(rf"^c-{day}-\d+$", rid):
                errors.append(f"{at}: needs id, c-{day}-<n>")
            if r.get("from") not in known_pieces and r.get("from") not in known_marks and r.get("from") not in known_games:
                errors.append(f"{at}: from must name the piece (r-…), mark (h-…) or missed game (p-…, l-…) the card comes from")
            if r.get("card") == "flip":
                if not r.get("front") or not r.get("back"):
                    errors.append(f"{at}: a flip card needs front and back")
            elif r.get("card") == "choice":
                _choice(r, at, errors, "a choice card")
            else:
                errors.append(f"{at}: card is flip or choice")
        elif what in ("predict", "link"):
            target = r.get(what)
            if not re.match(rf"^{what[0]}-{day}-\d+$", rid):
                errors.append(f"{at}: needs id, {what[0]}-{day}-<n>")
            if target not in pieces:
                errors.append(f"{at}: {what} must name a piece of this issue (r-{day}-…)")
            elif played[target] > 1:
                errors.append(f"{at}: {target} has two games; one a piece")
            elif what == "link":
                before = known_pieces.get(r.get("from"))
                if not pieces[target].get("thread"):
                    errors.append(f"{at}: a link is on a piece with a thread, whose story follows the answer")
                if not before or before["day"] >= day or not st.get(before["id"], {}).get("opened"):
                    errors.append(f"{at}: from must name the earlier piece of the story, one the reader opened")
            _choice(r, at, errors, f"a {what}")
        elif what == "crossword":
            if rid != f"x-{day}":
                errors.append(f"{at}: needs id, x-{day}")
            if date.fromisoformat(day).weekday() != 6:
                errors.append(f"{at}: the crossword is for Sunday's issue")
            words = r.get("crossword")
            if not isinstance(words, list) or not crossword.MIN_WORDS <= len(words) <= crossword.MAX_WORDS:
                errors.append(f"{at}: crossword is a list of {crossword.MIN_WORDS} to {crossword.MAX_WORDS} entries")
                continue
            week = (date.fromisoformat(day) - timedelta(days=7)).isoformat()
            good = []
            for n, w in enumerate(words, 1):
                w = w if isinstance(w, dict) else {}
                answer, clue, piece = crossword.normal(w.get("answer")), str(w.get("clue") or ""), known_pieces.get(w.get("piece"))
                lo, hi = crossword.LETTERS
                if not crossword.WORD.match(answer) or not lo <= len(answer) <= hi:
                    errors.append(f"{at}: entry {n}: answer is one word of {lo} to {hi} letters, no spaces or digits")
                elif not clue or len(clue) > CLUE_CHARS:
                    errors.append(f"{at}: entry {n}: needs a clue of {CLUE_CHARS} characters at most")
                elif not piece or not week < piece["day"] <= day or not st.get(piece["id"], {}).get("opened"):
                    errors.append(f"{at}: entry {n}: piece must name a piece of the past week the reader opened")
                else:
                    good.append(answer)
            if len(set(good)) < len(good):
                errors.append(f"{at}: an answer is in the crossword twice")
            elif len(good) == len(words) and (n := len(crossword.layout(good)["entries"])) < crossword.MIN_WORDS:
                errors.append(f"{at}: only {n} words cross on a {crossword.SIDE} by {crossword.SIDE} grid; "
                              "use shorter words that share letters")
    if count["card"] > CARDS:
        errors.append(f"{where}: {count['card']} cards; an issue writes {CARDS} at most")
    if count["predict"] > PREDICTS:
        errors.append(f"{where}: {count['predict']} predictions; an issue asks {PREDICTS} at most")
    if count["crossword"] > 1:
        errors.append(f"{where}: one crossword an issue")


def validate(h: Home, day: str) -> list[dict]:
    """The day's pieces, checked. Raises Invalid with every error at once."""
    if not DAY.match(day):
        raise Invalid([f"'{day}' is not a date; write YYYY-MM-DD"])
    date.fromisoformat(day)
    secs = sections(h)
    pieces = load(h, day)
    check(h, secs, pieces, day)
    return pieces


def _facts(text: str) -> set[str]:
    """The numbers and names in a text: what makes an entry news. A name is a capitalised word
    past a sentence's first, compared on its first five letters so that Hungarian endings
    (Péter, Péternek) do not make it new."""
    out = {n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)*", text)}
    for sentence in re.split(r"[.!?:;]\s+", text):
        out |= {w.lower()[:5] for w in re.findall(r"[^\W\d_][\w-]*", sentence)[1:] if w[0].isupper()}
    return out


def restated(h: Home, day: str) -> str | None:
    """Raises Invalid for each entry written since the last issue that says what an earlier entry
    of its story said: they score RESTATES or more and it brings no number or name the earlier
    one lacks. Returns a note when the text encoder is missing and nothing was checked."""
    before = [d for d in days(h) if d < day]
    since = before[-1] if before else ""
    checks = []  # (thread id, entry number, earlier number, text, earlier text)
    for tid, th in threads(h).items():
        entries = [x for x in th.get("entries") or [] if isinstance(x, dict)]
        for i, x in enumerate(entries):
            if str(x.get("day") or "") > since and not x.get("old"):
                checks += [(tid, i, j, str(x.get("text") or ""), str(y.get("text") or "")) for j, y in enumerate(entries[:i])]
    if not checks:
        return None
    texts = sorted({t for c in checks for t in c[3:]})
    try:
        vecs = dict(zip(texts, embed.encode(texts)))
    except embed.Unavailable as e:
        return f"threads not checked for restated entries: {e}"
    errors = [
        f"{h.threads}: {tid}: entry {i + 1} says what entry {j + 1} said (\"{old[:80]}\"); drop it, or write what is new"
        for tid, i, j, new, old in checks
        if float(vecs[new] @ vecs[old]) >= RESTATES and not _facts(new) - _facts(old)
    ]
    if errors:
        raise Invalid(errors)
    return None
