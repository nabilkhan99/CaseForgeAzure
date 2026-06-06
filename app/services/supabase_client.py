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

    # ── trend layer reads (Phase 8) ──
    def get_candidate_results(self, candidate_id: str) -> List[Dict[str, Any]]:
        """Persisted single-case results for a candidate, oldest first."""
        res = (
            self.client.table("session_results")
            .select(
                "session_id, verdict, weighted_score, domains, focus_areas, "
                "capability_links, conditional_features, created_at, "
                "clinical_sessions(station_id, user_id, completed_at, stations(title))"
            )
            .eq("clinical_sessions.user_id", candidate_id)
            .order("created_at", desc=False)
            .execute()
        )
        return res.data or []
