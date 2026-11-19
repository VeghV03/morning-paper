"""The topic model behind the steered sections (D25 to D30).

For each topic of a steered section, a Beta estimate of how often its pieces turn out well for
the reader. A piece whose headline was on screen is a trial: finished, kept or marked is a
success, opened and left a quarter of one, not opened a miss. "Less of this" adds LESS misses; a
card from the piece remembered later adds RECALL of a success. Evidence fades with a HALF_LIFE.

Each morning `draw` samples every estimate (Thompson sampling) into an order of topics, and names
the topic with the least evidence as the section's try. The record is read as it stood at the
start of the issue's day, so the draw and the why line on the page always see the same evidence.
"""

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time

from . import learn, reading
from .home import Home
from .issue import Invalid, all_pieces, sections

HALF_LIFE = 30  # days (D26)
OPENED = 0.25  # an open that went no further (D25)
LESS = 3  # misses one "less of this" counts as (D29)
RECALL = 0.5  # a card from the piece remembered later, once per piece (D25)
LAST = 5  # showings the why line counts back over


@dataclass
class Topic:
    trials: list = field(default_factory=list)  # (when, success, miss)
    showings: list = field(default_factory=list)  # oldest first: "finished", "kept", "opened" or "passed"
    less: list = field(default_factory=list)  # when "less of this" was pressed and not taken back


def start_of(day: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), time()).astimezone()


def _at(e: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(str(e.get("t"))).astimezone()
    except ValueError:
        return None


def pressed(evs: list[dict]) -> dict[str, datetime]:
    """Per piece, when "less of this" was pressed, for presses not taken back."""
    out: dict[str, datetime] = {}
    for e in evs:
        if e.get("ev") == "less" and e["id"] not in out:
            out[e["id"]] = _at(e)
        elif e.get("ev") == "less_undo":
            out.pop(e["id"], None)
    return {k: v for k, v in out.items() if v}


def evidence(h: Home, before: datetime) -> dict[str, dict[str, Topic]]:
    """Per steered section and topic, what the record held before `before`."""
    evs = [e for e in reading.events(h) if (at := _at(e)) and at < before]
    st = reading.state(h, evs)
    first_look: dict[str, datetime] = {}
    for e in evs:
        if e.get("ev") in ("look", "open", "read"):
            first_look.setdefault(e["id"], _at(e))
    marked = {m["piece"] for m in learn.marks(h).values() if (at := _at(m)) and at < before}
    recalled: dict[str, datetime] = {}
    cards = learn.card_pieces(h)
    for e in evs:
        if e.get("ev") == "review" and e.get("rating") == "good" and e["id"] in cards:
            recalled.setdefault(cards[e["id"]], _at(e))
    less = pressed(evs)
    try:
        steered = {s.id: s.topics for s in sections(h) if s.topics}
    except Invalid:
        steered = {}
    out = {sid: {t: Topic() for t in ts} for sid, ts in steered.items()}
    for p in sorted(all_pieces(h).values(), key=lambda p: (p["day"], p["id"])):
        topic = out.get(p.get("section"), {}).get(p.get("topic"))
        s = st.get(p["id"])
        if topic is None or not s or not s["looked"]:
            continue
        finished = reading.finished(h, p["id"], s)
        kept = reading.kept(p, s) or p["id"] in marked
        success = 1.0 if finished or kept else OPENED if s["opened"] else 0.0
        when = first_look.get(p["id"]) or start_of(p["day"])
        topic.trials.append((when, success, 1.0 - success))
        topic.showings.append("finished" if finished else "kept" if kept else "opened" if s["opened"] else "passed")
        if p["id"] in recalled:
            topic.trials.append((recalled[p["id"]], RECALL, 0.0))
        if p["id"] in less:
            topic.trials.append((less[p["id"]], 0.0, float(LESS)))
            topic.less.append(less[p["id"]])
    return out


def estimate(topic: Topic, now: datetime) -> tuple[float, float]:
    """The Beta(a, b) behind a topic: a flat prior and its faded evidence."""
    a = b = 1.0
    for when, success, miss in topic.trials:
        w = 0.5 ** (max(0.0, (now - when).total_seconds()) / 86400 / HALF_LIFE)
        a += w * success
        b += w * miss
    return a, b


def draw(h: Home, day: str) -> dict[str, dict]:
    """Per steered section, the morning's topic order and its try, with each topic's estimate
    (the share of its pieces expected to turn out well) and how much faded evidence it rests on.
    The same day gives the same draw, so the morning run can ask again."""
    now = start_of(day)
    out = {}
    for sid, topics in evidence(h, now).items():
        rng = random.Random(int.from_bytes(hashlib.sha256(f"{day}|{sid}".encode()).digest()[:8], "big"))
        est = {t: estimate(x, now) for t, x in topics.items()}
        sample = {t: rng.betavariate(a, b) for t, (a, b) in est.items()}
        order = sorted(topics, key=lambda t: -sample[t])
        out[sid] = {
            "order": order,
            "try": min(order, key=lambda t: sum(est[t])),  # the least evidence; the first of equals in the order
            "topics": {t: {"estimate": round(a / (a + b), 2), "evidence": round(a + b - 2, 1)} for t, (a, b) in est.items()},
        }
    return out


def why(h: Home, piece: dict, labels: dict) -> str | None:
    """The why line of a steered piece, from the record as it stood on the issue's morning."""
    topic = evidence(h, start_of(piece["day"])).get(piece.get("section"), {}).get(piece.get("topic"))
    if topic is None:
        return None
    name, last = piece["topic"], topic.showings[-LAST:]
    n = len(last)
    if not n:
        return labels["why_new"].format(topic=name)
    if piece.get("fit") == "tries" and topic.less:
        return labels["why_less"].format(topic=name, date=topic.less[-1].strftime("%Y-%m-%d"))
    for outcome, key in (("finished", "why_finished"), ("kept", "why_kept"), ("opened", "why_opened")):
        k = sum(1 for x in last if x == outcome or (outcome == "opened" and x != "passed"))
        if k:
            return labels[key + ("_one" if n == 1 else "")].format(topic=name, k=k, n=n)
    return labels["why_passed" + ("_one" if n == 1 else "")].format(topic=name, n=n)
