"""
Tests for patient prompt building logic.

Pure unit tests — no API keys or external services required.
"""

from ai_agents.patient import build_patient_prompt, PATIENT_PROMPT_TEMPLATE


def test_build_patient_prompt_with_station_data():
    """build_patient_prompt injects station data into template."""
    station_data = {
        "patient_name": "Sarah Thompson",
        "patient_age": "34",
        "title": "Headache Assessment",
        "station_script": "You have been experiencing severe headaches for 2 weeks.",
        "candidate_instructions": "PMH: migraine. Meds: paracetamol PRN.",
    }

    prompt = build_patient_prompt(station_data)

    # Patient identity injected
    assert "Sarah Thompson" in prompt
    assert "34" in prompt

    # Case context injected
    assert "Headache Assessment" in prompt
    assert "severe headaches" in prompt
    assert "migraine" in prompt

    # Template structure preserved
    assert "# Role & Objective" in prompt
    assert "# Personality & Tone" in prompt
    assert "# Safety" in prompt


def test_build_patient_prompt_without_station_data():
    """build_patient_prompt returns default prompt when no data provided."""
    prompt = build_patient_prompt(None)

    assert "Patient" in prompt  # default name
    assert "adult" in prompt  # default age
    assert "# Role & Objective" in prompt


def test_build_patient_prompt_partial_station_data():
    """build_patient_prompt handles partial station data gracefully."""
    station_data = {
        "title": "Back Pain",
        # missing patient_name, patient_age, station_script, candidate_instructions
    }

    prompt = build_patient_prompt(station_data)

    # Falls back to defaults for missing fields
    assert "Patient" in prompt  # default name
    assert "adult" in prompt  # default age
    assert "Back Pain" in prompt  # title still used


def test_prompt_contains_conversation_flow():
    """Prompt includes all conversation flow phases."""
    prompt = build_patient_prompt()

    assert "## 1) Waiting" in prompt
    assert "## 2) Opening" in prompt
    assert "## 3) History" in prompt
    assert "## 4) Examination" in prompt
    assert "## 5) Management & Closure" in prompt


def test_prompt_has_safety_section():
    """Prompt includes safety instructions."""
    prompt = build_patient_prompt()

    assert "NEVER break character" in prompt
    assert "ALWAYS respond in English" in prompt
