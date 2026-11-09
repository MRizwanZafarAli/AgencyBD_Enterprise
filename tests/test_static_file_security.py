"""The web app's file server must never hand out a file from outside its own folder (found by QA: /etc/passwd and .env were readable
without signing in)."""

import os

import pytest

from api import app, frontend_dist, safe_static_path

SECRET = "TOP-SECRET-VALUE-9f3a"


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>app</html>")
    (root / "assets" / "app.js").write_text("console.log(1)")
    (root / ".hidden").write_text("hidden")
    (tmp_path / ".env").write_text(f"JWT={SECRET}")
    (tmp_path / "outside.txt").write_text("outside")
    os.symlink(tmp_path / ".env", root / "assets" / "link.js")
    return root


def test_real_files_inside_the_folder_are_served(tree):
    assert safe_static_path(str(tree), "assets/app.js") == os.path.realpath(tree / "assets" / "app.js")
    assert safe_static_path(str(tree), "index.html") == os.path.realpath(tree / "index.html")


@pytest.mark.parametrize("bad", ["../.env", "../outside.txt", "assets/../../.env", "..\\.env", "/etc/passwd", "//etc/passwd", "/../.env",
                                 "assets/link.js", ".hidden", "assets/../.hidden", "\x00", "a\x00.js", "", "nothing-here.js"])
def test_nothing_outside_the_folder_and_no_hidden_or_linked_file_is_served(tree, bad):
    assert safe_static_path(str(tree), bad) is None


@pytest.mark.skipif(not os.path.isdir(frontend_dist), reason="the web app has not been built")
@pytest.mark.parametrize("url", ["/%2e%2e%2f%2e%2e%2f.env", "//etc/passwd", "/..%2f.env", "/%2e%2e/.env", "/assets/..%2f..%2f.env", "/..%2f..%2fetc/passwd", "/%252e%252e/.env"])
def test_the_live_server_never_returns_a_file_from_outside(client, url):
    r = client.get(url)
    assert r.status_code in (200, 404)
    assert "root:" not in r.text and "JWT_SECRET" not in r.text and "AGENCYBD_" not in r.text and "HMAC_VAULT" not in r.text
    if r.status_code == 200:
        assert r.headers["content-type"].startswith("text/html")             # only the app's own page, never a downloaded file
