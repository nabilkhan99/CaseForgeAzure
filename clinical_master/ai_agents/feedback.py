"""
Feedback Models

Pydantic models for structured consultation feedback.
Feedback generation is handled by a Supabase Edge Function (not this agent process).
These models are kept as shared schema definitions.
"""

from typing import List

from pydantic import BaseModel, Field


class DomainScore(BaseModel):
    """Score for a single assessment domain."""
    domain: str = Field(description="Name of the domain")
    score: int = Field(ge=0, le=100, description="Score out of 100")
    strengths: List[str] = Field(description="What the trainee did well")
    improvements: List[str] = Field(description="Areas for improvement")


class ConsultationFeedback(BaseModel):
    """Structured feedback for a consultation."""
    data_gathering: DomainScore = Field(description="Assessment of history taking and information gathering")
    clinical_management: DomainScore = Field(description="Assessment of diagnosis, management plan, and safety-netting")
    interpersonal_skills: DomainScore = Field(description="Assessment of communication, empathy, and rapport")
    overall_summary: str = Field(description="Brief overall summary of the consultation")
    key_learning_points: List[str] = Field(description="3-5 key takeaways for the trainee")
