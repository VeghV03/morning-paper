import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from paper import cli, cloud, vault
from paper.home import Home

CODE = "K7QM-W4XR-P9ND-3HTB-ZC6F-VJ2E"


class Base(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.h, self.out, self.repo = Home(tmp / "home"), tmp / "engine-out", tmp / "repo"
        for d in (self.h.root, self.out, self.repo):
            d.mkdir()
        self.key = cloud.run_key(CODE)

    def write(self, root: Path, rel: str, text: str):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


class SealTest(Base):
    def test_the_two_keys_differ_and_the_run_key_cannot_open_the_record(self):
        self.assertNotEqual(self.key, vault._derive(CODE))
        self.assertEqual(self.key, cloud.run_key(CODE.lower().replace("-", "")))

    def test_a_file_moved_to_another_path_does_not_open(self):
        blob = cloud.seal(self.key, "home/sections.md", b"World: news")
        self.assertEqual(cloud.open_(self.key, "home/sections.md", blob), b"World: news")
        with self.assertRaises(cloud.Locked):
            cloud.open_(self.key, "home/interests.md", blob)
        with self.assertRaises(cloud.Locked):
            cloud.open_(cloud.run_key("A" * 24), "home/sections.md", blob)


class PackTest(Base):
    def test_pack_and_unpack_round_trip_and_leave_the_record_out(self):
        self.write(self.h.root, "sections.md", "World: news")
        self.write(self.h.root, "issues/2026-11-19.jsonl", '{"id": "r-1"}\n')
        self.write(self.h.root, ".feed.json", "{}")
        for private in ("reads.jsonl", "marks.jsonl", "context.json", ".feed.json.pending", "cache/r-1.json", ".tls/key.pem"):
            self.write(self.h.root, private, "x")
        self.write(self.out, "feed-snapshots/manifest.jsonl", "{}\n")
        self.write(self.out, "feed-snapshots/2026-11-19/bbc.json", "{}")
        self.write(self.out, "discovery/2026-11-19.json", "{}")
        self.write(self.out, "kozlony/state.json", "{}")
        self.write(self.out, "kozlony/2026/MK-170.pdf", "%PDF")
        done = cloud.pack(self.h, self.out, self.repo, self.key)
        self.assertEqual(sorted(done["written"]), ["engine/feed-snapshots/manifest.jsonl", "engine/kozlony/state.json",
                                                   "home/.feed.json", "home/issues/2026-11-19.jsonl", "home/sections.md"])
        for p in self.repo.rglob("*"):
            if p.is_file():
                self.assertNotIn(b"World", p.read_bytes())  # nothing readable in the repository
        tmp = Path(tempfile.mkdtemp())
        h2, out2 = Home(tmp / "home"), tmp / "out"
        opened = cloud.unpack(h2, out2, self.repo, self.key)
        self.assertEqual(len(opened), 5)
        self.assertEqual((h2.root / "sections.md").read_text(), "World: news")
        self.assertTrue((out2 / "kozlony" / "state.json").exists())

    def test_an_unchanged_file_keeps_its_bytes_and_a_removed_one_goes(self):
        self.write(self.h.root, "sections.md", "World: news")
        self.write(self.h.root, "inbox.md", "https://example.org\n")
        cloud.pack(self.h, self.out, self.repo, self.key)
        before = (self.repo / "home" / "sections.md.sealed").read_bytes()
        (self.h.root / "inbox.md").unlink()
        done = cloud.pack(self.h, self.out, self.repo, self.key)
        self.assertEqual(done, {"written": [], "removed": ["home/inbox.md"]})
        self.assertEqual((self.repo / "home" / "sections.md.sealed").read_bytes(), before)

    def test_unpack_stops_on_a_file_it_cannot_open(self):
        self.write(self.h.root, "sections.md", "World: news")
        cloud.pack(self.h, self.out, self.repo, self.key)
        with self.assertRaises(cloud.Locked):
            cloud.unpack(self.h, self.out, self.repo, cloud.run_key("B" * 24))


class CliTest(Base):
    def run_cli(self, *argv, env=None):
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"PAPER_HOME": str(self.h.root), **(env or {})}), \
                mock.patch("paper.feed.engine_dir", lambda: self.out.parent / "engine"), redirect_stdout(buf):
            code = cli.main(list(argv))
        return code, buf.getvalue()

    def test_key_prints_the_run_key_never_the_code(self):
        code, out = self.run_cli("cloud", "key", "--code", CODE)
        self.assertEqual((code, out.strip()), (0, cloud.encoded(self.key)))
        self.assertNotIn(CODE, out)

    def test_without_a_run_key_unpack_says_how_to_get_one(self):
        with mock.patch.dict(os.environ, {cloud.ENV: ""}):
            code, out = self.run_cli("cloud", "unpack", "--repo", str(self.repo))
        self.assertEqual(code, 1)
        self.assertIn(cloud.ENV, out)

    def test_context_in_the_run_needs_no_record_key(self):
        env = {cloud.ENV: cloud.encoded(self.key), vault.ENV: ""}
        with mock.patch.object(vault, "_stored", lambda: None):
            code, out = self.run_cli("context", env=env)
        self.assertEqual(code, 0, out)
        self.assertIn('"recovery_unsaved": false', out)


if __name__ == "__main__":
    unittest.main()
