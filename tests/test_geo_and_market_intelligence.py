"""
Unit and Integration Tests for Global Geo Database & AI Market Intelligence Agent.
"""

import pytest
from data.geo_database import GeoDatabase

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


