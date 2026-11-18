"""The reader's folder, PAPER_HOME (default ~/paper): their own files, the issues, the reading log."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Home:
    root: Path

    @property
    def sections(self) -> Path:
        return self.root / "sections.md"

    @property
    def feeds(self) -> Path:
        return self.root / "feeds.yaml"

    @property
    def interests(self) -> Path:
        return self.root / "interests.md"

    @property
    def inbox(self) -> Path:
        return self.root / "inbox.md"

    @property
    def outlets(self) -> Path:
        """The outlets the engine reads and ranks by, a JSON array (presets/ has two)."""
        return self.root / "outlets.json"

    @property
    def config(self) -> Path:
        """language (the page's labels) and morning (the run's time)."""
        return self.root / "paper.yaml"

    @property
    def digests(self) -> Path:
        """Digests Claude writes, one `<id>.md` a piece."""
        return self.root / "digests"

    @property
    def issues(self) -> Path:
        return self.root / "issues"

    @property
    def threads(self) -> Path:
        return self.root / "threads.jsonl"

    @property
    def reads(self) -> Path:
        """What the reader did, one event a line, written by the server alone."""
        return self.root / "reads.jsonl"

    @property
    def marks(self) -> Path:
        """The reader's highlights and questions (learn.py)."""
        return self.root / "marks.jsonl"

    @property
    def cache(self) -> Path:
        """Article text the reader view extracted, one file a piece."""
        return self.root / "cache"

    @property
    def feed_state(self) -> Path:
        return self.root / ".feed.json"


def home() -> Home:
    return Home(Path(os.environ.get("PAPER_HOME") or Path.home() / "paper").expanduser())


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    """Write atomically, so a crash never leaves half a state file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def pending(path: Path) -> Path:
    """Where the cursor `feed` moved waits for `publish`, which commits it. A run that stops
    before publishing leaves the cursor as it was, so the same news comes back next time."""
    return path.with_name(path.name + ".pending")


def commit_pending(path: Path) -> None:
    if pending(path).exists():
        pending(path).replace(path)
