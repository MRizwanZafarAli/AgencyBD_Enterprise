"""
Base interfaces and models for Website Doctor audit checks.
Every finding contains a structured severity, evidence, fix, and service mapping.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class AuditFinding:
    category: str        # performance | seo | security | a11y | ux | geo | dns | stack
    check_id: str        # e.g. "missing_hsts", "slow_ttfb", "missing_robots_txt"
    severity: str        # critical | high | medium | low | info
    finding: str         # Plain-language explanation of what is wrong
    fix: str             # Actionable engineering remediation
    estimated_impact: str# Business/conversion/ranking impact
    service_id: str      # Internal agency service that solves this (e.g., "devops_sre", "seo_boost")
    evidence_value: str  # Raw measurement (e.g. "TTFB: 1,420ms", "Header missing")
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "check_id": self.check_id,
            "severity": self.severity,
            "finding": self.finding,
            "fix": self.fix,
            "estimated_impact": self.estimated_impact,
            "service_id": self.service_id,
            "evidence_value": self.evidence_value,
            "confidence": self.confidence,
        }
