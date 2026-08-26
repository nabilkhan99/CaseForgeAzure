"""Trend report prompt assembly (Runtime Prompts Prompt 3).

Source of truth: FF SCA Feedback Engine Build Package, Section 13.

The user turn used to be ``json.dumps(results, indent=2)`` over every persisted
single case result for the candidate. That is the whole marking output, evidence
quotes and per case coaching prose included, and it grew with every case sat, so
one request eventually exceeded the marking deployment's per minute token quota
and generate-trend answered 429 for everyone. Two guards below: a bounded window
(``MAX_TREND_CASES``) and a slimmed per case payload (``slim_case_result``).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.prompts._runtime_prompts import TREND_PROMPT

# The report is a picture of patterns across *recent* cases, so the window is
# bounded rather than "everything ever marked". Twelve is roughly a candidate's
# last month of practice and keeps the prompt flat as their history grows.
MAX_TREND_CASES = 12

# Evidence quotes are kept for the items that drive themes, but clipped: the
# pattern finder needs enough to recognise the moment, not the whole exchange.
MAX_QUOTE_CHARS = 200


def _first(value: Any) -> Optional[Dict[str, Any]]:
    """Normalise a PostgREST embed, which arrives as an object or a one item list."""
    if isinstance(value, list):
        return value[0] if value else None
    return value if isinstance(value, dict) else None


def _clip(text: Any, limit: int = MAX_QUOTE_CHARS) -> Optional[str]:
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def _compact(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Drop keys that carry no signal (None, empty string, empty list or dict)."""
    return {k: v for k, v in obj.items() if v not in (None, "", [], {})}


def _quote(item: Dict[str, Any]) -> Optional[str]:
    evidence = item.get("evidence") or {}
    if not isinstance(evidence, dict):
        return None
    return _clip(evidence.get("quote"))


def _slim_domain(domain: Dict[str, Any]) -> Dict[str, Any]:
    """One domain's grade plus the labels a pattern finder counts recurrence on.

    Kept: the grade and its points, the anchored RCGP statement titles, the
    labels of what was missed with status and consequence tier, cue handling
    status, the labels of what went well, and a clipped quote for the misses
    and missed cues only (the trend schema renders evidence, so those need to
    stay grounded rather than be invented).

    Stripped: every ``narrative`` (per case prose the candidate already read on
    their feedback report, and the single largest field here), ``how_to_improve``
    / ``grade_mover`` / ``model_moment`` (per case coaching the trend report
    replaces with its own suggestions), the evidence envelope around the quote
    (``speaker``, ``timestamp_ms``, ``evidence_kind``), quotes on the strengths
    and on explored cues, and derived display fields (``display_name``,
    ``max_points``, ``is_weighted``).
    """
    missed = []
    for item in domain.get("what_you_missed") or []:
        if not isinstance(item, dict):
            continue
        missed.append(
            _compact(
                {
                    "label": item.get("label"),
                    "status": item.get("status"),
                    "consequence_tier": item.get("consequence_tier"),
                    "quote": _quote(item),
                }
            )
        )

    cues = []
    for item in domain.get("cue_handling") or []:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        cues.append(
            _compact(
                {
                    "cue": item.get("cue"),
                    "status": status,
                    # Only a missed cue needs grounding; an explored one is a tick.
                    "quote": _quote(item) if status == "missed" else None,
                }
            )
        )

    return _compact(
        {
            "domain": domain.get("domain"),
            "grade": domain.get("grade"),
            "grade_points": domain.get("grade_points"),
            "weighted_points": domain.get("weighted_points"),
            "anchored_statements": [
                s.get("title")
                for s in domain.get("anchored_statements") or []
                if isinstance(s, dict) and s.get("title")
            ],
            "did_well": [
                w.get("label")
                for w in domain.get("what_you_did_well") or []
                if isinstance(w, dict) and w.get("label")
            ],
            "missed": missed,
            "cues": cues,
        }
    )


def slim_case_result(row: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce one persisted ``session_results`` row to its cross case signal.

    Everything the trend prompt asks for (grades, anchored statements,
    consequence tiers, evidence) survives; the per case narrative bulk does not.
    See ``_slim_domain`` for the field by field rationale.
    """
    session = _first(row.get("clinical_sessions")) or {}
    station = _first(session.get("stations")) or {}

    return _compact(
        {
            "case_id": session.get("station_id") or row.get("session_id"),
            "case_title": station.get("title"),
            "session_id": row.get("session_id"),
            "completed_at": session.get("completed_at") or row.get("created_at"),
            "verdict": row.get("verdict"),
            "weighted_score": row.get("weighted_score"),
            "one_line_summary": row.get("one_line_summary"),
            "capability_links": row.get("capability_links") or [],
            # Small flags object (safeguarding, complexity, ...); it is what lets
            # the model say a weakness clusters in one kind of presentation.
            "conditional_features": row.get("conditional_features") or {},
            "focus_areas": [
                _compact(
                    {
                        "priority": f.get("priority"),
                        "label": f.get("label"),
                        "domain": f.get("domain"),
                    }
                )
                for f in row.get("focus_areas") or []
                if isinstance(f, dict)
            ],
            "domains": [
                _slim_domain(d) for d in row.get("domains") or [] if isinstance(d, dict)
            ],
        }
    )


def slim_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Most recent ``MAX_TREND_CASES`` results, slimmed, still oldest first.

    The repo already caps the fetch; this is the belt and braces cap so no caller
    can put an unbounded window in front of the model.
    """
    recent = [r for r in results if isinstance(r, dict)][-MAX_TREND_CASES:]
    return [slim_case_result(r) for r in recent]


def build_trend_messages(
    results: List[Dict[str, Any]], candidate_id: str
) -> List[Dict[str, str]]:
    """Build the [system, user] messages for one candidate's trend report."""
    cases = slim_results(results)
    user = "\n\n".join(
        [
            f"CANDIDATE: {candidate_id}\nCASES INCLUDED: {len(cases)}"
            f" (most recent cases, window capped at {MAX_TREND_CASES})",
            "# PERSISTED SINGLE-CASE RESULTS (grades, verdicts, anchored statements, "
            "consequence tiers, evidence; oldest first)\n"
            # Separators, not indent: the pretty printing was pure token cost.
            + json.dumps(
                cases, ensure_ascii=False, default=str, separators=(",", ":")
            ),
            "Return only the JSON trend report for this candidate, matching the agreed "
            "schema. Do not include any text outside the JSON.",
        ]
    )
    return [
        {"role": "system", "content": TREND_PROMPT},
        {"role": "user", "content": user},
    ]
