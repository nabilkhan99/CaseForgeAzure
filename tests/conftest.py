"""Shared test fixtures.

`make_fat_result` builds a persisted ``session_results`` row at full size, prose
and coaching and evidence envelopes and all. Both the trend service tests (which
check what the slimmer throws away) and the trend schema tests (which check the
prompt names the keys the slimmer keeps) need the same row, and they need it to
be the real shape rather than two hand written approximations that drift.
"""
from __future__ import annotations

from typing import Any, Callable, Dict

import pytest

LONG_QUOTE = "so I just carried on with the cream she gave me last time " * 8


def build_fat_result(case_id: str = "derm") -> Dict[str, Any]:
    """One persisted result row, shaped like the real thing."""

    def _evidence() -> Dict[str, Any]:
        return {
            "quote": LONG_QUOTE,
            "speaker": "patient",
            "timestamp_ms": 570000,
            "evidence_kind": "supporting_quote",
        }

    return {
        "session_id": f"sess_{case_id}",
        "verdict": "Bare Fail",
        "weighted_score": 5.5,
        "one_line_summary": "Safe but thin management.",
        "created_at": "2026-06-03T10:00:00Z",
        "capability_links": ["Clinical Management"],
        "conditional_features": {"safeguarding": False, "complexity": True},
        "focus_areas": [
            {
                "priority": 1,
                "label": "Prescribing not current",
                "domain": "clinical_management",
                "narrative": "A long paragraph of per case coaching prose. " * 20,
            }
        ],
        "domains": [
            {
                "domain": "clinical_management",
                "display_name": "Clinical management and medical complexity",
                "grade": "F",
                "grade_points": 1,
                "max_points": 4.5,
                "weighted_points": 1.5,
                "is_weighted": True,
                "anchored_statements": [{"title": "The management plan was inappropriate."}],
                "what_you_did_well": [
                    {
                        "label": "Safety netted clearly",
                        "narrative": "More prose the candidate already read. " * 20,
                        "evidence": _evidence(),
                    }
                ],
                "what_you_missed": [
                    {
                        "indicator_id": "cm_04",
                        "label": "Potency of topical steroid",
                        "status": "not_met",
                        "consequence_tier": 2,
                        "narrative": "Yet more per case prose. " * 30,
                        "evidence": _evidence(),
                    }
                ],
                "cue_handling": [
                    {
                        "cue": "Worried about her job",
                        "status": "missed",
                        "narrative": "Prose. " * 30,
                        "evidence": _evidence(),
                    },
                    {
                        "cue": "Asked about steroids",
                        "status": "explored",
                        "narrative": "Prose. " * 30,
                        "evidence": _evidence(),
                    },
                ],
                "grade_mover": {"narrative": "How to move up a grade. " * 20},
                "model_moment": {"narrative": "What good looks like. " * 20, "source": "nice"},
                "how_to_improve": [
                    {"narrative": "Read the potency table. " * 20, "source": "learning_points"}
                ],
            }
        ],
        "clinical_sessions": {
            "station_id": f"station_{case_id}",
            "user_id": "cand_1",
            "completed_at": "2026-06-03T10:12:00Z",
            "stations": {"title": "Hand dermatitis"},
        },
    }


@pytest.fixture
def make_fat_result() -> Callable[..., Dict[str, Any]]:
    return build_fat_result
