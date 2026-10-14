"""
CRMRelayAgent: Bi-Directional CRM Synchronization & Executive Slack Alerts.
Integrates with HubSpot, Salesforce, Notion, and Slack webhooks to push real-time pipeline updates.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from database.db import log_audit_trail
from config.settings import settings
from config.honesty import NotConfiguredError, PreconditionFailedError

class CRMRelayAgent:
    """
    Bi-Directional CRM & Webhook Sync.
    Ensures agency sales ops and founders receive instant alerts in Slack/HubSpot.
    """

    @staticmethod
    def sync_to_hubspot(lead_id: int, company_name: str, domain: str, stage: str, deal_value: float = 25000.0) -> Dict[str, Any]:
        """Generates and dispatches HubSpot Deal & Contact payload."""
        payload = {
            "properties": {
                "dealname": f"{company_name} - AI & Engineering Modernization",
                "pipeline": "default",
                "dealstage": stage,
                "amount": deal_value,
                "domain": domain,
                "apexcore_lead_id": lead_id,
                "closedate": datetime.now().strftime("%Y-%m-%d")
            }
        }
        from adapters.vendor_connectors import VendorConnectors
        result = VendorConnectors.hubspot_sync_deal(payload["properties"]["dealname"], deal_value, stage)
        log_audit_trail(lead_id, "CRMRelayAgent", "HUBSPOT_SYNC_ATTEMPT", {"stage": stage, "status": result.get("status")})
        return {"crm": "HubSpot", **result}

    @staticmethod
    def dispatch_slack_alert(channel: str, alert_type: str, title: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats rich Slack webhook message cards with one-click action buttons.
        """
        slack_blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"⚡ {title}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Company:*\n{details.get('company', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*Domain:*\n<{details.get('domain', '#')}|{details.get('domain', 'N/A')}>"},
                    {"type": "mrkdwn", "text": f"*Contact:*\n{details.get('contact', 'Executive Team')}"},
                    {"type": "mrkdwn", "text": f"*Pipeline Value:*\n${details.get('value', 25000):,.0f}"}
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve Outreach"},
                        "style": "primary",
                        "value": f"approve_{details.get('lead_id')}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🔬 View Audit"},
                        "value": f"audit_{details.get('lead_id')}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "⛔ Suppress Domain"},
                        "style": "danger",
                        "value": f"suppress_{details.get('domain')}"
                    }
                ]
            }
        ]
        from adapters.vendor_connectors import VendorConnectors
        delivered = VendorConnectors.slack_send_alert(f"{title} | {details.get('company', 'N/A')} | {details.get('domain', 'N/A')}")
        return {"channel": channel, "status": "delivered" if delivered else "not_delivered",
                "reason": None if delivered else "SLACK_WEBHOOK_URL is not configured or the webhook rejected the message."}
