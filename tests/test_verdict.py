"""Verdict math, derived from FF SCA Feedback Engine Build Package Section 8.

Scoring geometry: s = g(D1) + 1.5*g(D2) + g(D3), where CP=3, P=2, F=1, CF=0.
Bands: Pass >= 7.0, Bare Pass 6.0 to 6.99, Bare Fail 4.5 to 5.99, Fail < 4.5.
A single Tier 3 dangerous error caps the verdict at Fail (Section 8.4).
"""
import pytest

from app.utils.verdict import (
    grade_points,
    weighted_score,
    verdict_band,
    apply_tier3_cap,
    compute_verdict,
)


@pytest.mark.parametrize("grade,points", [("CP", 3), ("P", 2), ("F", 1), ("CF", 0)])
def test_grade_points(grade, points):
    assert grade_points(grade) == points


@pytest.mark.parametrize(
    "d1,d2,d3,expected",
    [
        ("CP", "CP", "CP", 10.5),  # max
        ("P", "P", "P", 7.0),      # solid pass, near the mean
        ("F", "P", "P", 6.0),      # one light domain failed but compensated
        ("P", "F", "P", 5.5),      # weighted CM&C failed -> below the line (Sophie, Wright)
        ("P", "CF", "P", 4.0),     # clear CM&C fail
        ("P", "CF", "F", 3.0),     # Faduma grades (D1 P, D2 CF, D3 F)
        ("CF", "CF", "CF", 0.0),
    ],
)
def test_weighted_score(d1, d2, d3, expected):
    assert weighted_score(d1, d2, d3) == expected


@pytest.mark.parametrize(
    "score,band",
    [
        (10.5, "Pass"),
        (7.0, "Pass"),       # boundary: at 7.0 is Pass
        (6.99, "Bare Pass"),
        (6.0, "Bare Pass"),  # boundary: at 6.0 is Bare Pass
        (5.99, "Bare Fail"),
        (5.5, "Bare Fail"),
        (4.5, "Bare Fail"),  # boundary: at 4.5 is Bare Fail
        (4.49, "Fail"),
        (3.0, "Fail"),
        (0.0, "Fail"),
    ],
)
def test_verdict_band(score, band):
    assert verdict_band(score) == band


def test_tier3_cap_forces_fail_and_sets_flag():
    # A Tier 3 present caps to Fail and records the override, even if the band already failed.
    assert apply_tier3_cap("Bare Pass", has_tier3=True) == ("Fail", True)
    assert apply_tier3_cap("Fail", has_tier3=True) == ("Fail", True)


def test_no_tier3_leaves_band_untouched():
    assert apply_tier3_cap("Bare Fail", has_tier3=False) == ("Bare Fail", False)
    assert apply_tier3_cap("Pass", has_tier3=False) == ("Pass", False)


def test_compute_verdict_sophie_bare_fail():
    # Sophie Miller: D1 P, D2 F, D3 P, no Tier 3 -> Bare Fail 5.5
    result = compute_verdict("P", "F", "P", has_tier3=False)
    assert result == {
        "weighted_score": 5.5,
        "max_score": 10.5,
        "verdict": "Bare Fail",
        "tier3_override_applied": False,
    }


def test_compute_verdict_faduma_fail_capped():
    # Faduma FGM: D1 P, D2 CF, D3 F, Tier 3 -> Fail (score 3.0), override applied
    result = compute_verdict("P", "CF", "F", has_tier3=True)
    assert result == {
        "weighted_score": 3.0,
        "max_score": 10.5,
        "verdict": "Fail",
        "tier3_override_applied": True,
    }
