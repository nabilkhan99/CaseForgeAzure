"""TrendReport tolerates the two prompt/schema drifts seen on the first live run.

The model emitted `label` for `theme_label` and a bare sentence for
`development_suggestion`, which raised 8 validation errors across
style_patterns[0..3] and cost the whole report. The prompt now names the exact
keys; these tests pin the fallback, and pin that the canonical spellings and the
serialised contract are unchanged.
"""
import pytest
from pydantic import ValidationError

from app.schemas.trend import ConsistentStrength, Theme, TrendReport


def test_bare_string_development_suggestion_is_coerced():
    theme = Theme(
        theme_label="Premature closure",
        development_suggestion="After the opening, use a wider funnel before narrowing.",
    )
    assert theme.development_suggestion.narrative.startswith("After the opening")
    # No provenance to read from a bare sentence, so it is attributed, not guessed.
    assert theme.development_suggestion.source == "rcgp_educator_notes"


def test_development_suggestion_object_keeps_its_own_source():
    theme = Theme(
        theme_label="Prescribing not current",
        development_suggestion={"narrative": "Check potency guidance.", "source": "nice"},
    )
    assert theme.development_suggestion.source == "nice"


def test_development_suggestion_object_without_source_is_attributed():
    theme = Theme(
        theme_label="Rushed management",
        development_suggestion={"narrative": "Leave four minutes for the plan."},
    )
    assert theme.development_suggestion.source == "rcgp_educator_notes"


def test_empty_development_suggestion_becomes_none():
    assert Theme(theme_label="x", development_suggestion="   ").development_suggestion is None


def test_label_is_accepted_as_an_alias_for_theme_label():
    assert Theme(label="Closed questioning").theme_label == "Closed questioning"
    assert Theme(theme_label="Closed questioning").theme_label == "Closed questioning"
    assert ConsistentStrength(label="Empathy").theme_label == "Empathy"


def test_theme_label_is_still_required():
    # The alias tolerates a different spelling, it does not make the field optional.
    with pytest.raises(ValidationError):
        Theme(domain="data_gathering")


def test_fully_aliased_payload_validates_and_serialises_canonically():
    """The live 500, reproduced: `label` plus a bare-string suggestion throughout."""
    raw = {
        "candidate_id": "cand_1",
        "confidence": "medium",
        "overall_trajectory": "static",
        "overall_narrative": "Data gathering narrows too early.",
        "recurring_themes": [
            {
                "priority": 1,
                "label": "Prescribing not current",
                "domain": "clinical_management",
                "frequency": 3,
                "max_consequence_tier": 2,
                "evidence": [{"case_id": "derm", "quote": "hydrocortisone 1 percent"}],
                "development_suggestion": "Check potency guidance for hand skin.",
            }
        ],
        "style_patterns": [
            {"label": "Premature closure", "development_suggestion": "Funnel wider first."},
            {"label": "Closed questioning", "development_suggestion": "Open with an invitation."},
            {"label": "Weak opening", "development_suggestion": "Practise the first thirty seconds."},
            {"label": "Missed cues", "development_suggestion": "Name the worry out loud."},
        ],
        "consistent_strengths": [{"label": "Empathy", "evidence_count": 3}],
        "next_steps": ["Practise open funnelling."],
        "caution": "Based on 4 cases, treat as provisional.",
    }

    report = TrendReport(**raw)
    dumped = report.model_dump(by_alias=True)

    assert [t["theme_label"] for t in dumped["style_patterns"]] == [
        "Premature closure",
        "Closed questioning",
        "Weak opening",
        "Missed cues",
    ]
    assert dumped["consistent_strengths"][0]["theme_label"] == "Empathy"
    assert dumped["recurring_themes"][0]["development_suggestion"]["narrative"].startswith(
        "Check potency"
    )
    # Serialisation is untouched: the alias is validation only, so what the DB
    # and the frontend read is still theme_label, never label.
    for section in ("recurring_themes", "style_patterns", "consistent_strengths"):
        for item in dumped[section]:
            assert "theme_label" in item
            assert "label" not in item


# ── the prompt and the schema must name the same keys ──

# candidate_id is stamped server side by TrendService, never asked of the model.
# timestamp_ms is deliberately absent: the slimmed case payload no longer carries
# timestamps, so asking the model for one would be asking it to invent one.
_NOT_ASKED_OF_THE_MODEL = {"candidate_id", "timestamp_ms"}


def test_trend_prompt_names_every_schema_key():
    """The drift that caused the live 500 was prose that named no keys at all."""
    from app.prompts._runtime_prompts import TREND_PROMPT
    from app.schemas.trend import DevelopmentSuggestion, ThemeEvidence, TrendWindow

    models = (TrendReport, Theme, ConsistentStrength, DevelopmentSuggestion,
              ThemeEvidence, TrendWindow)
    expected = {
        (field.alias or name)
        for model in models
        for name, field in model.model_fields.items()
    } - _NOT_ASKED_OF_THE_MODEL

    missing = sorted(key for key in expected if f'"{key}"' not in TREND_PROMPT)
    assert not missing, f"TREND_PROMPT never names these schema keys: {missing}"


def test_trend_prompt_warns_off_the_two_observed_drifts():
    from app.prompts._runtime_prompts import TREND_PROMPT

    assert 'never "label"' in TREND_PROMPT
    assert "never a bare string" in TREND_PROMPT
