"""Trend service: confidence gating by case count, no-dash, persistence.

Build Package Section 13.1: below three completed cases the report is low
confidence (strengths + provisional only). Dashes are stripped before persist.

Also covers the prompt size guards added after generate-trend returned 429:
the window cap, the slimmed per case payload, and the rate limit retry.
"""
import json

import pytest

from app.prompts.trend_prompt import (
    MAX_QUOTE_CHARS,
    MAX_TREND_CASES,
    build_trend_messages,
    slim_case_result,
)
from app.services.trend_service import TrendService


def _result(case_id, verdict="Bare Fail"):
    return {
        "session_id": f"sess_{case_id}",
        "verdict": verdict,
        "weighted_score": 5.5,
        "domains": [],
        "focus_areas": [],
        "capability_links": ["Clinical Management"],
        "created_at": "2026-06-03T10:00:00Z",
    }


def _model_report(confidence="high"):
    return {
        "candidate_id": "cand_1",
        "window": {"from": "2026-05-01", "to": "2026-06-03", "cases_included": 2},
        "confidence": confidence,
        "overall_trajectory": "static",
        "overall_narrative": "Management is a recurring weak-spot across cases.",
        "recurring_themes": [
            {
                "priority": 1,
                "theme_label": "Prescribing not current",
                "mapped_statement": "The management plan relating to prescribing of medication was inappropriate or not reflective of current practice.",
                "domain": "clinical_management",
                "frequency": 2,
                "max_consequence_tier": 2,
                "evidence": [{"case_id": "derm", "quote": "hydrocortisone 1 percent", "timestamp_ms": 570000}],
                "development_suggestion": {"narrative": "Check potency guidance for hand skin.", "source": "learning_points"},
            }
        ],
        "style_patterns": [],
        "consistent_strengths": [{"theme_label": "Empathy", "domain": "relating_to_others", "evidence_count": 2}],
        "next_steps": ["Review topical steroid potency."],
        "caution": "Based on 2 cases only, treat as provisional.",
    }


class FakeTrendRepo:
    def __init__(self, results):
        self._results = results
        self.saved = None
        self.limit_asked = None

    def get_candidate_results(self, candidate_id, limit=None):
        self.limit_asked = limit
        return self._results if limit is None else self._results[-limit:]

    def save_trend(self, candidate_id, payload):
        self.saved = (candidate_id, payload)


def _stub_model(response):
    async def _call(messages):
        return response
    return _call


async def test_below_three_cases_forced_low_confidence():
    repo = FakeTrendRepo([_result("a"), _result("b")])  # 2 cases
    svc = TrendService(repo, _stub_model(json.dumps(_model_report(confidence="high"))))
    report = await svc.generate("cand_1")
    assert report["confidence"] == "low"  # forced down despite the model saying high
    assert repo.saved[0] == "cand_1"


async def test_five_cases_keeps_model_confidence():
    repo = FakeTrendRepo([_result(str(i)) for i in range(5)])
    svc = TrendService(repo, _stub_model(json.dumps(_model_report(confidence="high"))))
    report = await svc.generate("cand_1")
    assert report["confidence"] == "high"


async def test_dashes_stripped_in_trend_output():
    repo = FakeTrendRepo([_result(str(i)) for i in range(5)])
    rep = _model_report()
    rep["overall_narrative"] = "weak spot 2-3 cases, self-employed context"
    svc = TrendService(repo, _stub_model(json.dumps(rep)))
    report = await svc.generate("cand_1")
    assert "2-3" not in json.dumps(report)
    assert "self-employed" not in json.dumps(report)


# ── prompt size guards ──

_LONG_QUOTE = "so I just carried on with the cream she gave me last time " * 8


def _fat_result(case_id="derm"):
    """A persisted result shaped like the real session_results row, prose and all."""
    def _evidence():
        return {
            "quote": _LONG_QUOTE,
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


def test_slim_case_result_keeps_pattern_signal():
    slim = slim_case_result(_fat_result())
    domain = slim["domains"][0]

    assert slim["case_id"] == "station_derm"
    assert slim["case_title"] == "Hand dermatitis"
    assert slim["completed_at"] == "2026-06-03T10:12:00Z"
    assert slim["verdict"] == "Bare Fail"
    assert slim["weighted_score"] == 5.5
    assert slim["one_line_summary"] == "Safe but thin management."
    assert slim["conditional_features"]["complexity"] is True
    assert slim["focus_areas"] == [
        {"priority": 1, "label": "Prescribing not current", "domain": "clinical_management"}
    ]

    assert domain["grade"] == "F"
    assert domain["anchored_statements"] == ["The management plan was inappropriate."]
    assert domain["did_well"] == ["Safety netted clearly"]
    assert domain["missed"][0]["label"] == "Potency of topical steroid"
    assert domain["missed"][0]["consequence_tier"] == 2
    assert domain["missed"][0]["status"] == "not_met"
    assert [c["cue"] for c in domain["cues"]] == ["Worried about her job", "Asked about steroids"]


def test_slim_case_result_strips_narrative_bulk():
    slim = slim_case_result(_fat_result())
    dumped = json.dumps(slim)
    domain = slim["domains"][0]

    # Per case prose and coaching: gone, the trend report writes its own.
    assert "narrative" not in dumped
    assert "prose" not in dumped.lower()
    for dropped in (
        "how_to_improve",
        "grade_mover",
        "model_moment",
        "display_name",
        "max_points",
        "is_weighted",
        "indicator_id",
        "evidence_kind",
        "speaker",
        "timestamp_ms",
    ):
        assert dropped not in dumped, dropped

    # Quotes survive only where the trend schema needs grounding, and clipped.
    assert domain["missed"][0]["quote"].endswith("...")
    assert len(domain["missed"][0]["quote"]) <= MAX_QUOTE_CHARS + 3
    assert "quote" in domain["cues"][0]  # missed cue keeps its quote
    assert "quote" not in domain["cues"][1]  # explored cue does not
    assert isinstance(domain["did_well"][0], str)  # strengths are labels only


def test_trend_prompt_caps_the_window_and_drops_indentation():
    fat = [_fat_result(f"case_{i}") for i in range(MAX_TREND_CASES + 8)]
    messages = build_trend_messages(fat, "cand_1")
    user = messages[1]["content"]
    payload = user.split("oldest first)\n", 1)[1].split("\n\n", 1)[0]
    cases = json.loads(payload)

    assert len(cases) == MAX_TREND_CASES
    # Most recent kept, oldest first preserved.
    assert cases[-1]["case_id"] == f"station_case_{len(fat) - 1}"
    assert f"CASES INCLUDED: {MAX_TREND_CASES}" in user

    # Compact separators: no indent whitespace anywhere in the JSON block.
    assert "\n" not in payload
    assert payload == json.dumps(cases, ensure_ascii=False, separators=(",", ":"))

    naive = json.dumps(fat, ensure_ascii=False, default=str, indent=2)
    assert len(payload) < len(naive) / 5


async def test_rate_limited_model_call_is_retried_once(monkeypatch):
    slept = []

    async def _fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("app.services.trend_service.asyncio.sleep", _fake_sleep)

    calls = {"n": 0}

    class _RateLimitError(Exception):
        status_code = 429

    async def _flaky(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _RateLimitError("429 requests to gpt-5.6-luna exceeded rate limit")
        return json.dumps(_model_report())

    repo = FakeTrendRepo([_result(str(i)) for i in range(5)])
    report = await TrendService(repo, _flaky).generate("cand_1")

    assert calls["n"] == 2
    assert slept == [20.0]
    assert report["confidence"] == "high"


async def test_non_rate_limit_error_is_not_retried():
    calls = {"n": 0}

    async def _boom(messages):
        calls["n"] += 1
        raise RuntimeError("azure endpoint not configured")

    repo = FakeTrendRepo([_result(str(i)) for i in range(5)])
    with pytest.raises(RuntimeError):
        await TrendService(repo, _boom).generate("cand_1")
    assert calls["n"] == 1


async def test_service_asks_the_repo_for_a_bounded_window():
    repo = FakeTrendRepo([_result(str(i)) for i in range(30)])
    await TrendService(repo, _stub_model(json.dumps(_model_report()))).generate("cand_1")
    assert repo.limit_asked == MAX_TREND_CASES
