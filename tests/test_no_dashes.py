"""No-dash house rule, post-generation enforcement.

Source: Build Package Section 9.3 and the README house rule. No dashes anywhere
in generated output. Numeric ranges use the word "to"; everything else uses
commas, spaces, or restructuring. Covers hyphen-minus, en dash, and em dash.
"""
from app.utils.no_dashes import clean_prose, enforce_no_dashes, find_dashes, DASH_CHARS


def test_numeric_range_becomes_to():
    assert enforce_no_dashes("review in 2-3 weeks") == "review in 2 to 3 weeks"


def test_em_dash_spaced_becomes_comma():
    assert enforce_no_dashes("strong history — weak management") == "strong history, weak management"


def test_letter_compound_loses_hyphen():
    assert enforce_no_dashes("self-employed mother") == "self employed mother"


def test_en_dash_numeric_range():
    assert enforce_no_dashes("6–7 minutes") == "6 to 7 minutes"


def test_clean_string_unchanged():
    s = "A caring consultation with strong history taking."
    assert enforce_no_dashes(s) == s


def test_recurses_into_dict_and_list():
    payload = {
        "one_line_summary": "held back 2-3 ways",
        "domains": [
            {"narrative": "well-managed", "score": 5},
            {"narrative": "fine"},
        ],
        "flag": True,
        "n": 10,
    }
    cleaned = enforce_no_dashes(payload)
    assert cleaned["one_line_summary"] == "held back 2 to 3 ways"
    assert cleaned["domains"][0]["narrative"] == "well managed"
    assert cleaned["domains"][0]["score"] == 5
    assert cleaned["flag"] is True
    assert cleaned["n"] == 10


def test_no_dash_chars_remain_after_enforce():
    messy = "a-b – c—d 1-2"
    out = enforce_no_dashes(messy)
    assert not any(d in out for d in DASH_CHARS)


def test_clean_prose_is_the_single_string_entry_point():
    assert clean_prose("review in 2-3 weeks") == "review in 2 to 3 weeks"


def test_clean_prose_passes_non_strings_through():
    """So a caller walking a payload can name a field without type checking it."""
    for value in (None, 5, 5.5, True, ["a-b"], {"k": "a-b"}):
        assert clean_prose(value) is value


def test_enforce_no_dashes_cannot_tell_an_identifier_from_prose():
    """Pinning the reason the trend path does not use it.

    This is not a bug in enforce_no_dashes, it is its contract: every string is
    prose. Anything holding UUIDs, dates, or verbatim quotes needs a walk that
    knows which fields are which, e.g. trend_service.enforce_trend_no_dashes.
    """
    mangled = enforce_no_dashes(
        {"candidate_id": "56454120-2d2c-4b1a-9f3e-5f0a3b1c7d99", "date": "2026-06-17"}
    )
    assert mangled["candidate_id"] != "56454120-2d2c-4b1a-9f3e-5f0a3b1c7d99"
    assert mangled["date"] == "2026 to 06 to 17"


def test_find_dashes_reports_paths():
    payload = {"a": "clean", "b": ["x-y", "ok"], "c": {"d": "1–2"}}
    hits = find_dashes(payload)
    paths = {p for p, _ in hits}
    assert "b[0]" in paths
    assert "c.d" in paths
    assert "a" not in paths
