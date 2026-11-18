"""The phone: who may read the paper over Wi-Fi.

The Mac itself is always let in. Any other device needs the key, which it gets once by scanning
the QR code in settings and then keeps as a cookie. A new code makes every paired phone pair
again. Over plain Wi-Fi the key travels unencrypted: pairing keeps out whoever just opens the
address, not someone capturing the network's traffic.
"""

import hmac
import os
import secrets
import socket
import subprocess
import sys
from urllib.parse import urlsplit

from .home import Home

LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
LOCAL_NAMES = {"localhost", "127.0.0.1"}
COOKIE = "paper"


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


def allowed(h: Home, client: str, host_header: str | None, cookie_key: str | None) -> bool:
    return is_mac(client, host_header) or paired(h, cookie_key)


def same_origin(origin: str | None, host_header: str | None) -> bool:
    """A write comes from this page or from no page: another site's script cannot mark, review or
    change settings, which the unattended run would then read."""
    return not origin or urlsplit(origin).netloc.lower() == (host_header or "").lower()


def address(port: int) -> str:
    """How the phone finds this Mac on the home network: its Bonjour name."""
    name = ""
    if sys.platform == "darwin":
        try:
            name = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True,
                                  timeout=2).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            name = ""
    name = name or socket.gethostname().split(".")[0]
    return f"http://{name}.local:{port}"


def pair_url(h: Home, port: int) -> str:
    return f"{address(port)}/pair#{key(h)}"


def qr_svg(text: str) -> str:
    import io

    import segno

    out = io.BytesIO()
    segno.make(text, error="m").save(out, kind="svg", scale=6, border=2, dark="#1d1d1f", light="#ffffff",
                                     xmldecl=False, svgns=True, nl=False)
    return out.getvalue().decode()
