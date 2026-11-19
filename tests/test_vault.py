"""The record, encrypted: what is on disk, a lost key, a wrong key, and the plain rows from before."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper import learn, reading, vault
from paper.home import Home

CODE = "TEST-TEST-TEST-TEST-TEST-TEST"
OTHER = "ABCD-EFGH-JKLM-NPQR-STUV-WXYZ"


class VaultTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.env = mock.patch.dict(os.environ, {vault.ENV: CODE})
        self.env.start()
        vault._cache.clear()

    def tearDown(self):
        self.env.stop()
        vault._cache.clear()

    def test_the_record_on_disk_says_nothing(self):
        reading.log(self.h, {"ev": "open", "id": "r-2026-11-19-1"})
        learn.add_mark(self.h, "r-2026-11-19-1", "question", "What does three sigma mean?")
        for path in (self.h.reads, self.h.marks):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(all(ln.startswith(vault.PREFIX) for ln in text.splitlines()))
            self.assertNotIn("r-2026", text)
        self.assertNotIn("sigma", self.h.marks.read_text(encoding="utf-8"))
        self.assertEqual([e["id"] for e in reading.events(self.h)], ["r-2026-11-19-1"])
        self.assertEqual([m["text"] for m in learn.marks(self.h).values()], ["What does three sigma mean?"])

    def test_plain_rows_from_before_are_read_then_sealed(self):
        self.h.reads.parent.mkdir(parents=True, exist_ok=True)
        self.h.reads.write_text(json.dumps({"ev": "open", "id": "r-1", "t": "x"}) + "\n{cut sho", encoding="utf-8")
        reading.log(self.h, {"ev": "open", "id": "r-2"})
        self.assertEqual([e["id"] for e in reading.events(self.h)], ["r-1", "r-2"])
        self.assertEqual(vault.migrate(self.h), 1)
        self.assertNotIn("r-1", self.h.reads.read_text(encoding="utf-8"))
        self.assertEqual([e["id"] for e in reading.events(self.h)], ["r-1", "r-2"])
        self.assertEqual(vault.migrate(self.h), 0)

    def test_another_key_is_refused_not_read_as_empty(self):
        for n in range(3):
            reading.log(self.h, {"ev": "open", "id": f"r-{n}"})
        with mock.patch.dict(os.environ, {vault.ENV: OTHER}):
            with self.assertRaises(vault.Locked):
                reading.events(self.h)
            with self.assertRaises(ValueError):
                vault.restore(self.h, OTHER)
            vault.restore(self.h, CODE.lower().replace("-", " "))  # typed loosely, still the code
            self.assertEqual(len(reading.events(self.h)), 3)

    def test_a_new_key_never_replaces_the_lost_one(self):
        reading.log(self.h, {"ev": "open", "id": "r-1"})
        kept = {}
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(vault, "_stored", lambda: kept.get("code")), \
                mock.patch.object(vault, "_store", lambda c: kept.__setitem__("code", c)):
            vault._cache.clear()
            with self.assertRaises(vault.Locked):
                vault.ensure(self.h)
            self.assertEqual(kept, {})
            fresh = Home(Path(tempfile.mkdtemp()))
            made = vault.ensure(fresh)
            self.assertEqual(vault.normal(made), made)
            self.assertTrue(vault.unsaved(fresh))
            self.assertIsNone(vault.ensure(fresh))

    def test_codes(self):
        c = vault.new_code()
        self.assertRegex(c, r"^([A-HJ-NP-Z2-9]{4}-){5}[A-HJ-NP-Z2-9]{4}$")
        for bad in ("", "TEST", "0000-0000-0000-0000-0000-0000", CODE + "T"):
            with self.assertRaises(ValueError):
                vault.normal(bad)


if __name__ == "__main__":
    unittest.main()
