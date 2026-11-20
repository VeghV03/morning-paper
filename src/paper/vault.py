"""The reader's record, encrypted: reads.jsonl and marks.jsonl.

Each row is one line, `p1:` and the row's JSON sealed with AES-256-GCM. The key comes from a
24-character recovery code kept in the OS keychain (macOS Keychain, Windows Credential Manager,
the Secret Service on Linux); `PAPER_RECOVERY_CODE` overrides it, for tests and for machines
without a keychain. A lost keychain entry is restored with `paper restore <code>`. Plain lines
from before encryption are still read, and `migrate` seals them.
"""

import base64
import json
import os
import secrets
import subprocess
import sys

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .home import Home

PREFIX = "p1:"
SERVICE, ACCOUNT = "morning-paper", "record"
ENV = "PAPER_RECOVERY_CODE"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to misread
LENGTH = 24  # 120 bits
_cache: dict[str, bytes] = {}


class Locked(Exception):
    """The record cannot be read: no key, or a key that is not the one it was sealed with."""


def new_code() -> str:
    return normal("".join(secrets.choice(ALPHABET) for _ in range(LENGTH)))


def normal(code: str) -> str:
    """The code as shown: six groups of four. Raises ValueError for anything that is not a code."""
    raw = "".join(c for c in code.upper() if c.isalnum())
    if len(raw) != LENGTH or any(c not in ALPHABET for c in raw):
        raise ValueError("a recovery code is 24 letters and digits")
    return "-".join(raw[i:i + 4] for i in range(0, LENGTH, 4))


def _derive(code: str) -> bytes:
    return HKDF(hashes.SHA256(), 32, salt=b"morning-paper", info=b"record v1").derive(normal(code).encode())


# --- the keychain -------------------------------------------------------------------------------

def _stored() -> str | None:
    if os.environ.get(ENV):
        return os.environ[ENV]
    if sys.platform == "darwin":
        # through /usr/bin/security, which owns the item: a new Python after an update reads it
        # without a keychain prompt that would stop the unattended morning run
        r = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", ACCOUNT, "-w"],
                           capture_output=True, text=True)
        return r.stdout.strip() or None if r.returncode == 0 else None
    return _keyring("get_password", SERVICE, ACCOUNT)


def _store(code: str) -> None:
    if os.environ.get(ENV):
        os.environ[ENV] = code
    elif sys.platform == "darwin":
        subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICE, "-a", ACCOUNT, "-w", code],
                       check=True, capture_output=True)
    else:
        _keyring("set_password", SERVICE, ACCOUNT, code)
    _cache.clear()


def _keyring(call: str, *args):
    """Windows Credential Manager, or the Secret Service on Linux. A missing or locked one stops
    the record rather than putting the key somewhere weaker."""
    import keyring
    from keyring.errors import KeyringError
    try:
        return getattr(keyring, call)(*args)
    except (KeyringError, RuntimeError, OSError) as e:
        raise Locked(f"no keyring to keep the record's key ({type(e).__name__}): unlock or install one "
                     f"(GNOME Keyring or KWallet on Linux), or set {ENV} to the recovery code") from e


def code() -> str | None:
    found = _stored()
    try:
        return normal(found) if found else None
    except ValueError:
        return None


def _key() -> bytes:
    c = code()
    if not c:
        raise Locked("no key for the record: run `paper restore <recovery code>`")
    if c not in _cache:
        _cache.clear()
        _cache[c] = _derive(c)
    return _cache[c]


# --- rows ---------------------------------------------------------------------------------------

def seal(row: dict, key: bytes | None = None) -> str:
    nonce = secrets.token_bytes(12)
    data = AESGCM(key or _key()).encrypt(nonce, json.dumps(row, ensure_ascii=False).encode(), None)
    return PREFIX + base64.urlsafe_b64encode(nonce + data).decode()


def _open(line: str, key: bytes) -> dict | None:
    try:
        raw = base64.urlsafe_b64decode(line[len(PREFIX):])
        return json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], None))
    except (InvalidTag, ValueError):
        return None


def rows(path) -> list[dict]:
    """Every row of a record file, oldest first. A line cut short by a crash is skipped; a file
    sealed with another key raises Locked rather than reading as empty."""
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    sealed = [ln for ln in lines if ln.startswith(PREFIX)]
    key = _key() if sealed else None
    out, bad = [], 0
    for line in lines:
        if line.startswith(PREFIX):
            row = _open(line, key)
            bad += row is None
        else:
            try:
                row = json.loads(line)
            except ValueError:
                row = None
        if isinstance(row, dict):
            out.append(row)
    if sealed and bad == len(sealed) and len(sealed) > 1:
        raise Locked(f"{path.name} was sealed with another key: run `paper restore <recovery code>`")
    return out


def append(path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = seal(row)
    with path.open("a+b") as f:
        f.seek(0, os.SEEK_END)
        cut = f.tell() > 0 and (f.seek(-1, os.SEEK_END), f.read(1))[1] != b"\n"  # a crash's half line stays apart
        f.write((("\n" if cut else "") + line + "\n").encode())


def record(h: Home) -> list:
    return [h.reads, h.marks]


def ensure(h: Home) -> str | None:
    """A key for the record, made on first use. Returns the recovery code when it was just made,
    so the caller can show it; None when one already existed. Never makes a new key over a
    record sealed with an old one."""
    if code():
        return None
    for path in record(h):
        if path.exists() and any(ln.startswith(PREFIX) for ln in path.read_text(encoding="utf-8").splitlines()):
            raise Locked("the record is sealed and this computer has no key: run `paper restore <recovery code>`")
    c = new_code()
    _store(c)
    unsaved(h, True)
    return c


def migrate(h: Home) -> int:
    """Seals the plain lines left from before encryption; returns how many. Run while nothing
    else writes the record: at `paper init`."""
    n = 0
    for path in record(h):
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        plain = [ln for ln in lines if ln.strip() and not ln.startswith(PREFIX)]
        if not plain:
            continue
        key, out = _key(), []
        for line in lines:
            if line.startswith(PREFIX):
                out.append(line)
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(seal(row, key))
                n += 1
        tmp = path.with_suffix(".tmp")
        tmp.write_text("".join(ln + "\n" for ln in out), encoding="utf-8")
        os.replace(tmp, path)
    return n


def restore(h: Home, given: str) -> None:
    """Keeps `given` as this computer's key, once it opens the record (when there is one)."""
    c = normal(given)
    key = _derive(c)
    for path in record(h):
        if not path.exists():
            continue
        sealed = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith(PREFIX)]
        if sealed and not any(_open(ln, key) for ln in sealed[-20:]):
            raise ValueError("that code does not open this record")
    _store(c)
    unsaved(h, False)


# --- whether the reader has the code yet --------------------------------------------------------

def _flag(h: Home):
    return h.root / ".recovery-unsaved"


def unsaved(h: Home, value: bool | None = None) -> bool:
    """True until the reader says they saved the code shown in Settings on the computer."""
    path = _flag(h)
    if value is True:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    elif value is False:
        path.unlink(missing_ok=True)
    return path.exists()
