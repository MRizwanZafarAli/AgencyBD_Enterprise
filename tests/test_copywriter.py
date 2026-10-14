"""
Unit tests for CopywriterAgent and spam score verification.
"""

import pytest
from database.db import init_db
from database.models import LeadRepository
from agents.tech_audit_agent import TechAuditAgent
from agents.enrichment_agent import EnrichmentAgent
from agents.copywriter_agent import CopywriterAgent
from config.deliverability import analyze_spam_friction

def test_spam_filter_detector():
    clean_subj = "Quick question regarding mobile performance"
    clean_body = "Hi Sarah, noticed your site took 4.1s to load. Mind if I send a quick teardown?"
    score, flags, rating = analyze_spam_friction(clean_subj, clean_body)
    assert score == 0.0
    assert "PRISTINE" in rating

    spam_subj = "FREE CASH GUARANTEED WINNER ACT NOW!!!"
    spam_body = "Click here to make money fast and double your income! Don't hesitate!"
    score_spam, flags_spam, rating_spam = analyze_spam_friction(spam_subj, spam_body)
    assert score_spam > 2.5
    assert "CRITICAL" in rating_spam
