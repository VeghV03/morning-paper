"""Step 4 (D100 to D105): merging one story across languages, and refusing a restated thread
entry. A stand-in encoder gives each text a chosen vector, so the thresholds are what is tested."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from paper import embed, feed, group, issue
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")


def unit(cos: float, axis: int) -> np.ndarray:
    """A vector at `cos` from axis 0, leaning towards `axis`."""
    v = np.zeros(16, np.float32)
    v[0], v[axis] = cos, np.sqrt(1 - cos**2)
    return v


def encoder(vectors: dict[str, np.ndarray]):
    return lambda texts: np.array([vectors[t] for t in texts])


def story(title, org, lang, score=0, url=None):
    return {"day": "2026-11-17", "claim": title, "score": score, "primary": [],
            "sources": [{"org": org, "url": url or f"https://{org}/{title}", "lang": lang, "title": title}]}  # fmt: skip


class MergeTest(unittest.TestCase):
    def merged(self, stories, vectors):
        """How many sources each resulting story has, smallest first."""
        with mock.patch.object(embed, "encode", encoder(vectors)):
            out, _ = group.merge(stories, feed._k)
        return sorted(len(s["sources"]) for s in out)

    def test_one_story_in_two_languages(self):
        # Hungarian and English of one story at 0.86, each other's closest: one story with k 2.
        # A second English story is closer to neither.
        hu, en, other = story("hu", "telex", "hu"), story("en", "bbc", "en"), story("other", "ft", "en")
        self.assertEqual(self.merged([hu, en, other], {"hu": unit(1, 1), "en": unit(0.86, 2), "other": unit(0.5, 3)}), [1, 2])

    def test_across_languages_needs_the_closest_match_both_ways(self):
        # Both Hungarian stories score over ACROSS with the English one (0.90 and 0.89), but the
        # English one is closest to hu1, so hu2 stays apart.
        hu2 = np.zeros(16, np.float32)
        hu2[0], hu2[2], hu2[3] = 0.7, 0.6, np.sqrt(1 - 0.49 - 0.36)
        vectors = {"hu1": unit(1, 1), "hu2": hu2, "en": unit(0.9, 2)}
        stories = [story("hu1", "telex", "hu"), story("hu2", "hvg", "hu"), story("en", "bbc", "en")]
        self.assertEqual(self.merged(stories, vectors), [1, 2])

    def test_three_languages_end_as_one_story(self):
        # English and French are each closest to the Hungarian story; neither may take the
        # other's place, so all three end in one story.
        vectors = {"hu": unit(1, 1), "en": unit(0.9, 2), "fr": unit(0.88, 3)}
        stories = [story("hu", "telex", "hu"), story("en", "bbc", "en"), story("fr", "lefigaro", "fr")]
        self.assertEqual(self.merged(stories, vectors), [3])

    def test_same_language_only_near_identical(self):
        a, b, c = story("a", "telex", "hu"), story("b", "hvg", "hu"), story("c", "444", "hu")
        self.assertEqual(self.merged([a, b, c], {"a": unit(1, 1), "b": unit(0.95, 2), "c": unit(0.88, 3)}), [1, 2])

    def test_without_the_encoder_nothing_merges(self):
        def missing(texts):
            raise embed.Unavailable("the text encoder is not downloaded; run `paper model`")

        stories = [story("hu", "telex", "hu"), story("en", "bbc", "en")]
        with mock.patch.object(embed, "encode", missing):
            out, warnings = group.merge(stories, feed._k)
        self.assertEqual(out, stories)
        self.assertIn("paper model", warnings[0])

    def test_score_follows_discover(self):
        c = {"members": [{"brand": "kozlony"}, {"brand": "telex"}, {"brand": "24"}], "mechanismHits": ["törvény", "rendelet"]}
        self.assertEqual(feed._score(c), 40 + 15 + 16)
        self.assertEqual(feed._score({"members": [{"brand": "kozlony"}]}), 0)


class RestatedTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.h.issues.mkdir()
        (self.h.issues / "2026-11-17.jsonl").write_text("", encoding="utf-8")

    def check(self, entries, vectors):
        self.h.threads.write_text(json.dumps({"id": "t-a", "title": "A", "entries": entries}) + "\n", encoding="utf-8")
        with mock.patch.object(embed, "encode", encoder(vectors)):
            return issue.restated(self.h, "2026-11-18")

    def test_a_restatement_is_refused(self):
        old = "Az MNB változatlanul hagyta az alapkamatot, a forint gyengült."
        new = "A jegybank nem nyúlt a kamathoz, a döntés után esett a forint."
        with self.assertRaises(issue.Invalid) as e:
            self.check([{"day": "2026-11-17", "text": old}, {"day": "2026-11-18", "text": new}], {old: unit(1, 1), new: unit(0.94, 2)})
        self.assertIn("entry 2 says what entry 1 said", e.exception.errors[0])

    def test_a_new_number_or_name_is_news(self):
        old = "Az MNB változatlanul hagyta az alapkamatot."
        cut = "Az MNB váratlanul 25 bázisponttal csökkentette az alapkamatot."
        named = "A döntést Varga Mihály jelentette be."
        vectors = {old: unit(1, 1), cut: unit(0.94, 2), named: unit(0.94, 3)}
        entries = [{"day": "2026-11-17", "text": old}, {"day": "2026-11-18", "text": cut}, {"day": "2026-11-18", "text": named}]
        self.assertIsNone(self.check(entries, vectors))

    def test_only_entries_since_the_last_issue(self):
        a, b = "Ugyanaz.", "Ugyanaz megint."
        self.assertIsNone(self.check([{"day": "2026-11-16", "text": a}, {"day": "2026-11-17", "text": b}], {a: unit(1, 1), b: unit(1, 1)}))

    def test_without_the_encoder_a_note(self):
        def missing(texts):
            raise embed.Unavailable("the text encoder is not downloaded; run `paper model`")

        self.h.threads.write_text(json.dumps({"id": "t-a", "title": "A", "entries": [
            {"day": "2026-11-17", "text": "a"}, {"day": "2026-11-18", "text": "b"}]}) + "\n", encoding="utf-8")
        with mock.patch.object(embed, "encode", missing):
            self.assertIn("not checked", issue.restated(self.h, "2026-11-18"))


if __name__ == "__main__":
    unittest.main()
