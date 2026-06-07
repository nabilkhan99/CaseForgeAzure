"""Normalization of model feedback variants into the strict schema.

gpt-5.4-mini emits natural shapes (domain as display name, evidence as a bare
string with a sibling timestamp, grade_mover / model_moment / how_to_improve as
strings). normalize_feedback coerces these into the Section 12 schema so the
pydantic validation accepts a well-meaning but loosely-shaped response.
"""
from app.schemas.feedback import SingleCaseFeedback
from app.services.marking_service import normalize_feedback, _parse_ts


def test_parse_ts_variants():
    assert _parse_ts("05:02") == 302000
    assert _parse_ts(302000) == 302000
    assert _parse_ts("570000") == 570000
    assert _parse_ts(None) is None


def test_normalize_domain_displayname_and_string_evidence():
    raw = {
        "session_id": "s1",
        "overall": {"verdict": "Pass", "weighted_score": 9, "one_line_summary": "ok"},
        "domains": [
            {
                "domain": "Data gathering and diagnosis",
                "grade": "P",
                "what_you_did_well": [
                    {"timestamp": "01:25", "evidence": "You linked the rash to her work.", "point": "Good occupational history"}
                ],
                "what_you_missed": [
                    {"timestamp": "09:30", "evidence": "hydrocortisone one percent", "comment": "Mild steroid inadequate"}
                ],
                "cue_handling": [
                    {"timestamp": "05:02", "cue": "winces bathing baby", "status": "missed", "detail": "Not acknowledged"}
                ],
                "grade_mover": "Swap to a potent steroid.",
                "how_to_improve": ["Map the whole irritant burden."],
            },
            {"domain": "Clinical management and medical complexity", "grade": "F",
             "model_moment": "You could have explained patch testing."},
            {"domain": "Relating to others", "grade": "P"},
        ],
        "confidence": "high",
    }
    out = normalize_feedback(raw)
    fb = SingleCaseFeedback(**out)  # must validate

    d0 = fb.domains[0]
    assert d0.domain == "data_gathering"
    assert d0.display_name  # synthesised
    assert d0.what_you_did_well[0].label
    assert d0.what_you_did_well[0].narrative == "Good occupational history"
    assert d0.what_you_did_well[0].evidence.quote == "You linked the rash to her work."
    assert d0.what_you_did_well[0].evidence.timestamp_ms == 85000
    assert d0.what_you_missed[0].status == "not_met"
    assert d0.what_you_missed[0].consequence_tier >= 1
    assert d0.cue_handling[0].narrative == "Not acknowledged"
    assert d0.grade_mover.narrative == "Swap to a potent steroid."
    assert d0.how_to_improve[0].narrative == "Map the whole irritant burden."
    assert d0.how_to_improve[0].source == "learning_points"
    # model_moment string coerced; only kept because domain is F
    assert fb.domains[1].model_moment is not None
    assert fb.confidence.transcript_quality == "high"


def test_normalize_anchored_statements_strings():
    raw = {
        "session_id": "s1",
        "overall": {"verdict": "Fail", "weighted_score": 3, "one_line_summary": "x"},
        "domains": [
            {"domain": "data_gathering", "grade": "P", "anchored_statements": ["Some statement title"]},
            {"domain": "clinical_management", "grade": "F"},
            {"domain": "relating_to_others", "grade": "F"},
        ],
        "confidence": {"transcript_quality": "high", "notes": ""},
    }
    fb = SingleCaseFeedback(**normalize_feedback(raw))
    assert fb.domains[0].anchored_statements[0].title == "Some statement title"
