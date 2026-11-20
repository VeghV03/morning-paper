"""Text as vectors, from a local encoder on the CPU (D100): multilingual-e5-base, which turns a
headline or a sentence into 768 numbers so that two texts saying the same thing, in any of its
languages, land close together. It writes nothing, and nothing leaves the machine.

`paper model` downloads it once, pinned to one revision and checked against its hashes, into
$PAPER_MODELS (default ~/.cache/paper/models); the cloud run's `start` calls it (D103). Without
it every caller falls back and says so: `encode` raises Unavailable, it never downloads.
"""

import hashlib
import os
from pathlib import Path

import httpx
import numpy as np

REPO = "intfloat/multilingual-e5-base"
REVISION = "d128750597153bb5987e10b1c3493a34e5a4502a"
FILES = {  # path in the repository -> sha256, from Hugging Face's file list on 2026-11-20
    "onnx/model.onnx": "84a4d426f7e87a6bf5bf195f0bae2c4a7d15f675b23ca96f42fab8326d7a77aa",
    "onnx/tokenizer.json": "62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626",
}
MAX_TOKENS = 128  # a headline or a thread entry fits; longer text is cut
BATCH = 64


class Unavailable(Exception):
    """The model is not on this machine, or does not load."""


def folder() -> Path:
    return Path(os.environ.get("PAPER_MODELS") or Path.home() / ".cache" / "paper" / "models").expanduser() / REPO.replace("/", "--")


def fetch() -> Path:
    """Download what is missing, check each file's hash, and return the folder."""
    d = folder()
    for name, sha in FILES.items():
        dest = d / name
        if dest.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        digest = hashlib.sha256()
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}"
        with httpx.stream("GET", url, follow_redirects=True, timeout=60.0) as r, part.open("wb") as f:
            r.raise_for_status()
            for chunk in r.iter_bytes(1 << 20):
                digest.update(chunk)
                f.write(chunk)
        if digest.hexdigest() != sha:
            part.unlink()
            raise Unavailable(f"{name} from {url} does not match its pinned hash; nothing kept")
        part.replace(dest)
    return d


_loaded = None


def _load():
    global _loaded
    if _loaded is None:
        d = folder()
        if not all((d / name).exists() for name in FILES):
            raise Unavailable("the text encoder is not downloaded; run `paper model`")
        try:
            import onnxruntime
            from tokenizers import Tokenizer

            tok = Tokenizer.from_file(str(d / "onnx/tokenizer.json"))
            tok.enable_truncation(MAX_TOKENS)
            tok.enable_padding(pad_id=tok.token_to_id("<pad>"), pad_token="<pad>")
            session = onnxruntime.InferenceSession(str(d / "onnx/model.onnx"), providers=["CPUExecutionProvider"])
        except Exception as e:  # noqa: BLE001 - a broken install falls back like a missing model
            raise Unavailable(f"the text encoder does not load ({e})") from None
        _loaded = (tok, session)
    return _loaded


def encode(texts: list[str]) -> np.ndarray:
    """One unit-length row per text; the dot product of two rows is their cosine similarity."""
    tok, session = _load()
    out = []
    for i in range(0, len(texts), BATCH):
        enc = tok.encode_batch(["query: " + t for t in texts[i : i + BATCH]])  # e5 compares texts as queries
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        hidden = session.run(None, {"input_ids": ids, "attention_mask": mask})[0]
        v = (hidden * mask[..., None]).sum(1) / mask.sum(1, keepdims=True)
        out.append(v / np.linalg.norm(v, axis=1, keepdims=True))
    return np.concatenate(out).astype(np.float32) if out else np.zeros((0, 768), np.float32)
