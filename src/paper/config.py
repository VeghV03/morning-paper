"""$PAPER_HOME/paper.yaml: the page's language and the morning run's time. Both optional."""

from datetime import date

import yaml

from .home import Home

LABELS = {
    "en": {
        "saved": "Saved", "kept": "Kept", "keep": "Keep", "keeping": "Kept", "original": "Original",
        "empty": "Nothing to read today.", "nothing_kept": "Nothing yet.",
        "no_issue": "No issue yet. Run /paper in Claude Code.", "digest": "Digest of",
        "months": "January February March April May June July August September October November December",
        "days": "Monday Tuesday Wednesday Thursday Friday Saturday Sunday",
        "answers": "Answers", "done": "That's the issue.", "settings": "Settings", "next": "Next",
        "highlight": "Highlight", "question": "Question", "remove": "Remove",
        "show": "Show", "again": "Again", "good": "Got it",
        "sections": "Sections", "interests": "Interests", "feeds": "Feeds", "outlets": "Outlets",
        "language": "Language", "save_link": "Save a link", "add": "Add", "name": "Name", "what": "What belongs",
        "topics": "Topics", "url": "Address",
    },
    "hu": {
        "saved": "Mentett", "kept": "Megtartott", "keep": "Megtartom", "keeping": "Megtartva", "original": "Eredeti",
        "empty": "Ma nincs mit olvasni.", "nothing_kept": "Még semmi.",
        "no_issue": "Még nincs szám. Futtasd a /paper-t a Claude Code-ban.", "digest": "Összefoglaló:",
        "months": "január február március április május június július augusztus szeptember október november december",
        "days": "hétfő kedd szerda csütörtök péntek szombat vasárnap",
        "answers": "Válaszok", "done": "Ennyi volt a mai szám.", "settings": "Beállítások", "next": "Következő",
        "highlight": "Kiemelés", "question": "Kérdés", "remove": "Törlés",
        "show": "Mutasd", "again": "Újra", "good": "Megvan",
        "sections": "Rovatok", "interests": "Érdeklődés", "feeds": "Hírcsatornák", "outlets": "Lapok",
        "language": "Nyelv", "save_link": "Link mentése", "add": "Hozzáadás", "name": "Név", "what": "Mi kerül bele",
        "topics": "Témák", "url": "Cím",
    },
}


def load(h: Home) -> dict:
    try:
        data = yaml.safe_load(h.config.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        data = {}
    return data if isinstance(data, dict) else {}


def language(h: Home) -> str:
    lang = str(load(h).get("language") or "en")
    return lang if lang in LABELS else "en"


def labels(h: Home) -> dict:
    return LABELS[language(h)]


def dateline(h: Home, day: str) -> str:
    d, lang = date.fromisoformat(day), language(h)
    month, weekday = LABELS[lang]["months"].split()[d.month - 1], LABELS[lang]["days"].split()[d.weekday()]
    if lang == "hu":
        return f"{d.year}. {month} {d.day}., {weekday}"
    return f"{weekday} {d.day} {month} {d.year}"
