"""The phone: who may read the paper over Wi-Fi.

The Mac itself is always let in. Any other device needs the key, which it gets once and then
keeps as a cookie: by scanning the QR code in settings (Safari), or by typing the six-digit code
shown beside it (the home-screen app on iPhone keeps its own cookies, so it cannot use Safari's).
The six digits change every five minutes; five wrong ones close code pairing until settings is
opened on the Mac again. A new code makes every paired phone pair again. A phone reads the paper
over HTTPS, once it trusts the paper's own certificate (tls.py); plain HTTP from the network only
offers that certificate.
"""

import hashlib
import hmac
import os
import re
import secrets
import time
from urllib.parse import urlsplit

from . import tls
from .home import Home

LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
LOCAL_NAMES = {"localhost", "127.0.0.1"}
COOKIE = "paper"
WINDOW = 300  # seconds a six-digit code lasts; the one before it is still taken
TRIES = 5  # wrong codes before code pairing closes until settings is opened on the Mac
_wrong = {"n": 0}


def _file(h: Home):
    return h.root / ".phone-key"


def key(h: Home) -> str:
    path = _file(h)
    if path.exists():
        found = path.read_text(encoding="utf-8").strip()
        if found:
            return found
    return new_key(h)


def new_key(h: Home) -> str:
    k = secrets.token_urlsafe(32)
    path = _file(h)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(k + "\n")
    os.chmod(path, 0o600)
    return k


def hostname(host_header: str | None) -> str:
    return (urlsplit("//" + (host_header or "")).hostname or "").lower()


def is_mac(client: str, host_header: str | None) -> bool:
    """The Mac's own browser: a loopback connection that also names a local host, so a web page
    whose domain was pointed at 127.0.0.1 (DNS rebinding) is not taken for it."""
    return client in LOOPBACK and hostname(host_header) in LOCAL_NAMES


def paired(h: Home, given: str | None) -> bool:
    return bool(given) and hmac.compare_digest(given.encode(), key(h).encode())


def short_code(h: Home, at: float | None = None) -> str:
    """Six digits from the key and the current five minutes."""
    window = int((time.time() if at is None else at) // WINDOW)
    digest = hmac.new(key(h).encode(), str(window).encode(), hashlib.sha256).digest()
    return str(int.from_bytes(digest[:8], "big") % 1_000_000).zfill(6)


def open_codes() -> None:
    """Settings opened on the Mac: code pairing takes tries again."""
    _wrong["n"] = 0


def code_locked() -> bool:
    return _wrong["n"] >= TRIES


def check_code(h: Home, given: str, at: float | None = None) -> bool:
    """True for the current or the previous code. A wrong one counts toward the lock."""
    if code_locked():
        return False
    given = "".join(c for c in str(given) if c.isdigit())
    now = time.time() if at is None else at
    if any(hmac.compare_digest(given, short_code(h, now - back)) for back in (0, WINDOW)):
        _wrong["n"] = 0
        return True
    _wrong["n"] += 1
    return False


def allowed(h: Home, client: str, host_header: str | None, cookie_key: str | None) -> bool:
    return is_mac(client, host_header) or paired(h, cookie_key)


def same_origin(origin: str | None, host_header: str | None) -> bool:
    """A write comes from this page or from no page: another site's script cannot mark, review or
    change settings, which the unattended run would then read."""
    return not origin or urlsplit(origin).netloc.lower() == (host_header or "").lower()


def address(port: int) -> str:
    """Where a paired phone reads the paper: HTTPS at this computer's Bonjour name."""
    return f"https://{tls.name()}.local:{port}"


def pair_url(h: Home, port: int) -> str:
    """What the code in Settings opens: the plain-HTTP page that installs the certificate, then
    hands the key on to HTTPS in the address's fragment, which is never sent over the network."""
    return f"http://{tls.name()}.local:{port}/start#{key(h)}"


def qr_svg(text: str) -> str:
    import io

    import segno

    out = io.BytesIO()
    segno.make(text, error="m").save(out, kind="svg", scale=6, border=4, dark="#1d1d1f", light="#ffffff",
                                     xmldecl=False, svgns=True, nl=False)
    svg = out.getvalue().decode()
    # sized by the page: a viewBox instead of fixed pixels, so the whole code scales, never crops
    return re.sub(r'width="(\d+)" height="(\d+)"', r'viewBox="0 0 \1 \2"', svg, count=1)
