"""Single-case feedback output schema.

Source of truth: FF SCA Feedback Engine Build Package, Section 12 (output schema)
and Sections 9 to 10 (field meanings). Pydantic v2 models used to validate the
marking model's JSON before it is persisted or rendered.

Two invariants enforced here, independent of what the model returns:
  - grade_points is derived from grade (never trusted from the model).
  - conditional blocks are nulled when they do not apply: grade_mover only below
    CP, model_moment only for F or CF (Section 9.2).
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.utils.verdict import GRADE_POINTS

Grade = Literal["CP", "P", "F", "CF"]
DomainKey = Literal["data_gathering", "clinical_management", "relating_to_others"]
Verdict = Literal["Pass", "Bare Pass", "Bare Fail", "Fail"]
MissStatus = Literal["partial", "not_met"]
CueStatus = Literal["explored", "missed"]
Source = Literal["learning_points", "rcgp_educator_notes", "nice", "sign", "curriculum"]
TimingFlag = Literal["data_gathering_overran", "management_rushed", "no_timing_data"]
TranscriptQuality = Literal["high", "medium", "low"]


class Evidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    quote: str
    timestamp_ms: Optional[int] = None
    speaker: Optional[Literal["candidate", "patient"]] = None


class AnchoredStatement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str


class DidWell(BaseModel):
    model_config = ConfigDict(extra="ignore")
    indicator_id: Optional[str] = None
    label: str
    narrative: str
    evidence: Optional[Evidence] = None


class Missed(BaseModel):
    model_config = ConfigDict(extra="ignore")
    indicator_id: Optional[str] = None
    label: str
    status: MissStatus
    consequence_tier: int = Field(ge=0, le=3)
    narrative: str
    evidence: Optional[Evidence] = None


class CueHandling(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cue: str
    status: CueStatus
    narrative: str
    evidence: Optional[Evidence] = None


class GradeMover(BaseModel):
    model_config = ConfigDict(extra="ignore")
    narrative: str


class ModelMoment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    narrative: str
    source: Source


class HowToImprove(BaseModel):
    model_config = ConfigDict(extra="ignore")
    narrative: str
    source: Source


class DomainFeedback(BaseModel):
    model_config = ConfigDict(extra="ignore")
    domain: DomainKey
    display_name: str
    grade: Grade
    grade_points: int = 0
    anchored_statements: List[AnchoredStatement] = []
    what_you_did_well: List[DidWell] = []
    what_you_missed: List[Missed] = []
    cue_handling: List[CueHandling] = []
    grade_mover: Optional[GradeMover] = None
    model_moment: Optional[ModelMoment] = None
    how_to_improve: List[HowToImprove] = []

    @model_validator(mode="after")
    def _normalise_conditionals(self) -> "DomainFeedback":
        # grade_points is authoritative from the grade, not the model.
        self.grade_points = GRADE_POINTS[self.grade]
        # grade_mover only for domains below CP (Section 9.2).
        if self.grade == "CP":
            self.grade_mover = None
        # model_moment only for domains graded F or CF (Section 9.2).
        if self.grade not in ("F", "CF"):
            self.model_moment = None
        return self


class Overall(BaseModel):
    model_config = ConfigDict(extra="ignore")
    verdict: Verdict
    weighted_score: float
    max_score: float = 10.5
    one_line_summary: str
    tier3_override_applied: bool = False


class Timing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_duration_ms: Optional[int] = None
    data_gathering_end_ms: Optional[int] = None
    flags: List[TimingFlag] = []


class FocusArea(BaseModel):
    model_config = ConfigDict(extra="ignore")
    priority: int
    label: str
    narrative: str
    domain: str


class Confidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    transcript_quality: TranscriptQuality
    notes: str = ""


class SingleCaseFeedback(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str
    candidate_id: Optional[str] = None
    case_id: Optional[str] = None
    completed_at: Optional[str] = None
    overall: Overall
    domains: List[DomainFeedback]
    timing: Optional[Timing] = None
    focus_areas: List[FocusArea] = []
    capability_links: List[str] = []
    confidence: Confidence
    evidence_map: List[dict] = []
