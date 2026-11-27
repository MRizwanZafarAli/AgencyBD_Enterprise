"""Channel Registry: Archetype + Native Plugin Architecture for AgencyBD Channels."""

from typing import Any, Dict, List, Optional

ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "social_outbound": {
        "label": "Social & Outbound",
        "kpis": [
            {"id": "weekly_invites_left", "label": "Weekly Invites Left"},
            {"id": "acceptance_rate", "label": "Acceptance Rate %"},
            {"id": "reply_rate", "label": "Reply Rate %"},
            {"id": "meetings_booked", "label": "Meetings Booked"},
            {"id": "ssi_score", "label": "SSI / Profile Score"},
        ],
        "quick_actions": [
            {"kind": "invite_sent", "label": "Invite Sent"},
            {"kind": "invite_accepted", "label": "Invite Accepted"},
            {"kind": "comment_left", "label": "Warm-Up Comment"},
            {"kind": "message_sent", "label": "DM / InMail Sent"},
            {"kind": "reply_received", "label": "Reply Received"},
            {"kind": "call_booked", "label": "Meeting Booked"},
        ],
    },
    "bidding_marketplace": {
        "label": "Bidding Marketplace",
        "kpis": [
            {"id": "active_bids_value", "label": "Active Bids & Value"},
            {"id": "currency_roi", "label": "Cost per Reply"},
            {"id": "view_to_reply", "label": "View-to-Reply Rate %"},
            {"id": "win_rate", "label": "Win Rate %"},
            {"id": "followups_due", "label": "Follow-ups Due"},
        ],
        "quick_actions": [
            {"kind": "proposal_sent", "label": "Proposal Sent"},
            {"kind": "proposal_viewed", "label": "Proposal Viewed"},
            {"kind": "reply_received", "label": "Client Reply"},
            {"kind": "call_booked", "label": "Interview Booked"},
        ],
    },
    "inbound_storefront": {
        "label": "Inbound Storefront",
        "kpis": [
            {"id": "active_gigs", "label": "Active Gigs / Services"},
            {"id": "ctr_pct", "label": "Impressions -> Clicks (CTR)"},
            {"id": "cvr_pct", "label": "Click -> Order (CVR)"},
            {"id": "avg_response_sla", "label": "Avg Response Time (SLA)"},
            {"id": "monthly_revenue", "label": "Storefront Revenue"},
        ],
        "quick_actions": [
            {"kind": "gig_impressions", "label": "Gig Impressions"},
            {"kind": "gig_clicks", "label": "Gig Clicks"},
            {"kind": "inquiry_received", "label": "New Inquiry"},
            {"kind": "gig_orders", "label": "Order Won"},
        ],
    },
    "vetted_network": {
        "label": "Vetted Network",
        "kpis": [
            {"id": "availability_status", "label": "Availability Status"},
            {"id": "active_matches", "label": "Active Matches"},
            {"id": "interview_to_trial", "label": "Interview-to-Trial %"},
            {"id": "trial_to_hire", "label": "Trial-to-Hire %"},
            {"id": "avg_rate", "label": "Avg Hourly Rate"},
        ],
        "quick_actions": [
            {"kind": "match_received", "label": "New Match"},
            {"kind": "call_booked", "label": "Intro Call Booked"},
            {"kind": "trial_started", "label": "2-Week Trial Started"},
            {"kind": "hire_confirmed", "label": "Engagement Won"},
        ],
    },
    "review_directory": {
        "label": "B2B Review Directory",
        "kpis": [
            {"id": "verified_reviews", "label": "Verified Reviews"},
            {"id": "avg_rating", "label": "Avg Star Rating"},
            {"id": "directory_rank", "label": "Leader Matrix Rank"},
            {"id": "inbound_inquiries", "label": "Inbound Inquiries"},
            {"id": "utm_traffic", "label": "UTM Referral Clicks"},
        ],
        "quick_actions": [
            {"kind": "review_invited", "label": "Review Invited"},
            {"kind": "review_published", "label": "Review Published"},
            {"kind": "inquiry_received", "label": "Inbound Inquiry"},
            {"kind": "call_booked", "label": "Discovery Call Booked"},
        ],
    },
    "custom": {
        "label": "Custom Channel",
        "kpis": [
            {"id": "active_bids_value", "label": "Open Pipeline"},
            {"id": "followups_due", "label": "Follow-ups Due"},
            {"id": "win_rate", "label": "Win Rate %"},
            {"id": "avg_response_sla", "label": "Avg Reply Time"},
            {"id": "routine_streak", "label": "Routine Streak"},
        ],
        "quick_actions": [
            {"kind": "proposal_sent", "label": "Outreach Sent"},
            {"kind": "reply_received", "label": "Reply Received"},
            {"kind": "call_booked", "label": "Call Booked"},
            {"kind": "order_received", "label": "Deal Won"},
        ],
    },
}

CHANNEL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "linkedin": {
        "archetype": "social_outbound",
        "category": "Social & Outbound",
        "native_currency": None,
        "sla_target_mins": 1440,
    },
    "upwork": {
        "archetype": "bidding_marketplace",
        "category": "Bidding Marketplaces",
        "native_currency": {"name": "Connects", "unit_cost_usd": 0.15, "action_kind": "connects_spent"},
        "sla_target_mins": 240,
    },
    "freelancer": {
        "archetype": "bidding_marketplace",
        "category": "Bidding Marketplaces",
        "native_currency": {"name": "Bids", "unit_cost_usd": 0.50, "action_kind": "bids_spent"},
        "sla_target_mins": 240,
    },
    "peopleperhour": {
        "archetype": "bidding_marketplace",
        "category": "Bidding Marketplaces",
        "native_currency": {"name": "Proposal Credits", "unit_cost_usd": 1.00, "action_kind": "credits_spent"},
        "sla_target_mins": 240,
    },
    "guru": {
        "archetype": "bidding_marketplace",
        "category": "Bidding Marketplaces",
        "native_currency": {"name": "Quotes", "unit_cost_usd": 0.99, "action_kind": "quotes_spent"},
        "sla_target_mins": 240,
    },
    "fiverr": {
        "archetype": "inbound_storefront",
        "category": "Inbound Storefronts",
        "native_currency": None,
        "sla_target_mins": 60,
    },
    "contra": {
        "archetype": "inbound_storefront",
        "category": "Inbound Storefronts",
        "native_currency": None,
        "sla_target_mins": 180,
    },
    "toptal": {
        "archetype": "vetted_network",
        "category": "Vetted Networks",
        "native_currency": None,
        "sla_target_mins": 240,
    },
    "clutch": {
        "archetype": "review_directory",
        "category": "B2B Directories",
        "native_currency": None,
        "sla_target_mins": 360,
    },
    "other": {
        "archetype": "custom",
        "category": "Custom",
        "native_currency": None,
        "sla_target_mins": 1440,
    },
}

ACTIVITY_LABELS: Dict[str, str] = {
    "invite_sent": "Invites Sent",
    "invite_accepted": "Invites Accepted",
    "comment_left": "Warm-Up Comments",
    "message_sent": "Messages Sent",
    "reply_received": "Replies Received",
    "profile_view": "Profile Views",
    "proposal_sent": "Proposals Sent",
    "proposal_viewed": "Proposals Viewed",
    "order_received": "Orders Received",
    "gig_impressions": "Gig Impressions",
    "gig_clicks": "Gig Clicks",
    "gig_orders": "Gig Orders",
    "inquiry_received": "Inbound Inquiries",
    "call_booked": "Calls Booked",
    "connects_spent": "Connects Spent",
    "bids_spent": "Bids Spent",
    "credits_spent": "Proposal Credits Spent",
    "quotes_spent": "Quotes Spent",
    "match_received": "Matches Received",
    "trial_started": "Trials Started",
    "hire_confirmed": "Hires Confirmed",
    "review_invited": "Reviews Invited",
    "review_published": "Reviews Published",
}


def get_channel_spec(platform_id: str, custom_archetype: Optional[str] = None) -> Dict[str, Any]:
    """Returns strict archetype, currency, KPI definitions, and clean human quick actions."""
    reg = CHANNEL_REGISTRY.get(platform_id, CHANNEL_REGISTRY["other"])
    arch_id = custom_archetype if (platform_id == "other" or platform_id not in CHANNEL_REGISTRY) and custom_archetype in ARCHETYPES else reg["archetype"]
    arch = ARCHETYPES[arch_id]
    currency = reg.get("native_currency")
    quick_actions = list(arch["quick_actions"])
    if currency and currency.get("action_kind"):
        quick_actions.append({"kind": currency["action_kind"], "label": f"{currency['name']} Spent"})
    return {
        "archetype": arch_id,
        "archetype_label": arch["label"],
        "category": reg["category"],
        "native_currency": currency,
        "sla_target_mins": reg.get("sla_target_mins", 1440),
        "kpi_definitions": arch["kpis"],
        "quick_actions": quick_actions,
    }
