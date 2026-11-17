from routers.outbound import router as outbound_router
from routers.email_hub import router as email_hub_router
from routers.compliance import router as compliance_router
from routers.policy import router as policy_router
from routers.analytics import router as analytics_router
from routers.replies import router as replies_router
from routers.sequences import router as sequences_router
from routers.connectors import router as connectors_router
from routers.system import router as system_router
from routers.swarm import router as swarm_router
from routers.browser_sidepanel import router as browser_sidepanel_router

__all__ = [
    "outbound_router",
    "email_hub_router",
    "compliance_router",
    "policy_router",
    "analytics_router",
    "replies_router",
    "sequences_router",
    "connectors_router",
    "system_router",
    "swarm_router",
    "browser_sidepanel_router",
]
