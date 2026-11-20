"""The phone page walked in a real browser, on an edition built and sealed as the run builds and
seals it: a page and an edition that disagree fail here, not on the phone (BR33).

A local stand-in answers the GitHub calls the page makes (app.js asks localhost, not GitHub).
Skipped where Chrome or Node is missing; set CHROME to a browser's path to use another."""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from paper import cloud, edition
from paper.home import Home

CODE = "K7QM-W4XR-P9ND-3HTB-ZC6F-VJ2E"
REPO = "reader/paper-data"
DAY = "2026-11-19"
HERE = Path(__file__).resolve().parent
READER = HERE.parent / "reader"
ARTICLE = "<p>" + "The council met and voted on the budget for the coming year. " * 10 + "</p>"
ROWS = [
    {"id": "r-1", "section": "science", "url": "https://www.lab.org/a", "head": "A finding", "lead": "Lead one."},
    {"id": "r-2", "section": "world", "url": "https://daily.com/b", "head": "The budget", "lead": "Lead two."},
    {"id": "r-3", "section": "world", "url": "https://refuses.com/c", "head": "Walled", "lead": "Lead three."},
    {"id": "r-4", "saved": True, "url": "https://essays.net/d", "head": "An essay"},
    {"id": "p-1", "predict": "r-2", "prompt": "Will it pass?", "options": ["Yes", "No"], "answer": 0},
    {"id": f"x-{DAY}", "crossword": [{"answer": w, "clue": f"Clue {w}", "piece": "r-2"}
                                     for w in ("Danube", "budget", "vote", "senate", "bridge", "debt")]},
    {"id": f"w-{DAY}", "lede": "votes", "piece": "r-2"},
]


def extract(url):
    if "refuses" in url:
        return {}
    return {"title": "The budget passes | Daily", "author": "Ann Lee", "date": DAY, "html": ARTICLE}


def chrome():
    for name in (os.environ.get("CHROME"), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome",
                 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 r"C:\Program Files\Google\Chrome\Application\chrome.exe"):
        if name and (shutil.which(name) or Path(name).is_file()):
            return shutil.which(name) or name
    return None


def server(repo: Path):
    """The page's files, and GitHub's contents API over the sealed repository."""
    api = f"/repos/{REPO}"

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(READER), **kw)

        def log_message(self, *a):
            pass

        def send(self, status, body=b"", kind="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == api:
                return self.send(200, b"{}")
            if not path.startswith(api + "/contents/"):
                return super().do_GET()
            f = repo / path[len(api + "/contents/"):]
            if f.is_dir():
                return self.send(200, json.dumps([{"name": x.name, "type": "dir" if x.is_dir() else "file"}
                                                  for x in sorted(f.iterdir())]).encode())
            if not f.is_file():
                return self.send(404, b'{"message": "Not Found"}')
            if "raw" in self.headers.get("Accept", ""):
                return self.send(200, f.read_bytes(), "application/octet-stream")
            return self.send(200, json.dumps({"sha": hashlib.sha1(f.read_bytes()).hexdigest()}).encode())

        def do_PUT(self):  # the phone's record and brief, written back
            f = repo / self.path.split("?")[0][len(api + "/contents/"):]
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(base64.b64decode(body["content"]))
            self.send(201, b'{"content": {}}')

    return ThreadingHTTPServer(("127.0.0.1", 0), Handler)


@unittest.skipUnless(chrome() and shutil.which("node"), "Chrome or Node is not installed")
class PageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        h = Home(self.tmp / "home")
        h.issues.mkdir(parents=True)
        h.digests.mkdir()
        (h.root / "sections.md").write_text("World: news\nScience: research\n", encoding="utf-8")
        (h.issues / f"{DAY}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ROWS), encoding="utf-8")
        edition.build(h, DAY, extract)
        self.repo = self.tmp / "repo"
        cloud.pack(h, self.tmp / "engine-out", self.repo, cloud.run_key(CODE))
        self.http = server(self.repo)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.profile = self.tmp / "chrome"
        self.browser = subprocess.Popen([chrome(), "--headless=new", "--remote-debugging-port=0", "--no-first-run",
                                         "--no-default-browser-check", f"--user-data-dir={self.profile}", "about:blank"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        self.browser.kill()
        self.browser.wait()
        self.http.shutdown()
        self.http.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def walk(self, *routes):
        port_file = self.profile / "DevToolsActivePort"
        for _ in range(100):
            if port_file.exists() and port_file.read_text().strip():
                break
            time.sleep(0.1)
        port = port_file.read_text().split()[0]
        url = f"http://localhost:{self.http.server_address[1]}/"
        out = subprocess.run(["node", str(HERE / "walk.mjs"), port, url, REPO, CODE, *routes],
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout)

    def test_every_page_of_an_issue_opens(self):
        # r-3's outlet refused its text, so the page sends the reader there: not a page of ours
        got = self.walk("", f"{DAY}/r-1", f"{DAY}/r-2", f"{DAY}/r-4", f"{DAY}/done", f"{DAY}/crossword", f"{DAY}/lede",
                        "kept", "settings")
        self.assertEqual(got["errors"], [])
        pages = got["pages"]
        for route, text in pages.items():
            self.assertTrue(text, f"#{route} drew nothing")
        for head in ("A finding", "The budget", "Walled", "An essay"):
            self.assertIn(head, pages[""])
        self.assertIn("Will it pass?", pages[f"{DAY}/r-2"])  # the prediction comes before the piece
        self.assertIn("The council met", pages[f"{DAY}/r-1"])
        self.assertIn("Clue Danube", pages[f"{DAY}/crossword"])


if __name__ == "__main__":
    unittest.main()
