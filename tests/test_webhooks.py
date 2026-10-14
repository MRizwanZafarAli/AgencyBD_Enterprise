"""
Unit and Integration Tests for Inbound Webhooks & Thread Stripping.
"""

import pytest
import time
from security.webhook_verifier import WebhookSecurity, WEBHOOK_SECRET
from agents.inbound_webhook_router import InboundWebhookRouter
from database.db import init_db, is_entity_suppressed

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_webhook_hmac_signature_verification():
    payload = b'{"event":"reply_received","sender":"lead@targetcorp.com","text":"sounds good"}'
    valid_sig = WebhookSecurity.sign_payload(payload, WEBHOOK_SECRET)

    # Valid signature
    assert WebhookSecurity.verify_signature(payload, valid_sig, WEBHOOK_SECRET) is True
    # Valid signature with prefix
    assert WebhookSecurity.verify_signature(payload, f"sha256={valid_sig}", WEBHOOK_SECRET) is True
    # Forged signature
    assert WebhookSecurity.verify_signature(payload, "bad_signature_123", WEBHOOK_SECRET) is False

def test_webhook_replay_attack_protection():
    payload = b'{"event":"test"}'
    current_time = int(time.time())
    sig = WebhookSecurity.sign_payload(payload, WEBHOOK_SECRET, timestamp=current_time)

    # Fresh timestamp within 300s tolerance
    assert WebhookSecurity.verify_signature(payload, sig, WEBHOOK_SECRET, timestamp=current_time) is True

    # Replay attack: even a correctly signed message is rejected once it is older than the window
    stale_time = current_time - 600
    stale_sig = WebhookSecurity.sign_payload(payload, WEBHOOK_SECRET, timestamp=stale_time)
    assert WebhookSecurity.verify_signature(payload, stale_sig, WEBHOOK_SECRET, timestamp=stale_time) is False

    # The timestamp is bound into the signature: swapping it for a fresh one must fail
    assert WebhookSecurity.verify_signature(payload, stale_sig, WEBHOOK_SECRET, timestamp=current_time) is False

def test_email_thread_stripper():
    raw_reply = """Hi Alex,
Yes, we are interested in discussing the Next.js migration. Are you free Thursday at 2pm?

On Mon, Oct 12, 2026 at 10:14 AM Alex <alex@apexcore.ai> wrote:
> Hi Mark,
> Noticed your current setup on TargetCorp is running an older stack...
> Would you be open to reviewing the teardown?
-- 
Mark Spencer
VP Engineering | TargetCorp
"""
    clean = InboundWebhookRouter.strip_email_quotes(raw_reply)
    assert "Yes, we are interested in discussing the Next.js migration." in clean
    assert "On Mon, Oct 12" not in clean
    assert "Noticed your current setup" not in clean
    assert "> Hi Mark" not in clean

def test_esp_payload_normalization_resend():
    router = InboundWebhookRouter()
    resend_payload = {
        "id": "msg_resend_999",
        "data": {
            "from": "John Doe <johndoe@acmecorp.com>",
            "to": ["alex@apexcore.ai"],
            "subject": "Re: Site Speed Teardown",
            "text": "Send over the report, let's talk next week."
        }
    }
    normalized = router.normalize_esp_payload(resend_payload)
    assert normalized["provider"] == "resend"
    assert normalized["sender_email"] == "johndoe@acmecorp.com"
    assert "Send over the report" in normalized["clean_body"]

def test_inbound_opt_out_auto_suppression():
    router = InboundWebhookRouter()
    unsubscribe_payload = {
        "sender": "unsub_user@dontspamme.com",
        "subject": "Unsubscribe",
        "body": "Please remove me from your email list immediately."
    }
    res = router.process_inbound_reply(unsubscribe_payload)
    assert res["status"] == "processed"
    assert res["sentiment"] == "negative"
    assert res["objection_category"] == "not_interested"
    assert res["auto_suppressed"] is True

    # Verify entity is now blocked in the cryptographic suppression vault
    assert is_entity_suppressed("unsub_user@dontspamme.com") is True
    assert is_entity_suppressed("dontspamme.com") is True
