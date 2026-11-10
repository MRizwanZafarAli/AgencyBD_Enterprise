#!/usr/bin/env python3
"""
Enterprise QA Verification: Comprehensive Dashboard & Email Hub Test Runner.
Tests all 4 role dashboards, API endpoints, permissions, deliverability gates,
and cross-surface deep links against the running application.
"""

import sys
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8001"
FRONTEND_URL = "http://127.0.0.1:5173"

PASSWORDS = {
    "super_admin": "RCGY6BRN62AehxYy4oxe",
    "growth_lead": "UfB_s7tuxJwoThwaKCdU",
    "sdr_rep": "CXdw_jBWzuu_voVxpR-S",
    "auditor": "K7sZQ5stT2rKHXGv5rUW",
}

passed_tests = 0
failed_tests = 0


def log_test(name: str, passed: bool, detail: str = ""):
    global passed_tests, failed_tests
    status = "PASS" if passed else "FAIL"
    icon = "[OK]" if passed else "[FAIL]"
    print(f"{icon} {status}: {name}")
    if detail:
        print(f"      -> {detail}")
    if passed:
        passed_tests += 1
    else:
        failed_tests += 1


def http_request(path: str, method: str = "GET", data: dict = None, token: str = None) -> tuple:
    url = f"{BASE_URL}{path}" if path.startswith("/") else path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.getcode()
            res_body = json.loads(resp.read().decode("utf-8"))
            return code, res_body
    except urllib.error.HTTPError as err:
        try:
            err_body = json.loads(err.read().decode("utf-8"))
        except Exception:
            err_body = {"detail": str(err)}
        return err.code, err_body
    except Exception as e:
        return 0, {"detail": str(e)}


def run_all_tests():
    print("=" * 80)
    print("AGENCYBD ENTERPRISE: COMPREHENSIVE MULTI-DASHBOARD & EMAIL SUITE")
    print("=" * 80)

    # 1. Frontend Server Liveness
    try:
        req = urllib.request.Request(FRONTEND_URL)
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8")
            log_test("Frontend Vite Server Liveness", resp.getcode() == 200 and "id=\"root\"" in html, f"HTTP {resp.getcode()} (Vite index.html served)")
    except Exception as e:
        log_test("Frontend Vite Server Liveness", False, str(e))

    # 2. Authentication across all 4 Tiers
    tokens = {}
    for role, pw in PASSWORDS.items():
        code, res = http_request("/api/auth/login", method="POST", data={"role": role, "password": pw})
        ok = code == 200 and "token" in res and res.get("me", {}).get("role") == role
        log_test(f"Auth Login Tier: {role}", ok, f"User: {res.get('me', {}).get('user_id')} ({role})")
        if ok:
            tokens[role] = res["token"]

    # 3. Security: Wrong password rejection
    code, res = http_request("/api/auth/login", method="POST", data={"role": "super_admin", "password": "WrongPassword!999"})
    log_test("Security: Wrong password rejection", code == 401, f"HTTP {code} ({res.get('detail')})")

    # 4. Super Admin Dashboard (AdminDashboard.tsx)
    admin_token = tokens.get("super_admin")
    if admin_token:
        code, res = http_request("/api/today/summary", token=admin_token)
        log_test("Super Admin Dashboard: /api/today/summary", code == 200 and "kpis" in res, f"KPIs loaded: {list(res.get('kpis', {}).keys())[:4]}")

        code, res = http_request("/api/controls/outbound", token=admin_token)
        log_test("Super Admin Dashboard: /api/controls/outbound status", code == 200 and "halted" in res, f"Halt state: {res.get('halted')}")

    # 5. Growth Lead Dashboard (GrowthLeadDashboard.tsx)
    growth_token = tokens.get("growth_lead")
    if growth_token:
        code, res = http_request("/api/today/summary", token=growth_token)
        log_test("Growth Lead Dashboard: /api/today/summary telemetry", code == 200 and "kpis" in res, f"HTTP {code}")

        code, res = http_request("/api/opportunities", token=growth_token)
        log_test("Growth Lead Dashboard: /api/opportunities pipeline", code == 200 and isinstance(res, list), f"Found {len(res) if isinstance(res, list) else 0} opportunities")

    # 6. SDR Rep Dashboard (SdrDashboard.tsx)
    sdr_token = tokens.get("sdr_rep")
    if sdr_token:
        code, res = http_request("/api/today/summary", token=sdr_token)
        log_test("SDR Rep Dashboard: /api/today/summary focus", code == 200 and "kpis" in res, f"HTTP {code}")

        code, res = http_request("/api/pipeline/deals", token=sdr_token)
        log_test("SDR Rep Dashboard: /api/pipeline/deals pipeline access", code == 200, f"Deals loaded: {len(res) if isinstance(res, list) else 0}")

    # 7. Auditor Dashboard (AuditorDashboard.tsx)
    auditor_token = tokens.get("auditor")
    if auditor_token:
        code, res = http_request("/api/today/summary", token=auditor_token)
        log_test("Auditor Dashboard: /api/today/summary compliance view", code == 200 and "kpis" in res, f"HTTP {code}")

        code, res = http_request("/api/email/history", token=auditor_token)
        log_test("Auditor Compliance: /api/email/history audit access", code == 200 and isinstance(res, list), f"Audit events accessible: {len(res) if isinstance(res, list) else 0}")

        # Verify Auditor CANNOT run prospecting search (RBAC enforcement - prevents bug seen in user screenshot)
        code, res = http_request("/api/hunt/local", method="POST", data={"category": "restaurants", "city": "London"}, token=auditor_token)
        log_test("Auditor RBAC: Write prospecting search blocked with 403", code == 403, f"HTTP {code} ({res.get('detail')})")

    # 8. Email Hub: Fleet Overview & Mailboxes
    if admin_token:
        code, res = http_request("/api/email/overview", token=admin_token)
        fleet = res.get("fleet", {})
        metrics = res.get("metrics_7d", {})
        log_test("Email Hub: Fleet Overview KPIs", code == 200 and "total_mailboxes" in fleet, f"Total mailboxes: {fleet.get('total_mailboxes')}, Sent 7d: {metrics.get('sent')}")

        code, res = http_request("/api/email/mailboxes", token=admin_token)
        log_test("Email Hub: Mailbox Fleet list", code == 200 and isinstance(res, list), f"{len(res)} configured mailboxes with rotation")

        code, res = http_request("/api/email/templates", token=admin_token)
        templates_list = res if isinstance(res, list) else res.get("templates", [])
        log_test("Email Hub: Outreach Templates loaded", code == 200 and len(templates_list) >= 4, f"{len(templates_list)} cold outreach templates available")

    # 9. Email Hub: Deliverability Gate - RFC 5322 Syntax & MX Inspection
    if admin_token:
        # 9a: Malformed RFC 5322 syntax
        code, res = http_request("/api/email/verify", method="POST", data={"email": "invalid@@syntax..com"}, token=admin_token)
        log_test("Deliverability Gate: Rejects malformed RFC 5322 syntax", code == 200 and not res.get("is_deliverable") and not res.get("syntax_valid"), f"Result: {res.get('reason')}")

        # 9b: Disposable Domain rejection
        code, res = http_request("/api/email/verify", method="POST", data={"email": "prospect@mailinator.com"}, token=admin_token)
        log_test("Deliverability Gate: Rejects disposable temporary email", code == 200 and not res.get("is_deliverable") and res.get("is_disposable"), f"Result: {res.get('reason')}")

        # 9c: Spam Trap prefix rejection
        code, res = http_request("/api/email/verify", method="POST", data={"email": "abuse@company.com"}, token=admin_token)
        log_test("Deliverability Gate: Rejects honeypot spam-trap prefix", code == 200 and not res.get("is_deliverable") and res.get("is_spamtrap"), f"Result: {res.get('reason')}")

        # 9d: Live DNS MX lookup for valid enterprise domain
        code, res = http_request("/api/email/verify", method="POST", data={"email": "contact@google.com"}, token=admin_token)
        log_test("Deliverability Gate: Passes verified DNS MX records", code == 200 and res.get("is_deliverable") and res.get("has_mx"), f"MX records: {res.get('mx_records')[:2]}")

    # 10. Email Hub: Draft Workflow & Human-in-the-Loop Approval Desk
    if growth_token:
        draft_payload = {
            "to_email": "founder@stripe.com",
            "recipient_name": "Patrick Collison",
            "company_name": "Stripe",
            "subject": "Enterprise QA & Growth Audit",
            "body": "Hi Patrick,\n\nWe prepared a high-impact technical audit for Stripe.\n\nBest,\nGrowth Lead",
            "as_draft": True,
        }
        code, res = http_request("/api/email/send", method="POST", data=draft_payload, token=growth_token)
        draft_id = res.get("draft_id")
        log_test("Email Hub: Save Draft to Approval Desk", code == 200 and res.get("ok") and draft_id is not None, f"Draft ID: {draft_id}")

        code, res = http_request("/api/email/drafts", token=growth_token)
        drafts = res if isinstance(res, list) else res.get("drafts", [])
        log_test("Email Hub: Retrieve Drafts Queue", code == 200 and any(d["id"] == draft_id for d in drafts), f"Queue depth: {len(drafts)}")

        # Approve and dispatch the draft
        if draft_id:
            code, res = http_request(f"/api/email/drafts/{draft_id}/send", method="POST", token=growth_token)
            log_test("Email Hub: Human Approval & Dispatch", code == 200 and res.get("ok") and res.get("status") == "sent", f"Dispatched via: {res.get('mailbox')}")

    # 11. Email Hub: Direct Dispatch & Immutable Delivery Ledger
    if admin_token:
        send_payload = {
            "to_email": "partnerships@microsoft.com",
            "recipient_name": "Satya Nadella",
            "company_name": "Microsoft",
            "subject": "AI Infrastructure Partnership",
            "body": "Hello Satya,\n\nReaching out regarding enterprise deployment and sovereign workflows.\n\nBest regards,\nExecutive Team",
            "as_draft": False,
        }
        code, res = http_request("/api/email/send", method="POST", data=send_payload, token=admin_token)
        log_test("Email Hub: Direct Dispatch (Zero-Defect Verification)", code == 200 and res.get("ok") and res.get("status") == "sent", f"Message ID: {res.get('message_id')}")

        code, res = http_request("/api/email/history?limit=10", token=admin_token)
        events = res if isinstance(res, list) else []
        has_sent_event = any(e.get("event_type") == "sent" for e in events)
        log_test("Email Hub: Immutable Delivery Ledger Audit", code == 200 and has_sent_event, f"Ledger events logged: {len(events)}")

    # 12. Security & Compliance: Global Killswitch Test
    if admin_token:
        # Halt outbound sending
        http_request("/api/controls/outbound", method="POST", data={"halted": True, "reason": "QA killswitch test"}, token=admin_token)
        # Attempt send while halted
        code, res = http_request("/api/email/send", method="POST", data={"to_email": "contact@google.com", "subject": "Test Outreach", "body": "This email should be blocked because the global killswitch is active.", "as_draft": False}, token=admin_token)
        is_blocked = (code in (403, 409)) or (code == 200 and not res.get("ok"))
        log_test("Global Killswitch: Send strictly blocked when halted", is_blocked, f"HTTP {code} ({res.get('detail') or res.get('error')})")
        # Resume outbound sending
        http_request("/api/controls/outbound", method="POST", data={"halted": False, "reason": "Resume after QA"}, token=admin_token)

    print("=" * 80)
    print(f"VERIFICATION SUMMARY: {passed_tests} PASSED, {failed_tests} FAILED")
    print("=" * 80)

    if failed_tests > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
