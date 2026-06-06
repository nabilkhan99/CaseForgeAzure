"""Trend service: confidence gating by case count, no-dash, persistence.

Build Package Section 13.1: below three completed cases the report is low
confidence (strengths + provisional only). Dashes are stripped before persist.
"""
import json

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

    def get_candidate_results(self, candidate_id):
        return self._results

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
