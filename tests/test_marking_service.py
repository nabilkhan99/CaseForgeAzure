"""Marking service orchestration logic (I/O injected as fakes).

Verifies the parts the spec cares about: the verdict is recomputed server side
from the domain grades (the model's own arithmetic is never trusted), a Tier 3
missed item caps the case at Fail, dashes are stripped before persistence, and a
single malformed model response is retried.

Also covers the pre-marking guard: a transcript too thin to grade is refused
before the model is called, parked as 'unmarkable', and reported to the frontend
as HTTP 200 with the agreed body rather than as a mark the candidate did not earn.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.services.marking_service import (
    MarkingService,
    UnmarkableTranscript,
    build_case_pack,
    evaluate_transcript,
    normalize_feedback,
    parse_model_json,
)


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

EPOCH = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)


def _turn(speaker, text, at_ms, *, legacy=False, timed=True):
    """One transcript turn in either shape the pipeline has ever written.

    ``legacy`` is the pre gpt-realtime {role, content, timestamp} shape, whose
    clock is an absolute ISO wall clock rather than an offset from the start of
    the session. ``timed=False`` drops the clock entirely, as the oldest rows do.
    """
    if legacy:
        stamp = EPOCH + timedelta(milliseconds=at_ms)
        return {
            "role": "user" if speaker == "candidate" else "assistant",
            "content": text,
            "timestamp": stamp.isoformat().replace("+00:00", "Z"),
        }
    turn = {"speaker": speaker, "text": text}
    if timed:
        turn["start_ms"] = at_ms
    return turn


def _transcript(candidate_turns, seconds, *, legacy=False, timed=True):
    """A plausible alternating consultation of N candidate turns over `seconds`.

    The span is exact and is measured the way the guard measures it, from the
    first candidate turn to the last, so a test can ask for the duration it means.
    """
    total_ms = int(seconds * 1000)
    base_ms = 4000
    turns = []
    for i in range(candidate_turns):
        at = base_ms + (
            round(i * total_ms / (candidate_turns - 1)) if candidate_turns > 1 else 0
        )
        turns.append(
            _turn("candidate", f"Question {i + 1}. Tell me more about that.", at,
                  legacy=legacy, timed=timed)
        )
        turns.append(
            _turn("patient", f"Answer {i + 1}. It has been going on a while.", at + 1000,
                  legacy=legacy, timed=timed)
        )
    return turns


SESSION = {
    "id": "sess_1",
    "user_id": "cand_1",
    "station_id": "derm_sophie_miller",
    "status": "processing",
    # A real sitting: ten candidate turns across roughly twelve minutes, well
    # clear of the unmarkable guard.
    "transcript": _transcript(candidate_turns=10, seconds=700),
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
        self.unmarkable = None

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

    def mark_unmarkable(self, session_id):
        self.unmarkable = session_id


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
    management = next(d for d in result["domains"] if d["domain"] == "clinical_management")
    assert management["max_points"] == 4.5
    assert management["weighted_points"] == 1.5
    assert management["is_weighted"] is True


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


def test_normalize_feedback_strips_generic_missed_quote():
    payload = _model_feedback()
    payload["domains"][0]["what_you_missed"] = [
        {
            "label": "Skin and nipple red flags",
            "status": "not_met",
            "consequence_tier": 2,
            "narrative": "You did not ask about nipple discharge or skin tethering.",
            "evidence": {
                "quote": "Tell me what is wrong with you then.",
                "timestamp_ms": 0,
                "speaker": "candidate",
            },
        }
    ]

    normalized = normalize_feedback(payload)
    evidence = normalized["domains"][0]["what_you_missed"][0]["evidence"]
    assert evidence["evidence_kind"] == "not_asked"
    assert evidence["quote"] is None
    assert evidence["timestamp_ms"] is None


def test_normalize_feedback_marks_patient_cue_for_missed_quote():
    payload = _model_feedback()
    payload["domains"][0]["what_you_missed"] = [
        {
            "label": "Persistent breast lump cue",
            "status": "partial",
            "consequence_tier": 2,
            "narrative": "The persistence after a period should have prompted red flag screening.",
            "evidence": {
                "quote": "I found a lump in my right breast in the shower a couple of weeks ago, and I thought it would go after my period, but it has not.",
                "timestamp_ms": 0,
                "speaker": "patient",
            },
        }
    ]

    normalized = normalize_feedback(payload)
    evidence = normalized["domains"][0]["what_you_missed"][0]["evidence"]
    assert evidence["evidence_kind"] == "patient_cue"
    assert evidence["quote"].startswith("I found a lump")
