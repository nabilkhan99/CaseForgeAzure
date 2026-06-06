"""Cross-case trend report schema, FF SCA Build Package Section 13.5."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Source = Literal["learning_points", "rcgp_educator_notes", "nice", "sign", "curriculum"]
Confidence = Literal["low", "medium", "high"]
Trajectory = Literal["improving", "static", "declining"]


class ThemeEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    case_id: str
    completed_at: Optional[str] = None
    quote: str
    timestamp_ms: Optional[int] = None


class DevelopmentSuggestion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    narrative: str
    source: Source


class Theme(BaseModel):
    model_config = ConfigDict(extra="ignore")
    priority: int = 0
    theme_label: str
    mapped_statement: Optional[str] = None
    domain: Optional[str] = None
    capability_area: Optional[str] = None
    frequency: int = 0
    max_consequence_tier: int = Field(default=0, ge=0, le=3)
    trajectory: Optional[Trajectory] = None
    context_pattern: Optional[str] = None
    evidence: List[ThemeEvidence] = []
    development_suggestion: Optional[DevelopmentSuggestion] = None


class ConsistentStrength(BaseModel):
    model_config = ConfigDict(extra="ignore")
    theme_label: str
    domain: Optional[str] = None
    evidence_count: int = 0


class TrendWindow(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None
    cases_included: int = 0


class TrendReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    candidate_id: str
    window: Optional[TrendWindow] = None
    confidence: Confidence = "low"
    overall_trajectory: Trajectory = "static"
    overall_narrative: str = ""
    recurring_themes: List[Theme] = []
    style_patterns: List[Theme] = []
    consistent_strengths: List[ConsistentStrength] = []
    next_steps: List[str] = []
    caution: str = ""
