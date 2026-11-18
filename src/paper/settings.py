"""The reader's own files as the settings page shows and saves them. Each save checks what it
writes, so a bad edit is refused with its reason and the file stays as it was."""

import json
import re

import yaml

from . import config
from .home import Home
from .issue import MAX_SECTIONS, Invalid, section_id, sections

SECTIONS_HEAD = (
    "# The paper's sections, in page order.\n"
    "# One line each: the name, a colon, what belongs in it; topics after a | steer the section.\n\n"
)
FEEDS_HEAD = "# Feeds you follow. Their best new posts go into the sections they fit.\n"
INBOX_HEAD = "# Saved links, one a line. They arrive in the next issue and leave this file.\n"
NAME_CHARS = 32


def state(h: Home) -> dict:
    try:
        secs = [{"name": s.name, "what": s.what, "topics": ", ".join(s.topics)} for s in sections(h)]
    except Invalid:
        secs = []
    feeds = (yaml.safe_load(h.feeds.read_text(encoding="utf-8")) or {}) if h.feeds.exists() else {}
    outlets = json.loads(h.outlets.read_text(encoding="utf-8")) if h.outlets.exists() else []
    return {
        "sections": secs,
        "interests": h.interests.read_text(encoding="utf-8") if h.interests.exists() else "",
        "feeds": [{"name": f.get("name", ""), "url": f.get("url", "")} for f in feeds.get("feeds") or [] if isinstance(f, dict)],
        "outlets": _newsrooms(outlets),
        "language": config.language(h),
    }


def _newsrooms(outlets: list) -> list[dict]:
    """One entry per newsroom: two feeds of one `org` count once in k, and go together."""
    out: dict[str, dict] = {}
    for o in outlets:
        if isinstance(o, dict) and "id" in o:
            org = o.get("org") or o["id"]
            out.setdefault(org, {"org": org, "ids": []})["ids"].append(o["id"])
    return list(out.values())


def _one_line(value, field: str, limit: int | None = None) -> str:
    text = " ".join(str(value or "").split())
    if limit and len(text) > limit:
        raise Invalid([f"{field} is {len(text)} characters; {limit} at most"])
    return text


def save_sections(h: Home, rows: list) -> None:
    lines, ids, errors = [], set(), []
    for r in rows if isinstance(rows, list) else []:
        name = _one_line(r.get("name"), "a name", NAME_CHARS)
        what = _one_line(r.get("what"), "what belongs")
        topics = [t for t in (_one_line(x, "a topic") for x in str(r.get("topics") or "").split(",")) if t]
        if not name and not what:
            continue
        if not name or ":" in name or "|" in name or not section_id(name):
            errors.append(f"'{name}': a name needs a letter, and no : or |")
            continue
        if section_id(name) in ids:
            errors.append(f"'{name}' is there twice")
        ids.add(section_id(name))
        what = what.replace("|", "/")
        lines.append(f"{name}: {what}" + (f" | {', '.join(t.replace('|', '/') for t in topics)}" if topics else ""))
    if len(lines) > MAX_SECTIONS:
        errors.append(f"{len(lines)} sections; an issue holds {MAX_SECTIONS}")
    if not lines:
        errors.append("the paper needs a section")
    if errors:
        raise Invalid(errors)
    h.sections.write_text(SECTIONS_HEAD + "\n".join(lines) + "\n", encoding="utf-8")


def save_interests(h: Home, text) -> None:
    h.interests.write_text(str(text or "").rstrip() + "\n", encoding="utf-8")


def save_feeds(h: Home, rows: list) -> None:
    config_ = (yaml.safe_load(h.feeds.read_text(encoding="utf-8")) or {}) if h.feeds.exists() else {}
    feeds, errors = [], []
    for r in rows if isinstance(rows, list) else []:
        name, url = _one_line(r.get("name"), "a name"), _one_line(r.get("url"), "an address")
        if not name and not url:
            continue
        if not re.match(r"^https?://\S+$", url):
            errors.append(f"'{url}' is not a web address")
            continue
        feeds.append({"name": name or url, "url": url})
    if errors:
        raise Invalid(errors)
    config_["feeds"] = feeds
    body = yaml.safe_dump(config_, allow_unicode=True, sort_keys=False, default_flow_style=None)
    h.feeds.write_text(FEEDS_HEAD + body, encoding="utf-8")


def save_outlets(h: Home, keep: list) -> None:
    """Keeps the outlets whose ids are in `keep`; outlets are added by Claude, which tests them."""
    outlets = json.loads(h.outlets.read_text(encoding="utf-8")) if h.outlets.exists() else []
    wanted = {str(x) for x in keep} if isinstance(keep, list) else set()
    left = [o for o in outlets if isinstance(o, dict) and o.get("id") in wanted]
    if not left:
        raise Invalid(["the paper needs an outlet"])
    h.outlets.write_text(json.dumps(left, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def save_language(h: Home, lang) -> None:
    if lang not in config.LABELS:
        raise Invalid([f"the page speaks {' or '.join(config.LABELS)}"])
    text = h.config.read_text(encoding="utf-8") if h.config.exists() else ""
    if re.search(r"(?m)^language:.*$", text):
        text = re.sub(r"(?m)^language:.*$", f"language: {lang}", text)
    else:
        text = text.rstrip("\n") + ("\n" if text else "") + f"language: {lang}\n"
    h.config.write_text(text, encoding="utf-8")


def save_link(h: Home, url) -> None:
    url = _one_line(url, "a link")
    if not re.match(r"^https?://\S+$", url):
        raise Invalid([f"'{url}' is not a web address"])
    text = h.inbox.read_text(encoding="utf-8") if h.inbox.exists() else INBOX_HEAD
    h.inbox.write_text(text.rstrip("\n") + "\n" + url + "\n", encoding="utf-8")


SAVE = {"sections": save_sections, "interests": save_interests, "feeds": save_feeds,
        "outlets": save_outlets, "language": save_language, "link": save_link}
