import os
import tempfile
import unittest
from pathlib import Path

from paper import article, config
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain

SENT = "<p>The minister said on Tuesday that the plan would go ahead, whatever the courts decide next month.</p>"


def blocks(html: str) -> list[str]:
    import lxml.html

    return [article._plain(el) for el in lxml.html.fragment_fromstring(article.body(html, "The plan"), create_parent="div")]


class CleanTest(unittest.TestCase):
    """What pages leave around an article goes; the article stays, in English and in Hungarian."""

    def test_the_edges(self):
        html = ("<h1>The plan goes ahead</h1><ul><li>Published</li></ul><p>Listen to this essay</p>"
                "<p>Dark Energy Survey/DOE/FNAL/ DECam/CTIO/NOIRLab/NSF/AURA</p>" + SENT * 3 +
                "<p>Additional reporting by Ann Lee</p><h2>Related topics</h2>"
                "<ul><li>Another story Published10 November</li><li>One more</li></ul>"
                "<p>Get our newsletter with all the headlines you need. Sign up here.</p>")
        self.assertEqual(blocks(html), [SENT[3:-4]] * 3)

    def test_hungarian(self):
        html = (SENT + "<p>— 18 November, 17:57</p>" + SENT +
                "<p>(Borítókép: a miniszter 2026. november 16-án. Fotó: Kovács Anna / Lap)</p>"
                "<h3>Ne maradjon le a legjobb írásainkról, olvassa őket minden nap!</h3>"
                "<ul><li>Iratkozzon fel hírlevelünkre</li><li>Kövessen minket</li></ul>")
        got = blocks(html)
        self.assertEqual(got[-1], SENT[3:-4])
        self.assertIn("— 18 November, 17:57", got)  # in the middle, a short line is the article's

    def test_what_stays(self):
        html = (SENT + "<h2>What comes next</h2>" + SENT + "<p>Photo: a credit under a picture</p>" + SENT +
                "<ul><li>The first point is made in full.</li><li>So is the second one.</li></ul>"
                "<p>* Some names have been changed.</p>")
        got = blocks(html)
        self.assertIn("What comes next", got)
        self.assertNotIn("Photo: a credit under a picture", got)
        self.assertEqual(got[-1], "* Some names have been changed.")
        self.assertTrue(any("So is the second one." in g for g in got))

    def test_news_words_are_not_calls(self):
        last = "<p>Hungary was asked to join the initiative and to support our partners, the minister said</p>"
        html = SENT + "<p>A kormány arra kéri a lakosságot, hogy csatlakozzon és támogassa a javaslatot</p>" + SENT + last
        self.assertEqual(len(blocks(html)), 4)

    def test_lists_that_are_the_article(self):
        top = "<p>Key developments on Nov. 17:</p><ul><li>A bridge collapses after a long operation</li><li>Two more struck</li></ul>"
        end = "<ul><li>The game is out 19 November; £69.99 / €79.99 / $79.99</li></ul>"
        got = blocks(top + SENT + SENT + end)
        self.assertEqual(got[0], "Key developments on Nov. 17:")
        self.assertIn("£69.99", got[-1])

    def test_nothing_left_keeps_everything(self):
        self.assertEqual(blocks("<p>Sign up</p>"), ["Sign up"])


class BylineTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))

    def test_authors(self):
        self.assertEqual(article.authors("Charlie Wood November", "https://a.org/x"), "Charlie Wood")
        self.assertEqual(article.authors("Szerzo; Weiler-Vilmos; Weiler Vilmos", "https://b.hu/x"), "Weiler Vilmos")
        self.assertEqual(article.authors("HVG", "https://hvg.hu/x"), "")
        self.assertEqual(article.authors("April Rubin; Theresa May", "https://a.org"), "April Rubin, Theresa May")
        self.assertEqual(article.authors("A One; B Two; C Three; D Four", "https://a.org"), "A One, B Two, C Three")
        self.assertEqual(article.authors("Pal-Tamas, Pál Tamás", "https://telex.hu/x"), "Pál Tamás")  # one writer, accented
        self.assertEqual(article.authors("Pál Tamás; Pal Tamas", "https://telex.hu/x"), "Pál Tamás")

    def test_footnotes(self):
        raw = 'selected randomly<sup data-fn="9" class="fn"><a href="#9" id="9-link">1</a></sup> from 12<sup>[2]</sup>'
        self.assertEqual(article.FOOTNOTE.sub("", raw), "selected randomly from 12")
        self.assertEqual(blocks("<ol><li>" + "See the replication report for every detail of the study. " * 2 + "↩︎</li></ol>" + SENT * 2)[0][-6:], "study.")

    def test_dates(self):
        self.assertEqual(article.when(self.h, "2026-11-17", "2026-11-19"), "17 November")
        self.assertEqual(article.when(self.h, "2024-03-02", "2026-11-19"), "2 March 2024")
        self.assertEqual(article.when(self.h, None, "2026-11-19"), "")
        self.h.config.write_text("language: hu\n", encoding="utf-8")
        self.assertEqual(article.when(self.h, "2024-03-02", "2026-11-19"), "2024. március 2.")

    def test_morning(self):
        self.assertEqual(config.morning(self.h), "5:07")
        self.h.config.write_text('morning: "06:30"\n', encoding="utf-8")
        self.assertEqual(config.morning(self.h), "6:30")


if __name__ == "__main__":
    unittest.main()
