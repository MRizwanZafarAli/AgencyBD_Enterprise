"""
SSRF-safe HTTP client for AgencyBD_Enterprise.

Every outbound fetch of a user-influenced URL must go through ``SafeFetcher``.

How it is safe
  * The address validated is the address that is *connected to*. urllib3's connection
    factory is wrapped so each resolved IP is checked immediately before ``connect()``.
    That also covers every redirect hop and defeats DNS-rebinding (validate-then-resolve-again).
  * Only globally routable IPs are allowed: loopback, private, link-local (incl. cloud
    metadata 169.254.169.254), CGNAT, multicast, reserved, unspecified and IPv4-mapped
    forms of those are all refused.
  * Redirect count, response size and time are capped.
"""

import ipaddress
import socket
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
import urllib3.util.connection as _u3_connection

MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_TIMEOUT_SECONDS = 10
MAX_REDIRECTS = 5

_guard = threading.local()


class SSRFSecurityError(ValueError):
    """Raised when a request target resolves to a restricted or non-public address."""


class HostUnreachableError(OSError):
    """Raised when a host cannot be resolved. An operational failure, not a policy violation."""


def _check_ip(ip_str: str) -> None:
    ip = ipaddress.ip_address(ip_str.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if not ip.is_global or ip.is_multicast:
        raise SSRFSecurityError(f"Access to non-public network address {ip} is blocked by SSRF policy.")


def _guarded_create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, socket_options=None):
    """Drop-in for urllib3.util.connection.create_connection that validates the IP it connects to."""
    host, port = address
    host = host.strip("[]")
    last_error: Optional[Exception] = None
    infos = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    if not infos:
        raise OSError("getaddrinfo returned an empty list")
    for family, socktype, proto, _canon, sockaddr in infos:
        _check_ip(sockaddr[0])  # raises SSRFSecurityError; never swallowed below
        sock = None
        try:
            sock = socket.socket(family, socktype, proto)
            for opt in socket_options or ():
                sock.setsockopt(*opt)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            last_error = exc
            if sock is not None:
                sock.close()
    raise last_error or OSError("connection failed")


_original_create_connection = _u3_connection.create_connection


def _dispatching_create_connection(*args, **kwargs):
    # Guard only calls made by SafeFetcher (thread-local flag); all other urllib3 users are untouched.
    if getattr(_guard, "active", False):
        return _guarded_create_connection(*args, **kwargs)
    return _original_create_connection(*args, **kwargs)


_u3_connection.create_connection = _dispatching_create_connection


@dataclass
class FetchResult:
    status_code: int
    text: str
    headers: Dict[str, str] = field(default_factory=dict)
    final_url: str = ""
    elapsed_ms: int = 0


class SafeFetcher:
    """Hardened GET client. See module docstring."""

    @staticmethod
    def validate_ip_address(ip_str: str) -> None:
        _check_ip(ip_str)

    @staticmethod
    def resolve_and_validate_hostname(hostname: str) -> str:
        """Resolves a hostname and verifies every address is public. Returns the first address."""
        if not hostname:
            raise SSRFSecurityError("Hostname cannot be empty.")
        try:
            infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise HostUnreachableError(f"DNS resolution failure for host '{hostname}': {exc}")
        ips = [info[4][0] for info in infos]
        if not ips:
            raise HostUnreachableError(f"No IP address returned for host '{hostname}'.")
        for ip in ips:
            _check_ip(ip)
        return ips[0]

    @classmethod
    def safe_fetch(
        cls,
        url: str,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = MAX_RESPONSE_BYTES,
        headers: Optional[Dict[str, str]] = None,
        method: str = "GET",
        json_body: Optional[Any] = None,
        form_body: Optional[Dict[str, str]] = None,
    ) -> FetchResult:
        if "://" not in url:
            url = f"https://{url}"
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise SSRFSecurityError(f"Unsupported or invalid URL: {url!r}")
        if parsed.username or parsed.password:
            raise SSRFSecurityError("Credentials in URLs are not allowed.")

        cls.resolve_and_validate_hostname(parsed.hostname)  # friendly early error

        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 AgencyBD-Auditor/2.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if headers:
            req_headers.update(headers)

        session = requests.Session()
        session.max_redirects = MAX_REDIRECTS
        _guard.active = True
        try:
            response = session.request(method, url, headers=req_headers, timeout=timeout, stream=True, allow_redirects=True,
                                       json=json_body, data=form_body)
            try:
                chunks, total = [], 0
                for chunk in response.iter_content(chunk_size=16384):
                    total += len(chunk)
                    if total > max_bytes:
                        break
                    chunks.append(chunk)
                body = b"".join(chunks)
                text = body.decode(response.encoding or "utf-8", errors="replace")
                return FetchResult(
                    status_code=response.status_code,
                    text=text,
                    headers=dict(response.headers),
                    final_url=response.url,
                    elapsed_ms=int(response.elapsed.total_seconds() * 1000),
                )
            finally:
                response.close()
        except requests.exceptions.RequestException as exc:
            # requests wraps connect-time errors; surface our policy error unchanged.
            cause = exc
            while cause is not None:
                if isinstance(cause, SSRFSecurityError):
                    raise cause
                cause = cause.__cause__ or cause.__context__
            raise
        finally:
            _guard.active = False
            session.close()

    @classmethod
    def safe_get(
        cls,
        url: str,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = MAX_RESPONSE_BYTES,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, Dict[str, str]]:
        """Backwards-compatible tuple form: (status_code, text, headers)."""
        result = cls.safe_fetch(url, timeout=timeout, max_bytes=max_bytes, headers=headers)
        return result.status_code, result.text, result.headers
