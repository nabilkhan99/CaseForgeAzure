"""Trend service: cross-case development report for one candidate.

Source of truth: FF SCA Feedback Engine Build Package, Section 13. Reads the
persisted single-case outputs, asks the model for patterns, never re-grades a
case. Confidence is floored to low below three cases (Section 13.1); the no-dash
house rule is enforced before persistence.

The case window is capped and each case is slimmed before it reaches the model
(see app/prompts/trend_prompt.py). A single oversized request was blowing the
marking deployment's per-minute token quota, so every trend request came back
429 while marking on the same deployment carried on fine.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from app.prompts.trend_prompt import MAX_TREND_CASES, build_trend_messages
from app.schemas.trend import TrendReport
from app.services.marking_service import ModelCall, parse_model_json
from app.utils.no_dashes import enforce_no_dashes

logger = logging.getLogger(__name__)

MIN_CASES_FOR_PATTERNS = 3

# Backoff schedule for a rate-limited model call: one retry, then give up and
# let the endpoint return the error. A trend report is not worth holding an
# Azure Functions HTTP request open for longer than this.
RATE_LIMIT_BACKOFF_SECONDS = (20.0,)


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

    async def generate(self, candidate_id: str) -> dict:
        results = self.repo.get_candidate_results(candidate_id, limit=MAX_TREND_CASES) or []
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
        data.setdefault("candidate_id", candidate_id)
        report = TrendReport(**data)

        # Below three cases: provisional only, flagged low confidence (Section 13.1).
        if len(results) < MIN_CASES_FOR_PATTERNS:
            report.confidence = "low"

        payload = enforce_no_dashes(report.model_dump(by_alias=True))
        self.repo.save_trend(candidate_id, payload)
        return payload
