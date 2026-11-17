"""
InteractiveBrowserSession: Sovereign Dual-Mode Browser Controller.
Manages headless DOM rendering, live screenshot streaming for the slide-out sidepanel,
native headed Chrome window launch for human-in-the-loop intervention, and cookie state persistence.
"""

import base64
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from engines.native_browser_service import NativeBrowserService
from net.fetcher import _check_ip, SafeFetcher, SSRFSecurityError
from net.process_supervisor import ProcessSupervisor
from net.validate import clean_domain
from database.db import get_db


class InteractiveBrowserSession:
    """A per-user or per-domain interactive session manager with live view and headed launcher."""

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
        self.challenge_detected: bool = False
        self.challenge_type: Optional[str] = None

    def navigate(self, target: str, viewport: str = "desktop") -> Dict[str, Any]:
        """Navigates to URL, validates SSRF, renders DOM, checks for challenges, and captures live viewport."""
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

        # 3. Detect challenges
        from engines.universal_scraper import universal_scraper
        fetch_res = None
        try:
            fetch_res = SafeFetcher.safe_fetch(target_url, timeout=5)
            self.challenge_detected, self.challenge_type = universal_scraper.detect_challenges(fetch_res.text)
        except Exception:
            self.challenge_detected = False
            self.challenge_type = None

        return {
            "status": "success",
            "session_id": self.session_id,
            "current_url": self.current_url,
            "current_domain": self.current_domain,
            "title": dom_data.get("title", ""),
            "detected_stack": dom_data.get("detected_stack", []),
            "emails": dom_data.get("emails", []),
            "phones": dom_data.get("phones", []),
            "viewport_screenshot": self.last_screenshot_uri,
            "challenge_detected": self.challenge_detected,
            "challenge_type": self.challenge_type,
            "mode": "viewer",
        }

    def launch_headed_window(self, url: Optional[str] = None) -> Dict[str, Any]:
        """Opens a normal (non-headless) Chrome window on the host machine, with its own profile, for manual use."""
        target = url or self.current_url or "https://google.com"
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
            target,
        ]

        # Launch in background without blocking
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        return {
            "status": "launched",
            "message": f"Interactive Google Chrome window launched for '{target}'.",
            "url": target,
            "session_id": self.session_id,
        }

    def save_session_state(
        self,
        domain: str,
        cookies: Optional[Dict[str, Any]] = None,
        storage_state: Optional[Dict[str, Any]] = None,
        operator_id: str = "operator",
        org_id: str = "org_default",
    ) -> bool:
        """Saves authenticated cookies and session storage into browser_session_vault."""
        try:
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO browser_session_vault (
                        org_id, domain, session_cookies_enc, storage_state_json,
                        last_intervened_by, status, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
                    ON CONFLICT(org_id, domain) DO UPDATE SET
                        session_cookies_enc = excluded.session_cookies_enc,
                        storage_state_json = excluded.storage_state_json,
                        last_intervened_by = excluded.last_intervened_by,
                        status = 'active',
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        org_id,
                        domain.lower().strip(),
                        json.dumps(cookies or {}),
                        json.dumps(storage_state or {}),
                        operator_id,
                    ),
                )
                conn.commit()
            return True
        except Exception:
            return False

    def resolve_challenge(self, operator_id: str = "operator", org_id: str = "org_default") -> Dict[str, Any]:
        """Marks challenge resolved by operator and returns resumption state."""
        self.challenge_detected = False
        self.challenge_type = None
        if self.current_domain:
            self.save_session_state(self.current_domain, operator_id=operator_id, org_id=org_id)
        return {
            "status": "resolved",
            "session_id": self.session_id,
            "message": "Human intervention resolved. Resuming autonomous scraping.",
        }


# Session Manager Cache
_active_sessions: Dict[str, InteractiveBrowserSession] = {}


def get_browser_session(session_id: str = "default_session") -> InteractiveBrowserSession:
    """Retrieves or instantiates an interactive browser session."""
    if session_id not in _active_sessions:
        _active_sessions[session_id] = InteractiveBrowserSession(session_id=session_id)
    return _active_sessions[session_id]
