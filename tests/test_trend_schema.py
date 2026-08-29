"""The v2 trend contract, and the prompt that has to describe it.

The frontend Development page is built to this exact shape, so these tests are
the contract in executable form: the fields, the bounds, and the guarantee that
a v1 payload cannot be quietly accepted as a half filled v2 report.
"""
import pytest
from pydantic import ValidationError

from app.schemas.trend import (
    TREND_SCHEMA_VERSION,
    TrendEvidence,
    TrendPattern,
    TrendReport,
    TrendWindow,
)


def _pattern(**overrides):
    base = {
        "headline": "Close with a complete plan",
        "domain": "clinical_management",
        "frequency": 3,
        "your_quote": "so just carry on with the cream and see how you go",
        "quote_gloss": "The consultation ends without a review point or a red flag.",
        "model_line": (
            "Use the ointment twice a day for two weeks. If the skin cracks or "
            "starts weeping, come back sooner, and either way let us see you in a "
            "month to check it is settling."
        ),
        "model_gloss": "It names the treatment, the safety net, then the review.",
        "the_change": (
            "Reserve the last two minutes for the plan, which is what moves "
            "clinical management from Fail to Pass."
        ),
        "evidence": [
            {"case_id": "11111111-1111-1111-1111-111111111111", "quote": "so just carry on"}
        ],
    }
    return {**base, **overrides}


def _report(**overrides):
    base = {
        "candidate_id": "56454120-2d2c-4b1a-9f3e-000000000000",
        "window": {"cases_included": 5, "from": "2026-06-17", "to": "2026-08-29"},
        "overall_trajectory": "improving",
        "overall_narrative": "You are gathering more than you were in June.",
        "patterns": [_pattern()],
    }
    return {**base, **overrides}


def test_minimal_valid_report_round_trips():
    report = TrendReport(**_report())
    dumped = report.model_dump(by_alias=True)

    assert dumped["version"] == TREND_SCHEMA_VERSION
    assert dumped["window"]["from"] == "2026-06-17"  # alias, not from_
    assert dumped["patterns"][0]["headline"] == "Close with a complete plan"
    assert dumped["patterns"][0]["evidence"][0]["quote"] == "so just carry on"


def test_version_defaults_to_two_and_rejects_anything_else():
    assert TrendReport(**_report()).version == TREND_SCHEMA_VERSION
    assert TrendReport(**_report(), version=2).version == 2
    with pytest.raises(ValidationError):
        TrendReport(**{**_report(), "version": 1})


def test_a_v1_payload_does_not_validate_as_a_half_report():
    """The failure this guards: v1 shares no required field with v2."""
    v1 = {
        "candidate_id": "cand_1",
        "confidence": "medium",
        "overall_trajectory": "static",
        "overall_narrative": "Data gathering narrows too early.",
        "recurring_themes": [{"theme_label": "Prescribing not current"}],
        "next_steps": ["Practise open funnelling."],
        "caution": "Based on 4 cases.",
    }
    with pytest.raises(ValidationError):
        TrendReport(**v1)


@pytest.mark.parametrize("count", [0, 4])
def test_patterns_are_bounded_to_one_through_three(count):
    with pytest.raises(ValidationError):
        TrendReport(**_report(patterns=[_pattern() for _ in range(count)]))


@pytest.mark.parametrize("count", [1, 2, 3])
def test_one_two_or_three_patterns_are_accepted(count):
    report = TrendReport(**_report(patterns=[_pattern() for _ in range(count)]))
    assert len(report.patterns) == count


@pytest.mark.parametrize("count", [0, 5])
def test_evidence_is_bounded_to_one_through_four(count):
    evidence = [{"case_id": f"case_{i}", "quote": "q"} for i in range(count)]
    with pytest.raises(ValidationError):
        TrendPattern(**_pattern(evidence=evidence))


def test_trajectory_and_domain_are_closed_vocabularies():
    with pytest.raises(ValidationError):
        TrendReport(**_report(overall_trajectory="static"))  # v1's word
    with pytest.raises(ValidationError):
        TrendPattern(**_pattern(domain="interpersonal_skills"))

    for trajectory in ("improving", "steady", "declining"):
        assert TrendReport(**_report(overall_trajectory=trajectory))
    for domain in ("data_gathering", "clinical_management", "relating_to_others"):
        assert TrendPattern(**_pattern(domain=domain))


def test_every_pattern_field_is_required():
    for field in _pattern():
        partial = {k: v for k, v in _pattern().items() if k != field}
        with pytest.raises(ValidationError):
            TrendPattern(**partial)


def test_the_report_is_immutable_once_built():
    """Nothing downstream edits a validated report; v1's confidence floor did."""
    report = TrendReport(**_report())
    with pytest.raises(ValidationError):
        report.overall_trajectory = "declining"


def test_window_accepts_the_contract_spelling_and_the_field_name():
    assert TrendWindow(cases_included=3, **{"from": "2026-01-01"}).from_ == "2026-01-01"
    assert TrendWindow(cases_included=3, from_="2026-01-01").from_ == "2026-01-01"


def test_dead_v1_models_are_gone():
    """Ripped out, not deprecated: an import of one should fail loudly."""
    import app.schemas.trend as trend_schema

    for dead in ("Theme", "ThemeEvidence", "ConsistentStrength", "DevelopmentSuggestion",
                 "Confidence", "Source"):
        assert not hasattr(trend_schema, dead), dead


# ── the prompt and the schema must describe the same contract ──

# candidate_id and window are stamped server side by TrendService. The prompt
# still names both, because the model returns a complete object and the contract
# it is shown is the contract in full.
_STAMPED_SERVER_SIDE = {"candidate_id", "window"}


def test_trend_prompt_names_every_schema_key():
    """The v1 bug (commit 0ab0412) was a prompt naming keys that did not exist."""
    from app.prompts._runtime_prompts import TREND_PROMPT

    models = (TrendReport, TrendPattern, TrendEvidence, TrendWindow)
    expected = {
        (field.alias or name)
        for model in models
        for name, field in model.model_fields.items()
    }

    missing = sorted(key for key in expected if f'"{key}"' not in TREND_PROMPT)
    assert not missing, f"TREND_PROMPT never names these schema keys: {missing}"
    assert _STAMPED_SERVER_SIDE <= expected


def test_trend_prompt_names_the_input_keys_the_model_is_actually_given(make_fat_result):
    """The other half of 0ab0412: describing input fields that are not sent.

    Every key named here is one slim_case_result really emits, checked against a
    slimmed case rather than against a list written from memory.
    """
    from app.prompts._runtime_prompts import TREND_PROMPT
    from app.prompts.trend_prompt import slim_case_result

    slim = slim_case_result(make_fat_result())
    keys = set(slim) | set(slim["domains"][0]) | {"label", "status", "consequence_tier",
                                                  "quote", "cue"}

    missing = sorted(key for key in keys if f'"{key}"' not in TREND_PROMPT)
    assert not missing, f"TREND_PROMPT never names these input keys: {missing}"


def test_trend_prompt_carries_the_v2_rules_and_none_of_v1():
    from app.prompts._runtime_prompts import TREND_PROMPT

    lowered = TREND_PROMPT.lower()
    assert "verbatim" in lowered
    assert "at most three" in lowered
    assert '"version": 2' in TREND_PROMPT

    for dead in ("theme_label", "style_patterns", "next_steps", "consistent_strengths",
                 "development_suggestion", "max_consequence_tier", "mapped_statement",
                 "capability_area", "context_pattern", "confidence"):
        assert dead not in TREND_PROMPT, f"v1 leftover in TREND_PROMPT: {dead}"
