"""Cross case trend report schema, contract version 2.

Version 1 was an audit. It carried recurring_themes and style_patterns, each
theme dragging four evidence quotes and six fields of metadata behind it, plus
consistent_strengths, next_steps and a caution: roughly eight thousand generated
characters, most of which the candidate never read and the Development page
never showed.

Version 2 is the surgical form. At most three patterns, each pairing one
verbatim quote from the candidate's own consultations with what a model answer
sounds like at that same moment, and one structural change. The whole report
should land under two thousand characters, which is also where the build time
went: output tokens dominate the one to two minute wait for a trend report.

Everything that was metadata about a theme rather than something the candidate
could act on is gone, deliberately and permanently: confidence, style_patterns,
next_steps, caution, consistent_strengths, mapped_statement, capability_area,
context_pattern, max_consequence_tier, per theme trajectory,
development_suggestion, and the timestamp_ms / completed_at that used to ride
along inside each piece of evidence.

The models are frozen. A trend report is a rendered artefact: it is validated,
persisted and served, and nothing downstream has any business editing a field
after the fact (v1's confidence floor did exactly that, and it is gone too).
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Bumped only for a breaking change to the shape below. The frontend reads it to
# tell a v2 report from a v1 row that has not been rebuilt yet.
TREND_SCHEMA_VERSION = 2

# "steady" replaces v1's "static": the same idea in the register the report is
# written in. Note that migration 0005 widens the trend_reports check constraint
# to match, so a v1 database will reject a v2 report until it is applied.
Trajectory = Literal["improving", "steady", "declining"]

# The three SCA marking domains, spelled as the marking engine spells them.
Domain = Literal["data_gathering", "clinical_management", "relating_to_others"]

MAX_PATTERNS = 3
MAX_EVIDENCE_PER_PATTERN = 4


class TrendEvidence(BaseModel):
    """One case, and the candidate's or patient's own words from it.

    Both fields are copied, never composed: ``case_id`` exactly as it appeared
    in the input, ``quote`` character for character from that case's marked
    output. Nothing here is enforced by the type system, so the prompt states it
    as a hard rule and TrendService logs any quote it cannot find in the input.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    case_id: str
    quote: str


class TrendPattern(BaseModel):
    """One cross case habit, shown rather than described.

    The order of the fields is the order the candidate reads them in: the
    headline names the habit, their own quote shows it happening, the model line
    shows what the same moment sounds like when it goes well, and the_change is
    the one thing to do differently.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    headline: str
    domain: Domain
    # Cases in the window the pattern appeared in. One is legitimate for a
    # pattern that is severe enough to lead, but the prompt weights recurrence.
    frequency: int = Field(ge=1)
    your_quote: str
    quote_gloss: str
    model_line: str
    model_gloss: str
    the_change: str
    evidence: List[TrendEvidence] = Field(
        min_length=1, max_length=MAX_EVIDENCE_PER_PATTERN
    )


class TrendWindow(BaseModel):
    """Which cases the report covers, and when they were sat.

    Stamped by TrendService from the rows it actually fetched rather than taken
    from the model. Dates are the field a language model is most willing to
    round or invent, and this one is displayed to the candidate as fact.
    """

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    cases_included: int = Field(ge=0)
    # `from` is a Python keyword, so the field is from_ and the alias carries the
    # contract spelling in and out (populate_by_name keeps both working).
    from_: Optional[str] = Field(default=None, alias="from")
    to: Optional[str] = None


class TrendReport(BaseModel):
    """The whole v2 contract. One live report per candidate."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    version: int = TREND_SCHEMA_VERSION
    candidate_id: str
    window: TrendWindow
    overall_trajectory: Trajectory
    overall_narrative: str
    # At least one: a report with nothing to say is not worth building, and
    # TrendService refuses to ask for one below MIN_CASES_FOR_PATTERNS.
    patterns: List[TrendPattern] = Field(min_length=1, max_length=MAX_PATTERNS)

    @field_validator("version")
    @classmethod
    def _must_be_this_version(cls, value: int) -> int:
        """Refuse to validate anything but v2.

        A v1 payload reaching these models would otherwise be accepted field by
        field and silently persisted as a half report, because extra keys are
        ignored and the v1 shape shares no required field with this one.
        """
        if value != TREND_SCHEMA_VERSION:
            raise ValueError(
                f"trend report version must be {TREND_SCHEMA_VERSION}, got {value}"
            )
        return value
