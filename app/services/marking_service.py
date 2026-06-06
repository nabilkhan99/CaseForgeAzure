"""Marking service: transcript + case pack in, validated spec feedback out.

Source of truth: FF SCA Feedback Engine Build Package, Part 1. The verdict is
recomputed server side from the domain grades (Section 8) so the model's own
arithmetic is never trusted; a Tier 3 missed item caps the case at Fail; the
no-dash house rule (Section 9.3) is enforced before persistence.

I/O is injected (a repo and an async model_call) so the orchestration logic is
unit-testable without a database or a live model.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.prompts.marking_prompt import build_marking_messages
from app.schemas.feedback import SingleCaseFeedback
from app.utils.no_dashes import enforce_no_dashes
from app.utils.verdict import compute_verdict

logger = logging.getLogger(__name__)

ModelCall = Callable[[List[Dict[str, str]]], Awaitable[str]]
REQUIRED_DOMAINS = ("data_gathering", "clinical_management", "relating_to_others")


def parse_model_json(raw: str) -> dict:
    """Parse a model response into a dict, tolerating code fences and stray prose."""
    if not raw or not raw.strip():
        raise ValueError("empty model response")
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s).strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model response")
    try:
        return json.loads(s[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc


def build_case_pack(station: Dict[str, Any]) -> Dict[str, Any]:
    """Map the stations table row onto the four-part case pack the marker expects."""
    return {
        "candidate_brief": station.get("candidate_instructions") or "",
        "patient_script": station.get("station_script") or "",
        "mark_scheme_prose": {
            "data_gathering": station.get("data_gathering") or "",
            "clinical_management": station.get("clinical_management") or "",
            "relating_to_others": station.get("relating_to_others") or "",
        },
        "mark_scheme_structured": station.get("mark_scheme_structured"),
        "learning_points": station.get("clinical_learning_points") or "",
        "case_type": station.get("case_type"),
        "conditional_features": station.get("conditional_features"),
    }


def model_supports_temperature(deployment: str) -> bool:
    """GPT-5 family and o-series reasoning models only accept the default temperature."""
    name = (deployment or "").lower()
    if name.startswith(("o1", "o3", "o4")):
        return False
    if "gpt-5" in name:
        return False
    return True


def make_azure_model_call(
    client: Any, deployment: str, temperature: Optional[float] = 0.2
) -> ModelCall:
    """Build an async model_call bound to an AsyncAzureOpenAI client and deployment.

    `temperature` is included only when not None, so the same factory works for
    classic models (gpt-4.1) and reasoning models (gpt-5.x, o-series) that reject
    a custom temperature.
    """

    async def _call(messages: List[Dict[str, str]]) -> str:
        kwargs: Dict[str, Any] = {
            "model": deployment,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = await client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    return _call


class MarkingService:
    """Grades one completed consultation and persists the spec feedback object."""

    def __init__(self, repo: Any, model_call: ModelCall):
        self.repo = repo
        self.model_call = model_call

    async def _get_feedback_json(self, messages: List[Dict[str, str]]) -> dict:
        raw = await self.model_call(messages)
        try:
            return parse_model_json(raw)
        except ValueError:
            # One retry on a malformed response (README model/API notes).
            logger.warning("Marking model returned malformed JSON; retrying once.")
            raw = await self.model_call(messages)
            return parse_model_json(raw)

    async def mark(self, session_id: str) -> dict:
        session = self.repo.get_session(session_id)
        if not session:
            raise ValueError(f"session not found: {session_id}")

        station = self.repo.get_station(session.get("station_id"))
        if not station:
            self.repo.mark_errored(session_id)
            raise ValueError(f"station not found for session {session_id}")

        case_pack = build_case_pack(station)
        ids = {
            "session_id": session_id,
            "candidate_id": session.get("user_id"),
            "case_id": station.get("id"),
        }
        messages = build_marking_messages(case_pack, session.get("transcript") or [], ids)

        try:
            data = await self._get_feedback_json(messages)
            data.setdefault("session_id", session_id)
            fb = SingleCaseFeedback(**data)
        except Exception:
            self.repo.mark_errored(session_id)
            raise

        grades = {d.domain: d.grade for d in fb.domains}
        missing = [d for d in REQUIRED_DOMAINS if d not in grades]
        if missing:
            self.repo.mark_errored(session_id)
            raise ValueError(f"missing domain grades: {missing}")

        has_tier3 = any(
            m.consequence_tier == 3 for d in fb.domains for m in d.what_you_missed
        )
        verdict = compute_verdict(
            grades["data_gathering"],
            grades["clinical_management"],
            grades["relating_to_others"],
            has_tier3=has_tier3,
        )
        fb.overall.verdict = verdict["verdict"]
        fb.overall.weighted_score = verdict["weighted_score"]
        fb.overall.max_score = verdict["max_score"]
        fb.overall.tier3_override_applied = verdict["tier3_override_applied"]

        payload = enforce_no_dashes(fb.model_dump())
        # Persist which conditional features were in play, for the trend layer and audit
        # (Build Package action item 11). Not part of the candidate-facing schema.
        payload["conditional_features"] = case_pack.get("conditional_features")
        self.repo.save_results(session_id, payload)
        self.repo.mark_completed(session_id, int(round(verdict["weighted_score"])))
        return payload
