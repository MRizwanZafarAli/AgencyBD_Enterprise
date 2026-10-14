"""TLS inspection of a site's HTTPS endpoint.

Connects to the IP address already validated by the SSRF guard (so DNS cannot redirect it inward), performs a normal
verifying handshake with SNI, and reports what a browser would see. `valid` is True/False when we got a verdict and None
when we could not tell (port closed, timeout, handshake refused with modern settings)."""

import socket
import ssl
import time
from typing import Any, Dict

from net.fetcher import SafeFetcher


def inspect_tls(domain: str, timeout: float = 6.0) -> Dict[str, Any]:
    ip = SafeFetcher.resolve_and_validate_hostname(domain)
    context = ssl.create_default_context()
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=domain) as tls:
                cert, protocol, cipher = tls.getpeercert(), tls.version(), tls.cipher()
    except ssl.SSLCertVerificationError as exc:
        return {"valid": False, "error": exc.verify_message or str(exc), "verify_code": exc.verify_code}
    except (ssl.SSLError, OSError) as exc:
        return {"valid": None, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    not_after = ssl.cert_time_to_seconds(cert["notAfter"])
    issuer = dict(x[0] for x in cert.get("issuer", ()))
    subject = dict(x[0] for x in cert.get("subject", ()))
    return {
        "valid": True, "protocol": protocol, "cipher": cipher[0] if cipher else None,
        "not_after": cert["notAfter"], "days_remaining": int((not_after - time.time()) // 86400),
        "issuer": issuer.get("organizationName") or issuer.get("commonName"), "subject": subject.get("commonName"),
    }
