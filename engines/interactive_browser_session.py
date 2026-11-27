"""
InteractiveBrowserSession: Sovereign Dual-Mode Browser Controller.
Manages headless DOM rendering, live screenshot streaming for the slide-out sidepanel,
native headed Chrome window launch for human-in-the-loop intervention, and cookie state persistence.
"""

import base64
import json
import logging
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("InteractiveBrowserSession")

from engines.native_browser_service import NativeBrowserService
from net.fetcher import _check_ip, SafeFetcher, SSRFSecurityError
from net.process_supervisor import ProcessSupervisor
from net.validate import clean_domain
from database.db import get_db


class InteractiveBrowserSession:
    """A per-user or per-domain interactive session manager with live view, headed launcher, and auto-clearance radar."""

    CHALLENGE_TITLE_PATTERNS = [
        "just a moment...",
        "attention required! | cloudflare",
        "cloudflare",
        "turnstile",
        "ddos-guard",
        "security check",
        "verify you are human",
        "recaptcha",
        "hcaptcha",
        "perimeterx",
        "datadome",
        "bot detection",
    ]

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
        self.challenge_count: int = 0
        self.status: str = "idle"  # idle | challenge_blocked | cleared | completed | re_challenged
        self.cdp_port: int = 9222 + (abs(hash(session_id)) % 300)
        self.headed_process: Optional[subprocess.Popen] = None

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

        if dom_data.get("status") == "unreachable":
            self.status = "unreachable"
            return {
                "status": "unreachable",
                "session_id": self.session_id,
                "current_url": self.current_url,
                "current_domain": self.current_domain,
                "title": dom_data.get("title", clean_host),
                "error": dom_data.get("error", "Site could not be reached."),
                "detected_stack": [],
                "emails": [],
                "phones": [],
                "viewport_screenshot": None,
                "challenge_detected": False,
                "challenge_type": None,
                "mode": "viewer",
            }

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
            f"--remote-debugging-port={self.cdp_port}",
            "--no-first-run",
            "--no-default-browser-check",
            target,
        ]

        # Launch in background without blocking
        self.headed_process = subprocess.Popen(
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
            "cdp_port": self.cdp_port,
        }

    def check_live_clearance(self, target_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Actively checks whether an anti-bot challenge or login gate has been cleared.
        Uses live CDP tab inspection if headed Chrome is running; falls back to sovereign HTTP probe.
        """
        url = target_url or self.current_url
        if not url:
            return {"cleared": False, "status": "no_target", "message": "No target URL set"}
        clean_host = clean_domain(url)

        # 1. First probe via live CDP if headed window is active
        cdp_active = False
        cdp_cleared = False
        cdp_title = ""
        cdp_tab_url = ""
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.cdp_port}/json/list")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                tabs = json.loads(resp.read().decode("utf-8"))
                cdp_active = True
                for tab in tabs:
                    t_url = tab.get("url", "")
                    title = tab.get("title", "")
                    if clean_host in t_url or t_url.startswith("http"):
                        cdp_tab_url = t_url
                        cdp_title = title
                        title_lower = title.lower()
                        is_challenge_title = any(p in title_lower for p in self.CHALLENGE_TITLE_PATTERNS)
                        if not is_challenge_title and len(title) > 0 and "chrome://" not in t_url:
                            cdp_cleared = True
                            break
        except Exception:
            cdp_active = False

        if cdp_active and cdp_cleared:
            return {
                "cleared": True,
                "method": "cdp_telemetry",
                "session_id": self.session_id,
                "current_title": cdp_title,
                "current_url": cdp_tab_url or url,
                "domain": clean_host,
                "challenge_count": self.challenge_count,
                "message": "Challenge clearance confirmed via native CDP tab telemetry.",
            }

        # 2. Sovereign probe via SafeFetcher & Virtual DOM
        from engines.universal_scraper import universal_scraper
        try:
            fetch_res = SafeFetcher.safe_fetch(url, timeout=5)
            has_ch, ch_type = universal_scraper.detect_challenges(fetch_res.text)
            if not has_ch and len(fetch_res.text) > 250:
                return {
                    "cleared": True,
                    "method": "sovereign_http_probe",
                    "session_id": self.session_id,
                    "current_title": clean_host,
                    "current_url": url,
                    "domain": clean_host,
                    "challenge_count": self.challenge_count,
                    "message": "Target page resolved clean HTML without bot challenge signatures.",
                }
            else:
                return {
                    "cleared": False,
                    "method": "sovereign_http_probe",
                    "session_id": self.session_id,
                    "challenge_type": ch_type or self.challenge_type or "bot_barrier",
                    "domain": clean_host,
                    "challenge_count": self.challenge_count,
                    "message": f"Barrier still present: {ch_type or self.challenge_type}",
                }
        except Exception as exc:
            return {
                "cleared": False,
                "method": "error_fallback",
                "session_id": self.session_id,
                "error": str(exc),
                "domain": clean_host,
                "challenge_count": self.challenge_count,
            }

    def auto_resume_and_scrape(self, target_url: Optional[str] = None, org_id: str = "org_default") -> Dict[str, Any]:
        """
        Executes autonomous resume and scraping once clearance is confirmed.
        If a subsequent challenge is encountered on pagination/navigation, gracefully enters re-challenge state.
        """
        url = target_url or self.current_url
        if not url:
            return {"status": "error", "message": "No target URL available to scrape"}
        clean_host = clean_domain(url)

        from engines.universal_scraper import universal_scraper
        res = universal_scraper.scrape_url(url, org_id=org_id)

        if not res.challenge_detected:
            # Successfully cleared and scraped
            self.challenge_detected = False
            self.challenge_type = None
            self.status = "completed"
            self.save_session_state(clean_host, operator_id="auto_clearance_radar", org_id=org_id)

            try:
                from core.hooks import event_bus, HOOK_INTERVENTION_RESOLVED
                event_bus.emit(HOOK_INTERVENTION_RESOLVED, {
                    "domain": clean_host,
                    "url": url,
                    "session_id": self.session_id,
                    "org_id": org_id,
                    "challenge_count": self.challenge_count,
                })
            except Exception:
                pass

            return {
                "status": "completed",
                "re_challenged": False,
                "session_id": self.session_id,
                "domain": clean_host,
                "result": res.model_dump(),
                "message": "Scrape completed post-clearance.",
            }
        else:
            # Re-challenge detected! (Secondary barrier encountered)
            self.challenge_detected = True
            self.challenge_type = res.challenge_type
            self.challenge_count += 1
            self.status = "challenge_blocked"

            try:
                from core.hooks import event_bus, HOOK_CHALLENGE_DETECTED
                event_bus.emit(HOOK_CHALLENGE_DETECTED, {
                    "domain": clean_host,
                    "url": url,
                    "challenge_type": res.challenge_type,
                    "challenge_count": self.challenge_count,
                    "org_id": org_id,
                })
            except Exception:
                pass

            return {
                "status": "re_challenged",
                "re_challenged": True,
                "session_id": self.session_id,
                "domain": clean_host,
                "challenge_type": res.challenge_type,
                "challenge_count": self.challenge_count,
                "message": f"Subsequent anti-bot challenge detected ({res.challenge_type}). Human clearance required.",
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
