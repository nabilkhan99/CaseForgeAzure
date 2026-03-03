"""
Session Repository

Repository for clinical session database operations.
Handles CRUD operations for sessions, results, and progress tracking.
"""

import logging
from datetime import datetime
from typing import Any, Optional
from supabase import Client

from .supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class SessionRepository:
    """Repository for clinical session database operations."""
    
    def __init__(self):
        self.client: Client = get_supabase_client()
    
    def get_station(self, station_id: str) -> Optional[dict]:
        """
        Get station details by ID.
        
        Args:
            station_id: UUID of the station
            
        Returns:
            Station data dict or None if not found
        """
        try:
            result = self.client.table("stations").select(
                "*, domains(id, name, description)"
            ).eq("id", station_id).eq("is_active", True).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Error fetching station {station_id}: {e}")
            return None
    
    def get_first_station(self) -> Optional[dict]:
        """
        Get the first active station (for demo/testing).
        
        Returns:
            Station data dict or None if no stations exist
        """
        try:
            result = self.client.table("stations").select(
                "*, domains(id, name, description)"
            ).eq("is_active", True).limit(1).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error fetching first station: {e}")
            return None
    
    def create_session(self, user_id: str, station_id: str) -> Optional[dict]:
        """
        Create a new clinical session.
        
        Args:
            user_id: UUID of the user
            station_id: UUID of the station
            
        Returns:
            Created session data dict
        """
        try:
            result = self.client.table("clinical_sessions").insert({
                "user_id": user_id,
                "station_id": station_id,
                "status": "reading"
            }).execute()
            logger.info(f"Created session {result.data[0]['id']} for user {user_id}")
            return result.data[0]
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None

    def upsert_session(self, session_id: str, user_id: Optional[str], station_id: str) -> Optional[dict]:
        """
        Ensure a clinical session exists with the given ID.
        Creates it if missing, no-op if it already exists.
        Accepts user_id=None for guest/anonymous sessions.
        """
        try:
            data: dict[str, Any] = {
                "id": session_id,
                "station_id": station_id,
                "status": "reading",
            }
            if user_id is not None:
                data["user_id"] = user_id
            
            result = self.client.table("clinical_sessions").upsert(
                data,
                on_conflict="id",
            ).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error upserting session {session_id}: {e}")
            return None

    def claim_session(self, session_id: str, user_id: str) -> bool:
        """
        Associate a guest/anonymous session with a newly-authenticated user.
        Only updates if the session currently has no user_id (NULL).
        
        Args:
            session_id: UUID of the session to claim
            user_id: UUID of the authenticated user
            
        Returns:
            True if the session was claimed successfully
        """
        try:
            result = self.client.table("clinical_sessions").update(
                {"user_id": user_id}
            ).eq("id", session_id).is_("user_id", "null").execute()
            
            if result.data:
                logger.info(f"Claimed session {session_id} for user {user_id}")
                return True
            else:
                logger.warning(f"Session {session_id} was not claimed — may already have a user")
                return False
        except Exception as e:
            logger.error(f"Error claiming session {session_id}: {e}")
            return False
    
    def update_session_status(self, session_id: str, status: str) -> bool:
        """
        Update session status.
        
        Args:
            session_id: UUID of the session
            status: New status (reading, live, processing, completed, abandoned)
            
        Returns:
            True if successful
        """
        try:
            update_data: dict[str, Any] = {"status": status}
            if status == "completed":
                update_data["completed_at"] = datetime.now().isoformat()
            
            self.client.table("clinical_sessions").update(update_data).eq("id", session_id).execute()
            logger.info(f"Updated session {session_id} status to {status}")
            return True
        except Exception as e:
            logger.error(f"Error updating session status: {e}")
            return False
    
    def save_transcript(self, session_id: str, transcript: list[dict]) -> bool:
        """
        Save session transcript.
        
        Args:
            session_id: UUID of the session
            transcript: List of transcript entries with role, content, timestamp
            
        Returns:
            True if successful
        """
        try:
            self.client.table("clinical_sessions").update({
                "transcript": transcript
            }).eq("id", session_id).execute()
            logger.info(f"Saved transcript for session {session_id} ({len(transcript)} entries)")
            return True
        except Exception as e:
            logger.error(f"Error saving transcript: {e}")
            return False
    
    def save_feedback(self, session_id: str, feedback: dict) -> bool:
        """
        Save session feedback/results.
        
        Expected feedback structure:
        {
            "data_gathering": { "score": int, "strengths": [], "improvements": [] },
            "clinical_management": { "score": int, "strengths": [], "improvements": [] },
            "interpersonal_skills": { "score": int, "strengths": [], "improvements": [] },
            "overall_summary": str,
            "key_learning_points": []
        }
        
        Args:
            session_id: UUID of the session
            feedback: Feedback data dict
            
        Returns:
            True if successful
        """
        try:
            # Extract scores
            data_gathering = feedback.get("data_gathering", {})
            clinical_management = feedback.get("clinical_management", {})
            interpersonal_skills = feedback.get("interpersonal_skills", {})
            
            # Insert into session_results
            self.client.table("session_results").insert({
                "session_id": session_id,
                "data_gathering_score": data_gathering.get("score", 0),
                "clinical_management_score": clinical_management.get("score", 0),
                "interpersonal_skills_score": interpersonal_skills.get("score", 0),
                "data_gathering_feedback": {
                    "strengths": data_gathering.get("strengths", []),
                    "improvements": data_gathering.get("improvements", [])
                },
                "clinical_management_feedback": {
                    "strengths": clinical_management.get("strengths", []),
                    "improvements": clinical_management.get("improvements", [])
                },
                "interpersonal_skills_feedback": {
                    "strengths": interpersonal_skills.get("strengths", []),
                    "improvements": interpersonal_skills.get("improvements", [])
                },
                "overall_summary": feedback.get("overall_summary", ""),
                "key_learning_points": feedback.get("key_learning_points", [])
            }).execute()
            
            # Update session status to completed with overall score
            overall = round(
                (data_gathering.get("score", 0) +
                clinical_management.get("score", 0) +
                interpersonal_skills.get("score", 0)) / 3
            )
            self.client.table("clinical_sessions").update({
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "overall_score": overall
            }).eq("id", session_id).execute()
            
            logger.info(f"Saved feedback for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving feedback: {e}")
            return False
    
    def get_session_with_results(self, session_id: str) -> Optional[dict]:
        """
        Get session with its results.
        
        Args:
            session_id: UUID of the session
            
        Returns:
            Session data with nested results
        """
        try:
            result = self.client.table("clinical_sessions").select(
                "*, stations(id, title, patient_name), session_results(*)"
            ).eq("id", session_id).single().execute()
            return result.data
        except Exception as e:
            logger.error(f"Error fetching session with results: {e}")
            return None
    
    def update_user_streak(self, user_id: str) -> bool:
        """
        Update user's login streak.
        
        Increments streak if last login was yesterday, resets if login gap.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            True if successful
        """
        try:
            today = datetime.now().date()
            
            # Get current profile
            result = self.client.table("profiles").select(
                "last_login_date, current_streak"
            ).eq("id", user_id).single().execute()
            
            profile = result.data
            last_login = profile.get("last_login_date")
            current_streak = profile.get("current_streak", 0)
            
            if last_login:
                from datetime import timedelta
                last_login_date = datetime.strptime(last_login, "%Y-%m-%d").date()
                days_diff = (today - last_login_date).days
                
                if days_diff == 0:
                    # Already logged in today, no update needed
                    return True
                elif days_diff == 1:
                    # Consecutive day, increment streak
                    current_streak += 1
                else:
                    # Gap in login, reset streak
                    current_streak = 1
            else:
                # First login ever
                current_streak = 1
            
            # Update profile
            self.client.table("profiles").update({
                "last_login_date": str(today),
                "current_streak": current_streak
            }).eq("id", user_id).execute()
            
            logger.info(f"Updated streak for user {user_id}: {current_streak} days")
            return True
        except Exception as e:
            logger.error(f"Error updating user streak: {e}")
            return False
    
    def update_domain_progress(self, user_id: str, domain_id: str, score: int, passed: bool) -> bool:
        """
        Update user's progress for a domain after completing a session.
        
        Args:
            user_id: UUID of the user
            domain_id: UUID of the domain
            score: Overall score for the session
            passed: Whether the session was passed
            
        Returns:
            True if successful
        """
        try:
            # Check if progress exists
            result = self.client.table("domain_progress").select("*").eq(
                "user_id", user_id
            ).eq("domain_id", domain_id).execute()
            
            now = datetime.now().isoformat()
            
            if result.data:
                # Update existing progress
                progress = result.data[0]
                new_attempts = progress["stations_attempted"] + 1
                new_passed = progress["stations_passed"] + (1 if passed else 0)
                # Rolling average
                new_avg = ((progress["average_score"] * progress["stations_attempted"]) + score) // new_attempts
                
                self.client.table("domain_progress").update({
                    "stations_attempted": new_attempts,
                    "stations_passed": new_passed,
                    "average_score": new_avg,
                    "last_attempt_at": now
                }).eq("id", progress["id"]).execute()
            else:
                # Create new progress
                self.client.table("domain_progress").insert({
                    "user_id": user_id,
                    "domain_id": domain_id,
                    "stations_attempted": 1,
                    "stations_passed": 1 if passed else 0,
                    "average_score": score,
                    "last_attempt_at": now
                }).execute()
            
            logger.info(f"Updated domain progress for user {user_id}, domain {domain_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating domain progress: {e}")
            return False
