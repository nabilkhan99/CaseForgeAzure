"""Verdict computation for the SCA feedback engine.

Source of truth: FF SCA Feedback Engine Build Package, Section 8 (case verdict).
The grade is decided by the marking model per domain; this module turns the three
domain grades into the weighted score and verdict band deterministically, server
side, so the arithmetic is never left to the model.

    s = g(D1) + 1.5 * g(D2) + g(D3)        g(CP)=3, g(P)=2, g(F)=1, g(CF)=0
    Pass        s >= 7.0
    Bare Pass   6.0 <= s < 7.0
    Bare Fail   4.5 <= s < 6.0
    Fail        s < 4.5

A single Tier 3 dangerous error caps the verdict at Fail regardless of score
(Section 8.4) and sets the override flag.
"""
from __future__ import annotations

from typing import Tuple

Grade = str  # "CP" | "P" | "F" | "CF"
Verdict = str  # "Pass" | "Bare Pass" | "Bare Fail" | "Fail"

GRADE_POINTS: dict[Grade, int] = {"CP": 3, "P": 2, "F": 1, "CF": 0}
MAX_SCORE: float = 10.5
CM_WEIGHT: float = 1.5


def grade_points(grade: Grade) -> int:
    """Map a domain grade to its 0 to 3 point value."""
    try:
        return GRADE_POINTS[grade]
    except KeyError as exc:
        raise ValueError(f"Unknown grade: {grade!r}") from exc


def weighted_score(d1: Grade, d2: Grade, d3: Grade) -> float:
    """Weighted per case score (0 to 10.5). Clinical Management (D2) is weighted 1.5x."""
    score = grade_points(d1) + CM_WEIGHT * grade_points(d2) + grade_points(d3)
    return round(score, 1)


def verdict_band(score: float) -> Verdict:
    """Map a weighted score to its verdict band (Section 8.3)."""
    if score >= 7.0:
        return "Pass"
    if score >= 6.0:
        return "Bare Pass"
    if score >= 4.5:
        return "Bare Fail"
    return "Fail"


def apply_tier3_cap(verdict: Verdict, has_tier3: bool) -> Tuple[Verdict, bool]:
    """Cap the verdict at Fail when a genuine Tier 3 error is present (Section 8.4).

    Returns (verdict, tier3_override_applied). The override flag records that a
    Tier 3 was present and the cap rule is in force, regardless of whether the
    band had already failed.
    """
    if has_tier3:
        return "Fail", True
    return verdict, False


def compute_verdict(d1: Grade, d2: Grade, d3: Grade, has_tier3: bool = False) -> dict:
    """Full verdict object from the three domain grades and the Tier 3 flag."""
    score = weighted_score(d1, d2, d3)
    verdict, override = apply_tier3_cap(verdict_band(score), has_tier3)
    return {
        "weighted_score": score,
        "max_score": MAX_SCORE,
        "verdict": verdict,
        "tier3_override_applied": override,
    }
