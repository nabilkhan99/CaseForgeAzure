"""Supabase access for the SCA marking + trend pipeline (service role).

Thin data layer behind the marking and trend services so their logic stays
unit-testable. Reads stations + clinical_sessions, writes session_results and
session status. Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from app.config import Settings


def get_client(settings: Settings) -> Client:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionRepository:
    """Concrete repo used by MarkingService; mirrors the FakeRepo used in tests."""

    def __init__(self, client: Client):
        self.client = client

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        res = (
            self.client.table("clinical_sessions")
            .select("id, user_id, station_id, status, transcript")
            .eq("id", session_id)
            .maybe_single()
            .execute()
        )
        return res.data if res else None

    def get_station(self, station_id: str) -> Optional[Dict[str, Any]]:
        res = (
            self.client.table("stations")
            .select("*")
            .eq("id", station_id)
            .maybe_single()
            .execute()
        )
        return res.data if res else None

    def save_results(self, session_id: str, payload: Dict[str, Any]) -> None:
        overall = payload.get("overall", {})
        row = {
            "session_id": session_id,
            "verdict": overall.get("verdict"),
            "weighted_score": overall.get("weighted_score"),
            "max_score": overall.get("max_score"),
            "one_line_summary": overall.get("one_line_summary"),
            "tier3_override_applied": overall.get("tier3_override_applied"),
            "domains": payload.get("domains"),
            "timing": payload.get("timing"),
            "focus_areas": payload.get("focus_areas"),
            "capability_links": payload.get("capability_links"),
            "confidence": payload.get("confidence"),
            "evidence_map": payload.get("evidence_map"),
            "conditional_features": payload.get("conditional_features"),
        }
        self.client.table("session_results").upsert(row, on_conflict="session_id").execute()

    def mark_completed(self, session_id: str, overall_score: int) -> None:
        self.client.table("clinical_sessions").update(
            {"status": "completed", "overall_score": overall_score, "completed_at": _now_iso()}
        ).eq("id", session_id).execute()

    def mark_errored(self, session_id: str) -> None:
        self.client.table("clinical_sessions").update({"status": "error"}).eq(
            "id", session_id
        ).execute()

    # ── trend layer (v2 contract, app/schemas/trend.py) ──
    def save_trend(self, candidate_id: str, payload: Dict[str, Any]) -> None:
        """Write the one live trend report for this candidate.

        The v1 columns are nulled rather than left alone. This is an upsert on
        candidate_id, so a row that predates v2 would otherwise keep serving its
        recurring_themes and its caution alongside fresh v2 patterns, and the
        frontend would have no way to tell which half was current.
        """
        row = {
            "candidate_id": candidate_id,
            "version": payload.get("version"),
            "window": payload.get("window"),
            "overall_trajectory": payload.get("overall_trajectory"),
            "overall_narrative": payload.get("overall_narrative"),
            "patterns": payload.get("patterns"),
            # Retired by the v2 contract; columns kept by migration 0005 only so
            # an in-flight frontend does not read a missing column.
            "confidence": None,
            "recurring_themes": [],
            "style_patterns": [],
            "consistent_strengths": [],
            "next_steps": [],
            "caution": None,
        }
        # One live report per candidate (trend_reports_candidate_unique, added in
        # 0003): a rebuild replaces the old row instead of accumulating history,
        # and two concurrent rebuilds converge on it rather than duplicating.
        self.client.table("trend_reports").upsert(
            row, on_conflict="candidate_id"
        ).execute()

    def get_candidate_results(
        self, candidate_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Persisted single-case results for a candidate, oldest first.

        Two things worth knowing about the query:

        - The embed is ``clinical_sessions!inner``. A PostgREST filter on a plain
          embed filters the *embedded* rows, not the top level ones, so without
          the inner join this returned every session_results row in the table
          with a null embed on the ones that did not match. The trend prompt was
          therefore being handed every candidate's cases, not this candidate's.
        - ``limit`` bounds the window (see MAX_TREND_CASES). Newest first so the
          limit keeps the most recent cases, then reversed back to oldest first
          because that is the order the trend prompt documents.
        """
        query = (
            self.client.table("session_results")
            .select(
                "session_id, verdict, weighted_score, one_line_summary, domains, "
                "focus_areas, capability_links, conditional_features, created_at, "
                "clinical_sessions!inner(station_id, user_id, completed_at, stations(title))"
            )
            .eq("clinical_sessions.user_id", candidate_id)
            .order("created_at", desc=True)
        )
        if limit is not None:
            query = query.limit(limit)
        res = query.execute()
        return list(reversed(res.data or []))
