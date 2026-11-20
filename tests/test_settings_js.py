"""Settings on the phone (reader/settings.js) write what settings.py writes, and refuse what it
refuses, with the same reasons (D83); feeds keep every line but the one edited (D88); a link the
phone saves reaches the inbox (D86)."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from paper import feed, settings
from paper.home import Home
from paper.issue import Invalid

JS = Path(__file__).resolve().parent.parent / "reader" / "settings.js"
RUN = r"""
const fs = require("fs"), vm = require("vm");
const [file, input] = process.argv.slice(2);
const ctx = vm.createContext({ console });
vm.runInContext(fs.readFileSync(file, "utf8"), ctx);
const call = (name, ...args) => {
  try { return { ok: vm.runInContext(name, ctx)(...args) }; } catch (e) { return { errors: e.errors || [String(e)] }; }
};
const out = [];
for (const [name, args] of JSON.parse(fs.readFileSync(input, "utf8"))) out.push(call(name, ...args));
process.stdout.write(JSON.stringify(out));
"""

SECTIONS = [
    [{"name": "World", "what": "news", "topics": ""}, {"name": "Tudomány", "what": "kutatás | új", "topics": "agy, alvás"}],
    [{"name": "Mind:", "what": "x"}],
    [{"name": "A|B", "what": "x"}],
    [{"name": "World", "what": "a"}, {"name": "world!", "what": "b"}],
    [{"name": "N" * 33, "what": "x"}],
    [{"name": "", "what": "orphan"}],
    [{"name": "", "what": "", "topics": ""}],
    [{"name": f"S{i}", "what": "x"} for i in range(9)],
    [{"name": "  Világ hírei ", "what": " sok\n  sor ", "topics": " a | b ,, c "}],
    [{"name": "———", "what": "x"}],
]
FEEDS = """# Sources. A note the phone must keep.
max_per_feed: 2
feeds:
  # China: reporting
  - {name: Sixth Tone, url: "https://www.sixthtone.com/rss", topic: china}
  - {name: 'O''Brien', url: https://obrien.example/feed, only_topic: true}
  # Science
  - {name: "Quanta", url: "https://quanta.example/feed", topic: science}
max_per_topic: 10
"""
PAPER = ["# language: the page's own words\nlanguage: en\nmorning: \"05:07\"\n", "morning: \"05:07\"\n", "", "language: hu\nlanguage: en\n"]
OUTLETS = [{"id": "telex", "org": "Telex", "urls": ["https://telex.hu/rss"]},
           {"id": "nyt-world", "org": "NYT", "urls": ["https://nyt.example/w"]},
           {"id": "nyt-science", "org": "NYT", "urls": ["https://nyt.example/s"]}, {"id": "solo"}]


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class SettingsParityTest(unittest.TestCase):
    def js(self, calls):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "in.json").write_text(json.dumps(calls), encoding="utf-8")
        (tmp / "run.js").write_text(RUN, encoding="utf-8")
        out = subprocess.run(["node", str(tmp / "run.js"), str(JS), str(tmp / "in.json")], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def py(self, fn, path, *args):
        """What a settings.py save writes into a fresh home, or its errors."""
        h = Home(Path(tempfile.mkdtemp()))
        try:
            fn(h, *args)
        except Invalid as e:
            return {"errors": e.errors}
        return {"ok": getattr(h, path).read_text(encoding="utf-8")}

    def test_sections_written_and_refused_alike(self):
        js = self.js([["writeSections", [rows]] for rows in SECTIONS])
        for rows, got in zip(SECTIONS, js):
            self.assertEqual(got, self.py(settings.save_sections, "sections", rows), rows)
        h = Home(Path(tempfile.mkdtemp()))
        settings.save_sections(h, SECTIONS[0])
        read = self.js([["readSections", [h.sections.read_text(encoding="utf-8")]]])[0]["ok"]
        self.assertEqual(read, settings.state(h)["sections"])  # what the page shows is what the Mac shows

    def test_interests_language_and_outlets_alike(self):
        self.assertEqual(self.js([["writeInterests", ["Sleep, memory.\n\n  "]]])[0],
                         self.py(settings.save_interests, "interests", "Sleep, memory.\n\n  "))
        for text in PAPER:
            for lang in ("hu", "de"):
                h = Home(Path(tempfile.mkdtemp()))
                h.config.write_text(text, encoding="utf-8")
                try:
                    settings.save_language(h, lang)
                    want = {"ok": h.config.read_text(encoding="utf-8")}
                except Invalid as e:
                    want = {"errors": e.errors}
                self.assertEqual(self.js([["writeLanguage", [text, lang]]])[0], want, (text, lang))
        h = Home(Path(tempfile.mkdtemp()))
        self.assertEqual(self.js([["newsrooms", [OUTLETS]]])[0]["ok"], settings._newsrooms(OUTLETS))
        for keep in (["telex", "solo"], []):
            h.outlets.write_text(json.dumps(OUTLETS), encoding="utf-8")
            try:
                settings.save_outlets(h, keep)
                want = {"ok": json.loads(h.outlets.read_text(encoding="utf-8"))}
            except Invalid as e:
                want = {"errors": e.errors}
            got = self.js([["writeOutlets", [OUTLETS, keep]]])[0]
            self.assertEqual({"ok": json.loads(got["ok"])} if "ok" in got else got, want)

    def test_feeds_change_one_line_and_keep_the_rest(self):
        gone, added, bad, empty, none = self.js([
            ["removeFeed", [FEEDS, "https://obrien.example/feed"]],
            ["addFeed", [FEEDS, "Ars, \"Tech\"", "https://ars.example/feed"]],
            ["addFeed", [FEEDS, "x", "ftp://x"]],
            ["addFeed", ["max_per_feed: 2\nfeeds: []\n", "", "https://a.example/rss"]],
            ["addFeed", ["max_per_feed: 2\n", "A", "https://a.example/rss"]],
        ])
        before = yaml.safe_load(FEEDS)
        after = yaml.safe_load(gone["ok"])
        self.assertEqual(after["feeds"], [f for f in before["feeds"] if "obrien" not in f["url"]])
        self.assertIn("# Science", gone["ok"])  # the notes stay
        after = yaml.safe_load(added["ok"])
        self.assertEqual(after["feeds"][:3], before["feeds"])  # topics and flags stay
        self.assertEqual(after["feeds"][3], {"name": 'Ars, "Tech"', "url": "https://ars.example/feed"})
        self.assertEqual((after["max_per_feed"], after["max_per_topic"]), (2, 10))
        self.assertEqual(bad, {"errors": ["'ftp://x' is not a web address"]})
        self.assertEqual(yaml.safe_load(empty["ok"])["feeds"], [{"name": "https://a.example/rss", "url": "https://a.example/rss"}])
        self.assertEqual(yaml.safe_load(none["ok"]), {"max_per_feed": 2, "feeds": [{"name": "A", "url": "https://a.example/rss"}]})
        listed = self.js([["readFeeds", [FEEDS]]])[0]["ok"]
        self.assertEqual([(f["name"], f["url"]) for f in listed["feeds"]], [(f["name"], f["url"]) for f in before["feeds"]])
        self.assertTrue(listed["editable"])
        block = "feeds:\n  - name: A\n    url: https://a.example\n"
        self.assertFalse(self.js([["readFeeds", [block]]])[0]["ok"]["editable"])  # written over lines: shown, not edited

    def test_a_saved_link_reaches_the_inbox(self):
        url = self.js([["savedLink", ["  https://example.org/a?b=1 \n"]], ["savedLink", ["not a link"]]])
        self.assertEqual(url[1], {"errors": ["'not a link' is not a web address"]})
        h = Home(Path(tempfile.mkdtemp()))
        (h.root / "saved").mkdir()
        (h.root / "saved" / "2026-11-20T08-00-00-000Z-abc.txt").write_text(url[0]["ok"] + "\n", encoding="utf-8")
        self.assertEqual(feed.fold_saved(h), ["https://example.org/a?b=1"])
        self.assertEqual(feed.inbox(h)[0], ["https://example.org/a?b=1"])
        self.assertEqual(list((h.root / "saved").iterdir()), [])  # gone from the repository with the run's pack


if __name__ == "__main__":
    unittest.main()
