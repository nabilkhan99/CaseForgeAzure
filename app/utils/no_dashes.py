"""Post-generation no-dash enforcement for all generated feedback output.

Source: FF SCA Feedback Engine Build Package Section 9.3 and the README house
rule. No dashes anywhere in generated output: numeric ranges become "to", and
every other dash becomes a comma or a space. Covers hyphen-minus, en dash, em
dash, figure dash, horizontal bar, and the unicode minus sign.

`enforce_no_dashes` rewrites a value (str, or nested dict/list of strings) and
guarantees no dash character survives. `find_dashes` reports offending paths for
logging or assertions before persisting.
"""
from __future__ import annotations

import re
from typing import Any, List, Tuple

# Every dash-like codepoint we refuse to emit.
DASH_CHARS = "-‐‑‒–—―−"
_DASH_CLASS = re.escape(DASH_CHARS)

_NUMERIC_RANGE = re.compile(rf"(?<=\d)\s*[{_DASH_CLASS}]+\s*(?=\d)")
_WORD_COMPOUND = re.compile(rf"(?<=\w)[{_DASH_CLASS}](?=\w)")
_REMAINING = re.compile(rf"\s*[{_DASH_CLASS}]+\s*")
_ANY_DASH = re.compile(rf"[{_DASH_CLASS}]")


def _clean_str(s: str) -> str:
    # 1. numeric ranges: "2-3" -> "2 to 3"
    s = _NUMERIC_RANGE.sub(" to ", s)
    # 2. intra-word compounds: "self-employed" -> "self employed"
    s = _WORD_COMPOUND.sub(" ", s)
    # 3. anything left (spaced, doubled, or edge dashes) -> comma
    s = _REMAINING.sub(", ", s)
    # 4. tidy: drop any stray dash, collapse spaces, fix spacing around commas
    s = _ANY_DASH.sub("", s)
    s = re.sub(r"\s{2,}", " ", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r"^[,\s]+", "", s)
    return s.strip()


def enforce_no_dashes(value: Any) -> Any:
    """Recursively strip dashes from a string or nested dict/list, returning a new value."""
    if isinstance(value, str):
        return _clean_str(value)
    if isinstance(value, dict):
        return {k: enforce_no_dashes(v) for k, v in value.items()}
    if isinstance(value, list):
        return [enforce_no_dashes(v) for v in value]
    if isinstance(value, tuple):
        return tuple(enforce_no_dashes(v) for v in value)
    return value


def find_dashes(value: Any, path: str = "") -> List[Tuple[str, str]]:
    """Return (path, offending_string) for every string still containing a dash."""
    hits: List[Tuple[str, str]] = []
    if isinstance(value, str):
        if _ANY_DASH.search(value):
            hits.append((path or "<root>", value))
    elif isinstance(value, dict):
        for k, v in value.items():
            child = f"{path}.{k}" if path else str(k)
            hits.extend(find_dashes(v, child))
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            hits.extend(find_dashes(v, f"{path}[{i}]"))
    return hits
