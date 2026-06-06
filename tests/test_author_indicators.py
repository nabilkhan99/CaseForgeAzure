"""Indicator authoring prompt + proposal validation (offline-testable core)."""
from scripts.author_indicators import build_indicator_messages, validate_proposal


STATION = {
    "id": "derm_sophie_miller",
    "title": "Occupational hand dermatitis",
    "patient_name": "Sophie Miller",
    "patient_age": 29,
    "consultation_type": "face-to-face",
    "candidate_instructions": "Sophie Miller, 29, hands worsening.",
    "station_script": "Opening line: I am worried about my hands.",
    "data_gathering": "Occupational history; time off pattern.",
    "clinical_management": "Potent topical steroid; patch testing referral.",
    "relating_to_others": "Empathy for livelihood; explore ICE.",
    "clinical_learning_points": "Hydrocortisone 1 percent is inadequate.",
}


def test_build_indicator_messages_includes_all_parts():
    msgs = build_indicator_messages(STATION)
    assert [m["role"] for m in msgs] == ["system", "user"]
    user = msgs[1]["content"]
    assert "derm_sophie_miller" in user
    assert "Potent topical steroid" in user
    assert "Hydrocortisone 1 percent" in user
    assert "Opening line" in user


def test_validate_proposal_accepts_well_formed():
    data = {
        "case_type": "patient_direct",
        "conditional_features": {"safeguarding": False, "consent_capacity": False, "complexity": False, "third_party": False},
        "mark_scheme_structured": {
            "domains": [
                {
                    "domain": "clinical_management",
                    "indicators": [
                        {
                            "id": "potent_steroid",
                            "label": "Potent topical corticosteroid",
                            "positive_descriptor": "Prescribes a potent steroid for hand skin.",
                            "negative_descriptor": "Prescribes a mild steroid.",
                        }
                    ],
                }
            ]
        },
    }
    proposal = validate_proposal(data)
    assert proposal.case_type == "patient_direct"
    assert proposal.mark_scheme_structured.domains[0].indicators[0].id == "potent_steroid"
