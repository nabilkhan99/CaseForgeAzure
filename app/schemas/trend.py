"""Cross-case trend report schema, FF SCA Build Package Section 13.5.

Two tolerated deviations, both observed on the first end to end run of this
feature. The prompt described the output in prose ("a themes array, each with a
label ... and a concrete development suggestion") and never named the real keys,
so the model reasonably emitted `label` for `theme_label` and a bare sentence for
`development_suggestion`. The prompt now states the exact shape; these validators
are the belt to that pair of braces, because a spelling slip should not cost the
candidate the whole report. Nothing here is made optional that was required.
"""
from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

Source = Literal["learning_points", "rcgp_educator_notes", "nice", "sign", "curriculum"]
Confidence = Literal["low", "medium", "high"]
Trajectory = Literal["improving", "static", "declining"]

# `label` is what the model calls `theme_label` when it drifts. Listing the real
# name first keeps the canonical spelling working and keeps serialisation
# untouched (this is a validation alias only, so model_dump still emits
# theme_label and the DB/frontend contract is unchanged).
_THEME_LABEL_ALIASES = AliasChoices("theme_label", "label")

# A development suggestion carries its provenance. When the model hands us a
# bare sentence there is no provenance to read, and the sentence is the model's
# own developmental advice rather than a citation, so it is attributed to the
# examiner notes rather than dropped or guessed at as NICE or SIGN.
_DEFAULT_SUGGESTION_SOURCE = "rcgp_educator_notes"


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
    theme_label: str = Field(validation_alias=_THEME_LABEL_ALIASES)
    mapped_statement: Optional[str] = None
    domain: Optional[str] = None
    capability_area: Optional[str] = None
    frequency: int = 0
    max_consequence_tier: int = Field(default=0, ge=0, le=3)
    trajectory: Optional[Trajectory] = None
    context_pattern: Optional[str] = None
    evidence: List[ThemeEvidence] = []
    development_suggestion: Optional[DevelopmentSuggestion] = None

    @field_validator("development_suggestion", mode="before")
    @classmethod
    def _coerce_suggestion(cls, value: Any) -> Any:
        """Accept a bare sentence, or an object that omitted its source."""
        if isinstance(value, str):
            text = value.strip()
            return (
                {"narrative": text, "source": _DEFAULT_SUGGESTION_SOURCE}
                if text
                else None
            )
        if isinstance(value, dict) and value.get("narrative") and not value.get("source"):
            # Same normalisation applied consistently: a suggestion that reached
            # us without provenance is attributed, not thrown away.
            return {**value, "source": _DEFAULT_SUGGESTION_SOURCE}
        return value


class ConsistentStrength(BaseModel):
    model_config = ConfigDict(extra="ignore")
    theme_label: str = Field(validation_alias=_THEME_LABEL_ALIASES)
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
