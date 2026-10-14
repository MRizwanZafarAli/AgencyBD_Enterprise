"""
Unit tests for Next-Gen GTM capabilities (RB2B deanonymizer, Retell AI voice calls, Tavus video generator).
"""

import pytest
from database.db import init_db
from database.models import LeadRepository, ContactRepository
from agents.future_gtm_agent import FutureGTMAgent

def test_voice_call_pathway():
    init_db()
    lead = LeadRepository.create_or_get_lead(
        company_name="Vanguard Telemetry",
        domain="vanguardtelemetry.io",
        source_channel="venture_database"
    )
    ContactRepository.add_decision_maker(
        lead_id=lead["id"],
        first_name="Alexander",
        last_name="Vance",
        title="CTO",
        email="alexander.vance@vanguardtelemetry.io"
    )
    agent = FutureGTMAgent()
    call = agent.generate_voice_call_pathway(lead["id"])
    assert "conversational_tree" in call
    assert "step_1_opener" in call["conversational_tree"]
    assert "Alexander" in call["conversational_tree"]["step_1_opener"]

def test_video_pitch_spec():
    init_db()
    lead = LeadRepository.create_or_get_lead(
        company_name="Apex Commerce Labs",
        domain="apexcommercelabs.dev",
        source_channel="google_maps"
    )
    agent = FutureGTMAgent()
    video = agent.generate_video_pitch_spec(lead["id"])
    assert video["provider"] == "Tavus Dynamic Video Engine v3"
    assert "spoken_script" in video
    assert "apexcommercelabs.dev" in video["spoken_script"]
