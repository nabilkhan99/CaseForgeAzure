"""
Supabase client for the Clinical Master backend.

Uses the service role key for backend operations (bypasses RLS).
"""

import logging
from supabase import create_client, Client
from ..config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_supabase_client() -> Client:
    """
    Get Supabase client with service role key for backend operations.
    
    Returns a singleton client instance.
    
    Raises:
        ValueError: If Supabase credentials are not configured.
    """
    global _client
    
    if _client is not None:
        return _client
    
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    
    if not url or not key:
        logger.error("Missing Supabase configuration. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables")
    
    _client = create_client(url, key)
    logger.info("Supabase client initialized successfully")
    return _client
