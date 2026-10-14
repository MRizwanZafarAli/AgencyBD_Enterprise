"""
Password gate for the Streamlit control room.

The dashboard talks to the engine in-process (no API key involved), so it needs its own door.
  * AGENCYBD_DASHBOARD_PASSWORD set     -> login required.
  * unset in production                 -> the dashboard refuses to render.
  * unset elsewhere                     -> open, with a visible warning.
"""

import hashlib
import hmac
import os
import time

from config.env import is_production


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def require_dashboard_login(st) -> None:
    """Call once, right after st.set_page_config. Stops the script unless the viewer is authenticated."""
    expected = os.getenv("AGENCYBD_DASHBOARD_PASSWORD", "")

    if not expected:
        if is_production():
            st.error("Dashboard locked: AGENCYBD_DASHBOARD_PASSWORD is not configured.")
            st.stop()
        st.warning("Development mode: dashboard is unauthenticated. Set AGENCYBD_DASHBOARD_PASSWORD to enable login.")
        return

    if st.session_state.get("_agencybd_authed"):
        return

    st.title("ApexCore Control Room")
    entered = st.text_input("Password", type="password", key="_agencybd_pw")
    if entered:
        if hmac.compare_digest(_digest(entered), _digest(expected)):
            st.session_state["_agencybd_authed"] = True
            st.rerun()
        time.sleep(1.0)  # slow down guessing
        st.error("Incorrect password.")
    st.stop()
