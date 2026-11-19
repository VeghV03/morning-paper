"""HTTPS for the phone: the certificate a phone trusts, what plain HTTP still shows, and the
plain summary of the record that lives only through the run."""

import datetime as dt
import http.client
import os
import ssl
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from cryptography.x509.verification import PolicyBuilder, Store, VerificationError

from paper import cli, phone, server, tls
from paper.home import Home

os.environ.setdefault("PAPER_RECOVERY_CODE", "TEST-TEST-TEST-TEST-TEST-TEST")  # tests never touch the keychain


def _verify(h: Home, leaf, host: str):
    ca, _ = tls.authority(h)
    verifier = PolicyBuilder().store(Store([ca])).build_server_verifier(x509.DNSName(host))
    return verifier.verify(leaf, [])


class CertificateTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.patches = [mock.patch.object(tls, "name", lambda: "Testmac"),
                        mock.patch.object(tls, "lan_ip", lambda: "192.168.1.9")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def _leaf(self):
        cert_path, _ = tls.server_files(self.h)
        return x509.load_pem_x509_certificates(Path(cert_path).read_bytes())[0]

    def test_a_phone_that_trusts_the_authority_trusts_the_paper(self):
        _verify(self.h, self._leaf(), "testmac.local")
        with self.assertRaises(VerificationError):
            _verify(self.h, self._leaf(), "example.com")

    def test_a_long_computer_name_still_gets_a_certificate(self):
        long = "Mac-" + "x" * 59  # a DNS label may be 63 characters; with .local the name passes 64
        with mock.patch.object(tls, "name", lambda: long):
            _verify(self.h, self._leaf(), f"{long.lower()}.local")

    def test_the_authority_cannot_vouch_for_another_site(self):
        ca, ca_key = tls.authority(self.h)
        key = ec.generate_private_key(ec.SECP256R1())
        now = dt.datetime.now(dt.timezone.utc)
        forged = (x509.CertificateBuilder()
                  .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "bank.example")]))
                  .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
                  .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=30))
                  .add_extension(x509.SubjectAlternativeName([x509.DNSName("bank.example")]), critical=False)
                  .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                  .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                  .sign(ca_key, hashes.SHA256()))
        with self.assertRaises(VerificationError):
            _verify(self.h, forged, "bank.example")

    @unittest.skipIf(sys.platform == "win32", "Windows keeps files private by the folder's access list")
    def test_the_key_files_are_private(self):
        tls.server_files(self.h)
        for f in ("ca.key", "server.key"):
            self.assertEqual(os.stat(self.h.root / ".tls" / f).st_mode & 0o777, 0o600)

    def test_a_new_address_gets_a_new_certificate(self):
        first = self._leaf()
        self.assertEqual(self._leaf().serial_number, first.serial_number)
        with mock.patch.object(tls, "lan_ip", lambda: "192.168.1.10"):
            moved = self._leaf()
        self.assertNotEqual(moved.serial_number, first.serial_number)
        ips = {str(i) for i in moved.extensions.get_extension_for_class(x509.SubjectAlternativeName)
               .value.get_values_for_type(x509.IPAddress)}
        self.assertEqual(ips, {"192.168.1.10"})


class PlainHttpTest(unittest.TestCase):
    """A phone on plain HTTP is sent to /start; the computer and HTTPS are not."""

    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.patches = [mock.patch.dict(os.environ, {"PAPER_HOME": str(self.h.root)}),
                        mock.patch.object(tls, "name", lambda: "testmac"),
                        mock.patch.object(tls, "lan_ip", lambda: None)]
        for p in self.patches:
            p.start()
        self.plain = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.secure = server.TLSServer(("127.0.0.1", 0), tls.context(self.h))
        for s in (self.plain, self.secure):
            threading.Thread(target=s.serve_forever, daemon=True).start()

    def tearDown(self):
        for s in (self.plain, self.secure):
            s.shutdown()
            s.server_close()
        for p in self.patches:
            p.stop()

    def _get(self, path, secure=False):
        if secure:
            ctx = ssl.create_default_context(cadata=tls.authority_der(self.h))
            c = http.client.HTTPSConnection("127.0.0.1", self.secure.server_port, context=ctx, timeout=5)
            c.sock = ctx.wrap_socket(__import__("socket").create_connection(("127.0.0.1", self.secure.server_port)),
                                     server_hostname="testmac.local")
        else:
            c = http.client.HTTPConnection("127.0.0.1", self.plain.server_port, timeout=5)
        c.request("GET", path, headers={"Host": "testmac.local"})
        r = c.getresponse()
        r.read()
        return r

    def test_from_the_network_plain_http_offers_only_the_certificate(self):
        with mock.patch.object(phone, "LOOPBACK", set()):
            for path in ("/", "/settings", "/kept", "/read/r-1"):
                r = self._get(path)
                self.assertEqual((r.status, r.getheader("Location")), (302, "/start"), path)
            self.assertEqual(self._get("/start").status, 200)
            r = self._get("/authority.cer")
            self.assertEqual((r.status, r.getheader("Content-Type")), (200, "application/x-x509-ca-cert"))
            self.assertNotEqual(self._get("/settings", secure=True).getheader("Location"), "/start")

    def test_the_computer_keeps_plain_http(self):
        self.assertNotEqual(self._get("/kept").getheader("Location"), "/start")


class ContextTest(unittest.TestCase):
    def setUp(self):
        self.h = Home(Path(tempfile.mkdtemp()))
        self.path = self.h.root / "context.json"
        self.path.write_text("{}", encoding="utf-8")

    def test_a_stale_one_is_deleted(self):
        server.tidy(self.h)
        self.assertTrue(self.path.exists())
        old = time.time() - (server.CONTEXT_HOURS + 1) * 3600
        os.utime(self.path, (old, old))
        server.tidy(self.h)
        self.assertFalse(self.path.exists())

    def test_publish_deletes_it(self):
        with mock.patch.dict(os.environ, {"PAPER_HOME": str(self.h.root)}), \
                mock.patch.object(cli.issue, "validate", lambda h, day: []), \
                mock.patch.object(cli, "_up", lambda: False):
            self.assertEqual(cli.main(["publish", "--date", "2026-11-19"]), 0)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
