"""
Tests for LiveKit PatientAgent tool definitions.

Requires: livekit-agents installed (`uv sync`).
Run with: python -m pytest tests/test_agent_tools.py -v
"""

import inspect
import pytest

try:
    from agent import PatientAgent, _extract_transcript, _build_case_brief, _build_marking_criteria
    HAS_LIVEKIT = True
except ImportError:
    HAS_LIVEKIT = False

pytestmark = pytest.mark.skipif(not HAS_LIVEKIT, reason="livekit-agents not installed")


def test_patient_agent_instantiates():
    """PatientAgent can be created with station data."""
    station_data = {
        "patient_name": "John Smith",
        "patient_age": "55",
        "title": "Chest Pain",
        "station_script": "You have chest pain radiating to your left arm.",
    }
    agent = PatientAgent(station_data=station_data)

    assert "John Smith" in agent._instructions
    assert "55" in agent._instructions
    assert agent._consultation_ended is False


def test_patient_agent_default():
    """PatientAgent works with no station data (default patient)."""
    agent = PatientAgent()

    assert "Patient" in agent._instructions
    assert agent._station_data == {}


def test_patient_agent_has_function_tools():
    """PatientAgent has the expected @function_tool methods."""
    agent = PatientAgent()

    assert hasattr(agent, "request_examination")
    assert hasattr(agent, "end_consultation")


def test_build_case_brief_with_data():
    """_build_case_brief produces expected output with full station data (no truncation)."""
    long_instructions = "PMH: asthma. Meds: salbutamol. " * 50  # > 500 chars
    station_data = {
        "patient_name": "Emma Brown",
        "patient_age": "28",
        "candidate_instructions": long_instructions,
    }
    brief = _build_case_brief(station_data)

    assert "Emma Brown" in brief
    assert "28" in brief
    assert "asthma" in brief
    # Full content included (no truncation)
    assert len(brief) > 500
    assert brief.endswith(long_instructions)


def test_build_case_brief_without_data():
    """_build_case_brief produces fallback brief when no data."""
    brief = _build_case_brief(None)

    assert "Clinical consultation case" in brief
    assert "data gathering" in brief


def test_build_marking_criteria_with_data():
    """_build_marking_criteria extracts criteria from station data."""
    station_data = {
        "data_gathering": "Explore symptoms systematically.",
        "clinical_management": "Discuss management plan.",
        "relating_to_others": "Build rapport with patient.",
    }
    criteria = _build_marking_criteria(station_data)

    assert criteria is not None
    assert "Data Gathering Criteria" in criteria
    assert "Explore symptoms" in criteria
    assert "Clinical Management Criteria" in criteria
    assert "Interpersonal Skills Criteria" in criteria
    assert "Build rapport" in criteria


def test_build_marking_criteria_partial():
    """_build_marking_criteria handles partial criteria gracefully."""
    station_data = {
        "data_gathering": "Check red flags.",
    }
    criteria = _build_marking_criteria(station_data)

    assert criteria is not None
    assert "Data Gathering Criteria" in criteria
    assert "Clinical Management" not in criteria


def test_build_marking_criteria_none():
    """_build_marking_criteria returns None when no criteria available."""
    assert _build_marking_criteria(None) is None
    assert _build_marking_criteria({}) is None


def test_extract_transcript_empty():
    """_extract_transcript returns empty list for a mock session."""

    class MockItem:
        def __init__(self, type, role, text_content):
            self.type = type
            self.role = role
            self.text_content = text_content

    class MockHistory:
        def __init__(self, items):
            self.items = items

    class MockSession:
        def __init__(self, items):
            self.history = MockHistory(items)

    # Empty session
    session = MockSession([])
    transcript = _extract_transcript(session)
    assert transcript == []

    # Session with messages — provide timestamps
    timestamps = ["2026-01-01T10:00:00", "2026-01-01T10:01:00", "2026-01-01T10:02:00"]
    session = MockSession([
        MockItem("message", "user", "Hello doctor"),
        MockItem("message", "assistant", "Hello, how can I help?"),
        MockItem("function_call", None, None),
        MockItem("message", "user", "I have a headache"),
    ])
    transcript = _extract_transcript(session, timestamps)
    assert len(transcript) == 3
    assert transcript[0]["role"] == "user"
    assert transcript[0]["content"] == "Hello doctor"
    assert transcript[0]["timestamp"] == "2026-01-01T10:00:00"
    assert transcript[1]["role"] == "assistant"
    assert transcript[2]["content"] == "I have a headache"
