"""The phone page (reader/app.js) opens what the run seals (cloud.py), with the same code and key."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from paper import cloud

CODE = "K7QM-W4XR-P9ND-3HTB-ZC6F-VJ2E"
APP = Path(__file__).resolve().parent.parent / "reader" / "app.js"
# app.js in a bare context: its functions without a page
RUN = r"""
const fs = require("fs"), vm = require("vm");
const [app, code, rel, file, other] = process.argv.slice(2);
const noop = () => {};
const ctx = vm.createContext({ crypto: globalThis.crypto, TextEncoder, TextDecoder, console, setTimeout, clearTimeout,
  document: { getElementById: () => ({}), addEventListener: noop }, navigator: { language: "en" }, addEventListener: noop,
  indexedDB: { open: () => ({}) }, location: {}, history: {}, scrollTo: noop });
vm.runInContext(fs.readFileSync(app.replace("app.js", "learn.js"), "utf8"), ctx);
vm.runInContext(fs.readFileSync(app, "utf8"), ctx);
const runKey = vm.runInContext("runKey", ctx);
(async () => {
  const out = {};
  const key = await runKey(code.toLowerCase().replace(/-/g, " "));
  out.opened = await ctx.unseal(key, rel, fs.readFileSync(file));
  try { await ctx.unseal(key, other, fs.readFileSync(file)); out.moved = "opened"; } catch (e) { out.moved = e.message; }
  try { await ctx.unseal(await runKey("A".repeat(24)), rel, fs.readFileSync(file)); out.wrong = "opened"; } catch (e) { out.wrong = e.message; }
  try { ctx.normal("too short"); } catch (e) { out.bad = e.message; }
  const back = await ctx.seal(key, "home/brief.json", '{"day":"2026-11-20"}');  // what the page seals, Python opens
  fs.writeFileSync(file + ".back", back);
  process.stdout.write(JSON.stringify(out));
})();
"""


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class ReaderTest(unittest.TestCase):
    def test_the_page_opens_what_the_run_sealed_and_nothing_else(self):
        rel, data = "home/edition/2026-11-19.json", {"day": "2026-11-19", "dateline": "Csütörtök"}
        tmp = Path(tempfile.mkdtemp())
        (tmp / "blob").write_bytes(cloud.seal(cloud.run_key(CODE), rel, json.dumps(data, ensure_ascii=False).encode()))
        (tmp / "run.js").write_text(RUN, encoding="utf-8")
        out = subprocess.run(["node", str(tmp / "run.js"), str(APP), CODE, rel, str(tmp / "blob"), "home/edition/x.json"],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        got = json.loads(out.stdout)
        self.assertEqual(got["opened"], data)
        self.assertEqual(got["moved"], "That code doesn't open this paper.")  # the path is bound in
        self.assertEqual(got["wrong"], "That code doesn't open this paper.")
        self.assertEqual(got["bad"], "A recovery code is 24 letters and digits.")
        back = (tmp / "blob.back").read_bytes()
        self.assertEqual(cloud.open_(cloud.run_key(CODE), "home/brief.json", back), b'{"day":"2026-11-20"}')


if __name__ == "__main__":
    unittest.main()
