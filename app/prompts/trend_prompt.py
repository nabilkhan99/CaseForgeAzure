"""Trend report prompt assembly (Runtime Prompts Prompt 3).

Input side plumbing for the v2 trend contract. The system turn is TREND_PROMPT;
everything here builds the user turn that goes with it.

The user turn used to be ``json.dumps(results, indent=2)`` over every persisted
single case result for the candidate. That is the whole marking output, evidence
quotes and per case coaching prose included, and it grew with every case sat, so
one request eventually exceeded the marking deployment's per minute token quota
and generate-trend answered 429 for everyone. Two guards below: a bounded window
(``MAX_TREND_CASES``) and a slimmed per case payload (``slim_case_result``).

What survives the slimming is what v2 asks the model for: the grades and scores
and dates it judges trajectory from, the labels it counts recurrence on, and the
quotes it must copy verbatim. v2 needs no field v1 did not already keep, so the
slimming is unchanged from the shape that fixed the 429.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set

from app.prompts._runtime_prompts import TREND_PROMPT

# The report is a picture of patterns across *recent* cases, so the window is
# bounded rather than "everything ever marked" — one oversized request used to
# blow the deployment's per minute token quota. Twenty (raised from twelve for
# a more holistic read; the window grows with the candidate until it hits this)
# keeps the prompt flat as their history grows.
MAX_TREND_CASES = 20

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


# Who may be quoted, and which marking evidence kinds are NOT spoken words.
# The marking engine uses the quote field for two different things: real
# transcript lines (speaker = patient or candidate, kind = patient_cue) and its
# own descriptive stand-ins for moments with nothing to quote (not_asked,
# no_direct_quote, or no speaker at all). Only the first kind may reach the
# trend model: a report that "quotes" the examiner's commentary back at the
# candidate reads as fabricated, because to the candidate it is.
_QUOTE_SPEAKERS = ("patient", "candidate")
_NON_SPOKEN_KINDS = ("not_asked", "no_direct_quote")


def _spoken_quote(item: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """(quote, speaker) when the evidence is words someone actually said."""
    evidence = item.get("evidence") or {}
    if not isinstance(evidence, dict):
        return None, None
    speaker = evidence.get("speaker")
    if speaker not in _QUOTE_SPEAKERS:
        return None, None
    if evidence.get("evidence_kind") in _NON_SPOKEN_KINDS:
        return None, None
    quote = _clip(evidence.get("quote"))
    return (quote, speaker) if quote else (None, None)


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
    (``timestamp_ms``, ``evidence_kind`` — ``speaker`` is kept, and quotes that
    are not actually spoken words are dropped, see ``_spoken_quote``), quotes on
    the strengths
    and on explored cues, and derived display fields (``display_name``,
    ``max_points``, ``is_weighted``).
    """
    missed = []
    for item in domain.get("what_you_missed") or []:
        if not isinstance(item, dict):
            continue
        quote, speaker = _spoken_quote(item)
        missed.append(
            _compact(
                {
                    "label": item.get("label"),
                    "status": item.get("status"),
                    "consequence_tier": item.get("consequence_tier"),
                    "quote": quote,
                    "speaker": speaker,
                }
            )
        )

    cues = []
    for item in domain.get("cue_handling") or []:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        quote, speaker = _spoken_quote(item) if status == "missed" else (None, None)
        cues.append(
            _compact(
                {
                    "cue": item.get("cue"),
                    "status": status,
                    # Only a missed cue needs grounding; an explored one is a tick.
                    "quote": quote,
                    "speaker": speaker,
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


def window_for(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The authoritative ``window`` block for a report over these results.

    Computed from the rows actually fetched rather than taken from the model's
    answer. The candidate reads this as fact, and dates are exactly the field a
    language model will helpfully round, reformat, or invent outright. The
    contract still asks the model for a window so the shape it returns is
    complete; TrendService overwrites it with this.
    """
    cases = slim_results(results)
    dates = sorted(
        str(c["completed_at"]) for c in cases if c.get("completed_at")
    )
    return {
        "cases_included": len(cases),
        "from": dates[0] if dates else None,
        "to": dates[-1] if dates else None,
    }


def input_quotes(results: List[Dict[str, Any]]) -> Set[str]:
    """Every quote the model is allowed to reproduce, exactly as it will see it.

    The two places a quote can come from are a missed indicator and a missed
    cue (see ``_slim_domain``). TrendService checks the model's quotes against
    this set so an invented one is visible in the logs rather than served to the
    candidate as their own words.
    """
    quotes: Set[str] = set()
    for case in slim_results(results):
        for domain in case.get("domains") or []:
            for item in list(domain.get("missed") or []) + list(domain.get("cues") or []):
                quote = item.get("quote")
                if isinstance(quote, str) and quote:
                    quotes.add(quote)
    return quotes


def build_trend_messages(
    results: List[Dict[str, Any]], candidate_id: str
) -> List[Dict[str, str]]:
    """Build the [system, user] messages for one candidate's trend report."""
    cases = slim_results(results)
    user = "\n\n".join(
        [
            f"CANDIDATE: {candidate_id}\nCASES INCLUDED: {len(cases)}"
            f" (most recent cases, window capped at {MAX_TREND_CASES})",
            "# MARKED CASES (grades, scores, dates, anchored statements, missed "
            "items and cues with their quotes; oldest first)\n"
            # Separators, not indent: the pretty printing was pure token cost.
            + json.dumps(
                cases, ensure_ascii=False, default=str, separators=(",", ":")
            ),
            f'Return only the version 2 JSON trend report for candidate '
            f'{candidate_id}. Copy every quote and every case_id from the cases '
            f"above exactly. Do not include any text outside the JSON.",
        ]
    )
    return [
        {"role": "system", "content": TREND_PROMPT},
        {"role": "user", "content": user},
    ]
