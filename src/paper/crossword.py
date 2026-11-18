"""The Sunday crossword: Claude writes the words and their clues, this lays them on a grid.

The same words always give the same grid. Words that cannot cross into a SIDE by SIDE grid are
left out; the issue check refuses a crossword where fewer than MIN_WORDS fit.
"""

import random
import re

SIDE = 9
MIN_WORDS = 6
MAX_WORDS = 12
LETTERS = (3, SIDE)
TRIES = 300
WORD = re.compile(r"^[^\W\d_]+$")  # letters only, in any alphabet


def normal(word: str) -> str:
    return str(word or "").strip().upper()


def _fits(cells: dict, word: str, r: int, c: int, down: bool) -> int | None:
    """How many letters this placement shares with the grid, or None when it may not go there."""
    dr, dc = (1, 0) if down else (0, 1)
    if cells.get((r - dr, c - dc)) or cells.get((r + dr * len(word), c + dc * len(word))):
        return None  # touches another word end to end
    shared = 0
    for i, ch in enumerate(word):
        at = (r + dr * i, c + dc * i)
        found = cells.get(at)
        if found:
            if found[0] != ch or found[1 if down else 2]:
                return None  # another letter, or a word already runs this way through it
            shared += 1
        else:
            side = ((at[0] + dc, at[1] + dr), (at[0] - dc, at[1] - dr))
            if any(cells.get(s) for s in side):
                return None  # a new letter beside another word
    return shared


def _box(cells) -> tuple[int, int, int, int]:
    rows, cols = [r for r, _ in cells], [c for _, c in cells]
    return min(rows), min(cols), max(rows), max(cols)


def _attempt(words: list[str], order: list[int]) -> dict:
    cells: dict[tuple[int, int], list] = {}  # (row, col) -> [letter, in a down word, in an across word]
    placed = {}

    def put(i, r, c, down):
        dr, dc = (1, 0) if down else (0, 1)
        for k, ch in enumerate(words[i]):
            cell = cells.setdefault((r + dr * k, c + dc * k), [ch, False, False])
            cell[1 if down else 2] = True
        placed[i] = (r, c, down)

    first = order[0]
    put(first, 0, 0, False)
    for i in order[1:]:
        word, best = words[i], None
        for (r0, c0), (ch, _, _) in list(cells.items()):
            for k, wch in enumerate(word):
                if wch != ch:
                    continue
                for down in (True, False):
                    r, c = (r0 - k, c0) if down else (r0, c0 - k)
                    shared = _fits(cells, word, r, c, down)
                    if not shared:
                        continue
                    dr, dc = (1, 0) if down else (0, 1)
                    top, left, bottom, right = _box(list(cells) + [(r, c), (r + dr * (len(word) - 1), c + dc * (len(word) - 1))])
                    if bottom - top >= SIDE or right - left >= SIDE:
                        continue
                    score = (shared, -((bottom - top + 1) * (right - left + 1)))
                    if not best or score > best[0]:
                        best = (score, r, c, down)
        if best:
            put(i, best[1], best[2], best[3])
    return {"cells": cells, "placed": placed}


def layout(words: list[str]) -> dict:
    """{"rows", "cols", "entries": [{"i", "row", "col", "down", "num"}]}: the grid that places the
    most words, then the smallest; `i` is the word's index in `words`."""
    words = [normal(w) for w in words]
    best = None
    by_length = sorted(range(len(words)), key=lambda i: (-len(words[i]), i))
    for seed in range(TRIES):
        order = by_length[:] if seed == 0 else random.Random(seed).sample(by_length, len(by_length))
        got = _attempt(words, order)
        top, left, bottom, right = _box(got["cells"])
        score = (len(got["placed"]), -((bottom - top + 1) * (right - left + 1)))
        if not best or score > best[0]:
            best = (score, got, (top, left, bottom, right))
        if len(got["placed"]) == len(words) and seed >= 40:
            break
    _, got, (top, left, bottom, right) = best
    starts = sorted({(r - top, c - left) for r, c, _ in got["placed"].values()})
    number = {at: n for n, at in enumerate(starts, 1)}
    entries = [{"i": i, "row": r - top, "col": c - left, "down": down, "num": number[(r - top, c - left)]}
               for i, (r, c, down) in sorted(got["placed"].items(), key=lambda x: (x[1][2], x[1][0], x[1][1]))]
    return {"rows": bottom - top + 1, "cols": right - left + 1, "entries": entries}
