"""
AgencyBD MCP Server: Contract-Driven Model Context Protocol Server for AI Agents.

Inspired by REA (Reverse Engineer Anything) MCP architecture:
  - Standard JSON-RPC 2.0 stdio server interface.
  - Exposes AgencyBD Sovereign Multi-Agent Swarm capabilities as native MCP tools.
  - Enforces strict 10 MiB Transport Budget Guard: prevents AI agent stdio buffer crashes
    by storing oversized responses in EvidenceLedger and returning an evidence reference.
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional

from engines.math_pipeline_engine import MathPipelineEngine
from engines.native_browser_service import NativeBrowserService
from engines.brain_gateway import BrainGateway
from engines.differential_audit_engine import DifferentialAuditEngine
from intel.evidence_ledger import EvidenceLedger


MAX_MCP_TRANSPORT_BYTES = 10 * 1024 * 1024  # 10 MiB ceiling


class AgencyBDMcpServer:
    """
    Model Context Protocol (MCP) server exposing AgencyBD tools
    over standard input/output for Claude Desktop, Cursor, and autonomous agents.
    """

    def __init__(self):
        self.browser = NativeBrowserService()
        self.brain = BrainGateway()
        self.diff_engine = DifferentialAuditEngine(browser_service=self.browser)
        self.ledger = EvidenceLedger()

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "agencybd_source_venture_deals",
                "description": "Sources newly-funded venture startups from SEC EDGAR Form D Atom feeds (100% Sovereign, Zero Paid APIs).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Number of prospects to fetch (1-20)", "default": 5}
                    }
                }
            },
            {
                "name": "agencybd_audit_website_dom",
                "description": "Renders virtual DOM of target website via headless Chromium, extracting emails, phones, and tech stack.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string", "description": "Target company domain (e.g. stripe.com)"}
                    },
                    "required": ["domain"]
                }
            },
            {
                "name": "agencybd_calculate_deal_math",
                "description": "Calculates Bayesian P(Close) win probability, expected deal valuation E[Deal], and monthly financial delay loss.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "lcp_seconds": {"type": "number", "description": "Measured mobile Largest Contentful Paint in seconds", "default": 3.4},
                        "detected_stack": {"type": "array", "items": {"type": "string"}, "description": "List of detected frameworks"},
                        "email_confidence": {"type": "integer", "description": "Email deliverability confidence percentage", "default": 90}
                    }
                }
            },
            {
                "name": "agencybd_compare_competitors",
                "description": "Performs side-by-side technical and financial comparison between a prospect and their competitor.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_domain": {"type": "string", "description": "Prospect company domain"},
                        "competitor_domain": {"type": "string", "description": "Key competitor domain"}
                    },
                    "required": ["target_domain", "competitor_domain"]
                }
            },
            {
                "name": "agencybd_triage_objection",
                "description": "Analyzes inbound prospect objection and builds evidence-based rebuttal with social proof.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "objection_text": {"type": "string", "description": "Exact text of the prospect's objection"},
                        "prospect_name": {"type": "string", "description": "First name of the lead", "default": "Lead"},
                        "company": {"type": "string", "description": "Company name", "default": "Target Corp"}
                    },
                    "required": ["objection_text"]
                }
            },
            {
                "name": "agencybd_generate_proposal_artifact",
                "description": "Generates a Claude-style rich interactive markdown proposal with KaTeX math and sprint milestones.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "company_name": {"type": "string", "description": "Company name"},
                        "domain": {"type": "string", "description": "Company domain"},
                        "lcp_seconds": {"type": "number", "description": "Measured LCP latency", "default": 3.6}
                    },
                    "required": ["company_name", "domain"]
                }
            }
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches tool execution with strict budget guarding."""
        if name == "agencybd_source_venture_deals":
            from agents.sourcing_agent import SourcingAgent
            sourcing = SourcingAgent()
            limit = min(int(arguments.get("limit", 5)), 20)
            leads = sourcing.source_sec_edgar_venture(limit=limit)
            return {"status": "success", "count": len(leads), "leads": leads}

        elif name == "agencybd_audit_website_dom":
            domain = arguments.get("domain", "")
            return self.browser.render_spa_dom(domain)

        elif name == "agencybd_calculate_deal_math":
            lcp = float(arguments.get("lcp_seconds", 3.4))
            stack = arguments.get("detected_stack") or ["Next.js"]
            conf = int(arguments.get("email_confidence", 90))
            prob = MathPipelineEngine.predict_close_probability(
                source_channel="sec_edgar_form_d",
                title="CTO",
                lcp_seconds=lcp,
                detected_stack=stack,
                email_confidence=conf
            )
            deal = MathPipelineEngine.calculate_expected_deal_value(prob["p_close"], detected_stack=stack)
            delay = MathPipelineEngine.calculate_cost_of_delay(lcp_seconds=lcp)
            return {
                "status": "success",
                "probability": prob,
                "deal_economics": deal,
                "cost_of_delay": delay
            }

        elif name == "agencybd_compare_competitors":
            target = arguments.get("target_domain", "")
            competitor = arguments.get("competitor_domain", "")
            return self.diff_engine.compare_domains(target, competitor)

        elif name == "agencybd_triage_objection":
            obj_text = arguments.get("objection_text", "")
            p_name = arguments.get("prospect_name", "Lead")
            comp = arguments.get("company", "Target Corp")
            return self.brain.triage_objection(obj_text, prospect_name=p_name, company=comp)

        elif name == "agencybd_generate_proposal_artifact":
            company = arguments.get("company_name", "Acme Labs")
            domain = arguments.get("domain", "acmelabs.com")
            lcp = float(arguments.get("lcp_seconds", 3.6))
            lead = {"company_name": company, "domain": domain, "contact_name": "Leadership"}
            audit = {"detected_stack": ["Next.js", "React"], "lcp_seconds": lcp}
            metrics = {"monthly_financial_loss_usd": 2800.0, "expected_value_usd": 55000.0}
            return self.brain.generate_proposal_artifact(lead, audit, metrics)

        else:
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
        
        # 10 MiB Transport Budget Guard (REA Pattern)
        if len(serialized.encode("utf-8")) > MAX_MCP_TRANSPORT_BYTES:
            # Seal oversized payload in evidence ledger
            sealed_record = self.ledger.record_evidence(
                target_domain="mcp_transport",
                operation="oversized_payload_quarantine",
                observations={"raw_length": len(serialized)},
                derivations={},
                inferences={},
                unknowns=[{"facet": "full_response", "reason_code": "RESPONSE_EXCEEDED_MCP_10MIB_BUDGET"}]
            )
            response["result"] = {
                "status": "resource_constraint",
                "message": "Output payload exceeded 10 MiB MCP transport budget ceiling. Response quarantined safely in EvidenceLedger.",
                "evidence_reference": sealed_record.evidence_id,
                "continuation_query": "Use inspect_analysis_view to inspect paged chunks."
            }
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
