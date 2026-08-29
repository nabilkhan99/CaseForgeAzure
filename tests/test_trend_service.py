"""TrendService: the case gate, the stamped window, the house rule, persistence.

Also covers the input side guards that survive from v1, because they are what
stopped generate-trend returning 429 for everyone: the bounded window, the
slimmed per case payload, and the rate limit retry.
"""
import json
import logging

import pytest

from app.prompts.trend_prompt import (
    MAX_QUOTE_CHARS,
    MAX_TREND_CASES,
    build_trend_messages,
    input_quotes,
    slim_case_result,
    window_for,
)
from app.services.trend_service import (
    MIN_CASES_FOR_PATTERNS,
    InsufficientCases,
    TrendService,
    enforce_trend_no_dashes,
)

CANDIDATE = "56454120-2d2c-4b1a-9f3e-5f0a3b1c7d99"
CASE_ID = "11111111-2222-3333-4444-555555555555"
QUOTE = "so I just carried on with the cream she gave me last time"


def _result(case_id, completed_at="2026-06-03T10:00:00Z", weighted_score=5.5):
    """A marked case, slim enough to read, with one quotable missed item."""
    return {
        "session_id": f"sess_{case_id}",
        "verdict": "Bare Fail",
        "weighted_score": weighted_score,
        "capability_links": ["Clinical Management"],
        "created_at": completed_at,
        "domains": [
            {
                "domain": "clinical_management",
                "grade": "F",
                "what_you_missed": [
                    {
                        "label": "Potency of topical steroid",
                        "status": "not_met",
                        "consequence_tier": 2,
                        "evidence": {
                            "quote": QUOTE,
                            "speaker": "patient",
                            "evidence_kind": "patient_cue",
                        },
                    }
                ],
            }
        ],
        "clinical_sessions": {
            "station_id": case_id,
            "user_id": CANDIDATE,
            "completed_at": completed_at,
            "stations": {"title": "Hand dermatitis"},
        },
    }


def _results(n=5):
    return [
        _result(CASE_ID if i == 0 else f"{CASE_ID[:-1]}{i}", f"2026-0{i + 1}-01T10:00:00Z")
        for i in range(n)
    ]


def _model_report(**overrides):
    """What a well behaved model returns: v2, three fields of prose, one quote."""
    base = {
        "version": 2,
        "candidate_id": "whatever-the-model-felt-like",
        "window": {"cases_included": 99, "from": "1999-01-01", "to": "1999-01-02"},
        "overall_trajectory": "steady",
        "overall_narrative": "Your data gathering is holding up; the plan is where marks go.",
        "patterns": [
            {
                "headline": "Close with a complete plan",
                "domain": "clinical_management",
                "frequency": 3,
                "your_quote": QUOTE,
                "quote_gloss": "The consultation ends with no review point.",
                "model_line": "Use it twice a day for two weeks, and come back sooner if it cracks.",
                "model_gloss": "Treatment, safety net, then review.",
                "the_change": "Keep the last two minutes for the plan, which moves management to Pass.",
                "evidence": [{"case_id": CASE_ID, "quote": QUOTE}],
            }
        ],
    }
    return {**base, **overrides}


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


async def _generate(results, report=None):
    repo = FakeTrendRepo(results)
    svc = TrendService(repo, _stub_model(json.dumps(report or _model_report())))
    return repo, await svc.generate(CANDIDATE)


# ── the gate ──


@pytest.mark.parametrize("n", [0, 1, 2])
async def test_below_the_minimum_no_report_is_built(n):
    """Two cases are two cases. The model is not asked, and nothing is saved."""
    repo = FakeTrendRepo(_results(n))

    async def _never_called(messages):  # pragma: no cover - asserted by not raising
        raise AssertionError("the model was called below the case gate")

    with pytest.raises(InsufficientCases) as excinfo:
        await TrendService(repo, _never_called).generate(CANDIDATE)

    assert excinfo.value.cases_available == n
    assert excinfo.value.cases_required == MIN_CASES_FOR_PATTERNS
    assert repo.saved is None


async def test_at_the_minimum_a_report_is_built():
    _repo, report = await _generate(_results(MIN_CASES_FOR_PATTERNS))
    assert len(report["patterns"]) == 1


# ── what the service owns rather than the model ──


async def test_candidate_id_and_window_are_stamped_over_the_model():
    results = _results(5)
    _repo, report = await _generate(results)

    assert report["candidate_id"] == CANDIDATE  # not the model's answer
    assert report["window"] == {
        "cases_included": 5,
        "from": "2026-01-01T10:00:00Z",
        "to": "2026-05-01T10:00:00Z",
    }


async def test_version_is_stamped_when_the_model_omits_it():
    payload = _model_report()
    payload.pop("version")
    _repo, report = await _generate(_results(5), payload)
    assert report["version"] == 2


async def test_a_v1_shaped_answer_is_rejected_rather_than_saved():
    v1 = {
        "confidence": "high",
        "overall_trajectory": "static",
        "overall_narrative": "n",
        "recurring_themes": [{"theme_label": "Prescribing"}],
    }
    repo = FakeTrendRepo(_results(5))
    with pytest.raises(Exception):
        await TrendService(repo, _stub_model(json.dumps(v1))).generate(CANDIDATE)
    assert repo.saved is None


async def test_the_report_is_saved_under_the_candidate_id():
    repo, report = await _generate(_results(5))
    assert repo.saved == (CANDIDATE, report)


async def test_service_asks_the_repo_for_a_bounded_window():
    repo, _report = await _generate([_result(f"c{i}") for i in range(30)])
    assert repo.limit_asked == MAX_TREND_CASES


# ── the house rule, applied to prose and to nothing else ──


async def test_dashes_are_stripped_from_the_prose_the_model_wrote():
    payload = _model_report()
    payload["overall_narrative"] = "a weak spot in 2-3 cases, self-employed context"
    payload["patterns"][0]["the_change"] = "Re-order the last two minutes."
    _repo, report = await _generate(_results(5), payload)

    assert report["overall_narrative"] == "a weak spot in 2 to 3 cases, self employed context"
    assert report["patterns"][0]["the_change"] == "Re order the last two minutes."


async def test_uuids_dates_and_quotes_survive_the_house_rule_untouched():
    """The v1 bug: a recursive rewrite turned the candidate id into prose.

    v1 emitted "56454120 to 2d2c to 4b1a..." for the candidate id and
    "2026 to 06 to 17" for a date, and quietly re-punctuated every quote, which
    is worse: a quote that has been tidied is no longer verbatim.
    """
    hyphenated_quote = "it was hit-and-miss, so I left it 2-3 weeks"
    payload = _model_report()
    payload["patterns"][0]["your_quote"] = hyphenated_quote
    payload["patterns"][0]["evidence"] = [
        {"case_id": CASE_ID, "quote": hyphenated_quote}
    ]
    _repo, report = await _generate(_results(5), payload)

    assert report["candidate_id"] == CANDIDATE
    assert report["window"]["from"] == "2026-01-01T10:00:00Z"
    assert report["window"]["to"] == "2026-05-01T10:00:00Z"
    assert report["patterns"][0]["evidence"][0]["case_id"] == CASE_ID
    assert report["patterns"][0]["your_quote"] == hyphenated_quote
    assert report["patterns"][0]["evidence"][0]["quote"] == hyphenated_quote


def test_enforce_trend_no_dashes_touches_only_the_named_prose_fields():
    payload = {
        "version": 2,
        "candidate_id": CANDIDATE,
        "window": {"cases_included": 3, "from": "2026-06-17", "to": "2026-08-29"},
        "overall_trajectory": "improving",
        "overall_narrative": "up 2-3 points",
        "patterns": [
            {
                "headline": "Re-open the history",
                "domain": "data_gathering",
                "frequency": 2,
                "your_quote": "it's hit-and-miss",
                "quote_gloss": "A closed-question run.",
                "model_line": "What's been going through your mind?",
                "model_gloss": "Open-ended invitation.",
                "the_change": "Funnel wide-to-narrow.",
                "evidence": [{"case_id": CASE_ID, "quote": "hit-and-miss"}],
            }
        ],
    }
    cleaned = enforce_trend_no_dashes(payload)
    pattern = cleaned["patterns"][0]

    assert cleaned["overall_narrative"] == "up 2 to 3 points"
    assert pattern["headline"] == "Re open the history"
    assert pattern["quote_gloss"] == "A closed question run."
    assert pattern["model_gloss"] == "Open ended invitation."
    assert pattern["the_change"] == "Funnel wide to narrow."

    assert pattern["your_quote"] == "it's hit-and-miss"
    assert pattern["evidence"][0]["quote"] == "hit-and-miss"
    assert pattern["evidence"][0]["case_id"] == CASE_ID
    assert cleaned["candidate_id"] == CANDIDATE
    assert cleaned["window"] == payload["window"]
    assert cleaned["version"] == 2 and cleaned["overall_trajectory"] == "improving"

    # A new payload, not an edited one.
    assert payload["overall_narrative"] == "up 2-3 points"


# ── quote grounding ──


async def test_an_invented_quote_is_logged_against_the_pattern(caplog):
    payload = _model_report()
    payload["patterns"][0]["your_quote"] = "a line the candidate never said"

    with caplog.at_level(logging.WARNING, logger="app.services.trend_service"):
        await _generate(_results(5), payload)

    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("never said" in w and "Close with a complete plan" in w for w in warnings)


async def test_a_grounded_quote_logs_nothing(caplog):
    with caplog.at_level(logging.WARNING, logger="app.services.trend_service"):
        await _generate(_results(5))
    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


def test_input_quotes_are_exactly_what_the_model_can_copy(make_fat_result):
    quotes = input_quotes([make_fat_result()])
    slim = slim_case_result(make_fat_result())

    # The missed indicator and the missed cue; never the explored cue, and never
    # a strength (slimmed down to a label).
    assert quotes == {slim["domains"][0]["missed"][0]["quote"],
                      slim["domains"][0]["cues"][0]["quote"]}


def test_window_for_reads_the_dates_off_the_rows():
    assert window_for(_results(3)) == {
        "cases_included": 3,
        "from": "2026-01-01T10:00:00Z",
        "to": "2026-03-01T10:00:00Z",
    }
    assert window_for([]) == {"cases_included": 0, "from": None, "to": None}


# ── prompt size guards, carried over from the 429 fix ──


def test_slim_case_result_keeps_pattern_signal(make_fat_result):
    slim = slim_case_result(make_fat_result())
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


def test_slim_case_result_strips_narrative_bulk(make_fat_result):
    slim = slim_case_result(make_fat_result())
    dumped = json.dumps(slim)
    domain = slim["domains"][0]

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
        "timestamp_ms",
    ):
        assert dropped not in dumped, dropped

    # The speaker is the one envelope field that survives, beside its quote:
    # v2 prefers quoting the patient, and the model cannot prefer what it
    # cannot see.
    quoted = [m for m in domain["missed"] if m.get("quote")]
    assert quoted and all(m.get("speaker") in ("patient", "candidate") for m in quoted)

    assert domain["missed"][0]["quote"].endswith("...")
    assert len(domain["missed"][0]["quote"]) <= MAX_QUOTE_CHARS + 3
    assert "quote" in domain["cues"][0]  # missed cue keeps its quote
    assert "quote" not in domain["cues"][1]  # explored cue does not
    assert isinstance(domain["did_well"][0], str)


def test_trend_prompt_caps_the_window_and_drops_indentation(make_fat_result):
    fat = [make_fat_result(f"case_{i}") for i in range(MAX_TREND_CASES + 8)]
    messages = build_trend_messages(fat, CANDIDATE)
    user = messages[1]["content"]
    payload = user.split("oldest first)\n", 1)[1].split("\n\n", 1)[0]
    cases = json.loads(payload)

    assert len(cases) == MAX_TREND_CASES
    assert cases[-1]["case_id"] == f"station_case_{len(fat) - 1}"
    assert f"CASES INCLUDED: {MAX_TREND_CASES}" in user
    assert CANDIDATE in user

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

    repo = FakeTrendRepo(_results(5))
    report = await TrendService(repo, _flaky).generate(CANDIDATE)

    assert calls["n"] == 2
    assert slept == [20.0]
    assert report["version"] == 2


async def test_malformed_json_is_retried_once():
    calls = {"n": 0}

    async def _flaky(messages):
        calls["n"] += 1
        return "here you go: {oops" if calls["n"] == 1 else json.dumps(_model_report())

    repo = FakeTrendRepo(_results(5))
    report = await TrendService(repo, _flaky).generate(CANDIDATE)
    assert calls["n"] == 2
    assert report["patterns"][0]["headline"] == "Close with a complete plan"


async def test_non_rate_limit_error_is_not_retried():
    calls = {"n": 0}

    async def _boom(messages):
        calls["n"] += 1
        raise RuntimeError("azure endpoint not configured")

    repo = FakeTrendRepo(_results(5))
    with pytest.raises(RuntimeError):
        await TrendService(repo, _boom).generate(CANDIDATE)
    assert calls["n"] == 1


# ── the point of v2: a small report ──


async def test_the_generated_report_is_small():
    """v1 ran to roughly eight thousand generated characters; v2 targets under two."""
    payload = _model_report()
    payload["patterns"] = payload["patterns"] * 3
    _repo, report = await _generate(_results(5), payload)

    generated = len(report["overall_narrative"]) + sum(
        len(p[f])
        for p in report["patterns"]
        for f in ("headline", "quote_gloss", "model_line", "model_gloss", "the_change")
    )
    assert generated < 2000
