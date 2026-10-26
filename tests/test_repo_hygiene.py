"""Repository hygiene gates: no credentials in source, no runtime output tracked, CI in the place GitHub reads."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"node_modules", ".git", "dist", "__pycache__", ".pytest_cache", "data", "logs", ".venv", "venv"}
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".md", ".yml", ".yaml", ".json", ".sh", ".html", ".css", ".txt", ".example"}

SECRET_PATTERNS = [
    re.compile(r"agy_live_[0-9a-f]{32,}"),               # this app's API keys
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),            # Anthropic
    re.compile(r"AKIA[0-9A-Z]{16}"),                     # AWS access key id
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),           # GitHub tokens
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]
# Tests and docs may mention clearly fake keys; they must not look like real 48-hex keys.
ALLOWED_FILES = {"tests/test_repo_hygiene.py"}


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name.startswith(".env"):
            yield path


def test_no_credentials_in_source_files():
    offenders = []
    for path in iter_text_files():
        rel = str(path.relative_to(ROOT))
        if rel in ALLOWED_FILES or rel == ".env":          # the real .env is git-ignored and never committed
            continue
        text = path.read_text(errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{rel}: matches {pattern.pattern[:30]}")
    assert not offenders, "Credential-looking values found in source:\n" + "\n".join(offenders)


def test_env_file_is_ignored_and_runtime_output_is_not_tracked():
    ignore = (ROOT / ".gitignore").read_text()
    for needle in (".env", "data/*.db", "data/evidence/", "data/screenshots/"):
        assert needle in ignore, f".gitignore must cover {needle}"
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    bad = [f for f in tracked if f == ".env" or f.endswith((".db", ".db-wal", ".db-shm")) or f.startswith(("data/evidence/", "data/screenshots/"))]
    assert not bad, f"Runtime or secret files are tracked: {bad}"


def test_there_is_exactly_one_ci_workflow():
    """GitHub only runs workflows under .github/workflows/. The file may still sit at ci/ci.yml while the token used to push cannot create workflow
    files (it needs the `workflow` scope); move it to .github/workflows/ as soon as it can. Never keep two copies."""
    on_github = (ROOT / ".github" / "workflows" / "ci.yml").exists()
    legacy = (ROOT / "ci" / "ci.yml").exists()
    assert on_github != legacy, "keep exactly one CI workflow file (prefer .github/workflows/ci.yml)"