"""Single-case feedback schema, FF SCA Build Package Section 12.

Validates the engine output shape and the conditional-field rules:
grade_points is derived from the grade (never trusted from the model),
grade_mover only exists below CP, model_moment only for F or CF.
"""
import pytest
from pydantic import ValidationError

from app.schemas.feedback import SingleCaseFeedback, DomainFeedback


def _domain(**over):
    base = dict(
        domain="data_gathering",
        display_name="Data gathering and diagnosis",
        grade="P",
        grade_points=2,
        anchored_statements=[],
        what_you_did_well=[],
        what_you_missed=[],
        cue_handling=[],
        how_to_improve=[],
    )
    base.update(over)
    return base


def _full_payload():
    return dict(
        session_id="sess_1",
        candidate_id="cand_1",
        case_id="derm_sophie_miller",
        completed_at="2026-06-03T10:14:00Z",
        overall=dict(
            verdict="Bare Fail",
            weighted_score=5.5,
            max_score=10.5,
            one_line_summary="Strong history, weak management.",
            tier3_override_applied=False,
        ),
        domains=[
            _domain(),
            _domain(domain="clinical_management", display_name="Clinical management and medical complexity", grade="F", grade_points=1),
            _domain(domain="relating_to_others", display_name="Relating to others", grade="P", grade_points=2),
        ],
        timing=dict(total_duration_ms=712000, data_gathering_end_ms=480000, flags=["management_rushed"]),
        focus_areas=[dict(priority=1, label="Prescribing", narrative="Use a potent steroid.", domain="clinical_management")],
        capability_links=["Clinical Management"],
        confidence=dict(transcript_quality="high", notes=""),
        evidence_map=[],
    )


def test_full_payload_parses():
    fb = SingleCaseFeedback(**_full_payload())
    assert fb.overall.verdict == "Bare Fail"
    assert len(fb.domains) == 3


def test_missing_overall_raises():
    payload = _full_payload()
    del payload["overall"]
    with pytest.raises(ValidationError):
        SingleCaseFeedback(**payload)


def test_grade_points_derived_from_grade():
    # Model sends a wrong grade_points; schema corrects it from the grade.
    d = DomainFeedback(**_domain(grade="F", grade_points=99))
    assert d.grade_points == 1


def test_grade_mover_nulled_on_cp():
    d = DomainFeedback(**_domain(grade="CP", grade_points=3, grade_mover={"narrative": "should not exist"}))
    assert d.grade_mover is None


def test_model_moment_nulled_when_not_failing():
    d = DomainFeedback(**_domain(grade="P", grade_points=2, model_moment={"narrative": "x", "source": "learning_points"}))
    assert d.model_moment is None


def test_model_moment_kept_on_cf():
    d = DomainFeedback(**_domain(grade="CF", grade_points=0, model_moment={"narrative": "x", "source": "nice"}))
    assert d.model_moment is not None
    assert d.model_moment.source == "nice"


def test_consequence_tier_bounds():
    with pytest.raises(ValidationError):
        DomainFeedback(**_domain(what_you_missed=[dict(label="x", status="not_met", consequence_tier=9, narrative="y")]))


def test_bad_source_rejected():
    with pytest.raises(ValidationError):
        DomainFeedback(**_domain(grade="F", how_to_improve=[dict(narrative="x", source="wikipedia")]))
