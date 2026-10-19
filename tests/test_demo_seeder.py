import pytest
from engines.demo_seeder import DemoSeeder

def test_demo_seeder_direct():
    result = DemoSeeder.seed_demo_data(org_id="org_test_seeder")
    assert result["status"] == "success"
    assert result["proposals_won"] == 3
    assert result["pipeline_won_usd"] == 142500.0
    assert result["meetings_booked"] == 4
    assert result["evidence_records"] == 6

def test_demo_seeder_api_endpoint(client, make_key):
    # Test client using admin token header
    headers = make_key("growth_lead", org_id="org_test_seeder")
    response = client.post("/api/system/seed_demo_pipeline", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["pipeline_won_usd"] == 142500.0
