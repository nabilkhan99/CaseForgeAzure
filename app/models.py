# app/models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class CaseReviewRequest(BaseModel):
    case_description: str = Field(..., min_length=10, description="The case description to review")
    selected_capabilities: List[str] = Field(..., min_items=1, max_items=3, description="List of selected capabilities")

class CaseReviewSection(BaseModel):
    brief_description: str
    capabilities: Dict[str, str]
    reflection: str
    learning_needs: str
    
    class Config:
        from_attributes = True

class CaseReviewResponse(BaseModel):
    case_title: str
    review_content: str
    sections: CaseReviewSection
    
    class Config:
        from_attributes = True

class ImprovementRequest(BaseModel):
    original_case: str
    improvement_prompt: str
    selected_capabilities: List[str]

class CapabilitiesResponse(BaseModel):
    capabilities: Dict[str, List[str]]
    
    class Config:
        from_attributes = True

class ErrorResponse(BaseModel):
    error: bool = True
    message: str