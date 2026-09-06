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
import os
import re
from datetime import datetime, timezone
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


# ── unmarkable transcripts ───────────────────────────────────────────────────
# A consultation that never really happened must not be graded. Seven
# session_results rows sit on transcripts of two turns or fewer, and one
# single-turn transcript came back "Fail 3.5" with detailed commentary on a
# consultation the candidate had not had. Below either threshold the model is
# never called, no result row is written, and the session is parked as
# 'unmarkable' (migration 0007) with its marking claim released. Trial
# consumption is counted from session_results rows, so such a sitting is free.


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name) or default)
    except ValueError:
        return default


MIN_CANDIDATE_TURNS = _env_int("MIN_CANDIDATE_TURNS", 6)
MIN_CANDIDATE_SECONDS = _env_float("MIN_CANDIDATE_SECONDS", 90.0)


class UnmarkableTranscript(Exception):
    """Raised instead of marking when the transcript is too thin to grade.

    Carries the measurements so the HTTP layer can return the agreed contract
    body (status 200, ``{"status": "unmarkable", ...}``) rather than an error
    the frontend would have to guess at.
    """

    def __init__(
        self,
        candidate_turns: int,
        candidate_seconds: float,
        reason: str = "too_short",
    ):
        self.candidate_turns = candidate_turns
        self.candidate_seconds = candidate_seconds
        self.reason = reason
        super().__init__(
            f"transcript too thin to mark: {candidate_turns} candidate turns over "
            f"{candidate_seconds:.1f}s"
        )

    def to_response(self) -> Dict[str, Any]:
        return {
            "status": "unmarkable",
            "candidate_turns": self.candidate_turns,
            "candidate_seconds": self.candidate_seconds,
            "reason": self.reason,
        }


def _is_candidate_turn(turn: Any) -> bool:
    """True for a turn the marker would render as "Candidate:" with words in it.

    Mirrors format_transcript (app/prompts/marking_prompt.py): the spec shape
    labels by ``speaker``, the legacy shape by ``role``, and a turn with no text
    is dropped before the model ever sees it, so it cannot count as evidence
    that the candidate spoke.
    """
    if not isinstance(turn, dict):
        return False
    speaker = turn.get("speaker")
    if speaker is not None:
        is_candidate = speaker == "candidate"
    else:
        is_candidate = turn.get("role") == "user"
    if not is_candidate:
        return False
    return bool(str(turn.get("text") or turn.get("content") or "").strip())


def _as_ms(value: Any) -> Optional[float]:
    """A millisecond offset as a float, or None when the field is absent or junk."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _as_epoch_seconds(value: Any) -> Optional[float]:
    """Parse the legacy shape's ISO 8601 ``timestamp`` to epoch seconds."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _span(values: List[float]) -> Optional[float]:
    return max(values) - min(values) if len(values) >= 2 else None


def _candidate_span_seconds(turns: List[Dict[str, Any]]) -> Optional[float]:
    """Seconds from the first candidate turn to the last, or None if untimed.

    Live turns carry two independent clocks: the spec shape's millisecond
    offsets from the start of the session, and the legacy shape's absolute ISO
    wall clock. They are measured separately and never mixed, because a span
    taken across both is a number with no meaning.

    Where both survive we take the longer. The offsets come from realtime VAD
    events and go missing on individual turns, so a mostly untimed twelve minute
    consultation can show two adjacent offsets and look like ten seconds; the
    ISO stamp is written on every turn. Reading the more generous clock means a
    thin clock can never fabricate a short consultation, and neither clock can
    overstate one.
    """
    offsets_ms = [
        ms
        for turn in turns
        for ms in (_as_ms(turn.get("start_ms")), _as_ms(turn.get("end_ms")))
        if ms is not None
    ]
    stamps_s = [
        s
        for s in (_as_epoch_seconds(turn.get("timestamp")) for turn in turns)
        if s is not None
    ]
    offset_span = _span(offsets_ms)
    candidates = [s for s in (
        offset_span / 1000.0 if offset_span is not None else None,
        _span(stamps_s),
    ) if s is not None]
    return max(candidates) if candidates else None


def evaluate_transcript(transcript: Any) -> Dict[str, Any]:
    """Measure a transcript against the unmarkable thresholds.

    Returns the two numbers the HTTP contract reports plus whether marking
    should be refused. A transcript with no usable clock is judged on turn count
    alone: older rows carry no timings, and failing them for that would be a
    regression dressed up as a guard.
    """
    turns = [turn for turn in (transcript or []) if _is_candidate_turn(turn)]
    seconds = _candidate_span_seconds(turns)
    too_few = len(turns) < MIN_CANDIDATE_TURNS
    too_short = seconds is not None and seconds < MIN_CANDIDATE_SECONDS
    return {
        "candidate_turns": len(turns),
        "candidate_seconds": round(seconds, 1) if seconds is not None else 0.0,
        "unmarkable": too_few or too_short,
    }


DOMAIN_DISPLAY = {
    "data_gathering": "Data gathering and diagnosis",
    "clinical_management": "Clinical management and medical complexity",
    "relating_to_others": "Relating to others",
}
_VALID_SOURCES = {"learning_points", "rcgp_educator_notes", "nice", "sign", "curriculum"}
_VALID_EVIDENCE_KINDS = {"supporting_quote", "patient_cue", "not_asked", "no_direct_quote"}
_GENERIC_OPENING_PATTERNS = (
    "tell me what's wrong",
    "tell me what is wrong",
    "what can i do for you",
    "what seems to be the problem",
    "how can i help",
)


def _parse_ts(value: Any) -> Optional[int]:
    """Parse a timestamp (mm:ss string, numeric string, or int ms) to milliseconds."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if ":" in s:
        parts = s.split(":")
        try:
            mm, ss = int(parts[0]), int(parts[1])
            return (mm * 60 + ss) * 1000
        except (ValueError, IndexError):
            return None
    return int(s) if s.isdigit() else None


def _looks_like_non_evidence_quote(quote: Any) -> bool:
    """Return true for generic doctor openers that do not evidence an omission."""
    if not isinstance(quote, str):
        return True
    q = quote.strip().lower()
    if len(q) < 44:
        return True
    return any(pattern in q for pattern in _GENERIC_OPENING_PATTERNS)


def _absence_evidence(status: str | None = None) -> dict:
    return {
        "evidence_kind": "not_asked" if status == "not_met" else "no_direct_quote",
        "quote": None,
        "timestamp_ms": None,
        "speaker": None,
    }


def _domain_key(name: str) -> str:
    low = (name or "").lower()
    if "data gathering" in low or "diagnosis" in low:
        return "data_gathering"
    if "management" in low or "complexity" in low:
        return "clinical_management"
    if "relating" in low or "interpersonal" in low:
        return "relating_to_others"
    return name


def _norm_item(it: dict, *, missed: bool = False, cue: bool = False) -> dict:
    it = dict(it)
    ts = it.pop("timestamp", None)
    quote = it.get("quote")
    ev = it.get("evidence")
    if isinstance(ev, str):
        it["evidence"] = {"quote": ev}
    if isinstance(it.get("evidence"), dict):
        e = it["evidence"]
        if not e.get("quote") and isinstance(quote, str):
            e["quote"] = quote
        if e.get("timestamp_ms") is None:
            e["timestamp_ms"] = _parse_ts(e.pop("timestamp", None) or ts)
        if e.get("evidence_kind") not in _VALID_EVIDENCE_KINDS:
            e["evidence_kind"] = "patient_cue" if cue else "supporting_quote"
    elif isinstance(quote, str):
        it["evidence"] = {
            "evidence_kind": "patient_cue" if cue else "supporting_quote",
            "quote": quote,
            "timestamp_ms": _parse_ts(ts),
        }
    if not it.get("narrative"):
        it["narrative"] = (
            it.get("point") or it.get("comment") or it.get("detail")
            or it.get("text") or it.get("description") or ""
        )
    if not cue and not it.get("label"):
        it["label"] = (
            it.get("indicator") or it.get("title") or it.get("indicator_id")
            or (it["narrative"][:60] if it.get("narrative") else "point")
        )
    if missed:
        it["status"] = it["status"] if it.get("status") in ("partial", "not_met") else "not_met"
        try:
            ct = int(it.get("consequence_tier", 1))
        except (TypeError, ValueError):
            ct = 1
        it["consequence_tier"] = max(0, min(3, ct or 1))
        ev = it.get("evidence")
        if not isinstance(ev, dict) or _looks_like_non_evidence_quote(ev.get("quote")):
            it["evidence"] = _absence_evidence(it.get("status"))
        elif ev.get("evidence_kind") == "supporting_quote":
            ev["evidence_kind"] = "patient_cue"
    if cue:
        it["status"] = it["status"] if it.get("status") in ("explored", "missed") else "missed"
        if not it.get("cue"):
            it["cue"] = it.get("label") or it.get("title") or (it.get("narrative", "")[:60] or "cue")
        if not isinstance(it.get("evidence"), dict):
            it["evidence"] = _absence_evidence()
        else:
            it["evidence"]["evidence_kind"] = "patient_cue"
    elif not missed and not isinstance(it.get("evidence"), dict):
        # Strengths should be quote-backed where possible, but tolerate older or
        # imperfect model output without failing the whole marking run.
        it["evidence"] = None
    return it


def normalize_feedback(data: dict) -> dict:
    """Coerce a loosely-shaped model response into the Section 12 schema.

    Models often return domain display names instead of keys, evidence as a bare
    string with a sibling timestamp, and grade_mover / model_moment /
    how_to_improve / anchored_statements as strings. This maps those variants onto
    the strict schema before pydantic validation.
    """
    d = dict(data)
    out_domains = []
    for dom in d.get("domains") or []:
        if not isinstance(dom, dict):
            continue
        dom = dict(dom)
        orig = str(dom.get("domain", ""))
        key = _domain_key(orig)
        dom["domain"] = key
        if not dom.get("display_name"):
            dom["display_name"] = DOMAIN_DISPLAY.get(key, orig or key)
        if isinstance(dom.get("what_you_did_well"), list):
            dom["what_you_did_well"] = [_norm_item(x) for x in dom["what_you_did_well"] if isinstance(x, dict)]
        if isinstance(dom.get("what_you_missed"), list):
            dom["what_you_missed"] = [_norm_item(x, missed=True) for x in dom["what_you_missed"] if isinstance(x, dict)]
        if isinstance(dom.get("cue_handling"), list):
            dom["cue_handling"] = [_norm_item(x, cue=True) for x in dom["cue_handling"] if isinstance(x, dict)]
        if isinstance(dom.get("anchored_statements"), list):
            dom["anchored_statements"] = [
                {"title": a} if isinstance(a, str) else a for a in dom["anchored_statements"]
            ]
        gm = dom.get("grade_mover")
        if isinstance(gm, str):
            dom["grade_mover"] = {"narrative": gm}
        mm = dom.get("model_moment")
        if isinstance(mm, str):
            dom["model_moment"] = {"narrative": mm, "source": "learning_points"}
        elif isinstance(mm, dict) and mm.get("source") not in _VALID_SOURCES:
            mm["source"] = "learning_points"
        if isinstance(dom.get("how_to_improve"), list):
            improved = []
            for h in dom["how_to_improve"]:
                if isinstance(h, str):
                    improved.append({"narrative": h, "source": "learning_points"})
                elif isinstance(h, dict):
                    h = dict(h)
                    if not h.get("narrative"):
                        h["narrative"] = h.get("text") or h.get("suggestion") or ""
                    if h.get("source") not in _VALID_SOURCES:
                        h["source"] = "learning_points"
                    improved.append(h)
            dom["how_to_improve"] = improved
        out_domains.append(dom)
    d["domains"] = out_domains

    # evidence_map is a write-only audit blob. Models return it as a flat list
    # of records OR as an object keyed by section; both are fine and are stored
    # as-is. Anything else is dropped rather than allowed to fail validation —
    # a diagnostic field must never cost us the verdict and the domain grades.
    em = d.get("evidence_map")
    if not isinstance(em, (list, dict)):
        d["evidence_map"] = []
    elif isinstance(em, list):
        d["evidence_map"] = [x for x in em if isinstance(x, dict)]

    c = d.get("confidence")
    if isinstance(c, str):
        d["confidence"] = {"transcript_quality": c if c in ("high", "medium", "low") else "high", "notes": ""}
    elif isinstance(c, dict):
        if c.get("transcript_quality") not in ("high", "medium", "low"):
            c["transcript_quality"] = "high"
        c.setdefault("notes", "")
    else:
        d["confidence"] = {"transcript_quality": "high", "notes": ""}

    if isinstance(d.get("focus_areas"), list):
        areas = []
        for i, f in enumerate(d["focus_areas"], 1):
            if isinstance(f, str):
                areas.append({"priority": i, "label": f[:60], "narrative": f, "domain": ""})
                continue
            if not isinstance(f, dict):
                continue
            f = dict(f)
            try:
                f["priority"] = int(f.get("priority", i))
            except (TypeError, ValueError):
                f["priority"] = i
            if not f.get("label"):
                f["label"] = (f.get("narrative", "") or "focus")[:60]
            if not f.get("narrative"):
                f["narrative"] = f.get("label", "")
            f["domain"] = _domain_key(str(f.get("domain", "") or ""))
            areas.append(f)
        d["focus_areas"] = areas

    if not isinstance(d.get("capability_links"), list):
        d["capability_links"] = []
    o = d.get("overall")
    if isinstance(o, dict):
        o.setdefault("one_line_summary", o.get("summary", ""))
    return d


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

        # Before anything costs money: is there a consultation here at all?
        measure = evaluate_transcript(session.get("transcript"))
        if measure["unmarkable"]:
            logger.warning(
                "marking.unmarkable session_id=%s candidate_turns=%d "
                "candidate_seconds=%.1f min_turns=%d min_seconds=%.1f reason=too_short",
                session_id,
                measure["candidate_turns"],
                measure["candidate_seconds"],
                MIN_CANDIDATE_TURNS,
                MIN_CANDIDATE_SECONDS,
            )
            # Park the session and release the marking claim, so a proper re-run
            # of the same case can take a fresh claim without waiting out the
            # ten minute stale TTL in the frontend's generate-feedback route.
            self.repo.mark_unmarkable(session_id)
            raise UnmarkableTranscript(
                candidate_turns=measure["candidate_turns"],
                candidate_seconds=measure["candidate_seconds"],
            )

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
            fb = SingleCaseFeedback(**normalize_feedback(data))
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
        # Stamped from the session row, and stamped *after* the no-dash pass:
        # that pass rewrites every string in the payload, and a UUID with its
        # hyphens rewritten is not a UUID. The post-marking trend rebuild reads
        # this to know whose report to build, so it has to be the real id, and
        # the session row is a better source for it than the model's echo.
        payload["candidate_id"] = session.get("user_id")
        # Persist which conditional features were in play, for the trend layer and audit
        # (Build Package action item 11). Not part of the candidate-facing schema.
        payload["conditional_features"] = case_pack.get("conditional_features")
        self.repo.save_results(session_id, payload)
        self.repo.mark_completed(session_id, int(round(verdict["weighted_score"])))
        return payload
