"""
Pydantic Schemas for Leads & Sourcing Ingestion.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class LeadBase(BaseModel):
    company_name: str = Field(..., description="Legal or trade name of target company")
    domain: str = Field(..., description="Clean root domain or URL of company")
    phone: Optional[str] = Field(None, description="Direct or office telephone number")
    address: Optional[str] = Field(None, description="Physical location or headquarters city/state")
    rating: float = Field(0.0, description="Average review rating (0.0 to 5.0)")
    reviews_count: int = Field(0, description="Total number of reviews")
    source_channel: str = Field("google_maps", description="Channel where lead was captured")
    source_query: Optional[str] = Field(None, description="Specific keyword or geography used in sourcing")
    notes: Optional[str] = Field(None, description="Initial discovery notes or intent triggers")

class LeadCreate(LeadBase):
    pass

class LeadOut(LeadBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: str
    updated_at: str

class SourcingQueryRequest(BaseModel):
    channel: str = Field("google_maps", description="'google_maps', 'hiring_intent', or 'venture_database'")
    query: str = Field("luxury home renovation in Austin TX", description="Search term or role trigger")
    location: Optional[str] = Field("Austin, TX", description="Target geography")
    limit: int = Field(10, ge=1, le=50, description="Number of prospects to capture")
