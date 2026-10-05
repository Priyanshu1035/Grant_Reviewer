from pydantic import BaseModel
from typing import Literal


class Requirement(BaseModel):
    requirement: str
    mandatory: bool
    category: Literal[
        "eligibility",
        "submission",
        "supporting_document",
        "budget",
        "timeline",
        "other"
    ]
    source_text: str
    
    
class EvidenceItem(BaseModel):
    source_text: str
    page_number: int | None = None


class RequirementMapping(BaseModel):
    requirement_id: int
    status: Literal[
        "SUPPORTED",
        "MISSING",
        "WEAK",
        "AMBIGUOUS"
    ]
    confidence: float
    reason: str
    evidence: list[EvidenceItem]
    
    
class MappingReview(BaseModel):
    review_status: Literal[
        "CONFIRMED",
        "CORRECTED",
        "REJECTED"
    ]
    
    corrected_status: Literal[
        "SUPPORTED",
        "MISSING",
        "WEAK",
        "AMBIGUOUS"
    ] | None = None

    corrected_reason: str | None = None
    
    review_reason: str | None = None