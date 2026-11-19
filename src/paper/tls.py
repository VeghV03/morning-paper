"""HTTPS for the phone: the paper's own certificate authority and the certificate it signs.

The authority is made once, kept in $PAPER_HOME/.tls, and installed on each phone. It may vouch
only for `.local` names and home-network addresses (name constraints), so a stolen copy cannot
pass for any other site on a phone that honours the limit. The server's certificate names this
computer's Bonjour name and its current home-network address; it is made again when the address
changes or a month before it runs out.
"""

import datetime as dt
import ipaddress
import os
import socket
import ssl
import subprocess
import sys

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .home import Home

HOME_NETWORKS = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
LEAF_DAYS = 397  # under every phone's limit for a server certificate
RENEW = dt.timedelta(days=30)


def _dir(h: Home):
    return h.root / ".tls"


def name() -> str:
    """This computer's Bonjour name, without `.local`."""
    found = ""
    if sys.platform == "darwin":
        try:
            found = subprocess.run(["scutil", "--get", "LocalHostName"], capture_output=True, text=True,
                                   timeout=2).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            found = ""
    return found or socket.gethostname().split(".")[0]


def lan_ip() -> str | None:
    """The address this computer has on the home network, when it is a home-network address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent; it picks the outgoing interface
            ip = ipaddress.ip_address(s.getsockname()[0])
    except OSError:
        return None
    return str(ip) if any(ip in n for n in HOME_NETWORKS) else None


def _write_private(path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)


def _key_pem(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def authority(h: Home):
    """(certificate, key) of the paper's certificate authority, made on first use."""
    d = _dir(h)
    cert_path, key_path = d / "ca.pem", d / "ca.key"
    if cert_path.exists() and key_path.exists():
        return (x509.load_pem_x509_certificate(cert_path.read_bytes()),
                serialization.load_pem_private_key(key_path.read_bytes(), None))
    d.mkdir(parents=True, exist_ok=True)
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"Morning paper on {name()}")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=True,
                                         crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.NameConstraints(
                permitted_subtrees=[x509.DNSName("local"), *(x509.IPAddress(n) for n in HOME_NETWORKS)],
                excluded_subtrees=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    _write_private(key_path, _key_pem(key))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert, key


def authority_der(h: Home) -> bytes:
    """The authority as the file a phone installs."""
    return authority(h)[0].public_bytes(serialization.Encoding.DER)


def _wanted() -> tuple[str, str | None]:
    return f"{name()}.local".lower(), lan_ip()


def _names(cert) -> tuple[set[str], set[str]]:
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return ({n.lower() for n in san.get_values_for_type(x509.DNSName)},
            {str(i) for i in san.get_values_for_type(x509.IPAddress)})


def server_files(h: Home) -> tuple[str, str]:
    """Paths of the server's certificate chain and key, made again when stale."""
    d = _dir(h)
    cert_path, key_path = d / "server.pem", d / "server.key"
    host, ip = _wanted()
    ca, ca_key = authority(h)
    if cert_path.exists() and key_path.exists():
        cert = x509.load_pem_x509_certificates(cert_path.read_bytes())[0]
        dns, ips = _names(cert)
        fresh = cert.not_valid_after_utc - dt.datetime.now(dt.timezone.utc) > RENEW
        if fresh and host in dns and (ip is None or ip in ips) and cert.issuer == ca.subject:
            return str(cert_path), str(key_path)
    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    alt = [x509.DNSName(host)] + ([x509.IPAddress(ipaddress.ip_address(ip))] if ip else [])
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])).issuer_name(ca.subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=LEAF_DAYS))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    _write_private(key_path, _key_pem(key))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM))
    return str(cert_path), str(key_path)


def context(h: Home) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(*server_files(h))
    return ctx


def refresh(h: Home, ctx: ssl.SSLContext) -> None:
    """Loads a new server certificate into the running context when the address changed."""
    ctx.load_cert_chain(*server_files(h))
