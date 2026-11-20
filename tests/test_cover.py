"""The cover's composer and the museum search's parsing, with no network."""

import json
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from paper import cover

SAVED = json.loads((Path(__file__).parent / "museums.json").read_text(encoding="utf-8"))
CLAIM = "Saudi oil exports reached their highest level since the war began in February."


class ComposerTest(unittest.TestCase):
    photo = Image.fromarray(np.tile(np.linspace(0, 255, 600, dtype=np.uint8), (800, 1)))

    def test_sizes_are_honoured_and_a_rerun_is_the_same(self):
        for size in ((390, 844), (480, 800), (780, 1688)):
            for theme in cover.THEMES:
                self.assertEqual(cover.draw("2026-11-21", CLAIM, self.photo, size, theme).size, size)
        a, b = (cover.png(cover.draw("2026-11-21", CLAIM, self.photo)) for _ in range(2))
        self.assertEqual(a, b)

    def test_the_photo_sits_where_the_specimen_put_it(self):
        img = np.asarray(cover.draw("2026-11-21", CLAIM, self.photo).convert("L"))
        rows = [y for y in range(844) if (img[y] != img[0, 0]).mean() > 0.9]  # full width, off the ground: the photo
        self.assertAlmostEqual(rows[0], 96, delta=2)
        self.assertAlmostEqual(rows[-1] - rows[0] + 1, 500, delta=2)

    def test_a_grim_day_has_no_photo(self):
        img = np.asarray(cover.draw("2026-11-21", "A test.", None).convert("L"))
        self.assertEqual(img[300:].std(), 0)  # below a short claim: the ground alone, no grain
        self.assertGreater(len(np.unique(img[96:300])), 2)  # the claim, set large


class SearchTest(unittest.TestCase):
    def test_only_cc0_records_come_through(self):
        self.assertEqual([c["id"] for c in cover.cma(SAVED["cleveland"])], ["cma-163456"])
        self.assertEqual([c["id"] for c in cover.aic(SAVED["art_institute"])], ["aic-152747"])
        self.assertEqual([c["id"] for c in cover.met(SAVED["met_object"])], ["met-335809"])
        self.assertEqual(cover.met({**SAVED["met_object"], "isPublicDomain": False}), [])

    def test_a_candidate_names_its_picture(self):
        c = cover.aic(SAVED["art_institute"])[0]
        self.assertEqual(c["image"], "https://www.artic.edu/iiif/2/3192ae4d-ffca-fe91-af12-2ca681f43e13/full/843,/0/default.jpg")
        self.assertEqual(cover.cma(SAVED["cleveland"])[0]["artist"], "Fitz Henry Lane (American, 1804–1865)")

    def test_an_id_that_is_not_a_museums_is_refused_before_any_request(self):
        with self.assertRaises(cover.Refused):
            cover.record("wiki-12")


if __name__ == "__main__":
    unittest.main()
