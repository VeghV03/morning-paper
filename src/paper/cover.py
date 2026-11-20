"""The day's cover (BR12, BR35, BR37, BR39 to BR41): the wordmark and the date on top, an archive
photo full width, the lead claim under it in the reading serif. On a grim day, no photo: the claim
alone, set large. Claude picks the claim and the photo; this lays them out. No model is called (D107).

Every measure is the approved specimen's (390 px wide) times W / 390, so one layout serves the
phone and the X4. The photo is fitted to its final pixels first, then treated: grey, auto-contrast,
+25% contrast, every third row 10% darker, Gaussian grain (sigma 14, seeded from the date, so a
rerun gives the same bytes); the dark cover dims it to 86%.

Photos come only from records that say CC0 or public domain per picture: the Met (v1.1 search),
Cleveland (`cc0=1`) and the Art Institute (`is_public_domain`). `photo(id)` reads the record again
and refuses anything else, whatever the search said.
"""

import io
from datetime import date
from pathlib import Path

import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

from . import config

HERE = Path(__file__).resolve().parent
MONO = HERE / "fonts"
SERIF = MONO / "PaperSerif-Roman.ttf"  # reader/fonts' woff2 unpacked: not every FreeType reads woff2
YELLOW = "#FFD400"
THEMES = {"light": {"bg": "#fbfbf9", "ink": "#1a1a1a", "grey": "#6f6f6b", "dim": 1.0},
          "dark": {"bg": "#121212", "ink": "#f4f4f1", "grey": "#9a9a95", "dim": 0.86}}
UA = "morning-paper cover"  # generic: the Art Institute asks for a name, never a person's details
HEADERS = {"User-Agent": UA, "AIC-User-Agent": UA}


class Refused(Exception):
    """A photo that is not CC0, a record that is gone, or a museum that did not answer."""


# the photo

def _get(url: str, **params) -> httpx.Response:
    r = httpx.get(url, params=params, headers=HEADERS, timeout=30, follow_redirects=True)
    r.raise_for_status()
    return r


def cma(data: dict) -> list[dict]:
    """Cleveland's search or record answer as candidates, CC0 only."""
    rows = data.get("data")
    rows = rows if isinstance(rows, list) else [rows] if isinstance(rows, dict) else []
    return [{"id": f"cma-{o['id']}", "title": o.get("title") or "", "artist": ((o.get("creators") or [{}])[0] or {}).get("description") or "",
             "date": o.get("creation_date") or "", "source": "Cleveland Museum of Art",
             "image": ((o["images"].get("print") or {}).get("url") or o["images"]["web"]["url"]), "record": o.get("url") or ""}
            for o in rows if o.get("share_license_status") == "CC0" and ((o.get("images") or {}).get("web") or {}).get("url")]


def met(o: dict) -> list[dict]:
    """One Met object record as a candidate, public domain only."""
    if not (o.get("isPublicDomain") and o.get("primaryImageSmall")):
        return []
    return [{"id": f"met-{o['objectID']}", "title": o.get("title") or "", "artist": o.get("artistDisplayName") or "",
             "date": o.get("objectDate") or "", "source": "The Metropolitan Museum of Art",
             "image": o["primaryImageSmall"], "record": o.get("objectURL") or ""}]


def aic(data: dict) -> list[dict]:
    """The Art Institute's search or record answer as candidates, public domain only."""
    rows = data.get("data")
    rows = rows if isinstance(rows, list) else [rows] if isinstance(rows, dict) else []
    return [{"id": f"aic-{o['id']}", "title": o.get("title") or "", "artist": o.get("artist_display") or "",
             "date": o.get("date_display") or "", "source": "Art Institute of Chicago",
             "image": f"https://www.artic.edu/iiif/2/{o['image_id']}/full/843,/0/default.jpg",
             "record": f"https://www.artic.edu/artworks/{o['id']}"}
            for o in rows if o.get("is_public_domain") and o.get("image_id")]


AIC_FIELDS = "id,title,image_id,is_public_domain,artist_display,date_display"


def search(words: str, per: int = 6) -> tuple[list[dict], list[str]]:
    """CC0 candidates from the three museums, and which of them did not answer."""
    out, errors = [], []
    try:
        out += cma(_get("https://openaccess-api.clevelandart.org/api/artworks/", q=words, cc0=1, has_image=1, limit=per).json())
    except (httpx.HTTPError, ValueError, KeyError) as e:
        errors.append(f"Cleveland: {e}")
    try:
        ids = _get("https://collectionapi.metmuseum.org/public/collection/v1.1/search", q=words, hasImages="true",
                   isPublicDomain="true", limit=per * 2).json().get("objectIDs") or []
        got = []
        for i in ids[: per * 2]:  # the search's own filter is loose: each record says for itself
            if len(got) >= per:
                break
            try:
                got += met(_get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{i}").json())
            except httpx.HTTPStatusError:  # the search lists objects whose record is gone
                continue
        out += got
    except (httpx.HTTPError, ValueError, KeyError) as e:
        errors.append(f"the Met: {e}")
    try:
        out += aic(_get("https://api.artic.edu/api/v1/artworks/search", q=words, limit=per, fields=AIC_FIELDS,
                        **{"query[term][is_public_domain]": "true"}).json())
    except (httpx.HTTPError, ValueError, KeyError) as e:
        errors.append(f"the Art Institute: {e}")
    return out, errors


def record(pid: str) -> dict:
    """The candidate for an id, read again from its museum. Raises Refused when it is not CC0."""
    museum, _, n = pid.partition("-")
    if not n.isdigit() or museum not in ("cma", "met", "aic"):
        raise Refused(f"{pid}: not a photo id; take one from `paper cover search`")
    try:
        if museum == "cma":
            found = cma(_get(f"https://openaccess-api.clevelandart.org/api/artworks/{n}").json())
        elif museum == "met":
            found = met(_get(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{n}").json())
        else:
            found = aic(_get(f"https://api.artic.edu/api/v1/artworks/{n}", fields=AIC_FIELDS).json())
    except (httpx.HTTPError, ValueError, KeyError) as e:
        raise Refused(f"{pid}: the museum did not answer ({e})") from None
    if not found:
        raise Refused(f"{pid}: its record does not say CC0 or public domain, or has no image")
    return found[0]


def photo(rec: dict) -> Image.Image:
    try:
        return Image.open(io.BytesIO(_get(rec["image"]).content))
    except (httpx.HTTPError, OSError) as e:
        raise Refused(f"{rec['id']}: the image did not load ({e})") from None


def treat(img: Image.Image, w: int, h: int, day: str, dim: float, crop: tuple[float, ...] | None = None) -> Image.Image:
    """Cut to `crop` (fractions left, top, right, bottom: the picture inside a mount or plate),
    fitted to w by h, then the specimen's treatment."""
    g = ImageOps.exif_transpose(img).convert("L")
    if crop:
        g = g.crop(tuple(round(f * n) for f, n in zip(crop, g.size * 2)))
    g = ImageOps.fit(g, (w, h), Image.LANCZOS)
    g = ImageEnhance.Contrast(ImageOps.autocontrast(g)).enhance(1.25)
    a = np.asarray(g, dtype=np.float32).copy()
    a[2::3] *= 0.9
    a += np.random.default_rng(int(day.replace("-", ""))).normal(0, 14, a.shape)
    return Image.fromarray((np.clip(a, 0, 255) * dim).astype(np.uint8))


# the layout

def stamp(day: str, lang: str) -> str:
    """"Fri 20 Nov", "nov. 20., péntek"."""
    d, t = date.fromisoformat(day), config.LABELS[lang]
    month, weekday = t["months"].split()[d.month - 1], t["days"].split()[d.weekday()]
    return f"{month[:3]}. {d.day}., {weekday}" if lang == "hu" else f"{weekday[:3]} {d.day} {month[:3]}"


def _serif(px: float, opsz: float) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(SERIF), round(px))
    f.set_variation_by_axes([600, max(8, min(60, opsz))])
    return f


def _wrap(text: str, font: ImageFont.FreeTypeFont, width: float) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and font.getlength(lines[-1] + " " + word) <= width:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


def draw(day: str, claim: str, img: Image.Image | None, size: tuple[int, int] = (390, 844),
         theme: str = "light", lang: str = "en", crop: tuple[float, ...] | None = None) -> Image.Image:
    """The cover as an RGB image of exactly `size`. `img` None is a grim day."""
    W, H = size
    s, t = W / 390, THEMES[theme]
    out = Image.new("RGB", size, t["bg"])
    d = ImageDraw.Draw(out)

    # wordmark and date on one baseline: 56 from the top, 24 from the sides, 18 below
    mark, small = ImageFont.truetype(str(MONO / "IBMPlexMono-Medium.ttf"), round(17 * s)), ImageFont.truetype(str(MONO / "IBMPlexMono-Regular.ttf"), round(13 * s))
    asc, desc = mark.getmetrics()
    base, x = 56 * s + asc, 24 * s
    d.text((x, base), "morning_paper", font=mark, fill=t["ink"], anchor="ls")
    x += mark.getlength("morning_paper")
    top = base - asc + (asc + desc - 1.15 * mark.size) / 2  # the cursor: an inline block, line-height 1.15
    d.rectangle((x, top, x + mark.getlength("_") - 1, top + 1.15 * mark.size - 1), fill=YELLOW)
    d.text((x, base), "_", font=mark, fill="#1a1a1a", anchor="ls")
    d.text((W - 24 * s, base), stamp(day, lang), font=small, fill=t["grey"], anchor="rs")
    y0 = base + max(desc, small.getmetrics()[1]) + 18 * s

    room = W - 48 * s
    if img is None:  # grim (BR37): the claim alone, as large as fits, where the photo would start
        for pt in range(60, 29, -2):
            f = _serif(pt * s, pt)
            lines, lh = _wrap(claim, f, room), pt * 1.12 * s
            if len(lines) * lh <= H - y0 - 26 * s - 24 * s and all(f.getlength(ln) <= room for ln in lines):
                break
        _lines(d, lines, f, x=24 * s, y=y0 + 26 * s, lh=lh, ink=t["ink"])
        return out

    # the claim measured first; the photo takes 500 of what is left, less when the claim needs it
    for pt in range(30, 19, -2):
        f = _serif(pt * s, pt)
        lines, lh = _wrap(claim, f, room), pt * 1.2 * s
        ph = min(500 * s, H - y0 - 26 * s - len(lines) * lh - 24 * s)
        if ph >= 0.45 * H:
            break
    ph = round(max(ph, 0.3 * H))
    out.paste(treat(img, W, ph, day, t["dim"], crop), (0, round(y0)))
    _lines(d, lines, f, x=24 * s, y=round(y0) + ph + 26 * s, lh=lh, ink=t["ink"])
    return out


def _lines(d: ImageDraw.ImageDraw, lines: list[str], f: ImageFont.FreeTypeFont, x: float, y: float, lh: float, ink: str) -> None:
    asc, desc = f.getmetrics()
    for n, ln in enumerate(lines):  # each line's baseline as CSS puts it: half the leading above the ascent
        d.text((x, y + n * lh + (lh - asc - desc) / 2 + asc), ln, font=f, fill=ink, anchor="ls")


def png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
