"""One story once, in whatever language it was told (D101, D102).

The engine groups headlines that share title words, which is precise inside one language and
blind across them. Here its groups are the building blocks, and the text encoder merges them by
two strict rules:
- near-identical groups, in any language: every pair of their headlines' centres scores SAME;
- a group and one in another language that are each other's closest match there, at ACROSS.
A wrong merge pushes a non-story up the ranking by `k`; a missed one is what Claude saw before,
so both thresholds favour precision. Measured on the snapshots of 2026-11-17 (decision log).
"""

from collections import Counter

import numpy as np

from . import embed

SAME = 0.91
ACROSS = 0.84
MAX_TITLES = 6000  # ponytail: one similarity matrix in memory; a 14-day catch-up embeds the strongest first


def _lang(story: dict) -> str:
    return Counter(s.get("lang", "en") for s in story["sources"]).most_common(1)[0][0]


def _merge(stories: list[dict]) -> dict:
    """Merged stories keep the strongest member's claim and day order, every source once."""
    first = stories[0]
    sources, primary, seen = [], [], set()
    for s in stories:
        for x in s["sources"]:
            if x["url"] not in seen:
                seen.add(x["url"])
                sources.append(x)
        primary += [p for p in s.get("primary") or [] if p not in primary]
    return {**first, "day": max(s["day"] for s in stories), "score": max(s["score"] for s in stories),
            "sources": sources, "primary": primary}  # fmt: skip


def merge(stories: list[dict], k) -> tuple[list[dict], list[str]]:
    """The stories with the same story merged; `k(sources)` ranks them. Without the encoder
    they come back as they were, with a warning."""
    order = sorted(range(len(stories)), key=lambda i: (-k(stories[i]["sources"]), -stories[i]["score"]))
    titles: dict[str, int] = {}
    units: list[int] = []
    capped = False
    for i in order:
        new = {s["title"] for s in stories[i]["sources"] if s["title"]} - titles.keys()
        if len(titles) + len(new) > MAX_TITLES:
            capped = True
            break
        for t in sorted(new):
            titles[t] = len(titles)
        if any(s["title"] for s in stories[i]["sources"]):
            units.append(i)
    if not units:
        return stories, []
    try:
        vecs = embed.encode(list(titles))
    except embed.Unavailable as e:
        return stories, [f"news: stories not merged across languages: {e}"]
    warnings = [f"news: the weakest stories not merged: over {MAX_TITLES} headlines"] if capped else []

    def centre(rows):
        v = vecs[rows].mean(0)
        return v / np.linalg.norm(v)

    U = np.array([centre([titles[s["title"]] for s in stories[i]["sources"] if s["title"]]) for i in units])
    S = U @ U.T
    group = list(range(len(units)))  # unit -> its group's first unit
    members = {g: [g] for g in group}

    def join(a, b):
        for m in members[b]:
            group[m] = a
        members[a] += members.pop(b)

    # near-identical: complete linkage, strongest pairs first
    a_, b_ = np.nonzero(np.triu(S >= SAME, 1))
    for a, b in sorted(zip(a_, b_), key=lambda p: -S[p]):
        ga, gb = group[a], group[b]
        if ga != gb and S[np.ix_(members[ga], members[gb])].min() >= SAME:
            join(ga, gb)

    # across languages: mutual closest match between groups
    gs = list(members)
    G = np.array([centre([titles[s["title"]] for u in members[g] for s in stories[units[u]]["sources"] if s["title"]]) for g in gs])
    lang = np.array([Counter(_lang(stories[units[u]]) for u in members[g]).most_common(1)[0][0] for g in gs])
    T = G @ G.T
    T[lang[:, None] == lang[None, :]] = -1
    best = T.argmax(1)
    for x, y in enumerate(best):
        if x < y and best[y] == x and T[x, y] >= ACROSS:
            join(gs[x], gs[y])

    out = [_merge([stories[units[u]] for u in sorted(m)]) for m in members.values()]  # units are in rank order
    rest = set(order) - set(units)
    return out + [stories[i] for i in sorted(rest)], warnings
