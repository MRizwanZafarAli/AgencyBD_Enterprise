"""
Unit tests for LinkedInAgent and SiteCrawlerAgent.
"""

import pytest
from agents.linkedin_agent import LinkedInAgent
from agents.site_crawler_agent import SiteCrawlerAgent

def test_linkedin_sequence_generation():
    agent = LinkedInAgent()
    seq = agent.generate_linkedin_sequence(
        first_name="Alexander",
        company_name="Vanguard Logistics",
        trigger_hook="Saw your team posted an open Staff ML Engineer role for 45 days"
    )
    assert "connection_request_note" in seq
    assert seq["connection_note_char_count"] <= 300
    assert "Alexander" in seq["connection_request_note"]
    assert "post_acceptance_message" in seq
    assert "followup_value_message" in seq
