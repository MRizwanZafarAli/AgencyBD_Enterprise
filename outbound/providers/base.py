"""
Base abstractions for Outbound Sending Providers.
Enforces a uniform interface for all outbound email channels
(SMTP, Google Workspace, Microsoft Graph, Smartlead, Instantly).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

@dataclass
class OutboundMessage:
    to_email: str
    from_email: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    reply_to: Optional[str] = None
    org_id: str = "default_org"
    campaign_id: Optional[str] = None
    lead_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SendResult:
    success: bool
    provider_message_id: Optional[str] = None
    provider: str = "unknown"
    status: str = "pending"  # sent, failed, queued, not_configured
    error: Optional[str] = None
    status_code: Optional[int] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

class SendProvider(ABC):
    """Abstract interface for all outbound dispatch providers."""

    @abstractmethod
    def send(self, message: OutboundMessage) -> SendResult:
        """Dispatches an outbound message or returns an honest diagnostic result."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Checks provider connectivity, authentication, and dispatch readiness."""
        pass
