"""$PAPER_HOME/paper.yaml: the page's language and the morning run's time. Both optional."""

from datetime import date

import yaml

from .home import Home

LABELS = {
    "en": {
        "saved": "Saved", "kept": "Kept", "keep": "Keep", "keeping": "Kept", "original": "Original",
        "empty": "Nothing to read today.", "nothing_kept": "Nothing yet.",
        "no_issue": "No issue yet. Run /paper:today in Claude Code.", "digest": "Digest of",
        "months": "January February March April May June July August September October November December",
        "days": "Monday Tuesday Wednesday Thursday Friday Saturday Sunday",
        "answers": "Answers", "done": "That's the issue.", "settings": "Settings", "next": "Next",
        "highlight": "Highlight", "question": "Question", "remove": "Remove",
        "show": "Show", "again": "Again", "good": "Got it",
        "sections": "Sections", "interests": "Interests", "feeds": "Feeds", "outlets": "Outlets",
        "language": "Language", "save_link": "Save a link", "add": "Add", "name": "Name", "what": "What belongs",
        "topics": "Topics", "url": "Address", "phone": "Phone", "new_code": "New code",
        "unpaired": "Enter the code from Settings on your computer.", "pair": "Pair",
        "wrong_code": "That code doesn't match.", "locked": "Too many tries. Open Settings on your computer.",
        "skip": "Skip", "crossword": "Crossword", "across": "Across", "down": "Down", "lede": "Lede", "not_word": "Not in the word list.", "guess": "Guess",
        "since": "Since you left", "earlier": "Earlier", "next_at": "The next one comes at {time}.",
        "recovery": "Recovery code", "recovery_saved": "I've saved it",
        "why_new": "Something new: you haven't read about {topic} here yet.",
        "why_less": "Trying {topic} again, though you asked for less of it on {date}.",
        "why_finished": "You finished {k} of your last {n} pieces on {topic}.",
        "why_finished_one": "You finished your last piece on {topic}.",
        "why_kept": "You kept or marked {k} of your last {n} pieces on {topic}.",
        "why_kept_one": "You kept or marked your last piece on {topic}.",
        "why_opened": "You opened {k} of your last {n} pieces on {topic}.",
        "why_opened_one": "You opened your last piece on {topic}.",
        "why_passed": "Trying {topic} again: you passed your last {n} pieces on it.",
        "why_passed_one": "Trying {topic} again: you passed your last piece on it.",
        "less": "Less of this", "less_done": "Less of {topic} here from now on.", "undo": "Undo",
        "connect": "Connect this phone", "install_cert": "Install the certificate",
        "trust_iphone": "iPhone: Settings › General › VPN & Device Management › install it, then Settings › General › About › Certificate Trust Settings › turn it on.",
        "trust_android": "Android: open the downloaded file, or Settings › Security › Install a certificate › CA certificate.",
        "open_paper": "Open the paper",
    },
    "hu": {
        "saved": "Mentett", "kept": "Megtartott", "keep": "Megtartom", "keeping": "Megtartva", "original": "Eredeti",
        "empty": "Ma nincs mit olvasni.", "nothing_kept": "Még semmi.",
        "no_issue": "Még nincs szám. Futtasd a /paper:today-t a Claude Code-ban.", "digest": "Összefoglaló:",
        "months": "január február március április május június július augusztus szeptember október november december",
        "days": "hétfő kedd szerda csütörtök péntek szombat vasárnap",
        "answers": "Válaszok", "done": "Ennyi volt a mai szám.", "settings": "Beállítások", "next": "Következő",
        "highlight": "Kiemelés", "question": "Kérdés", "remove": "Törlés",
        "show": "Mutasd", "again": "Újra", "good": "Megvan",
        "sections": "Rovatok", "interests": "Érdeklődés", "feeds": "Hírcsatornák", "outlets": "Lapok",
        "language": "Nyelv", "save_link": "Link mentése", "add": "Hozzáadás", "name": "Név", "what": "Mi kerül bele",
        "topics": "Témák", "url": "Cím", "phone": "Telefon", "new_code": "Új kód",
        "unpaired": "Írd be a kódot a számítógéped Beállításaiból.", "pair": "Párosítás",
        "wrong_code": "Ez a kód nem egyezik.", "locked": "Túl sok próbálkozás. Nyisd meg a Beállításokat a számítógépeden.",
        "skip": "Kihagyom", "crossword": "Keresztrejtvény", "across": "Vízszintes", "down": "Függőleges", "guess": "Tipp",
        "since": "Ahol abbahagytad", "earlier": "Korábban", "next_at": "A következő szám {time}-kor jön.",
        "recovery": "Helyreállító kód", "recovery_saved": "Elmentettem",
        "why_new": "Valami új: {topic} témában itt még nem olvastál semmit.",
        "why_less": "Újra megpróbáljuk: {topic}, bár kevesebbet kértél belőle ({date}).",
        "why_finished": "{topic}: a legutóbbi {n} cikkből {k} cikket végigolvastál.",
        "why_finished_one": "{topic}: a legutóbbi cikket végigolvastad.",
        "why_kept": "{topic}: a legutóbbi {n} cikkből {k} cikket megtartottál vagy megjelöltél.",
        "why_kept_one": "{topic}: a legutóbbi cikket megtartottad vagy megjelölted.",
        "why_opened": "{topic}: a legutóbbi {n} cikkből {k} cikket megnyitottál.",
        "why_opened_one": "{topic}: a legutóbbi cikket megnyitottad.",
        "why_passed": "Újra megpróbáljuk: {topic}. A legutóbbi {n} cikket nem nyitottad meg.",
        "why_passed_one": "Újra megpróbáljuk: {topic}. A legutóbbi cikket nem nyitottad meg.",
        "less": "Kevesebbet ebből", "less_done": "Mostantól kevesebb ebből: {topic}.", "undo": "Visszavonás",
        "connect": "A telefon csatlakoztatása", "install_cert": "A tanúsítvány telepítése",
        "trust_iphone": "iPhone: Beállítások › Általános › VPN és eszközkezelés › telepítsd, majd Beállítások › Általános › Névjegy › Tanúsítványmegbízhatósági beállítások › kapcsold be.",
        "trust_android": "Android: nyisd meg a letöltött fájlt, vagy Beállítások › Biztonság › Tanúsítvány telepítése › CA-tanúsítvány.",
        "open_paper": "Az újság megnyitása",
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


def morning(h: Home) -> str:
    """The morning run's time as the page writes it: "5:07"."""
    hh, _, mm = str(load(h).get("morning") or "05:07").partition(":")
    return f"{int(hh)}:{mm[:2]}" if hh.isdigit() and mm[:2].isdigit() else "5:07"


def dateline(h: Home, day: str) -> str:
    d, lang = date.fromisoformat(day), language(h)
    month, weekday = LABELS[lang]["months"].split()[d.month - 1], LABELS[lang]["days"].split()[d.weekday()]
    if lang == "hu":
        return f"{d.year}. {month} {d.day}., {weekday}"
    return f"{weekday} {d.day} {month} {d.year}"


def short_date(h: Home, day: str) -> str:
    """The day and month, for links: the page's own heading carries the full date."""
    d, lang = date.fromisoformat(day), language(h)
    month = LABELS[lang]["months"].split()[d.month - 1]
    return f"{month} {d.day}." if lang == "hu" else f"{d.day} {month}"
