"""Structured mark-scheme indicator schema, FF SCA Build Package Section 3.3 + 4.10.

Used by scripts/author_indicators.py to convert each station's free-text mark
scheme into a structured indicator set plus the case type and which conditional
rubrics are in play.
"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, ConfigDict

DomainKey = Literal["data_gathering", "clinical_management", "relating_to_others"]


class Indicator(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    label: str
    positive_descriptor: str
    negative_descriptor: str


class DomainIndicators(BaseModel):
    model_config = ConfigDict(extra="ignore")
    domain: DomainKey
    indicators: List[Indicator]


class MarkSchemeStructured(BaseModel):
    model_config = ConfigDict(extra="ignore")
    domains: List[DomainIndicators]


class ConditionalFeatures(BaseModel):
    model_config = ConfigDict(extra="ignore")
    safeguarding: bool = False
    consent_capacity: bool = False
    complexity: bool = False
    third_party: bool = False


class StationIndicatorProposal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    case_type: Literal["patient_direct", "third_party"]
    conditional_features: ConditionalFeatures
    mark_scheme_structured: MarkSchemeStructured
