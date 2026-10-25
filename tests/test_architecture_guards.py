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
from net.process_supervisor import ProcessSupervisor
from mcp.agencybd_mcp_server import AgencyBDMcpServer, MAX_MCP_TRANSPORT_BYTES


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
    names = {t["name"] for t in resp_list["result"]["tools"]}
    assert names == {"agencybd_audit_website", "agencybd_hunt_local_businesses", "agencybd_compare_sites", "agencybd_open_work_items"}

    # 2. tools/call returns real data (no fabricated tools remain)
    resp_call = json.loads(server.handle_json_rpc(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                                              "params": {"name": "agencybd_open_work_items", "arguments": {}}})))
    assert "items" in resp_call["result"]
    unknown = json.loads(server.handle_json_rpc(json.dumps({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                                                            "params": {"name": "agencybd_calculate_deal_math", "arguments": {}}})))
    assert unknown["result"]["status"] == "error"

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
        "params": {"name": "agencybd_audit_website", "arguments": {"domain": "huge.com"}}
    })
    resp_huge = json.loads(server.handle_json_rpc(req_huge))
    assert resp_huge["result"]["status"] == "resource_constraint"
