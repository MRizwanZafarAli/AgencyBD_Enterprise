"""
InteractiveBrowserSession: a page viewer (rendered DOM summary + screenshot) and a launcher for a normal Chrome window.

It does NOT drive pages: it never clicks, types or scrolls for you. To work a page by hand (log in, fill a form), use
launch_headed_window, which opens a real Chrome window on THIS machine with its own profile folder.
"""

import base64
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from engines.native_browser_service import NativeBrowserService
from net.fetcher import _check_ip, SafeFetcher, SSRFSecurityError
from net.process_supervisor import ProcessSupervisor
from net.validate import clean_domain


class InteractiveBrowserSession:
    """A per-user viewer session: navigate, then read the rendered DOM summary and a screenshot."""

    def __init__(self, session_id: str = "default_session", storage_dir: Optional[str] = None):
        self.session_id = session_id
        self.storage_dir = Path(storage_dir or os.path.join("data", "interactive_sessions", session_id))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.browser_service = NativeBrowserService(storage_dir=str(self.storage_dir))
        self.current_url: Optional[str] = None
        self.current_domain: Optional[str] = None
        self.history: list[str] = []
        self.last_screenshot_path: Optional[str] = None
        self.last_screenshot_uri: Optional[str] = None
        self.dom_state: Dict[str, Any] = {}

    def navigate(self, target: str, viewport: str = "desktop") -> Dict[str, Any]:
        """Navigates to URL, validates SSRF, renders DOM, and captures live viewport."""
        clean_host = clean_domain(target)
        target_url = f"https://{clean_host}" if not target.startswith("http") else target
        self.browser_service._validate_ssrf_for_url(target_url)

        self.current_url = target_url
        self.current_domain = clean_host
        self.history.append(target_url)

        # 1. Render Virtual DOM
        dom_data = self.browser_service.render_spa_dom(target_url)
        self.dom_state = dom_data

        # 2. Capture Viewport Screenshot
        shot_data = self.browser_service.capture_screenshot(target_url, viewport=viewport)
        if shot_data.get("status") == "success":
            self.last_screenshot_path = shot_data.get("file_path")
            self.last_screenshot_uri = shot_data.get("data_uri")

        return {
            "status": "success",
            "session_id": self.session_id,
            "current_url": self.current_url,
            "title": dom_data.get("title", ""),
            "detected_stack": dom_data.get("detected_stack", []),
            "emails": dom_data.get("emails", []),
            "phones": dom_data.get("phones", []),
            "viewport_screenshot": self.last_screenshot_uri,
            "mode": "viewer"
        }

    def launch_headed_window(self, url: Optional[str] = None) -> Dict[str, Any]:
        """Opens a normal (non-headless) Chrome window on the host machine, with its own profile, for manual use."""
        target = url or self.current_url or "https://google.com"
        # A value starting with "-" would be read by Chrome as a command-line switch (command execution), so only
        # well-formed public http(s) URLs are accepted.
        if not target.lower().startswith(("http://", "https://")):
            return {"status": "error", "message": "Only http(s) URLs can be opened."}
        self.browser_service._validate_ssrf_for_url(target)
        chrome_binary = self.browser_service.chrome_binary

        if not chrome_binary:
            return {"status": "unavailable", "message": "Chrome binary not found on host system"}

        # Open non-headless window
        user_data_dir = self.storage_dir / "user_profile"
        user_data_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            chrome_binary,
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            target
        ]

        # Launch in background without blocking
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        return {
            "status": "launched",
            "message": f"Interactive Google Chrome window launched for '{target}'.",
            "url": target,
            "session_id": self.session_id
        }
