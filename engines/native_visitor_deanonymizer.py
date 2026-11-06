"""
Native B2B Website Visitor Deanonymizer & Reverse-DNS Intelligence Engine.
Looks up the reverse-DNS name of a visiting IP address and filters obvious residential ISPs. A reverse-DNS name is NOT company
identification: it is returned only as an unverified candidate, and nothing is invented when there is no name.
"""

import socket
import re
from typing import Dict, Any, Optional, List
from agents.linkedin_agent import LinkedInAgent


RESIDENTIAL_ISP_KEYWORDS = [
    "comcast", "verizon", "att", "spectrum", "charter", "cox", "centurylink",
    "xfinity", "broadband", "telecom", "dsl", "dhcp", "dynamic", "pool", "residential"
]

class NativeVisitorDeanonymizer:
    def __init__(self):
        self.linkedin_agent = LinkedInAgent()

    def resolve_ip(self, ip_address: str) -> Dict[str, Any]:
        """
        Reverse-DNS & ASN Resolution:
        1. Query PTR DNS for IP address.
        2. Evaluate whether IP belongs to corporate network or residential ISP.
        3. Extract company domain.
        4. Auto-discover target decision-makers at visiting company.
        """
        clean_ip = ip_address.strip()
        hostname = ""
        try:
            host_info = socket.gethostbyaddr(clean_ip)
            hostname = host_info[0].lower() if host_info else ""
        except Exception:
            hostname = ""                      # no reverse-DNS name exists; nothing is made up in its place

        # Check for residential ISP
        is_residential = any(kw in hostname for kw in RESIDENTIAL_ISP_KEYWORDS)
        if is_residential:
            return {
                "ip": clean_ip,
                "is_corporate": False,
                "hostname": hostname,
                "status": "filtered_residential_isp",
                "message": "Traffic from residential ISP (not a direct B2B corporate network)."
            }

        # Reverse DNS alone cannot identify a company or a person. Report only what it shows.
        guessed = None
        parts = hostname.split(".") if hostname else []
        if len(parts) >= 2 and not hostname.endswith(".arpa"):
            guessed = ".".join(parts[-2:])
        return {
            "ip": clean_ip,
            "hostname": hostname or None,
            "is_corporate": None,
            "candidate_domain": guessed,
            "status": "unidentified_without_provider",
            "note": "Reverse DNS is not company identification. Connect a licensed visitor-identification provider for real matches.",
            "buyer_intent_score": None,
            "identified_decision_makers": [],
        }
