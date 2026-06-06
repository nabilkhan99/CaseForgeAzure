"""Trend service: cross-case development report for one candidate.

Source of truth: FF SCA Feedback Engine Build Package, Section 13. Reads the
persisted single-case outputs, asks the model for patterns, never re-grades a
case. Confidence is floored to low below three cases (Section 13.1); the no-dash
house rule is enforced before persistence.
"""
from __future__ import annotations

import logging
from typing import Any

from app.prompts.trend_prompt import build_trend_messages
from app.schemas.trend import TrendReport
from app.services.marking_service import ModelCall, parse_model_json
from app.utils.no_dashes import enforce_no_dashes

logger = logging.getLogger(__name__)

MIN_CASES_FOR_PATTERNS = 3


class TrendService:
    def __init__(self, repo: Any, model_call: ModelCall):
        self.repo = repo
        self.model_call = model_call

    async def _get_report_json(self, messages):
        raw = await self.model_call(messages)
        try:
            return parse_model_json(raw)
        except ValueError:
            logger.warning("Trend model returned malformed JSON; retrying once.")
            raw = await self.model_call(messages)
            return parse_model_json(raw)

    async def generate(self, candidate_id: str) -> dict:
        results = self.repo.get_candidate_results(candidate_id) or []
        messages = build_trend_messages(results, candidate_id)

        data = await self._get_report_json(messages)
        data.setdefault("candidate_id", candidate_id)
        report = TrendReport(**data)

        # Below three cases: provisional only, flagged low confidence (Section 13.1).
        if len(results) < MIN_CASES_FOR_PATTERNS:
            report.confidence = "low"

        payload = enforce_no_dashes(report.model_dump(by_alias=True))
        self.repo.save_trend(candidate_id, payload)
        return payload
