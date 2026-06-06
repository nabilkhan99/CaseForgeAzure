"""Marking prompt assembly (Runtime Prompts Prompt 2 + RCGP library + case pack)."""
from app.prompts.marking_prompt import (
    ms_to_mmss,
    format_transcript,
    build_system_prompt,
    build_marking_messages,
)


def test_ms_to_mmss():
    assert ms_to_mmss(64000) == "01:04"
    assert ms_to_mmss(0) == "00:00"
    assert ms_to_mmss(605000) == "10:05"


def test_format_transcript_new_shape():
    turns = [
        {"speaker": "candidate", "start_ms": 4000, "text": "Hello, tell me what is going on."},
        {"speaker": "patient", "start_ms": 18000, "text": "My hands are cracking."},
    ]
    out = format_transcript(turns)
    assert "[00:04] Candidate: Hello, tell me what is going on." in out
    assert "[00:18] Patient: My hands are cracking." in out


def test_format_transcript_legacy_shape():
    turns = [
        {"role": "user", "content": "Hi", "timestamp": "2026-06-03T10:00:00Z"},
        {"role": "assistant", "content": "Hello doctor", "timestamp": "2026-06-03T10:00:05Z"},
    ]
    out = format_transcript(turns)
    assert "Candidate: Hi" in out
    assert "Patient: Hello doctor" in out


def test_system_prompt_carries_rules_and_library():
    sp = build_system_prompt()
    assert "RCGP Simulated Consultation Assessment examiner" in sp
    assert "Bare Pass" in sp
    assert "No dashes" in sp
    # a known D2 anchor title is present in the bundled library
    assert "prescribing of medication was inappropriate" in sp
    # educator notes bundled
    assert "Capability area" in sp


def test_build_marking_messages_shape():
    case_pack = {
        "candidate_brief": "Patient: Sophie Miller, 29. Hands worsening.",
        "patient_script": "Opening line: I am worried about my hands.",
        "mark_scheme_prose": {"data_gathering": "Occupational history...", "clinical_management": "Potent steroid...", "relating_to_others": "Empathy..."},
        "mark_scheme_structured": {"domains": []},
        "learning_points": "Potent topical corticosteroid required.",
        "case_type": "patient_direct",
        "conditional_features": {"safeguarding": False, "consent_capacity": False, "complexity": False, "third_party": False},
    }
    transcript = [{"speaker": "candidate", "start_ms": 4000, "text": "Hello Sophie."}]
    ids = {"session_id": "sess_1", "candidate_id": "cand_1", "case_id": "derm_sophie_miller"}
    msgs = build_marking_messages(case_pack, transcript, ids)
    assert [m["role"] for m in msgs] == ["system", "user"]
    user = msgs[1]["content"]
    assert "Sophie Miller" in user
    assert "derm_sophie_miller" in user
    assert "Hello Sophie." in user
    assert "patient_direct" in user
