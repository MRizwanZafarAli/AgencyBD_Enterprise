"""
Egress-filtering forward proxy for headless Chrome.

Chrome follows redirects and loads sub-resources (images, scripts, iframes, fetch/XHR) on its own, so checking only the first URL
is not enough: any of those could point at 127.0.0.1, a cloud metadata address or an internal host. Chrome is started with
`--proxy-server` pointing at this proxy, so EVERY connection it makes passes through `_open_upstream`, which:

  1. allows only ports 80 and 443,
  2. resolves the host itself and rejects the connection if ANY resolved address is not globally routable, and
  3. connects to the validated IP (pinned), so a DNS answer that changes afterwards cannot redirect the connection (rebinding).

Supports CONNECT (HTTPS) and absolute-URI HTTP requests. Bounded in bytes and time per connection.
"""

import select
import socket
import threading
from typing import List, Optional, Tuple
from urllib.parse import urlsplit

from net.fetcher import SSRFSecurityError, _check_ip

ALLOWED_PORTS = (80, 443)
MAX_HEADER_BYTES = 16 * 1024
MAX_RELAY_BYTES = 40 * 1024 * 1024
CONNECTION_DEADLINE = 25.0


_resolve = socket.getaddrinfo      # indirection so tests can fake DNS without touching the global socket module


def _open_upstream(host: str, port: int) -> socket.socket:
    if port not in ALLOWED_PORTS:
        raise SSRFSecurityError(f"Port {port} is not allowed for browser traffic.")
    infos = _resolve(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    if not infos:
        raise OSError("no address")
    for *_, sockaddr in infos:
        _check_ip(sockaddr[0])                      # every answer must be public, not just the one we use
    family, socktype, proto, _canon, sockaddr = infos[0]
    sock = socket.socket(family, socktype, proto)
    sock.settimeout(10)
    sock.connect(sockaddr)
    return sock


def _relay(a: socket.socket, b: socket.socket, deadline: float) -> None:
    import time
    total = 0
    socks = [a, b]
    while time.time() < deadline and total < MAX_RELAY_BYTES:
        ready, _, _ = select.select(socks, [], [], 1.0)
        for s in ready:
            try:
                data = s.recv(65536)
            except OSError:
                return
            if not data:
                return
            total += len(data)
            (b if s is a else a).sendall(data)


class EgressProxy:
    """Context manager: `with EgressProxy() as proxy: ... proxy.url`"""

    def __init__(self):
        self._server: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.blocked: List[Tuple[str, str]] = []
        self.allowed = 0
        self.port = 0

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> "EgressProxy":
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))              # loopback only
        self._server.listen(64)
        self._server.settimeout(0.5)
        self.port = self._server.getsockname()[1]
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._server:
            self._server.close()

    def _serve(self) -> None:
        while self._running:
            try:
                client, _ = self._server.accept()
            except (socket.timeout, OSError):
                continue
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _deny(self, client: socket.socket, target: str, reason: str, status: str = "403 Forbidden") -> None:
        self.blocked.append((target, reason))
        try:
            client.sendall(f"HTTP/1.1 {status}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
        except OSError:
            pass

    def _handle(self, client: socket.socket) -> None:
        import time
        deadline = time.time() + CONNECTION_DEADLINE
        upstream = None
        try:
            client.settimeout(10)
            buf = b""
            while b"\r\n\r\n" not in buf and len(buf) < MAX_HEADER_BYTES:
                chunk = client.recv(4096)
                if not chunk:
                    return
                buf += chunk
            head, _, rest = buf.partition(b"\r\n\r\n")
            lines = head.decode("latin-1").split("\r\n")
            method, target, _version = (lines[0].split(" ", 2) + ["", ""])[:3]
            if method.upper() == "CONNECT":
                host, _, port_s = target.rpartition(":")
                try:
                    upstream = _open_upstream(host.strip("[]"), int(port_s))
                except SSRFSecurityError as exc:
                    return self._deny(client, target, str(exc))
                except (OSError, ValueError):
                    return self._deny(client, target, "unreachable", "502 Bad Gateway")
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                if rest:
                    upstream.sendall(rest)
            else:
                parts = urlsplit(target)
                if parts.scheme != "http" or not parts.hostname:
                    return self._deny(client, target, "unsupported proxy request", "400 Bad Request")
                try:
                    upstream = _open_upstream(parts.hostname, parts.port or 80)
                except SSRFSecurityError as exc:
                    return self._deny(client, target, str(exc))
                except (OSError, ValueError):
                    return self._deny(client, target, "unreachable", "502 Bad Gateway")
                path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
                headers = [l for l in lines[1:] if not l.lower().startswith(("proxy-", "connection:"))]
                upstream.sendall((f"{method} {path} HTTP/1.1\r\n" + "\r\n".join(headers) + "\r\nConnection: close\r\n\r\n").encode("latin-1") + rest)
            self.allowed += 1
            _relay(client, upstream, deadline)
        except Exception:
            pass
        finally:
            for s in (upstream, client):
                try:
                    if s:
                        s.close()
                except OSError:
                    pass
