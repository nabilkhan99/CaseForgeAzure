"""Portfolio output privacy and age formatting (build spec section 8).

Section 8b is a data protection requirement: this output is pasted straight into
an RCGP ePortfolio, so no patient or colleague name may reach it. Section 8a is a
house style rule ("63 year old", never "63-year-old") that the prompt alone does
not enforce reliably, hence the regex backstop.

Three generation paths exist and all three are covered here, because the
frontend calls improve_section live: a name or a hyphenated age stripped by
generate-review can otherwise be reintroduced by an improve call.
"""
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from app.config import Settings
from app.services.portfolio_prompts import (
    PORTFOLIO_PRIVACY_RULES,
    with_portfolio_privacy_rules,
)
from app.services.portfolio_service import PortfolioService
from app.utils.no_dashes import enforce_no_dashes
from app.utils.text_processing import find_name_title_patterns, strip_age_hyphens


# ---------------------------------------------------------------------------
# 8a: the age backstop
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("a 42-year-old man", "a 42 year old man"),
        ("a 4-year-old boy", "a 4 year old boy"),
        ("a 7-month-old infant", "a 7 month old infant"),
        ("a 6-week-old baby", "a 6 week old baby"),
        ("a 3-day-old neonate", "a 3 day old neonate"),
    ],
)
def test_strip_age_hyphens_covers_years_months_weeks_and_days(raw, expected):
    assert strip_age_hyphens(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("A 42-Year-Old man", "A 42 Year Old man"),
        ("a 6-WEEK-OLD baby", "a 6 WEEK OLD baby"),
        ("a 68-Year-old woman", "a 68 Year old woman"),
    ],
)
def test_strip_age_hyphens_preserves_casing(raw, expected):
    """Casing is preserved rather than normalised, so prose is not disturbed."""
    assert strip_age_hyphens(raw) == expected


def test_strip_age_hyphens_rewrites_every_occurrence():
    raw = "I saw a 42-year-old man, then a 6-week-old baby, then an 89-year-old woman."
    assert strip_age_hyphens(raw) == (
        "I saw a 42 year old man, then a 6 week old baby, then an 89 year old woman."
    )


def test_strip_age_hyphens_handles_multi_digit_ages():
    assert strip_age_hyphens("a 103-year-old patient") == "a 103 year old patient"


@pytest.mark.parametrize(
    "untouched",
    [
        "I prescribed co-amoxiclav 625mg three times a day.",
        "He is self-employed and could not take time off.",
        "I arranged a follow-up in two weeks.",
        "Her father-in-law drove her to the surgery.",
        "We used a two-week-wait referral.",
        "The out-of-hours service saw her overnight.",
        "an old man of 42",
        "a year-long wait",
    ],
)
def test_strip_age_hyphens_leaves_clinical_and_ordinary_hyphens_alone(untouched):
    """The whole point of the narrow pattern.

    "two-week-wait" is the sharpest case: it contains a number word and an age
    word but not the trailing "old", so the pattern cannot reach it.
    """
    assert strip_age_hyphens(untouched) == untouched


def test_strip_age_hyphens_is_not_enforce_no_dashes():
    """Pinning why app.utils.no_dashes must not be reused on portfolio prose.

    enforce_no_dashes strips every intra-word hyphen, so it de-hyphenates drug
    names. The Portfolio prompt calls that a clinical error. This is not a bug
    in enforce_no_dashes, it is its contract; it is simply the wrong tool here.
    """
    prose = "I prescribed co-amoxiclav to a 42-year-old man."

    assert strip_age_hyphens(prose) == "I prescribed co-amoxiclav to a 42 year old man."
    assert "co amoxiclav" in enforce_no_dashes(prose)


def test_strip_age_hyphens_rejects_non_strings():
    with pytest.raises(TypeError):
        strip_age_hyphens(None)


# ---------------------------------------------------------------------------
# 8b: the name pattern review flag
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I discussed the case with Dr Smith.", ["Dr Smith"]),
        ("I discussed the case with Dr O'Rourke.", ["Dr O'Rourke"]),
        ("Dr. Patel reviewed the notes.", ["Dr. Patel"]),
        ("Mrs Johnson attended with her daughter.", ["Mrs Johnson"]),
        ("Mr Ahmed was seen in clinic.", ["Mr Ahmed"]),
        ("Ms Okafor called back.", ["Ms Okafor"]),
        ("Miss Chen declined the referral.", ["Miss Chen"]),
        ("Prof Williams gave a second opinion.", ["Prof Williams"]),
        ("Sister Amara escorted the patient.", ["Sister Amara"]),
        ("Nurse Bailey took the observations.", ["Nurse Bailey"]),
    ],
)
def test_find_name_title_patterns_flags_titles_followed_by_a_name(text, expected):
    assert find_name_title_patterns(text) == expected


def test_find_name_title_patterns_reports_each_distinct_hit_once_in_order():
    text = "Dr Smith called Mrs Johnson. Dr Smith then rang Dr Ellis."
    assert find_name_title_patterns(text) == ["Dr Smith", "Mrs Johnson", "Dr Ellis"]


@pytest.mark.parametrize(
    "safe",
    [
        # The replacement conventions the prompt actually asks for.
        "I discussed the case with a senior colleague.",
        "The practice nurse took the observations.",
        "I asked the duty doctor to review her.",
        "Her daughter drove her to the surgery.",
        "The pharmacist flagged the interaction.",
        # Roles that happen to start with a title word.
        "The Nurse Practitioner reviewed the results.",
        "I spoke to the Nurse In Charge.",
        "The Practice Manager arranged the appointment.",
        "A Clinical Nurse Specialist was involved.",
        # A title with no name after it.
        "I was the duty dr that afternoon.",
        "",
    ],
)
def test_find_name_title_patterns_is_false_positive_safe(safe):
    """A flag nobody trusts gets ignored, so role phrases must not fire it."""
    assert find_name_title_patterns(safe) == []


def test_find_name_title_patterns_rejects_non_strings():
    with pytest.raises(TypeError):
        find_name_title_patterns(None)


# ---------------------------------------------------------------------------
# Prompt content: pin the rules inside the 450 line prompt string
# ---------------------------------------------------------------------------

SETTINGS = Settings()


def _flat(text: str) -> str:
    """Collapse whitespace, so a prompt reflow cannot fail a content assertion."""
    return " ".join(text.split())


def test_system_prompt_still_bans_hyphenated_ages():
    assert 'Ages without hyphens ("63 year old man", not "63-year-old man").' in SETTINGS.SYSTEM_PROMPT


def test_system_prompt_still_protects_clinical_hyphens():
    assert "co-amoxiclav" in SETTINGS.SYSTEM_PROMPT


@pytest.mark.parametrize(
    "clause",
    [
        "never carry any name into the output",
        "Never substitute an initial",
        "pseudonym",
        "Patient A",
        "[name]",
        "preserve the distinction between them by role or relationship",
        "date of birth, NHS number, address, postcode",
        "omit them from the output entirely",
    ],
)
def test_system_prompt_carries_the_full_name_suppression_rule(clause):
    """Spec 8b. A future edit to the prompt must not silently drop any of these."""
    assert clause in _flat(SETTINGS.SYSTEM_PROMPT)


@pytest.mark.parametrize(
    "clause",
    [
        "Never include personal names in your output",
        "patients, relatives, carers, doctors, nurses, pharmacists",
        "named practices, surgeries, hospitals and trusts",
        "Never substitute an initial, a pseudonym, or a placeholder",
        '"Patient A" or "[name]"',
        "preserve the distinction between them using role or relationship",
        "date of birth, NHS number, address or postcode",
        "Never hyphenate age expressions",
        'Never write "42-year-old"',
        "co-amoxiclav",
    ],
)
def test_shared_privacy_rules_carry_every_spec_clause(clause):
    assert clause in _flat(PORTFOLIO_PRIVACY_RULES)


def test_with_portfolio_privacy_rules_appends_and_keeps_the_base_prompt():
    combined = with_portfolio_privacy_rules("BASE PROMPT")
    assert combined.startswith("BASE PROMPT")
    assert PORTFOLIO_PRIVACY_RULES.strip() in combined


# ---------------------------------------------------------------------------
# The few-shot examples must not teach what the rules forbid
# ---------------------------------------------------------------------------

LIVE_FEW_SHOT_ATTRS = [
    "IMPROVEMENT_EXAMPLE_1",
    "IMPROVEMENT_REQUEST_1",
    "IMPROVEMENT_RESPONSE_1",
    "IMPROVEMENT_EXAMPLE_2",
    "IMPROVEMENT_REQUEST_2",
    "IMPROVEMENT_RESPONSE_2",
]


@pytest.mark.parametrize("attr", LIVE_FEW_SHOT_ATTRS)
def test_live_few_shot_examples_contain_no_hyphenated_ages(attr):
    text = getattr(SETTINGS, attr)
    assert strip_age_hyphens(text) == text


@pytest.mark.parametrize("attr", LIVE_FEW_SHOT_ATTRS)
def test_live_few_shot_examples_contain_no_title_plus_name(attr):
    assert find_name_title_patterns(getattr(SETTINGS, attr)) == []


@pytest.mark.parametrize("attr", LIVE_FEW_SHOT_ATTRS)
def test_live_few_shot_examples_use_no_patient_initial_or_named_hospital(attr):
    """The two leaks these examples used to teach the model directly."""
    text = getattr(SETTINGS, attr)
    assert "patient VH" not in text
    assert "VH " not in text
    assert "Ravenswood" not in text


@pytest.mark.parametrize(
    "attr", ["IMPROVEMENT_EXAMPLE_3", "IMPROVEMENT_REQUEST_3", "IMPROVEMENT_RESPONSE_3"]
)
def test_dead_third_example_is_gone(attr):
    """Deleted rather than fixed: never referenced, and full of hyphenated ages.

    Leaving a dead example in place invites someone to wire it in later.
    """
    assert not hasattr(SETTINGS, attr)


# ---------------------------------------------------------------------------
# All three service paths
# ---------------------------------------------------------------------------


class _FakeCompletions:
    """Returns canned completions in order and records the messages it was sent."""

    def __init__(self, responses: List[str]):
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        content = self._responses.pop(0) if self._responses else "Case Review"
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class _FakeClient:
    def __init__(self, responses: List[str]):
        self.completions = _FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


class _RecordingAuditLogger:
    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    def record(self, **kwargs: Any) -> None:
        self.rows.append(kwargs)


def _service(responses: List[str]) -> PortfolioService:
    service = PortfolioService.__new__(PortfolioService)
    service.settings = SETTINGS
    service.openai_client = _FakeClient(responses)
    service.audit_logger = _RecordingAuditLogger()
    service.capabilities = {}
    return service


REVIEW_WITH_HYPHENATED_AGE = """Brief description:
I saw a 42-year-old man with chest pain and prescribed co-amoxiclav.

Capability: Clinical management and medical complexity
Justification: I arranged a 6-week-old review of the plan.

Reflection:
It went well.

Learning needs identified from this event:
Read the chest pain guidance."""


def _system_prompt_of(service: PortfolioService) -> str:
    return service.openai_client.completions.calls[0]["messages"][0]["content"]


async def test_generate_case_review_cleans_ages_and_carries_privacy_rules():
    service = _service([REVIEW_WITH_HYPHENATED_AGE, "Chest pain review"])

    response = await service.generate_case_review(
        case_description="Notes about a man with chest pain.",
        selected_capabilities=["Clinical management and medical complexity"],
    )

    assert "42 year old" in response.review_content
    assert "6 week old" in response.review_content
    assert "-year-old" not in response.review_content
    # the clinical hyphen survives
    assert "co-amoxiclav" in response.review_content
    assert PORTFOLIO_PRIVACY_RULES.strip() in _system_prompt_of(service)


async def test_generate_case_review_keeps_privacy_rules_under_a_prompt_override():
    """The playground can replace the whole system prompt; it cannot drop these."""
    service = _service([REVIEW_WITH_HYPHENATED_AGE, "Chest pain review"])

    await service.generate_case_review(
        case_description="Notes about a man with chest pain.",
        selected_capabilities=["Clinical management and medical complexity"],
        system_prompt_override="Write whatever you like.",
        enforce_output_contract=True,
    )

    assert PORTFOLIO_PRIVACY_RULES.strip() in _system_prompt_of(service)


async def test_improve_case_review_cleans_ages_and_carries_privacy_rules():
    service = _service([REVIEW_WITH_HYPHENATED_AGE, "Chest pain review"])

    response = await service.improve_case_review(
        original_case="Existing review text",
        improvement_prompt="Add more detail",
        selected_capabilities=["Clinical management and medical complexity"],
    )

    assert "42 year old" in response.review_content
    assert "-year-old" not in response.review_content
    assert "co-amoxiclav" in response.review_content
    assert PORTFOLIO_PRIVACY_RULES.strip() in _system_prompt_of(service)


async def test_improve_section_cleans_ages_and_carries_privacy_rules():
    """The path with no cleanup at all before this change, and the one the UI calls live."""
    service = _service(["  I reviewed a 6-week-old baby and a 42-year-old man.  "])

    improved = await service.improve_section(
        section_type="brief_description",
        section_content="I reviewed a baby.",
        improvement_prompt="Add the ages",
    )

    assert improved == "I reviewed a 6 week old baby and a 42 year old man."
    assert PORTFOLIO_PRIVACY_RULES.strip() in _system_prompt_of(service)


async def test_improve_section_records_an_audit_row():
    service = _service(["Improved text."])

    await service.improve_section(
        section_type="reflection",
        section_content="Old text.",
        improvement_prompt="Make it fuller",
    )

    assert [row["operation"] for row in service.audit_logger.rows] == ["improve_section"]


async def test_name_pattern_flag_is_logged_and_never_mutates_the_output(caplog):
    service = _service(["I handed over to Dr O'Rourke, who agreed the plan."])

    with caplog.at_level("WARNING"):
        improved = await service.improve_section(
            section_type="reflection",
            section_content="I handed over.",
            improvement_prompt="Say who to",
        )

    # flagged...
    assert "Dr O'Rourke" in caplog.text
    assert "flagged for review" in caplog.text
    # ...but the trainee's text is returned untouched
    assert improved == "I handed over to Dr O'Rourke, who agreed the plan."


async def test_clean_output_raises_no_name_flag(caplog):
    service = _service(["I handed over to the duty doctor, who agreed the plan."])

    with caplog.at_level("WARNING"):
        await service.improve_section(
            section_type="reflection",
            section_content="I handed over.",
            improvement_prompt="Say who to",
        )

    assert "flagged for review" not in caplog.text
