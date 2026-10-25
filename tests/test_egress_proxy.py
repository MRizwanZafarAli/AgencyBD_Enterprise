"""The egress proxy is what stops headless Chrome (redirects, sub-resources, rebinding) from reaching internal addresses."""

import socket
import threading

import pytest

import net.egress_proxy as ep
from net.egress_proxy import EgressProxy


def _request(proxy: EgressProxy, payload: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", proxy.port), timeout=5) as s:
        s.sendall(payload)
        s.settimeout(5)
        try:
            return s.recv(4096)
        except socket.timeout:
            return b""


@pytest.mark.parametrize("target", ["127.0.0.1:443", "localhost:443", "169.254.169.254:80", "10.0.0.5:443", "[::1]:443"])
def test_connect_to_internal_addresses_is_refused(target):
    with EgressProxy() as proxy:
        reply = _request(proxy, f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
        assert reply.startswith(b"HTTP/1.1 403"), reply
        assert proxy.blocked and proxy.allowed == 0


def test_plain_http_to_internal_addresses_is_refused():
    with EgressProxy() as proxy:
        reply = _request(proxy, b"GET http://127.0.0.1:8001/api/leads HTTP/1.1\r\nHost: 127.0.0.1:8001\r\n\r\n")
        assert reply.startswith(b"HTTP/1.1 403")


def test_odd_ports_are_refused_even_on_public_hosts(monkeypatch):
    monkeypatch.setattr(ep, "_resolve", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 22))])
    with EgressProxy() as proxy:
        assert _request(proxy, b"CONNECT example.com:22 HTTP/1.1\r\n\r\n").startswith(b"HTTP/1.1 403")


def test_a_hostname_with_any_private_answer_is_refused(monkeypatch):
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)), (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
    monkeypatch.setattr(ep, "_resolve", lambda *a, **k: answers)
    with EgressProxy() as proxy:
        assert _request(proxy, b"CONNECT rebind.example:443 HTTP/1.1\r\n\r\n").startswith(b"HTTP/1.1 403")


def test_public_destination_is_connected_by_validated_ip_and_relayed(monkeypatch):
    """A local echo server stands in for a public host; the proxy must connect to the IP it validated."""
    echo = socket.socket()
    echo.bind(("127.0.0.1", 0))
    echo.listen(1)
    port = echo.getsockname()[1]
    threading.Thread(target=lambda: (lambda c: (c.sendall(b"pong:" + c.recv(16)), c.close()))(echo.accept()[0]), daemon=True).start()
    monkeypatch.setattr(ep, "_resolve", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))])
    monkeypatch.setattr(ep, "_check_ip", lambda ip: None)                     # pretend 127.0.0.1 is public for this one test
    monkeypatch.setattr(ep, "ALLOWED_PORTS", (port,))
    with EgressProxy() as proxy, socket.create_connection(("127.0.0.1", proxy.port), timeout=5) as s:
        s.sendall(f"CONNECT public.example:{port} HTTP/1.1\r\n\r\n".encode())
        assert s.recv(200).startswith(b"HTTP/1.1 200")
        s.sendall(b"ping")
        assert s.recv(100) == b"pong:ping"


def test_proxy_listens_on_loopback_only_and_closes():
    with EgressProxy() as proxy:
        assert proxy.url.startswith("http://127.0.0.1:")
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", proxy.port), timeout=1).close()


def test_chrome_runs_through_the_proxy_with_sandbox_on(monkeypatch):
    from engines.native_browser_service import NativeBrowserService
    monkeypatch.delenv("AGENCYBD_BROWSER_NO_SANDBOX", raising=False)
    monkeypatch.setattr("os.geteuid", lambda: 1000)
    assert NativeBrowserService._sandbox_flags() == []
    monkeypatch.setenv("AGENCYBD_BROWSER_NO_SANDBOX", "on")
    assert NativeBrowserService._sandbox_flags() == ["--no-sandbox"]
    with EgressProxy() as proxy:
        flags = NativeBrowserService._proxy_flags(proxy)
    assert flags[0].startswith("--proxy-server=http://127.0.0.1:") and flags[1] == "--proxy-bypass-list=<-loopback>"
