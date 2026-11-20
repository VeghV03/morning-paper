"""The paper's files in the reader's private data repository, sealed (D45 to D55).

The morning run works in the cloud. It opens the data repository into a plain working folder
(`unpack`), writes the issue there as on a computer, and seals what changed back (`pack`). Every
file is sealed whole with AES-256-GCM under the run key, its path bound in so that files cannot
be swapped. The run key comes from the recovery code; the run holds only the run key (in
PAPER_RUN_KEY), never the code, so it cannot derive the record key, which opens the reading
record on the reader's devices alone.

Two areas: `home/` (the reader's files, issues, digests, threads, the feed's state) and
`engine/` (the news engine's own record, without the raw daily snapshots, which the next run
does not read and which would grow the repository by megabytes a day, nor the gazette's PDFs).
"""

import base64
import os
import secrets
from pathlib import Path, PurePath

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from . import vault
from .home import Home

ENV = "PAPER_RUN_KEY"
MAGIC = b"pf1"
SUFFIX = ".sealed"
# the reader's record and what lives only through one run, or only on a computer, stays out
HOME_SKIP = {"reads.jsonl", "marks.jsonl", "context.json", "candidates.json", ".serve.pid", ".fsrs.json",
             ".recovery-unsaved", ".feed.json.pending"}  # a cursor publish never committed
HOME_SKIP_DIRS = {".tls", "cache", ".tools"}


class Locked(Exception):
    """No run key, or a data repository sealed with another one."""


def run_key(code: str) -> bytes:
    return HKDF(hashes.SHA256(), 32, salt=b"morning-paper", info=b"run v1").derive(vault.normal(code).encode())


def encoded(key: bytes) -> str:
    return base64.urlsafe_b64encode(key).decode()


def key_from_env() -> bytes:
    raw = os.environ.get(ENV, "")
    try:
        key = base64.urlsafe_b64decode(raw)
    except ValueError:
        key = b""
    if len(key) != 32:
        raise Locked(f"no run key: set {ENV} in the cloud environment (setup prints it)")
    return key


def active() -> bool:
    """Whether this is the cloud run, which has the run key and no reading record."""
    return bool(os.environ.get(ENV))


def seal(key: bytes, rel: str, data: bytes) -> bytes:
    nonce = secrets.token_bytes(12)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, data, rel.encode())


def open_(key: bytes, rel: str, blob: bytes) -> bytes:
    if not blob.startswith(MAGIC):
        raise Locked(f"{rel}: not a sealed file")
    try:
        return AESGCM(key).decrypt(blob[3:15], blob[15:], rel.encode())
    except InvalidTag:
        raise Locked(f"{rel}: sealed with another key, or changed") from None


def _home_skip(rel: PurePath) -> bool:
    return rel.parts[0] in HOME_SKIP_DIRS or rel.name in HOME_SKIP or rel.suffix == ".tmp"


def _engine_skip(rel: PurePath) -> bool:
    return ((rel.parts[0] == "feed-snapshots" and len(rel.parts) > 1 and rel.parts[1][:2] == "20")  # a day's raw snapshots: read once, the same morning
            or rel.parts[0] in ("discovery", "genealogy")  # made again from the snapshots
            or rel.suffix == ".pdf")  # the gazette's raw bytes: its text stays, and acts.jsonl keeps acts from repeating


def _files(skip):
    def files(root: Path):
        for p in sorted(root.rglob("*")):
            if p.is_file() and not skip(rel := p.relative_to(root)):
                yield rel.as_posix(), p
    return files


_home_files, _engine_files = _files(_home_skip), _files(_engine_skip)


def _areas(h: Home, engine_out: Path):
    return {"home": (h.root, _home_files, _home_skip), "engine": (engine_out, _engine_files, _engine_skip)}


def pack(h: Home, engine_out: Path, repo: Path, key: bytes, prune: bool = False) -> dict:
    """Seals the working folders into the repository. A file whose content did not change keeps
    its sealed bytes, so git sees only what changed. Returns the paths written and removed.

    A file gone from the folder goes from the repository only with `prune`, which the morning run
    passes (old texts, saved links folded in): any other pack is from a folder that may be behind
    the repository, a computer's setup run again, and would delete what the run and the phone wrote
    (D115). A file this key cannot open is never sealed over: it is another code's paper (D115)."""
    plan, removed = [], []
    for area, (root, files, skip) in _areas(h, engine_out).items():
        keep = set()
        for rel, p in (files(root) if root.exists() else ()):
            name = f"{area}/{rel}"
            target = repo / (name + SUFFIX)
            keep.add(target)
            data = p.read_bytes()
            if target.exists() and open_(key, name, target.read_bytes()) == data:  # Locked: another code's
                continue
            plan.append((name, target, data))
        base = repo / area
        for t in sorted(base.rglob("*" + SUFFIX)) if base.exists() else ():
            # a file pack never carries (an old version's .pdf) is not the reader's: it waits for the run's prune
            if t not in keep and (prune or not skip(PurePath(t.relative_to(base).as_posix()[: -len(SUFFIX)]))):
                removed.append(t)
    gone = [t.relative_to(repo).as_posix()[: -len(SUFFIX)] for t in removed]
    if gone and not prune:
        raise Locked(f"the repository has files this folder lacks ({', '.join(gone[:5])}"
                     f"{', …' if len(gone) > 5 else ''}): open it first with `paper cloud unpack`")
    for name, target, data in plan:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(seal(key, name, data))
    for t in removed:
        t.unlink()
    return {"written": [n for n, _, _ in plan], "removed": gone}


def unpack(h: Home, engine_out: Path, repo: Path, key: bytes) -> list[str]:
    """Opens every sealed file of the repository into the working folders. A file that does not
    open stops it all: a run on half the reader's files would write a wrong issue."""
    out = []
    areas = _areas(h, engine_out)
    for target in sorted(repo.rglob("*" + SUFFIX)):
        name = target.relative_to(repo).as_posix()[: -len(SUFFIX)]
        area, _, rel = name.partition("/")
        if area not in areas or not rel or ".." in Path(rel).parts:
            continue
        data = open_(key, name, target.read_bytes())
        dest = areas[area][0] / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        out.append(name)
    return out
