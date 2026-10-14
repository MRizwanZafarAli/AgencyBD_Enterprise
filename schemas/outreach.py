"""
Pydantic Schemas for Contacts, Outreach Sequences, Objection Handling, and Bookings.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class DecisionMakerSchema(BaseModel):
    id: Optional[int] = None
    lead_id: int
    first_name: str
    last_name: str
    title: str
    email: str
    linkedin_url: Optional[str] = None
    email_source: str = "waterfall_enrichment"
    verification_status: str = "valid"
    mx_verified: bool = True
    smtp_handshake_status: str = "250_OK"

class SequenceStep(BaseModel):
    step_number: int = Field(..., ge=1, le=3)
    channel: str = Field("email", description="'email' or 'linkedin'")
    subject: str = Field(..., description="Compelling, low-friction subject line")
    body: str = Field(..., description="Body of message, under 85 words with zero spam triggers")
    spam_score: float = Field(0.0, description="Calculated spam friction score")
    status: str = Field("drafted")

class OutreachPackage(BaseModel):
    lead_id: int
    decision_maker: DecisionMakerSchema
    pitch_angle: str
    steps: List[SequenceStep]
    linkedin_connection_note: str

class ObjectionTriageRequest(BaseModel):
    lead_id: int
    reply_text: str

class ObjectionTriageResult(BaseModel):
    lead_id: int
    reply_text: str
    sentiment: str = Field(..., description="'positive', 'neutral', or 'negative'")
    objection_category: str = Field(..., description="'interested', 'in_house_team', 'no_budget', 'send_info', 'not_interested'")
    rebuttal_strategy: str
    auto_rebuttal_draft: str

class BookingRequest(BaseModel):
    lead_id: int
    decision_maker_id: Optional[int] = None
    booking_time: str
    cal_link: Optional[str] = None
