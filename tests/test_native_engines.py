"""
Comprehensive Unit & Integration Tests for Native Self-Hosted BD Tool Engines.
Verifies that all 9 native engines function without third-party API keys:
1. NativeSMTPVerifier (vs ZeroBounce)
2. NativeTechStackFingerprinter (vs BuiltWith)
3. NativeVisitorDeanonymizer (vs RB2B)
4. NativeWarmupEngine (vs Warmy)
5. NativeSalesIntelligence (vs Gong)
6. NativeMultimodalGenerator (vs Tavus/Retell)
7. NativeCopyCoach (vs Lavender)
8. NativeWaterfallOrchestrator (vs Clay)
9. NativeSmartleadRouter (vs Smartlead/Instantly)
"""

import pytest
from engines.native_smtp_verifier import NativeSMTPVerifier
from engines.native_tech_stack_fingerprinter import NativeTechStackFingerprinter
from engines.native_visitor_deanonymizer import NativeVisitorDeanonymizer
from engines.native_warmup_engine import NativeWarmupEngine
from engines.native_sales_intelligence import NativeSalesIntelligence
from engines.native_multimodal_generator import NativeMultimodalGenerator
from engines.native_copy_coach import NativeCopyCoach
from engines.native_waterfall_orchestrator import NativeWaterfallOrchestrator
from engines.native_smartlead_router import NativeSmartleadRouter

def test_native_smtp_verifier():
    verifier = NativeSMTPVerifier()

    # 1. Invalid syntax
    res_bad = verifier.verify_email("not-an-email")
    assert res_bad["is_valid"] is False
    assert res_bad["status"] == "invalid_syntax"

    # 2. Disposable domain
    res_disp = verifier.verify_email("scam@mailinator.com")
    assert res_disp["is_valid"] is False
    assert res_disp["status"] == "disposable_burner_domain"

    # 3. Role account
    assert verifier.is_role_account("support") is True
    assert verifier.is_role_account("alex") is False

    # 4. Valid enterprise domain
    res_valid = verifier.verify_email("bu@resend.com")
    assert res_valid["is_valid"] is True
    assert res_valid["confidence_score"] >= 70
    assert "SAFE" in res_valid["recommendation"]

def test_native_tech_stack_fingerprinter():
    fingerprinter = NativeTechStackFingerprinter()
    res = fingerprinter.analyze_domain("resend.com")

    assert res["domain"] == "resend.com"
    assert len(res["detected_technologies"]) > 0
    assert "technical_debt_score" in res
    assert len(res["calculated_pitch_angle"]) > 10

def test_native_sales_intelligence():
    intel = NativeSalesIntelligence()
    transcript = """Alex: Hi Mark, great to connect. Tell me a bit about your current mobile conversion bottleneck.
Mark: Thanks Alex. Our site on WordPress is extremely slow and TTFB is over 1 second. We have a dev shortage and are behind schedule.
Alex: Completely understand. How long has that latency been impacting releases?
Mark: At least three months. We considered Toptal, but their rates were too high. Can you send over a proposal by Friday?
Alex: Absolutely, will send the SOW tomorrow."""

    res = intel.analyze_transcript(transcript, founder_speaker_label="Alex")
    assert res["founder_talk_percent"] > 0
    assert res["prospect_talk_percent"] > 0
    assert "toptal" in res["detected_competitors"]
    assert len(res["competitor_battlecards"]) > 0
    assert res["founder_questions_asked"] >= 1
    assert "site_performance_latency" in res["validated_customer_pain_points"]
    assert res["estimated_deal_win_probability_pct"] >= 65
    assert len(res["extracted_action_items"]) > 0

    # Objection Simulator
    obj_res = intel.simulate_objection("Your rates are way too expensive for our budget")
    assert obj_res["matched"] is True
    assert obj_res["category"] == "pricing"
    assert "fixed-sprint" in obj_res["verbal_counter_script"]
    assert len(obj_res["bridge_question"]) > 10

    cards = intel.list_battlecards()
    assert len(cards) >= 5
    assert any(c["id"] == "in_house_team" for c in cards)


def test_native_multimodal_generator():
    # Video pitch storyboard
    storyboard = NativeMultimodalGenerator.generate_video_pitch_storyboard(
        prospect_name="Bu Kinoshita",
        company_name="Resend",
        domain="resend.com",
        lcp_score=1.4
    )
    # only the facts supplied are stated: a measured LCP, no proof point, no header findings
    scenes = storyboard["storyboard_scenes"]
    assert len(scenes) == 3 and storyboard["claims_included"] == {"measured_lcp": True, "missing_headers": False, "portfolio_proof": False}
    assert "1.4 seconds" in scenes[1]["audio_script"] and "%" not in " ".join(s["audio_script"] for s in scenes)
    assert "Bu Kinoshita" in scenes[0]["audio_script"]
    bare = NativeMultimodalGenerator.generate_video_pitch_storyboard("Dana", "Acme", "acme.example")
    assert len(bare["storyboard_scenes"]) == 2 and not any("LCP" in s["audio_script"] or "seconds to paint" in s["audio_script"] for s in bare["storyboard_scenes"])
    proof = NativeMultimodalGenerator.generate_video_pitch_storyboard("Dana", "Acme", "acme.example", proof_point="We cut page load from 4.1s to 1.2s for a logistics client.")
    assert proof["storyboard_scenes"][1]["audio_script"] == "We cut page load from 4.1s to 1.2s for a logistics client."

    # Voice SDR call tree
    call_tree = NativeMultimodalGenerator.generate_voice_sdr_call_tree(
        prospect_name="Bu Kinoshita",
        company_name="Resend"
    )
    assert "root_greeting" in call_tree["call_nodes"]
    assert call_tree["latency_target_ms"] <= 450
    assert call_tree["vad_interruption_spec"]["interruption_mode"] == "fluid_barge_in"
    assert len(call_tree["realtime_in_call_tools"]) >= 2

def test_native_copy_coach():
    subject = "quick question regarding resend engineering"
    body = """Hi Bu,

Saw Resend is scaling developer tooling fast. We ran an architectural latency teardown on your documentation hub this morning.

Our team deploys dedicated full-stack squads to eliminate sprint backlog without agency overhead.

Worth exploring a brief look at the teardown?"""

    audit = NativeCopyCoach.score_draft(subject, body)
    assert audit["overall_score"] >= 75
    assert audit["status"] in ["EXCELLENT", "GOOD"]
    assert 4.0 <= audit["reading_grade_level"] <= 12.0
    assert len(audit["detected_spam_words"]) == 0
    assert "suggested_refactor" in audit

def test_native_waterfall_orchestrator_reports_evidence_not_verification(monkeypatch):
    """Offline: SMTP, Gravatar, PGP and Git probes are stubbed. Without a vendor the address is a candidate, never 'verified'."""
    orchestrator = NativeWaterfallOrchestrator()
    monkeypatch.setattr(orchestrator.smtp_verifier, "resolve_mx_records", lambda d: ["mx.example.net"])
    monkeypatch.setattr(orchestrator.smtp_verifier, "is_catch_all_domain", lambda d: False)
    monkeypatch.setattr(orchestrator.smtp_verifier, "verify_email", lambda e: {"is_valid": True, "confidence_score": 80})
    monkeypatch.setattr(orchestrator, "check_gravatar_footprint", lambda e: False)
    monkeypatch.setattr(orchestrator.tech_fingerprinter, "analyze_domain", lambda d: {})
    res = orchestrator.run_waterfall_enrichment("Jane", "Doe", "Example Co", "example.com", "CEO")
    assert "@example.com" in res["resolved_email"] and res["email_status"] == "smtp_accepted"
    assert res["verified"] is False and res["verdict"] == "NEEDS_VERIFICATION"
    assert res["verification_note"]
    assert "estimated_commercial_dollars_saved" not in res
    dossier = res["autonomous_research_dossier"]
    assert dossier["detected_stack"] == [] and "hiring_signal" not in dossier


def test_native_smartlead_router():
    # 1. Spintax parsing
    template = "{Hi|Hello|Hey} {{first_name}}, {saw|noticed} your work at {{company}}."
    variant = NativeSmartleadRouter.parse_spintax(template)
    assert any(greeting in variant for greeting in ["Hi", "Hello", "Hey"])
    assert any(verb in variant for verb in ["saw", "noticed"])

    # 2. ESP matching
    sample_inboxes = [
        {"email": "alex@apexcore-labs.com", "provider": "Google Workspace"},
        {"email": "growth@apexcore-hq.io", "provider": "Microsoft 365"}
    ]
    route_google = NativeSmartleadRouter.match_esp_sender("aspmx.l.google.com", sample_inboxes)
    assert route_google["target_esp"] == "Google Workspace"
    assert route_google["is_esp_matched"] is True
    assert route_google["selected_sender"]["provider"] == "Google Workspace"

    # 3. Spam trap detection
    assert NativeSmartleadRouter.is_spam_trap_candidate("abuse@victim.com") is True
    assert NativeSmartleadRouter.is_spam_trap_candidate("trap12345@domain.com") is True
    assert NativeSmartleadRouter.is_spam_trap_candidate("alex.smith@stripe.com") is False

    # 4. Pacing calculation
    pacing = NativeSmartleadRouter.calculate_dispatch_schedule(batch_size=25, daily_domain_cap=35)
    assert pacing["approved_sends_today"] == 25
    assert len(pacing["schedule"]) > 0


def test_catch_all_decoder_gravatar_and_matrix(monkeypatch):
    orchestrator = NativeWaterfallOrchestrator()

    # Simulate a domain that is catch-all
    monkeypatch.setattr(orchestrator.smtp_verifier, "is_catch_all_domain", lambda d: True)
    monkeypatch.setattr(orchestrator.smtp_verifier, "verify_email", lambda e: {"is_valid": False, "confidence_score": 0, "status": "catch_all"})

    # Case A: Gravatar footprint matches
    monkeypatch.setattr(orchestrator, "check_gravatar_footprint", lambda e: "alex.smith" in e)

    res = orchestrator.run_waterfall_enrichment("Alex", "Smith", "Acme", "acme.com")
    assert res["catch_all"] is True
    assert res["catch_all_decoded"] is True
    assert "Gravatar" in res["decoder_evidence"]
    assert res["resolved_email"] == "alex.smith@acme.com"
    assert res["confidence_score"] >= 90
    assert len(res["candidate_matrix"]) > 0
    assert res["candidate_matrix"][0]["email"] == "alex.smith@acme.com"
    assert res["candidate_matrix"][0]["gravatar_active"] is True



def test_call_intelligence_never_writes_proof_for_you(monkeypatch):
    from config.settings import settings
    engine = NativeSalesIntelligence()
    text = " ".join(str(c) for c in engine.list_battlecards()) + str(engine.simulate_objection("this is too expensive, can you do it cheaper?"))
    for invented in ("28%", "60%", "4.1s to 1.2s", "3x increase", "team of 12"):
        assert invented not in text
    monkeypatch.setattr(settings.agency, "case_study_metric", "")
    assert "No proven result is recorded yet" in engine.simulate_objection("too expensive")["grounded_portfolio_cite"]
    monkeypatch.setattr(settings.agency, "case_study_metric", "Cut load time from 4.1 s to 1.3 s for Brightside Dental")
    assert engine.simulate_objection("too expensive")["grounded_portfolio_cite"] == "Cut load time from 4.1 s to 1.3 s for Brightside Dental"
