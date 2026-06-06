"""Marking prompt assembly.

Combines the verbatim Marking system prompt (Runtime Prompts, Prompt 2) with the
bundled RCGP feedback statement library and a per-run user message carrying the
full case pack and the transcript. Source of truth: FF SCA Feedback Engine Build
Package, Part 1 (all sections) and the Runtime Prompts file.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.prompts._runtime_prompts import MARKING_PROMPT
from app.prompts.rcgp_statements import EDUCATOR_NOTES, STATEMENT_TITLES


def ms_to_mmss(ms: int) -> str:
    """Format a millisecond offset as mm:ss."""
    total = max(0, int(ms)) // 1000
    return f"{total // 60:02d}:{total % 60:02d}"


def _speaker_label(turn: Dict[str, Any]) -> str:
    speaker = turn.get("speaker")
    if speaker == "candidate":
        return "Candidate"
    if speaker == "patient":
        return "Patient"
    # legacy shape: role user = the doctor (candidate), assistant = the patient
    role = turn.get("role")
    if role == "user":
        return "Candidate"
    if role == "assistant":
        return "Patient"
    return "Unknown"


def format_transcript(transcript: List[Dict[str, Any]]) -> str:
    """Render the transcript as speaker-labelled, timestamped lines for the model.

    Uses start_ms when present (the spec transcript shape); falls back to plain
    speaker labels for the legacy {role, content, timestamp} shape. A low ASR
    confidence on a candidate turn is annotated so the model can apply caution.
    """
    lines: List[str] = []
    for turn in transcript:
        label = _speaker_label(turn)
        text = (turn.get("text") or turn.get("content") or "").strip()
        if not text:
            continue
        prefix = ""
        if turn.get("start_ms") is not None:
            prefix = f"[{ms_to_mmss(turn['start_ms'])}] "
        conf = turn.get("asr_confidence")
        suffix = ""
        if isinstance(conf, (int, float)) and conf < 0.6 and label == "Candidate":
            suffix = "  (low transcription confidence)"
        lines.append(f"{prefix}{label}: {text}{suffix}")
    return "\n".join(lines)


def _statement_library_block() -> str:
    out = ["# RCGP FEEDBACK STATEMENT LIBRARY (anchor headings)"]
    domain_names = {
        "data_gathering": "Domain 1, Data gathering and diagnosis",
        "clinical_management": "Domain 2, Clinical management and medical complexity",
        "relating_to_others": "Domain 3, Relating to others",
    }
    for key, titles in STATEMENT_TITLES.items():
        out.append(f"\n{domain_names[key]}:")
        for i, title in enumerate(titles, 1):
            out.append(f"  {i}. {title}")
    return "\n".join(out)


def build_system_prompt() -> str:
    """Marking system prompt plus the bundled RCGP statement library and educator notes."""
    return (
        MARKING_PROMPT
        + "\n\n"
        + _statement_library_block()
        + "\n\n# RCGP EDUCATOR NOTES (Explanation, Suggestions, Capability areas; ground how_to_improve in these)\n"
        + EDUCATOR_NOTES
    )


def _mark_scheme_block(case_pack: Dict[str, Any]) -> str:
    parts: List[str] = []
    structured = case_pack.get("mark_scheme_structured")
    if structured:
        parts.append("# MARK SCHEME (structured indicators, Section 3.3)")
        parts.append(json.dumps(structured, ensure_ascii=False, indent=2))
    prose = case_pack.get("mark_scheme_prose") or {}
    if prose:
        parts.append("# MARK SCHEME (authored prose, by domain)")
        for dom, txt in prose.items():
            if txt:
                parts.append(f"## {dom}\n{txt}")
    return "\n".join(parts)


def build_marking_messages(
    case_pack: Dict[str, Any],
    transcript: List[Dict[str, Any]],
    ids: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build the [system, user] message list for one marking run."""
    features = case_pack.get("conditional_features") or {}
    user = "\n\n".join(
        [
            "SESSION\n"
            f"session_id: {ids.get('session_id')}\n"
            f"candidate_id: {ids.get('candidate_id')}\n"
            f"case_id: {ids.get('case_id')}",
            "# CANDIDATE BRIEF\n" + (case_pack.get("candidate_brief") or ""),
            "# PATIENT SCRIPT\n" + (case_pack.get("patient_script") or ""),
            _mark_scheme_block(case_pack),
            "# LEARNING POINTS (primary clinical source of truth)\n"
            + (case_pack.get("learning_points") or ""),
            "# CASE TYPE AND CONDITIONAL FEATURES\n"
            f"case_type: {case_pack.get('case_type')}\n"
            f"conditional_features: {json.dumps(features, ensure_ascii=False)}",
            "# TRANSCRIPT (speaker labelled, mm:ss)\n" + format_transcript(transcript),
            "Return only the JSON feedback object for this consultation, matching the agreed schema. "
            "Do not include any text outside the JSON.",
        ]
    )
    return [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": user},
    ]
