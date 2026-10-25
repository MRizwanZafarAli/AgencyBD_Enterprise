"""
AgencyBD MCP server: exposes read-mostly AgencyBD tools to local AI clients (Claude Desktop, Cursor) over stdio JSON-RPC 2.0.

It runs with the local user's privileges against ONE tenant (env AGENCYBD_MCP_ORG, default org_default). It has no network
listener and no authentication of its own, so never wrap it in a network service. Every tool returns real, evidence-backed
results or an honest error; responses over 10 MiB are refused rather than truncated silently.
"""

import json
import os
import sys
from typing import Any, Dict, List

from database.db import init_db

MAX_MCP_TRANSPORT_BYTES = 10 * 1024 * 1024  # 10 MiB ceiling


class AgencyBDMcpServer:
    def __init__(self):
        init_db()
        self.org_id = os.getenv("AGENCYBD_MCP_ORG", "org_default")

    def list_tools(self) -> List[Dict[str, Any]]:
        def tool(name, desc, props, required=()):
            return {"name": name, "description": desc, "inputSchema": {"type": "object", "properties": props, "required": list(required)}}
        s = lambda d: {"type": "string", "description": d}
        return [
            tool("agencybd_audit_website", "Runs the Website Doctor on a domain (security headers, TLS, SEO, GEO, accessibility, email DNS). Returns measured findings only.",
                 {"domain": s("Domain to audit, e.g. example.com")}, ["domain"]),
            tool("agencybd_hunt_local_businesses", "Finds local businesses in a city and ranks how winnable they are (no website, broken site, etc.). Uses OpenStreetMap unless a Google Places key is set.",
                 {"category": s("Business type, e.g. dentist"), "city": s("City, e.g. Leeds, UK"), "limit": {"type": "integer", "default": 10}}, ["category", "city"]),
            tool("agencybd_compare_sites", "Audits two sites with the same checks and lists measured differences.",
                 {"target_domain": s("Prospect domain"), "competitor_domain": s("Competitor domain")}, ["target_domain", "competitor_domain"]),
            tool("agencybd_open_work_items", "Lists open work items (things a person needs to do) for the workspace.", {}),
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "agencybd_audit_website":
            from auditors.engine import WebsiteDoctorEngine
            return WebsiteDoctorEngine.run_audit(arguments.get("domain", ""), org_id=self.org_id)
        if name == "agencybd_hunt_local_businesses":
            from intel import local_hunt
            return local_hunt.hunt(arguments.get("category", ""), arguments.get("city", ""), min(int(arguments.get("limit", 10)), 40))
        if name == "agencybd_compare_sites":
            from intel.comparison import compare_domains
            return compare_domains(arguments.get("target_domain", ""), arguments.get("competitor_domain", ""), self.org_id)
        if name == "agencybd_open_work_items":
            from workflows.inbox import WorkItemRepository
            return {"items": WorkItemRepository.list_open(self.org_id)}
        return {"status": "error", "error": f"Unknown tool: {name}"}

    def handle_json_rpc(self, request_str: str) -> str:
        """Processes a single JSON-RPC message and applies the 10 MiB budget guard."""
        try:
            req = json.loads(request_str)
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            })

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "tools/list":
            result = {"tools": self.list_tools()}
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                result = self.call_tool(tool_name, tool_args)
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
        else:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            })

        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        }

        serialized = json.dumps(response)
        
        if len(serialized.encode("utf-8")) > MAX_MCP_TRANSPORT_BYTES:
            response["result"] = {"status": "resource_constraint",
                                  "message": "The result exceeded the 10 MiB transport limit and was not returned. Narrow the request."}
            serialized = json.dumps(response)

        return serialized


def run_stdio_server():
    """Stdio entrypoint loop for Claude Desktop / Cursor MCP connection."""
    server = AgencyBDMcpServer()
    for line in sys.stdin:
        line_clean = line.strip()
        if not line_clean:
            continue
        resp_str = server.handle_json_rpc(line_clean)
        sys.stdout.write(resp_str + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    run_stdio_server()
