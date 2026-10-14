"""
Smartlead API Outbound Provider.
Integrates with Smartlead.ai API (or Instantly REST API) for automated sequence dispatch.
Supports sending via authenticated campaigns and accounts.
"""

import uuid
from typing import Dict, Any, Optional
import requests

from outbound.providers.base import SendProvider, OutboundMessage, SendResult
from config.settings import get_settings

class SmartleadProvider(SendProvider):
    BASE_URL = "https://server.smartlead.ai/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or getattr(settings, "smartlead_api_key", None)

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def health_check(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "provider": "smartlead",
                "status": "not_configured",
                "ready": False
            }
        try:
            resp = requests.get(
                f"{self.BASE_URL}/campaigns",
                params={"api_key": self.api_key},
                timeout=5
            )
            return {
                "provider": "smartlead",
                "status": "connected" if resp.status_code == 200 else "auth_failed",
                "ready": resp.status_code == 200,
                "status_code": resp.status_code
            }
        except Exception as e:
            return {
                "provider": "smartlead",
                "status": "unreachable",
                "ready": False,
                "error": str(e)
            }

    def send(self, message: OutboundMessage) -> SendResult:
        if not self.is_configured():
            return SendResult(
                success=False,
                provider="smartlead",
                status="not_configured",
                error="Smartlead API key is not configured."
            )

        campaign_id = message.campaign_id
        if not campaign_id:
            return SendResult(
                success=False,
                provider="smartlead",
                status="missing_campaign_id",
                error="campaign_id is required for Smartlead dispatch."
            )

        payload = {
            "lead_list": [
                {
                    "email": message.to_email,
                    "first_name": message.metadata.get("first_name", ""),
                    "last_name": message.metadata.get("last_name", ""),
                    "company_name": message.metadata.get("company_name", ""),
                    "custom_fields": {
                        "custom_subject": message.subject,
                        "custom_body": message.body_text
                    }
                }
            ]
        }

        try:
            url = f"{self.BASE_URL}/campaigns/{campaign_id}/leads"
            resp = requests.post(
                url,
                params={"api_key": self.api_key},
                json=payload,
                timeout=10
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return SendResult(
                    success=True,
                    provider="smartlead",
                    provider_message_id=str(data.get("upload_id") or uuid.uuid4().hex[:12]),
                    status="enqueued",
                    status_code=resp.status_code,
                    diagnostics=data
                )
            else:
                return SendResult(
                    success=False,
                    provider="smartlead",
                    status="failed",
                    status_code=resp.status_code,
                    error=f"Smartlead API returned status {resp.status_code}: {resp.text}"
                )
        except Exception as e:
            return SendResult(
                success=False,
                provider="smartlead",
                status="network_error",
                error=str(e)
            )
