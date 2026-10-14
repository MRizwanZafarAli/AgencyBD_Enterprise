"""A deterministic fake internet for auditor/resolver tests (no sockets, no DNS).

    web["acme.example"] = html                       # https://acme.example/ and http://acme.example/ (same page)
    web["acme.example/robots.txt"] = "User-agent: *" # any path on a known host
    web["acme.example"] = {"html": ..., "headers": {...}, "status": 200, "elapsed_ms": 120}
    web["http://acme.example"] = {"redirect": "https://acme.example/"}
Unknown hosts raise HostUnreachableError; unknown paths on known hosts return 404.
"""

from net.fetcher import FetchResult, HostUnreachableError


def page(title="", desc="", h1="", footer="", extra="", body="Welcome to our site. " * 6, lang=""):
    html_open = f"<html lang='{lang}'>" if lang else "<html>"
    return (f"{html_open}<head><title>{title}</title><meta name='description' content='{desc}'>{extra}</head>"
            f"<body><h1>{h1}</h1><p>{body}</p><footer>{footer}</footer></body></html>")


DEFAULT_TLS = {"valid": True, "protocol": "TLSv1.3", "cipher": "TLS_AES_256_GCM_SHA384", "not_after": "Jan  1 00:00:00 2030 GMT",
               "days_remaining": 400, "issuer": "Test CA", "subject": "example"}


def install_fake_web(monkeypatch):
    from net.fetcher import SafeFetcher
    import auditors.context as ctxmod

    class Pages(dict):
        pass

    pages, tls, seen = Pages(), {}, []

    def normalise(url):
        scheme, rest = url.split("://", 1) if "://" in url else ("https", url)
        host, _, path = rest.partition("/")
        return scheme, host.lower(), "/" + path.split("?")[0]

    def fake(cls, url, timeout=10, max_bytes=0, headers=None, method="GET", json_body=None, form_body=None):
        scheme, host, path = normalise(url)
        seen.append(f"{scheme}://{host}{path}")
        known = [k for k in pages if k.split("://")[-1].split("/")[0].lower() == host]
        if not known:
            raise HostUnreachableError(f"no such host {host}")
        root = path.rstrip("/") == ""
        entry = None
        for key in ([f"{scheme}://{host}"] if root else []) + ([f"{scheme}://{host}{path}"] if not root else []) + \
                  ([host] if root else [host + path]):
            if key in pages:
                entry = pages[key]
                break
        if entry is None:
            return FetchResult(404, "Not found", {}, f"{scheme}://{host}{path}", 30)
        if isinstance(entry, str):
            entry = {"html": entry}
        if "redirect" in entry:
            return FetchResult(200, "<html><body>redirected</body></html>", {}, entry["redirect"], entry.get("elapsed_ms", 80))
        return FetchResult(entry.get("status", 200), entry.get("html", ""), entry.get("headers", {"Content-Type": "text/html", "Content-Encoding": "gzip", "Cache-Control": "max-age=60"}),
                           f"{scheme}://{host}{path if not root else '/'}", entry.get("elapsed_ms", 120))

    monkeypatch.setattr(SafeFetcher, "safe_fetch", classmethod(fake))
    monkeypatch.setattr(ctxmod, "inspect_tls", lambda domain, timeout=6.0: tls.get(domain, dict(DEFAULT_TLS)))
    pages.tls, pages.seen = tls, seen  # attribute access for tests
    return pages
