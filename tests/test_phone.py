import http.client
import json
import os
import stat
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from paper import phone, server
from paper.home import Home


class GateTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.key = phone.key(self.h)

    def test_the_mac_is_let_in_by_its_address(self):
        self.assertTrue(phone.allowed(self.h, "127.0.0.1", "localhost:4747", None))
        self.assertTrue(phone.allowed(self.h, "::1", "127.0.0.1:4747", None))

    def test_another_device_naming_localhost_is_not(self):
        self.assertFalse(phone.allowed(self.h, "192.168.1.20", "localhost:4747", None))
        self.assertFalse(phone.allowed(self.h, "192.168.1.20", "localhost", "wrong"))

    def test_a_rebound_name_on_the_mac_is_not(self):
        self.assertFalse(phone.allowed(self.h, "127.0.0.1", "evil.example:4747", None))

    def test_a_paired_phone_is(self):
        self.assertTrue(phone.allowed(self.h, "192.168.1.20", "mac.local:4747", self.key))

    def test_a_new_code_unpairs(self):
        phone.new_key(self.h)
        self.assertFalse(phone.allowed(self.h, "192.168.1.20", "mac.local:4747", self.key))

    def test_key_file_is_private(self):
        mode = stat.S_IMODE(os.stat(self.h.root / ".phone-key").st_mode)
        self.assertEqual(mode, 0o600)

    def test_writes_from_another_site_are_refused(self):
        self.assertTrue(phone.same_origin(None, "mac.local:4747"))
        self.assertTrue(phone.same_origin("http://mac.local:4747", "mac.local:4747"))
        self.assertFalse(phone.same_origin("http://evil.example", "mac.local:4747"))
        self.assertFalse(phone.same_origin("http://mac.local:9999", "mac.local:4747"))


class CodeTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        phone.open_codes()

    def test_current_and_previous_code_pair(self):
        now = 1_800_000_000.0
        self.assertTrue(phone.check_code(self.h, phone.short_code(self.h, now), now))
        self.assertTrue(phone.check_code(self.h, phone.short_code(self.h, now - 300), now))
        self.assertFalse(phone.check_code(self.h, phone.short_code(self.h, now - 600), now))

    def test_spaces_are_fine(self):
        code = phone.short_code(self.h)
        self.assertTrue(phone.check_code(self.h, code[:3] + " " + code[3:]))

    def test_five_wrong_codes_lock_until_settings_opens(self):
        right = phone.short_code(self.h)
        wrong = str((int(right) + 1) % 1_000_000).zfill(6)
        for _ in range(phone.TRIES):
            self.assertFalse(phone.check_code(self.h, wrong))
        self.assertTrue(phone.code_locked())
        self.assertFalse(phone.check_code(self.h, right))
        phone.open_codes()
        self.assertTrue(phone.check_code(self.h, right))

    def test_a_new_key_changes_the_code(self):
        now = 1_800_000_000.0
        before = phone.short_code(self.h, now)
        phone.new_key(self.h)
        self.assertNotEqual(phone.short_code(self.h, now), before)


class PairTest(unittest.TestCase):
    """The pair route over a real socket, from the Mac's own address."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        os.environ["PAPER_HOME"] = str(self.root)
        (self.root / "sections.md").write_text("World: news\n", encoding="utf-8")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.port = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        os.environ.pop("PAPER_HOME", None)

    def ask(self, method, path, body=None, host=None, cookie=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        headers = {"Host": host or f"localhost:{self.port}"}
        if cookie:
            headers["Cookie"] = cookie
        c.request(method, path, json.dumps(body) if body is not None else None, headers)
        r = c.getresponse()
        return r.status, r.getheader("Set-Cookie"), r.read()

    def test_pairing(self):
        key = phone.key(Home(self.root))
        self.assertEqual(self.ask("GET", "/settings")[0], 200)
        self.assertEqual(self.ask("GET", "/settings", host="evil.example")[0], 403)
        self.assertEqual(self.ask("POST", "/pair", {"key": "nope"})[0], 403)
        status, cookie, _ = self.ask("POST", "/pair", {"key": key})
        self.assertEqual(status, 204)
        self.assertIn(f"paper={key}", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertEqual(self.ask("GET", "/settings", host="evil.example", cookie=f"paper={key}")[0], 200)
        self.assertEqual(self.ask("GET", "/pair", host="evil.example")[0], 200)  # tells nothing

    def test_pairing_by_code(self):
        phone.open_codes()
        status, _, body = self.ask("POST", "/pair", {"code": "nope"})
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body), {"locked": False})
        status, cookie, _ = self.ask("POST", "/pair", {"code": phone.short_code(Home(self.root))})
        self.assertEqual(status, 204)
        self.assertIn("paper=", cookie)

    def test_a_huge_body_is_not_read(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.putrequest("POST", "/pair", skip_host=True)
        c.putheader("Host", f"localhost:{self.port}")
        c.putheader("Content-Length", str(10**9))
        c.endheaders()
        self.assertEqual(c.getresponse().status, 400)
        c.close()

    def test_only_the_mac_makes_a_new_code(self):
        key = phone.key(Home(self.root))
        self.assertEqual(self.ask("PUT", "/settings/phone", {}, host="mac.local", cookie=f"paper={key}")[0], 403)
        self.assertEqual(self.ask("PUT", "/settings/phone", {})[0], 200)
        self.assertNotEqual(phone.key(Home(self.root)), key)


if __name__ == "__main__":
    unittest.main()
