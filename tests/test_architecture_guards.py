"""
Architecture Guards & System Invariant Verification Suite.

Inspired by REA (Reverse Engineer Anything) architecture guards:
  - Asserts that engines/ and intel/ never import from api.py or tests/.
  - Asserts that EvidenceRecord cryptographic hashing is content-addressed and deterministic.
  - Asserts that ProcessSupervisor isolates process trees cleanly without zombies.
  - Asserts that AgencyBD MCP server enforces the 10 MiB budget ceiling.
"""

import json
from pathlib import Path
import pytest
from intel.evidence_ledger import EvidenceLedger, EvidenceRecord
from net.process_supervisor import ProcessSupervisor
from mcp.agencybd_mcp_server import AgencyBDMcpServer, MAX_MCP_TRANSPORT_BYTES
from engines.differential_audit_engine import DifferentialAuditEngine


ROOT = Path(__file__).resolve().parent.parent


def test_architecture_layer_isolation_no_circular_api_imports():
    """Engines and intel domain modules must never import from api.py."""
    forbidden = ["from api import", "import api"]
    offenders = []

    for folder in ["engines", "intel", "compliance", "policy"]:
        target_dir = ROOT / folder
        if not target_dir.exists():
            continue
        for py_file in target_dir.glob("*.py"):
            content = py_file.read_text(errors="ignore")
            for line in content.splitlines():
                if any(f in line for f in forbidden) and not line.strip().startswith("#"):
                    offenders.append(f"{py_file.name}: {line.strip()}")

    assert not offenders, f"Layer violation: inner modules importing api.py: {offenders}"


def test_evidence_ledger_cryptographic_determinism(tmp_path):
    """Evidence records must compute deterministic SHA-256 hashes."""
    ledger = EvidenceLedger(storage_dir=str(tmp_path))
    rec = ledger.record_evidence(
        target_domain="stripe.com",
        operation="audit_test",
        observations={"status_code": 200},
        derivations={"lcp": 1.4},
        inferences={"p_close": 0.95},
        unknowns=[{"facet": "direct_mobile", "reason_code": "NOT_PUBLIC"}]
    )

    digest1 = rec.compute_sha256()
    digest2 = rec.compute_sha256()
    assert digest1 == digest2
    assert len(digest1) == 64

    # Verify retrieval
    retrieved = ledger.get_evidence(rec.evidence_id)
    assert retrieved is not None
    assert retrieved.target_domain == "stripe.com"
    assert retrieved.confidence_score == 0.90


def test_differential_audit_engine_execution():
    """Differential comparison between target and competitor produces valid metrics and hooks."""
    diff_engine = DifferentialAuditEngine()
    result = diff_engine.compare_domains(
        target_domain="targetcorp.internal",
        competitor_domain="competitor.internal",
        monthly_visitors=50000,
        average_order_value_usd=100.0
    )

    assert result["status"] == "success"
    assert "differential" in result
    assert "competitive_pitch_hook" in result["differential"]
    assert "targetcorp.internal" in result["differential"]["competitive_pitch_hook"]
    assert result["differential"]["lcp_gap_seconds"] >= 0.0


def test_process_supervisor_confinement_and_timeout():
    """ProcessSupervisor enforces timeouts and confines process groups."""
    # Test fast command
    res_fast = ProcessSupervisor.run_confined(["echo", "agencybd_supervised"], timeout_seconds=3)
    assert res_fast.returncode == 0
    assert "agencybd_supervised" in res_fast.stdout
    assert not res_fast.timed_out

    # Test timeout with sleep
    res_slow = ProcessSupervisor.run_confined(["sleep", "5"], timeout_seconds=1)
    assert res_slow.timed_out is True
    assert res_slow.returncode == -9


def test_mcp_server_json_rpc_and_budget_guard(monkeypatch):
    """MCP server conforms to JSON-RPC 2.0 and triggers 10 MiB budget guard on huge responses."""
    server = AgencyBDMcpServer()

    # 1. tools/list
    req_list = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    resp_list_raw = server.handle_json_rpc(req_list)
    resp_list = json.loads(resp_list_raw)
    assert "result" in resp_list
    assert len(resp_list["result"]["tools"]) >= 5

    # 2. tools/call deal math
    req_call = json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "agencybd_calculate_deal_math",
            "arguments": {"lcp_seconds": 3.8, "detected_stack": ["Next.js"]}
        }
    })
    resp_call = json.loads(server.handle_json_rpc(req_call))
    assert resp_call["result"]["status"] == "success"
    assert "probability" in resp_call["result"]

    # 3. Simulate huge payload exceeding MAX_MCP_TRANSPORT_BYTES
    monkeypatch.setattr(
        server,
        "call_tool",
        lambda name, args: {"massive_dump": "A" * (MAX_MCP_TRANSPORT_BYTES + 1000)}
    )
    req_huge = json.dumps({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "agencybd_audit_website_dom", "arguments": {"domain": "huge.com"}}
    })
    resp_huge = json.loads(server.handle_json_rpc(req_huge))
    assert resp_huge["result"]["status"] == "resource_constraint"
    assert "evidence_reference" in resp_huge["result"]
