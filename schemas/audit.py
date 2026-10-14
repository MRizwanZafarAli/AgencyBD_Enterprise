"""
Pydantic Schemas for Technical Audits & Performance Metrics.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class AuditMetrics(BaseModel):
    load_time_ms: int = Field(..., description="Full page load duration in milliseconds")
    ttfb_ms: int = Field(..., description="Time to First Byte in milliseconds")
    lcp_score: float = Field(..., description="Largest Contentful Paint in seconds")
    mobile_responsive: bool = Field(..., description="Whether mobile viewport and responsive tags are present")
    tech_stack: List[str] = Field(default_factory=list, description="Detected frameworks, CMS, and libraries")
    missing_headers: List[str] = Field(default_factory=list, description="Missing security headers like HSTS, CSP")
    console_errors: List[str] = Field(default_factory=list, description="Simulated console runtime errors or broken links")

class TechAuditResult(AuditMetrics):
    lead_id: int
    audit_summary: str = Field(..., description="Executive summary of technical findings")
    calculated_pitch_angle: str = Field(..., description="Agency-tailored pitch angle to convert prospect")

class AuditRequest(BaseModel):
    lead_id: int
    url: Optional[str] = None
