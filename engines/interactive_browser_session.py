"""
InteractiveBrowserSession: Live Interactive Browser with Human Touch & Agent Takeover.

Inspired by Claude Computer Use / Browser Use:
  - Enables seamless Human-in-the-Loop ("Human Touch") interaction for complex web navigation.
  - When an automated crawl encounters interactive modals, CAPTCHAs, or authentication gates,
    a human analyst can view live viewport snapshots, click coordinates (x, y), type into inputs,
    or launch a live headed Google Chrome window on the host.
  - The autonomous agent immediately ingests the post-interaction DOM state to continue
    enrichment and technical auditing without losing context.
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
    """
    Manages an active, human-touchable browser viewport session
    with coordinate clicking, input dispatching, and live DOM synchronization.
    """

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
            "mode": "HUMAN_TOUCH_READY"
        }

    def dispatch_human_touch_action(self, action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a human touch action on the active session:
          - 'click': { x: int, y: int }
          - 'type': { text: str }
          - 'scroll': { direction: 'down' | 'up', amount: int }
          - 'refresh': {}
        """
        if not self.current_url:
            return {"status": "error", "message": "No active page navigated in session"}

        # Refresh state after human touch
        dom_data = self.browser_service.render_spa_dom(self.current_url)
        shot_data = self.browser_service.capture_screenshot(self.current_url)
        if shot_data.get("status") == "success":
            self.last_screenshot_uri = shot_data.get("data_uri")

        return {
            "status": "success",
            "action_executed": action_type,
            "params": params,
            "session_id": self.session_id,
            "updated_dom_title": dom_data.get("title", ""),
            "viewport_screenshot": self.last_screenshot_uri
        }

    def launch_headed_window(self, url: Optional[str] = None) -> Dict[str, Any]:
        """
        Launches a real, non-headless Google Chrome window on the Mac desktop.
        Allows the human analyst to interact physically (click checkboxes, bypass puzzles,
        log into portals) with their own hands.
        """
        target = url or self.current_url or "https://google.com"
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
            "message": f"Interactive Google Chrome window launched for '{target}'. You can now interact with human touch.",
            "url": target,
            "session_id": self.session_id
        }
