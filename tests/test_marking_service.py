"""Marking service orchestration logic (I/O injected as fakes).

Verifies the parts the spec cares about: the verdict is recomputed server side
from the domain grades (the model's own arithmetic is never trusted), a Tier 3
missed item caps the case at Fail, dashes are stripped before persistence, and a
single malformed model response is retried.
"""
import json
import pytest

from app.services.marking_service import MarkingService, build_case_pack, parse_model_json


STATION = {
    "id": "derm_sophie_miller",
    "candidate_instructions": "Patient: Sophie Miller, 29. Hands worsening, affects her work.",
    "station_script": "Opening line: I am really worried about my hands.",
    "data_gathering": "Occupational history; time off pattern; atopic background.",
    "clinical_management": "Potent topical steroid; patch testing referral; soap substitute.",
    "relating_to_others": "Empathy for livelihood; explore ICE; check understanding.",
    "clinical_learning_points": "Hydrocortisone 1 percent is inadequate; a potent steroid is required.",
    "mark_scheme_structured": {"domains": []},
    "case_type": "patient_direct",
    "conditional_features": {"safeguarding": False, "consent_capacity": False, "complexity": False, "third_party": False},
}

SESSION = {
    "id": "sess_1",
    "user_id": "cand_1",
    "station_id": "derm_sophie_miller",
    "status": "processing",
    "transcript": [
        {"speaker": "candidate", "start_ms": 4000, "text": "Hello Sophie, tell me what is going on."},
        {"speaker": "patient", "start_ms": 18000, "text": "My hands are cracking and painful."},
    ],
}


def _domain(domain, display, grade, missed=None):
    return {
        "domain": domain,
        "display_name": display,
        "grade": grade,
        "grade_points": 0,
        "anchored_statements": [],
        "what_you_did_well": [],
        "what_you_missed": missed or [],
        "cue_handling": [],
        "how_to_improve": [],
    }


def _model_feedback(d1="P", d2="F", d3="P", missed=None, bogus_overall=True):
    return {
        "session_id": "sess_1",
        "candidate_id": "cand_1",
        "case_id": "derm_sophie_miller",
        # Deliberately WRONG overall to prove the service recomputes it.
        "overall": {
            "verdict": "Pass" if bogus_overall else "Bare Fail",
            "weighted_score": 9.9 if bogus_overall else 5.5,
            "max_score": 10.5,
            "one_line_summary": "Held back over 2-3 management points for a self-employed mother.",
            "tier3_override_applied": False,
        },
        "domains": [
            _domain("data_gathering", "Data gathering and diagnosis", d1),
            _domain("clinical_management", "Clinical management and medical complexity", d2, missed=missed),
            _domain("relating_to_others", "Relating to others", d3),
        ],
        "timing": {"total_duration_ms": 712000, "data_gathering_end_ms": 480000, "flags": ["management_rushed"]},
        "focus_areas": [],
        "capability_links": ["Clinical Management"],
        "confidence": {"transcript_quality": "high", "notes": ""},
        "evidence_map": [],
    }


class FakeRepo:
    def __init__(self, session, station):
        self._session = session
        self._station = station
        self.saved = None
        self.completed = None
        self.errored = None

    def get_session(self, session_id):
        return self._session if self._session and self._session["id"] == session_id else None

    def get_station(self, station_id):
        return self._station if self._station and self._station["id"] == station_id else None

    def save_results(self, session_id, payload):
        self.saved = (session_id, payload)

    def mark_completed(self, session_id, overall_score):
        self.completed = (session_id, overall_score)

    def mark_errored(self, session_id):
        self.errored = session_id


def _stub_model(*responses):
    calls = {"n": 0}

    async def _call(messages):
        i = calls["n"]
        calls["n"] += 1
        return responses[min(i, len(responses) - 1)]

    _call.calls = calls
    return _call


# ── parse helper ──

def test_parse_model_json_strips_fences():
    raw = "```json\n{\"a\": 1}\n```"
    assert parse_model_json(raw) == {"a": 1}


def test_parse_model_json_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_model_json("not json at all")


# ── recompute + no-dash ──

async def test_verdict_recomputed_and_dashes_stripped():
    repo = FakeRepo(SESSION, STATION)
    model = _stub_model(json.dumps(_model_feedback(d1="P", d2="F", d3="P")))
    svc = MarkingService(repo, model)

    result = await svc.mark("sess_1")

    # Recomputed from grades P,F,P -> 5.5 Bare Fail, NOT the model's bogus Pass/9.9.
    assert result["overall"]["verdict"] == "Bare Fail"
    assert result["overall"]["weighted_score"] == 5.5
    assert result["overall"]["tier3_override_applied"] is False
    # No dashes anywhere in the persisted payload.
    assert "2-3" not in json.dumps(result)
    assert "self-employed" not in json.dumps(result)
    assert "2 to 3" in result["overall"]["one_line_summary"]
    # Persisted + session completed; coarse int score on the session.
    assert repo.saved[0] == "sess_1"
    assert repo.completed == ("sess_1", 6)  # round(5.5) -> 6


async def test_tier3_missed_item_caps_to_fail():
    missed = [{"label": "Safeguarding pathway", "status": "not_met", "consequence_tier": 3, "narrative": "Wrong route."}]
    repo = FakeRepo(SESSION, STATION)
    model = _stub_model(json.dumps(_model_feedback(d1="P", d2="CF", d3="F", missed=missed)))
    svc = MarkingService(repo, model)

    result = await svc.mark("sess_1")
    assert result["overall"]["verdict"] == "Fail"
    assert result["overall"]["tier3_override_applied"] is True
    assert result["overall"]["weighted_score"] == 3.0


async def test_malformed_then_valid_is_retried():
    repo = FakeRepo(SESSION, STATION)
    model = _stub_model("garbage", json.dumps(_model_feedback()))
    svc = MarkingService(repo, model)
    result = await svc.mark("sess_1")
    assert result["overall"]["verdict"] == "Bare Fail"
    assert model.calls["n"] == 2


async def test_missing_session_marks_errored():
    repo = FakeRepo(None, STATION)
    model = _stub_model(json.dumps(_model_feedback()))
    svc = MarkingService(repo, model)
    with pytest.raises(ValueError):
        await svc.mark("nope")


# ── case pack ──

def test_build_case_pack_maps_station_columns():
    pack = build_case_pack(STATION)
    assert pack["candidate_brief"].startswith("Patient: Sophie Miller")
    assert pack["patient_script"].startswith("Opening line")
    assert pack["mark_scheme_prose"]["clinical_management"].startswith("Potent topical steroid")
    assert pack["learning_points"].startswith("Hydrocortisone")
    assert pack["case_type"] == "patient_direct"
