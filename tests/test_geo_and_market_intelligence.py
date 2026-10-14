"""
Unit and Integration Tests for Global Geo Database & AI Market Intelligence Agent.
"""

import pytest
from data.geo_database import GeoDatabase
from agents.market_intelligence_agent import MarketIntelligenceAgent

def test_geo_database_hierarchies():
    countries = GeoDatabase.get_all_countries()
    assert "United States" in countries
    assert "United Kingdom" in countries
    assert "Germany" in countries
    assert "United Arab Emirates" in countries
    assert "Singapore" in countries

    # Test states in US
    us_states = GeoDatabase.get_states_provinces("United States")
    assert "California" in us_states
    assert "Texas" in us_states
    assert "New York" in us_states

    # Test cities in California
    ca_cities = GeoDatabase.get_cities("United States", "California")
    assert "San Francisco" in ca_cities
    assert "Palo Alto" in ca_cities

    # Test tech tags
    tags = GeoDatabase.get_tech_tags("United States", "California")
    assert "AI/ML" in tags

def test_geo_global_city_search():
    results = GeoDatabase.search_cities_globally("London")
    assert len(results) > 0
    assert any(r["city"] == "London" and r["country"] == "United Kingdom" for r in results)

    dubai_results = GeoDatabase.search_cities_globally("Dubai")
    assert len(dubai_results) > 0
    assert any(r["country"] == "United Arab Emirates" for r in dubai_results)

def test_market_intelligence_ai_demand_analysis():
    agent = MarketIntelligenceAgent()
    
    # Project 1: AI Agent & RAG platform
    res = agent.analyze_demand(
        project_demand="We build autonomous multi-agent systems and enterprise RAG on LangChain & FastAPI",
        ticket_size="$50k-$150k"
    )

    assert res["matched_research_vector"] == "ai_agent_rag"
    assert res["primary_target"]["country"] == "United States"
    assert res["primary_target"]["city"] in ["San Francisco", "Palo Alto", "San Jose"]
    assert res["primary_target"]["opportunity_score"] >= 90
    assert "google_maps_query" in res["operational_search_queries"]
    assert "linkedin_xray_boolean" in res["operational_search_queries"]
    assert len(res["regulatory_attack_angles"]) > 0

def test_market_intelligence_fintech_demand_analysis():
    agent = MarketIntelligenceAgent()
    
    # Project 2: FinTech & Payment Architecture
    res = agent.analyze_demand(
        project_demand="High-frequency payment processing API and PCI-DSS compliance auditing",
        ticket_size="$75k-$200k"
    )

    assert res["matched_research_vector"] == "fintech_banking"
    assert res["primary_target"]["city"] == "New York City"
    assert "Fintech" in res["operational_search_queries"]["google_maps_query"]
