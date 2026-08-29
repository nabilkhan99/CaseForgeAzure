"""Trend service: the cross case development report for one candidate.

Reads the persisted single case outputs, asks the model for the few habits that
are costing the most marks, and never re grades a case. The contract it produces
is version 2 (app/schemas/trend.py): at most three patterns, each pairing one
verbatim quote from the candidate's own consultations with what a model answer
sounds like at that same moment.

Three things this service owns beyond the model call:

- The gate. Below MIN_CASES_FOR_PATTERNS there is no cross case pattern to find,
  only a single case restated, so the model is never asked. The caller gets
  InsufficientCases and decides what to tell the candidate.
- The window. Counts and dates are stamped from the rows actually fetched, not
  taken from the model's answer.
- The house rule. Dashes are stripped from the prose the model wrote and from
  nothing else (see enforce_trend_no_dashes).

The case window is capped and each case is slimmed before it reaches the model
(see app/prompts/trend_prompt.py). A single oversized request was blowing the
marking deployment's per minute token quota, so every trend request came back
429 while marking on the same deployment carried on fine.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Tuple

from app.prompts.trend_prompt import (
    MAX_TREND_CASES,
    build_trend_messages,
    input_quotes,
    window_for,
)
from app.schemas.trend import TREND_SCHEMA_VERSION, TrendReport
from app.services.marking_service import ModelCall, parse_model_json
from app.utils.no_dashes import clean_prose

logger = logging.getLogger(__name__)

# Two cases are two cases, not a trend. Below this the endpoint reports that it
# skipped the build rather than spending a minute of model time on a report that
# would say "you did this once".
MIN_CASES_FOR_PATTERNS = 3

# Backoff schedule for a rate-limited model call: one retry, then give up and
# let the endpoint return the error. A trend report is not worth holding an
# Azure Functions HTTP request open for longer than this.
RATE_LIMIT_BACKOFF_SECONDS = (20.0,)

# The fields the model actually writes, and therefore the only fields the
# no-dash house rule may touch. Everything else in the payload is either an
# identifier, a date, an enum, a number, or a quote.
#
# The v1 service ran enforce_no_dashes over the entire payload. That rewrote the
# candidate's own UUID ("56454120 to 2d2c...") and every ISO date
# ("2026 to 06 to 17"), and it rewrote the quotes, which is the worse damage: a
# quote with its punctuation edited is no longer the candidate's words, and
# verbatim quoting is the whole premise of the v2 report.
REPORT_PROSE_FIELDS: Tuple[str, ...] = ("overall_narrative",)
PATTERN_PROSE_FIELDS: Tuple[str, ...] = (
    "headline",
    "quote_gloss",
    "model_line",
    "model_gloss",
    "the_change",
)


class InsufficientCases(Exception):
    """Raised instead of building a report the data cannot support.

    Carries the counts so the HTTP layer can tell the candidate how many more
    cases they need without going back to the database for them.
    """

    def __init__(self, candidate_id: str, cases_available: int) -> None:
        self.candidate_id = candidate_id
        self.cases_available = cases_available
        self.cases_required = MIN_CASES_FOR_PATTERNS
        super().__init__(
            f"candidate {candidate_id} has {cases_available} marked cases; "
            f"{MIN_CASES_FOR_PATTERNS} are needed for a trend report"
        )


def enforce_trend_no_dashes(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the no-dash house rule to model-authored prose only.

    An explicit walk over the v2 shape rather than a recursive rewrite of every
    string: see REPORT_PROSE_FIELDS for why the recursive version was wrong.
    Returns a new payload; the input is not modified.

    Deliberately untouched: ``candidate_id`` and every ``case_id`` (UUIDs),
    ``window`` (ISO dates and a count), ``version``, ``domain``,
    ``overall_trajectory`` and ``frequency`` (enums and numbers), and
    ``your_quote`` and every evidence ``quote`` (the candidate's and the
    patient's own words, which are reproduced or they are not quotes).
    """
    cleaned: Dict[str, Any] = {
        key: clean_prose(value) if key in REPORT_PROSE_FIELDS else value
        for key, value in payload.items()
    }
    patterns = payload.get("patterns")
    if isinstance(patterns, list):
        cleaned["patterns"] = [
            {
                key: clean_prose(value) if key in PATTERN_PROSE_FIELDS else value
                for key, value in pattern.items()
            }
            if isinstance(pattern, dict)
            else pattern
            for pattern in patterns
        ]
    return cleaned


def _is_rate_limited(exc: BaseException) -> bool:
    """True for an Azure OpenAI 429.

    Matched structurally rather than by importing openai, because the model call
    is injected here (marking_service.make_azure_model_call builds the real one)
    and this service is unit-tested with a plain async stub. openai>=1 raises
    RateLimitError with status_code 429; the string check covers wrappers that
    re-raise the message only.
    """
    if getattr(exc, "status_code", None) == 429:
        return True
    if type(exc).__name__ == "RateLimitError":
        return True
    text = str(exc).lower()
    return "429" in text or "rate limit" in text


class TrendService:
    def __init__(self, repo: Any, model_call: ModelCall):
        self.repo = repo
        self.model_call = model_call

    async def _call_model(self, messages: List[Dict[str, str]]) -> str:
        """One model call, retried on a 429 per RATE_LIMIT_BACKOFF_SECONDS."""
        attempts = len(RATE_LIMIT_BACKOFF_SECONDS) + 1
        for attempt in range(attempts):
            try:
                return await self.model_call(messages)
            except Exception as exc:  # noqa: BLE001 - re-raised unless retryable
                if attempt == attempts - 1 or not _is_rate_limited(exc):
                    raise
                delay = RATE_LIMIT_BACKOFF_SECONDS[attempt]
                logger.warning(
                    "Trend model call rate limited (%s); retrying in %.0fs.", exc, delay
                )
                await asyncio.sleep(delay)
        raise RuntimeError("unreachable")  # pragma: no cover

    async def _get_report_json(self, messages: List[Dict[str, str]]) -> dict:
        raw = await self._call_model(messages)
        try:
            return parse_model_json(raw)
        except ValueError:
            logger.warning("Trend model returned malformed JSON; retrying once.")
            raw = await self._call_model(messages)
            return parse_model_json(raw)

    def _log_unverified_quotes(
        self, report: TrendReport, results: List[Dict[str, Any]]
    ) -> None:
        """Warn about any quote that is not character for character in the input.

        Not a rejection. A near miss is usually the model trimming a trailing
        ellipsis rather than fabricating a moment, and losing the whole report
        over it serves nobody. But an invented quote is the one failure mode of
        this contract that a candidate cannot detect and would rightly be angry
        about, so it is never allowed to pass silently.
        """
        allowed = input_quotes(results)
        strays = [
            (pattern.headline, quote)
            for pattern in report.patterns
            for quote in [pattern.your_quote, *(e.quote for e in pattern.evidence)]
            if quote not in allowed
        ]
        for headline, quote in strays:
            logger.warning(
                "Trend report for candidate %s quotes text absent from the input "
                "under pattern %r: %r",
                report.candidate_id,
                headline,
                quote[:120],
            )

    async def generate(self, candidate_id: str) -> dict:
        results = self.repo.get_candidate_results(candidate_id, limit=MAX_TREND_CASES) or []
        if len(results) < MIN_CASES_FOR_PATTERNS:
            raise InsufficientCases(candidate_id, len(results))

        messages = build_trend_messages(results, candidate_id)

        # Logged before the call so a future quota failure is diagnosable from
        # App Insights alone: chars is the honest number, tokens the rough guide.
        prompt_chars = sum(len(m["content"]) for m in messages)
        logger.info(
            "Trend prompt for candidate %s: %d cases, %d chars (roughly %d tokens).",
            candidate_id,
            len(results),
            prompt_chars,
            prompt_chars // 4,
        )

        data = await self._get_report_json(messages)
        # Stamped, not requested: the id is ours and the window is arithmetic
        # over rows we have in hand. Whatever the model said about either loses.
        data["candidate_id"] = candidate_id
        data["window"] = window_for(results)
        data.setdefault("version", TREND_SCHEMA_VERSION)

        report = TrendReport(**data)
        self._log_unverified_quotes(report, results)

        payload = enforce_trend_no_dashes(report.model_dump(by_alias=True))
        self.repo.save_trend(candidate_id, payload)
        logger.info(
            "Trend report v%d saved for candidate %s: %d patterns, %d generated chars.",
            payload.get("version"),
            candidate_id,
            len(payload.get("patterns") or []),
            _generated_chars(payload),
        )
        return payload


def _generated_chars(payload: Dict[str, Any]) -> int:
    """Rough size of the prose the model wrote, for the v1 to v2 comparison.

    v1 ran to roughly eight thousand characters; v2 is meant to sit under two
    thousand. Logging it is how that stays true once real candidates are in it.
    """
    total = sum(len(str(payload.get(f, ""))) for f in REPORT_PROSE_FIELDS)
    for pattern in payload.get("patterns") or []:
        if isinstance(pattern, dict):
            total += sum(len(str(pattern.get(f, ""))) for f in PATTERN_PROSE_FIELDS)
    return total
