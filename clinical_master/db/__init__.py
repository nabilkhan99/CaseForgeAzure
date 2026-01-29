"""
Database module for Clinical Master.
"""

from .supabase_client import get_supabase_client
from .session_repository import SessionRepository

__all__ = ["get_supabase_client", "SessionRepository"]
