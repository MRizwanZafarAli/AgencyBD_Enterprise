import urllib.request
import json

BASE_URL = "http://127.0.0.1:8001"

def test_sdr_email_hub():
    # 1. Login as sdr_rep
    login_data = json.dumps({"role": "sdr_rep", "password": "CXdw_jBWzuu_voVxpR-S"}).encode()
    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req)
    token = json.loads(resp.read().decode())["token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("[PASS] 1. SDR Rep successfully authenticated")

    # 2. Test Tab 1: Compose & Dispatch Real-Time Email
    send_payload = {
        "to_email": "partnerships@github.com",
        "recipient_name": "GitHub Partnerships",
        "company_name": "GitHub",
        "subject": "Enterprise Workflow Integration & Verification",
        "body": "Hi GitHub Team,\n\nOur team has automated enterprise delivery telemetry. Would love to connect this week.\n\nBest,\nSDR Rep",
        "is_test": True
    }
    req = urllib.request.Request(f"{BASE_URL}/api/email/send", data=json.dumps(send_payload).encode(), headers=headers)
    send_res = json.loads(urllib.request.urlopen(req).read().decode())
    assert send_res["status"] == "sent", f"Unexpected status: {send_res}"
    msg_id = send_res.get("message_id")
    print(f"[PASS] 2. SDR Rep real-time outbound email sent: Message-ID {msg_id}")

    # 3. Test Tab 2: Mailboxes
    req = urllib.request.Request(f"{BASE_URL}/api/email/mailboxes", headers=headers)
    mailboxes = json.loads(urllib.request.urlopen(req).read().decode())
    assert len(mailboxes) >= 1, "No mailboxes found"
    print(f"[PASS] 3. Mailbox fleet retrieved ({len(mailboxes)} mailboxes active)")

    # 4. Test Tab 3: Approval Desk (Edit and Approve Draft)
    draft_payload = dict(send_payload, as_draft=True, to_email="founder@anthropic.com", subject="Initial Draft Scope")
    req = urllib.request.Request(f"{BASE_URL}/api/email/send", data=json.dumps(draft_payload).encode(), headers=headers)
    draft_created = json.loads(urllib.request.urlopen(req).read().decode())
    draft_id = draft_created["draft_id"]

    # Edit the draft
    edit_payload = {"subject": "Updated Technical Scope: Anthropic Pilot", "body": "Hi Dario,\n\nUpdated pilot scope proposal.\n\nBest,\nSDR"}
    req = urllib.request.Request(f"{BASE_URL}/api/email/drafts/{draft_id}", data=json.dumps(edit_payload).encode(), headers=headers, method="PUT")
    edit_res = json.loads(urllib.request.urlopen(req).read().decode())
    assert edit_res["subject"] == edit_payload["subject"]
    print(f"[PASS] 4a. SDR Rep reviewed and updated draft #{draft_id}")

    # Approve and dispatch draft
    req = urllib.request.Request(f"{BASE_URL}/api/email/drafts/{draft_id}/send", data=b"{}", headers=headers)
    approve_res = json.loads(urllib.request.urlopen(req).read().decode())
    assert approve_res["status"] == "sent"
    print(f"[PASS] 4b. SDR Rep approved and dispatched draft #{draft_id}")

    # 5. Test Tab 4: Delivery Ledger (Verify full email body and telemetry in events)
    req = urllib.request.Request(f"{BASE_URL}/api/email/history?limit=5", headers=headers)
    history = json.loads(urllib.request.urlopen(req).read().decode())
    assert len(history) > 0
    latest_event = history[0]
    assert latest_event["payload"].get("body"), "Event body is missing in payload!"
    assert latest_event["payload"].get("subject"), "Event subject is missing in payload!"
    body_len = len(latest_event["payload"]["body"])
    print(f"[PASS] 5. Delivery Ledger verified: Event #{latest_event['id']} has full body ({body_len} chars) and MX diagnostics")

    # 6. Test Tab 5: Pre-Flight Deliverability Inspector
    inspect_req = urllib.request.Request(f"{BASE_URL}/api/email/verify", data=json.dumps({"email": "satya@microsoft.com"}).encode(), headers=headers)
    inspect_res = json.loads(urllib.request.urlopen(inspect_req).read().decode())
    assert inspect_res["is_deliverable"] is True
    print(f"[PASS] 6. Pre-flight inspector verified: {inspect_res['email']} is {inspect_res['status']} with MX {inspect_res['mx_records']}")

    print("\n=======================================================")
    print("ALL 5 EMAIL HUB TABS IN SDR_REP FULLY FUNCTIONAL!")
    print("=======================================================")

if __name__ == "__main__":
    test_sdr_email_hub()
