"""Trend report prompt assembly (Runtime Prompts Prompt 3).

Source of truth: FF SCA Feedback Engine Build Package, Section 13.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.prompts._runtime_prompts import TREND_PROMPT


def build_trend_messages(
    results: List[Dict[str, Any]], candidate_id: str
) -> List[Dict[str, str]]:
    """Build the [system, user] messages for one candidate's trend report."""
    user = "\n\n".join(
        [
            f"CANDIDATE: {candidate_id}\nCASES INCLUDED: {len(results)}",
            "# PERSISTED SINGLE-CASE RESULTS (grades, verdicts, anchored statements, "
            "consequence tiers, evidence; oldest first)\n"
            + json.dumps(results, ensure_ascii=False, default=str, indent=2),
            "Return only the JSON trend report for this candidate, matching the agreed "
            "schema. Do not include any text outside the JSON.",
        ]
    )
    return [
        {"role": "system", "content": TREND_PROMPT},
        {"role": "user", "content": user},
    ]
